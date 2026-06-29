import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_SCRIPT = ROOT / "scripts" / "subtitlemanualupload_compat_inventory.py"


def load_inventory_module():
    spec = importlib.util.spec_from_file_location("subtitlemanualupload_compat_inventory", INVENTORY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_compat_inventory_reports_deletion_gate_fields():
    inventory = load_inventory_module().build_inventory()

    assert isinstance(inventory["runtime_refs"], dict)
    assert isinstance(inventory["test_refs"], dict)
    assert isinstance(inventory["dynamic_installs"], list)
    assert isinstance(inventory["delete_blockers"], dict)

    runtime_hits = [hit for hits in inventory["runtime_refs"].values() for hit in hits]
    assert not [hit for hit in runtime_hits if "plugins.v2/subtitlemanualupload/compat.py:" in hit]

    dynamic_installs = inventory["dynamic_installs"]
    assert dynamic_installs
    assert not any(item["installer"] == "install_compat_core_methods" for item in dynamic_installs)
    assert not any(item["installer"] == "install_compat_service_factories" for item in dynamic_installs)
    assert any(item["installer"] == "install_compat_archive_methods" for item in dynamic_installs)
    assert any(item["installer"] == "LEGACY_INSTANCE_SERVICE_DELEGATES" for item in dynamic_installs)

    assert inventory["dynamic_install_count"] == len(dynamic_installs)
    assert inventory["dynamic_install_method_count"] == len({item["name"] for item in dynamic_installs})
    assert "_extract_subtitle_files" in inventory["delete_blockers"]["dynamic_installs"]
