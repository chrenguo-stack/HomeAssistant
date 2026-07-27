#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "h3_n2_stage2d9r_consumed_marker_evidence_20260727_v1.py"
SPEC = importlib.util.spec_from_file_location("stage2d9r_marker_evidence_test", TOOL)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


class ConsumedMarkerEvidenceTests(unittest.TestCase):
    AUTH_ID = "U1-TEST"
    AUTH_BYTES = b'{"authorization":"retired"}\n'
    RESULT_BYTES = b'{"result":"pass"}\n'
    AUTH_SHA = hashlib.sha256(AUTH_BYTES).hexdigest()
    RESULT_SHA = hashlib.sha256(RESULT_BYTES).hexdigest()

    def marker(self, root: Path, *, aliases: bool = True) -> Path:
        path = root / "consumed.json"
        value = {
            "authorization_id": self.AUTH_ID,
            "status": "CONSUMED",
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "secret_values_included": False,
            "private_paths_included": False,
        }
        if aliases:
            value["record_sha256"] = self.AUTH_SHA
            value["execution_result_sha256"] = self.RESULT_SHA
        else:
            value["authorization_record_sha256"] = self.AUTH_SHA
            value["result_sha256"] = self.RESULT_SHA
        write(path, value)
        return path

    def test_marker_only_alias_fields_pass_without_reconstruction(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            marker = self.marker(root)
            before = MODULE.sha256_file(marker)
            result = MODULE.validate_consumed_evidence(
                marker=marker,
                authorization_id=self.AUTH_ID,
                authorization_record_sha256=self.AUTH_SHA,
                result_sha256=self.RESULT_SHA,
            )
            self.assertEqual(result["evidence_mode"], "CONSUMED_MARKER_ONLY")
            self.assertFalse(result["authorization_reconstructed"])
            self.assertFalse(result["authorization_replayed"])
            self.assertEqual(MODULE.sha256_file(marker), before)

    def test_original_files_and_marker_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            marker = self.marker(root, aliases=False)
            auth = root / "authorization.json"
            result = root / "result.json"
            auth.write_bytes(self.AUTH_BYTES)
            result.write_bytes(self.RESULT_BYTES)
            os.chmod(auth, 0o600)
            os.chmod(result, 0o600)
            observed = MODULE.validate_consumed_evidence(
                marker=marker,
                authorization_id=self.AUTH_ID,
                authorization_record_sha256=self.AUTH_SHA,
                result_sha256=self.RESULT_SHA,
                authorization_record=auth,
                result=result,
            )
            self.assertEqual(
                observed["evidence_mode"],
                "ORIGINAL_FILES_AND_CONSUMED_MARKER",
            )

    def test_partial_original_evidence_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            marker = self.marker(root)
            auth = root / "authorization.json"
            auth.write_bytes(self.AUTH_BYTES)
            os.chmod(auth, 0o600)
            with self.assertRaisesRegex(
                MODULE.ConsumedEvidenceError,
                "PARTIAL_ORIGINAL_CONSUMED_EVIDENCE",
            ):
                MODULE.validate_consumed_evidence(
                    marker=marker,
                    authorization_id=self.AUTH_ID,
                    authorization_record_sha256=self.AUTH_SHA,
                    result_sha256=self.RESULT_SHA,
                    authorization_record=auth,
                )

    def test_marker_digest_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            marker = self.marker(Path(td))
            value = json.loads(marker.read_text())
            value["record_sha256"] = "0" * 64
            write(marker, value)
            with self.assertRaisesRegex(
                MODULE.ConsumedEvidenceError,
                "CONSUMED_MARKER_AUTHORIZATION_RECORD_MISMATCH",
            ):
                MODULE.validate_consumed_evidence(
                    marker=marker,
                    authorization_id=self.AUTH_ID,
                    authorization_record_sha256=self.AUTH_SHA,
                    result_sha256=self.RESULT_SHA,
                )

    def test_replay_expansion_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            marker = self.marker(Path(td))
            value = json.loads(marker.read_text())
            value["replay_permitted"] = True
            write(marker, value)
            with self.assertRaisesRegex(
                MODULE.ConsumedEvidenceError,
                "CONSUMED_MARKER_REPLAY_EXPANDED",
            ):
                MODULE.validate_consumed_evidence(
                    marker=marker,
                    authorization_id=self.AUTH_ID,
                    authorization_record_sha256=self.AUTH_SHA,
                    result_sha256=self.RESULT_SHA,
                )


if __name__ == "__main__":
    unittest.main()
