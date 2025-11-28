from __future__ import annotations

"""Utilities for classifying attachment file types."""

from enum import Enum
from typing import Final

# Supported extension groups (lowercase, with leading dot)
IMAGE_EXTENSIONS: Final[set[str]] = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
PDF_EXTENSIONS: Final[set[str]] = {".pdf"}
PLAIN_TEXT_EXTENSIONS: Final[set[str]] = {".txt", ".text", ".log", ".cfg", ".conf", ".ini", ".env"}
STRUCTURED_TEXT_EXTENSIONS: Final[set[str]] = {
    ".md",
    ".markdown",
    ".rst",
    ".html",
    ".htm",
    ".xhtml",
    ".xml",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".tsv",
    ".srt",
    ".vtt",
}
CODE_EXTENSIONS: Final[set[str]] = {
    # C / C++
    ".c",
    ".h",
    ".hpp",
    ".hh",
    ".hxx",
    ".cpp",
    ".cc",
    ".cxx",
    # C#, Java, Go, Rust
    ".cs",
    ".java",
    ".go",
    ".rs",
    # Python
    ".py",
    ".pyw",
    # JS / TS
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    # Shell / scripting
    ".sh",
    ".bash",
    ".zsh",
    ".ksh",
    ".ps1",
    ".psm1",
    ".bat",
    ".cmd",
    # Web
    ".css",
    ".scss",
    ".sass",
    ".less",
    # Other languages
    ".php",
    ".rb",
    ".pl",
    ".pm",
    ".r",
    ".lua",
    ".sql",
    ".kt",
    ".kts",
    ".scala",
    ".swift",
    ".hs",
    ".clj",
    ".cljs",
    ".edn",
}
OFFICE_TEXT_EXTENSIONS: Final[set[str]] = {".doc", ".docx", ".rtf", ".odt"}
OFFICE_SHEET_EXTENSIONS: Final[set[str]] = {".xls", ".xlsx", ".ods"}
OFFICE_PRESENTATION_EXTENSIONS: Final[set[str]] = {".ppt", ".pptx", ".odp"}
AUDIO_EXTENSIONS: Final[set[str]] = {
    ".flac",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mpga",
    ".m4a",
    ".ogg",
    ".wav",
    ".webm",
}
VIDEO_EXTENSIONS: Final[set[str]] = {".mp4", ".mov", ".mkv", ".avi", ".wmv", ".flv", ".webm"}
ARCHIVE_EXTENSIONS: Final[set[str]] = {
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".tgz",
    ".zst",
}
BINARY_EXTENSIONS: Final[set[str]] = {".exe", ".dll", ".so", ".dylib", ".bin", ".iso", ".img"}


class AttachmentKind(str, Enum):
    """Semantic buckets for different attachment types."""

    IMAGE = "image"
    PDF = "pdf"
    TEXT = "text"
    CODE = "code"
    OFFICE_TEXT = "office_text"
    OFFICE_SHEET = "office_sheet"
    OFFICE_PRESENTATION = "office_presentation"
    AUDIO = "audio"
    VIDEO = "video"
    ARCHIVE = "archive"
    BINARY = "binary"
    UNKNOWN = "unknown"


def classify_extension(ext: str) -> AttachmentKind:
    """Классифицирует расширение файла (с точкой, в нижнем регистре) в AttachmentKind."""

    if ext in IMAGE_EXTENSIONS:
        return AttachmentKind.IMAGE
    if ext in PDF_EXTENSIONS:
        return AttachmentKind.PDF
    if ext in PLAIN_TEXT_EXTENSIONS or ext in STRUCTURED_TEXT_EXTENSIONS:
        return AttachmentKind.TEXT
    if ext in CODE_EXTENSIONS:
        return AttachmentKind.CODE
    if ext in OFFICE_TEXT_EXTENSIONS:
        return AttachmentKind.OFFICE_TEXT
    if ext in OFFICE_SHEET_EXTENSIONS:
        return AttachmentKind.OFFICE_SHEET
    if ext in OFFICE_PRESENTATION_EXTENSIONS:
        return AttachmentKind.OFFICE_PRESENTATION
    if ext in AUDIO_EXTENSIONS:
        return AttachmentKind.AUDIO
    if ext in VIDEO_EXTENSIONS:
        return AttachmentKind.VIDEO
    if ext in ARCHIVE_EXTENSIONS:
        return AttachmentKind.ARCHIVE
    if ext in BINARY_EXTENSIONS:
        return AttachmentKind.BINARY
    return AttachmentKind.UNKNOWN


def is_text_like(kind: AttachmentKind) -> bool:
    """Returns True for kinds that can be handled as text in LLM prompts."""

    return kind in {AttachmentKind.TEXT, AttachmentKind.CODE}
