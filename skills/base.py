"""Clase base de skills Python (plug-in)."""

from __future__ import annotations

from typing import Any

from core.models import AnalysisResult, Transcript, VideoMetadata


class Skill:
    name: str = "base"
    description: str = ""

    def should_run(self, analysis: AnalysisResult) -> bool:
        return True

    def run(
        self,
        metadata: VideoMetadata,
        transcript: Transcript,
        analysis: AnalysisResult,
        llm=None,
    ) -> Any:
        raise NotImplementedError
