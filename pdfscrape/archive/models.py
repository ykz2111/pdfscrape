"""Common record model shared by archive source adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class ArchiveRecord:
    """Normalized bibliographic and file metadata for one public document."""

    id: str
    source_id: str
    title: str
    creators: list[str] = field(default_factory=list)
    year: str | None = None
    period: str | None = None
    language: str | None = None
    rights: str | None = None
    landing_url: str | None = None
    pdf_url: str | None = None
    text_url: str | None = None
    checksum: str | None = None
    copilot_url: str | None = None

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("archive record id must not be empty")
        if not self.source_id.strip():
            raise ValueError("archive record source_id must not be empty")
        if not self.title.strip():
            self.title = self.id

    def to_dict(self) -> dict:
        """Return a JSON-friendly mapping."""
        return asdict(self)
