from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import types
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch


def load_upload_session(variant):
    root = Path(__file__).resolve().parents[1]
    package_dir = root / f"plugins.{variant}" / "subtitlemanualupload"
    package_name = f"subtitle_archive_regression_{variant}"
    package = types.ModuleType(package_name)
    package.__path__ = [str(package_dir)]
    sys.modules[package_name] = package
    name = f"{package_name}.upload.upload_session"
    spec = importlib.util.spec_from_file_location(name, package_dir / "upload" / "upload_session.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ArchiveTestCases:
    def setUp(self):
        self.module = load_upload_session(self.variant)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def session_service(self):
        return self.module.UploadSessionService(
            data_path=self.root,
            subtitle_exts={".srt", ".sup", ".idx", ".sub"},
            archive_exts={".zip", ".rar", ".7z"},
            rar_exts={".rar"},
            sevenzip_exts={".7z"},
            default_session_hours=1,
            hash_text=lambda value: hashlib.sha256(value.encode()).hexdigest(),
            extract_rar_subtitle_files=Mock(),
            extract_7z_subtitle_files=Mock(),
        )

    def list_members(self, contents):
        output = json.dumps({"lsarContents": contents}).encode()
        with patch.object(self.module, "find_lsar_tool", return_value="/usr/bin/lsar"):
            return self.module.list_rar_members(
                self.root / "sample.rar",
                "/usr/bin/unar",
                decode_preview_bytes=bytes.decode,
                run_command=lambda args: output,
            )

    def command_extract(self, members, read_member):
        return self.module.extract_command_archive_subtitle_files(
            "sample.rar",
            self.root / "sample.rar",
            self.root,
            "/usr/bin/unar",
            subtitle_exts={".srt", ".sup"},
            hash_text=lambda value: hashlib.sha256(value.encode()).hexdigest(),
            list_members=lambda *args: members,
            read_member=read_member,
        )

    def rarfile_extract(self, expected_size, payload):
        member = types.SimpleNamespace(filename="nested/a[b].srt", file_size=expected_size, isdir=lambda: False)
        archive = Mock()
        archive.__enter__ = Mock(return_value=archive)
        archive.__exit__ = Mock(return_value=False)
        archive.infolist.return_value = [member]
        archive.read.return_value = payload
        return self.module.extract_rar_subtitle_files_with_rarfile(
            "sample.rar",
            self.root / "sample.rar",
            self.root,
            rarfile_module_factory=lambda: types.SimpleNamespace(RarFile=lambda path: archive),
            rar_python_package="rarfile",
            subtitle_exts={".srt"},
            hash_text=lambda value: hashlib.sha256(value.encode()).hexdigest(),
        )

    def test_lsar_preserves_exact_indexes_names_and_sizes(self):
        members = self.list_members([
            {"XADFileName": "nested", "XADIsDirectory": True, "XADIndex": 0},
            {"XADFileName": "nested/a[b]*?.srt", "XADIndex": 4, "XADFileSize": 3},
            {"XADFileName": "nested/a[b]*?.srt", "XADIndex": 7, "XADFileSize": 5},
            {"XADFileName": " other/a[b]*?.srt ", "XADIndex": 8},
        ])
        self.assertEqual(
            [(member.name, member.index, member.size) for member in members],
            [("nested/a[b]*?.srt", 4, 3), ("nested/a[b]*?.srt", 7, 5), (" other/a[b]*?.srt ", 8, None)],
        )

    def test_lsar_rejects_missing_or_duplicate_indexes_and_invalid_sizes(self):
        for contents in [
            [{"XADFileName": "a.srt"}],
            [{"XADFileName": "a.srt", "XADIndex": -1}],
            [{"XADFileName": "a.srt", "XADIndex": True}],
            [{"XADFileName": "a.srt", "XADIndex": 0}, {"XADFileName": "b.srt", "XADIndex": 0}],
            [{"XADFileName": "a.srt", "XADIndex": 0, "XADFileSize": -1}],
            [{"XADFileName": "a.srt", "XADIndex": 0, "XADFileSize": "3"}],
        ]:
            with self.subTest(contents=contents), self.assertRaises(ValueError):
                self.list_members(contents)

    def test_unar_selects_only_the_member_index(self):
        run_command = Mock(return_value=b"exact subtitle")
        member = self.module.ArchiveMember("nested/a[b]*?.srt", 7, 14)
        actual = self.module.read_rar_member(
            self.root / "sample.rar", member, "/usr/bin/unar", run_command=run_command,
        )
        self.assertEqual(actual, b"exact subtitle")
        self.assertEqual(run_command.call_args.args[0], [
            "/usr/bin/unar", "-quiet", "-no-directory", "-no-recursion", "-indexes",
            "-output-directory", "-", str(self.root / "sample.rar"), "7",
        ])

    def test_command_extraction_rejects_empty_and_incomplete_content(self):
        for size, payload in [(0, b""), (None, b""), (3, b"ab"), (3, b"abcd")]:
            with self.subTest(size=size, payload=payload), self.assertRaises(self.module.SubtitleContentError):
                self.command_extract(
                    [self.module.ArchiveMember("nested/a[b].srt", 1, size)],
                    lambda *args: payload,
                )
        self.assertEqual(list(self.root.iterdir()), [])

    def test_command_extraction_checks_known_size_before_read(self):
        read_member = Mock()
        oversized = self.module.DEFAULT_ARCHIVE_RESOURCE_LIMITS.max_archive_member_bytes + 1
        with self.assertRaises(self.module.ArchiveResourceLimitError):
            self.command_extract([self.module.ArchiveMember("a.srt", 1, oversized)], read_member)
        read_member.assert_not_called()

    def test_command_extraction_keeps_same_named_members_separate(self):
        members = [self.module.ArchiveMember("nested/a[b].srt", index, 3) for index in (1, 2)]
        with patch.object(self.module, "datetime"):
            extracted = self.command_extract(members, lambda path, member, tool: {1: b"one", 2: b"two"}[member.index])
        self.assertEqual([Path(item["stored_path"]).read_bytes() for item in extracted], [b"one", b"two"])
        self.assertNotEqual(extracted[0]["stored_path"], extracted[1]["stored_path"])

    def test_direct_upload_rejects_empty_text_and_bitmap_subtitles(self):
        service = self.session_service()
        for name in ("a.srt", "a.sup", "a.idx", "a.sub"):
            with self.subTest(name=name), self.assertRaises(self.module.SubtitleContentError):
                service.extract_subtitle_files(name, b"", self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_zip_extracts_wildcard_characters_and_duplicate_names_exactly(self):
        data = io.BytesIO()
        with warnings.catch_warnings(), zipfile.ZipFile(data, "w") as archive:
            warnings.simplefilter("ignore", UserWarning)
            archive.writestr("nested/a[b]*?.srt", b"one")
            archive.writestr("nested/a[b]*?.srt", b"two")
            archive.writestr("other/a[b]*?.srt", b"end")
        with patch.object(self.module, "datetime"):
            extracted = self.session_service().extract_subtitle_files("sample.zip", data.getvalue(), self.root)
        self.assertEqual([Path(item["stored_path"]).read_bytes() for item in extracted], [b"one", b"two", b"end"])

    def test_zip_rejects_empty_subtitles(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("a.srt", b"")
        with self.assertRaises(self.module.SubtitleContentError):
            self.session_service().extract_subtitle_files("sample.zip", data.getvalue(), self.root)
        self.assertEqual([path.name for path in self.root.iterdir()], ["sample.zip"])

    def test_rarfile_rejects_empty_and_incomplete_content(self):
        for size, payload in [(0, b""), (None, b""), (3, b"ab"), (3, b"abcd")]:
            with self.subTest(size=size, payload=payload), self.assertRaises(self.module.SubtitleContentError):
                self.rarfile_extract(size, payload)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_rar_content_error_does_not_fallback_or_hide_the_error(self):
        fallback = Mock()
        error = self.module.SubtitleContentError("empty subtitle")
        with self.assertRaises(self.module.SubtitleContentError):
            self.module.extract_rar_subtitle_files(
                "sample.rar", self.root / "sample.rar", self.root,
                rar_python_available_func=lambda: True,
                extract_with_rarfile=Mock(side_effect=error),
                rar_tool_func=lambda: "",
                extract_command_archive_subtitle_files_func=fallback,
                rar_python_package="rarfile",
            )
        fallback.assert_not_called()

    @unittest.skipUnless(shutil.which("unar") and shutil.which("lsar"), "requires unar and lsar")
    def test_real_unar_extracts_special_and_duplicate_names_by_index(self):
        archive_path = self.root / "probe.zip"
        expected = [b"one", b"two", b"three", b"four"]
        names = ["nested/a[b]*?.srt", "nested/a[b]*?.srt", "other/a[b]*?.srt", "nested/escaped\\name.srt"]
        with warnings.catch_warnings(), zipfile.ZipFile(archive_path, "w") as archive:
            warnings.simplefilter("ignore", UserWarning)
            archive.writestr("nested/", b"")
            for name, payload in zip(names, expected):
                archive.writestr(name, payload)
        tool = shutil.which("unar")
        dependency = self.module.ArchiveDependencyService(
            rar_dependency_mode="none", rar_tool_path=tool, rar_python_package="rarfile",
            rar_tools=("unar",), sevenzip_tools=("unar",),
            normalize_text=str, decode_preview_bytes=bytes.decode,
        )
        members = dependency.list_rar_members(archive_path, tool)
        self.assertEqual([member.index for member in members], [1, 2, 3, 4])
        self.assertEqual([dependency.read_rar_member(archive_path, member, tool) for member in members], expected)
        extracted = self.module.extract_command_archive_subtitle_files(
            "probe.zip", archive_path, self.root, tool,
            subtitle_exts={".srt"},
            hash_text=lambda value: hashlib.sha256(value.encode()).hexdigest(),
            list_members=dependency.list_rar_members, read_member=dependency.read_rar_member,
        )
        self.assertEqual([Path(item["stored_path"]).read_bytes() for item in extracted], expected)


class V2ArchiveTests(ArchiveTestCases, unittest.TestCase):
    variant = "v2"


class V3ArchiveTests(ArchiveTestCases, unittest.TestCase):
    variant = "v3"


if __name__ == "__main__":
    unittest.main(verbosity=2)
