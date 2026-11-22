#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[4]
TOOLS_ROOT = REPO_ROOT / "tools"
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

import contract
from n3w_t1_portable_image_identity import parse_verified_load_archive
from n3w_t1_ssh_transport import SSHTransport


REPOSITORY = "chrenguo-stack/HomeAssistant"
RECOVERY_ARTIFACT_ID = 14755286389
RECOVERY_ZIP_SIZE = 97749
RECOVERY_ZIP_SHA256 = "3e8d9be4100392403aef5af15c9782fe866db77be159dbe5c53814eda486c15e"
RECOVERY_MANIFEST_SHA256 = "f3dd26c2074c721e45d37f134cf9f90a1e269370b11eaf992e1f892b9053cd6"
RECOVERY_PACKAGE_SHA256 = "823a4522a34aae926913e8980fb9442af457084ff4243c74419ccdd66ff6a4e7"
RECOVERY_SOURCE_HEAD = "eac5794afbeef265dee0f5f60d5e5223de111e35"
DEFAULT_CACHE = (
    Path.home()
    / "Documents/N3W/t1-core-stack-cache"
    / "24382caae4a1f5d459297f86e8d18f10a848ca64"
    / "homeassistant-arm64.tar"
)
COMPATIBILITY = (
    REPO_ROOT
    / "infra/n3w-t1/upgrades/homeassistant-2026.10.4-compatibility-review.json"
)
TARGET = REPO_ROOT / "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json"
STORAGE_POLICY = REPO_ROOT / "infra/n3w-t1/upgrades/homeassistant-2026.10.4-storage-policy.json"


class OperatorError(RuntimeError):
    pass


def run(
    argv: list[str],
    *,
    timeout: int = 120,
    check: bool = True,
    input_text: str | None = None,
    input_file=None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    kwargs: dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "timeout": timeout,
        "check": False,
        "env": env,
    }
    if input_text is not None:
        kwargs["input"] = input_text
        kwargs["text"] = True
    elif input_file is not None:
        kwargs["stdin"] = input_file
    result = subprocess.run(argv, **kwargs)
    if check and result.returncode:
        stderr = result.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        raise OperatorError(
            "command_failed:" + Path(argv[0]).name + ":" + str(result.returncode)
            + (":" + stderr.strip()[:200] if stderr else "")
        )
    return result


def git_text(*args: str) -> str:
    return run(
        ["git", "-C", str(REPO_ROOT), *args],
        timeout=30,
    ).stdout.decode().strip()


