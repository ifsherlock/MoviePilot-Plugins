"""Legacy private API compatibility shell for SubtitleManualUpload.

New runtime behavior belongs in domain services or API modules; this mixin is
kept only while existing source paths and legacy tests still reference private
``_xxx`` helpers.
"""

from __future__ import annotations

from .compat_services import (
    LEGACY_INSTANCE_SERVICE_DELEGATES,
    install_compat_archive_methods,
    install_legacy_service_delegates,
)


class SubtitleManualUploadCompatMixin:
    pass


install_compat_archive_methods(SubtitleManualUploadCompatMixin)
install_legacy_service_delegates(SubtitleManualUploadCompatMixin, LEGACY_INSTANCE_SERVICE_DELEGATES)
