from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
READER_PATH = ROOT / "plugins.v3/subtitlemanualupload/runtime/transfer_history_reader.py"


def _load_reader(fake_model):
    package_names = (
        "app",
        "app.db",
        "app.db.models",
        "app.db.oper",
        "plugins_v3_test",
        "plugins_v3_test.runtime",
    )
    previous = {name: sys.modules.get(name) for name in package_names}
    try:
        sys.modules["app"] = types.ModuleType("app")
        sys.modules["app.db"] = types.ModuleType("app.db")
        sys.modules["app.db.models"] = types.ModuleType("app.db.models")
        sys.modules["app.db.oper"] = types.ModuleType("app.db.oper")
        sys.modules["app.db.models.transferhistory"] = types.SimpleNamespace(
            TransferHistory=fake_model
        )
        sys.modules["app.db.oper.transferhistory"] = types.SimpleNamespace(
            TransferHistoryOper=type(
                "TransferHistoryOper",
                (),
                {"__init__": lambda self, db=None: setattr(self, "_db", db)},
            )
        )

        package = types.ModuleType("plugins_v3_test")
        package.__path__ = []
        runtime_package = types.ModuleType("plugins_v3_test.runtime")
        runtime_package.__path__ = []
        sys.modules["plugins_v3_test"] = package
        sys.modules["plugins_v3_test.runtime"] = runtime_package

        spec = importlib.util.spec_from_file_location(
            "plugins_v3_test.runtime.transfer_history_reader",
            READER_PATH,
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
        sys.modules.pop("app.db.models.transferhistory", None)
        sys.modules.pop("app.db.oper.transferhistory", None)
        sys.modules.pop("plugins_v3_test.runtime.transfer_history_reader", None)


def test_reader_uses_v3_model_query_without_removed_execute_sync_query():
    calls = []

    class FakeTransferHistory:
        @classmethod
        def list_by_page(cls, db, *, page, count, status):
            calls.append((db, page, count, status))
            return [{"id": 1}]

    module = _load_reader(FakeTransferHistory)
    previous_session = sys.modules.get("app.db.session")
    try:
        sys.modules["app.db.session"] = types.SimpleNamespace(
            SessionFactory=lambda: types.SimpleNamespace(close=lambda: None)
        )
        reader = module.TransferHistoryReader()

        assert reader.list_by_page(page=2, count=17, status=True) == [{"id": 1}]
        assert calls[0][1:] == (2, 17, True)
        assert calls[0][0] is not None
    finally:
        if previous_session is None:
            sys.modules.pop("app.db.session", None)
        else:
            sys.modules["app.db.session"] = previous_session


def test_reader_closes_explicit_session_after_query():
    calls = []

    class FakeSession:
        closed = False

        def close(self):
            self.closed = True

    session = FakeSession()

    class FakeTransferHistory:
        @classmethod
        def list_by_page(cls, db, *, page, count, status):
            calls.append((db, page, count, status))
            return []

    module = _load_reader(FakeTransferHistory)
    previous_session = sys.modules.get("app.db.session")
    try:
        sys.modules["app.db.session"] = types.SimpleNamespace(
            SessionFactory=lambda: session
        )
        reader = module.TransferHistoryReader()

        assert reader.list_by_page(page=1, count=30, status=True) == []
        assert calls == [(session, 1, 30, True)]
        assert session.closed is True
    finally:
        if previous_session is None:
            sys.modules.pop("app.db.session", None)
        else:
            sys.modules["app.db.session"] = previous_session
