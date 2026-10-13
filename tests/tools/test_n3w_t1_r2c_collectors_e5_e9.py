from __future__ import annotations

from pathlib import Path

from n3w_t1_r2c_collectors_e5_e9 import (
    E6_UNITS,
    E7_UNITS,
    collect_e5,
    collect_e6,
    collect_e7,
    collect_e8,
    collect_e9,
)
from n3w_t1_r2c_readonly_commands import CommandResult


def _result(
    name: str,
    stdout: bytes = b"",
    *,
    returncode: int = 0,
) -> CommandResult:
    return CommandResult(
        executable=f"/usr/bin/{name}",
        argv=(name,),
        returncode=returncode,
        stdout=stdout,
        stderr=b"",
    )


def _write_unit(root: Path, unit: str) -> str:
    path = (
        root
        / "usr"
        / "lib"
        / "systemd"
        / "system"
        / unit
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"[Unit]\nDescription={unit}\n"
    )
    return "/" + path.relative_to(root).as_posix()


def _runner(
    root: Path,
    *,
    loaded: dict[str, dict[str, str]] | None = None,
):
    loaded = loaded or {}
    fragment_paths = {
        unit: _write_unit(root, unit)
        for unit in loaded
    }

    def run(
        command_id: str,
        **kwargs: object,
    ) -> CommandResult:
        if command_id == "C4_UNIT":
            unit = str(kwargs["value"])
            if unit not in loaded:
                return _result(
                    "systemctl",
                    (
                        f"Id={unit}\n"
                        "LoadState=not-found\n"
                    ).encode(),
                )
            spec = loaded[unit]
            body = {
                "Id": unit,
                "Names": unit,
                "LoadState": "loaded",
                "FragmentPath": fragment_paths[unit],
                "DropInPaths": "",
                "UnitFileState": spec.get(
                    "unit_file_state",
                    "enabled",
                ),
                "ActiveState": spec.get(
                    "active_state",
                    "active",
                ),
                "SubState": spec.get(
                    "sub_state",
                    "running",
                ),
                "Before": spec.get("before", ""),
                "After": spec.get("after", ""),
                "Wants": spec.get("wants", ""),
                "Requires": spec.get("requires", ""),
                "ConditionResult": spec.get(
                    "condition_result",
                    "yes",
                ),
                "Conditions": spec.get(
                    "conditions",
                    "",
                ),
                "ExecStart": spec.get(
                    "exec_start",
                    "/usr/bin/true",
                ),
                "ExecStartPre": "",
                "ExecStartPost": "",
                "TriggeredBy": spec.get(
                    "triggered_by",
                    "",
                ),
                "Triggers": spec.get(
                    "triggers",
                    "",
                ),
                "ActiveEnterTimestampMonotonic": (
                    spec.get("active_enter", "100")
                ),
                "InactiveExitTimestampMonotonic": (
                    spec.get("inactive_exit", "50")
                ),
            }
            return _result(
                "systemctl",
                (
                    "\n".join(
                        f"{key}={value}"
                        for key, value in body.items()
                    )
                    + "\n"
                ).encode(),
            )
        if command_id == "C3_OWNER":
            return _result(
                "dpkg-query",
                (
                    b"openssh-client: "
                    b"/usr/bin/ssh-keygen\n"
                ),
            )
        if command_id == "C3_LIST":
            return _result(
                "dpkg-query",
                (
                    b"/usr/lib/systemd/system/"
                    b"systemd-random-seed.service\n"
                    b"/var/lib/systemd/random-seed\n"
                ),
            )
        if command_id == "C6_LISTEN":
            return _result(
                "ss",
                (
                    b"LISTEN 0 128 "
                    b"0.0.0.0:22 0.0.0.0:*\n"
                    b"LISTEN 0 128 "
                    b"[::]:22 [::]:*\n"
                ),
            )
        raise AssertionError(command_id)

    return run


