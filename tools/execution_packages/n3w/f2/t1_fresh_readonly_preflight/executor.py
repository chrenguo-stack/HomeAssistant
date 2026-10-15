#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[5]
IDENTITY_RELATIVE = "tools/n3w_t1_os_identity_readonly_probe.py"
INVENTORY_RELATIVE = "tools/n3w_t1_minimal_baseline_readonly_inventory.py"
STAGING_RELATIVE = "tools/n3w_t1_fresh_product_staging_host.py"
BASELINE_RELATIVE = "tools/n3w_t1_fresh_host_baseline.py"
EXPECTED_BLOBS = {
    IDENTITY_RELATIVE: "26a2f47c9c83fef5637f551ea75ba6b5d5ba3866",
    INVENTORY_RELATIVE: "073bbc936cef3648411a95023a59d6b7e04d4a32",
    STAGING_RELATIVE: "e924f02265564666efab89986479d1b5af40123d",
    BASELINE_RELATIVE: "d6f72a7a595f7ba5b8d9d2e5dc06188dbfa973b2",
}
SCHEMA = "gh.n3w-t1-f2-fresh-readonly-preflight-execution/1"
CONFIRMATION = "READONLY FRESH T1 PREFLIGHT: YES"
REMOTE_IDENTITY_COMMAND = "sudo -n python3 -B - --root /"
EXPECTED_OS = {
    "ID": "ubuntu",
    "VERSION_ID": "26.04",
    "VERSION_CODENAME": "resolute",
    "PRETTY_NAME": "Armbian OS 26.05.0 resolute",
}
EXPECTED_ARMBIAN = {
    "BOARD": "S912-Phicomm-T1",
    "BOARD_NAME": "Aml.S912",
    "VERSION": "26.05.0",
    "BRANCH": "current",
    "ARCH": "arm64",
    "IMAGE_TYPE": "rebuild",
}
DEFAULT_NETWORKS = frozenset(("bridge", "host", "none"))
RESIDUE_PATHS = (
    "/var/lib/n3w-fresh-bootstrap-authorizations",
    "/var/lib/n3w-t1-provisioning",
    "/var/tmp/n3w-t1-provisioning-candidate",
    "/usr/local/sbin/n3w-t1-provision",
    "/usr/local/sbin/n3w-t1-systemd-staged-install",
    "/usr/local/sbin/n3w-t1-production-activation-enable",
    "/etc/systemd/system/n3wfc4-provision-resume.service",
)
ENGINE_RESIDUE_PATHS = ("/var/lib/docker", "/var/lib/containerd")

