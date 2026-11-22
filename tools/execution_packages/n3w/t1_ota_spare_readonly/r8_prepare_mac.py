"""Run the R7 observer and verify the frozen R8 image artifacts from a Mac."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


REPO = "chrenguo-stack/HomeAssistant"
OBSERVER = "3af2bf616d5e56c69f695b18a16d5377bb070950"
OBSERVER_PATH = "tools/execution_packages/n3w/t1_ota_spare_readonly/observe.py"
OBSERVER_SHA256 = "e9f9a5740dd9482a441fc962923ffb24f7eea46072f3daec2357147caaa68110"
RECOVERY = (14715501376, "078500292fba59c2acd187ca3613258a7c6d1c6594113d925e98352d4bc9b055")
FACTORY = (13070404405, "99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93")
CANDIDATE_HEAD = "741a1463e7de065401749e47e59d30b295d5d6e8"
CANDIDATE = (14716899788, "1d4f857de78e5967ff94978411b813c8b7af0391d56e52ff3407ab480f0ae277")
TARGET = (13391983948, "df95749cec1e48796d2cf3241d19739601fe7be78c48638284d10eec786e4fd2")
TARGET_ARCHIVE_SHA256 = "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"
PREDECESSOR_IMAGE_ID = "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306"

USB_OBSERVATION = r'''
import hashlib
import json
from pathlib import Path
import subprocess

listing = subprocess.check_output((
    "lsblk", "--json", "--bytes", "--tree", "--output", "NAME,TRAN,TYPE,FSTYPE,SIZE,MAJ:MIN,UUID",
))
media = [
    {key: part[key] for key in ("name", "fstype", "size", "maj:min", "uuid")}
    for disk in json.loads(listing)["blockdevices"] if disk["type"] == "disk" and disk["tran"] == "usb"
    for part in (disk.get("children") or [disk]) if part["type"] in ("disk", "part")
]
counts = {part["maj:min"]: 0 for part in media}
seen = set()
unreadable = set()
if counts:
    for process in Path("/proc").glob("[0-9]*"):
        try:
            namespace = (process / "ns/mnt").stat().st_ino
            if namespace in seen:
                continue
            mounts = (process / "mountinfo").read_text().splitlines()
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError:
            unreadable.add(process.name)
            continue
        seen.add(namespace)
        for device in {row.split()[2] for row in mounts} & counts.keys():
            counts[device] += 1
for part in media:
    part["observed_mount_namespaces"] = counts[part.pop("maj:min")]
    uuid = part.pop("uuid")
    part["filesystem_uuid_sha256"] = hashlib.sha256(uuid.encode()).hexdigest() if uuid else None
print(json.dumps({"usb_candidates": media, "mount_namespace_scan_incomplete": bool(unreadable)}, sort_keys=True))
'''


def check(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha256(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def get_zip(spec, directory):
    artifact_id, expected = spec
    path = directory / f"{artifact_id}.zip"
    if not path.exists():
        print(f"Downloading GitHub artifact {artifact_id}", file=sys.stderr, flush=True)
        with TemporaryDirectory(dir=directory) as temporary:
            candidate = Path(temporary) / path.name
            with candidate.open("wb") as output:
                subprocess.run(["gh", "api", f"repos/{REPO}/actions/artifacts/{artifact_id}/zip"],
                               stdout=output, check=True)
            with candidate.open("rb") as content:
                check(sha256(content) == expected, f"artifact {artifact_id} ZIP digest mismatch")
            candidate.rename(path)
    else:
        with path.open("rb") as content:
            check(sha256(content) == expected, f"artifact {artifact_id} local ZIP digest mismatch")
    return ZipFile(path)


def observe(ssh):
    with TemporaryDirectory() as directory:
        work = Path(directory)
        observer = work / "observe.py"
        raw = subprocess.check_output([
            "gh", "api", "-H", "Accept: application/vnd.github.raw+json",
            f"repos/{REPO}/contents/{OBSERVER_PATH}?ref={OBSERVER}",
        ])
        check(hashlib.sha256(raw).hexdigest() == OBSERVER_SHA256, "R7 observer source digest mismatch")
        observer.write_bytes(raw)
        with get_zip(RECOVERY, work) as archive:
            archive.extractall(work)
        subprocess.run([sys.executable, str(observer), "--ssh", ssh, "--package", str(work)], check=True)
    subprocess.run([
        "ssh", "-o", "StrictHostKeyChecking=yes", "-o", "ForwardAgent=no",
        "-o", "ClearAllForwardings=yes", "-o", "ConnectTimeout=10", "-o", "RequestTTY=no",
        "--", ssh, 'if [ "$(id -u)" -eq 0 ]; then exec /usr/bin/python3 -I -B -; '
        'else exec sudo -n /usr/bin/python3 -I -B -; fi',
    ], input=USB_OBSERVATION, text=True, check=True)


def verify_bundled_image(archive, image, member_name, expected_ref):
    check(image["image"] == expected_ref and image["platform"] == "linux/arm64",
          f"{member_name} image identity mismatch")
    member = archive.getinfo(member_name)
    with archive.open(member) as content:
        check(member.file_size == image["tar_size_bytes"] and sha256(content) == image["tar_sha256"],
              f"{member_name} archive mismatch")


def verify_images(directory, candidate_bundle=False):
    directory.mkdir(parents=True, exist_ok=True)
    bundle = CANDIDATE if candidate_bundle else FACTORY
    expected_source = CANDIDATE_HEAD if candidate_bundle else "24382caae4a1f5d459297f86e8d18f10a848ca64"
    with get_zip(bundle, directory) as factory:
        binding = json.loads(factory.read("binding.json"))
        check(binding["source_head"] == expected_source, "three-image bundle source mismatch")
        image = binding["homeassistant"]
        check(image["image_id"] == PREDECESSOR_IMAGE_ID, "frozen predecessor HA image ID mismatch")
        verify_bundled_image(factory, image, "homeassistant-arm64.tar", "local/n3w-homeassistant:2026.10.0-0c73235a")
        print(json.dumps({"artifact_id": bundle[0], "factory_ha_archive_verified": True, "image": image}), flush=True)
        if candidate_bundle:
            manager = binding["manager"]
            verify_bundled_image(factory, manager, "greenhouse-manager-arm64.tar",
                                 f"local/greenhouse-manager:fresh-{CANDIDATE_HEAD[:12]}")
            print(json.dumps({"artifact_id": bundle[0], "manager_archive_verified": True, "image": manager}), flush=True)
    with get_zip(TARGET, directory) as target:
        identity = json.loads(target.read("portable-image-identity.json"))
        binding = json.loads(target.read("upstream-binding.json"))
        check(binding["control_plane_head"] == "fb7cfc857003ace3d368521d76ca2320ba399736"
              and binding["local_image"] == "local/n3w-homeassistant:2026.10.4-5881590f"
              and identity["os"] == "linux" and identity["architecture"] == "arm64", "target HA identity mismatch")
        member = target.getinfo("homeassistant-arm64.tar.gz")
        with target.open(member) as content:
            check(member.file_size == 835309535 and sha256(content) == TARGET_ARCHIVE_SHA256,
                  "frozen target HA archive mismatch")
        print(json.dumps({"artifact_id": TARGET[0], "target_ha_archive_verified": True,
                          "archive_size_bytes": member.file_size, "archive_sha256": TARGET_ARCHIVE_SHA256,
                          "image_id": identity["config_digest"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--ssh", metavar="VERIFIED_SPARE_T1_ALIAS")
    actions.add_argument("--verify-images", type=Path, metavar="MAC_DOWNLOAD_DIRECTORY")
    parser.add_argument("--candidate-bundle", action="store_true",
                        help="verify the compatible Manager and predecessor HA from the same ARM64 artifact")
    args = parser.parse_args()
    if args.candidate_bundle and args.verify_images is None:
        parser.error("--candidate-bundle requires --verify-images")
    if args.ssh is not None and not args.ssh.strip():
        parser.error("--ssh requires a non-empty spare T1 target")
    try:
        if args.ssh is not None:
            observe(args.ssh)
        else:
            verify_images(args.verify_images, candidate_bundle=args.candidate_bundle)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"R8 preparation stopped: {error}\n")


if __name__ == "__main__":
    main()
