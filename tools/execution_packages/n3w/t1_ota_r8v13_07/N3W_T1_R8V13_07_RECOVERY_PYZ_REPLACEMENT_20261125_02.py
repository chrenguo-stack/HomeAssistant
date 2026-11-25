#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APPROVAL_ENV = "N3W_T1_R8V13_07_RECOVERY_PYZ_REPLACEMENT_APPROVED"
EXPECTED_TX_ID = "f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a"
EXPECTED_TX_SHA256 = "4b1cc60e5557b9bc338d3d0469d30aa94c7974c34a0c26dffae5caf9fde4b105"
EXPECTED_ENV_SHA256 = "d139286ebd1379af96851321755a78c8cee795edb64f93ec7b74f2bb1e152d4b"
EXPECTED_OLD_PYZ_SHA256 = "9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa"
EXPECTED_NEW_PYZ_SHA256 = "807110108df6580328e9ecde2ea18321c199b07caab4fb1c087f81d8df1b7cd2"
EXPECTED_NORMALIZED_LAUNCH_SHA256 = "67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26"
EXPECTED_RAW_LAUNCH_SHA256 = "987189ccd61c0784db089b08e51a9ad3ff317372ad8a952dcda7a03a6d844c70"
EXPECTED_AUTHORIZATION_ID_SHA256 = "de25e2d5c8ea8f183a6dca35048f6896c54d3876bea70f6c35afc847819ed136"
EXPECTED_USB_UUID = "b72ac2fc-79a0-4fb8-888e-f35b0114f959"
EXPECTED_HA_REF = "local/n3w-homeassistant:2026.10.4-5881590f"
EXPECTED_HA_ID = "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365"
TARGET_REF = "local/n3w-homeassistant:2026.10.0-0c73235a"
TARGET_ID = "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306"

LIVE = Path("/opt/n3w-t1-core-updater/ha-recovery.pyz")
TX_FILE = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
ENV_FILE = Path("/etc/n3wfc4/docker-compose.env")
STAGE = Path("/tmp/n3w-r8v13-07-recovery-pyz-replacement-20261125-02")
CANDIDATE = STAGE / "new-ha-recovery.pyz"
BACKUP = STAGE / "old-ha-recovery.pyz"
UNITS = {
    "timer": "n3w-t1-ha-recovery-retry.timer",
    "retry": "n3w-t1-ha-recovery-retry.service",
    "socket": "n3w-t1-ha-ota-ipc.socket",
    "ipc": "n3w-t1-ha-ota-ipc.service",
}

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def run(*argv: str, check: bool = True) -> str:
    return subprocess.run(argv, check=check, text=True, capture_output=True, timeout=180).stdout.strip()

def state(unit: str) -> str:
    return run("systemctl", "is-active", unit, check=False)

def atomic_publish(source: Path, destination: Path) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix=".ha-recovery.pyz.r8v13-07.", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as output, source.open("rb") as incoming:
            os.fchmod(output.fileno(), 0o644)
            shutil.copyfileobj(incoming, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)

def verify_terminal() -> dict:
    if sha256(TX_FILE) != EXPECTED_TX_SHA256 or sha256(ENV_FILE) != EXPECTED_ENV_SHA256:
        raise RuntimeError("terminal_control_file_drift")
    document = json.loads(TX_FILE.read_text(encoding="utf-8"))
    expected = {
        "transaction_id_sha256": EXPECTED_TX_ID,
        "status": "ROLLED_BACK",
        "phase": "U13B_ROLLED_BACK",
        "failure_code": "ha_usb_target_acceptance_evidence_unavailable",
        "recovery_required": False,
        "authorization_claimed": True,
        "authorization_consumed": True,
        "authorization_id_sha256": EXPECTED_AUTHORIZATION_ID_SHA256,
    }
    for key, value in expected.items():
        if document.get(key) != value:
            raise RuntimeError(f"terminal_transaction_drift:{key}")
    return document

RUNTIME_CHECK = r"""
import json
import sys
sys.path.insert(0, sys.argv[1])
from n3w_t1_core_updater_ha_recovery_startup import LocalHaPredecessorRuntime

document = json.load(open(sys.argv[2], encoding="utf-8"))
expected = document["predecessor_start"]
journal = document.get("ha_data_restore")
if not isinstance(journal, dict) or journal.get("step") != "PUBLISHED":
    raise SystemExit("published_data_journal_missing")
runtime = LocalHaPredecessorRuntime()
raw_binding, _ = runtime._restart_binding()
normalized_binding, _ = runtime._restart_binding(published=journal)
if raw_binding["images"] != expected["images"]:
    raise SystemExit("image_binding_drift")
if raw_binding["launch_sha256"] != sys.argv[4]:
    raise SystemExit("raw_launch_drift")
if normalized_binding != expected:
    raise SystemExit("normalized_binding_drift")
if normalized_binding["launch_sha256"] != sys.argv[3]:
    raise SystemExit("normalized_launch_drift")
runtime.verify_published_predecessor_health(document)
"""

def verify_runtime(pyz: Path) -> None:
    subprocess.run(
        ["/usr/bin/python3", "-I", "-", str(pyz), str(TX_FILE),
         EXPECTED_NORMALIZED_LAUNCH_SHA256, EXPECTED_RAW_LAUNCH_SHA256],
        input=RUNTIME_CHECK, text=True, check=True, timeout=180,
    )

