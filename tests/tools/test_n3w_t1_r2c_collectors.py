from __future__ import annotations

import gzip
from pathlib import Path

from n3w_t1_r2c_collectors import collect_e1, collect_e2, collect_e3, collect_e4
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
    if command_id == "C5_MACHINE_ID_MOUNT":
        return _result("findmnt", returncode=1)
    if command_id == "C4_UNIT":
        return _result("systemctl", b"LoadState=not-found\n")
    if command_id == "C3_LIST":
        return _result("dpkg-query", b"")
    raise AssertionError(command_id)


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


def _e4_complete_runner(command_id: str, **kwargs: object) -> CommandResult:
    if command_id == "C5_MACHINE_ID_MOUNT":
        return _result("findmnt", returncode=1)
    if command_id == "C3_LIST":
        return _result(
            "dpkg-query",
            b"/usr/share/man/man5/machine-id.5.gz\n",
        )
    if command_id == "C4_UNIT":
        unit = str(kwargs["value"])
        return _result(
            "systemctl",
            (
                f"Id={unit}\n"
                "LoadState=loaded\n"
                f"FragmentPath=/usr/lib/systemd/system/{unit}\n"
                "DropInPaths=\n"
                "UnitFileState=static\n"
                "ActiveState=inactive\n"
                "SubState=dead\n"
                "Before=network.target\n"
                "After=local-fs.target\n"
                "Wants=\n"
                "Requires=\n"
                "ConditionResult=yes\n"
                "Conditions=[ConditionFirstBoot=|yes]\n"
                "ExecStart=/usr/lib/systemd/systemd-test\n"
                "ExecStartPre=\n"
                "ExecStartPost=\n"
                "TriggeredBy=\n"
                "Triggers=\n"
                "ActiveEnterTimestampMonotonic=0\n"
                "InactiveExitTimestampMonotonic=0\n"
            ).encode(),
        )
    raise AssertionError(command_id)


def test_collect_e4_captures_units_and_installed_machine_id_manual(
    tmp_path: Path,
) -> None:
    (tmp_path / "etc").mkdir()
    (tmp_path / "var" / "lib" / "dbus").mkdir(parents=True)
    value = ("c" * 32) + "\n"
    (tmp_path / "etc" / "machine-id").write_text(value)
    (tmp_path / "var" / "lib" / "dbus" / "machine-id").write_text(value)

    units = tmp_path / "usr" / "lib" / "systemd" / "system"
    units.mkdir(parents=True)
    for name in (
        "systemd-machine-id-commit.service",
        "systemd-firstboot.service",
    ):
        (units / name).write_text("[Unit]\nConditionFirstBoot=yes\n")

    manual = tmp_path / "usr" / "share" / "man" / "man5"
    manual.mkdir(parents=True)
    manual_text = (
        "machine-id uses /etc/machine-id. "
        "The uninitialized state is handled on first boot. "
        "A fallback may use /run/machine-id."
    ).encode()
    (manual / "machine-id.5.gz").write_bytes(gzip.compress(manual_text))

    evidence = collect_e4(str(tmp_path), runner=_e4_complete_runner)

    assert evidence["status"] == "OBSERVED"
    assert evidence["complete"] is True
    assert evidence["reason_code"] is None
    assert evidence["method_ids"] == ["R1", "C3", "C4", "C5"]
    assert evidence["fields"]["boot_condition_contract"]["status"] == "OBSERVED"
    assert evidence["fields"]["fallback_sources"]["status"] == "OBSERVED"
    sources = evidence["fields"]["fallback_sources"]["value"]["sources"]
    assert sources[0]["role"] == "machine-id.5"
    assert sources[0]["markers"]["run_machine_id"] is True


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



def _owner_runner(command_id: str, **_: object) -> CommandResult:
    assert command_id == "C3_OWNER"
    return _result("dpkg-query", b"armbian-bsp: /usr/lib/armbian/armbian-firstrun\n")


