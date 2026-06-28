from __future__ import annotations

import json
import re
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException


HashText = Callable[[str], str]
DecodePreviewBytes = Callable[[bytes], str]
ArchiveExtractor = Callable[[str, Path, Path], List[Dict[str, Any]]]
NormalizeText = Callable[[Any], str]
WarningLogger = Callable[..., None]


def archive_suffix_from_content(content: bytes) -> str:
    head = (content or b"")[:8]
    if head.startswith(b"PK\x03\x04") or head.startswith(b"PK\x05\x06") or head.startswith(b"PK\x07\x08"):
        return ".zip"
    if head.startswith(b"Rar!\x1a\x07"):
        return ".rar"
    if head.startswith(b"7z\xbc\xaf\x27\x1c"):
        return ".7z"
    return ""


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
            return self._extract_rar_subtitle_files(source_name, archive_path, session_dir)
        if ext in self._sevenzip_exts:
            return self._extract_7z_subtitle_files(source_name, archive_path, session_dir)

        try:
            with zipfile.ZipFile(archive_path) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    member_name = Path(member.filename).name
                    if not member_name or member_name.startswith("."):
                        continue
                    member_ext = Path(member_name).suffix.lower()
                    if member_ext not in self._subtitle_exts:
                        continue
                    member_bytes = archive.read(member)
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
