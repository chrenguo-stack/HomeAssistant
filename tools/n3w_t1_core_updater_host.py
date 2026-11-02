from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

from n3w_t1_core_updater_common import (
    BROKER_ENV,
    BROKER_UNIT,
    COMPOSE,
    COMPOSE_ENV,
    EXPECTED_EXECSTART,
    EXPECTED_EXECSTOP,
    IMAGE_ID,
    PROJECT,
    REGISTRATION_GUARD_UNIT,
    SERVICES_UNIT,
    UpdaterError,
    canonical,
    manager_env_image,
    rewrite_manager_env,
    sha256_bytes,
    sha256_text,
)


class LocalHost:
    def _run(
        self,
        argv: Sequence[str],
        *,
        timeout: int = 60,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        result = subprocess.run(
            tuple(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        if check and result.returncode:
            detail = (result.stderr or result.stdout).decode(errors="replace").strip()
            raise UpdaterError(
                f"command_failed:{Path(argv[0]).name}:{detail[:300]}"
            )
        return result

    def _systemctl(self, action: str, unit: str) -> str:
        result = self._run(("systemctl", action, unit), check=False)
        value = result.stdout.decode().strip()
        allowed = {"inactive", "failed", "disabled", "static", "not-found"}
        if result.returncode and value not in allowed:
            raise UpdaterError(f"systemctl_{action}_failed:{unit}")
        return value

    def _activation_env(self) -> None:
        if BROKER_ENV.is_symlink() or not BROKER_ENV.is_file():
            raise UpdaterError("activation_env_invalid")
        values: dict[str, str] = {}
        for raw in BROKER_ENV.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            if "=" not in line:
                raise UpdaterError("activation_env_line_invalid")
            key, value = line.split("=", 1)
            key = key.strip()
            if key in values:
                raise UpdaterError("activation_env_duplicate")
            values[key] = value.strip().strip("'\"")
        expected = {
            "N3WFC4_COMPOSE_FILE": str(COMPOSE),
            "N3WFC4_COMPOSE_ENV_FILE": str(COMPOSE_ENV),
            "N3WFC4_COMPOSE_PROJECT_NAME": PROJECT,
        }
        if any(values.get(key) != value for key, value in expected.items()):
            raise UpdaterError("activation_env_authority_drift")

    def _service_unit(self) -> dict[str, str]:
        raw = self._run(("systemctl", "cat", SERVICES_UNIT)).stdout.decode()
        starts = [
            line.strip()
            for line in raw.splitlines()
            if line.strip().startswith("ExecStart=")
        ]
        stops = [
            line.strip()
            for line in raw.splitlines()
            if line.strip().startswith("ExecStop=")
        ]
        if (
            starts != [EXPECTED_EXECSTART]
            or stops != [EXPECTED_EXECSTOP]
            or "--force-recreate" in raw
        ):
            raise UpdaterError("services_supervision_contract_drift")
        return {
            "execstart_sha256": sha256_text(starts[0]),
            "execstop_sha256": sha256_text(stops[0]),
        }

    def _compose_argv(self) -> tuple[str, ...]:
        return (
            "docker",
            "compose",
            "--project-name",
            PROJECT,
            "--env-file",
            str(COMPOSE_ENV),
            "-f",
            str(COMPOSE),
        )

    def render_compose(self) -> dict[str, Any]:
        raw = self._run(
            (*self._compose_argv(), "--profile", "application", "config", "--format", "json"),
            timeout=120,
        ).stdout
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as error:
            raise UpdaterError("compose_render_invalid") from error
        if not isinstance(document, dict):
            raise UpdaterError("compose_render_shape_invalid")
        return document

    def _container_id(self, service: str) -> str:
        raw = self._run(
            (
                "docker",
                "ps",
                "-q",
                "--filter",
                f"label=com.docker.compose.project={PROJECT}",
                "--filter",
                f"label=com.docker.compose.service={service}",
            )
        ).stdout.decode()
        values = [line.strip() for line in raw.splitlines() if line.strip()]
        if len(values) != 1:
            raise UpdaterError(f"{service}_container_count_invalid")
        return values[0]

    def _runtime(self, service: str) -> dict[str, Any]:
        container_id = self._container_id(service)
        try:
            document = json.loads(
                self._run(("docker", "inspect", container_id)).stdout
            )
        except json.JSONDecodeError as error:
            raise UpdaterError("docker_inspect_invalid") from error
        if (
            not isinstance(document, list)
            or len(document) != 1
            or not isinstance(document[0], dict)
        ):
            raise UpdaterError("docker_inspect_shape_invalid")
        item = document[0]
        state = item.get("State")
        config = item.get("Config")
        host = item.get("HostConfig")
        labels = config.get("Labels") if isinstance(config, dict) else None
        if (
            not isinstance(state, dict)
            or state.get("Running") is not True
            or not isinstance(config, dict)
            or not isinstance(host, dict)
            or not isinstance(labels, dict)
            or labels.get("com.docker.compose.project") != PROJECT
            or labels.get("com.docker.compose.service") != service
        ):
            raise UpdaterError(f"{service}_runtime_invalid")
        result = {
            "container_id": item.get("Id"),
            "image_ref": config.get("Image"),
            "image_id": item.get("Image"),
            "started_at": state.get("StartedAt"),
            "restart_count": item.get("RestartCount"),
            "network_mode": host.get("NetworkMode"),
        }
        if (
            not isinstance(result["container_id"], str)
            or not isinstance(result["image_ref"], str)
            or not isinstance(result["image_id"], str)
            or IMAGE_ID.fullmatch(result["image_id"]) is None
            or not isinstance(result["started_at"], str)
            or not isinstance(result["restart_count"], int)
        ):
            raise UpdaterError(f"{service}_runtime_identity_invalid")
        return result

    def _listener_count(self, protocol: str, port: int) -> int:
        flag = "-ltn" if protocol == "tcp" else "-lun"
        raw = self._run(
            ("ss", "-H", flag, "sport", "=", f":{port}")
        ).stdout.decode()
        return len([line for line in raw.splitlines() if line.strip()])

    def manager_binding(self) -> str:
        if COMPOSE_ENV.is_symlink() or not COMPOSE_ENV.is_file():
            raise UpdaterError("compose_env_invalid")
        return manager_env_image(COMPOSE_ENV.read_bytes())

    def inspect(self) -> dict[str, Any]:
        for unit in (BROKER_UNIT, SERVICES_UNIT, REGISTRATION_GUARD_UNIT):
            if self._systemctl("is-active", unit) != "active":
                raise UpdaterError(f"unit_not_active:{unit}")
            if self._systemctl("is-enabled", unit) != "enabled":
                raise UpdaterError(f"unit_not_enabled:{unit}")
        self._activation_env()
        unit = self._service_unit()
        if (
            COMPOSE.is_symlink()
            or not COMPOSE.is_file()
            or COMPOSE_ENV.is_symlink()
            or not COMPOSE_ENV.is_file()
        ):
            raise UpdaterError("compose_authority_invalid")
        env_payload = COMPOSE_ENV.read_bytes()
        env_image = self.manager_binding()
        rendered = self.render_compose()
        services = rendered.get("services")
        if not isinstance(services, dict):
            raise UpdaterError("compose_services_invalid")
        manager_compose = services.get("manager")
        ha_compose = services.get("homeassistant")
        broker_compose = services.get("broker")
        if not all(
            isinstance(item, dict)
            for item in (manager_compose, ha_compose, broker_compose)
        ):
            raise UpdaterError("compose_service_missing")
        if manager_compose.get("image") != env_image:
            raise UpdaterError("compose_env_manager_image_drift")
        if (
            manager_compose.get("network_mode") != "host"
            or ha_compose.get("network_mode") != "host"
        ):
            raise UpdaterError("host_network_contract_drift")
        if any(
            item.get("pull_policy") != "never"
            for item in (manager_compose, ha_compose, broker_compose)
        ):
            raise UpdaterError("pull_policy_contract_drift")
        runtime = {
            name: self._runtime(name)
            for name in ("broker", "manager", "homeassistant")
        }
        if runtime["manager"]["image_ref"] != env_image:
            raise UpdaterError("manager_runtime_image_drift")
        if (
            runtime["manager"]["network_mode"] != "host"
            or runtime["homeassistant"]["network_mode"] != "host"
        ):
            raise UpdaterError("runtime_network_contract_drift")
        listeners = {
            "tcp_8883": self._listener_count("tcp", 8883),
            "tcp_47110": self._listener_count("tcp", 47110),
            "udp_47111": self._listener_count("udp", 47111),
            "tcp_47112": self._listener_count("tcp", 47112),
        }
        expected_listeners = {
            "tcp_8883": 1,
            "tcp_47110": 1,
            "udp_47111": 1,
            "tcp_47112": 0,
        }
        if listeners != expected_listeners:
            raise UpdaterError("listener_contract_drift")
        return {
            "manager_image": env_image,
            "compose_env_sha256": sha256_bytes(env_payload),
            "compose_render": rendered,
            "compose_render_sha256": sha256_bytes(canonical(rendered)),
            "services_unit": unit,
            "runtime": runtime,
            "listeners": listeners,
        }

    def image_id(self, reference: str) -> str | None:
        result = self._run(
            ("docker", "image", "inspect", reference),
            check=False,
        )
        if result.returncode:
            return None
        try:
            document = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise UpdaterError("image_inspect_invalid") from error
        value = (
            document[0].get("Id")
            if isinstance(document, list)
            and len(document) == 1
            and isinstance(document[0], dict)
            else None
        )
        if not isinstance(value, str) or IMAGE_ID.fullmatch(value) is None:
            raise UpdaterError("image_id_invalid")
        return value

    def load_image(self, tar_path: Path) -> None:
        self._run(("docker", "load", "-i", str(tar_path)), timeout=1800)

    def _running_count(self, service: str) -> int:
        result = self._run(
            (
                "docker",
                "ps",
                "-q",
                "--filter",
                f"label=com.docker.compose.project={PROJECT}",
                "--filter",
                f"label=com.docker.compose.service={service}",
            ),
            check=False,
        )
        if result.returncode:
            raise UpdaterError(f"{service}_container_lookup_failed")
        return len(
            [line for line in result.stdout.decode().splitlines() if line.strip()]
        )

    def stop_services(self) -> None:
        self._run(("systemctl", "stop", SERVICES_UNIT), timeout=180)
        if self._systemctl("is-active", SERVICES_UNIT) != "inactive":
            raise UpdaterError("services_not_inactive")
        if self._running_count("manager") or self._running_count("homeassistant"):
            raise UpdaterError("application_container_still_running")

    def start_services(self) -> None:
        self._run(("systemctl", "start", SERVICES_UNIT), timeout=180)
        self.wait_services()

    def wait_services(self, timeout: int = 120) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._systemctl("is-active", SERVICES_UNIT) == "active":
                try:
                    self._container_id("manager")
                    self._container_id("homeassistant")
                    return
                except UpdaterError:
                    pass
            time.sleep(2)
        raise UpdaterError("services_start_timeout")

    def rewrite_manager_image(self, expected: str, replacement: str) -> str:
        if COMPOSE_ENV.is_symlink() or not COMPOSE_ENV.is_file():
            raise UpdaterError("compose_env_invalid")
        original = COMPOSE_ENV.read_bytes()
        updated = rewrite_manager_env(original, expected, replacement)
        meta = COMPOSE_ENV.stat()
        fd, raw = tempfile.mkstemp(
            prefix=f".{COMPOSE_ENV.name}.",
            dir=COMPOSE_ENV.parent,
        )
        temporary = Path(raw)
        try:
            os.fchmod(fd, stat.S_IMODE(meta.st_mode))
            with os.fdopen(fd, "wb") as stream:
                stream.write(updated)
                stream.flush()
                os.fsync(stream.fileno())
            os.chown(temporary, meta.st_uid, meta.st_gid)
            os.replace(temporary, COMPOSE_ENV)
            directory = os.open(
                COMPOSE_ENV.parent,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)
        observed = COMPOSE_ENV.read_bytes()
        if observed != updated:
            raise UpdaterError("compose_env_replace_verify_failed")
        return sha256_bytes(observed)

    def broker_continuity(self, baseline: dict[str, Any]) -> None:
        current = self._runtime("broker")
        for key in (
            "container_id",
            "image_ref",
            "image_id",
            "started_at",
            "restart_count",
        ):
            if key in baseline and current.get(key) != baseline.get(key):
                raise UpdaterError("broker_continuity_failed")
        if self._listener_count("tcp", 8883) != 1:
            raise UpdaterError("broker_listener_continuity_failed")
