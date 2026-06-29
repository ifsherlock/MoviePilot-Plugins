"""Legacy private API compatibility shell for SubtitleManualUpload.

New runtime behavior belongs in domain services or API modules; this mixin is
kept only while existing source paths and legacy tests still reference private
``_xxx`` helpers.
"""

from __future__ import annotations

class SubtitleManualUploadCompatMixin:
    pass