SUPPLEMENT_SCRIPT = r"""
import hashlib,json,os,socket,subprocess
from pathlib import Path

def run(argv):
    try:
        p=subprocess.run(argv,capture_output=True,text=True,check=False,timeout=20)
        return {"rc":p.returncode,"out":p.stdout.strip(),"err":p.stderr.strip()[:120]}
    except Exception as e:
        return {"rc":127,"out":"","err":type(e).__name__}

def service(name):
    a=run(["systemctl","is-active",name])
    l=run(["systemctl","show","-p","LoadState","--value",name])
    r=run(["systemctl","show","-p","Result","--value",name])
    s=run(["systemctl","show","-p","ExecMainStatus","--value",name])
    t=run(["systemctl","show","-p","ExecMainStartTimestampMonotonic","--value",name])
    u=run(["systemctl","show","-p","UnitFileState","--value",name])
    return {
      "active":a["out"] or "rc="+str(a["rc"]),
      "load_state":l["out"] or "rc="+str(l["rc"]),
      "result":r["out"] if r["rc"]==0 else None,
      "exec_main_status":s["out"] if s["rc"]==0 else None,
      "exec_main_start_timestamp_monotonic":t["out"] if t["rc"]==0 else None,
      "unit_file_state":u["out"] if u["rc"]==0 else None,
    }

def candidate(name):
    p=run(["apt-cache","policy",name])
    if p["rc"]!=0:return None
    for line in p["out"].splitlines():
        line=line.strip()
        if line.startswith("Candidate:"):
            value=line.split(":",1)[1].strip()
            return value if value and value!="(none)" else None
    return None

def apt_source_summary():
    paths=[Path("/etc/apt/sources.list")]
    root=Path("/etc/apt/sources.list.d")
    if root.is_dir():
        paths.extend(sorted(p for p in root.iterdir() if p.is_file()))
    lines=[]
    for path in paths:
        try:
            text=path.read_text(encoding="utf-8",errors="ignore")
        except OSError:
            continue
        for raw in text.splitlines():
            line=raw.split("#",1)[0].strip()
            if line:
                lines.append(line)
    joined="\n".join(lines).casefold()
    return {
      "ubuntu_ports": "ports.ubuntu.com" in joined,
      "resolute": "resolute" in joined,
      "universe": "universe" in joined,
    }

def apt_lists_file_count():
    root=Path("/var/lib/apt/lists")
    if not root.is_dir():
        return 0
    try:
        return sum(1 for path in root.iterdir() if path.is_file())
    except OSError:
        return -1

def present(path):
    return Path(path).exists() or Path(path).is_symlink()

names=sorted(p.name for p in Path("/var/tmp").glob("n3w-fresh-bootstrap*"))
try:
    dns=bool(socket.getaddrinfo("github.com",443,type=socket.SOCK_STREAM))
except OSError:
    dns=False
report={
  "schema":"gh.n3w-t1-f2-fresh-readonly-supplement/1",
  "status":"PASS",
  "architecture":os.uname().machine,
  "ssh":service("ssh"),
  "networkmanager":service("NetworkManager"),
  "armbian_firstrun":service("armbian-firstrun.service"),
  "default_route_present":bool(run(["ip","-4","route","show","default"])["out"]),
  "dns_resolution_present":dns,
  "ntp_synchronized":run(["timedatectl","show","-p","NTPSynchronized","--value"])["out"],
  "package_candidates":{"docker.io":candidate("docker.io"),"docker-compose-v2":candidate("docker-compose-v2")},
  "apt":{"lists_file_count":apt_lists_file_count(),"source":apt_source_summary()},
  "residue_paths":{path:present(path) for path in %s},
  "engine_residue_paths":{path:present(path) for path in %s},
  "fresh_staging_count":len(names),
  "fresh_staging_names_sha256":hashlib.sha256("".join(n+"\n" for n in names).encode()).hexdigest(),
  "raw_staging_names_included":False,
  "mutation":False,
  "t1_file_write":False,
  "production_service_start":False,
  "board_access":False,
}
print(json.dumps(report,sort_keys=True,separators=(",",":")))
""" % (repr(RESIDUE_PATHS), repr(ENGINE_RESIDUE_PATHS))


class StopExecution(RuntimeError):
    pass


