from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException


HashText = Callable[[str], str]
DecodePreviewBytes = Callable[[bytes], str]
ArchiveExtractor = Callable[..., List[Dict[str, Any]]]
NormalizeText = Callable[[Any], str]
WarningLogger = Callable[..., None]
InfoLogger = Callable[..., None]
StatusSetter = Callable[[str, str], None]

MAX_UPLOAD_CONTENT_BYTES = 50 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 512
MAX_ARCHIVE_MEMBER_BYTES = 20 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 80 * 1024 * 1024
MAX_SUBTITLE_FILES = 100


@dataclass(frozen=True)
class ArchiveResourceLimits:
    max_content_bytes: int = MAX_UPLOAD_CONTENT_BYTES
    max_archive_members: int = MAX_ARCHIVE_MEMBERS
    max_archive_member_bytes: int = MAX_ARCHIVE_MEMBER_BYTES
    max_archive_total_bytes: int = MAX_ARCHIVE_TOTAL_BYTES
    max_subtitle_files: int = MAX_SUBTITLE_FILES


DEFAULT_ARCHIVE_RESOURCE_LIMITS = ArchiveResourceLimits()


class ArchiveResourceLimitError(ValueError):
    """Raised when uploaded content or extracted archive data exceeds policy limits."""


def _default_normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _default_decode_preview_bytes(raw: bytes) -> str:
    try:
        return (raw or b"").decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _size_label(size: int) -> str:
    return f"{size} bytes"


def validate_upload_content_size(
    source_name: str,
    content_size: int,
    limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
) -> None:
    if content_size > limits.max_content_bytes:
        name = source_name or "上传内容"
        raise ArchiveResourceLimitError(
            f"上传内容大小超过限制: {name} "
            f"{_size_label(content_size)} > {_size_label(limits.max_content_bytes)}"
        )


class ArchiveResourceGuard:
    def __init__(
        self,
        source_name: str,
        limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
    ) -> None:
        self._source_name = source_name or "压缩包"
        self._limits = limits
        self._member_count = 0
        self._subtitle_count = 0
        self._total_size = 0

    def count_member(self, member_name: str) -> None:
        self._member_count += 1
        if self._member_count > self._limits.max_archive_members:
            raise ArchiveResourceLimitError(
                f"压缩包成员数量超过限制: {self._source_name} "
                f"{self._member_count} > {self._limits.max_archive_members}"
            )

    def check_member_size(self, member_name: str, member_size: int) -> None:
        if member_size > self._limits.max_archive_member_bytes:
            raise ArchiveResourceLimitError(
                f"压缩包单文件大小超过限制: {member_name or self._source_name} "
                f"{_size_label(member_size)} > {_size_label(self._limits.max_archive_member_bytes)}"
            )

    def accept_subtitle(self, member_name: str, member_size: int) -> None:
        self.check_member_size(member_name, member_size)
        self._subtitle_count += 1
        if self._subtitle_count > self._limits.max_subtitle_files:
            raise ArchiveResourceLimitError(
                f"压缩包字幕文件数量超过限制: {self._source_name} "
                f"{self._subtitle_count} > {self._limits.max_subtitle_files}"
            )
        self._total_size += member_size
        if self._total_size > self._limits.max_archive_total_bytes:
            raise ArchiveResourceLimitError(
                f"压缩包总解压大小超过限制: {self._source_name} "
                f"{_size_label(self._total_size)} > {_size_label(self._limits.max_archive_total_bytes)}"
            )


def archive_suffix_from_content(content: bytes) -> str:
    head = (content or b"")[:8]
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06") or head.startswith(b"PK\x07\x08"):
        return ".zip"
    if head.startswith(b"Rar!\x1a\x07"):
        return ".rar"
    if head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return ".7z"
    return ""


def is_executable_file(path: Path) -> bool:
    try:
        return path.is_file() and os.access(path, os.X_OK)
    except Exception:
        return False


def _is_unar_executable(path: Any) -> bool:
    if not path:
        return False
    candidate = Path(str(path))
    return candidate.name.lower() == "unar" and is_executable_file(candidate)


