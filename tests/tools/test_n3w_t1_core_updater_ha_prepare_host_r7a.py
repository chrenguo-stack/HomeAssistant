from __future__ import annotations

import copy
import inspect
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import n3w_t1_core_updater_ha_daemon as daemon
import n3w_t1_core_updater_ha_capacity as capacity
import n3w_t1_core_updater_ha_prepare_host as host
from n3w_t1_core_updater_ha_prepare import HostUsbCandidate, PreparedUsbMedia
from n3w_t1_core_updater_v2_common import UpdaterV2Error

FINGERPRINT = "a" * 64
UUID = "12345678-1234-5678-1234-567812345678"


def completed(stdout: bytes = b"", returncode: int = 0) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(
        args=(),
        returncode=returncode,
        stdout=stdout,
        stderr=b"",
    )


def test_policy_v2_computes_dynamic_backup_above_eight_gib() -> None:
    policy = host.HostReleasePolicy(
        release_identity="homeassistant-2026.10.4",
        artifact_url=(
            "https://ota.hahub.top/n3w/homeassistant/releases/"
            "homeassistant-2026.10.4/homeassistant-arm64.tar.gz"
        ),
        target_archive_sha256="1" * 64,
        target_archive_size_bytes=1 * 1024**3,
        expected_predecessor_image_ref=(
            "local/n3w-homeassistant:2026.10.0-0c73235a"
        ),
        predecessor_recovery_budget_bytes=2 * 1024**3,
        capacity_policy=capacity.CapacityPolicy.frozen(),
    )
    assert policy.validate() is policy
    breakdown = policy.capacity_breakdown(12 * 1024**3)
    assert breakdown.ha_data_backup_budget_bytes == 15 * 1024**3
    assert breakdown.usb_required_bytes > breakdown.ha_data_backup_budget_bytes


def test_inventory_ignores_irrelevant_internal_disk_without_serial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lsblk = {
        "blockdevices": [
            {
                "path": "/dev/mmcblk0",
                "type": "disk",
                "rm": False,
                "ro": False,
                "size": 16 * 1024**3,
                "model": "Internal",
                "serial": None,
                "wwn": None,
                "tran": "",
                "mountpoints": [None],
                "maj:min": "179:0",
                "children": [
                    {
                        "path": "/dev/mmcblk0p1",
                        "type": "part",
                        "mountpoints": ["/"],
                        "maj:min": "179:1",
                    }
                ],
            },
            {
                "path": "/dev/sdz",
                "type": "disk",
                "rm": True,
                "ro": False,
                "size": 16 * 1024**3,
                "model": "Synthetic USB",
                "serial": "SERIAL-1",
                "wwn": None,
                "tran": "usb",
                "mountpoints": [None],
                "maj:min": "8:240",
            },
        ]
    }

    def fake_run(argv, **_kwargs):
        if argv[0] == "findmnt":
            return completed(b"179:1\n")
        if argv[0] == "lsblk":
            return completed(json.dumps(lsblk).encode())
        raise AssertionError(argv)

    monkeypatch.setattr(host.subprocess, "run", fake_run)
    candidates = host.SubprocessPrepareBackend().inventory()

    assert len(candidates) == 1
    assert candidates[0].locator == "/dev/sdz"
    assert candidates[0].public_fingerprint


def test_relevant_usb_without_stable_identity_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lsblk = {
        "blockdevices": [
            {
                "path": "/dev/sdz",
                "type": "disk",
                "rm": True,
                "ro": False,
                "size": 16 * 1024**3,
                "model": "Anonymous USB",
                "serial": None,
                "wwn": None,
                "tran": "usb",
                "mountpoints": [None],
                "maj:min": "8:240",
            }
        ]
    }

    def fake_run(argv, **_kwargs):
        if argv[0] == "findmnt":
            return completed(b"179:1\n")
        if argv[0] == "lsblk":
            return completed(json.dumps(lsblk).encode())
        raise AssertionError(argv)

    monkeypatch.setattr(host.subprocess, "run", fake_run)
    with pytest.raises(UpdaterV2Error, match="usb_stable_identity_unavailable"):
        host.SubprocessPrepareBackend().inventory()


