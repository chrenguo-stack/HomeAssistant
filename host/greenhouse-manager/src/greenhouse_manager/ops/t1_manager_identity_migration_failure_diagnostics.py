from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TypeVar

from .t1_manager_identity_migration_production_runtime_probe import (
    ManagerRuntimeProbeFailureCode,
)

SCHEMA = "gh.m2.t1-manager-identity-failure-diagnostic/1"
PROGRESS_SCHEMA = "gh.m2.t1-manager-identity-stage-progress/1"
FAILURE_FILE = "failure-diagnostic.json"
ROLLBACK_FAILURE_FILE = "rollback-failure-diagnostic.json"
PROGRESS_FILE = "stage-progress.json"
_STAGE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
_EXCEPTION = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,95}$")
_PROBE_FAILURE_CODES = frozenset(code.value for code in ManagerRuntimeProbeFailureCode)

FAILURE_CODES = {
    "adapter_prepare": "M2_MANAGER_ADAPTER_PREPARE_FAILED",
    "mutation_pipeline": "M2_MANAGER_MUTATION_PIPELINE_FAILED",
    "manager_recreate": "M2_MANAGER_RECREATE_FAILED",
    "authenticated_identity": "M2_MANAGER_IDENTITY_BINDING_FAILED",
    "ingress_subscription": "M2_MANAGER_INGRESS_SUBSCRIPTION_FAILED",
    "canonical_publication": "M2_MANAGER_CANONICAL_PUBLICATION_FAILED",
    "availability_publication": "M2_MANAGER_AVAILABILITY_PUBLICATION_FAILED",
    "discovery_publication": "M2_MANAGER_DISCOVERY_PUBLICATION_FAILED",
    "reconnect": "M2_MANAGER_RECONNECT_FAILED",
    "existing_entities": "M2_MANAGER_ENTITY_CONTINUITY_FAILED",
    "postactivation_pipeline": "M2_MANAGER_POSTACTIVATION_PIPELINE_FAILED",
    "postactivation_audit": "M2_MANAGER_POSTACTIVATION_AUDIT_FAILED",
    "rollback_pipeline": "M2_MANAGER_ROLLBACK_PIPELINE_FAILED",
    "rollback_manager_recreate": "M2_MANAGER_ROLLBACK_RECREATE_FAILED",
    "rollback_anonymous_path": "M2_MANAGER_ROLLBACK_ANONYMOUS_PATH_FAILED",
    "rollback_existing_entities": "M2_MANAGER_ROLLBACK_ENTITY_CONTINUITY_FAILED",
}

T = TypeVar("T")


class ManagerFailureDiagnosticError(RuntimeError):
    pass


class ManagerDriverLike(Protocol):
    def recreate_manager(
        self,
        *,
        environment_file: Path,
        password_file: Path,
        overlay_file: Path,
    ) -> None: ...

    def verify_authenticated_identity(self, username: str, client_id: str) -> None: ...

    def verify_ingress_subscription(self) -> None: ...

    def verify_canonical_publication(self) -> None: ...

    def verify_availability_publication(self) -> None: ...

    def verify_discovery_publication(self) -> None: ...

    def verify_reconnect(self) -> None: ...

    def verify_existing_entities(self) -> None: ...

    def postactivation_audit(self) -> dict[str, object]: ...

    def recreate_after_rollback(self) -> None: ...

    def verify_legacy_anonymous_path(self) -> None: ...


