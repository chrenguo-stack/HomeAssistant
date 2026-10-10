from __future__ import annotations

import json
import os
import shutil
import socket
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
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command_failed executable={Path(command[0]).name} "
            f"returncode={result.returncode}"
        )
    return result


def _wait_tcp(
    host: str,
    port: int,
    timeout_s: float,
) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(
                (host, port),
                timeout=1.0,
            ):
                return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("broker_tcp_timeout")


def _probe_host_network_tcp() -> None:
    result = _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            "--entrypoint",
            "python",
            HA_IMAGE,
            "-c",
            (
                "import socket,time;"
                "deadline=time.monotonic()+30;"
                "ok=False;"
                "\nwhile time.monotonic()<deadline:"
                "\n try:"
                "\n  s=socket.create_connection(('127.0.0.1',1883),1);"
                "\n  s.close();ok=True;break"
                "\n except OSError:"
                "\n  time.sleep(0.25)"
                "\nraise SystemExit(0 if ok else 1)"
            ),
        ],
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "host_network_tcp_probe_failed "
            f"returncode={result.returncode}"
        )


def _probe_host_network_mqtt_v5() -> None:
    result = _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
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
            PASSWORD,
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
    )
    if result.returncode != 0:
        raise RuntimeError(
            "host_network_mqtt_v5_probe_failed "
            f"returncode={result.returncode}"
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
) -> dict:
    deadline = time.monotonic() + timeout_s
    last_log_probe = 0.0
    while time.monotonic() < deadline:
        if path.is_file():
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
        time.sleep(0.5)

    storage_state = (
        f"storage_exists={path.exists()} "
        f"storage_size={path.stat().st_size if path.exists() else 0}"
    )
    raise RuntimeError(
        "mqtt_config_entry_timeout "
        + _container_state(ha_name)
        + " "
        + storage_state
        + "\nHOMEASSISTANT_LOG_TAIL_BEGIN\n"
        + _safe_logs(ha_name)
        + "\nHOMEASSISTANT_LOG_TAIL_END"
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
        (broker_dir / "mosquitto.conf").write_text(
            (
                "listener 1883 127.0.0.1\n"
                "allow_anonymous false\n"
                "password_file /mosquitto/config/passwords\n"
                "persistence false\n"
                "log_dest stdout\n"
            ),
            encoding="utf-8",
        )
        os.chmod(
            broker_dir / "mosquitto.conf",
            0o644,
        )

        _run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                broker_name,
                "--network",
                "host",
                "-v",
                f"{broker_dir}:/mosquitto/config:ro",
                BROKER_IMAGE,
                "mosquitto",
                "-c",
                "/mosquitto/config/mosquitto.conf",
            ]
        )
        _probe_host_network_tcp()
        _probe_host_network_mqtt_v5()

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
            "host",
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
        )
        _assert_entry(first)
        assert _container_running(ha_name)

        _run(
            [
                "docker",
                "rm",
                "-f",
                ha_name,
            ]
        )
        _run(common)

        second = _wait_config_entry(
            entry_path,
            120.0,
            ha_name=ha_name,
        )
        _assert_entry(second)
        assert _container_running(ha_name)
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