def load_module(name: str, relative: str) -> Any:
    path = REPO_ROOT / relative
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise StopExecution(f"module_load_failed:{name}")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def run(
    argv: tuple[str, ...],
    *,
    input_bytes: bytes | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[bytes]:
    try:
        completed = subprocess.run(
            argv,
            input=input_bytes,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        raise StopExecution("command_timeout") from error
    except OSError as error:
        raise StopExecution("command_transport_error") from error
    if completed.returncode != 0:
        raise StopExecution(
            f"command_failed:{Path(argv[0]).name}:{completed.returncode}"
        )
    return completed


def git_text(*args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(REPO_ROOT), *args),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if completed.returncode != 0:
        raise StopExecution("local_git_failed")
    return completed.stdout.strip()


def validate_target(target: str) -> None:
    if (
        not target
        or target.strip() != target
        or any(c.isspace() for c in target)
        or target.startswith("-")
    ):
        raise StopExecution("t1_target_invalid")
    if any(
        mark in target.casefold()
        for mark in ("placeholder", "example", "<", ">")
    ):
        raise StopExecution("t1_target_placeholder")


def validate_timeout(timeout_seconds: int) -> None:
    if (
        isinstance(timeout_seconds, bool)
        or timeout_seconds < 1
        or timeout_seconds > 600
    ):
        raise StopExecution("timeout_seconds_invalid")


def validate_source(
    expected_head: str,
    artifact_head: str,
) -> dict[str, object]:
    for value in (expected_head, artifact_head):
        if re.fullmatch(r"[0-9a-f]{40}", value) is None:
            raise StopExecution("source_head_invalid")
    if git_text("rev-parse", "HEAD") != expected_head:
        raise StopExecution("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise StopExecution("tracked_worktree_dirty")
    for relative, expected_blob in EXPECTED_BLOBS.items():
        if (
            git_text("rev-parse", f"{expected_head}:{relative}")
            != expected_blob
        ):
            raise StopExecution(f"source_blob_mismatch:{relative}")
    ancestor = subprocess.run(
        (
            "git",
            "-C",
            str(REPO_ROOT),
            "merge-base",
            "--is-ancestor",
            artifact_head,
            expected_head,
        ),
        capture_output=True,
        check=False,
        timeout=15,
    )
    if ancestor.returncode != 0:
        raise StopExecution("artifact_source_not_ancestor")
    return {
        "head": expected_head,
        "artifact_head": artifact_head,
        "clean": True,
    }


def evidence_root(path: Path) -> Path:
    path = path.expanduser().resolve()
    repo = REPO_ROOT.resolve()
    if path == repo or repo in path.parents:
        raise StopExecution("evidence_root_inside_repository")
    if path.exists():
        if (
            path.is_symlink()
            or not path.is_dir()
            or path.stat().st_uid != os.geteuid()
            or stat.S_IMODE(path.stat().st_mode) != 0o700
            or any(path.iterdir())
        ):
            raise StopExecution("evidence_root_invalid")
    else:
        path.mkdir(parents=True, mode=0o700)
    return path


def write_private(path: Path, document: Any) -> None:
    data = (
        json.dumps(document, indent=2, sort_keys=True) + "\n"
    ).encode()
    fd = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        if stat.S_IMODE(os.fstat(fd).st_mode) != 0o600:
            raise StopExecution("evidence_file_mode_invalid")
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise StopExecution("evidence_write_short")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def ssh_stream(
    target: str,
    command: str,
    source: bytes,
    timeout: int,
) -> dict[str, Any]:
    validate_target(target)
    argv = (
        "ssh",
        "-o",
        "BatchMode=no",
        "-o",
        "NumberOfPasswordPrompts=1",
        "-o",
        "PreferredAuthentications=publickey,password",
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
    )
    completed = run(
        argv,
        input_bytes=source,
        timeout=timeout,
    )
    try:
        document = json.loads(completed.stdout.decode())
    except (UnicodeError, json.JSONDecodeError) as error:
        raise StopExecution("remote_json_invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("status") != "PASS"
    ):
        raise StopExecution("remote_report_invalid")
    return document


def capacity_preflight(
    target: str,
    run_id: str,
    artifact_name: str,
    artifact_id: int,
    artifact_zip_sha256: str,
    artifact_head: str,
) -> dict[str, Any]:
    staging = load_module("n3w_f2_staging", STAGING_RELATIVE)
    work = Path(tempfile.mkdtemp(prefix="n3w-f2-artifact."))
    digest = artifact_zip_sha256.removeprefix("sha256:")
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise StopExecution("artifact_zip_sha256_invalid")
    try:
        staging._download_artifact(
            work,
            run_id=run_id,
            artifact_name=artifact_name,
            artifact_id=artifact_id,
            artifact_zip_sha256=digest,
        )
        archive_sha = staging._read_sidecar(
            work / "runtime-payload.sha256"
        )
        manifest_sha = staging._read_sidecar(
            work / "payload-manifest.sha256"
        )
        archive = staging._verify_outer_artifact(
            work,
            archive_sha256=archive_sha,
            manifest_sha256=manifest_sha,
        )
        manifest = staging._read_payload_manifest(
            archive,
            manifest_sha256=manifest_sha,
        )
        if manifest.get("source_head") != artifact_head:
            raise StopExecution("artifact_source_head_mismatch")
        capacity = staging._capacity_contract(work, manifest)
        staging._verify_image_artifacts(work, manifest, capacity)
        baseline = staging._remote_baseline_report(
            target,
            work / "host-baseline.py",
            "check",
        )
        if baseline.get("status") == "PASS":
            storage = staging._remote_storage_report(target)
            free = min(
                int(storage[k])
                for k in (
                    "staging_free_bytes",
                    "docker_free_bytes",
                    "image_store_free_bytes",
                )
            )
            admission = "PASS"
        else:
            storage = None
            free = staging._remote_root_free_bytes(target)
            admission = "PREBASELINE_ROOT_PASS"
        plan = staging._plan_transport(
            manifest,
            archive_size_bytes=archive.stat().st_size,
            remote_free_bytes=free,
            capacity=capacity,
        )
        if plan.capacity_pass is not True:
            raise StopExecution("transport_capacity_insufficient")
        return {
            "status": "PASS",
            "artifact_source_head": artifact_head,
            "host_baseline": baseline,
            "storage": storage,
            "transport": plan.to_dict(),
            "capacity_admission": admission,
            "payload_transfer": False,
            "docker_mutation": False,
            "authorization_claimed": False,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def accept(
    identity: dict[str, Any],
    supplement: dict[str, Any],
    inventory: dict[str, Any],
    capacity: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    for key, value in EXPECTED_OS.items():
        if identity.get("os_release", {}).get(key) != value:
            failures.append(f"os:{key}")
    for key, value in EXPECTED_ARMBIAN.items():
        if identity.get("armbian_release", {}).get(key) != value:
            failures.append(f"armbian:{key}")
    if supplement.get("architecture") not in {"arm64", "aarch64"}:
        failures.append("architecture")

    machine = identity.get("machine_identity", {})
    machine_records = (
        list(machine.values()) if isinstance(machine, dict) else []
    )
    hashes = [
        item.get("content_sha256")
        for item in machine_records
        if isinstance(item, dict)
        and item.get("valid_hex32") is True
        and item.get("content_sha256")
    ]
    if len(hashes) < 2 or len(set(hashes)) != 1:
        failures.append("machine_id")

    key_records = identity.get("ssh_host_keys", [])
    private_names = {
        str(item.get("name"))
        for item in key_records
        if isinstance(item, dict)
        and item.get("material") == "private_metadata_only"
        and item.get("kind") == "regular"
        and item.get("uid") == 0
        and item.get("gid") == 0
        and item.get("mode") == "0600"
        and isinstance(item.get("name"), str)
    }
    public_names = {
        str(item.get("name")).removesuffix(".pub")
        for item in key_records
        if isinstance(item, dict)
        and item.get("material") == "public"
        and item.get("kind") == "regular"
        and item.get("uid") == 0
        and item.get("gid") == 0
        and item.get("mode") == "0644"
        and item.get("public_key_parse") == "PASS"
        and isinstance(item.get("name"), str)
        and str(item.get("name")).endswith(".pub")
    }
    if not private_names.intersection(public_names):
        failures.append("ssh_host_keys")

    if supplement.get("ssh", {}).get("active") != "active":
        failures.append("ssh")
    if (
        supplement.get("networkmanager", {}).get("active")
        != "active"
    ):
        failures.append("networkmanager")
    firstboot = supplement.get("armbian_firstrun", {})
    if (
        firstboot.get("load_state") != "loaded"
        or firstboot.get("active") != "inactive"
        or firstboot.get("unit_file_state") != "disabled"
        or firstboot.get("result") != "success"
        or firstboot.get("exec_main_status") != "0"
    ):
        failures.append("firstboot")
    for key in ("default_route_present", "dns_resolution_present"):
        if supplement.get(key) is not True:
            failures.append(key)
    if str(supplement.get("ntp_synchronized", "")).lower() != "yes":
        failures.append("ntp")

    if (
        any(supplement.get("residue_paths", {}).values())
        or supplement.get("fresh_staging_count") != 0
    ):
        failures.append("product_residue")

    classifications = inventory.get("classifications", {})
    if classifications.get("DELETE_PRODUCT_STATE_CANDIDATE"):
        failures.append("product_state")
    baseline = capacity.get("host_baseline", {})
    baseline_status = baseline.get("status")
    unknown = classifications.get("UNKNOWN_STOP") or []
    if inventory.get("status") != "PASS":
        allowed = (
            baseline_status == "MISSING"
            and unknown
            and all(
                isinstance(item, dict)
                and item.get("type") == "firewall_visibility"
                for item in unknown
            )
        )
        if not allowed:
            failures.append("inventory")

    remote = inventory.get("remote", {})
    if any(
        isinstance(item, dict) and item.get("exists")
        for item in remote.get("product_paths", [])
    ):
        failures.append("product_paths")
    if remote.get("systemd", {}).get("units"):
        failures.append("product_units")
    if remote.get("listeners", {}).get("records"):
        failures.append("production_listeners")

    if baseline_status == "PASS":
        docker = remote.get("docker", {})
        if any(
            docker.get(name)
            for name in ("containers", "images", "volumes")
        ):
            failures.append("docker_objects")
        networks = {
            str(item.get("Name"))
            for item in docker.get("networks", [])
            if isinstance(item, dict) and item.get("Name")
        }
        if (
            networks != DEFAULT_NETWORKS
            or any((docker.get("errors") or {}).values())
        ):
            failures.append("docker_state")
    elif baseline_status == "MISSING":
        if any(
            supplement.get("engine_residue_paths", {}).values()
        ):
            failures.append("engine_residue")
        candidates = supplement.get("package_candidates", {})
        packages_visible = bool(
            candidates.get("docker.io")
            and candidates.get("docker-compose-v2")
        )
        apt = supplement.get("apt", {})
        apt_source = apt.get("source", {})
        fresh_apt_index_deferred = (
            apt.get("lists_file_count") == 0
            and apt_source.get("ubuntu_ports") is True
            and apt_source.get("resolute") is True
            and apt_source.get("universe") is True
        )
        if not (packages_visible or fresh_apt_index_deferred):
            failures.append("docker_packages")
    else:
        failures.append("host_baseline")

    if (
        capacity.get("transport", {}).get("capacity_pass")
        is not True
    ):
        failures.append("capacity")
    return failures


def _persist_stop(
    root: Path,
    *,
    target: str,
    error_code: str,
) -> None:
    path = root / "result.json"
    if path.exists() or path.is_symlink():
        return
    document = {
        "schema": SCHEMA,
        "status": "STOP",
        "error_code": error_code,
        "target_sha256": hashlib.sha256(target.encode()).hexdigest(),
        "read_only": True,
        "t1_file_write": False,
        "live_runtime_mutation": False,
        "production_service_start": False,
        "authorization_claimed": False,
        "f3_authorized": False,
        "board_access": False,
    }
    try:
        write_private(path, document)
    except (OSError, StopExecution):
        pass


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.confirm != CONFIRMATION:
        raise StopExecution("readonly_confirmation_invalid")
    validate_timeout(args.timeout_seconds)
    validate_source(
        args.expected_source_head,
        args.expected_artifact_source_head,
    )
    root = evidence_root(args.evidence_root)

    try:
        identity_source = (
            REPO_ROOT / IDENTITY_RELATIVE
        ).read_bytes()
        identity = ssh_stream(
            args.target,
            REMOTE_IDENTITY_COMMAND,
            identity_source,
            args.timeout_seconds,
        )
        supplement = ssh_stream(
            args.target,
            "sudo -n python3 -B -",
            SUPPLEMENT_SCRIPT.encode(),
            args.timeout_seconds,
        )
        inventory = load_module(
            "n3w_f2_inventory",
            INVENTORY_RELATIVE,
        ).collect(args.target)
        capacity = capacity_preflight(
            args.target,
            args.artifact_run_id,
            args.artifact_name,
            args.artifact_id,
            args.artifact_zip_sha256,
            args.expected_artifact_source_head,
        )
        failures = accept(
            identity,
            supplement,
            inventory,
            capacity,
        )

        for name, document in (
            ("identity.json", identity),
            ("supplement.json", supplement),
            ("inventory.json", inventory),
            ("capacity.json", capacity),
        ):
            write_private(root / name, document)

        result = {
            "schema": SCHEMA,
            "status": "PASS" if not failures else "STOP",
            "failures": failures,
            "expected_source_head": args.expected_source_head,
            "expected_artifact_source_head":
                args.expected_artifact_source_head,
            "artifact_id": args.artifact_id,
            "target_sha256":
                hashlib.sha256(args.target.encode()).hexdigest(),
            "read_only": True,
            "t1_file_write": False,
            "live_runtime_mutation": False,
            "production_service_start": False,
            "authorization_claimed": False,
            "f3_authorized": False,
            "board_access": False,
        }
        write_private(root / "result.json", result)
        return result
    except Exception as error:
        error_code = (
            str(error)
            if isinstance(error, StopExecution)
            else f"readonly_preflight_component_failed:{type(error).__name__}"
        )
        _persist_stop(
            root,
            target=args.target,
            error_code=error_code,
        )
        if isinstance(error, StopExecution):
            raise
        raise StopExecution(error_code) from error


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--execute", action="store_true")
    value.add_argument("--target")
    value.add_argument("--evidence-root", type=Path)
    value.add_argument("--confirm", default="")
    value.add_argument("--expected-source-head")
    value.add_argument("--artifact-run-id")
    value.add_argument("--artifact-name")
    value.add_argument("--artifact-id", type=int)
    value.add_argument("--artifact-zip-sha256")
    value.add_argument("--expected-artifact-source-head")
    value.add_argument("--timeout-seconds", type=int, default=90)
    return value


def main() -> int:
    args = parser().parse_args()
    required = (
        args.target,
        args.evidence_root,
        args.expected_source_head,
        args.artifact_run_id,
        args.artifact_name,
        args.artifact_id,
        args.artifact_zip_sha256,
        args.expected_artifact_source_head,
    )
    if not args.execute or any(item is None for item in required):
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "error_code": "execution_arguments_missing",
                    "f3_authorized": False,
                }
            )
        )
        return 2
    try:
        result = execute(args)
    except StopExecution as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "STOP",
                    "error_code": str(error),
                    "read_only": True,
                    "f3_authorized": False,
                }
            )
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
