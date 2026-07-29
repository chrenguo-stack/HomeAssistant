#!/usr/bin/env python3
"""Physical D2 successor -07 with durable redacted PREPARE evidence.

Inert without a separately created exact one-shot authorization.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

import h3_n2_stage2d9r_g3r_prepare_timeout_evidence_execution_binding_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_prepare_timeout_evidence_overlay_20260729_v1 as evidence_overlay
import h3_n2_stage2d9r_g3r_prepare_timeout_evidence_recorder_20260729_v1 as evidence_recorder
import h3_n2_stage2d9r_g3r_corrected_baseline_physical_d2_overlay_wrapper_20260729_v1 as previous
import h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1 as handoff

core = previous.core
STAGE = contract.STAGE
D2_REQUEST_ID = contract.REQUEST_07_ID
AUTH_SCHEMA = contract.AUTH_SCHEMA
RESULT_SCHEMA = contract.RESULT_SCHEMA
MARKER_SCHEMA = contract.MARKER_SCHEMA
PRE_RESULT_SCHEMA = contract.PRE_RESULT_SCHEMA
PRE_MARKER_SCHEMA = contract.PRE_MARKER_SCHEMA
_BASE_VALIDATE_AUTHORIZATION = previous._BASE_VALIDATE_AUTHORIZATION
_ORIGINAL_HANDOFF_PARSER = previous.parser
_ORIGINAL_PREPARE_PAYLOAD_HANDOFF = previous._ORIGINAL_PREPARE_PAYLOAD_HANDOFF
_BOUND_PHYSICAL_REQUEST: dict[str, Any] | None = None
_EVIDENCE_ROOT: Path | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _prime_core() -> None:
    previous._prime_core()
    core.STAGE = STAGE
    core.D2_REQUEST_ID = D2_REQUEST_ID
    core.AUTH_SCHEMA = AUTH_SCHEMA
    core.RESULT_SCHEMA = RESULT_SCHEMA
    core.MARKER_SCHEMA = MARKER_SCHEMA
    core.canonical_package_digest = contract.canonical_package_digest
    core.__file__ = __file__


class EvidenceExecutionController:
    """Binds the source-only evidence recorder to the repaired serial flow."""

    def __init__(self, repaired_controller: Any, root: Path) -> None:
        self.repaired = repaired_controller
        self.overlay = evidence_overlay.PrepareTimeoutEvidenceOverlay(root)
        self.journal: evidence_recorder.EvidenceJournal | None = None
        self.broker_log_path: Path | None = None
        self.prepare_deadline_at: str | None = None
        self.last_failure_code: str | None = None
        self.manifest: dict[str, Any] | None = None
        self._original_start_broker = core.start_broker
        self._original_stop_broker = core.stop_broker
        self._original_locked_recovery = core.locked_recovery
        self._original_result_object = core.result_object

    def install(self) -> None:
        core.start_broker = self.start_broker
        core.stop_broker = self.stop_broker
        core.wait_serial_line = self.wait_serial_line
        core.locked_recovery = self.locked_recovery
        core.result_object = self.result_object

    def _ensure_journal(self) -> evidence_recorder.EvidenceJournal:
        if self.journal is None:
            self.journal = self.overlay.initialize()
        return self.journal

    @staticmethod
    def _phase(expected: bytes) -> str:
        if expected.endswith(b"PREPARE"):
            return "prepare"
        if expected.endswith(b"VERIFY"):
            return "verify"
        raise core.ExecutionError("SERIAL_EXPECTED_MARKER_UNSUPPORTED")

    def _record_transcript(self, captured: bytes, phase: str) -> None:
        journal = self._ensure_journal()
        text = captured.decode("utf-8", errors="replace")
        for line in text.splitlines():
            journal.record_serial(line, phase)
            stripped = evidence_recorder.redact_text(line)
            if stripped == "stage2d9r_prepare=pass":
                journal.record_timeline("PREPARE_PASS")
            elif stripped == "stage2d9r_verify=pass":
                journal.record_timeline("VERIFY_PASS")
            elif stripped == "stage2d9r_executor=fail":
                journal.record_timeline("DEVICE_EXECUTOR_FAIL", phase=phase)
            elif stripped.startswith("stage2d9r_") and "command_ready=" not in stripped:
                if stripped not in {"stage2d9r_prepare=pass", "stage2d9r_verify=pass", "stage2d9r_executor=fail"}:
                    journal.record_timeline("UNRECOGNIZED_RESULT", marker_sha256=evidence_recorder.sha256_text(stripped))

    def start_broker(self, mosquitto_path: Path, private_root: Path, log_path: Path):
        journal = self._ensure_journal()
        journal.record_timeline("BROKER_START_REQUESTED")
        self.broker_log_path = log_path
        process = self._original_start_broker(mosquitto_path, private_root, log_path)
        journal.record_timeline("BROKER_STARTED")
        return process

    def _record_broker_log(self) -> None:
        if self.broker_log_path is None or not self.broker_log_path.exists():
            return
        journal = self._ensure_journal()
        try:
            text = self.broker_log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            journal.record_timeline("BROKER_LOG_READ_FAILED")
            return
        for line in text.splitlines():
            journal.record_broker(line, "prepare")

    def stop_broker(self, process: Any | None) -> None:
        try:
            self._original_stop_broker(process)
        finally:
            if self.journal is not None:
                self._record_broker_log()
                self.journal.record_timeline("BROKER_STOPPED")
                self._persist(terminal=False, failure_code=self.last_failure_code)

    def wait_serial_line(
        self,
        device: str,
        expected: bytes,
        timeout: float,
        command: bytes | None,
        log_path: Path,
    ) -> bytes:
        phase = self._phase(expected)
        journal = self._ensure_journal()
        result_marker = self.repaired.module.RESULT_MARKERS[expected]
        failure_marker = self.repaired.module.DEVICE_FAILURE_MARKER

        if phase == "verify":
            self.repaired._open_session(replace=True)
        elif self.repaired.session is None:
            self.repaired._open_session(replace=False)
        session = self.repaired.session
        if session is None or session.device != device:
            raise core.ExecutionError("SERIAL_CAPTURE_DEVICE_MISMATCH")

        journal.record_timeline(phase.upper() + "_READY_WAIT_STARTED")
        captured = b""
        try:
            marker, captured = session.wait_for_any((expected, failure_marker), timeout)
            if marker == failure_marker:
                self.last_failure_code = "DEVICE_EXECUTOR_FAILED"
                journal.record_timeline("DEVICE_EXECUTOR_FAIL", phase=phase)
                raise core.ExecutionError(self.last_failure_code)
            if marker is None:
                self.last_failure_code = self.repaired.module.READY_TIMEOUT_CODES[expected]
                journal.record_timeline(phase.upper() + "_READY_TIMEOUT")
                raise core.ExecutionError(self.last_failure_code)
            journal.record_timeline(phase.upper() + "_READY_MARKER_OBSERVED")
            if command is None:
                return captured

            session.write(command)
            command_kind = phase.upper() + "_COMMAND_SENT"
            deadline = datetime.now(timezone.utc) + timedelta(seconds=core.SERIAL_PASS_TIMEOUT_S)
            deadline_at = deadline.isoformat().replace("+00:00", "Z")
            if phase == "prepare":
                self.prepare_deadline_at = deadline_at
                command_kind = "PREPARE_COMMAND_SENT"
            journal.record_timeline(command_kind, deadline_at=deadline_at)

            marker, captured = session.wait_for_any((result_marker, failure_marker), core.SERIAL_PASS_TIMEOUT_S)
            if marker == failure_marker:
                self.last_failure_code = "DEVICE_EXECUTOR_FAILED"
                journal.record_timeline("DEVICE_EXECUTOR_FAIL", phase=phase)
                raise core.ExecutionError(self.last_failure_code)
            if marker is None:
                late_marker, captured = session.wait_for_any(
                    (result_marker, failure_marker),
                    float(contract.LATE_RESULT_OBSERVATION_WINDOW_SECONDS),
                )
                if late_marker == result_marker:
                    journal.record_timeline(phase.upper() + "_PASS", late=True)
                elif late_marker == failure_marker:
                    journal.record_timeline("DEVICE_EXECUTOR_FAIL", phase=phase, late=True)
                self.last_failure_code = self.repaired.module.RESULT_TIMEOUT_CODES[expected]
                journal.record_timeline(phase.upper() + "_RESULT_TIMEOUT")
                raise core.ExecutionError(self.last_failure_code)
            journal.record_timeline(phase.upper() + "_PASS", late=False)
            return captured
        finally:
            try:
                captured = session.snapshot()
                session.persist_redacted(log_path)
                self._record_transcript(captured, phase)
            except Exception as exc:
                journal.record_timeline("SERIAL_EVIDENCE_CAPTURE_FAILED", error_class=type(exc).__name__)

    def _classification(self) -> str:
        if self.journal is None:
            return "NO_RESULT"
        deadline = self.prepare_deadline_at or _utc_now()
        events = self.journal.timeline
        regular_pass = any(
            event.get("kind") == "PREPARE_PASS" and str(event.get("at", "")) <= deadline
            for event in events
        )
        if regular_pass:
            return "PREPARE_PASS"
        return evidence_recorder.classify_prepare_outcome(events, deadline_at=deadline)

    def _persist(self, *, terminal: bool, failure_code: str | None) -> dict[str, Any] | None:
        if self.journal is None:
            return None
        classification = self._classification()
        self.journal.record_timeline(
            "TERMINAL_EVIDENCE_PERSIST_REQUESTED" if terminal else "EVIDENCE_CHECKPOINT_PERSIST_REQUESTED",
            failure_code=failure_code,
            before_recovery=terminal and failure_code is not None,
        )
        self.manifest = self.journal.persist(classification=classification, terminal=terminal)
        return self.manifest

    def locked_recovery(self, selected: Any, esptool_path: Path, erased: Path, work: Path) -> bool:
        self._persist(terminal=True, failure_code=self.last_failure_code or "PRE_RECOVERY_FAILURE")
        return self._original_locked_recovery(selected, esptool_path, erased, work)

    def result_object(self, **kwargs: Any) -> dict[str, Any]:
        failure_code = kwargs.get("failure_code")
        if failure_code:
            self.last_failure_code = str(failure_code)
        manifest = self._persist(terminal=True, failure_code=self.last_failure_code)
        value = self._original_result_object(**kwargs)
        value["prepare_evidence_policy_version"] = contract.EVIDENCE_POLICY_VERSION
        value["prepare_evidence_persisted"] = manifest is not None
        value["prepare_evidence_classification"] = manifest.get("classification") if manifest else None
        value["prepare_serial_evidence_sha256"] = manifest.get("serial_evidence_sha256") if manifest else None
        value["prepare_broker_evidence_sha256"] = manifest.get("broker_evidence_sha256") if manifest else None
        value["prepare_timeline_sha256"] = manifest.get("timeline_sha256") if manifest else None
        value["prepare_evidence_manifest_sha256"] = (
            evidence_recorder.sha256_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
            if manifest else None
        )
        value["prepare_evidence_private_values_included"] = False
        value.pop("terminal_result_sha256", None)
        value["terminal_result_sha256"] = core.canonical_sha256(value)
        return value


def configure_core() -> Any:
    _prime_core()

    def validate_authorization(*args: Any, **kwargs: Any) -> dict[str, Any]:
        value = _BASE_VALIDATE_AUTHORIZATION(*args, **kwargs)
        package_root = kwargs.get("package_root")
        core.require(isinstance(package_root, Path), "AUTHORIZATION_PACKAGE_ROOT_MISSING")
        core.require(_BOUND_PHYSICAL_REQUEST is not None, "PHYSICAL_REQUEST_NOT_BOUND")
        try:
            contract.validate_authorization_contract(value, _BOUND_PHYSICAL_REQUEST, package_root)
        except contract.ContractError as exc:
            raise core.ExecutionError(str(exc)) from exc
        required = contract.authorization_contract_required(_BOUND_PHYSICAL_REQUEST, package_root)
        for key, expected in required.items():
            core.require(value.get(key) == expected, "AUTHORIZATION_" + key.upper() + "_MISMATCH")
        core.require(value.get("locked_recovery_authorized") is True,
                     "AUTHORIZATION_LOCKED_RECOVERY_NOT_GRANTED")
        return value

    core.validate_authorization = validate_authorization
    repaired_controller = previous.repaired.repair.install_repaired_handshake(core)
    core.require(_EVIDENCE_ROOT is not None, "PREPARE_EVIDENCE_ROOT_NOT_BOUND")
    evidence_controller = EvidenceExecutionController(repaired_controller, _EVIDENCE_ROOT)
    evidence_controller.install()
    setattr(core, "_prepare_timeout_evidence_controller", evidence_controller)
    return core


def parser() -> argparse.ArgumentParser:
    result = _ORIGINAL_HANDOFF_PARSER()
    result.add_argument("--prepare-evidence-root", type=Path, required=True)
    return result


def prepare_payload_handoff(args: argparse.Namespace) -> None:
    global _BOUND_PHYSICAL_REQUEST, _EVIDENCE_ROOT
    _ORIGINAL_PREPARE_PAYLOAD_HANDOFF(args)
    request_path = handoff.normalized_path(args.physical_request, strict=True)
    package_root = args.package_root
    core.require(request_path.is_file() and not request_path.is_symlink(), "PHYSICAL_REQUEST_FILE_INVALID")
    try:
        raw = json.loads(request_path.read_text(encoding="utf-8"))
        core.require(isinstance(raw, dict), "PHYSICAL_REQUEST_FILE_INVALID")
        _BOUND_PHYSICAL_REQUEST = contract.validate_physical_request(raw, package_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, contract.ContractError) as exc:
        raise core.ExecutionError(str(exc) if isinstance(exc, contract.ContractError) else "PHYSICAL_REQUEST_FILE_INVALID") from exc
    evidence_root = handoff.normalized_path(args.prepare_evidence_root, strict=False)
    if evidence_root.exists():
        core.require(evidence_root.is_dir() and not evidence_root.is_symlink(), "PREPARE_EVIDENCE_ROOT_INVALID")
        core.require(not any(evidence_root.iterdir()), "PREPARE_EVIDENCE_ROOT_NOT_EMPTY")
    _EVIDENCE_ROOT = evidence_root
    args.physical_request = request_path
    args.prepare_evidence_root = evidence_root


def install() -> None:
    _prime_core()
    handoff.STAGE = STAGE
    handoff.D2_REQUEST_ID = D2_REQUEST_ID
    handoff.AUTH_SCHEMA = AUTH_SCHEMA
    handoff.RESULT_SCHEMA = RESULT_SCHEMA
    handoff.MARKER_SCHEMA = MARKER_SCHEMA
    handoff.PRE_RESULT_SCHEMA = PRE_RESULT_SCHEMA
    handoff.PRE_MARKER_SCHEMA = PRE_MARKER_SCHEMA
    handoff.parser = parser
    handoff.prepare_payload_handoff = prepare_payload_handoff
    handoff.configure_core = configure_core


def _contract_check(argv: list[str]) -> int:
    check = argparse.ArgumentParser()
    check.add_argument("--package-root", type=Path, required=True)
    check.add_argument("--physical-request", type=Path, required=True)
    check.add_argument("--authorization-record", type=Path, required=True)
    check.add_argument("--result-output", type=Path, required=True)
    check.add_argument("--now")
    args = check.parse_args(argv)
    try:
        package_root = args.package_root.expanduser().resolve(strict=True)
        request = json.loads(args.physical_request.read_text(encoding="utf-8"))
        authorization = json.loads(args.authorization_record.read_text(encoding="utf-8"))
        now = datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(timezone.utc) if args.now else None
        contract.validate_authorization_contract(authorization, request, package_root, now=now)
        result: dict[str, Any] = {
            "schema": "gh.h3.n2.stage2d9r-g3r-prepare-timeout-evidence-authorization-contract-check/1",
            "status": "PASS",
            "d2_request_id": D2_REQUEST_ID,
            "request_binding_sha256": request["request_binding_sha256"],
            "evidence_policy_version": contract.EVIDENCE_POLICY_VERSION,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
        }
        rc = 0
    except Exception as exc:
        result = {
            "schema": "gh.h3.n2.stage2d9r-g3r-prepare-timeout-evidence-authorization-contract-check/1",
            "status": "FAIL",
            "failure_code": str(exc.args[0]) if exc.args else type(exc).__name__,
            "d2_request_id": D2_REQUEST_ID,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
        }
        rc = 2
    args.result_output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return rc


def main() -> int:
    if len(sys.argv) == 1:
        print(json.dumps({
            "status": "SOURCE_ONLY_REQUIRES_NEW_EXACT_PHYSICAL_D2_AUTHORIZATION",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": D2_REQUEST_ID,
            "evidence_policy_version": contract.EVIDENCE_POLICY_VERSION,
            "authorization_created": False,
            "board_operation": False,
            "usb_enumeration": False,
            "serial_operation": False,
            "esptool_operation": False,
            "flash_operation": False,
            "network_operation": False,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
        }, sort_keys=True))
        return 0
    if sys.argv[1] == "contract-check":
        return _contract_check(sys.argv[2:])
    if sys.argv[1] != "execute":
        print("first argument must be contract-check or execute", file=sys.stderr)
        return 2
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    install()
    return handoff.main()


if __name__ == "__main__":
    raise SystemExit(main())