def validate_source(expected_head: str) -> dict[str, Any]:
    if git_text("rev-parse", "HEAD") != expected_head:
        raise OperatorError("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise OperatorError("tracked_worktree_dirty")

    review = json.loads(COMPATIBILITY.read_text(encoding="utf-8"))
    target = json.loads(TARGET.read_text(encoding="utf-8"))
    if contract.sha256_bytes(contract.canonical(review)) != contract.COMPATIBILITY_REVIEW_SHA256:
        raise OperatorError("compatibility_review_sha256_drift")
    contract.validate_compatibility_authority(review, target)
    policy = json.loads(STORAGE_POLICY.read_text(encoding="utf-8"))
    admission = policy.get("p5_upgrade_admission")
    if (
        policy.get("schema")
        != "gh.n3w-t1-core-updater-homeassistant-storage-policy/1"
        or policy.get("component") != "homeassistant"
        or not isinstance(admission, dict)
        or admission.get("historical_fixed_5_gib_retired") is not True
        or admission.get("derived_post_peak_reserve_bytes")
        != contract.POST_PEAK_RESERVE_BYTES
    ):
        raise OperatorError("storage_policy_authority_invalid")
    return {
        "source_head": expected_head,
        "compatibility_review_sha256": contract.COMPATIBILITY_REVIEW_SHA256,
        "persistent_schema_compatible": True,
        "rollback_compatible": True,
        "post_peak_reserve_bytes": contract.POST_PEAK_RESERVE_BYTES,
    }


def validate_cache(path: Path) -> dict[str, Any]:
    contract.validate_predecessor_cache(path)
    unpacked: list[int] = []
    with path.open("rb") as stream:
        identity = parse_verified_load_archive(
            stream,
            archive_sha256=contract.PREDECESSOR_ARCHIVE_SHA256,
            archive_size_bytes=contract.PREDECESSOR_ARCHIVE_SIZE,
            expected_tag=contract.PREDECESSOR_IMAGE,
            unpacked_sizes=unpacked,
        )
    if (
        (identity.os, identity.architecture) != ("linux", "arm64")
        or identity.config_digest != contract.PREDECESSOR_IMAGE_ID
    ):
        raise OperatorError("predecessor_cache_portable_identity_drift")
    import_bytes = contract.import_worst_case_bytes(unpacked)
    return {
        "path": str(path),
        "archive_size_bytes": contract.PREDECESSOR_ARCHIVE_SIZE,
        "archive_sha256": contract.PREDECESSOR_ARCHIVE_SHA256,
        "image_ref": contract.PREDECESSOR_IMAGE,
        "image_id": contract.PREDECESSOR_IMAGE_ID,
        "platform": "linux/arm64",
        "import_worst_case_bytes": import_bytes,
        "post_peak_reserve_bytes": contract.POST_PEAK_RESERVE_BYTES,
        "post_release_required_bytes": (
            import_bytes + contract.POST_PEAK_RESERVE_BYTES
        ),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def recovery_package(temp_root: Path) -> Path:
    archive = temp_root / "recovery.zip"
    downloaded = False
    for _ in range(3):
        result = run(
            [
                "gh",
                "api",
                "--method",
                "GET",
                f"/repos/{REPOSITORY}/actions/artifacts/{RECOVERY_ARTIFACT_ID}/zip",
            ],
            timeout=90,
            check=False,
        )
        if result.returncode == 0:
            archive.write_bytes(result.stdout)
            downloaded = True
            break
    if not downloaded:
        raise OperatorError("recovery_artifact_download_failed")
    if (
        archive.stat().st_size != RECOVERY_ZIP_SIZE
        or _sha256_file(archive) != RECOVERY_ZIP_SHA256
    ):
        raise OperatorError("recovery_artifact_zip_identity_drift")

    directory = temp_root / "recovery"
    directory.mkdir()
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if (
            not names
            or any(
                not name
                or name.startswith("/")
                or ".." in Path(name).parts
                for name in names
            )
        ):
            raise OperatorError("recovery_artifact_zip_layout_invalid")
        bundle.extractall(directory)

    manifest = directory / "manifest.json"
    package = directory / "ha-recovery.pyz"
    if (
        _sha256_file(manifest) != RECOVERY_MANIFEST_SHA256
        or _sha256_file(package) != RECOVERY_PACKAGE_SHA256
    ):
        raise OperatorError("recovery_artifact_package_identity_drift")
    document = json.loads(manifest.read_text(encoding="utf-8"))
    if document.get("source_head") != RECOVERY_SOURCE_HEAD:
        raise OperatorError("recovery_artifact_source_drift")
    files = document.get("files")
    if not isinstance(files, dict):
        raise OperatorError("recovery_artifact_manifest_invalid")
    for name, expected in files.items():
        path = directory / name
        if (
            not isinstance(expected, str)
            or not path.is_file()
            or _sha256_file(path) != expected
        ):
            raise OperatorError("recovery_artifact_file_drift")
    return package


def _encoded_source(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def readonly_bootstrap(
    *,
    recovery_pyz: Path,
    mode: str,
    source_head: str,
) -> str:
    if mode not in {"preflight", "status"}:
        raise OperatorError("readonly_mode_invalid")
    sources = {
        name: _encoded_source(PACKAGE_DIR / name)
        for name in ("contract.py", "executor.py", "remote_live.py")
    }
    recovery = base64.b64encode(recovery_pyz.read_bytes()).decode("ascii")
    return f"""
import base64
import os
import sys
import types

def load_module(name, encoded):
    module = types.ModuleType(name)
    module.__file__ = "<memory:" + name + ">"
    sys.modules[name] = module
    exec(compile(base64.b64decode(encoded), module.__file__, "exec"), module.__dict__)
    return module

load_module("contract", {sources["contract.py"]!r})
load_module("executor", {sources["executor.py"]!r})
fd = os.memfd_create("n3w-r8-recovery")
with os.fdopen(os.dup(fd), "wb") as stream:
    stream.write(base64.b64decode({recovery!r}))
recovery_path = "/proc/self/fd/" + str(fd)
sys.argv = [
    "remote_live.py",
    "--mode", {mode!r},
    "--recovery-pyz", recovery_path,
    "--source-head", {source_head!r},
]
namespace = {{"__name__": "__main__", "__file__": "<memory:remote_live>"}}
exec(compile(base64.b64decode({sources["remote_live.py"]!r}), namespace["__file__"], "exec"), namespace)
"""


def ssh_epoch(
    *,
    target: str,
    known_hosts: Path,
    expected_host_key_sha256: str,
):
    transport = SSHTransport(
        target=target,
        known_hosts=known_hosts,
        expected_host_key_sha256=expected_host_key_sha256,
    )
    result = transport.start_epoch()
    print(
        "SSH_HOST_KEY_BINDING=PASS "
        f"EPOCH={result['epoch']} "
        f"HOST_KEY_SHA256={result['host_key_sha256']}"
    )
    return transport


def run_readonly(
    *,
    mode: str,
    target: str,
    known_hosts: Path,
    expected_host_key_sha256: str,
    recovery_pyz: Path,
    source_head: str,
) -> dict[str, Any]:
    transport = ssh_epoch(
        target=target,
        known_hosts=known_hosts,
        expected_host_key_sha256=expected_host_key_sha256,
    )
    try:
        env = transport.managed_environment()
        payload = readonly_bootstrap(
            recovery_pyz=recovery_pyz,
            mode=mode,
            source_head=source_head,
        )
        command = (
            'if [ "$(id -u)" -eq 0 ]; then '
            'exec /usr/bin/unshare --mount --propagation private --fork '
            '/usr/bin/python3 -I -B -; '
            'else exec sudo -n /usr/bin/unshare --mount --propagation private --fork '
            '/usr/bin/python3 -I -B -; fi'
        )
        result = run(
            [
                "ssh",
                "-o",
                "StrictHostKeyChecking=yes",
                "-o",
                "ForwardAgent=no",
                "-o",
                "ClearAllForwardings=yes",
                "-o",
                "RequestTTY=no",
                "--",
                target,
                command,
            ],
            timeout=1800,
            check=False,
            input_text=payload,
            env=env,
        )
        stdout = result.stdout if isinstance(result.stdout, str) else result.stdout.decode()
        stderr = result.stderr if isinstance(result.stderr, str) else result.stderr.decode()
        if stderr:
            print(stderr, file=sys.stderr, end="")
        if result.returncode:
            raise OperatorError("readonly_remote_failed:" + str(result.returncode))
        rows = [
            json.loads(line)
            for line in stdout.splitlines()
            if line.strip().startswith("{")
        ]
        if len(rows) != 1 or not isinstance(rows[0], dict):
            raise OperatorError("readonly_remote_report_invalid")
        return rows[0]
    finally:
        transport.close_epoch()


def load_grant(path: Path, *, source_head: str, cache: dict[str, Any]) -> contract.SwitchGrant:
    if path.is_symlink() or not path.is_file():
        raise OperatorError("grant_file_invalid")
    info = path.stat()
    if (
        info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_size <= 0
        or info.st_size > 16 * 1024
    ):
        raise OperatorError("grant_file_metadata_invalid")
    grant = contract.SwitchGrant.from_document(
        json.loads(path.read_text(encoding="utf-8"))
    )
    if (
        grant.source_head != source_head
        or grant.predecessor_import_worst_case_bytes
        != cache["import_worst_case_bytes"]
    ):
        raise OperatorError("grant_local_binding_drift")
    return grant


def stage_execute_bundle(
    *,
    transport: SSHTransport,
    target: str,
    remote_dir: str,
    recovery_pyz: Path,
    grant_path: Path,
) -> None:
    env = transport.managed_environment()
    run(
        [
            "ssh",
            "--",
            target,
            "umask 077 && mkdir --mode=700 -- " + remote_dir,
        ],
        env=env,
        timeout=30,
    )
    sources = (
        (PACKAGE_DIR / "contract.py", "contract.py"),
        (PACKAGE_DIR / "executor.py", "executor.py"),
        (PACKAGE_DIR / "remote_live.py", "remote_live.py"),
        (recovery_pyz, "ha-recovery.pyz"),
        (grant_path, "grant.json"),
    )
    for source, remote_name in sources:
        run(
            [
                "scp",
                str(source),
                target + ":" + remote_dir + "/" + remote_name,
            ],
            env=env,
            timeout=120,
        )
    run(
        [
            "ssh",
            "--",
            target,
            "chmod 600 -- "
            + " ".join(
                remote_dir + "/" + name
                for name in (
                    "contract.py",
                    "executor.py",
                    "remote_live.py",
                    "ha-recovery.pyz",
                    "grant.json",
                )
            ),
        ],
        env=env,
        timeout=30,
    )


def execute_live(
    *,
    target: str,
    known_hosts: Path,
    expected_host_key_sha256: str,
    recovery_pyz: Path,
    source_head: str,
    grant_path: Path,
    cache_path: Path,
    grant: contract.SwitchGrant,
) -> dict[str, Any]:
    transport = ssh_epoch(
        target=target,
        known_hosts=known_hosts,
        expected_host_key_sha256=expected_host_key_sha256,
    )
    remote_dir = "/tmp/n3w-r8-predecessor-switch-" + contract.transaction_id(grant)[:16]
    env = None
    result_report: dict[str, Any] | None = None
    try:
        env = transport.managed_environment()
        stage_execute_bundle(
            transport=transport,
            target=target,
            remote_dir=remote_dir,
            recovery_pyz=recovery_pyz,
            grant_path=grant_path,
        )
        command = (
            "/usr/bin/unshare --mount --propagation private --fork "
            "/usr/bin/python3 -I -B "
            + remote_dir
            + "/remote_live.py --mode execute --recovery-pyz "
            + remote_dir
            + "/"
            + "ha-recovery.pyz"
            + " --source-head "
            + source_head
            + " --grant "
            + remote_dir
            + "/"
            + "grant.json"
        )
        with cache_path.open("rb") as source:
            result = run(
                [
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=yes",
                    "-o",
                    "ForwardAgent=no",
                    "-o",
                    "ClearAllForwardings=yes",
                    "-o",
                    "RequestTTY=no",
                    "--",
                    target,
                    command,
                ],
                timeout=7200,
                check=False,
                input_file=source,
                env=env,
            )
        stdout = result.stdout.decode()
        stderr = result.stderr.decode()
        if stderr:
            print(stderr, file=sys.stderr, end="")
        rows = [
            json.loads(line)
            for line in stdout.splitlines()
            if line.strip().startswith("{")
        ]
        if len(rows) == 1 and isinstance(rows[0], dict):
            result_report = rows[0]
        if result.returncode not in {0, 2, 3} or result_report is None:
            raise OperatorError("live_remote_report_invalid")
        return result_report
    finally:
        if env is not None and (
            result_report is None
            or result_report.get("status")
            != "PREDECESSOR_SWITCH_RECOVERY_REQUIRED"
        ):
            run(
                [
                    "ssh",
                    "--",
                    target,
                    "rm -rf -- " + remote_dir,
                ],
                env=env,
                timeout=60,
                check=False,
            )
        transport.close_epoch()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("source-check", "preflight", "status", "execute"),
        required=True,
    )
    parser.add_argument("--expected-source-head", required=True)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--target")
    parser.add_argument("--known-hosts", type=Path)
    parser.add_argument(
        "--expected-host-key-sha256",
        default=contract.EXPECTED_HOST_KEY_SHA256,
    )
    parser.add_argument("--grant", type=Path)
    args = parser.parse_args()

    source = validate_source(args.expected_source_head)
    cache = validate_cache(args.cache)
    report: dict[str, Any] = {
        "source": source,
        "predecessor_cache": cache,
        "live_write_authorization": "NONE" if args.grant is None else "PRESENT_UNCLAIMED",
    }
    if args.mode == "source-check":
        report["status"] = "R8_PREDECESSOR_SWITCH_SOURCE_CHECK_PASS"
        print(json.dumps(report, sort_keys=True))
        return 0

    if not args.target or args.known_hosts is None:
        parser.error("--target and --known-hosts are required for this mode")

    with tempfile.TemporaryDirectory(prefix="n3w-r8-pred-switch-") as raw:
        recovery = recovery_package(Path(raw))
        if args.mode in {"preflight", "status"}:
            observed = run_readonly(
                mode=args.mode,
                target=args.target,
                known_hosts=args.known_hosts,
                expected_host_key_sha256=args.expected_host_key_sha256,
                recovery_pyz=recovery,
                source_head=args.expected_source_head,
            )
            report["remote"] = observed
            report["status"] = (
                "R8_PREDECESSOR_SWITCH_PREFLIGHT_PASS"
                if args.mode == "preflight"
                else "R8_PREDECESSOR_SWITCH_STATUS_OBSERVED"
            )
            print(json.dumps(report, sort_keys=True))
            return 0

        if args.grant is None:
            parser.error("--grant is required for execute")
        grant = load_grant(
            args.grant,
            source_head=args.expected_source_head,
            cache=cache,
        )
        report["remote"] = execute_live(
            target=args.target,
            known_hosts=args.known_hosts,
            expected_host_key_sha256=args.expected_host_key_sha256,
            recovery_pyz=recovery,
            source_head=args.expected_source_head,
            grant_path=args.grant,
            cache_path=args.cache,
            grant=grant,
        )
        report["status"] = report["remote"]["status"]
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] == "PREDECESSOR_SWITCH_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
