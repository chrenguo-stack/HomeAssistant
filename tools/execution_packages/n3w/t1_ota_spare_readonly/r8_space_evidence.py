"""Read spare T1 storage and measure the frozen R8 image inputs on the Mac."""

import argparse
from collections import Counter
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

REPO = "chrenguo-stack/HomeAssistant"
RUN = "n3w-r8-current-backup-20261122-01"
BACKUP_SHA = "951e03aa715f44f41bededc9beb1e5ff8efd15e6fc57f6a2e798b851a8481f46"
USB_SHA = "85ffe7fc36b40a32cd95846cc6126aa5fb3a29e3a880e2fc46411e7301664eaa"
RECOVERY_ZIP_SHA = "287307871e3cc4262a3f010888f71001cb2e705f1d87f637742e995c5d015106"
RECOVERY_PYZ_SHA = "f39629268ffeab9906f9de8cb60362d604d5b9150ef4c13571926b00921e6b84"
ORIGINAL = {
    "homeassistant": ("local/n3w-homeassistant:2026.10.4-5881590f", "sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365"),
    "manager": ("local/greenhouse-manager:fresh-44e7d7472714", "sha256:1471828ab07cf9b71c01a6e78994711a5954f0a178b8be087a28bb65a967c7d2"),
    "broker": ("local/n3w-mosquitto:2.1.2-3184566d", "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563"),
}
INPUTS = {
    "predecessor_ha": ("14716899788.zip", "homeassistant-arm64.tar",
                       "local/n3w-homeassistant:2026.10.0-0c73235a",
                       2448553472, "755ae190b0f9c7cc89b0b9d9b2153ea3a81c3cf5c9dd5bc71ab9471603861acb"),
    "candidate_manager": ("14716899788.zip", "greenhouse-manager-arm64.tar",
                          "local/greenhouse-manager:fresh-741a1463e7de",
                          62950400, "259f6dacd92cfb96b178e0afd61a1c04d8fee52a217822e66bf43b6c9ed3196e"),
    "target_ha": ("13391983948.zip", "homeassistant-arm64.tar.gz", ORIGINAL["homeassistant"][0],
                  835309535, "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"),
}


def sha(value):
    return hashlib.sha256(value).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def read(*command):
    return subprocess.check_output(command, timeout=45, stderr=subprocess.PIPE, text=True)


def usb_evidence():
    disks = json.loads(read("lsblk", "--bytes", "--json", "--tree", "-o",
                           "PATH,TRAN,TYPE,FSTYPE,MAJ:MIN,UUID,SIZE"))["blockdevices"]
    matches = [row for disk in disks if disk["type"] == "disk" and disk["tran"] == "usb"
               for row in disk.get("children", [disk])
               if row["fstype"] == "ext4" and sha((row["uuid"] or "").encode()) == USB_SHA]
    if len(matches) != 1:
        return {"observation": "EXPECTED_MEDIA_NOT_UNIQUE"}
    row = matches[0]
    record = {"device_bytes": int(row["size"]), "filesystem_uuid_sha256": USB_SHA}
    namespaces = set()
    for process in Path("/proc").glob("[0-9]*"):
        try:
            namespace = (process / "ns/mnt").stat().st_ino
            if namespace in namespaces:
                continue
            mounts = (process / "mountinfo").read_text().splitlines()
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            return dict(record, observation="MOUNT_SCAN_INCOMPLETE")
        namespaces.add(namespace)
        if any(line.split()[2] == row["maj:min"] for line in mounts):
            return dict(record, observation="ALREADY_MOUNTED")
    dumpe2fs = shutil.which("dumpe2fs", path="/usr/sbin:/sbin:/usr/bin:/bin")
    if not dumpe2fs:
        return dict(record, observation="SUPERBLOCK_TOOL_UNAVAILABLE")
    try:
        header = read(dumpe2fs, "-h", row["path"])
        fields = dict((key.strip(), value.strip()) for key, value in
                      (line.split(":", 1) for line in header.splitlines() if ":" in line))
        require(sha(fields["Filesystem UUID"].encode()) == USB_SHA, "usb_superblock_identity_drift")
        if fields["Filesystem state"] != "clean" or "needs_recovery" in fields["Filesystem features"].split():
            return dict(record, observation="FILESYSTEM_NEEDS_RECOVERY")
        bs, free, reserved = (int(fields[key]) for key in
                              ("Block size", "Free blocks", "Reserved block count"))
        require(bs > 0 and free >= 0 and reserved >= 0, "usb_superblock_geometry_invalid")
    except (KeyError, ValueError, OSError, subprocess.SubprocessError):
        return dict(record, observation="SUPERBLOCK_READ_UNAVAILABLE")
    return dict(record, observation="UNMOUNTED_SUPERBLOCK_ESTIMATE",
                nonreserved_free_estimate_bytes=max(0, free - reserved) * bs)