def test_format_backend_uses_fixed_argv_without_shell(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    backend = host.SubprocessPrepareBackend(runtime_root=runtime)
    candidate = HostUsbCandidate(
        locator="/dev/sdz",
        public_fingerprint=FINGERPRINT,
        display_model="Synthetic USB",
        display_capacity_bytes=16 * 1024**3,
    )
    monkeypatch.setattr(backend, "_same_candidate", lambda value: value)
    calls: list[tuple[str, ...]] = []

    def fake_run(argv, *, input_bytes=None, timeout=30):
        calls.append(tuple(argv))
        if argv[0] == "lsblk":
            return json.dumps(
                {
                    "blockdevices": [
                        {
                            "path": "/dev/sdz",
                            "type": "disk",
                            "pkname": None,
                            "children": [
                                {
                                    "path": "/dev/sdz1",
                                    "type": "part",
                                    "pkname": "/dev/sdz",
                                }
                            ],
                        }
                    ]
                }
            ).encode()
        if argv[0] == "blkid":
            return (UUID + "\n").encode()
        return b""

    monkeypatch.setattr(host, "_run", fake_run)
    monkeypatch.setattr(
        host.os,
        "statvfs",
        lambda _path: SimpleNamespace(f_bavail=16 * 1024**3, f_frsize=1),
    )

    media = backend.format_and_mount(
        candidate=candidate,
        transaction_id_sha256="b" * 64,
    )

    assert media.locator == "/dev/sdz"
    assert media.filesystem_uuid == UUID
    assert ("wipefs", "--all", "--force", "/dev/sdz") in calls
    assert ("mkfs.ext4", "-F", "-L", "N3W-UPDATE", "/dev/sdz1") in calls
    assert all(isinstance(call, tuple) for call in calls)


class FakePolicyProvider:
    def load(self, _transaction):
        return host.HostReleasePolicy(
            release_identity="homeassistant-2026.10.4",
            artifact_url=(
                "https://ota.hahub.top/n3w/homeassistant/releases/"
                "homeassistant-2026.10.4/homeassistant-arm64.tar.gz"
            ),
            target_archive_sha256="1" * 64,
            target_archive_size_bytes=1024,
            expected_predecessor_image_ref=(
                "local/n3w-homeassistant:2026.10.0-0c73235a"
            ),
            predecessor_recovery_budget_bytes=1024,
            capacity_policy=capacity.CapacityPolicy.frozen(),
        )


class FakeResponse:
    headers = {"Content-Length": "1024"}

    def geturl(self):
        return "http://downgrade.example.invalid/ha.tar.gz"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _size):
        return b""




def test_stale_target_temporaries_are_cleaned_without_touching_final_target(
    tmp_path: Path,
) -> None:
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    stale_a = target_dir / ".homeassistant-target.crash-a"
    stale_b = target_dir / ".homeassistant-target.crash-b"
    final = target_dir / "homeassistant-arm64.tar.gz"
    unrelated = target_dir / "keep.txt"
    stale_a.write_bytes(b"a")
    stale_b.write_bytes(b"b")
    final.write_bytes(b"final")
    unrelated.write_bytes(b"keep")

    host.SubprocessPrepareBackend._cleanup_stale_target_temporaries(target_dir)

    assert not stale_a.exists()
    assert not stale_b.exists()
    assert final.read_bytes() == b"final"
    assert unrelated.read_bytes() == b"keep"


def test_stale_target_temporary_cleanup_fails_closed_on_symlink(
    tmp_path: Path,
) -> None:
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")
    link = target_dir / ".homeassistant-target.link"
    link.symlink_to(outside)

    with pytest.raises(UpdaterV2Error, match="ha_target_temporary_invalid"):
        host.SubprocessPrepareBackend._cleanup_stale_target_temporaries(target_dir)

    assert outside.read_bytes() == b"outside"

def test_target_download_rejects_https_to_http_redirect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mount = tmp_path / "media"
    mount.mkdir(mode=0o700)
    media = PreparedUsbMedia(
        locator="/dev/sdz",
        public_fingerprint=FINGERPRINT,
        filesystem_uuid=UUID,
        measured_usable_bytes=16 * 1024**3,
        mount_path=str(mount),
    )
    backend = host.SubprocessPrepareBackend(
        policy_provider=FakePolicyProvider(),
        runtime_root=tmp_path,
    )
    monkeypatch.setattr(backend, "_require_bound_media", lambda _media: "/dev/sdz1")
    monkeypatch.setattr(host.urllib.request, "urlopen", lambda *_a, **_k: FakeResponse())

    transaction = {
        "target_image_ref": "local/n3w-homeassistant:2026.10.4-bbbbbbbb",
        "target_manifest_identity": {
            "release_identity": "homeassistant-2026.10.4",
        },
        "target_archive_sha256": "1" * 64,
        "target_archive_size": 1024,
    }

    with pytest.raises(UpdaterV2Error, match="ha_target_download_redirect_invalid"):
        backend.prepare_target(transaction=transaction, media=media)


