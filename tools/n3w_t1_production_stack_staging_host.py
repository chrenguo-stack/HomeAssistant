#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence

REPOSITORY = "chrenguo-stack/HomeAssistant"


class HostTransportError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(
    command: Sequence[str],
    *,
    timeout: float | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        tuple(command),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        reason = completed.stderr.strip() or completed.stdout.strip()
        raise HostTransportError(
            f"command_failed:{command[0]}:{completed.returncode}:{reason[:500]}"
        )
    return completed


def _remote_command(parts: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def _download_artifact(
    work: Path,
    *,
    run_id: str,
    artifact_name: str,
) -> None:
    _run(
        (
            "gh",
            "run",
            "download",
            run_id,
            "-R",
            REPOSITORY,
            "-n",
            artifact_name,
            "-D",
            str(work),
        ),
        timeout=900,
    )


def _verify_artifact(
    work: Path,
    *,
    archive_sha256: str,
    executor_sha256: str,
    manifest_sha256: str,
) -> None:
    archive = work / "payload-archive.tar.gz"
    executor_sidecar = work / "executor.sha256"
    manifest_sidecar = work / "payload-manifest.sha256"
    if _sha256_file(archive) != archive_sha256:
        raise HostTransportError("payload_archive_sha256_mismatch")
    if executor_sidecar.read_text(encoding="utf-8").strip() != executor_sha256:
        raise HostTransportError("executor_sidecar_mismatch")
    if manifest_sidecar.read_text(encoding="utf-8").strip() != manifest_sha256:
        raise HostTransportError("manifest_sidecar_mismatch")


def _remote_mktemp(t1: str, prefix: str) -> str:
    command = _remote_command(("mktemp", "-d", f"/tmp/{prefix}.XXXXXX"))
    completed = _run(("ssh", "-n", t1, command), timeout=60)
    path = completed.stdout.strip()
    if not path.startswith(f"/tmp/{prefix}."):
        raise HostTransportError("remote_temp_path_invalid")
    return path


def _remote_prepare(
    t1: str,
    remote_dir: str,
    local_archive: Path,
    *,
    archive_sha256: str,
    executor_sha256: str,
    manifest_sha256: str,
) -> None:
    _run(
        (
            "scp",
            str(local_archive),
            f"{t1}:{remote_dir}/payload.tar.gz",
        ),
        timeout=900,
    )
    command = _remote_command(
        (
            "python3",
            "-c",
            (
                "import hashlib,sys,tarfile;"
                "from pathlib import Path;"
                "root=Path(sys.argv[1]);"
                "archive=root/'payload.tar.gz';"
                "assert hashlib.sha256(archive.read_bytes()).hexdigest()==sys.argv[2];"
                "tarfile.open(archive,'r:gz').extractall(root);"
                "assert hashlib.sha256((root/'tools/n3w_t1_production_stack_staging.py').read_bytes()).hexdigest()==sys.argv[3];"
                "assert hashlib.sha256((root/'payload-manifest.json').read_bytes()).hexdigest()==sys.argv[4]"
            ),
            remote_dir,
            archive_sha256,
            executor_sha256,
            manifest_sha256,
        )
    )
    _run(("ssh", "-n", t1, command), timeout=300)


def _invoke_remote_executor(
    t1: str,
    remote_dir: str,
    *,
    phase: str,
    executor_sha256: str,
    authorization_id: str | None,
) -> subprocess.CompletedProcess[str]:
    parts = [
        "python3",
        f"{remote_dir}/tools/n3w_t1_production_stack_staging.py",
        "--phase",
        phase,
        "--payload-root",
        remote_dir,
        "--expected-executor-sha256",
        executor_sha256,
    ]
    if phase == "apply":
        if not authorization_id:
            raise HostTransportError("authorization_id_required")
        parts.extend(("--authorization-id", authorization_id))
    return _run(
        ("ssh", "-n", t1, _remote_command(parts)),
        timeout=3600,
        check=False,
    )


def _remote_cleanup(t1: str, remote_dir: str) -> None:
    _run(
        ("ssh", "-n", t1, _remote_command(("rm", "-rf", remote_dir))),
        timeout=60,
        check=False,
    )


def _emit(value: dict[str, object]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")), flush=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--t1", required=True)
    parser.add_argument("--phase", choices=("preflight", "apply"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--executor-sha256", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--authorization-id")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.phase == "apply" and not args.authorization_id:
        raise SystemExit("apply requires --authorization-id")

    work = Path(tempfile.mkdtemp(prefix="n3w-staging-host."))
    remote_dir: str | None = None
    apply_invoked = False
    try:
        _download_artifact(
            work,
            run_id=args.run_id,
            artifact_name=args.artifact_name,
        )
        _verify_artifact(
            work,
            archive_sha256=args.archive_sha256,
            executor_sha256=args.executor_sha256,
            manifest_sha256=args.manifest_sha256,
        )
        remote_dir = _remote_mktemp(
            args.t1,
            "n3w-staging-apply" if args.phase == "apply" else "n3w-staging-preflight",
        )
        _remote_prepare(
            args.t1,
            remote_dir,
            work / "payload-archive.tar.gz",
            archive_sha256=args.archive_sha256,
            executor_sha256=args.executor_sha256,
            manifest_sha256=args.manifest_sha256,
        )
        if args.phase == "apply":
            apply_invoked = True
            _emit(
                {
                    "event": "apply_transport_invoked",
                    "authorization_id": args.authorization_id,
                    "authorization_claimed": True,
                    "do_not_replay": True,
                }
            )

        completed = _invoke_remote_executor(
            args.t1,
            remote_dir,
            phase=args.phase,
            executor_sha256=args.executor_sha256,
            authorization_id=args.authorization_id,
        )
        if completed.stdout:
            sys.stdout.write(completed.stdout)
        if completed.stderr:
            sys.stderr.write(completed.stderr)
        sys.stdout.flush()
        sys.stderr.flush()

        if completed.returncode == 0:
            _remote_cleanup(args.t1, remote_dir)
            shutil.rmtree(work)
            _emit(
                {
                    "transport_completion": "KNOWN_SUCCESS",
                    "phase": args.phase,
                    "authorization_claimed": apply_invoked,
                    "authorization_consumed": apply_invoked,
                }
            )
            return 0

        _emit(
            {
                "transport_completion": "FAILED_OR_UNKNOWN",
                "phase": args.phase,
                "remote_payload_retained": remote_dir,
                "local_evidence_retained": str(work),
                "authorization_claimed": apply_invoked,
                "authorization_consumed": apply_invoked,
                "do_not_replay": apply_invoked,
                "ssh_returncode": completed.returncode,
            }
        )
        if args.phase == "preflight":
            _remote_cleanup(args.t1, remote_dir)
            shutil.rmtree(work)
        return completed.returncode or 1
    except (HostTransportError, OSError, subprocess.TimeoutExpired) as error:
        _emit(
            {
                "transport_completion": "HOST_ERROR",
                "phase": args.phase,
                "reason": str(error),
                "remote_payload_retained": remote_dir,
                "local_evidence_retained": str(work),
                "authorization_claimed": apply_invoked,
                "authorization_consumed": apply_invoked,
                "do_not_replay": apply_invoked,
            }
        )
        if args.phase == "preflight" and remote_dir:
            _remote_cleanup(args.t1, remote_dir)
        if args.phase == "preflight":
            shutil.rmtree(work, ignore_errors=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
