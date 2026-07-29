#!/usr/bin/env python3
"""Physical D2 successor -08 repairing PREPARE evidence controller constant binding.

The module is inert without a separately created exact one-shot authorization.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Any, NoReturn

import h3_n2_stage2d9r_g3r_prepare_evidence_controller_constant_binding_repair_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_prepare_timeout_evidence_physical_d2_wrapper_20260729_v1 as upstream
import h3_n2_stage2d9r_serial_handshake_repair_20260727_v1 as serial_repair
import h3_n2_stage2d9r_g3r_physical_payload_handoff_repair_wrapper_20260728_v1 as handoff

core = upstream.core
STAGE = contract.STAGE
D2_REQUEST_ID = contract.REQUEST_08_ID
AUTH_SCHEMA = contract.AUTH_SCHEMA
RESULT_SCHEMA = contract.RESULT_SCHEMA
MARKER_SCHEMA = contract.MARKER_SCHEMA
PRE_RESULT_SCHEMA = contract.PRE_RESULT_SCHEMA
PRE_MARKER_SCHEMA = contract.PRE_MARKER_SCHEMA
_BASE_VALIDATE_AUTHORIZATION = upstream._BASE_VALIDATE_AUTHORIZATION
_ORIGINAL_HANDOFF_PARSER = upstream._ORIGINAL_HANDOFF_PARSER
_ORIGINAL_PREPARE_PAYLOAD_HANDOFF = upstream._ORIGINAL_PREPARE_PAYLOAD_HANDOFF
_BOUND_PHYSICAL_REQUEST: dict[str, Any] | None = None
_EVIDENCE_ROOT: Path | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _prime_core() -> None:
    upstream._prime_core()
    core.STAGE = STAGE
    core.D2_REQUEST_ID = D2_REQUEST_ID
    core.AUTH_SCHEMA = AUTH_SCHEMA
    core.RESULT_SCHEMA = RESULT_SCHEMA
    core.MARKER_SCHEMA = MARKER_SCHEMA
    core.canonical_package_digest = contract.canonical_package_digest
    core.__file__ = __file__


class ConstantBindingRepairEvidenceExecutionController(upstream.EvidenceExecutionController):
    """Uses constants from the serial-repair module, never from the core executor."""

    def _raise_internal(self, phase: str, site: str, exc: BaseException) -> NoReturn:
        code = f"{phase.upper()}_EVIDENCE_CONTROLLER_{site}_INTERNAL_ERROR"
        self.last_failure_code = code
        self._ensure_journal().record_timeline(
            "EVIDENCE_CONTROLLER_INTERNAL_ERROR",
            phase=phase,
            site=site,
            error_class=type(exc).__name__,
            stable_failure_code=code,
        )
        raise core.ExecutionError(code) from exc

    def _markers(self, expected: bytes, phase: str) -> tuple[bytes, bytes, str, str]:
        try:
            result_marker = serial_repair.RESULT_MARKERS[expected]
            ready_timeout = serial_repair.READY_TIMEOUT_CODES[expected]
            result_timeout = serial_repair.RESULT_TIMEOUT_CODES[expected]
            failure_marker = serial_repair.DEVICE_FAILURE_MARKER
        except (KeyError, AttributeError, TypeError) as exc:
            self._raise_internal(phase, "CONSTANT_BINDING", exc)
        return result_marker, failure_marker, ready_timeout, result_timeout

    def _wait(
        self,
        session: Any,
        markers: tuple[bytes, ...],
        timeout: float,
        *,
        phase: str,
        site: str,
    ) -> tuple[bytes | None, bytes]:
        try:
            return session.wait_for_any(markers, timeout)
        except core.ExecutionError:
            raise
        except Exception as exc:
            self._raise_internal(phase, site, exc)

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
        result_marker, failure_marker, ready_timeout, result_timeout = self._markers(expected, phase)

        try:
            if phase == "verify":
                self.repaired._open_session(replace=True)
            elif self.repaired.session is None:
                self.repaired._open_session(replace=False)
        except core.ExecutionError:
            raise
        except Exception as exc:
            self._raise_internal(phase, "SESSION_OPEN", exc)

        session = self.repaired.session
        if session is None or session.device != device:
            raise core.ExecutionError("SERIAL_CAPTURE_DEVICE_MISMATCH")

        journal.record_timeline(phase.upper() + "_READY_WAIT_STARTED")
        captured = b""
        try:
            marker, captured = self._wait(
                session,
                (expected, failure_marker),
                timeout,
                phase=phase,
                site="READY_WAIT",
            )
            if marker == failure_marker:
                self.last_failure_code = "DEVICE_EXECUTOR_FAILED"
                journal.record_timeline("DEVICE_EXECUTOR_FAIL", phase=phase)
                raise core.ExecutionError(self.last_failure_code)
            if marker is None:
                self.last_failure_code = ready_timeout
                journal.record_timeline(phase.upper() + "_READY_TIMEOUT")
                raise core.ExecutionError(self.last_failure_code)
            journal.record_timeline(phase.upper() + "_READY_MARKER_OBSERVED")
            if command is None:
                return captured

            try:
                session.write(command)
            except core.ExecutionError:
                raise
            except Exception as exc:
                self._raise_internal(phase, "COMMAND_WRITE", exc)

            command_kind = phase.upper() + "_COMMAND_SENT"
            deadline = datetime.now(timezone.utc) + timedelta(seconds=core.SERIAL_PASS_TIMEOUT_S)
            deadline_at = deadline.isoformat().replace("+00:00", "Z")
            if phase == "prepare":
                self.prepare_deadline_at = deadline_at
                command_kind = "PREPARE_COMMAND_SENT"
            journal.record_timeline(command_kind, deadline_at=deadline_at)

            marker, captured = self._wait(
                session,
                (result_marker, failure_marker),
                core.SERIAL_PASS_TIMEOUT_S,
                phase=phase,
                site="RESULT_WAIT",
            )
            if marker == failure_marker:
                self.last_failure_code = "DEVICE_EXECUTOR_FAILED"
                journal.record_timeline("DEVICE_EXECUTOR_FAIL", phase=phase)
                raise core.ExecutionError(self.last_failure_code)
            if marker is None:
                late_marker, captured = self._wait(
                    session,
                    (result_marker, failure_marker),
                    float(contract.LATE_RESULT_OBSERVATION_WINDOW_SECONDS),
                    phase=phase,
                    site="LATE_RESULT_WAIT",
                )
                if late_marker == result_marker:
                    journal.record_timeline(phase.upper() + "_PASS", late=True)
                elif late_marker == failure_marker:
                    journal.record_timeline("DEVICE_EXECUTOR_FAIL", phase=phase, late=True)
                self.last_failure_code = result_timeout
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
                journal.record_timeline(
                    "SERIAL_EVIDENCE_CAPTURE_FAILED",
                    phase=phase,
                    site="TRANSCRIPT_PERSIST",
                    error_class=type(exc).__name__,
                )


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
        core.require(
            value.get("locked_recovery_authorized") is True,
            "AUTHORIZATION_LOCKED_RECOVERY_NOT_GRANTED",
        )
        return value

    core.validate_authorization = validate_authorization
    repaired_controller = serial_repair.install_repaired_handshake(core)
    core.require(_EVIDENCE_ROOT is not None, "PREPARE_EVIDENCE_ROOT_NOT_BOUND")
    evidence_controller = ConstantBindingRepairEvidenceExecutionController(
        repaired_controller,
        _EVIDENCE_ROOT,
    )
    evidence_controller.install()
    setattr(core, "_prepare_evidence_controller_constant_binding_repair", evidence_controller)
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
    core.require(
        request_path.is_file() and not request_path.is_symlink(),
        "PHYSICAL_REQUEST_FILE_INVALID",
    )
    try:
        raw = json.loads(request_path.read_text(encoding="utf-8"))
        core.require(isinstance(raw, dict), "PHYSICAL_REQUEST_FILE_INVALID")
        _BOUND_PHYSICAL_REQUEST = contract.validate_physical_request(raw, package_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, contract.ContractError) as exc:
        raise core.ExecutionError(
            str(exc) if isinstance(exc, contract.ContractError) else "PHYSICAL_REQUEST_FILE_INVALID"
        ) from exc
    evidence_root = handoff.normalized_path(args.prepare_evidence_root, strict=False)
    if evidence_root.exists():
        core.require(
            evidence_root.is_dir() and not evidence_root.is_symlink(),
            "PREPARE_EVIDENCE_ROOT_INVALID",
        )
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
        now = (
            datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(timezone.utc)
            if args.now
            else None
        )
        contract.validate_authorization_contract(
            authorization,
            request,
            package_root,
            now=now,
        )
        result: dict[str, Any] = {
            "schema": "gh.h3.n2.stage2d9r-g3r-prepare-evidence-controller-repair-authorization-contract-check/1",
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
            "schema": "gh.h3.n2.stage2d9r-g3r-prepare-evidence-controller-repair-authorization-contract-check/1",
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
    args.result_output.write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, sort_keys=True))
    return rc


def main() -> int:
    if len(sys.argv) == 1:
        print(json.dumps({
            "status": "SOURCE_ONLY_REQUIRES_NEW_EXACT_PHYSICAL_D2_AUTHORIZATION",
            "decision_id": contract.DECISION_ID,
            "d2_request_id": D2_REQUEST_ID,
            "predecessor_status": contract.D2_07_STATUS,
            "predecessor_failure_code": contract.D2_07_FAILURE_CODE,
            "controller_constant_binding_repaired": True,
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
