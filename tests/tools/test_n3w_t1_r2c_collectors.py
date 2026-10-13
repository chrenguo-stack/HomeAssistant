from __future__ import annotations

from pathlib import Path

from n3w_t1_r2c_collectors import collect_e1, collect_e4
from n3w_t1_r2c_readonly_commands import CommandResult


def _result(
    name: str,
    stdout: bytes = b"",
    *,
    returncode: int = 0,
    stderr: bytes = b"",
) -> CommandResult:
    return CommandResult(
        executable=f"/usr/bin/{name}",
        argv=(name,),
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _e1_runner(command_id: str, **_: object) -> CommandResult:
    responses = {
        "C1_SYSTEMD": _result("systemd", b"systemd 255 (255.4)\n"),
        "C1_ARCH": _result("uname", b"aarch64\n"),
        "C2_PYTHON": _result("python3", b"Python 3.11.9\n"),
        "C3_PACKAGES": _result(
            "dpkg-query",
            (
                b"systemd\t255.4\tarm64\n"
                b"openssh-server\t1:9.6p1\tarm64\n"
                b"network-manager\t1.46.0\tarm64\n"
                b"netplan.io\t1.0\tarm64\n"
            ),
        ),
    }
    return responses[command_id]


def _mount_not_present_runner(command_id: str, **_: object) -> CommandResult:
    assert command_id == "C5_MACHINE_ID_MOUNT"
    return _result("findmnt", returncode=1)


def _write_platform_fixture(root: Path) -> None:
    (root / "etc").mkdir(parents=True)
    (root / "etc" / "os-release").write_text(
        "ID=ubuntu\n"
        'PRETTY_NAME="Armbian OS test"\n'
        "VERSION_ID=26.04\n"
        "VERSION_CODENAME=resolute\n"
    )
    (root / "etc" / "armbian-release").write_text(
        "BOARD=S912-Phicomm-T1\n"
        "BOARD_NAME=Aml.S912\n"
        "VERSION=26.05.0\n"
        "BRANCH=current\n"
        "ARCH=arm64\n"
        "IMAGE_TYPE=rebuild\n"
    )


def test_collect_e1_observes_exact_platform_fields(tmp_path: Path) -> None:
    _write_platform_fixture(tmp_path)
    evidence = collect_e1(str(tmp_path), runner=_e1_runner)
    assert evidence["status"] == "OBSERVED"
    assert evidence["complete"] is True
    assert evidence["reason_code"] is None
    assert evidence["method_ids"] == ["R1", "R2", "C1", "C2", "C3"]
    assert evidence["fields"]["os_release"]["value"]["ID"] == "ubuntu"
    assert evidence["fields"]["armbian_release"]["value"]["ARCH"] == "arm64"
    assert evidence["fields"]["architecture"]["value"] == "aarch64"
    assert evidence["fields"]["systemd_version"]["value"] == "systemd 255 (255.4)"
    assert evidence["fields"]["package_versions"]["value"]["systemd"] == {
        "version": "255.4",
        "architecture": "arm64",
    }


def test_collect_e1_missing_release_is_incomplete_not_false_pass(tmp_path: Path) -> None:
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc" / "armbian-release").write_text("ARCH=arm64\n")
    evidence = collect_e1(str(tmp_path), runner=_e1_runner)
    assert evidence["status"] == "UNKNOWN"
    assert evidence["complete"] is False
    assert evidence["reason_code"] == "STOP_EVIDENCE_GAP"
    assert evidence["fields"]["os_release"]["status"] == "ABSENT"


def test_collect_e4_compares_machine_ids_without_returning_contents(
    tmp_path: Path,
) -> None:
    (tmp_path / "etc").mkdir()
    (tmp_path / "var" / "lib" / "dbus").mkdir(parents=True)
    value = ("a" * 32) + "\n"
    (tmp_path / "etc" / "machine-id").write_text(value)
    (tmp_path / "var" / "lib" / "dbus" / "machine-id").write_text(value)

    evidence = collect_e4(str(tmp_path), runner=_mount_not_present_runner)
    assert evidence["status"] == "UNKNOWN"
    assert evidence["complete"] is False
    assert evidence["reason_code"] == "STOP_SEMANTICS_GAP"
    assert evidence["fields"]["contents_equal"] == {
        "value": True,
        "status": "OBSERVED",
    }
    rendered = repr(evidence)
    assert "a" * 32 not in rendered
    assert (
        evidence["fields"]["etc_machine_id"]["value"]["content_class"]
        == "VALID_HEX32"
    )
    assert evidence["fields"]["mount_relation"]["value"]["is_mountpoint"] is False


def test_collect_e4_classifies_dbus_symlink_without_following(
    tmp_path: Path,
) -> None:
    (tmp_path / "etc").mkdir()
    (tmp_path / "var" / "lib" / "dbus").mkdir(parents=True)
    (tmp_path / "etc" / "machine-id").write_text("uninitialized\n")
    (tmp_path / "var" / "lib" / "dbus" / "machine-id").symlink_to(
        "../../../etc/machine-id"
    )

    evidence = collect_e4(str(tmp_path), runner=_mount_not_present_runner)
    relation = evidence["fields"]["path_relation"]["value"]
    assert relation["dbus_kind"] == "symlink"
    assert relation["dbus_points_to_etc"] is True
    assert evidence["fields"]["contents_equal"]["status"] == "UNKNOWN"
    assert "uninitialized" not in repr(evidence)


def test_collect_e1_stops_on_target_drift(tmp_path: Path) -> None:
    _write_platform_fixture(tmp_path)
    (tmp_path / "etc" / "armbian-release").write_text(
        "BOARD=UNEXPECTED-BOARD\n"
        "BOARD_NAME=Aml.S912\n"
        "VERSION=26.05.0\n"
        "BRANCH=current\n"
        "ARCH=arm64\n"
        "IMAGE_TYPE=rebuild\n"
    )
    evidence = collect_e1(str(tmp_path), runner=_e1_runner)
    assert evidence["status"] == "ERROR"
    assert evidence["complete"] is False
    assert evidence["reason_code"] == "STOP_TARGET_DRIFT"


def test_collect_e4_marks_missing_machine_id_as_absent(tmp_path: Path) -> None:
    (tmp_path / "etc").mkdir()
    (tmp_path / "var" / "lib" / "dbus").mkdir(parents=True)
    evidence = collect_e4(str(tmp_path), runner=_mount_not_present_runner)
    assert evidence["fields"]["etc_machine_id"]["status"] == "ABSENT"
    assert evidence["fields"]["dbus_machine_id"]["status"] == "ABSENT"
    assert evidence["fields"]["contents_equal"]["status"] == "UNKNOWN"


def test_collect_e1_observed_conflict_is_drift_even_with_other_gaps(
    tmp_path: Path,
) -> None:
    (tmp_path / "etc").mkdir()
    (tmp_path / "etc" / "os-release").write_text("ID=ubuntu\n")
    (tmp_path / "etc" / "armbian-release").write_text("ARCH=amd64\n")
    evidence = collect_e1(str(tmp_path), runner=_e1_runner)
    assert evidence["status"] == "ERROR"
    assert evidence["complete"] is False
    assert evidence["reason_code"] == "STOP_TARGET_DRIFT"
