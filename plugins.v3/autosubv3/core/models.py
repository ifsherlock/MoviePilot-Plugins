from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class UserInterruptException(Exception):
    """Raised when the current AutoSub task is interrupted by the user."""
    pass


class TranslationQualityException(Exception):
    """Raised when translation quality is too low to write subtitle output."""
    pass


class TaskSource(Enum):
    MANUAL = "manual"
    EVENT = "event"
    SUBTITLE_MANUAL_UPLOAD = "subtitle_manual_upload"


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    IGNORED = "ignored"
    NO_AUDIO = "no_audio"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GenerationMode(Enum):
    FALLBACK = "fallback"
    MONITOR = "monitor"
    MIXED = "mixed"


class TriggerType(Enum):
    MANUAL = "manual"
    SUBTITLE_FALLBACK = "subtitle_fallback"


class SourcePolicy(Enum):
    AUTO = "auto"
    MATCHED_EXTERNAL = "matched_external"
    LOCAL_EXTERNAL = "local_external"
    EMBEDDED = "embedded"
    ASR = "asr"
    REUSE = "reuse"


class ResolvedSource(Enum):
    AUTO = "auto"
    MATCHED_EXTERNAL = "matched_external"
    LOCAL_EXTERNAL = "local_external"
    EMBEDDED = "embedded"
    ASR = "asr"


class OverwritePolicy(Enum):
    SKIP = "skip"
    BACKUP_REPLACE = "backup_replace"
    NEW_VARIANT = "new_variant"


@dataclass
class TaskItem:
    task_id: str
    video_file: str
    source: TaskSource
    add_time: datetime
    force_generate: bool = False
    source_subtitle_path: str = ""
    source_subtitle_lang: str = ""
    trigger: str = TriggerType.MANUAL.value
    source_policy: str = SourcePolicy.AUTO.value
    resolved_source: str = ""
    source_asset_path: str = ""
    source_lang: str = ""
    output_path: str = ""
    output_variant: str = ""
    reuse_output_path: str = ""
    reuse_source_lang: str = ""
    overwrite_policy: str = OverwritePolicy.SKIP.value
    rerun_of: str = ""
    status: TaskStatus = TaskStatus.PENDING
    complete_time: datetime = None
    error_message: str = ""
    cancel_requested: bool = False