def reclaim_inventory(docker, root):
    def inspect_rows(command, ids, template):
        if not ids:
            return []
        raw = read(docker, *command, "--format", template, *ids)
        return [line.split("\t") for line in raw.splitlines()]

    all_containers = read(docker, "ps", "-aq", "--no-trunc").splitlines()
    attached = Counter(row[0] for row in inspect_rows(
        ("inspect", "--type", "container"), all_containers, "{{.Image}}"))
    protected = {identity for _, identity in ORIGINAL.values()}
    image_ids = sorted(set(read(docker, "image", "ls", "-aq", "--no-trunc").splitlines()))
    rows = inspect_rows(("image", "inspect"), image_ids, "{{.Id}}\t{{.Size}}\t{{json .RepoTags}}")
    unreferenced = [{"image_id": identity, "nominal_size_bytes": int(size), "tags": json.loads(tags) or []}
                    for identity, size, tags in rows if not attached[identity] and identity not in protected]
    try:
        summary = [json.loads(row) for row in
                   read(docker, "system", "df", "--format", "{{json .}}").splitlines()]
    except (OSError, subprocess.SubprocessError):
        summary = None
    usage = {}
    for label, path in {"apt_archives": "/var/cache/apt/archives", "logs": "/var/log", "var_tmp": "/var/tmp"}.items():
        location = Path(path)
        if location.is_dir() and location.stat().st_dev == root.stat().st_dev:
            usage[label] = int(read("du", "-sx", "-B1", "--", path).split()[0])
    return {"scope": "READ_ONLY_NO_RECLAIM_ESTIMATE", "unreferenced_images": sorted(
            unreferenced, key=lambda item: item["nominal_size_bytes"], reverse=True),
            "original_ha_container_reference_count": attached[ORIGINAL["homeassistant"][1]],
            "docker_space_summary": summary, "other_same_filesystem_usage_bytes": usage}


