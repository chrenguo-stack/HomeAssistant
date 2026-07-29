#!/usr/bin/env python3
"""D2-11 successor wrapper with paced transport and terminalization safety.

The module is inert on import and without arguments. Physical execution still
requires a separately created exact, current, one-shot authorization.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable

import h3_n2_stage2d9r_g3r_d2_11_prepare_transport_pacing_execution_binding_contract_20260729_v1 as contract
import h3_n2_stage2d9r_g3r_executor_terminalization_repair_20260729_v1 as terminalization
import h3_n2_stage2d9r_g3r_prepare_transport_pacing_repair_20260729_v1 as pacing
import h3_n2_stage2d9r_g3r_watchdog_repaired_payload_physical_d2_wrapper_20260729_v1 as base

core = base.core
handoff = base.handoff
repaired = base.repaired
serial_repair = base.serial_repair
upstream = base.upstream

STAGE = contract.STAGE
D2_REQUEST_ID = contract.D2_REQUEST_ID
AUTH_SCHEMA = contract.AUTH_SCHEMA
RESULT_SCHEMA = contract.RESULT_SCHEMA
MARKER_SCHEMA = contract.MARKER_SCHEMA
PRE_RESULT_SCHEMA = contract.PRE_RESULT_SCHEMA
PRE_MARKER_SCHEMA = contract.PRE_MARKER_SCHEMA

_BASE_VALIDATE_AUTHORIZATION = base._BASE_VALIDATE_AUTHORIZATION
_ORIGINAL_HANDOFF_PARSER = base._ORIGINAL_HANDOFF_PARSER
_ORIGINAL_PREPARE_PAYLOAD_HANDOFF = base._ORIGINAL_PREPARE_PAYLOAD_HANDOFF
_BOUND_PHYSICAL_REQUEST: dict[str, Any] | None = None
_EVIDENCE_ROOT: Path | None = None
_DELIVERY_EVIDENCE_ROOT: Path | None = None
_TERMINALIZATION_EVIDENCE_ROOT: Path | None = None


def _error_code(exc: BaseException) -> str:
    if (
        isinstance(exc, pacing.TransportRepairError)
        and exc.args
        and isinstance(exc.args[0], str)
        and exc.args[0]
    ):
        return exc.args[0]
    return type(exc).__name__


def _atomic_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    data = json.dumps(value, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    os.chmod(path, 0o600)


class _TrackingHandle:
    def __init__(self, handle: Any) -> None:
        self._handle = handle
        self.attempted_chunks = 0
        self.completed_chunks = 0
        self.flush_count = 0
        self.last_expected = 0
        self.last_written: int | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._handle, name)

    def write(self, value: bytes) -> Any:
        self.attempted_chunks += 1
        self.last_expected = len(value)
        result = self._handle.write(value)
        self.last_written = result if isinstance(result, int) else None
        if result == len(value):
            self.completed_chunks += 1
        return result

    def flush(self) -> Any:
        result = self._handle.flush()
        self.flush_count += 1
        return result


def _install_tracked_pacing(
    session_class: type[Any],
    *,
    sleep: Callable[[float], None],
) -> None:
    pacing.install_on_session_class(session_class, sleep=sleep)
    paced_write = session_class.write
    if getattr(session_class, "_stage2d9r_tracked_pacing_v1", False):
        raise pacing.TransportRepairError("TRACKED_TRANSPORT_ALREADY_INSTALLED")

    def write(self: Any, value: bytes) -> None:
        handle = getattr(self, "_handle", None)
        if handle is None:
            raise pacing.TransportRepairError("SERIAL_CAPTURE_NOT_OPEN")
        for attr in (
            "_stage2d9r_transport_delivery_evidence",
            "_stage2d9r_transport_delivery_failure",
        ):
            if hasattr(self, attr):
                delattr(self, attr)
        tracked = _TrackingHandle(handle)
        self._handle = tracked
        try:
            paced_write(self, value)
        except BaseException as exc:
            schema = (
                pacing._command_schema(value)
                if isinstance(value, bytes)
                and value.endswith(b"\n")
                and len(value) <= pacing.MAX_COMMAND_BYTES
                else "UNKNOWN"
            )
            failure = {
                "schema": (
                    "gh.h3.n2.stage2d9r-g3r-command-delivery-failure-evidence/1"
                ),
                "command_schema": schema,
                "command_sha256": (
                    hashlib.sha256(value).hexdigest()
                    if isinstance(value, bytes)
                    else None
                ),
                "command_bytes": len(value) if isinstance(value, bytes) else None,
                "chunk_bytes": pacing.PACED_CHUNK_BYTES,
                "inter_chunk_delay_ms": int(
                    pacing.INTER_CHUNK_DELAY_SECONDS * 1000
                ),
                "attempted_chunk_count": tracked.attempted_chunks,
                "completed_chunk_count": tracked.completed_chunks,
                "failed_chunk_index": (
                    tracked.attempted_chunks - 1
                    if tracked.attempted_chunks
                    > tracked.completed_chunks
                    else None
                ),
                "failed_chunk_expected_bytes": tracked.last_expected,
                "failed_chunk_written_bytes": tracked.last_written,
                "flush_count": tracked.flush_count,
                "exact_write_confirmed": False,
                "failure_code": _error_code(exc),
                "raw_command_included": False,
                "transport_layer_authorizes_physical_operation": False,
            }
            setattr(self, "_stage2d9r_transport_delivery_failure", failure)
            raise
        finally:
            self._handle = handle

    session_class.write = write
    session_class._stage2d9r_tracked_pacing_v1 = True


class PacedDeliveryEvidenceController:
    """Persist one redacted delivery record per PREPARE/VERIFY command."""

    def __init__(self, module: Any, panic_controller: Any, root: Path) -> None:
        self.module = module
        self.panic_controller = panic_controller
        self.root = root
        self._original_wait_serial_line = module.wait_serial_line
        self._original_result_object = module.result_object
        self.records: dict[str, dict[str, Any]] = {}

    def install(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        self.module.wait_serial_line = self.wait_serial_line
        self.module.result_object = self.result_object

    @staticmethod
    def _phase(expected: bytes) -> str:
        if expected.endswith(b"PREPARE"):
            return "prepare"
        if expected.endswith(b"VERIFY"):
            return "verify"
        raise core.ExecutionError("SERIAL_EXPECTED_MARKER_UNSUPPORTED")

    def _session(self) -> Any | None:
        current = getattr(self.panic_controller, "_current_session", None)
        return current() if callable(current) else None

    def _persist(
        self,
        *,
        phase: str,
        command: bytes,
        call_error: BaseException | None,
    ) -> None:
        session = self._session()
        success = (
            getattr(session, "_stage2d9r_transport_delivery_evidence", None)
            if session is not None
            else None
        )
        failure = (
            getattr(session, "_stage2d9r_transport_delivery_failure", None)
            if session is not None
            else None
        )
        if isinstance(success, dict):
            if (
                success.get("command_sha256")
                != hashlib.sha256(command).hexdigest()
                or success.get("command_bytes") != len(command)
                or success.get("chunk_bytes") != pacing.PACED_CHUNK_BYTES
                or success.get("inter_chunk_delay_ms")
                != int(pacing.INTER_CHUNK_DELAY_SECONDS * 1000)
                or success.get("exact_write_confirmed") is not True
            ):
                raise core.ExecutionError("DELIVERY_EVIDENCE_BINDING_MISMATCH")
            value = dict(success)
            value.update(
                {
                    "phase": phase,
                    "status": "DELIVERED",
                    "failure_code": None,
                }
            )
        elif isinstance(failure, dict):
            if (
                failure.get("command_sha256")
                != hashlib.sha256(command).hexdigest()
                or failure.get("command_bytes") != len(command)
            ):
                raise core.ExecutionError(
                    "DELIVERY_FAILURE_EVIDENCE_BINDING_MISMATCH"
                )
            value = dict(failure)
            value.update({"phase": phase, "status": "FAILED"})
        else:
            value = {
                "schema": (
                    "gh.h3.n2.stage2d9r-g3r-command-delivery-failure-evidence/1"
                ),
                "phase": phase,
                "status": "NOT_DELIVERED",
                "command_schema": pacing._command_schema(command),
                "command_sha256": hashlib.sha256(command).hexdigest(),
                "command_bytes": len(command),
                "chunk_bytes": pacing.PACED_CHUNK_BYTES,
                "inter_chunk_delay_ms": int(
                    pacing.INTER_CHUNK_DELAY_SECONDS * 1000
                ),
                "attempted_chunk_count": 0,
                "completed_chunk_count": 0,
                "failed_chunk_index": None,
                "failed_chunk_expected_bytes": 0,
                "failed_chunk_written_bytes": None,
                "flush_count": 0,
                "exact_write_confirmed": False,
                "failure_code": (
                    _error_code(call_error)
                    if call_error is not None
                    else "DELIVERY_EVIDENCE_MISSING"
                ),
                "raw_command_included": False,
                "transport_layer_authorizes_physical_operation": False,
            }
        value["raw_command_included"] = False
        value["transport_layer_authorizes_physical_operation"] = False
        without = dict(value)
        without.pop("delivery_evidence_sha256", None)
        value["delivery_evidence_sha256"] = contract.canonical_sha256(without)
        path = self.root / f"{phase}-transport-delivery.json"
        _atomic_new(path, value)
        self.records[phase] = value
        if value["status"] == "NOT_DELIVERED" and call_error is None:
            raise core.ExecutionError("DELIVERY_EVIDENCE_MISSING")

    def wait_serial_line(
        self,
        device: str,
        expected: bytes,
        timeout: float,
        command: bytes | None,
        log_path: Path,
    ) -> bytes:
        phase = self._phase(expected)
        error: BaseException | None = None
        try:
            result = self._original_wait_serial_line(
                device, expected, timeout, command, log_path
            )
        except BaseException as exc:
            error = exc
            result = b""
        if command is not None:
            self._persist(phase=phase, command=command, call_error=error)
        if error is not None:
            record = self.records.get(phase)
            leaf = record.get("failure_code") if record else None
            if (
                record
                and record.get("status") == "FAILED"
                and isinstance(leaf, str)
                and leaf
            ):
                raise self.module.ExecutionError(leaf) from error
            raise error
        return result

    def result_object(self, **kwargs: Any) -> dict[str, Any]:
        value = self._original_result_object(**kwargs)
        if not isinstance(value, dict):
            raise TypeError("RESULT_OBJECT_NOT_MAPPING")
        for phase in ("prepare", "verify"):
            record = self.records.get(phase)
            value[f"{phase}_transport_delivery_status"] = (
                record.get("status") if record else "NOT_ATTEMPTED"
            )
            value[f"{phase}_transport_delivery_sha256"] = (
                record.get("delivery_evidence_sha256") if record else None
            )
        value["transport_pacing_policy_version"] = 1
        value["transport_paced_chunk_bytes"] = pacing.PACED_CHUNK_BYTES
        value["transport_inter_chunk_delay_ms"] = int(
            pacing.INTER_CHUNK_DELAY_SECONDS * 1000
        )
        value["transport_command_retry_added"] = False
        value.pop("terminal_result_sha256", None)
        value["terminal_result_sha256"] = self.module.canonical_sha256(value)
        return value


def _prime_payload_constants() -> None:
    base._prime_payload_constants()


def _prime_core() -> None:
    _prime_payload_constants()
    base._prime_core()
    bindings = {
        "STAGE": STAGE,
        "D2_REQUEST_ID": D2_REQUEST_ID,
        "AUTH_SCHEMA": AUTH_SCHEMA,
        "RESULT_SCHEMA": RESULT_SCHEMA,
        "MARKER_SCHEMA": MARKER_SCHEMA,
        "validate_public_inputs": handoff.validate_public_inputs,
        "locked_recovery": repaired.locked_recovery,
    }
    for key, value in bindings.items():
        setattr(core, key, value)
    core.canonical_package_digest = contract.canonical_package_digest
    core.__file__ = __file__


def configure_core() -> Any:
    _prime_core()

    def validate_authorization(*args: Any, **kwargs: Any) -> dict[str, Any]:
        value = _BASE_VALIDATE_AUTHORIZATION(*args, **kwargs)
        package_root = kwargs.get("package_root")
        core.require(
            isinstance(package_root, Path),
            "AUTHORIZATION_PACKAGE_ROOT_MISSING",
        )
        core.require(_BOUND_PHYSICAL_REQUEST is not None, "PHYSICAL_REQUEST_NOT_BOUND")
        try:
            contract.validate_authorization_contract(
                value, _BOUND_PHYSICAL_REQUEST, package_root
            )
        except contract.ContractError as exc:
            raise core.ExecutionError(str(exc)) from exc
        return value

    core.validate_authorization = validate_authorization
    try:
        import serial  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise serial_repair.HandshakeRepairError("PYSERIAL_UNAVAILABLE") from exc

    session_class = upstream.realtime.RealtimeSerialCaptureSession
    _install_tracked_pacing(session_class, sleep=pacing.time.sleep)

    repaired_controller = upstream.RealtimeRepairedHandshakeController(
        core, serial.Serial
    )
    repaired_controller.install()
    core.require(_EVIDENCE_ROOT is not None, "PREPARE_EVIDENCE_ROOT_NOT_BOUND")
    panic_controller = upstream.PanicTimelineEvidenceExecutionController(
        repaired_controller, _EVIDENCE_ROOT
    )
    panic_controller.install()
    setattr(
        core,
        "_d2_11_prepare_panic_timeline_controller",
        panic_controller,
    )

    core.require(
        _DELIVERY_EVIDENCE_ROOT is not None,
        "DELIVERY_EVIDENCE_ROOT_NOT_BOUND",
    )
    delivery_controller = PacedDeliveryEvidenceController(
        core, panic_controller, _DELIVERY_EVIDENCE_ROOT
    )
    delivery_controller.install()
    setattr(core, "_d2_11_paced_delivery_controller", delivery_controller)

    core.require(
        _TERMINALIZATION_EVIDENCE_ROOT is not None,
        "TERMINALIZATION_EVIDENCE_ROOT_NOT_BOUND",
    )
    terminal_controller = terminalization.TerminalizationSafetyController(
        core, _TERMINALIZATION_EVIDENCE_ROOT
    )
    terminal_controller.install()
    setattr(core, "_d2_11_terminalization_controller", terminal_controller)
    return core


def parser() -> argparse.ArgumentParser:
    value = _ORIGINAL_HANDOFF_PARSER()
    value.add_argument("--prepare-evidence-root", type=Path, required=True)
    value.add_argument("--delivery-evidence-root", type=Path, required=True)
    value.add_argument("--terminalization-evidence-root", type=Path, required=True)
    return value


def _bind_empty_root(value: Path, code: str) -> Path:
    root = handoff.normalized_path(value, strict=False)
    if root.exists():
        core.require(root.is_dir() and not root.is_symlink(), code + "_INVALID")
        core.require(not any(root.iterdir()), code + "_NOT_EMPTY")
    return root


def prepare_payload_handoff(args: argparse.Namespace) -> None:
    global _BOUND_PHYSICAL_REQUEST
    global _EVIDENCE_ROOT, _DELIVERY_EVIDENCE_ROOT, _TERMINALIZATION_EVIDENCE_ROOT
    _prime_payload_constants()
    _ORIGINAL_PREPARE_PAYLOAD_HANDOFF(args)
    request_path = handoff.normalized_path(args.physical_request, strict=True)
    core.require(
        request_path.is_file() and not request_path.is_symlink(),
        "PHYSICAL_REQUEST_FILE_INVALID",
    )
    try:
        raw = json.loads(request_path.read_text(encoding="utf-8"))
        core.require(isinstance(raw, dict), "PHYSICAL_REQUEST_FILE_INVALID")
        _BOUND_PHYSICAL_REQUEST = contract.validate_physical_request(
            raw, args.package_root
        )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        contract.ContractError,
    ) as exc:
        code = (
            str(exc)
            if isinstance(exc, contract.ContractError)
            else "PHYSICAL_REQUEST_FILE_INVALID"
        )
        raise core.ExecutionError(code) from exc
    _EVIDENCE_ROOT = _bind_empty_root(
        args.prepare_evidence_root, "PREPARE_EVIDENCE_ROOT"
    )
    _DELIVERY_EVIDENCE_ROOT = _bind_empty_root(
        args.delivery_evidence_root, "DELIVERY_EVIDENCE_ROOT"
    )
    _TERMINALIZATION_EVIDENCE_ROOT = _bind_empty_root(
        args.terminalization_evidence_root, "TERMINALIZATION_EVIDENCE_ROOT"
    )
    roots = {
        _EVIDENCE_ROOT.resolve(strict=False),
        _DELIVERY_EVIDENCE_ROOT.resolve(strict=False),
        _TERMINALIZATION_EVIDENCE_ROOT.resolve(strict=False),
    }
    core.require(len(roots) == 3, "EVIDENCE_ROOTS_NOT_DISTINCT")
    args.physical_request = request_path


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
        root = args.package_root.expanduser().resolve(strict=True)
        request = json.loads(args.physical_request.read_text(encoding="utf-8"))
        authorization = json.loads(
            args.authorization_record.read_text(encoding="utf-8")
        )
        now = (
            datetime.fromisoformat(args.now.replace("Z", "+00:00")).astimezone(
                timezone.utc
            )
            if args.now
            else None
        )
        contract.validate_authorization_contract(
            authorization, request, root, now=now
        )
        result: dict[str, Any] = {
            "schema": (
                "gh.h3.n2.stage2d9r-g3r-d2-11-prepare-transport-"
                "pacing-authorization-contract-check/1"
            ),
            "status": "PASS",
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
        rc = 0
    except Exception as exc:
        result = {
            "schema": (
                "gh.h3.n2.stage2d9r-g3r-d2-11-prepare-transport-"
                "pacing-authorization-contract-check/1"
            ),
            "status": "FAIL",
            "failure_code": _error_code(exc),
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


def source_status() -> dict[str, Any]:
    return {
        "schema": (
            "gh.h3.n2.stage2d9r-g3r-d2-11-prepare-transport-"
            "pacing-execution-binding-source/1"
        ),
        "status": "SOURCE_ONLY_REQUIRES_NEW_EXACT_D2_11_AUTHORIZATION",
        "decision_id": contract.DECISION_ID,
        "d2_request_id": D2_REQUEST_ID,
        "predecessor_request_id": contract.D2_10_ID,
        "predecessor_status": "CONSUMED_FAILED",
        "predecessor_terminalization_state": "FORENSIC_TERMINAL_CLOSED",
        "predecessor_locked_recovery_outcome": "UNKNOWN",
        "paced_chunk_bytes": pacing.PACED_CHUNK_BYTES,
        "inter_chunk_delay_ms": int(
            pacing.INTER_CHUNK_DELAY_SECONDS * 1000
        ),
        "terminalization_guard_installed_only_during_execute": True,
        "physical_request_created": False,
        "physical_authorization_created": False,
        "board_operation": False,
        "usb_enumeration": False,
        "serial_operation": False,
        "esptool_operation": False,
        "flash_operation": False,
        "network_operation": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }


def main() -> int:
    if len(sys.argv) == 1:
        print(json.dumps(source_status(), sort_keys=True))
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
