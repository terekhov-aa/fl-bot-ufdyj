from __future__ import annotations

from enum import Enum
from pathlib import Path


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
PDF_EXTENSIONS = {".pdf"}
PLAIN_TEXT_EXTENSIONS = {".txt", ".text", ".log", ".cfg", ".conf", ".ini", ".env"}
MARKUP_TEXT_EXTENSIONS = {
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
CODE_EXTENSIONS = {
    ".c",
    ".h",
    ".hpp",
    ".hh",
    ".hxx",
    ".cpp",
    ".cc",
    ".cxx",
    ".cs",
    ".java",
    ".go",
    ".rs",
    ".py",
    ".pyw",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".sh",
    ".bash",
    ".zsh",
    ".ksh",
    ".ps1",
    ".psm1",
    ".bat",
    ".cmd",
    ".css",
    ".scss",
    ".sass",
    ".less",
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
OFFICE_TEXT_EXTENSIONS = {".doc", ".docx", ".rtf", ".odt"}
OFFICE_SHEET_EXTENSIONS = {".xls", ".xlsx", ".ods"}
OFFICE_PRESENTATION_EXTENSIONS = {".ppt", ".pptx", ".odp"}
AUDIO_EXTENSIONS = {
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
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".wmv", ".flv", ".webm"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".zst"}
BINARY_MISC_EXTENSIONS = {".exe", ".dll", ".so", ".dylib", ".bin", ".iso", ".img"}


class AttachmentKind(str, Enum):
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
    ext = ext.lower()

    if ext in IMAGE_EXTENSIONS:
        return AttachmentKind.IMAGE
    if ext in PDF_EXTENSIONS:
        return AttachmentKind.PDF
    if ext in PLAIN_TEXT_EXTENSIONS or ext in MARKUP_TEXT_EXTENSIONS:
        return AttachmentKind.TEXT
    if ext in CODE_EXTENSIONS:
        return AttachmentKind.CODE
    if ext in OFFICE_TEXT_EXTENSIONS:
        return AttachmentKind.OFFICE_TEXT
    if ext in OFFICE_SHEET_EXTENSIONS:
        return AttachmentKind.OFFICE_SHEET
    if ext in OFFICE_PRESENTATION_EXTENSIONS:
        return AttachmentKind.OFFICE_PRESENTATION
    if ext in VIDEO_EXTENSIONS:
        return AttachmentKind.VIDEO
    if ext in AUDIO_EXTENSIONS:
        # MP4/WEBM могут быть как аудио, так и видео — видео уже перехвачено выше.
        return AttachmentKind.AUDIO
    if ext in ARCHIVE_EXTENSIONS:
        return AttachmentKind.ARCHIVE
    if ext in BINARY_MISC_EXTENSIONS:
        return AttachmentKind.BINARY

    return AttachmentKind.UNKNOWN


def suffix_for_filename(filename: str) -> str:
    return Path(filename).suffix.lower()