def _write_firstrun_fixture(root: Path) -> None:
    main = root / "usr" / "lib" / "armbian" / "armbian-firstrun"
    helper = root / "usr" / "lib" / "armbian" / "helper-identity.sh"
    config = root / "etc" / "default" / "armbian-firstrun"
    main.parent.mkdir(parents=True)
    config.parent.mkdir(parents=True)
    main.write_text(
        "#!/bin/sh\n"
        "source /etc/default/armbian-firstrun\n"
        'if [ "${SET_HOSTNAME}" = "yes" ]; then\n'
        '  hostnamectl set-hostname "${TARGET_HOSTNAME}"\n'
        "fi\n"
        "source /usr/lib/armbian/helper-identity.sh\n"
    )
    helper.write_text(
        'if [ "${SSH_HOST_KEY_REGENERATE}" = "yes" ]; then\n'
        "  ssh-keygen -A\n"
        "fi\n"
    )
    config.write_text(
        "SET_HOSTNAME=yes\n"
        "TARGET_HOSTNAME=custom-value\n"
        "SSH_HOST_KEY_REGENERATE=no\n"
    )


def test_collect_e2_closes_static_source_and_owner_binding(tmp_path: Path) -> None:
    _write_firstrun_fixture(tmp_path)
    evidence = collect_e2(str(tmp_path), runner=_owner_runner)
    assert evidence["status"] == "OBSERVED"
    assert evidence["complete"] is True
    assert evidence["reason_code"] is None
    assert evidence["fields"]["firstrun_body_complete"]["value"] is True
    assert len(evidence["fields"]["body_sha256"]["value"]) == 64
    assert evidence["provenance"] == [
        {
            "file_role": "armbian_firstrun",
            "package_owner": "BOUND",
        }
    ]


def test_collect_e2_dynamic_source_stays_unresolved(tmp_path: Path) -> None:
    main = tmp_path / "usr" / "lib" / "armbian" / "armbian-firstrun"
    main.parent.mkdir(parents=True)
    main.write_text(
        "#!/bin/sh\n"
        'source "${HELPER_PATH}"\n'
        "hostnamectl set-hostname static-placeholder\n"
    )
    evidence = collect_e2(str(tmp_path), runner=_owner_runner)
    assert evidence["status"] == "UNKNOWN"
    assert evidence["complete"] is False
    assert evidence["reason_code"] == "STOP_UNRESOLVED_IMPLEMENTATION"


def test_collect_e3_reports_classes_not_config_values(tmp_path: Path) -> None:
    _write_firstrun_fixture(tmp_path)
    evidence = collect_e3(str(tmp_path))
    assert evidence["status"] == "OBSERVED"
    assert evidence["complete"] is True
    classes = evidence["fields"]["identity_setting_classes"]["value"]
    assert classes == {
        "SET_HOSTNAME": "BOOLEAN",
        "SSH_HOST_KEY_REGENERATE": "BOOLEAN",
        "TARGET_HOSTNAME": "CUSTOM",
    }
    assert "custom-value" not in repr(evidence)


def test_collect_e3_dynamic_config_stays_unresolved(tmp_path: Path) -> None:
    _write_firstrun_fixture(tmp_path)
    config = tmp_path / "etc" / "default" / "armbian-firstrun"
    config.write_text(
        "SET_HOSTNAME=yes\n"
        "TARGET_HOSTNAME=$(hostname)\n"
        "SSH_HOST_KEY_REGENERATE=no\n"
    )
    evidence = collect_e3(str(tmp_path))
    assert evidence["status"] == "UNKNOWN"
    assert evidence["complete"] is False
    assert evidence["reason_code"] == "STOP_CONFIG_UNRESOLVED"
    assert (
        evidence["fields"]["identity_setting_classes"]["status"]
        == "UNKNOWN"
    )



def test_collect_e3_does_not_complete_when_source_closure_is_unresolved(
    tmp_path: Path,
) -> None:
    _write_firstrun_fixture(tmp_path)
    main = tmp_path / "usr" / "lib" / "armbian" / "armbian-firstrun"
    main.write_text(
        "#!/bin/sh\n"
        "source /etc/default/armbian-firstrun\n"
        'if [ "${SET_HOSTNAME}" = "yes" ]; then\n'
        '  hostnamectl set-hostname "${TARGET_HOSTNAME}"\n'
        "fi\n"
        'source "${HELPER_PATH}"\n'
    )
    evidence = collect_e3(str(tmp_path))
    assert evidence["status"] == "UNKNOWN"
    assert evidence["complete"] is False
    assert evidence["reason_code"] == "STOP_CONFIG_UNRESOLVED"