def test_inactive_activation_assets_preserve_privilege_boundary() -> None:
    root = Path(__file__).resolve().parents[2]
    unit = (
        root / "infra/n3w-t1/systemd/n3w-t1-ha-ota.service"
    ).read_text(encoding="utf-8")
    dropin = (
        root
        / "infra/n3w-t1/systemd/n3wfc4-services-activation.ha-ota.conf"
    ).read_text(encoding="utf-8")
    override = (
        root / "infra/n3w-t1/production/docker-compose.ha-ota.yml"
    ).read_text(encoding="utf-8")

    assert "User=root" in unit
    assert "Group=999" in unit
    assert "RuntimeDirectory=n3w-t1-ota" in unit
    assert "RuntimeDirectoryMode=0750" in unit
    assert "systemctl" not in unit
    assert "GH_N3W_T1_OTA_ENABLED" in override
    assert ":-false" in override
    assert '${GH_N3W_T1_OTA_INSTALLED_VERSION:-}' in override
    assert ":?GH_N3W_T1_OTA_INSTALLED_VERSION" not in override
    assert "source: /run/n3w-t1-ota" in override
    assert "target: /run/n3w/t1-ota" in override
    assert "read_only: true" in override
    assert "/var/run/docker.sock" not in override
    assert "/dev/" not in override
    assert "Requires=n3w-t1-ha-ota.service" in dropin
    assert "After=n3w-t1-ha-ota.service" in dropin
    assert "[Service]" in dropin
    assert "EnvironmentFile=-/etc/n3wfc4/ha-ota-activation.env" in dropin
    assert "2026.10.0" not in dropin
    assert "ExecStart=\nExecStart=/usr/bin/docker compose " in dropin
    assert "ExecStop=\nExecStop=/usr/bin/docker compose " in dropin
    overlay_path = (
        "-f /opt/HomeAssistant/infra/n3w-t1/production/"
        "docker-compose.ha-ota.yml"
    )
    assert dropin.count(overlay_path) == 2
    assert "--abort-on-container-exit manager homeassistant" in dropin
    assert "stop homeassistant manager" in dropin


def test_daemon_requires_root_and_manager_group_contract_in_source() -> None:
    source = inspect.getsource(daemon.build_server)
    assert "os.geteuid() != 0" in source
    assert "os.getegid() != EXPECTED_MANAGER_GID" in source
    assert "stat.S_IMODE(metadata.st_mode) != 0o750" in source
    assert "expected_peer_uid=EXPECTED_MANAGER_UID" in source
    assert "mode=0o660" in source


def approved_manifest_vector() -> dict:
    root = Path(__file__).resolve().parents[2]
    return json.loads(
        (
            root
            / "infra/n3w-t1/upgrades/homeassistant-2026.10.4-approved.json"
        ).read_text(encoding="utf-8")
    )


def test_production_approved_manifest_binds_exact_frozen_target() -> None:
    root = Path(__file__).resolve().parents[2]
    document = approved_manifest_vector()
    target = json.loads(
        (
            root / "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json"
        ).read_text(encoding="utf-8")
    )

    assert set(document) == {
        "schema",
        "approval_status",
        "signature_status",
        "validity_status",
        "verification_status",
        "version",
        "release_identity",
        "target_archive_size_bytes",
        "target",
    }
    assert document["schema"] == "gh.n3w-t1-ota-approved-manifest/1"
    assert document["approval_status"] == "APPROVED"
    assert document["signature_status"] == "VERIFIED"
    assert document["validity_status"] == "VALID"
    assert document["verification_status"] == "PASS"
    assert document["version"] == "2026.10.4"
    assert document["release_identity"] == "homeassistant-2026.10.4"
    assert document["target_archive_size_bytes"] == 835309535
    assert document["target"] == target


