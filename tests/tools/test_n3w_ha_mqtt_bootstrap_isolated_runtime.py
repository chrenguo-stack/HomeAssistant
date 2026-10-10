from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = (
    ROOT
    / "infra/n3w-t1/homeassistant/custom_components"
    / "n3w_mqtt_bootstrap"
)
HA_IMAGE = "ghcr.io/home-assistant/home-assistant:2026.10.0"
BROKER_IMAGE = "eclipse-mosquitto:2.1.2-alpine"
USERNAME = "ghs_greenhouse_homeassistant"
CLIENT_ID = "gh-homeassistant-greenhouse"
PASSWORD = "n3w-ci-homeassistant-password-20261010"


def _run(
    command: list[str],
    *,
    check: bool = True,
    timeout_s: float = 60.0,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"command_timeout executable={Path(command[0]).name}"
        ) from error
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command_failed executable={Path(command[0]).name} "
            f"returncode={result.returncode}"
        )
    return result


def _broker_failure(
    name: str,
    failure_class: str,
    probe_stderr: str = "",
) -> RuntimeError:
    detail = _sanitize(probe_stderr.strip())
    return RuntimeError(
        f"{failure_class} "
        + _container_state(name)
        + f" probe={detail or 'none'}"
        + "\nBROKER_LOG_TAIL_BEGIN\n"
        + _safe_logs(name, tail=100)
        + "\nBROKER_LOG_TAIL_END"
    )


def _wait_broker_authenticated(
    name: str,
    timeout_s: float,
) -> None:
    deadline = time.monotonic() + timeout_s
    last_stderr = ""
    while time.monotonic() < deadline:
        if not _container_running(name):
            raise _broker_failure(
                name,
                "broker_stopped_before_readiness",
                last_stderr,
            )
        result = _run(
            [
                "docker",
                "exec",
                name,
                "mosquitto_pub",
                "-h",
                "127.0.0.1",
                "-p",
                "1883",
                "-u",
                USERNAME,
                "-P",
                PASSWORD,
                "-i",
                "n3w-ci-broker-readiness",
                "-V",
                "mqttv5",
                "-t",
                "n3w/ci/broker-readiness",
                "-m",
                "ok",
            ],
            check=False,
            timeout_s=5.0,
        )
        last_stderr = result.stderr
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise _broker_failure(
        name,
        "broker_authenticated_readiness_timeout",
        last_stderr,
    )


def _probe_container_network_tcp(name: str) -> None:
    result = _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            f"container:{name}",
            "--entrypoint",
            "python",
            HA_IMAGE,
            "-c",
            (
                "import socket;"
                "s=socket.create_connection(('127.0.0.1',1883),5);"
                "s.close()"
            ),
        ],
        check=False,
        timeout_s=15.0,
    )
    if result.returncode != 0:
        raise _broker_failure(
            name,
            "container_namespace_tcp_probe_failed",
            result.stderr,
        )


def _probe_container_network_mqtt_v5(
    name: str,
    password: str,
    *,
    expect_success: bool,
) -> None:
    result = _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            f"container:{name}",
            "--entrypoint",
            "mosquitto_pub",
            BROKER_IMAGE,
            "-h",
            "127.0.0.1",
            "-p",
            "1883",
            "-u",
            USERNAME,
            "-P",
            password,
            "-i",
            "n3w-ci-preflight-probe",
            "-V",
            "mqttv5",
            "-t",
            "n3w/ci/ha-bootstrap-probe",
            "-m",
            "ok",
        ],
        check=False,
        timeout_s=15.0,
    )
    passed = result.returncode == 0
    if passed != expect_success:
        raise _broker_failure(
            name,
            (
                "container_namespace_mqtt_v5_expected_success_failed"
                if expect_success
                else "container_namespace_wrong_password_not_rejected"
            ),
            result.stderr,
        )


def _container_running(name: str) -> bool:
    result = _run(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Running}}",
            name,
        ],
        check=False,
    )
    return (
        result.returncode == 0
        and result.stdout.strip() == "true"
    )


def _sanitize(value: str) -> str:
    result = value
    for secret in (
        PASSWORD,
        USERNAME,
        CLIENT_ID,
    ):
        result = result.replace(
            secret,
            "<redacted>",
        )
    return result


