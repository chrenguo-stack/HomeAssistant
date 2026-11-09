from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ENCODING_SCHEMA = "gh.n3w-t1-ha-predecessor-recovery-encoding/1"
QUALIFICATION_SCHEMA = "gh.n3w-t1-ha-predecessor-recovery-qualification/1"

PREDECESSOR_UPSTREAM_REPOSITORY = "ghcr.io/home-assistant/home-assistant"
PREDECESSOR_UPSTREAM_TAG = "2026.10.0"
PREDECESSOR_ARM64_MANIFEST_DIGEST = (
    "sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4"
)
PREDECESSOR_IMAGE_REF = "local/n3w-homeassistant:2026.10.0-0c73235a"
PREDECESSOR_IMAGE_ID = (
    "sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879"
)

GZIP_LEVEL = 1
GZIP_NO_NAME = True
ROUND_UP_QUANTUM_BYTES = 256 * 1024 * 1024
RECOVERY_MARGIN_RATIO_PERCENT = 110
MAX_SAFE_BYTES = (1 << 63) - 1


class RecoveryEncodingError(ValueError):
    pass


def docker_save_argv(image_ref: str = PREDECESSOR_IMAGE_REF) -> tuple[str, ...]:
    if image_ref != PREDECESSOR_IMAGE_REF:
        raise RecoveryEncodingError("predecessor_image_ref_mismatch")
    return ("docker", "save", image_ref)


def gzip_argv() -> tuple[str, ...]:
    return ("gzip", "-1", "-n", "-c")


def export_predecessor_archive(
    destination: Path,
    *,
    image_ref: str = PREDECESSOR_IMAGE_REF,
) -> tuple[int, str]:
    if not isinstance(destination, Path) or not destination.is_absolute():
        raise RecoveryEncodingError("recovery_destination_invalid")
    if destination.is_symlink() or destination.exists():
        raise RecoveryEncodingError("recovery_destination_exists")
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise RecoveryEncodingError("recovery_destination_parent_invalid")

    docker_argv = docker_save_argv(image_ref)
    gzip_command = gzip_argv()
    try:
        with destination.open("xb") as output:
            docker = subprocess.Popen(
                docker_argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert docker.stdout is not None
            gzip = subprocess.Popen(
                gzip_command,
                stdin=docker.stdout,
                stdout=output,
                stderr=subprocess.PIPE,
            )
            docker.stdout.close()
            _, gzip_stderr = gzip.communicate()
            _, docker_stderr = docker.communicate()
            if docker.returncode != 0:
                raise RecoveryEncodingError(
                    "docker_save_failed:"
                    + docker_stderr.decode(errors="replace")[:512]
                )
            if gzip.returncode != 0:
                raise RecoveryEncodingError(
                    "gzip_failed:"
                    + gzip_stderr.decode(errors="replace")[:512]
                )
            output.flush()
            os.fsync(output.fileno())
    except RecoveryEncodingError:
        destination.unlink(missing_ok=True)
        raise
    except (OSError, subprocess.SubprocessError) as error:
        destination.unlink(missing_ok=True)
        raise RecoveryEncodingError("recovery_export_failed") from error

    size = destination.stat().st_size
    if size <= 0 or size > MAX_SAFE_BYTES:
        destination.unlink(missing_ok=True)
        raise RecoveryEncodingError("recovery_export_size_invalid")
    return size, sha256_file(destination)


def round_up(value: int, quantum: int = ROUND_UP_QUANTUM_BYTES) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise RecoveryEncodingError("positive_integer_required")
    if isinstance(quantum, bool) or not isinstance(quantum, int) or quantum <= 0:
        raise RecoveryEncodingError("positive_quantum_required")
    if value > MAX_SAFE_BYTES or quantum > MAX_SAFE_BYTES:
        raise RecoveryEncodingError("byte_value_out_of_range")
    result = ((value + quantum - 1) // quantum) * quantum
    if result > MAX_SAFE_BYTES:
        raise RecoveryEncodingError("rounded_byte_value_out_of_range")
    return result


def qualification_measured_export_bytes(sample_sizes: tuple[int, ...]) -> int:
    if not isinstance(sample_sizes, tuple) or len(sample_sizes) < 2:
        raise RecoveryEncodingError("qualification_samples_insufficient")
    for value in sample_sizes:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value <= 0
            or value > MAX_SAFE_BYTES
        ):
            raise RecoveryEncodingError("qualification_sample_size_invalid")
    return max(sample_sizes)


def predecessor_recovery_budget_bytes(measured_export_bytes: int) -> int:
    if (
        isinstance(measured_export_bytes, bool)
        or not isinstance(measured_export_bytes, int)
        or measured_export_bytes <= 0
        or measured_export_bytes > MAX_SAFE_BYTES
    ):
        raise RecoveryEncodingError("measured_export_bytes_invalid")

    ratio_bound = (
        measured_export_bytes * RECOVERY_MARGIN_RATIO_PERCENT + 99
    ) // 100
    additive_bound = measured_export_bytes + ROUND_UP_QUANTUM_BYTES
    if additive_bound > MAX_SAFE_BYTES:
        raise RecoveryEncodingError("recovery_budget_overflow")

    return round_up(max(ratio_bound, additive_bound))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class QualificationEvidence:
    source_head: str
    measured_export_bytes: int
    archive_sha256: str
    portable_identity_sha256: str

    def to_dict(self) -> dict[str, Any]:
        budget = predecessor_recovery_budget_bytes(self.measured_export_bytes)
        return {
            "schema": QUALIFICATION_SCHEMA,
            "source_head": self.source_head,
            "predecessor": {
                "upstream_repository": PREDECESSOR_UPSTREAM_REPOSITORY,
                "upstream_tag": PREDECESSOR_UPSTREAM_TAG,
                "arm64_manifest_digest": PREDECESSOR_ARM64_MANIFEST_DIGEST,
                "image_ref": PREDECESSOR_IMAGE_REF,
                "image_id": PREDECESSOR_IMAGE_ID,
            },
            "encoding": {
                "schema": ENCODING_SCHEMA,
                "representation": "docker-save",
                "compression": "gzip",
                "compression_level": GZIP_LEVEL,
                "no_name": GZIP_NO_NAME,
                "docker_save_argv": list(docker_save_argv()),
                "gzip_argv": list(gzip_argv()),
            },
            "measurement": {
                "archive_sha256": self.archive_sha256,
                "measured_export_bytes": self.measured_export_bytes,
                "portable_identity_sha256": self.portable_identity_sha256,
            },
            "budget": {
                "round_up_quantum_bytes": ROUND_UP_QUANTUM_BYTES,
                "ratio_percent": RECOVERY_MARGIN_RATIO_PERCENT,
                "predecessor_recovery_budget_bytes": budget,
            },
        }


def canonical_sha256(document: dict[str, Any]) -> str:
    raw = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
