from __future__ import annotations

import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from greenhouse_manager.t1_backup import create_backup
from greenhouse_manager.t1_migration_package import (
    MigrationPackageError,
    create_migration_package,
    verify_migration_package,
)


class FakeDocker:
    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        if command[:3] == ("docker", "inspect", "-f"):
            name = command[-1]
            return (
                0,
                json.dumps(
                    {
                        "image_id": f"sha256:{name}",
                        "image_ref": f"test/{name}:latest",
                    }
                ),
            )
        if command[:4] == (
            "docker",
            "exec",
            "greenhouse-manager",
            "sh",
        ):
            return (0, "absent\n")
        if command[:3] == ("docker", "cp", "--archive"):
            destination = Path(command[4])
            destination.mkdir(parents=True)
            if "mosquitto:/mosquitto/config" in command[3]:
                (destination / "mosquitto.conf").write_text(
                    "listener 1883\nallow_anonymous true\n",
                    encoding="utf-8",
                )
            elif "mosquitto:/mosquitto/data" in command[3]:
                (destination / "mosquitto.db").write_bytes(b"retained-state")
            return (0, "")
        return (1, "unexpected")


class DeterministicBytes:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self, size: int) -> bytes:
        self.value += 1
        return bytes([self.value]) * size


def _rollback_archive(tmp_path: Path) -> Path:
    output = tmp_path / "rollback"
    output.mkdir(mode=0o700)
    return create_backup(
        output,
        runner=FakeDocker(),
        now=datetime(2026, 7, 11, 17, 55, 40, tzinfo=UTC),
    )


def test_builds_private_disabled_authenticated_migration_package(
    tmp_path: Path,
) -> None:
    rollback = _rollback_archive(tmp_path)
    output = tmp_path / "packages"
    output.mkdir(mode=0o700)

    package = create_migration_package(
        rollback,
        output,
        now=datetime(2026, 7, 12, 3, 0, tzinfo=UTC),
        random_bytes=DeterministicBytes(),
        token_factory=lambda: "deadbeef",
    )
    manifest = verify_migration_package(package)

    assert package.name == "greenhouse-t1-auth-migration-20260712T030000Z-deadbeef.tar.gz"
    assert package.stat().st_mode & 0o777 == 0o600
    assert manifest["schema"] == "gh.m2.t1-auth-migration/1"
    assert manifest["classification"] == "secret-local-migration"
    assert manifest["portable_off_host"] is False
    assert manifest["apply_enabled"] is False
    assert manifest["current_services_modified"] is False
    assert manifest["source_rollback"]["archive"] == rollback.name
    assert manifest["source_rollback"]["mosquitto_image_id"] == "sha256:mosquitto"
    assert [identity["label"] for identity in manifest["identities"]] == [
        "provisioning",
        "manager",
        "homeassistant",
        "node",
    ]
    assert len({identity["username"] for identity in manifest["identities"]}) == 4
    assert len({identity["client_id"] for identity in manifest["identities"]}) == 4

    with tarfile.open(package, "r:gz") as archive:
        members = archive.getmembers()
        assert all(member.isfile() for member in members)
        assert all(member.mode & 0o777 == 0o600 for member in members)
        contents = {}
        for member in members:
            stream = archive.extractfile(member)
            assert stream is not None
            contents[member.name] = stream.read().decode("utf-8")

    manager_password = contents["manager/password"].strip()
    bootstrap_password = contents["bootstrap/dynsec-password-init"].strip()
    ha_update = json.loads(contents["homeassistant/mqtt-update.json"])
    node_update = json.loads(contents["node/gh-n1-a9f2f8/mqtt-credentials.json"])
    dynsec_request = json.loads(contents["broker/dynsec-request.json"])
    create_clients = [
        command
        for command in dynsec_request["commands"]
        if command["command"] == "createClient"
    ]
    provisioned_passwords = {command["password"] for command in create_clients}

    assert len(create_clients) == 4
    assert len(provisioned_passwords) == 4
    assert manager_password in provisioned_passwords
    assert ha_update["password"] in provisioned_passwords
    assert node_update["password"] in provisioned_passwords
    assert bootstrap_password not in provisioned_passwords
    assert contents["manager/manager.env"].count("GH_MQTT_PASSWORD_FILE=") == 1
    assert manager_password not in contents["manager/manager.env"]
    assert "apply_enabled\":false" in contents["apply-plan.json"]
    assert "close_anonymous_access" in contents["apply-plan.json"]

    serialized_manifest = json.dumps(manifest, sort_keys=True)
    for password in provisioned_passwords | {bootstrap_password}:
        assert password not in serialized_manifest


def test_rejects_public_package_directory(tmp_path: Path) -> None:
    rollback = _rollback_archive(tmp_path)
    output = tmp_path / "public-packages"
    output.mkdir(mode=0o755)

    with pytest.raises(MigrationPackageError, match="group or other"):
        create_migration_package(rollback, output)


def test_rejects_duplicate_password_material(tmp_path: Path) -> None:
    rollback = _rollback_archive(tmp_path)
    output = tmp_path / "packages"
    output.mkdir(mode=0o700)

    with pytest.raises(MigrationPackageError, match="must be unique"):
        create_migration_package(
            rollback,
            output,
            random_bytes=lambda size: b"x" * size,
            token_factory=lambda: "deadbeef",
        )