def _ssh_fixture(root: Path) -> None:
    ssh = root / "etc" / "ssh"
    (ssh / "sshd_config.d").mkdir(parents=True)
    (ssh / "sshd_config").write_text(
        "Include /etc/ssh/sshd_config.d/*.conf\n"
        "HostKey /etc/ssh/ssh_host_ecdsa_key\n"
        "HostKey /etc/ssh/ssh_host_ed25519_key\n"
        "HostKey /etc/ssh/ssh_host_rsa_key\n"
    )
    (
        ssh
        / "sshd_config.d"
        / "10-default.conf"
    ).write_text("Port 22\n")
    for name in (
        "ssh_host_ecdsa_key",
        "ssh_host_ed25519_key",
        "ssh_host_rsa_key",
    ):
        path = ssh / name
        path.write_text(
            f"PRIVATE-SENTINEL-{name}\n"
        )
        path.chmod(0o600)


def test_e5_collects_metadata_without_private_key_body(
    tmp_path: Path,
) -> None:
    _ssh_fixture(tmp_path)
    loaded = {
        "sshd-keygen.service": {
            "conditions": (
                "ConditionFirstBoot=yes "
                "ConditionPathIsReadWrite=/etc/ssh "
                "ConditionPathIsSymbolicLink=!/etc/ssh"
            ),
            "exec_start": "/usr/bin/ssh-keygen -A",
            "before": "ssh.service ssh.socket",
        },
        "ssh.service": {
            "after": "sshd-keygen.service"
        },
        "ssh.socket": {
            "after": "sshd-keygen.service"
        },
    }
    evidence = collect_e5(
        tmp_path.as_posix(),
        runner=_runner(
            tmp_path,
            loaded=loaded,
        ),
    )
    assert evidence["status"] == "OBSERVED"
    assert evidence["complete"] is True
    assert evidence["fields"]["key_families"]["value"] == [
        "ECDSA",
        "ED25519",
        "RSA",
    ]
    conditions = evidence["fields"][
        "keygen_conditions"
    ]["value"]["condition_names"]
    assert "ConditionFirstBoot" in conditions
    assert "ConditionPathIsReadWrite" in conditions
    assert "PRIVATE-SENTINEL" not in repr(evidence)


def test_e5_custom_hostkey_fails_closed_without_reading_it(
    tmp_path: Path,
) -> None:
    _ssh_fixture(tmp_path)
    (
        tmp_path
        / "etc"
        / "ssh"
        / "sshd_config"
    ).write_text(
        "HostKey /srv/custom/private-host-key\n"
    )
    custom = (
        tmp_path
        / "srv"
        / "custom"
        / "private-host-key"
    )
    custom.parent.mkdir(parents=True)
    custom.write_text(
        "CUSTOM-PRIVATE-SENTINEL\n"
    )
    loaded = {
        "sshd-keygen.service": {
            "conditions": "ConditionFirstBoot=yes",
            "exec_start": "/usr/bin/ssh-keygen -A",
        }
    }
    evidence = collect_e5(
        tmp_path.as_posix(),
        runner=_runner(
            tmp_path,
            loaded=loaded,
        ),
    )
    assert evidence["status"] == "UNKNOWN"
    assert evidence["complete"] is False
    assert (
        evidence["reason_code"]
        == "STOP_SSH_IDENTITY_UNKNOWN"
    )
    assert (
        "CUSTOM-PRIVATE-SENTINEL"
        not in repr(evidence)
    )


def _network_fixture(root: Path) -> None:
    profile = (
        root
        / "etc"
        / "NetworkManager"
        / "system-connections"
        / "greenhouse.nmconnection"
    )
    profile.parent.mkdir(parents=True)
    profile.write_text(
        "[connection]\n"
        "id=private-profile-name\n"
        "uuid=12345678-1234-1234-1234-123456789abc\n"
        "stable-id=${CONNECTION}\n"
        "[ethernet]\n"
        "cloned-mac-address=random\n"
        "[ipv4]\n"
        "dhcp-client-id=stable\n"
    )
    netplan = (
        root
        / "etc"
        / "netplan"
        / "50-private.yaml"
    )
    netplan.parent.mkdir(parents=True)
    netplan.write_text(
        "network:\n"
        "  version: 2\n"
        "  renderer: NetworkManager\n"
        "  ethernets:\n"
        "    eth0:\n"
        "      dhcp4: true\n"
        "      dhcp-identifier: mac\n"
        "      macaddress: custom-link-identity\n"
    )