def _container_state(name: str) -> str:
    result = _run(
        [
            "docker",
            "inspect",
            "--format",
            (
                "running={{.State.Running}} "
                "exit={{.State.ExitCode}} "
                "oom={{.State.OOMKilled}} "
                "error={{json .State.Error}} "
                "restarts={{.RestartCount}}"
            ),
            name,
        ],
        check=False,
    )
    if result.returncode != 0:
        return "container_state_unavailable"
    return _sanitize(result.stdout.strip())


def _safe_logs(name: str, *, tail: int = 160) -> str:
    result = _run(
        [
            "docker",
            "logs",
            "--tail",
            str(tail),
            name,
        ],
        check=False,
    )
    return _sanitize(
        (result.stdout + result.stderr).strip()
    )


def _wait_config_entry(
    path: Path,
    timeout_s: float,
    *,
    ha_name: str,
    expected_bootstrap_class: str,
) -> dict:
    deadline = time.monotonic() + timeout_s
    last_log_probe = 0.0
    success_seen = False
    while time.monotonic() < deadline:
        if success_seen and path.is_file():
            try:
                document = json.loads(
                    path.read_text(encoding="utf-8")
                )
            except (
                OSError,
                UnicodeError,
                json.JSONDecodeError,
            ):
                time.sleep(0.5)
                continue
            data = document.get("data")
            entries = (
                data.get("entries")
                if isinstance(data, dict)
                else None
            )
            if isinstance(entries, list):
                matches = [
                    entry
                    for entry in entries
                    if isinstance(entry, dict)
                    and entry.get("domain") == "mqtt"
                    and entry.get("disabled_by") is None
                ]
                if len(matches) == 1:
                    return matches[0]

        now = time.monotonic()
        if now - last_log_probe >= 2.0:
            last_log_probe = now
            if not _container_running(ha_name):
                raise RuntimeError(
                    "homeassistant_container_stopped "
                    + _container_state(ha_name)
                )
            logs = _safe_logs(
                ha_name,
                tail=80,
            )
            marker = "N3-W MQTT bootstrap failed class="
            if marker in logs:
                matching = [
                    line.strip()
                    for line in logs.splitlines()
                    if marker in line
                ]
                raise RuntimeError(
                    "homeassistant_bootstrap_reported_failure "
                    + matching[-1]
                    + "\nHOMEASSISTANT_LOG_TAIL_BEGIN\n"
                    + logs
                    + "\nHOMEASSISTANT_LOG_TAIL_END"
                )
            success_marker = (
                "N3-W MQTT bootstrap success class="
                + expected_bootstrap_class
            )
            if success_marker in logs:
                success_seen = True
        time.sleep(0.5)

    storage_state = (
        f"storage_exists={path.exists()} "
        f"storage_size={path.stat().st_size if path.exists() else 0}"
    )
    raise RuntimeError(
        "mqtt_config_entry_timeout "
        + f"expected_bootstrap_class={expected_bootstrap_class} "
        + _container_state(ha_name)
        + " "
        + storage_state
        + "\nHOMEASSISTANT_LOG_TAIL_BEGIN\n"
        + _safe_logs(ha_name)
        + "\nHOMEASSISTANT_LOG_TAIL_END"
    )


def _named_uid_gid(
    image: str,
    user: str,
) -> tuple[int, int]:
    result = _run(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "sh",
            image,
            "-c",
            f"id -u {user}; id -g {user}",
        ]
    )
    values = result.stdout.splitlines()
    if (
        len(values) != 2
        or not values[0].isdigit()
        or not values[1].isdigit()
    ):
        raise RuntimeError("named_runtime_identity_invalid")
    return int(values[0]), int(values[1])


def _assert_broker_material_readable(
    broker_dir: Path,
    uid: int,
    gid: int,
) -> None:
    result = _run(
        [
            "docker",
            "run",
            "--rm",
            "--user",
            f"{uid}:{gid}",
            "-v",
            f"{broker_dir}:/work:ro",
            "--entrypoint",
            "sh",
            BROKER_IMAGE,
            "-c",
            (
                "test -x /work && "
                "test -r /work/mosquitto.conf && "
                "test -r /work/passwords"
            ),
        ],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "broker_material_not_readable_by_runtime_user"
        )


