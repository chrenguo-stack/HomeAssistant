from __future__ import annotations

import io
import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from greenhouse_manager.t1_backup import (
    BackupError,
    create_backup,
    restore_drill,
    verify_backup,
)


class FakeDocker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.calls.append(command)
        if command[:3] == ("docker", "inspect", "-f"):
            if command[3].startswith('{"image_id"'):
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
            return (0, "running\n")
        if command[:4] == (
            "docker",
            "exec",
            "greenhouse-manager",
            "sh",
        ):
            return (0, "absent\n")
        if command[:3] == ("docker", "cp", "--archive") and ":" in command[3]:
            destination = Path(command[4])
            destination.mkdir(parents=True)
            if "mosquitto:/mosquitto/config" in command[3]:
                (destination / "mosquitto.conf").write_text(
                    "listener 1883\nallow_anonymous true\n",
                    encoding="utf-8",
                )
            elif "mosquitto:/mosquitto/data" in command[3]:
                (destination / "mosquitto.db").write_bytes(b"test-state")
            return (0, "")
        if command[:2] == ("docker", "create"):
            return (0, "restore-container-id\n")
        if command[:2] in {
            ("docker", "start"),
            ("docker", "rm"),
        }:
            return (0, "")
        if command[:3] == ("docker", "cp", "--archive"):
            return (0, "")
        return (1, "unexpected")


def test_create_verify_and_isolated_restore_drill(tmp_path: Path) -> None:
    output = tmp_path / "private"
    output.mkdir(mode=0o700)
    docker = FakeDocker()

    archive = create_backup(
        output,
        runner=docker,
        now=datetime(2026, 7, 11, 17, 30, tzinfo=UTC),
    )
    manifest = verify_backup(archive)
    drill = restore_drill(
        archive,
        runner=docker,
        name_factory=lambda: "gh-m2-restore-test",
    )

    assert archive.stat().st_mode & 0o777 == 0o600
    assert manifest["classification"] == "sensitive-local-rollback"
    assert manifest["portable_off_host"] is False
    assert manifest["absent_optional_sources"] == [
        {
            "container": "greenhouse-manager",
            "path": "/var/lib/greenhouse-manager",
            "reason": "not_present",
        }
    ]
    assert all(
        {"mode", "uid", "gid"} <= record.keys()
        for record in manifest["files"]
    )
    assert drill["network"] == "none"
    assert drill["broker_started"] is True
    assert drill["current_services_modified"] is False
    commands = [" ".join(command) for command in docker.calls]
    assert not any("stop mosquitto" in command for command in commands)
    assert not any("restart mosquitto" in command for command in commands)
    assert any("docker create --network none" in command for command in commands)


def test_rejects_world_readable_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "public"
    output.mkdir(mode=0o755)

    with pytest.raises(BackupError, match="group or other"):
        create_backup(output, runner=FakeDocker())


def test_present_optional_source_must_copy_successfully(tmp_path: Path) -> None:
    class PresentButBrokenDocker(FakeDocker):
        def run(self, command: tuple[str, ...]) -> tuple[int, str]:
            if command[:4] == (
                "docker",
                "exec",
                "greenhouse-manager",
                "sh",
            ):
                return (0, "present\n")
            if (
                command[:3] == ("docker", "cp", "--archive")
                and "greenhouse-manager:" in command[3]
            ):
                return (1, "must remain redacted")
            return super().run(command)

    output = tmp_path / "private"
    output.mkdir(mode=0o700)

    with pytest.raises(BackupError, match="failed to copy required data"):
        create_backup(output, runner=PresentButBrokenDocker())


def test_detects_archive_tampering(tmp_path: Path) -> None:
    output = tmp_path / "private"
    output.mkdir(mode=0o700)
    archive = create_backup(output, runner=FakeDocker())
    tampered = output / "tampered.tar.gz"

    with tarfile.open(archive, "r:gz") as source, tarfile.open(
        tampered, "w:gz"
    ) as destination:
        for member in source.getmembers():
            stream = source.extractfile(member)
            assert stream is not None
            payload = stream.read()
            if member.name == "mosquitto-data/mosquitto.db":
                payload = b"tampered"
                member.size = len(payload)
            destination.addfile(member, io.BytesIO(payload))
    tampered.chmod(0o600)

    with pytest.raises(BackupError, match="checksum"):
        verify_backup(tampered)


def test_archive_does_not_expose_file_contents_in_manifest(tmp_path: Path) -> None:
    output = tmp_path / "private"
    output.mkdir(mode=0o700)

    manifest = verify_backup(create_backup(output, runner=FakeDocker()))
    serialized = json.dumps(manifest)

    assert "allow_anonymous true" not in serialized
    assert "test-state" not in serialized