def test_e6_classifies_network_identity_without_raw_values(
    tmp_path: Path,
) -> None:
    _network_fixture(tmp_path)
    loaded = {
        unit: {}
        for unit in E6_UNITS
    }
    evidence = collect_e6(
        tmp_path.as_posix(),
        runner=_runner(
            tmp_path,
            loaded=loaded,
        ),
    )
    assert evidence["status"] == "OBSERVED"
    assert evidence["complete"] is True
    assert (
        evidence["fields"][
            "unknown_identity_state"
        ]["value"]
        is False
    )
    assert (
        "uuid"
        in evidence["fields"][
            "effective_identity_sources"
        ]["value"]["identity_field_names"]
    )
    rendered = repr(evidence)
    assert (
        "12345678-1234-1234-1234-123456789abc"
        not in rendered
    )
    assert "custom-link-identity" not in rendered
    assert "private-profile-name" not in rendered


def test_e6_symlinked_profile_is_unknown_and_not_followed(
    tmp_path: Path,
) -> None:
    profiles = (
        tmp_path
        / "etc"
        / "NetworkManager"
        / "system-connections"
    )
    profiles.mkdir(parents=True)
    outside = tmp_path / "private-profile"
    outside.write_text(
        "[connection]\n"
        "uuid=raw-private-uuid\n"
    )
    (
        profiles
        / "linked.nmconnection"
    ).symlink_to(outside)
    evidence = collect_e6(
        tmp_path.as_posix(),
        runner=_runner(
            tmp_path,
            loaded={
                unit: {}
                for unit in E6_UNITS
            },
        ),
    )
    assert evidence["status"] == "UNKNOWN"
    assert (
        evidence["reason_code"]
        == "STOP_NETWORK_IDENTITY_UNKNOWN"
    )
    assert "raw-private-uuid" not in repr(evidence)


def test_e7_classifies_journal_directories_without_names_or_body(
    tmp_path: Path,
) -> None:
    machine_id = "a" * 32
    (tmp_path / "etc").mkdir()
    (
        tmp_path
        / "etc"
        / "machine-id"
    ).write_text(machine_id + "\n")
    persistent = (
        tmp_path
        / "var"
        / "log"
        / "journal"
    )
    (persistent / machine_id).mkdir(parents=True)
    (persistent / ("b" * 32)).mkdir()
    (
        persistent
        / machine_id
        / "system.journal"
    ).write_text(
        "JOURNAL-BODY-SENTINEL"
    )
    journald = (
        tmp_path
        / "etc"
        / "systemd"
        / "journald.conf"
    )
    journald.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    journald.write_text(
        "[Journal]\n"
        "Storage=persistent\n"
        "SplitMode=uid\n"
    )
    loaded = {
        unit: {}
        for unit in E7_UNITS[:-1]
    }
    evidence = collect_e7(
        tmp_path.as_posix(),
        runner=_runner(
            tmp_path,
            loaded=loaded,
        ),
    )
    assert evidence["status"] == "OBSERVED"
    assert evidence["complete"] is True
    relation = evidence["fields"][
        "directory_identity_relation"
    ]["value"]
    assert relation["matches_current"] == 1
    assert relation["other_machine_id"] == 1
    rendered = repr(evidence)
    assert machine_id not in rendered
    assert ("b" * 32) not in rendered
    assert (
        "JOURNAL-BODY-SENTINEL"
        not in rendered
    )