def find_rar_tool(
    *,
    configured_tool_path: Any,
    normalize_text: NormalizeText,
    rar_tools: Iterable[str],
) -> str:
    configured = normalize_text(configured_tool_path)
    if _is_unar_executable(configured):
        return str(Path(configured))
    for tool in rar_tools:
        if Path(str(tool)).name.lower() != "unar":
            continue
        found = shutil.which(tool)
        if _is_unar_executable(found):
            return found
    return ""


def find_lsar_tool(unar_tool_path: str) -> str:
    unar_path = Path(unar_tool_path)
    if unar_path.name.lower() != "unar":
        return ""
    sibling = unar_path.with_name("lsar")
    if is_executable_file(sibling):
        return str(sibling)
    found = shutil.which("lsar")
    return found or ""


def find_sevenzip_tool(
    *,
    configured_tool_path: Any,
    normalize_text: NormalizeText,
    sevenzip_tools: Iterable[str],
) -> str:
    configured = normalize_text(configured_tool_path)
    if _is_unar_executable(configured):
        return str(Path(configured))
    for tool in sevenzip_tools:
        if Path(str(tool)).name.lower() != "unar":
            continue
        found = shutil.which(tool)
        if _is_unar_executable(found):
            return found
    return ""


class ArchiveDependencyService:
    def __init__(
        self,
        *,
        rar_dependency_mode: str,
        rar_tool_path: str,
        rar_python_package: str,
        rar_tools: Iterable[str],
        sevenzip_tools: Iterable[str],
        normalize_text: NormalizeText,
        decode_preview_bytes: DecodePreviewBytes,
        subprocess_module: Any = subprocess,
        logger_info: Optional[InfoLogger] = None,
        logger_warning: Optional[WarningLogger] = None,
        status_setter: Optional[StatusSetter] = None,
    ) -> None:
        self._rar_dependency_mode = rar_dependency_mode
        self._rar_tool_path = rar_tool_path
        self._rar_python_package = rar_python_package
        self._rar_tools = tuple(rar_tools)
        self._sevenzip_tools = tuple(sevenzip_tools)
        self._normalize_text = normalize_text
        self._decode_preview_bytes = decode_preview_bytes
        self._subprocess = subprocess_module
        self._logger_info = logger_info
        self._logger_warning = logger_warning
        self._status_setter = status_setter

    def dependency_status(self, state: str, message: str) -> Dict[str, Any]:
        return {
            "mode": self._rar_dependency_mode,
            "state": state,
            "message": message,
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "tool_path": self._rar_tool_path,
        }

    def set_dependency_status(self, state: str, message: str) -> None:
        if self._status_setter:
            self._status_setter(state, message)

    def prepare_rar_dependency(self) -> None:
        if self._rar_dependency_mode == "none":
            self.set_dependency_status("skipped", "未启用 RAR 解压器自动处理，将只检测现有 unar")
            return

        if self.rar_tool():
            self.set_dependency_status("ready", "已检测到可用 RAR 解压器")
            return

        if self._rar_dependency_mode == "mapped_binary":
            self.set_dependency_status(
                "missing",
                f"未检测到映射文件，请把宿主机 unar 映射到容器 {self._rar_tool_path}",
            )
            self._log_info("[SubtitleManualUpload] RAR 映射模式未检测到工具 path=%s", self._rar_tool_path)
            return

        if self._rar_dependency_mode == "container_install":
            self.install_container_rar_tool()
            return

        self.set_dependency_status("skipped", "未知 RAR 依赖处理方式")

    def install_container_rar_tool(self) -> None:
        self._log_info("[SubtitleManualUpload] 开始尝试在容器内安装 RAR 解压器")
        install_script = r"""
set -eu
if command -v unar >/dev/null 2>&1; then
  exit 0
fi
if ! command -v apt-get >/dev/null 2>&1; then
  echo "当前容器没有 apt-get，无法自动安装，请使用宿主机 unar 映射" >&2
  exit 78
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends unar
"""
        try:
            completed = self._subprocess.run(
                ["sh", "-lc", install_script],
                stdout=self._subprocess.PIPE,
                stderr=self._subprocess.PIPE,
                check=True,
                timeout=600,
            )
        except self._subprocess.TimeoutExpired:
            self.set_dependency_status("failed", "容器内安装 RAR 解压器超时")
            self._log_warning("[SubtitleManualUpload] 容器内安装 RAR 解压器超时")
            return
        except self._subprocess.CalledProcessError as exc:
            stderr = self._decode_preview_bytes(exc.stderr or b"").strip()
            message = stderr[-500:] if stderr else str(exc)
            self.set_dependency_status("failed", f"容器内安装失败: {message}")
            self._log_warning(
                "[SubtitleManualUpload] 容器内安装 RAR 解压器失败 returncode=%s error=%s",
                exc.returncode,
                message,
            )
            return

        stdout = self._decode_preview_bytes(completed.stdout or b"").strip()
        tool_path = self.rar_tool()
        if tool_path:
            self.set_dependency_status("ready", f"容器内安装完成，当前工具: {Path(tool_path).name}")
            self._log_info(
                "[SubtitleManualUpload] 容器内安装 RAR 解压器完成 tool=%s output_tail=%s",
                Path(tool_path).name,
                stdout[-300:],
            )
            return

        self.set_dependency_status("failed", "安装命令结束，但仍未检测到 unar")
        self._log_warning("[SubtitleManualUpload] 容器内安装后仍未检测到 RAR 解压器")

    def rar_tool(self) -> str:
        return find_rar_tool(
            configured_tool_path=self._rar_tool_path,
            normalize_text=self._normalize_text,
            rar_tools=self._rar_tools,
        )

    def sevenzip_tool(self) -> str:
        return find_sevenzip_tool(
            configured_tool_path=self._rar_tool_path,
            normalize_text=self._normalize_text,
            sevenzip_tools=self._sevenzip_tools,
        )

    def rar_python_available(self) -> bool:
        return rar_python_available(self._rar_python_package)

    def rarfile_module(self) -> Any:
        return rarfile_module(self._rar_python_package)

    def run_archive_command(self, args: List[str], timeout: int = 120) -> bytes:
        return run_archive_command(args, decode_preview_bytes=self._decode_preview_bytes, timeout=timeout)

    def list_rar_members(self, archive_path: Path, tool_path: str) -> List[str]:
        return list_rar_members(
            archive_path,
            tool_path,
            decode_preview_bytes=self._decode_preview_bytes,
            run_command=self.run_archive_command,
        )

    def read_rar_member(self, archive_path: Path, member: str, tool_path: str) -> bytes:
        return read_rar_member(
            archive_path,
            member,
            tool_path,
            run_command=self.run_archive_command,
        )

    def _log_info(self, *args: Any, **kwargs: Any) -> None:
        if self._logger_info:
            self._logger_info(*args, **kwargs)

    def _log_warning(self, *args: Any, **kwargs: Any) -> None:
        if self._logger_warning:
            self._logger_warning(*args, **kwargs)