def verify_images_and_media() -> None:
    if run("docker", "image", "inspect", EXPECTED_HA_REF, "--format", "{{.Id}}") != EXPECTED_HA_ID:
        raise RuntimeError("ha_image_drift")
    if subprocess.run(["docker", "image", "inspect", TARGET_REF], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60).returncode == 0:
        raise RuntimeError("target_image_present")
    if subprocess.run(["docker", "image", "inspect", TARGET_ID], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60).returncode == 0:
        raise RuntimeError("target_image_id_present")
    mount = run(
        "findmnt", "--list", "--noheadings", "--source", f"UUID={EXPECTED_USB_UUID}",
        "--output", "TARGET,FSTYPE,OPTIONS",
    ).split(maxsplit=2)
    if len(mount) != 3 or mount[1] != "ext4" or "rw" not in mount[2].split(","):
        raise RuntimeError("bound_usb_mount_drift")

def restore(states: dict[str, str]) -> None:
    if states["socket"] in {"active", "activating"}:
        run("systemctl", "start", UNITS["socket"])
    if states["ipc"] in {"active", "activating"}:
        run("systemctl", "start", UNITS["ipc"])
    if states["timer"] in {"active", "activating"}:
        run("systemctl", "start", UNITS["timer"])

def main() -> int:
    if os.environ.get(APPROVAL_ENV) != "YES":
        raise SystemExit("explicit replacement approval required")
    if os.geteuid() != 0:
        raise SystemExit("root required")
    if len(sys.argv) != 1:
        raise SystemExit("replacement executor accepts no positional arguments")
    metadata = STAGE.lstat()
    if not STAGE.is_dir() or metadata.st_uid != 0 or (metadata.st_mode & 0o077):
        raise SystemExit("stage_directory_invalid")
    candidate_metadata = CANDIDATE.lstat()
    if not CANDIDATE.is_file() or CANDIDATE.is_symlink() or candidate_metadata.st_uid != 0:
        raise SystemExit("candidate_file_invalid")
    if sha256(CANDIDATE) != EXPECTED_NEW_PYZ_SHA256:
        raise SystemExit("candidate_pyz_digest_drift")
    if sha256(LIVE) != EXPECTED_OLD_PYZ_SHA256:
        raise SystemExit("live_pyz_digest_drift")

    verify_terminal()
    verify_images_and_media()
    verify_runtime(LIVE)

    states = {name: state(unit) for name, unit in UNITS.items()}
    if states["timer"] != "active" or states["retry"] not in {"inactive", "failed"} or states["socket"] != "active":
        raise SystemExit("control_plane_prestate_drift")

    backup = BACKUP
    published = False
    quiesced = False
    try:
        for unit in (UNITS["timer"], UNITS["retry"], UNITS["socket"], UNITS["ipc"]):
            run("systemctl", "stop", unit, check=False)
        quiesced = True
        if state(UNITS["timer"]) != "inactive" or state(UNITS["socket"]) not in {"inactive", "failed"}:
            raise RuntimeError("control_plane_quiesce_failed")

        if sha256(LIVE) != EXPECTED_OLD_PYZ_SHA256 or sha256(TX_FILE) != EXPECTED_TX_SHA256:
            raise RuntimeError("premutation_recheck_drift")
        shutil.copyfile(LIVE, backup)
        os.chmod(backup, 0o600)
        if sha256(backup) != EXPECTED_OLD_PYZ_SHA256:
            raise RuntimeError("backup_digest_drift")

        atomic_publish(CANDIDATE, LIVE)
        published = True
        if sha256(LIVE) != EXPECTED_NEW_PYZ_SHA256:
            raise RuntimeError("new_pyz_publish_drift")
        subprocess.run(["/usr/bin/python3", "-I", str(LIVE), "--help"], check=True, stdout=subprocess.DEVNULL, timeout=60)

        restore(states)
        quiesced = False
        if state(UNITS["timer"]) != "active" or state(UNITS["socket"]) != "active":
            raise RuntimeError("control_plane_restore_failed")

        verify_terminal()
        verify_images_and_media()
        verify_runtime(LIVE)
    except Exception:
        if published and backup.is_file():
            for unit in (UNITS["timer"], UNITS["retry"], UNITS["socket"], UNITS["ipc"]):
                run("systemctl", "stop", unit, check=False)
            atomic_publish(backup, LIVE)
            if sha256(LIVE) != EXPECTED_OLD_PYZ_SHA256:
                print("PYZ_ROLLBACK=FAIL")
            else:
                print("PYZ_ROLLBACK=PASS")
        if quiesced or published:
            restore(states)
        print("RESULT=R8V13_07_RECOVERY_PYZ_REPLACEMENT_STOP")
        raise

    backup.unlink(missing_ok=True)
    print("LIVE_RECOVERY_PYZ_SHA256=" + EXPECTED_NEW_PYZ_SHA256)
    print("TERMINAL_TRANSACTION_UNCHANGED=true")
    print("TARGET_2026_10_0_PRESENT=false")
    print("NEW_TRANSACTION=false")
    print("INSTALL_REPLAY=false")
    print("R8V13_08_AUTO_ADVANCE=false")
    print("RESULT=R8V13_07_RECOVERY_PYZ_REPLACEMENT_PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