def test_e8_never_reads_or_hashes_random_seed_body(
    tmp_path: Path,
) -> None:
    seed = (
        tmp_path
        / "var"
        / "lib"
        / "systemd"
        / "random-seed"
    )
    seed.parent.mkdir(parents=True)
    seed.write_text(
        "RANDOM-SEED-PRIVATE-SENTINEL"
    )
    seed.chmod(0o600)
    loaded = {
        "systemd-random-seed.service": {
            "before": "sysinit.target",
            "after": (
                "var-lib-systemd-random"
                "\\x2dseed.mount"
            ),
        }
    }
    evidence = collect_e8(
        tmp_path.as_posix(),
        runner=_runner(
            tmp_path,
            loaded=loaded,
        ),
    )
    assert evidence["status"] == "OBSERVED"
    assert evidence["complete"] is True
    limit = evidence["fields"][
        "boot_entropy_limit"
    ]["value"]
    assert limit["seed_body_read"] is False
    assert limit["seed_body_hashed"] is False
    assert (
        "RANDOM-SEED-PRIVATE-SENTINEL"
        not in repr(evidence)
    )


def _e9_loaded(
    *,
    requires_only: bool = False,
) -> dict[str, dict[str, str]]:
    network = "NetworkManager.service"
    ssh = "ssh.service"
    identity = (
        "systemd-firstboot.service",
        "systemd-machine-id-commit.service",
        "armbian-firstrun.service",
    )
    loaded: dict[str, dict[str, str]] = {
        network: {},
        ssh: {},
        "sshd-keygen.service": {
            "before": ssh
        },
    }
    for unit in identity:
        if requires_only:
            loaded[unit] = {
                "requires": (
                    network
                    + " "
                    + ssh
                )
            }
        else:
            loaded[unit] = {
                "before": (
                    network
                    + " "
                    + ssh
                )
            }
    return loaded


def test_e9_proves_order_only_from_before_after_edges(
    tmp_path: Path,
) -> None:
    loaded = _e9_loaded()
    evidence = collect_e9(
        tmp_path.as_posix(),
        runner=_runner(
            tmp_path,
            loaded=loaded,
        ),
    )
    assert evidence["status"] == "OBSERVED"
    assert evidence["complete"] is True
    assert (
        evidence["fields"][
            "identity_before_network"
        ]["value"]["classification"]
        == "SUPPORTED"
    )
    assert (
        evidence["fields"][
            "identity_before_ssh"
        ]["value"]["classification"]
        == "SUPPORTED"
    )
    activation = evidence["fields"][
        "activation_edges"
    ]["value"]
    assert activation[
        "ordering_semantics_excluded"
    ] == [
        "WANTS",
        "REQUIRES",
        "TRIGGERS",
    ]


def test_e9_requires_does_not_count_as_ordering(
    tmp_path: Path,
) -> None:
    loaded = _e9_loaded(requires_only=True)
    evidence = collect_e9(
        tmp_path.as_posix(),
        runner=_runner(
            tmp_path,
            loaded=loaded,
        ),
    )
    assert evidence["status"] == "OBSERVED"
    assert evidence["complete"] is True
    assert (
        evidence["fields"][
            "identity_before_network"
        ]["status"]
        == "UNKNOWN"
    )
    assert (
        evidence["fields"][
            "identity_before_ssh"
        ]["status"]
        == "UNKNOWN"
    )
    assert (
        evidence["fields"][
            "identity_before_network"
        ]["value"]["classification"]
        == "UNKNOWN"
    )


def test_e9_unknown_unit_capture_fails_closed(
    tmp_path: Path,
) -> None:
    good = _runner(
        tmp_path,
        loaded=_e9_loaded(),
    )

    def runner(
        command_id: str,
        **kwargs: object,
    ) -> CommandResult:
        if (
            command_id == "C4_UNIT"
            and kwargs.get("value")
            == "armbian-firstrun.service"
        ):
            return _result(
                "systemctl",
                returncode=1,
            )
        return good(command_id, **kwargs)

    evidence = collect_e9(
        tmp_path.as_posix(),
        runner=runner,
    )
    assert evidence["status"] == "UNKNOWN"
    assert evidence["complete"] is False
    assert (
        evidence["reason_code"]
        == "STOP_BOOT_ORDER_CAPTURE_GAP"
    )