class TransactionAdaptersLike(Protocol):
    mutation_started: bool

    def prepare(self) -> dict[str, object]: ...

    def mutation_executor(self) -> dict[str, object]: ...

    def postactivation_auditor(self) -> dict[str, object]: ...

    def rollback_executor(self) -> dict[str, object]: ...


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _private_directory(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if (
        not resolved.is_dir()
        or resolved.is_symlink()
        or resolved.stat().st_mode & 0o077
    ):
        raise ManagerFailureDiagnosticError(f"{label} is missing, unsafe, or not private")
    return resolved


def _private_json(path: Path, label: str) -> dict[str, Any]:
    if (
        not path.is_file()
        or path.is_symlink()
        or path.stat().st_mode & 0o777 != 0o600
    ):
        raise ManagerFailureDiagnosticError(f"{label} is missing, unsafe, or not mode 0600")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ManagerFailureDiagnosticError(f"{label} is invalid") from error
    if not isinstance(document, dict):
        raise ManagerFailureDiagnosticError(f"{label} must be a JSON object")
    return document


def _atomic_private_write(path: Path, document: Mapping[str, Any]) -> None:
    if path.exists() and path.is_symlink():
        raise ManagerFailureDiagnosticError("diagnostic target cannot be a symlink")
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(_canonical(document) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _stage(value: str) -> str:
    if _STAGE.fullmatch(value) is None or value not in FAILURE_CODES:
        raise ValueError("manager diagnostic stage is invalid")
    return value


def _exception_name(error: Exception) -> str:
    name = type(error).__name__
    if _EXCEPTION.fullmatch(name) is None:
        return "Exception"
    return name


def _probe_failure_code(error: Exception) -> str | None:
    value = getattr(error, "failure_code", None)
    if isinstance(value, str) and value in _PROBE_FAILURE_CODES:
        return value
    return None


class TransactionStageRecorder:
    def __init__(self, workspace_directory: str | Path) -> None:
        self.workspace = _private_directory(
            Path(workspace_directory),
            "manager production transaction workspace",
        )
        self.progress_path = self.workspace / PROGRESS_FILE
        self.failure_path = self.workspace / FAILURE_FILE
        self.rollback_failure_path = self.workspace / ROLLBACK_FAILURE_FILE

    def _progress(self, *, stage: str, completed: bool) -> None:
        document = {
            "schema": PROGRESS_SCHEMA,
            "stage": _stage(stage),
            "completed": completed,
            "observed_at": _timestamp(),
            "secret_values_included": False,
            "path_values_redacted": True,
        }
        _atomic_private_write(self.progress_path, document)

    def _failure(self, *, stage: str, error: Exception, rollback: bool) -> None:
        path = self.rollback_failure_path if rollback else self.failure_path
        if path.exists():
            _private_json(path, "manager failure diagnostic")
            return
        document = {
            "schema": SCHEMA,
            "failed_stage": _stage(stage),
            "failure_code": FAILURE_CODES[stage],
            "exception_class": _exception_name(error),
            "rollback_failure": rollback,
            "observed_at": _timestamp(),
            "exception_message_included": False,
            "secret_values_included": False,
            "path_values_redacted": True,
        }
        probe_failure_code = _probe_failure_code(error)
        if probe_failure_code is not None:
            document["probe_failure_code"] = probe_failure_code
        _atomic_private_write(path, document)

    def run(self, stage: str, operation: Callable[..., T], *args: object, **kwargs: object) -> T:
        checked = _stage(stage)
        self._progress(stage=checked, completed=False)
        try:
            result = operation(*args, **kwargs)
        except Exception as error:
            self._failure(stage=checked, error=error, rollback=False)
            raise
        self._progress(stage=checked, completed=True)
        return result

    def run_rollback(
        self,
        stage: str,
        operation: Callable[..., T],
        *args: object,
        **kwargs: object,
    ) -> T:
        checked = _stage(stage)
        self._progress(stage=checked, completed=False)
        try:
            result = operation(*args, **kwargs)
        except Exception as error:
            self._failure(stage=checked, error=error, rollback=True)
            raise
        self._progress(stage=checked, completed=True)
        return result


class StageAwareManagerDriver:
    def __init__(self, inner: ManagerDriverLike, recorder: TransactionStageRecorder) -> None:
        self.inner = inner
        self.recorder = recorder

    def recreate_manager(
        self,
        *,
        environment_file: Path,
        password_file: Path,
        overlay_file: Path,
    ) -> None:
        self.recorder.run(
            "manager_recreate",
            self.inner.recreate_manager,
            environment_file=environment_file,
            password_file=password_file,
            overlay_file=overlay_file,
        )

    def verify_authenticated_identity(self, username: str, client_id: str) -> None:
        self.recorder.run(
            "authenticated_identity",
            self.inner.verify_authenticated_identity,
            username,
            client_id,
        )

    def verify_ingress_subscription(self) -> None:
        self.recorder.run("ingress_subscription", self.inner.verify_ingress_subscription)

    def verify_canonical_publication(self) -> None:
        self.recorder.run("canonical_publication", self.inner.verify_canonical_publication)

    def verify_availability_publication(self) -> None:
        self.recorder.run(
            "availability_publication",
            self.inner.verify_availability_publication,
        )

    def verify_discovery_publication(self) -> None:
        self.recorder.run("discovery_publication", self.inner.verify_discovery_publication)

    def verify_reconnect(self) -> None:
        self.recorder.run("reconnect", self.inner.verify_reconnect)

    def verify_existing_entities(self) -> None:
        self.recorder.run("existing_entities", self.inner.verify_existing_entities)

    def postactivation_audit(self) -> dict[str, object]:
        return self.recorder.run("postactivation_audit", self.inner.postactivation_audit)

    def recreate_after_rollback(self) -> None:
        self.recorder.run_rollback(
            "rollback_manager_recreate",
            self.inner.recreate_after_rollback,
        )

    def verify_legacy_anonymous_path(self) -> None:
        self.recorder.run_rollback(
            "rollback_anonymous_path",
            self.inner.verify_legacy_anonymous_path,
        )


class StageAwareTransactionAdapters:
    def __init__(
        self,
        inner: TransactionAdaptersLike,
        recorder: TransactionStageRecorder,
    ) -> None:
        self.inner = inner
        self.recorder = recorder

    @property
    def mutation_started(self) -> bool:
        return self.inner.mutation_started

    def prepare(self) -> dict[str, object]:
        return self.recorder.run("adapter_prepare", self.inner.prepare)

    def mutation_executor(self) -> dict[str, object]:
        return self.recorder.run("mutation_pipeline", self.inner.mutation_executor)

    def postactivation_auditor(self) -> dict[str, object]:
        return self.recorder.run(
            "postactivation_pipeline",
            self.inner.postactivation_auditor,
        )

    def rollback_executor(self) -> dict[str, object]:
        return self.recorder.run_rollback(
            "rollback_pipeline",
            self.inner.rollback_executor,
        )


def build_failure_diagnostic(transaction_workspace: str | Path) -> dict[str, object]:
    workspace = _private_directory(
        Path(transaction_workspace),
        "manager production transaction workspace",
    )
    journal = _private_json(workspace / "journal.json", "manager production journal")
    failure = (
        _private_json(workspace / FAILURE_FILE, "manager failure diagnostic")
        if (workspace / FAILURE_FILE).exists()
        else None
    )
    rollback_failure = (
        _private_json(
            workspace / ROLLBACK_FAILURE_FILE,
            "manager rollback failure diagnostic",
        )
        if (workspace / ROLLBACK_FAILURE_FILE).exists()
        else None
    )
    phase = journal.get("phase")
    if not isinstance(phase, str) or not phase:
        raise ManagerFailureDiagnosticError("manager production journal phase is missing")
    result: dict[str, object] = {
        "schema": SCHEMA,
        "transaction_phase": phase,
        "failure_stage_available": failure is not None,
        "rollback_failure_stage_available": rollback_failure is not None,
        "rollback_completed": phase == "rollback_completed",
        "rollback_terminal": phase == "rollback_failed",
        "secret_values_included": False,
        "path_values_redacted": True,
    }
    if failure is not None:
        result.update(
            {
                "failed_stage": failure.get("failed_stage"),
                "failure_code": failure.get("failure_code"),
                "failure_exception_class": failure.get("exception_class"),
            }
        )
    if rollback_failure is not None:
        result.update(
            {
                "rollback_failed_stage": rollback_failure.get("failed_stage"),
                "rollback_failure_code": rollback_failure.get("failure_code"),
                "rollback_exception_class": rollback_failure.get("exception_class"),
            }
        )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read the redacted failure stage for one manager production transaction "
            "without reading credential material or modifying services."
        )
    )
    parser.add_argument("transaction_workspace")
    args = parser.parse_args(argv)
    try:
        result = build_failure_diagnostic(args.transaction_workspace)
    except (ManagerFailureDiagnosticError, OSError, UnicodeError, ValueError) as error:
        print(f"T1 manager failure diagnostic failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