def test_privileged_manifest_accepts_exact_frozen_vector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = approved_manifest_vector()
    monkeypatch.setattr(
        daemon,
        "_root_owned_manifest",
        lambda _path: copy.deepcopy(document),
    )

    validated = daemon._validated_manifest(Path("/ignored"))
    assert validated == document


@pytest.mark.parametrize(
    ("mutator", "reason"),
    (
        (
            lambda document: document["target"].__setitem__(
                "a1_classification_sha256",
                "0" * 64,
            ),
            "ha_ota_target_a1_authority_mismatch",
        ),
        (
            lambda document: document["target"]["compatibility_evidence"].__setitem__(
                "peer_contracts_compatible",
                False,
            ),
            "ha_ota_target_compatibility_invalid",
        ),
        (
            lambda document: document.__setitem__("version", "2026.10.5"),
            "ha_ota_target_image_invalid",
        ),
    ),
)
def test_privileged_manifest_rejects_weakened_authority(
    monkeypatch: pytest.MonkeyPatch,
    mutator,
    reason: str,
) -> None:
    document = approved_manifest_vector()
    mutator(document)
    monkeypatch.setattr(
        daemon,
        "_root_owned_manifest",
        lambda _path: copy.deepcopy(document),
    )

    with pytest.raises(UpdaterV2Error, match=reason):
        daemon._validated_manifest(Path("/ignored"))


def test_privileged_json_parsers_reject_duplicate_fields() -> None:
    with pytest.raises(
        UpdaterV2Error,
        match="ha_prepare_json_duplicate_field",
    ):
        json.loads(
            '{"schema":"a","schema":"b"}',
            object_pairs_hook=host._reject_duplicate_object,
        )
    with pytest.raises(
        UpdaterV2Error,
        match="ha_ota_approved_manifest_duplicate_field",
    ):
        json.loads(
            '{"schema":"a","schema":"b"}',
            object_pairs_hook=daemon._reject_duplicate_object,
        )


def test_usb_fingerprint_binds_both_serial_and_wwn() -> None:
    first = {
        "serial": "SERIAL-1",
        "wwn": "WWN-1",
        "model": "Synthetic USB",
        "size": 16 * 1024**3,
        "tran": "usb",
    }
    second = dict(first)
    second["wwn"] = "WWN-2"

    assert host._stable_fingerprint(first) != host._stable_fingerprint(second)


class BadShaResponse:
    headers = {"Content-Length": "1024"}

    def __init__(self) -> None:
        self.sent = False

    def geturl(self):
        return "https://updates.example.invalid/ha.tar.gz"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _size):
        if self.sent:
            return b""
        self.sent = True
        return b"x" * 1024


def test_target_download_sha_mismatch_never_reaches_archive_parser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mount = tmp_path / "media-sha"
    mount.mkdir(mode=0o700)
    media = PreparedUsbMedia(
        locator="/dev/sdz",
        public_fingerprint=FINGERPRINT,
        filesystem_uuid=UUID,
        measured_usable_bytes=16 * 1024**3,
        mount_path=str(mount),
    )
    backend = host.SubprocessPrepareBackend(
        policy_provider=FakePolicyProvider(),
        runtime_root=tmp_path,
    )
    monkeypatch.setattr(
        backend,
        "_require_bound_media",
        lambda _media: "/dev/sdz1",
    )
    monkeypatch.setattr(
        host.urllib.request,
        "urlopen",
        lambda *_a, **_k: BadShaResponse(),
    )
    monkeypatch.setattr(
        host.portable,
        "parse_image_archive",
        lambda *_a, **_k: pytest.fail("archive parser must not run"),
    )

    transaction = {
        "target_image_ref": "local/n3w-homeassistant:2026.10.4-bbbbbbbb",
        "target_manifest_identity": {
            "release_identity": "homeassistant-2026.10.4",
        },
        "target_archive_sha256": "1" * 64,
        "target_archive_size": 1024,
    }

    with pytest.raises(
        UpdaterV2Error,
        match="ha_target_download_identity_mismatch",
    ):
        backend.prepare_target(transaction=transaction, media=media)


def test_missing_approved_release_keeps_daemon_publish_path_nonfatal(
    tmp_path: Path,
) -> None:
    source = tmp_path / "missing-approved.json"
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    destination = runtime / "approved-homeassistant.json"
    destination.write_text("stale", encoding="utf-8")

    assert (
        daemon.publish_manager_manifest(
            source=source,
            destination=destination,
        )
        is False
    )
    assert not destination.exists()