def rar_python_available(rar_python_package: str) -> bool:
    return importlib.util.find_spec(rar_python_package) is not None


def rarfile_module(rar_python_package: str) -> Any:
    try:
        return __import__(rar_python_package)
    except Exception:
        return None


def run_archive_command(
    args: List[str],
    *,
    decode_preview_bytes: DecodePreviewBytes,
    timeout: int = 120,
) -> bytes:
    try:
        completed = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=timeout,
        )
        return completed.stdout
    except subprocess.CalledProcessError as exc:
        stderr = decode_preview_bytes(exc.stderr or b"").strip()
        raise ValueError(f"压缩包解压失败: {stderr or exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("压缩包解压超时") from exc


def list_rar_members(
    archive_path: Path,
    tool_path: str,
    *,
    decode_preview_bytes: DecodePreviewBytes,
    run_command: Callable[..., bytes],
) -> List[str]:
    tool_name = Path(tool_path).name.lower()
    if tool_name == "unar":
        lsar_path = find_lsar_tool(tool_path)
        if not lsar_path:
            raise ValueError("当前容器缺少 lsar，无法列出 RAR 压缩包内容")
        output = run_command([lsar_path, "-json", str(archive_path)])
        try:
            payload = json.loads(decode_preview_bytes(output))
        except Exception as exc:
            raise ValueError("lsar 输出无法解析") from exc
        contents = payload.get("lsarContents") if isinstance(payload, dict) else []
        members = []
        for item in contents or []:
            if not isinstance(item, dict) or item.get("XADIsDirectory"):
                continue
            member = str(item.get("XADFileName") or "").strip()
            if member:
                members.append(member)
        return members
    return []


def read_rar_member(
    archive_path: Path,
    member: str,
    tool_path: str,
    *,
    run_command: Callable[..., bytes],
) -> bytes:
    tool_name = Path(tool_path).name.lower()
    if tool_name == "unar":
        return run_command([tool_path, "-quiet", "-no-directory", "-output-directory", "-", str(archive_path), member])
    raise ValueError("当前容器缺少可用的 unar 解压工具")


def extract_rar_subtitle_files_with_rarfile(
    source_name: str,
    archive_path: Path,
    session_dir: Path,
    *,
    rarfile_module_factory: Callable[[], Any],
    rar_python_package: str,
    subtitle_exts: Iterable[str],
    hash_text: HashText,
    resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
) -> List[Dict[str, Any]]:
    rarfile = rarfile_module_factory()
    if not rarfile:
        raise ValueError(f"未安装 Python 依赖 {rar_python_package}")

    prepared: List[Dict[str, Any]] = []
    subtitle_ext_set = set(subtitle_exts)
    guard = ArchiveResourceGuard(source_name, resource_limits)
    try:
        with rarfile.RarFile(str(archive_path)) as archive:
            for member in archive.infolist():
                guard.count_member(member.filename)
                if member.isdir():
                    continue
                member_name = re.split(r"[\\/]", member.filename)[-1]
                if not member_name or member_name.startswith("."):
                    continue
                member_ext = Path(member_name).suffix.lower()
                if member_ext not in subtitle_ext_set:
                    continue
                member_size = int(getattr(member, "file_size", 0) or 0)
                if member_size:
                    guard.check_member_size(member_name, member_size)
                member_bytes = archive.read(member)
                guard.accept_subtitle(member_name, len(member_bytes))
                upload_id = hash_text(
                    f"{source_name}|{member.filename}|{len(member_bytes)}|{datetime.now().timestamp()}"
                )
                stored_path = session_dir / f"{upload_id}{member_ext}"
                stored_path.write_bytes(member_bytes)
                prepared.append(
                    {
                        "upload_id": upload_id,
                        "source_name": member_name,
                        "archive_name": source_name,
                        "stored_path": str(stored_path),
                        "ext": member_ext,
                    }
                )
    except ArchiveResourceLimitError:
        raise
    except Exception as exc:
        raise ValueError(str(exc)) from exc
    return prepared


def extract_rar_subtitle_files(
    source_name: str,
    archive_path: Path,
    session_dir: Path,
    *,
    rar_python_available_func: Callable[[], bool],
    extract_with_rarfile: Callable[..., List[Dict[str, Any]]],
    rar_tool_func: Callable[[], str],
    extract_command_archive_subtitle_files_func: Callable[..., List[Dict[str, Any]]],
    rar_python_package: str,
    logger_warning: Optional[WarningLogger] = None,
    resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
) -> List[Dict[str, Any]]:
    tool_path = rar_tool_func()
    if tool_path and Path(tool_path).name.lower() == "unar":
        return extract_command_archive_subtitle_files_func(
            source_name,
            archive_path,
            session_dir,
            tool_path,
            resource_limits=resource_limits,
        )

    if rar_python_available_func():
        try:
            return extract_with_rarfile(
                source_name,
                archive_path,
                session_dir,
                resource_limits=resource_limits,
            )
        except ArchiveResourceLimitError:
            raise
        except ValueError as exc:
            if logger_warning:
                logger_warning(
                    "[SubtitleManualUpload] rarfile 解析 RAR 失败，将尝试外部命令回退 archive=%s error=%s",
                    source_name,
                    exc,
                )

    if not tool_path:
        package_note = f"已声明 Python 依赖 {rar_python_package}，但 RAR 内容解压仍需要外部解压程序"
        raise ValueError(f"{package_note}；请在容器安装或映射 /usr/bin/unar")

    return extract_command_archive_subtitle_files_func(
        source_name,
        archive_path,
        session_dir,
        tool_path,
        resource_limits=resource_limits,
    )


def extract_7z_subtitle_files(
    source_name: str,
    archive_path: Path,
    session_dir: Path,
    *,
    sevenzip_tool_func: Callable[[], str],
    extract_command_archive_subtitle_files_func: Callable[..., List[Dict[str, Any]]],
    resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
) -> List[Dict[str, Any]]:
    tool_path = sevenzip_tool_func()
    if not tool_path:
        raise ValueError("7z 压缩包解压需要容器内可执行 unar，或映射宿主机 unar 到容器 /usr/bin/unar")
    return extract_command_archive_subtitle_files_func(
        source_name,
        archive_path,
        session_dir,
        tool_path,
        resource_limits=resource_limits,
    )


def extract_command_archive_subtitle_files(
    source_name: str,
    archive_path: Path,
    session_dir: Path,
    tool_path: str,
    *,
    subtitle_exts: Iterable[str],
    hash_text: HashText,
    list_members: Callable[[Path, str], List[str]],
    read_member: Callable[[Path, str, str], bytes],
    resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
) -> List[Dict[str, Any]]:
    prepared: List[Dict[str, Any]] = []
    subtitle_ext_set = set(subtitle_exts)
    guard = ArchiveResourceGuard(source_name, resource_limits)
    members = list_members(archive_path, tool_path)
    for member in members:
        guard.count_member(member)
        member_name = re.split(r"[\\/]", member)[-1]
        if not member_name or member_name.startswith("."):
            continue
        member_ext = Path(member_name).suffix.lower()
        if member_ext not in subtitle_ext_set:
            continue
        member_bytes = read_member(archive_path, member, tool_path)
        guard.accept_subtitle(member_name, len(member_bytes))
        upload_id = hash_text(f"{source_name}|{member}|{len(member_bytes)}|{datetime.now().timestamp()}")
        stored_path = session_dir / f"{upload_id}{member_ext}"
        stored_path.write_bytes(member_bytes)
        prepared.append(
            {
                "upload_id": upload_id,
                "source_name": member_name,
                "archive_name": source_name,
                "stored_path": str(stored_path),
                "ext": member_ext,
            }
        )
    return prepared


class ArchiveSubtitleExtractor:
    def __init__(
        self,
        *,
        archive_dependency_service: ArchiveDependencyService,
        subtitle_exts: Iterable[str],
        hash_text: HashText,
        rar_python_package: str,
        logger_warning: Optional[WarningLogger] = None,
        resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
    ) -> None:
        self._archive_dependency_service = archive_dependency_service
        self._subtitle_exts = set(subtitle_exts)
        self._hash_text = hash_text
        self._rar_python_package = rar_python_package
        self._logger_warning = logger_warning
        self._resource_limits = resource_limits

    def extract_rar_subtitle_files_with_rarfile(
        self,
        source_name: str,
        archive_path: Path,
        session_dir: Path,
        resource_limits: Optional[ArchiveResourceLimits] = None,
    ) -> List[Dict[str, Any]]:
        return extract_rar_subtitle_files_with_rarfile(
            source_name,
            archive_path,
            session_dir,
            rarfile_module_factory=self._archive_dependency_service.rarfile_module,
            rar_python_package=self._rar_python_package,
            subtitle_exts=self._subtitle_exts,
            hash_text=self._hash_text,
            resource_limits=resource_limits or self._resource_limits,
        )

    def extract_rar_subtitle_files(
        self,
        source_name: str,
        archive_path: Path,
        session_dir: Path,
        resource_limits: Optional[ArchiveResourceLimits] = None,
    ) -> List[Dict[str, Any]]:
        return extract_rar_subtitle_files(
            source_name,
            archive_path,
            session_dir,
            rar_python_available_func=self._archive_dependency_service.rar_python_available,
            extract_with_rarfile=self.extract_rar_subtitle_files_with_rarfile,
            rar_tool_func=self._archive_dependency_service.rar_tool,
            extract_command_archive_subtitle_files_func=self.extract_command_archive_subtitle_files,
            rar_python_package=self._rar_python_package,
            logger_warning=self._logger_warning,
            resource_limits=resource_limits or self._resource_limits,
        )

    def extract_7z_subtitle_files(
        self,
        source_name: str,
        archive_path: Path,
        session_dir: Path,
        resource_limits: Optional[ArchiveResourceLimits] = None,
    ) -> List[Dict[str, Any]]:
        return extract_7z_subtitle_files(
            source_name,
            archive_path,
            session_dir,
            sevenzip_tool_func=self._archive_dependency_service.sevenzip_tool,
            extract_command_archive_subtitle_files_func=self.extract_command_archive_subtitle_files,
            resource_limits=resource_limits or self._resource_limits,
        )

    def extract_command_archive_subtitle_files(
        self,
        source_name: str,
        archive_path: Path,
        session_dir: Path,
        tool_path: str,
        resource_limits: Optional[ArchiveResourceLimits] = None,
    ) -> List[Dict[str, Any]]:
        return extract_command_archive_subtitle_files(
            source_name,
            archive_path,
            session_dir,
            tool_path,
            subtitle_exts=self._subtitle_exts,
            hash_text=self._hash_text,
            list_members=self._archive_dependency_service.list_rar_members,
            read_member=self._archive_dependency_service.read_rar_member,
            resource_limits=resource_limits or self._resource_limits,
        )


def normalize_online_download_name(
    name: str,
    content: bytes,
    result: Dict[str, Any],
    *,
    subtitle_exts: Iterable[str],
    archive_exts: Iterable[str],
    normalize_text: NormalizeText,
    decode_preview_bytes: DecodePreviewBytes,
) -> str:
    safe_name = Path(normalize_text(name)).name
    suffix = Path(safe_name).suffix.lower()
    magic_suffix = archive_suffix_from_content(content)
    if magic_suffix:
        stem = Path(safe_name).stem if safe_name else ""
        if not stem:
            stem = re.sub(r"[\\/:*?\"<>|]+", " ", normalize_text(result.get("title")) or "online-subtitle").strip()
        return f"{stem or 'online-subtitle'}{magic_suffix}"
    if suffix in set(subtitle_exts) or suffix in set(archive_exts):
        return safe_name
    title = re.sub(r"[\\/:*?\"<>|]+", " ", normalize_text(result.get("title")) or "online-subtitle").strip()
    if content.startswith(b"PK\x03\x04"):
        return f"{title}.zip"
    if content.startswith(b"Rar!\x1a\x07"):
        return f"{title}.rar"
    text_head = decode_preview_bytes(content[:4096]).lstrip()
    if re.match(r"^\d+\s*\n\d{2}:\d{2}:\d{2}[,.]\d{3}\s+-->", text_head):
        return f"{title}.srt"
    if "[Script Info]" in text_head or "[V4+ Styles]" in text_head:
        return f"{title}.ass"
    return safe_name or f"{title}.zip"


class UploadSessionService:
    def __init__(
        self,
        *,
        data_path: Path,
        subtitle_exts: Iterable[str],
        archive_exts: Iterable[str],
        rar_exts: Iterable[str],
        sevenzip_exts: Iterable[str],
        default_session_hours: int,
        hash_text: HashText,
        extract_rar_subtitle_files: ArchiveExtractor,
        extract_7z_subtitle_files: ArchiveExtractor,
        logger_warning: Optional[WarningLogger] = None,
        resource_limits: ArchiveResourceLimits = DEFAULT_ARCHIVE_RESOURCE_LIMITS,
        normalize_text: NormalizeText = _default_normalize_text,
        decode_preview_bytes: DecodePreviewBytes = _default_decode_preview_bytes,
    ) -> None:
        self._data_path = Path(data_path)
        self._subtitle_exts = set(subtitle_exts)
        self._archive_exts = set(archive_exts)
        self._rar_exts = set(rar_exts)
        self._sevenzip_exts = set(sevenzip_exts)
        self._default_session_hours = default_session_hours
        self._hash_text = hash_text
        self._extract_rar_subtitle_files = extract_rar_subtitle_files
        self._extract_7z_subtitle_files = extract_7z_subtitle_files
        self._logger_warning = logger_warning
        self._resource_limits = resource_limits
        self._normalize_text = normalize_text
        self._decode_preview_bytes = decode_preview_bytes

    def get_session_root(self) -> Path:
        root = self._data_path / "sessions"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def cleanup_old_sessions(self) -> None:
        root = self.get_session_root()
        expire_before = datetime.now() - timedelta(hours=self._default_session_hours)
        for child in root.iterdir():
            try:
                if not child.is_dir():
                    continue
                if datetime.fromtimestamp(child.stat().st_mtime) < expire_before:
                    shutil.rmtree(child, ignore_errors=True)
            except Exception as exc:
                if self._logger_warning:
                    self._logger_warning("[SubtitleManualUpload] 清理旧会话失败 %s: %s", child, exc)

    def extract_subtitle_files(
        self,
        upload_name: str,
        raw_bytes: bytes,
        session_dir: Path,
    ) -> List[Dict[str, Any]]:
        source_name = Path(upload_name or "").name
        ext = Path(source_name).suffix.lower()
        prepared: List[Dict[str, Any]] = []
        validate_upload_content_size(source_name, len(raw_bytes), self._resource_limits)

        if ext in self._subtitle_exts:
            upload_id = self._hash_text(f"{source_name}|{len(raw_bytes)}|{datetime.now().timestamp()}")
            stored_path = session_dir / f"{upload_id}{ext}"
            stored_path.write_bytes(raw_bytes)
            prepared.append(
                {
                    "upload_id": upload_id,
                    "source_name": source_name,
                    "archive_name": "",
                    "stored_path": str(stored_path),
                    "ext": ext,
                }
            )
            return prepared

        if ext not in self._archive_exts:
            return prepared

        archive_path = session_dir / source_name
        archive_path.write_bytes(raw_bytes)
        if ext in self._rar_exts:
            return self._extract_rar_subtitle_files(
                source_name,
                archive_path,
                session_dir,
                resource_limits=self._resource_limits,
            )
        if ext in self._sevenzip_exts:
            return self._extract_7z_subtitle_files(
                source_name,
                archive_path,
                session_dir,
                resource_limits=self._resource_limits,
            )

        try:
            with zipfile.ZipFile(archive_path) as archive:
                guard = ArchiveResourceGuard(source_name, self._resource_limits)
                for member in archive.infolist():
                    guard.count_member(member.filename)
                    if member.is_dir():
                        continue
                    member_name = Path(member.filename).name
                    if not member_name or member_name.startswith("."):
                        continue
                    member_ext = Path(member_name).suffix.lower()
                    if member_ext not in self._subtitle_exts:
                        continue
                    guard.check_member_size(member_name, int(member.file_size or 0))
                    member_bytes = archive.read(member)
                    guard.accept_subtitle(member_name, len(member_bytes))
                    upload_id = self._hash_text(
                        f"{source_name}|{member.filename}|{len(member_bytes)}|{datetime.now().timestamp()}"
                    )
                    stored_path = session_dir / f"{upload_id}{member_ext}"
                    stored_path.write_bytes(member_bytes)
                    prepared.append(
                        {
                            "upload_id": upload_id,
                            "source_name": member_name,
                            "archive_name": source_name,
                            "stored_path": str(stored_path),
                            "ext": member_ext,
                        }
                    )
        except zipfile.BadZipFile as exc:
            raise ValueError(f"压缩包损坏或格式不正确: {source_name}") from exc
        return prepared

    def normalize_online_download_name(self, name: str, content: bytes, result: Dict[str, Any]) -> str:
        return normalize_online_download_name(
            name,
            content,
            result,
            subtitle_exts=self._subtitle_exts,
            archive_exts=self._archive_exts,
            normalize_text=self._normalize_text,
            decode_preview_bytes=self._decode_preview_bytes,
        )

    def write_session(self, session_id: str, payload: Dict[str, Any]) -> None:
        session_dir = self.get_session_root() / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        session_file = session_dir / "session.json"
        session_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_session(self, session_id: str, *, normalize_text: NormalizeText) -> Tuple[Path, Dict[str, Any]]:
        session_dir = self.get_session_root() / normalize_text(session_id)
        session_file = session_dir / "session.json"
        if not session_file.exists():
            raise HTTPException(status_code=404, detail="上传会话不存在或已过期")
        try:
            return session_dir, json.loads(session_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"读取上传会话失败: {exc}") from exc
