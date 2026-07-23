#!/usr/bin/env python3
"""Host-only model for Stage2D9 V69 serial evidence persistence.

The model performs no serial or device I/O. It proves that capture bytes are
atomically preserved on success, fail marker, timeout and host exception while
keeping host write attempt, device acceptance and transaction success distinct.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import tempfile
from typing import Iterable


@dataclass
class CaptureState:
    host_write_attempted: bool = False
    device_command_accepted: bool = False
    transaction_succeeded: bool = False
    terminal_reason: str = "none"
    log_sha256: str = ""
    log_size: int = 0


class CaptureFailure(RuntimeError):
    def __init__(self, message: str, state: CaptureState):
        super().__init__(message)
        self.state = state


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(data)
        stream.flush()
    temporary.replace(path)


def capture_event_stream(
    events: Iterable[str],
    log_path: Path,
    *,
    inject_exception_at: int | None = None,
) -> CaptureState:
    state = CaptureState(host_write_attempted=True)
    capture = bytearray()
    pending_error: Exception | None = None
    try:
        for index, event in enumerate(events):
            if inject_exception_at is not None and index == inject_exception_at:
                raise OSError("simulated host capture exception")
            line = event.rstrip("\r\n") + "\n"
            capture.extend(line.encode("utf-8"))
            if "stage2d9_v69_command_accepted=true" in line:
                state.device_command_accepted = True
            if "stage2d9_v69_prepare=pass" in line or "stage2d9_v69_verify=pass" in line:
                state.device_command_accepted = True
                state.transaction_succeeded = True
                state.terminal_reason = "pass"
                break
            if "stage2d9_v69_executor=fail" in line:
                state.terminal_reason = "device_fail_marker"
                raise RuntimeError("simulated device fail marker")
        else:
            state.terminal_reason = "timeout"
            raise TimeoutError("simulated serial timeout")
    except Exception as exc:
        pending_error = exc
    finally:
        payload = bytes(capture)
        atomic_write(log_path, payload)
        state.log_sha256 = sha256_bytes(payload)
        state.log_size = len(payload)

    if pending_error is not None:
        if state.terminal_reason == "none":
            state.terminal_reason = "host_exception"
        raise CaptureFailure(str(pending_error), state) from pending_error
    return state


def state_dict(state: CaptureState) -> dict[str, object]:
    return asdict(state)