def _broker_client_event_count(name: str) -> int:
    result = _run(
        [
            "docker",
            "logs",
            name,
        ],
        check=False,
    )
    return sum(
        CLIENT_ID in line
        for line in (result.stdout + result.stderr).splitlines()
    )


def _wait_broker_client_connected(
    name: str,
    *,
    minimum_event_count: int,
    timeout_s: float,
) -> int:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _container_running(name):
            raise _broker_failure(
                name,
                "broker_stopped_waiting_for_ha_client",
            )
        result = _run(
            [
                "docker",
                "logs",
                name,
            ],
            check=False,
        )
        events = [
            line
            for line in (result.stdout + result.stderr).splitlines()
            if CLIENT_ID in line
        ]
        if (
            len(events) >= minimum_event_count
            and "New client connected" in events[-1]
        ):
            return len(events)
        time.sleep(0.5)
    raise _broker_failure(
        name,
        "homeassistant_mqtt_client_not_connected",
    )


def _image_uid_gid() -> tuple[int, int]:
    uid = _run(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "id",
            HA_IMAGE,
            "-u",
        ]
    ).stdout.strip()
    gid = _run(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "id",
            HA_IMAGE,
            "-g",
        ]
    ).stdout.strip()
    if not uid.isdigit() or not gid.isdigit():
        raise RuntimeError("homeassistant_runtime_identity_invalid")
    return int(uid), int(gid)


