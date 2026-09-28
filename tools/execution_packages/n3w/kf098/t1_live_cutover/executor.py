#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REMOTE_EXECUTOR = PACKAGE_DIR / "remote_cutover.py"
STAGE_ROOT = "/root/n3w-kf098-manager-cutover-20260928-01"
ARTIFACT_ID = 10935052471
ARTIFACT_RUN_ID = 36329597775
ARTIFACT_NAME = "n3w-kf098-manager-exact-source-575ce642"
IMAGE_TAR_SHA256 = "6392b8c9bb87d95404346583d6f44967bd4e20fcc092be393c45f75a4ca7a5b2"
SOURCE_SHA = "575ce642e372961e21de14a36eba5877082de3cf"
IMAGE_ID = "sha256:49c9fcc0a17d47678b0667c48a06f9a9475609a757e510ca148983b53ed537e3"
EXPECTED_MANAGER_ENV_SHA256 = "f454c6e886ee286192a3c3683a87c33d98e79428de0a6d0c9d2a6e0a19a9d6a6"
STALE_SHADOW_OLD_OVERLAY_SHA256 = "aeab3dafd4edceca69bd3e17964d7fc670c7ef50ee079d80e984f8dd2cabeff8"
PLACEHOLDERS = (
    "placeholder",
    "example",
    "t1_ssh_target",
    "<",
    ">",
)


