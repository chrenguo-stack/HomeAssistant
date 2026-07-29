#!/usr/bin/env python3
"""Reviewable future-executor overlay; inert without a later exact request."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import h3_n2_stage2d9r_g3r_prepare_timeout_evidence_recorder_20260729_v1 as recorder

SOURCE_STATE = "SOURCE_ONLY_OVERLAY_NOT_BOUND_TO_PHYSICAL_REQUEST"


@dataclass
class PrepareTimeoutEvidenceOverlay:
    evidence_root: Path

    def initialize(self) -> recorder.EvidenceJournal:
        journal = recorder.EvidenceJournal(self.evidence_root)
        journal.initialize()
        journal.record_timeline("EVIDENCE_CAPTURE_INITIALIZED")
        return journal

    @staticmethod
    def terminal_manifest(
        journal: recorder.EvidenceJournal,
        *,
        deadline_at: str,
        failure_code: str,
        recovery_about_to_start: bool,
    ) -> dict[str, Any]:
        classification = recorder.classify_prepare_outcome(journal.timeline, deadline_at=deadline_at)
        journal.record_timeline(
            "TERMINAL_EVIDENCE_PERSIST_REQUESTED",
            failure_code=failure_code,
            before_recovery=recovery_about_to_start,
        )
        return journal.persist(classification=classification, terminal=True)


def source_boundary() -> dict[str, Any]:
    return {
        "state": SOURCE_STATE,
        "physical_request_created": False,
        "physical_request_authorized": False,
        "authorization_created": False,
        "board_operation": False,
        "serial_operation": False,
        "flash_operation": False,
        "network_operation": False,
    }


if __name__ == "__main__":
    print(json.dumps(source_boundary(), sort_keys=True))