def _chown(path: Path, uid: int, gid: int) -> None:
    if (
        path.stat().st_uid == uid
        and path.stat().st_gid == gid
    ):
        return
    result = _run(
        [
            "sudo",
            "chown",
            f"{uid}:{gid}",
            str(path),
        ],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("secret_ownership_bind_failed")


def _assert_entry(entry: dict) -> None:
    data = entry.get("data")
    assert isinstance(data, dict)
    assert data.get("broker") == "127.0.0.1"
    assert data.get("port") == 1883
    assert data.get("protocol") == "5"
    assert data.get("username") == USERNAME
    assert data.get("client_id") == CLIENT_ID
    assert data.get("password") == PASSWORD
    assert data.get("certificate") is None


def test_exact_homeassistant_image_bootstrap_and_recreate(
    tmp_path: Path,
) -> None:
    token = uuid.uuid4().hex[:12]
    broker_name = f"n3w-ha-bootstrap-broker-{token}"
    ha_name = f"n3w-ha-bootstrap-ha-{token}"
    broker_dir = tmp_path / "broker"
    ha_config = tmp_path / "ha-config"
    secrets = tmp_path / "secrets"
    broker_dir.mkdir(mode=0o700)
    ha_config.mkdir(mode=0o755)
    secrets.mkdir(mode=0o700)

    try:
        _run(
            [
                "docker",
                "run",
                "--rm",
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--entrypoint",
                "mosquitto_passwd",
                "-v",
                f"{broker_dir}:/work",
                BROKER_IMAGE,
                "-b",
                "-c",
                "/work/passwords",
                USERNAME,
                PASSWORD,
            ]
        )
        if (
            broker_dir.joinpath("passwords").stat().st_uid
            != os.getuid()
        ):
            raise RuntimeError(
                "broker_password_file_owner_generation_mismatch"
            )
        (broker_dir / "mosquitto.conf").write_text(
            (
                "listener 1883 127.0.0.1\n"
                "allow_anonymous false\n"
                "password_file /mosquitto/config/passwords\n"
                "persistence false\n"
                "log_dest stdout\n"
                "log_type all\n"
            ),
            encoding="utf-8",
        )
        os.chmod(
            broker_dir / "mosquitto.conf",
            0o600,
        )
        os.chmod(
            broker_dir / "passwords",
            0o600,
        )
        broker_uid, broker_gid = _named_uid_gid(
            BROKER_IMAGE,
            "mosquitto",
        )
        _chown(
            broker_dir / "mosquitto.conf",
            broker_uid,
            broker_gid,
        )
        _chown(
            broker_dir / "passwords",
            broker_uid,
            broker_gid,
        )
        _chown(broker_dir, broker_uid, broker_gid)
        _assert_broker_material_readable(
            broker_dir,
            broker_uid,
            broker_gid,
        )

        _run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                broker_name,
                "-v",
                f"{broker_dir}:/mosquitto/config:ro",
                BROKER_IMAGE,
                "mosquitto",
                "-c",
                "/mosquitto/config/mosquitto.conf",
            ]
        )
        _wait_broker_authenticated(
            broker_name,
            30.0,
        )
        _probe_container_network_tcp(broker_name)
        _probe_container_network_mqtt_v5(
            broker_name,
            PASSWORD,
            expect_success=True,
        )
        _probe_container_network_mqtt_v5(
            broker_name,
            PASSWORD + "-wrong",
            expect_success=False,
        )

        custom_root = (
            ha_config
            / "custom_components"
            / "n3w_mqtt_bootstrap"
        )
        shutil.copytree(COMPONENT, custom_root)
        (ha_config / "configuration.yaml").write_text(
            (
                "homeassistant:\n"
                "  name: N3W CI\n"
                "n3w_mqtt_bootstrap:\n"
                "  metadata_file: /run/n3w/ha-mqtt-bootstrap.json\n"
            ),
            encoding="utf-8",
        )

        password_file = secrets / "password"
        metadata_file = secrets / "mqtt-bootstrap.json"
        password_file.write_text(
            PASSWORD + "\n",
            encoding="utf-8",
        )
        metadata_file.write_text(
            json.dumps(
                {
                    "schema": (
                        "gh.n3w.t1-clean-homeassistant-"
                        "mqtt-bootstrap/1"
                    ),
                    "service": "homeassistant",
                    "broker": "127.0.0.1",
                    "port": 1883,
                    "protocol": "5",
                    "username": USERNAME,
                    "client_id": CLIENT_ID,
                    "generation": 1,
                    "password_file": (
                        "/run/secrets/"
                        "gh_homeassistant_mqtt_password"
                    ),
                    "official_config_flow_only": True,
                    "direct_storage_edit_forbidden": True,
                    "automatic_apply": True,
                    "operator_plaintext_copy_required": False,
                    "runtime_verified": False,
                },
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        os.chmod(password_file, 0o600)
        os.chmod(metadata_file, 0o600)

        uid, gid = _image_uid_gid()
        _chown(password_file, uid, gid)
        _chown(metadata_file, uid, gid)

        common = [
            "docker",
            "run",
            "-d",
            "--name",
            ha_name,
            "--network",
            f"container:{broker_name}",
            "-v",
            f"{ha_config}:/config",
            "-v",
            (
                f"{password_file}:"
                "/run/secrets/gh_homeassistant_mqtt_password:ro"
            ),
            "-v",
            (
                f"{metadata_file}:"
                "/run/n3w/ha-mqtt-bootstrap.json:ro"
            ),
            HA_IMAGE,
        ]
        _run(common)

        entry_path = (
            ha_config
            / ".storage"
            / "core.config_entries"
        )
        first = _wait_config_entry(
            entry_path,
            120.0,
            ha_name=ha_name,
            expected_bootstrap_class="created",
        )
        _assert_entry(first)
        assert _container_running(ha_name)
        first_event_count = _wait_broker_client_connected(
            broker_name,
            minimum_event_count=1,
            timeout_s=60.0,
        )

        _run(
            [
                "docker",
                "rm",
                "-f",
                ha_name,
            ]
        )
        recreate_event_baseline = max(
            first_event_count,
            _broker_client_event_count(broker_name),
        )
        _run(common)

        second = _wait_config_entry(
            entry_path,
            120.0,
            ha_name=ha_name,
            expected_bootstrap_class="existing_match",
        )
        _assert_entry(second)
        assert _container_running(ha_name)
        _wait_broker_client_connected(
            broker_name,
            minimum_event_count=recreate_event_baseline + 1,
            timeout_s=60.0,
        )
        assert (
            second.get("entry_id")
            == first.get("entry_id")
        )
    finally:
        _run(
            [
                "docker",
                "rm",
                "-f",
                ha_name,
            ],
            check=False,
        )
        _run(
            [
                "docker",
                "rm",
                "-f",
                broker_name,
            ],
            check=False,
        )