class StopExecution(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_target(target: str) -> None:
    if (
        not target
        or target.strip() != target
        or any(character.isspace() for character in target)
    ):
        raise StopExecution("T1 SSH target is empty or contains whitespace")
    folded = target.casefold()
    if any(marker.casefold() in folded for marker in PLACEHOLDERS):
        raise StopExecution("T1 SSH target looks like a placeholder")
    try:
        target.encode("ascii")
    except UnicodeEncodeError as exc:
        raise StopExecution("T1 SSH target must be ASCII") from exc


def validate_evidence_root(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise StopExecution("evidence root is not a directory")
        if any(path.iterdir()):
            raise StopExecution("evidence root exists and is non-empty")
        if path.stat().st_mode & 0o777 != 0o700:
            raise StopExecution("evidence root mode must be 0700")
    else:
        path.mkdir(parents=True, mode=0o700)
    if path.stat().st_mode & 0o777 != 0o700:
        raise StopExecution("evidence root mode must be 0700")


def write_private_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")
    os.chmod(path, 0o600)


def write_private_bytes(path: Path, value: bytes) -> None:
    path.write_bytes(value)
    os.chmod(path, 0o600)


def record(
    root: Path,
    index: int,
    name: str,
    argv: list[str],
    *,
    timeout: int = 180,
) -> subprocess.CompletedProcess[bytes]:
    directory = root / f"op_{index:02d}_{name}"
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    write_private_text(
        directory / "command.json",
        json.dumps({"argv": argv}, indent=2, sort_keys=True) + "\n",
    )
    try:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        if isinstance(stdout, str):
            stdout = stdout.encode()
        if isinstance(stderr, str):
            stderr = stderr.encode()
        write_private_bytes(directory / "stdout.bin", stdout)
        write_private_bytes(directory / "stderr.bin", stderr)
        write_private_text(
            directory / "result.json",
            json.dumps(
                {
                    "returncode": None,
                    "timed_out": True,
                    "timeout_seconds": timeout,
                    "stdout_bytes": len(stdout),
                    "stderr_bytes": len(stderr),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        raise StopExecution(
            f"{name} timed out after {timeout} seconds"
        ) from exc
    write_private_bytes(directory / "stdout.bin", completed.stdout)
    write_private_bytes(directory / "stderr.bin", completed.stderr)
    write_private_text(
        directory / "result.json",
        json.dumps(
            {
                "returncode": completed.returncode,
                "timed_out": False,
                "timeout_seconds": timeout,
                "stdout_bytes": len(completed.stdout),
                "stderr_bytes": len(completed.stderr),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return completed


def require_ok(
    completed: subprocess.CompletedProcess[bytes],
    message: str,
) -> str:
    if completed.returncode:
        stderr = completed.stderr.decode("utf-8", errors="backslashreplace")
        stdout = completed.stdout.decode("utf-8", errors="backslashreplace")
        detail = stderr.strip() or stdout.strip()
        raise StopExecution(f"{message}: {detail[:800]}")
    return completed.stdout.decode("utf-8", errors="strict")


def ssh_argv(target: str, command: str) -> list[str]:
    return [
        "ssh",
        "-n",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=2",
        target,
        command,
    ]


def scp_argv(source: Path, target: str, destination: str) -> list[str]:
    return [
        "scp",
        "-B",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        str(source),
        f"{target}:{destination}",
    ]


def verify_local_artifact(artifact_dir: Path) -> dict[str, Any]:
    image = artifact_dir / "greenhouse-manager-arm64.tar"
    manifest = artifact_dir / "manifest.json"
    manifest_sha = artifact_dir / "manifest.sha256"
    if not image.is_file() or not manifest.is_file() or not manifest_sha.is_file():
        raise StopExecution("exact artifact directory is incomplete")
    if sha256_file(image) != IMAGE_TAR_SHA256:
        raise StopExecution("exact Manager image tar SHA256 mismatch")
    expected_manifest_line = f"{sha256_file(manifest)}  manifest.json"
    if manifest_sha.read_text(encoding="utf-8").strip() != expected_manifest_line:
        raise StopExecution("portable manifest checksum mismatch")
    document = json.loads(manifest.read_text(encoding="utf-8"))
    source = document.get("source")
    image_binding = document.get("image")
    if not isinstance(source, dict) or not isinstance(image_binding, dict):
        raise StopExecution("manifest source/image binding missing")
    if source.get("commit") != SOURCE_SHA:
        raise StopExecution("manifest source SHA mismatch")
    if image_binding.get("id") != IMAGE_ID:
        raise StopExecution("manifest image ID mismatch")
    if image_binding.get("architecture") != "arm64":
        raise StopExecution("manifest image architecture mismatch")
    if not REMOTE_EXECUTOR.is_file():
        raise StopExecution("remote executor is missing")
    return {
        "artifact_id": ARTIFACT_ID,
        "run_id": ARTIFACT_RUN_ID,
        "artifact_name": ARTIFACT_NAME,
        "image_tar_sha256": IMAGE_TAR_SHA256,
        "remote_executor_sha256": sha256_file(REMOTE_EXECUTOR),
    }


def target_preflight(
    root: Path,
    index: int,
    target: str,
) -> int:
    probe = """
import json
import os
import platform
import subprocess

root_ok = os.geteuid() == 0
host_arch = platform.machine()
docker_arch = ""
docker_probe = "not_run"

try:
    result = subprocess.run(
        ["docker", "info", "--format", "{{.Architecture}}"],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )
    docker_arch = result.stdout.strip()
    docker_probe = (
        "ok"
        if result.returncode == 0
        else "failed"
    )
except subprocess.TimeoutExpired:
    docker_probe = "timeout"

arch_ok = (
    host_arch in {"aarch64", "arm64"}
    and docker_arch in {"aarch64", "arm64"}
)
ok = root_ok and docker_probe == "ok" and arch_ok

print(
    json.dumps(
        {
            "root": root_ok,
            "host_arch": host_arch,
            "docker_arch": docker_arch,
            "docker_probe": docker_probe,
            "pass": ok,
        },
        sort_keys=True,
    )
)
raise SystemExit(0 if ok else 2)
""".strip()
    require_ok(
        record(
            root,
            index,
            "target_preflight",
            ssh_argv(
                target,
                "python3 -c " + shlex.quote(probe),
            ),
            timeout=30,
        ),
        "T1 host/architecture preflight failed",
    )
    return index + 1


def stage(
    root: Path,
    index: int,
    target: str,
    artifact_dir: Path,
) -> int:
    remote_sha = sha256_file(REMOTE_EXECUTOR)
    classifier_script = """
from pathlib import Path
import hashlib
import os

r = Path("__STAGE_ROOT__")
base = {
    "greenhouse-manager-arm64.tar",
    "manifest.json",
    "manifest.sha256",
    "remote_cutover.py",
}
forbidden = {
    "manager-kf098-overlay.yml",
    "manager-kf098-rollback-overlay.yml",
    "manager-kf098-shadow-new-overlay.yml",
}
known_residual = "manager-kf098-shadow-old-overlay.yml"
if not r.exists():
    print("STAGE_CLASS=ABSENT")
    raise SystemExit(0)

existing = {p.name for p in r.iterdir()}
if existing & forbidden:
    print("STAGE_CLASS=UNKNOWN_NONEMPTY")
    raise SystemExit(2)

if known_residual in existing:
    residual = r / known_residual
    if (
        not residual.is_file()
        or hashlib.sha256(residual.read_bytes()).hexdigest()
        != "__STALE_SHADOW_OLD_SHA__"
    ):
        print("STAGE_CLASS=UNKNOWN_NONEMPTY")
        raise SystemExit(2)

extra = existing - base - {"rollback", known_residual}
if extra:
    print("STAGE_CLASS=UNKNOWN_NONEMPTY")
    raise SystemExit(2)

rb = r / "rollback"
if not rb.exists():
    print("STAGE_CLASS=REUSABLE_OR_EMPTY")
    raise SystemExit(0)

if not rb.is_dir():
    print("STAGE_CLASS=UNKNOWN_NONEMPTY")
    raise SystemExit(2)
st = rb.stat()
if (st.st_mode & 0o777) != 0o700 or st.st_uid != 0:
    print("STAGE_CLASS=UNKNOWN_NONEMPTY")
    raise SystemExit(2)
children = {p.name for p in rb.iterdir()}
if children != {"manager.env.before", "manager-prestate.json"}:
    print("STAGE_CLASS=UNKNOWN_NONEMPTY")
    raise SystemExit(2)
backup = rb / "manager.env.before"
prestate = rb / "manager-prestate.json"
if not backup.is_file() or not prestate.is_file():
    print("STAGE_CLASS=UNKNOWN_NONEMPTY")
    raise SystemExit(2)
digest = hashlib.sha256(backup.read_bytes()).hexdigest()
if digest != "__MANAGER_ENV_SHA__":
    print("STAGE_CLASS=UNKNOWN_NONEMPTY")
    raise SystemExit(2)
print("STAGE_CLASS=REUSABLE_PRETRANSACTION_SNAPSHOT")
raise SystemExit(0)
""".strip()
    classifier_script = classifier_script.replace(
        "__STAGE_ROOT__",
        STAGE_ROOT,
    ).replace(
        "__MANAGER_ENV_SHA__",
        EXPECTED_MANAGER_ENV_SHA256,
    ).replace(
        "__STALE_SHADOW_OLD_SHA__",
        STALE_SHADOW_OLD_OVERLAY_SHA256,
    )
    classifier = (
        "python3 -c "
        + shlex.quote(classifier_script)
    )
    require_ok(
        record(
            root,
            index,
            "stage_classifier",
            ssh_argv(target, classifier),
        ),
        "remote stage root is not reusable",
    )
    index += 1

    prepare = (
        f"install -d -m 0700 {shlex.quote(STAGE_ROOT)} "
        f"{shlex.quote(STAGE_ROOT + '/.incoming')} && "
        f"chmod 0700 {shlex.quote(STAGE_ROOT)} "
        f"{shlex.quote(STAGE_ROOT + '/.incoming')}"
    )
    require_ok(
        record(
            root,
            index,
            "stage_prepare",
            ssh_argv(target, prepare),
        ),
        "cannot prepare durable T1 staging root",
    )
    index += 1

    files = [
        artifact_dir / "greenhouse-manager-arm64.tar",
        artifact_dir / "manifest.json",
        artifact_dir / "manifest.sha256",
        REMOTE_EXECUTOR,
    ]
    for file in files:
        require_ok(
            record(
                root,
                index,
                f"stage_copy_{file.name.replace('.', '_')}",
                scp_argv(
                    file,
                    target,
                    STAGE_ROOT + "/.incoming/" + file.name,
                ),
            ),
            f"cannot stage {file.name}",
        )
        index += 1

    promote_script = (
        "from pathlib import Path;"
        "import hashlib,os;"
        f"r=Path('{STAGE_ROOT}');i=r/'.incoming';"
        f"expected={{'greenhouse-manager-arm64.tar':'{IMAGE_TAR_SHA256}',"
        f"'remote_cutover.py':'{remote_sha}'}};"
        "h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();"
        "assert all((i/n).is_file() and h(i/n)==v for n,v in expected.items());"
        "assert (i/'manifest.json').is_file() and (i/'manifest.sha256').is_file();"
        "line=(i/'manifest.sha256').read_text().strip();"
        "assert line==h(i/'manifest.json')+'  manifest.json';"
        "[os.replace(i/n,r/n) for n in ['greenhouse-manager-arm64.tar','manifest.json','manifest.sha256','remote_cutover.py']];"
        "os.chmod(r/'remote_cutover.py',0o700);"
        "i.rmdir();"
        "print('STAGE_PROMOTE=PASS')"
    )
    require_ok(
        record(
            root,
            index,
            "stage_promote",
            ssh_argv(
                target,
                "python3 -c " + shlex.quote(promote_script),
            ),
        ),
        "remote stage promotion failed",
    )
    return index + 1


def remote_phase(
    root: Path,
    index: int,
    target: str,
    phase: str,
) -> tuple[int, dict[str, Any]]:
    command = (
        "python3 "
        + shlex.quote(STAGE_ROOT + "/remote_cutover.py")
        + " "
        + shlex.quote(phase)
    )
    phase_timeout = {
        "preflight": 180,
        "apply": 900,
        "rollback": 600,
    }.get(phase)
    if phase_timeout is None:
        raise StopExecution(
            f"unsupported remote phase timeout contract: {phase}"
        )
    raw = require_ok(
        record(
            root,
            index,
            f"remote_{phase}",
            ssh_argv(target, command),
            timeout=phase_timeout,
        ),
        f"remote {phase} failed",
    )
    try:
        result = json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        raise StopExecution(
            f"remote {phase} returned invalid JSON"
        ) from exc
    if not isinstance(result, dict):
        raise StopExecution(f"remote {phase} result is not an object")
    if result.get("result") not in {"PASS", "FAIL_ROLLED_BACK"}:
        raise StopExecution(
            f"remote {phase} stopped: {json.dumps(result, sort_keys=True)[:1200]}"
        )
    return index + 1, result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        required=True,
        choices=(
            "local-preflight",
            "stage",
            "remote-preflight",
            "apply",
            "rollback",
        ),
    )
    parser.add_argument("--t1-ssh-target")
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()

    try:
        validate_evidence_root(args.evidence_root)
        closure: dict[str, Any] = {
            "phase": args.phase,
            "result": "STOP",
            "artifact_id": ARTIFACT_ID,
            "source_sha": SOURCE_SHA,
            "image_id": IMAGE_ID,
            "t1_runtime_mutation": False,
        }
        index = 1

        if args.artifact_dir is None:
            raise StopExecution("--artifact-dir is required")
        local = verify_local_artifact(args.artifact_dir)
        closure["local_artifact"] = local

        if args.phase == "local-preflight":
            closure["result"] = "PASS"
        else:
            if args.t1_ssh_target is None:
                raise StopExecution("--t1-ssh-target is required")
            validate_target(args.t1_ssh_target)
            index = target_preflight(
                args.evidence_root,
                index,
                args.t1_ssh_target,
            )

            if args.phase == "stage":
                index = stage(
                    args.evidence_root,
                    index,
                    args.t1_ssh_target,
                    args.artifact_dir,
                )
                closure["result"] = "PASS"
                closure["t1_file_staging"] = True
            else:
                if args.phase in {"remote-preflight", "apply", "rollback"}:
                    index, remote = remote_phase(
                        args.evidence_root,
                        index,
                        args.t1_ssh_target,
                        {
                            "remote-preflight": "preflight",
                            "apply": "apply",
                            "rollback": "rollback",
                        }[args.phase],
                    )
                    closure["remote"] = remote
                    closure["result"] = remote.get("result")
                    closure["t1_runtime_mutation"] = args.phase in {
                        "apply",
                        "rollback",
                    }

        write_private_text(
            args.evidence_root / "closure.json",
            json.dumps(closure, indent=2, sort_keys=True) + "\n",
        )
        print(json.dumps(closure, sort_keys=True))
        return 0 if closure["result"] in {"PASS", "FAIL_ROLLED_BACK"} else 2
    except StopExecution as exc:
        failure = {
            "phase": args.phase,
            "result": "STOP",
            "reason": str(exc)[:1600],
            "artifact_id": ARTIFACT_ID,
            "source_sha": SOURCE_SHA,
            "image_id": IMAGE_ID,
        }
        if args.evidence_root.exists():
            write_private_text(
                args.evidence_root / "closure.json",
                json.dumps(failure, indent=2, sort_keys=True) + "\n",
            )
        print(json.dumps(failure, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
