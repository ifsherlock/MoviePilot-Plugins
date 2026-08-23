from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins.v3/subtitlemanualupload"
WHEELS_DIR = PLUGIN_DIR / "wheels"
EXPECTED_WHEELS = {
    "webrtcvad_wheels-2.0.14-cp314-cp314-linux_x86_64.whl": "x86_64-linux-gnu.so",
    "webrtcvad_wheels-2.0.14-cp314-cp314-linux_aarch64.whl": "aarch64-linux-gnu.so",
}


def test_v3_webrtcvad_wheels_cover_python_314_linux_architectures():
    wheels = {path.name: path for path in WHEELS_DIR.glob("*.whl")}
    assert set(wheels) == set(EXPECTED_WHEELS)

    for filename, extension_suffix in EXPECTED_WHEELS.items():
        with ZipFile(wheels[filename]) as archive:
            names = archive.namelist()
            assert "webrtcvad.py" in names
            assert any(
                name.startswith("_webrtcvad.cpython-314-") and name.endswith(extension_suffix)
                for name in names
            )
            wheel_metadata = archive.read("webrtcvad_wheels-2.0.14.dist-info/WHEEL").decode("utf-8")
            expected_tag = "-".join(filename.removesuffix(".whl").split("-")[2:])
            assert f"Tag: {expected_tag}" in wheel_metadata


def test_v3_webrtcvad_wheel_checksums_match():
    recorded = {}
    for line in (WHEELS_DIR / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        checksum, filename = line.split(maxsplit=1)
        recorded[filename] = checksum

    assert set(recorded) == set(EXPECTED_WHEELS)
    for filename in EXPECTED_WHEELS:
        actual = hashlib.sha256((WHEELS_DIR / filename).read_bytes()).hexdigest()
        assert recorded[filename] == actual


def test_v3_requirements_select_local_python_314_wheels_without_changing_v2():
    v3_requirements = (PLUGIN_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert (
        'webrtcvad-wheels==2.0.14; python_version == "3.14" '
        'and platform_system == "Linux" and platform_machine == "x86_64"'
    ) in v3_requirements
    assert (
        'webrtcvad-wheels==2.0.14; python_version == "3.14" '
        'and platform_system == "Linux" and platform_machine == "aarch64"'
    ) in v3_requirements

    v2_requirements = (
        ROOT / "plugins.v2/subtitlemanualupload/requirements.txt"
    ).read_text(encoding="utf-8").splitlines()
    assert "webrtcvad-wheels>=2.0.14" in v2_requirements
