"""Dataclasses centrales del pipeline. Sin dependencias externas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class VideoMetadata:
    video_id: str
    url: str
    title: str = ""
    channel: str = ""
    channel_id: str = ""
    duration_seconds: int = 0
    upload_date: Optional[str] = None
    language: str = "es"
    has_manual_captions: bool = False
    has_auto_captions: bool = False


@dataclass
class TranscriptSegment:
    text: str
    start: float = 0.0
    duration: float = 0.0

    @property
    def end(self) -> float:
        return self.start + self.duration


@dataclass
class Transcript:
    segments: list[TranscriptSegment] = field(default_factory=list)
    full_text: str = ""
    source: str = "unknown"  # youtube_api | ytdlp | whisper
    language: str = "es"

    @classmethod
    def from_segments(
        cls, segments: list[TranscriptSegment], source: str, language: str
    ) -> "Transcript":
        full = " ".join(s.text.strip() for s in segments if s.text.strip())
        return cls(segments=segments, full_text=full, source=source, language=language)


@dataclass
class SponsorReport:
    segments_removed: list[dict[str, Any]] = field(default_factory=list)
    method: str = "none"  # sponsorblock | heuristic | llm | none
    chars_before: int = 0
    chars_after: int = 0


@dataclass
class AnalysisResult:
    category: str = "sin-categorizar"
    subcategory: Optional[str] = None
    confidence: float = 0.0
    tags: list[str] = field(default_factory=list)
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    main_topics: list[str] = field(default_factory=list)
    difficulty: Optional[str] = None
    content_type: str = "otro"
    method: str = "heuristic"  # llm | heuristic


@dataclass
class ProcessedVideo:
    metadata: VideoMetadata
    transcript: Transcript          # transcript LIMPIO (sin sponsors)
    raw_transcript: Optional[Transcript] = None
    analysis: AnalysisResult = field(default_factory=AnalysisResult)
    sponsors: SponsorReport = field(default_factory=SponsorReport)
    output_paths: dict[str, Path] = field(default_factory=dict)
    processed_at: datetime = field(default_factory=datetime.now)
    skills_applied: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