def observe(inventory=False):
    require(sys.platform == "linux" and os.geteuid() == 0 and os.uname().machine in {"aarch64", "arm64"},
            "unexpected_spare_environment")
    os.environ["LC_ALL"] = "C"
    for key in ("DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY"):
        os.environ.pop(key, None)
    os.environ["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    receipt = json.loads((Path("/var/tmp") / RUN / "receipt.json").read_bytes())
    require(receipt["run_id"] == RUN and receipt["status"] == "R8_CURRENT_BACKUP_PASS"
            and receipt["backup"]["archive_sha256"] == BACKUP_SHA, "spare_backup_binding_changed")
    docker = "/usr/bin/docker"
    for service, (ref, identity) in ORIGINAL.items():
        containers = read(docker, "ps", "-q", "--filter", "label=com.docker.compose.project=n3wfc4",
                          "--filter", f"label=com.docker.compose.service={service}").splitlines()
        require(len(containers) == 1, f"{service}_running_container_count_changed")
        live = read(docker, "inspect", "--type", "container", "--format", "{{.Image}} {{.Config.Image}}",
                    containers[0]).strip()
        require(live == f"{identity} {ref}", f"{service}_runtime_image_changed")
        require(read(docker, "image", "inspect", "--format", "{{.Id}}", ref).strip() == identity,
                f"{service}_tag_binding_changed")
    listing = dict(line.split() for line in read(
        docker, "image", "ls", "--no-trunc", "--format", "{{.Repository}}:{{.Tag}} {{.ID}}").splitlines())
    driver = read(docker, "info", "--format", "{{.Driver}}").strip()
    root = Path(read(docker, "info", "--format", "{{.DockerRootDir}}").strip())
    require(root.is_absolute(), "docker_root_unavailable")
    roots = {"root": Path("/"), "docker": root, "ha": Path("/var/lib/n3wfc4-homeassistant"),
             "manager": Path("/var/lib/greenhouse-manager/manager"),
             "replay": Path("/var/lib/greenhouse-manager/n3w")}
    state = {}
    for name, path in roots.items():
        disk = os.statvfs(path)
        state[name] = {"same_filesystem_as_docker": path.stat().st_dev == root.stat().st_dev,
                       "available_bytes": disk.f_bavail * disk.f_frsize}
    if inventory:
        print(json.dumps({"storage": state, "inventory": reclaim_inventory(docker, root)}, sort_keys=True))
        return
    print(json.dumps({"storage": state, "docker_storage_driver": driver, "usb": usb_evidence(),
                      "input_tags": {key: listing.get(spec[2]) for key, spec in INPUTS.items()}},
                     sort_keys=True))


def measure(work, assets, spec):
    from n3w_t1_portable_image_identity import parse_verified_load_archive

    archive, member, tag, expected_size, expected_sha = spec
    require(shutil.disk_usage(work).free >= expected_size, "mac_temporary_space_insufficient")
    digest = hashlib.sha256()
    with tempfile.TemporaryFile(dir=work) as local, ZipFile(assets / archive) as zipped:
        require(zipped.getinfo(member).file_size == expected_size, "frozen_archive_size_mismatch")
        with zipped.open(member) as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
                local.write(block)
        require(local.tell() == expected_size and digest.hexdigest() == expected_sha,
                "frozen_archive_digest_mismatch")
        local.seek(0)
        sizes = []
        image = parse_verified_load_archive(local, archive_sha256=expected_sha,
                                          archive_size_bytes=expected_size, expected_tag=tag,
                                          unpacked_sizes=sizes)
        require(bool(sizes) and sum(sizes) > 0, "unpacked_layers_unavailable")
    return {"archive_bytes": expected_size, "unpacked_layer_bytes": sum(sizes),
            "layer_count": len(sizes), "config_digest": image.config_digest}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ssh", required=True)
    parser.add_argument("--assets", type=Path, default=Path.home() / "Downloads" / "n3w-r8-artifacts")
    parser.add_argument("--inventory", action="store_true")
    args = parser.parse_args()
    if not args.inventory:
        for filename in {spec[0] for spec in INPUTS.values()}:
            require((args.assets / filename).is_file(), f"local_artifact_missing:{filename}")
    ssh = ("ssh", "-o", "StrictHostKeyChecking=yes", "-o", "ForwardAgent=no", "-o",
           "ClearAllForwardings=yes", "-o", "ConnectTimeout=10", "-T", "--", args.ssh,
           "/usr/bin/python3 -I -B -")
    print("正在只读盘点备用 T1 的镜像和缓存。" if args.inventory else
          "正在读取备用 T1 容量和镜像标签。", flush=True)
    source = f"REMOTE_INVENTORY = {args.inventory!r}\n".encode() + Path(__file__).read_bytes()
    snapshot = json.loads(subprocess.run(ssh, input=source, stdout=subprocess.PIPE, check=True).stdout)
    if args.inventory:
        print("R8_T1_STORAGE_INVENTORY=" + json.dumps(snapshot, sort_keys=True))
        return
    print("R8_T1_STORAGE=" + json.dumps(snapshot, sort_keys=True), flush=True)
    zipped = subprocess.check_output(("gh", "api", f"repos/{REPO}/actions/artifacts/14717720726/zip"), timeout=120)
    require(sha(zipped) == RECOVERY_ZIP_SHA, "recovery_zip_sha_mismatch")
    with ZipFile(io.BytesIO(zipped)) as archive:
        package = archive.read("ha-recovery.pyz")
    require(sha(package) == RECOVERY_PYZ_SHA, "recovery_pyz_sha_mismatch")
    with tempfile.TemporaryDirectory(prefix=".r8-space-", dir=args.assets) as directory:
        work = Path(directory)
        recovery = work / "ha-recovery.pyz"
        recovery.write_bytes(package)
        sys.path.insert(0, str(recovery))
        for component, spec in INPUTS.items():
            print(f"正在测量 Mac 缓存中的 {component} 镜像层。", flush=True)
            row = measure(work, args.assets, spec)
            print("R8_IMAGE_SPACE=" + json.dumps(dict(row, component=component), sort_keys=True), flush=True)
    print("R8_SPACE_EVIDENCE_COLLECTED=true")


if __name__ == "__main__":
    try:
        observe(REMOTE_INVENTORY) if "REMOTE_INVENTORY" in globals() else main()
    except (ValueError, KeyError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        detail = str(error) if isinstance(error, ValueError) else type(error).__name__
        print(f"R8 space evidence stopped: {detail}", file=sys.stderr)
        sys.exit(1)
