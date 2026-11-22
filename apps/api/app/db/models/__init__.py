"""ORM models — import side effects register metadata for Alembic."""

from app.db.models.audit import AuditEvent
from app.db.models.chat import ChatMessage, ChatThread, MessageCitation
from app.db.models.evidence import ExternalEvidence
from app.db.models.identity import Session, User, Workspace, WorkspaceMembership
from app.db.models.indexing import IndexManifest
from app.db.models.jobs import IngestionJob, OutboxEvent
from app.db.models.library import Playlist, PlaylistItem, Video
from app.db.models.media import MediaAsset, MediaFrame
from app.db.models.summaries import ProviderRun, Summary
from app.db.models.transcript import Chapter, SourceAsset, TranscriptSegment
from app.db.models.tutor import (
    Concept,
    ConceptEdge,
    LearnerProgress,
    QuizAttempt,
    ReviewSchedule,
    StudyDeck,
    StudyItem,
    TutorPreference,
)
from app.db.models.usage import UsageLimit

__all__ = [
    "User",
    "Workspace",
    "WorkspaceMembership",
    "Session",
    "Video",
    "Playlist",
    "PlaylistItem",
    "SourceAsset",
    "TranscriptSegment",
    "Chapter",
    "IngestionJob",
    "OutboxEvent",
    "ProviderRun",
    "Summary",
    "IndexManifest",
    "ChatThread",
    "ChatMessage",
    "MessageCitation",
    "AuditEvent",
    "ExternalEvidence",
    "UsageLimit",
    "MediaAsset",
    "MediaFrame",
    "Concept",
    "ConceptEdge",
    "StudyDeck",
    "StudyItem",
    "QuizAttempt",
    "ReviewSchedule",
    "LearnerProgress",
    "TutorPreference",
]
