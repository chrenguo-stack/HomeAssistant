"""Observe spare T1 reception and preserve its original image archives on the Mac."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile

REPO = "chrenguo-stack/HomeAssistant"
ARTIFACT = 14717720726
ZIP_SHA = "287307871e3cc4262a3f010888f71001cb2e705f1d87f637742e995c5d015106"
PYZ_SHA = "f39629268ffeab9906f9de8cb60362d604d5b9150ef4c13571926b00921e6b84"
RUN_ID = "n3w-r8-current-backup-20261122-01"
BACKUP_SHA = "951e03aa715f44f41bededc9beb1e5ff8efd15e6fc57f6a2e798b851a8481f46"
IMAGES = {
    "homeassistant": ("local/n3w-homeassistant:2026.10.4-5881590f", "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365"),
    "manager": ("local/greenhouse-manager:fresh-44e7d7472714", "sha256:1471828ab07cf9b71c01a6e78994711a5954f0a178b8be087a28bb65a967c7d2"),
}
ROOM = 256 * 1024 * 1024
REMOTE_COMMAND = "/usr/bin/python3 -I -B -"


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def file_sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def private(path, uid):
    info = path.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == uid
         and stat.S_IMODE(info.st_mode) & 0o077 == 0, "backup_directory_not_private")


def check_receipt(folder):
    record = json.loads((folder / "receipt.json").read_bytes())
    need(record.get("run_id") == RUN_ID and record.get("status") == "R8_CURRENT_BACKUP_PASS"
         and record.get("backup", {}).get("archive_sha256") == BACKUP_SHA
         and record.get("isolated_restore_verified") is True
         and record.get("original_stack_healthy") is True,
         "current_backup_receipt_not_bound")
    return record


def docker(*args):
    return subprocess.check_output(("/usr/bin/docker", *args), timeout=35, stderr=subprocess.PIPE)


def image(service):
    ref, image_id = IMAGES[service]
    ids = docker("ps", "-q", "--filter", "label=com.docker.compose.project=n3wfc4",
                 "--filter", f"label=com.docker.compose.service={service}").splitlines()
    need(len(ids) == 1, "running_application_container_count_changed")
    running = docker("inspect", "--type", "container", "--format", "{{.Image}} {{.Config.Image}}",
                     ids[0].decode()).decode().strip()
    need(running == f"{image_id} {ref}", "running_application_image_changed")
    objects = json.loads(docker("image", "inspect", ref))
    need(len(objects) == 1, "image_inspect_shape_changed")
    info = objects[0]
    need(info["Id"] == image_id and info["Os"] == "linux" and info["Architecture"] == "arm64"
         and type(info["Size"]) is int and info["Size"] > 0, "application_image_binding_changed")
    return {key: info.get(key) for key in ("Id", "Os", "Architecture", "Variant", "Config", "RootFS", "Size")}


def observe_receive():
    from n3w_t1_core_updater_ha_data_evidence import read_local_database
    from n3w_t1_core_updater_v2_common import UpdaterV2Error

    def cursors():
        path = Path("/var/lib/greenhouse-manager/n3w/replay.sqlite3")
        with read_local_database(path) as connection:
            rows = connection.execute("SELECT node_id, boot_session_hex, seq FROM n3w_canonical_cursors")
            return {node: (boot, seq) for node, boot, seq in rows}

    try:
        before = cursors()
        for _ in range(6):
            time.sleep(5)
            after = cursors()
            if any(node not in before or boot != before[node][0] or seq > before[node][1]
                   for node, (boot, seq) in after.items()):
                return "FRESH_CURSOR_OBSERVED"
    except (OSError, sqlite3.Error, UpdaterV2Error):
        return "EVIDENCE_UNAVAILABLE"
    return "NO_FRESH_CURSOR_OBSERVED"


def remote(mode):
    need(os.geteuid() == 0 and sys.platform == "linux" and platform.machine() in {"aarch64", "arm64"},
         "unexpected_spare_environment")
    for key in ("DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY"):
        os.environ.pop(key, None)
    os.environ["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    work = Path("/var/tmp") / RUN_ID
    private(work, 0)
    check_receipt(work)
    if mode == "inspect":
        recovery = work / "ha-recovery.pyz"
        need(file_sha(recovery) == PYZ_SHA, "recovery_pyz_sha_mismatch")
        sys.path.insert(0, str(recovery))
        result = {service: image(service) for service in IMAGES}
        print(json.dumps({"images": result, "manager_receive_observation": observe_receive()}))
        return
    need(mode in IMAGES, "unexpected_export_component")
    before = image(mode)
    docker_root = Path(docker("info", "--format", "{{.DockerRootDir}}").decode().strip())
    need(docker_root.is_absolute() and shutil.disk_usage(docker_root).free >= before["Size"] + ROOM,
         "spare_docker_export_space_insufficient")
    subprocess.run(("/usr/bin/docker", "image", "save", IMAGES[mode][0]), check=True, timeout=3600)
    need(image(mode) == before, "application_image_changed_during_export")


def operator():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh", required=True)
    args = parser.parse_args()
    need(bool(args.ssh.strip()), "missing_spare_ssh_target")
    os.umask(0o077)
    private_root = Path.home() / ".n3w-r8-private"
    root = private_root / RUN_ID
    private(private_root, os.getuid())
    private(root, os.getuid())
    record = check_receipt(root)
    need(file_sha(root / "homeassistant-preupgrade.tar.gz.enc") == BACKUP_SHA, "mac_data_backup_sha_mismatch")
    need(file_sha(root / "homeassistant-preupgrade.metadata.json") == record["metadata_sha256"],
         "mac_data_backup_metadata_sha_mismatch")
    source = Path(__file__).read_bytes()
    ssh = ("ssh", "-o", "StrictHostKeyChecking=yes", "-o", "ForwardAgent=no", "-o",
           "ClearAllForwardings=yes", "-o", "ConnectTimeout=10", "-T", "--", args.ssh, REMOTE_COMMAND)

    def payload(mode):
        return f"REMOTE_MODE = {mode!r}\n".encode() + source

    zipped = subprocess.check_output(("gh", "api", f"repos/{REPO}/actions/artifacts/{ARTIFACT}/zip"), timeout=120)
    need(sha(zipped) == ZIP_SHA, "recovery_zip_sha_mismatch")
    with ZipFile(io.BytesIO(zipped)) as archive:
        package = archive.read("ha-recovery.pyz")
    need(sha(package) == PYZ_SHA, "recovery_pyz_sha_mismatch")
    print("正在只读核对实际运行镜像，并观察新的 Manager 收数。", flush=True)
    remote_info = subprocess.run(ssh, input=payload("inspect"), stdout=subprocess.PIPE, check=True)
    observation = json.loads(remote_info.stdout)
    print("R8_MANAGER_RECEIVE=" + observation["manager_receive_observation"], flush=True)
    destination = root / "original-images"
    destination.mkdir(mode=0o700, exist_ok=True)
    private(destination, os.getuid())
    needed = sum(observation["images"][service]["Size"] for service in IMAGES
                 if not (destination / (service + ".tar")).is_file())
    need(shutil.disk_usage(destination).free >= needed + ROOM, "mac_image_export_space_insufficient")
    with tempfile.TemporaryDirectory(prefix=".receiving-", dir=destination) as temporary:
        work = Path(temporary)
        recovery = work / "ha-recovery.pyz"
        recovery.write_bytes(package)
        sys.path.insert(0, str(recovery))
        from n3w_t1_portable_image_identity import parse_verified_load_archive, verify_runtime_document

        for service, (ref, expected_id) in IMAGES.items():
            final = destination / (service + ".tar")
            exists = final.exists()
            if exists:
                info = final.lstat()
                need(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                     and stat.S_IMODE(info.st_mode) & 0o077 == 0, "existing_image_archive_not_private")
            else:
                need(not final.is_symlink(), "image_destination_is_symlink")
            path = final if exists else work / final.name
            if not exists:
                print(f"正在导出 {service} 镜像至 Mac。", flush=True)
                with path.open("xb") as output:
                    subprocess.run(ssh, input=payload(service), stdout=output, check=True)
                    output.flush()
                    os.fsync(output.fileno())
            print(f"正在校验 {service} 归档、镜像配置和层。", flush=True)
            digest = file_sha(path)
            size = path.stat().st_size
            with path.open("rb") as stream:
                identity = parse_verified_load_archive(
                    stream, archive_sha256=digest, archive_size_bytes=size, expected_tag=ref)
            outcome = verify_runtime_document(identity, observation["images"][service])
            need(outcome.status == "VERIFIED" and outcome.runtime_image_id == expected_id,
                 "saved_image_does_not_match_spare_runtime")
            if not exists:
                os.link(path, final, follow_symlinks=False)
            print(json.dumps({"component": service, "runtime_image_id": expected_id, "image_reference": ref,
                              "archive_bytes": size, "archive_sha256": digest,
                              "portable_identity_verified": True}), flush=True)
    print("R8_ORIGINAL_IMAGE_EXPORT_PASS=true")


if __name__ == "__main__":
    try:
        remote(REMOTE_MODE) if "REMOTE_MODE" in globals() else operator()
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(f"R8 image preservation stopped: {message}", file=sys.stderr)
        sys.exit(1)
