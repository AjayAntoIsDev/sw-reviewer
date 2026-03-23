"""Artifact bundle persistence and management."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from ..models import EvidenceBundle, EvidenceItem, FinalVerdict

logger = logging.getLogger(__name__)


class ArtifactBundle:
    """
    Manages the full artifact set for a single review run.
    Persists evidence items, verdict JSON, and report paths under artifacts/<review_id>/.
    """

    def __init__(self, review_id: str, base_dir: str = "artifacts"):
        self.review_id = review_id
        self.base_dir = Path(base_dir) / review_id
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._evidence_items: List[EvidenceItem] = []

    def add_evidence(self, item: EvidenceItem) -> None:
        """Register an evidence item."""
        self._evidence_items.append(item)

    def add_evidence_batch(self, items: List[EvidenceItem]) -> None:
        """Register multiple evidence items."""
        self._evidence_items.extend(items)

    def build_bundle(self) -> EvidenceBundle:
        """Build and return an EvidenceBundle from registered items."""
        return EvidenceBundle(review_id=self.review_id, items=self._evidence_items)

    def save_verdict(self, verdict: FinalVerdict) -> str:
        """Save the final verdict JSON to disk and return the path."""
        path = self.base_dir / "verdict.json"
        path.write_text(verdict.model_dump_json(indent=2), encoding="utf-8")
        logger.info("Verdict saved to %s", path)
        return str(path)

    def save_evidence_index(self) -> str:
        """Write evidence index JSON file and return its path."""
        bundle = self.build_bundle()
        path = self.base_dir / "evidence_index.json"
        path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def get_artifact_paths(self) -> Dict[str, str]:
        """Return a dict of artifact type -> path for all known artifacts."""
        paths: Dict[str, str] = {}
        for candidate in ("verdict.json", "evidence_index.json", "report/report.typ", "report/report.pdf"):
            full = self.base_dir / candidate
            if full.exists():
                paths[candidate] = str(full)
        return paths
