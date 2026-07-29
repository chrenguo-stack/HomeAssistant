#!/usr/bin/env python3
"""Reusable post-claim terminalization guard for future physical executors.

This module has no CLI and cannot start a physical run. A later, separately
bound physical wrapper may install it after all of its evidence controllers.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Callable

HEX40 = re.compile(r"^[0-9a-f]{40}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _code(exc: BaseException) -> str:
    if exc.args and isinstance(exc.args[0], str):
        return exc.args[0]
    return type(exc).__name__


def _write_exclusive(path: Path, value: object) -> None:
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


def _replace(path: Path, value: object) -> None:
    if path.exists() and (not path.is_file() or path.is_symlink()):
        raise RuntimeError("TERMINAL_TARGET_INVALID")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temp = path.with_name(path.name + ".terminalization-guard.tmp")
    if temp.exists():
        raise RuntimeError("TERMINAL_TEMP_EXISTS")
    _write_exclusive(temp, value)
    os.replace(temp, path)
    os.chmod(path, 0o600)
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        pass


class TerminalizationSafetyController:
    """Protects result, marker, and recovery evidence after an atomic claim."""

    def __init__(self, core: Any, evidence_root: Path) -> None:
        self.core = core
        self.evidence_root = evidence_root
        self.recovery_path = evidence_root / "locked-recovery-terminal.json"
        self.guard_path = evidence_root / "terminalization-guard.json"
        self._original_execute: Callable[..., Any] = core.execute
        self._original_result_object: Callable[..., dict[str, Any]] = (
            core.result_object
        )
        self._original_locked_recovery: Callable[..., bool] = core.locked_recovery
        self._last_result_kwargs: dict[str, Any] | None = None
        self._last_result: dict[str, Any] | None = None
        self._recovery_state: dict[str, Any] | None = None

    def install(self) -> None:
        self.evidence_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.evidence_root, 0o700)
        self.core.locked_recovery = self.locked_recovery
        self.core.result_object = self.result_object
        self.core.execute = self.execute

    def _persist_recovery(self, value: dict[str, Any]) -> None:
        self._recovery_state = dict(value)
        _replace(self.recovery_path, value)

    def locked_recovery(self, *args: Any, **kwargs: Any) -> bool:
        started = {
            "schema": (
                "gh.h3.n2.stage2d9r-g3r-locked-recovery-terminal-evidence/1"
            ),
            "status": "STARTED",
            "started_at": _utc_now(),
            "attempt_count": 1,
            "scope": "TEST_PARTITION_ONLY",
            "succeeded": None,
            "failure_code": None,
            "private_paths_included": False,
            "secret_values_included": False,
        }
        self._persist_recovery(started)
        try:
            succeeded = bool(self._original_locked_recovery(*args, **kwargs))
        except BaseException as exc:
            failed = dict(started)
            failed.update(
                {
                    "status": "FAILED",
                    "completed_at": _utc_now(),
                    "succeeded": False,
                    "failure_code": _code(exc),
                }
            )
            self._persist_recovery(failed)
            raise
        completed = dict(started)
        completed.update(
            {
                "status": "COMPLETED" if succeeded else "FAILED",
                "completed_at": _utc_now(),
                "succeeded": succeeded,
                "failure_code": None if succeeded else "RECOVERY_RETURNED_FALSE",
            }
        )
        self._persist_recovery(completed)
        return succeeded

    @staticmethod
    def _repository_head(authorization: dict[str, Any]) -> str | None:
        for key in ("repository_head_sha", "main_sha"):
            value = authorization.get(key)
            if isinstance(value, str) and HEX40.fullmatch(value):
                return value
        return None

    def _fallback_result(
        self,
        kwargs: dict[str, Any],
        generator_error: BaseException,
    ) -> dict[str, Any]:
        authorization = kwargs.get("authorization")
        if not isinstance(authorization, dict):
            authorization = {}
        repository_head = self._repository_head(authorization)
        primary = kwargs.get("failure_code")
        if not isinstance(primary, str) or not primary:
            primary = "POST_CLAIM_EXECUTION_FAILED"
        recovery = self._recovery_state or {}
        recovery_attempted = bool(
            kwargs.get("recovery_attempted") or recovery.get("attempt_count") == 1
        )
        recovery_succeeded = recovery.get("succeeded")
        if not isinstance(recovery_succeeded, bool):
            candidate = kwargs.get("recovery_succeeded")
            recovery_succeeded = candidate if isinstance(candidate, bool) else None
        prepare_log = kwargs.get("prepare_log")
        verify_log = kwargs.get("verify_log")
        value: dict[str, Any] = {
            "schema": getattr(self.core, "RESULT_SCHEMA", "unknown"),
            "stage": getattr(self.core, "STAGE", "unknown"),
            "d2_request_id": getattr(self.core, "D2_REQUEST_ID", "unknown"),
            "status": "CONSUMED_FAILED",
            "terminal_state": (
                "LOCKED_RECOVERY_COMPLETED"
                if recovery_succeeded is True
                else "CONSUMED_FAILED"
            ),
            "failure_code": primary,
            "primary_failure_code": primary,
            "secondary_failure_code": type(generator_error).__name__,
            "secondary_failure_detail": _code(generator_error),
            "terminalization_fallback_used": True,
            "request_binding_sha256": authorization.get(
                "request_binding_sha256"
            ),
            "authorization_record_sha256": authorization.get(
                "authorization_record_sha256"
            ),
            "source_sha": authorization.get("source_sha"),
            "repository_head_sha": repository_head,
            "main_sha": repository_head,
            "board_identity_sha256": authorization.get("board_identity_sha256"),
            "serial_identity_sha256": authorization.get(
                "serial_identity_sha256"
            ),
            "baseline_state_sha256": authorization.get("baseline_state_sha256"),
            "flash_sha256": kwargs.get("flash_sha256"),
            "prepare_count": (
                1
                if isinstance(prepare_log, Path) and prepare_log.exists()
                else 0
            ),
            "verify_count": (
                1 if isinstance(verify_log, Path) and verify_log.exists() else 0
            ),
            "recovery_attempted": recovery_attempted,
            "recovery_succeeded": recovery_succeeded,
            "recovery_failure_code": recovery.get("failure_code"),
            "recovery_terminal_evidence_persisted": bool(self._recovery_state),
            "activate_executed": False,
            "cleanup_executed": False,
            "production_operation": False,
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "private_paths_included": False,
            "secret_values_included": False,
        }
        value["terminal_result_sha256"] = self.core.canonical_sha256(value)
        return value

    def result_object(self, **kwargs: Any) -> dict[str, Any]:
        self._last_result_kwargs = dict(kwargs)
        try:
            value = self._original_result_object(**kwargs)
            if not isinstance(value, dict):
                raise TypeError("RESULT_OBJECT_NOT_MAPPING")
            authorization = kwargs.get("authorization")
            if not isinstance(authorization, dict):
                raise TypeError("AUTHORIZATION_NOT_MAPPING")
            repository_head = self._repository_head(authorization)
            if repository_head is None:
                raise KeyError("repository_head_sha")
            value["repository_head_sha"] = repository_head
            value["main_sha"] = repository_head
            value["terminalization_fallback_used"] = False
            if self._recovery_state is not None:
                value["recovery_terminal_evidence_persisted"] = True
                value["recovery_failure_code"] = self._recovery_state.get(
                    "failure_code"
                )
                value["recovery_succeeded"] = self._recovery_state.get(
                    "succeeded"
                )
            value.pop("terminal_result_sha256", None)
            value["terminal_result_sha256"] = self.core.canonical_sha256(value)
        except BaseException as exc:
            value = self._fallback_result(kwargs, exc)
        self._last_result = value
        return value

    def _marker_path(self, args: Any) -> Path:
        name = self.core.sha256_bytes(
            self.core.D2_REQUEST_ID.encode("utf-8")
        ) + ".json"
        return args.state_root.expanduser().resolve(strict=False) / name

    def _authorization(self, args: Any) -> dict[str, Any]:
        try:
            value = json.loads(
                args.authorization_record.expanduser()
                .resolve(strict=True)
                .read_text(encoding="utf-8")
            )
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}

    def _emergency_result(
        self, args: Any, exc: BaseException
    ) -> dict[str, Any]:
        if self._last_result is not None:
            value = dict(self._last_result)
            value["post_result_terminalization_failure_code"] = _code(exc)
            value.pop("terminal_result_sha256", None)
            value["terminal_result_sha256"] = self.core.canonical_sha256(value)
            return value
        kwargs = self._last_result_kwargs or {
            "authorization": self._authorization(args),
            "failure_code": _code(exc),
            "recovery_attempted": self._recovery_state is not None,
            "recovery_succeeded": (
                self._recovery_state.get("succeeded")
                if self._recovery_state is not None
                else None
            ),
        }
        return self._fallback_result(kwargs, exc)

    def _terminal_marker(
        self, result: dict[str, Any], previous: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "schema": getattr(self.core, "MARKER_SCHEMA", previous.get("schema")),
            "stage": getattr(self.core, "STAGE", previous.get("stage")),
            "d2_request_id": getattr(
                self.core, "D2_REQUEST_ID", previous.get("d2_request_id")
            ),
            "status": "CONSUMED_FAILED",
            "failure_code": result.get("failure_code"),
            "primary_failure_code": result.get("primary_failure_code"),
            "secondary_failure_code": result.get("secondary_failure_code"),
            "terminal_result_sha256": result["terminal_result_sha256"],
            "recovery_attempted": result.get("recovery_attempted"),
            "recovery_succeeded": result.get("recovery_succeeded"),
            "one_shot": True,
            "replay_permitted": False,
            "automatic_retry_permitted": False,
            "private_paths_included": False,
            "secret_values_included": False,
        }

    def execute(self, args: Any) -> Any:
        try:
            return self._original_execute(args)
        except BaseException as exc:
            marker_path = self._marker_path(args)
            if marker_path.is_file() and not marker_path.is_symlink():
                try:
                    previous = json.loads(marker_path.read_text(encoding="utf-8"))
                except Exception:
                    previous = {}
                if (
                    isinstance(previous, dict)
                    and previous.get("status") == "CLAIMED"
                ):
                    result = self._emergency_result(args, exc)
                    result_path = args.result_output.expanduser().resolve(
                        strict=False
                    )
                    if not result_path.exists():
                        _write_exclusive(result_path, result)
                    else:
                        try:
                            existing = json.loads(
                                result_path.read_text(encoding="utf-8")
                            )
                        except Exception:
                            existing = None
                        if (
                            isinstance(existing, dict)
                            and isinstance(
                                existing.get("terminal_result_sha256"), str
                            )
                        ):
                            result = existing
                    _replace(
                        marker_path, self._terminal_marker(result, previous)
                    )
                    guard = {
                        "schema": (
                            "gh.h3.n2.stage2d9r-g3r-terminalization-guard/1"
                        ),
                        "status": "TERMINALIZED",
                        "terminalized_at": _utc_now(),
                        "failure_code": _code(exc),
                        "terminal_result_sha256": result[
                            "terminal_result_sha256"
                        ],
                        "replay_permitted": False,
                        "automatic_retry_permitted": False,
                        "private_paths_included": False,
                        "secret_values_included": False,
                    }
                    _replace(self.guard_path, guard)
            raise
