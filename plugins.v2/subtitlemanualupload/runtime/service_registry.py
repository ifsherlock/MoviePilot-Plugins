from __future__ import annotations

from pathlib import Path
from typing import Any

from . import service_factories


class SubtitleManualUploadServices:
    def __init__(self, owner: Any) -> None:
        self._owner = owner

    def archive_dependency(self, status_setter=None):
        return service_factories.archive_dependency_service(self._owner, status_setter=status_setter)

    def upload_session_for_path(self, data_path: Path):
        return service_factories.upload_session_service_for_path(self._owner, data_path)

    def upload_session(self):
        return self.upload_session_for_path(self._owner.get_data_path())

    def subtitle_inventory(self):
        return service_factories.subtitle_inventory(self._owner)

    def writer(self):
        return service_factories.subtitle_writer(self._owner)

    def history(self):
        return service_factories.subtitle_history(self._owner)

    def autosub_bridge(self):
        return service_factories.autosub_bridge(self._owner)

    def online_ai(self):
        return service_factories.online_ai_service(self._owner)

    def auto_transfer(self):
        return service_factories.auto_transfer_service(self._owner)

    def target_resolver(self):
        return service_factories.target_resolver(self._owner)

    def local_media_catalog(self):
        return service_factories.local_media_catalog(self._owner)

    def media_metadata(self):
        return service_factories.media_metadata_service(self._owner)

    def timeline_tasks(self):
        return service_factories.timeline_task_store(self._owner)

    def online_subtitles(self):
        return service_factories.online_service(self._owner)
