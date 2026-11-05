from __future__ import annotations

import fcntl
import http.client
import json
import os
import re
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

from n3w_t1_portable_image_identity import (
    PortableImageIdentityError,
    parse_image_archive,
    verify_runtime_document,
)

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

from n3w_t1_core_updater_v2_common import (
    COMPONENTS,
    IMAGE_BINDINGS,
    IMAGE_PREFIXES,
    converge_homeassistant_compose,
    converge_homeassistant_env,
    restore_homeassistant_compose,
    restore_homeassistant_env,
    rewrite_component_env,
)


EXPECTED_LISTENERS = {
    "tcp_8883": 1,
    "tcp_47110": 1,
    "udp_47111": 1,
    "tcp_47112": 0,
}

CERT_LIFECYCLE_UNIT = "n3wfc4-broker-certificate-lifecycle.service"
CERT_LIFECYCLE_TIMER = "n3wfc4-broker-certificate-lifecycle.timer"
PROVISION_UNIT = "n3wfc4-provision-resume.service"
BROKER_INGRESS_GUARD_UNIT = "n3wfc4-broker-ingress-guard.service"
REQUIRED_ACTIVE_ENABLED_UNITS = (
    PROVISION_UNIT,
    BROKER_INGRESS_GUARD_UNIT,
    REGISTRATION_GUARD_UNIT,
    BROKER_UNIT,
    SERVICES_UNIT,
    CERT_LIFECYCLE_TIMER,
)
RELEVANT_UNITS = frozenset(
    (*REQUIRED_ACTIVE_ENABLED_UNITS, CERT_LIFECYCLE_UNIT)
)
EXPECTED_PLATFORM = "linux/arm64"
DEFAULT_SERVICES_READINESS_TIMEOUT_SECONDS = 120
HOMEASSISTANT_SERVICES_READINESS_TIMEOUT_SECONDS = 600
BROKER_CERT_LIFECYCLE_LOCK = Path(
    "/var/lib/n3wfc4-certificate-lifecycle/.certificate-lifecycle.lock"
)
MQTT_IDENTITY_FILES = {
    "manager": Path("/opt/greenhouse-secrets/mqtt/manager/runtime.env"),
    "homeassistant": Path(
        "/opt/greenhouse-secrets/mqtt/homeassistant/mqtt-bootstrap.json"
    ),
}


class LocalHost:
    def __init__(self) -> None:
        self._component_guard_fd: int | None = None

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
        image_reference = config.get("Image")
        if not isinstance(image_reference, str) or not image_reference:
            raise UpdaterError(f"{service}_runtime_image_ref_invalid")
        image_document = self._image_document(image_reference)
        if image_document is None:
            raise UpdaterError(f"{service}_runtime_image_missing")
        image_os = image_document.get("Os")
        image_arch = image_document.get("Architecture")
        if not isinstance(image_os, str) or not isinstance(image_arch, str):
            raise UpdaterError(f"{service}_runtime_platform_invalid")
        platform = f"{image_os}/{image_arch}"
        if platform != EXPECTED_PLATFORM:
            raise UpdaterError(f"{service}_runtime_platform_unsupported")

        mounts = item.get("Mounts")
        if not isinstance(mounts, list):
            raise UpdaterError(f"{service}_runtime_mounts_invalid")
        mount_contract = sorted(
            (
                {
                    "type": row.get("Type"),
                    "source": row.get("Source"),
                    "destination": row.get("Destination"),
                    "rw": row.get("RW"),
                }
                for row in mounts
                if isinstance(row, dict)
            ),
            key=lambda row: (
                str(row.get("destination")),
                str(row.get("type")),
                str(row.get("source")),
                str(row.get("rw")),
            ),
        )
        runtime_contract = {
            "user": config.get("User"),
            "network_mode": host.get("NetworkMode"),
            "readonly_rootfs": host.get("ReadonlyRootfs"),
            "restart_policy": host.get("RestartPolicy"),
            "cap_drop": sorted(host.get("CapDrop") or []),
            "security_opt": sorted(host.get("SecurityOpt") or []),
            "mounts": mount_contract,
            "port_bindings": host.get("PortBindings") or {},
        }
        result = {
            "container_id": item.get("Id"),
            "image_ref": config.get("Image"),
            "image_id": item.get("Image"),
            "started_at": state.get("StartedAt"),
            "restart_count": item.get("RestartCount"),
            "network_mode": host.get("NetworkMode"),
            "platform": platform,
            "runtime_contract_sha256": sha256_bytes(
                canonical(runtime_contract)
            ),
        }
        if (
            not isinstance(result["container_id"], str)
            or not isinstance(result["image_ref"], str)
            or not isinstance(result["image_id"], str)
            or IMAGE_ID.fullmatch(result["image_id"]) is None
            or not isinstance(result["started_at"], str)
            or not isinstance(result["restart_count"], int)
            or result["platform"] != EXPECTED_PLATFORM
            or not isinstance(result["runtime_contract_sha256"], str)
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

    def _system_health_v2(self) -> dict[str, Any]:
        state_result = self._run(
            ("systemctl", "is-system-running"),
            timeout=15,
            check=False,
        )
        state = state_result.stdout.decode().strip()
        if state_result.returncode not in {0, 1} or state not in {
            "running",
            "degraded",
        }:
            raise UpdaterError("system_state_not_acceptable")

        failed_result = self._run(
            ("systemctl", "--failed", "--no-legend", "--plain"),
            timeout=20,
            check=False,
        )
        if failed_result.returncode not in {0, 1}:
            raise UpdaterError("failed_unit_query_invalid")
        failed_units = [
            line.split()[0]
            for line in failed_result.stdout.decode().splitlines()
            if line.strip()
        ]
        relevant_failed = sorted(set(failed_units) & RELEVANT_UNITS)
        if relevant_failed:
            raise UpdaterError(
                "relevant_failed_units:" + ",".join(relevant_failed)
            )

        units: dict[str, dict[str, str]] = {}
        for unit in RELEVANT_UNITS:
            units[unit] = {
                "active": self._systemctl("is-active", unit),
                "enabled": self._systemctl("is-enabled", unit),
            }
        for unit in REQUIRED_ACTIVE_ENABLED_UNITS:
            if units[unit] != {"active": "active", "enabled": "enabled"}:
                raise UpdaterError(f"unit_health_invalid:{unit}")
        if units[CERT_LIFECYCLE_UNIT]["active"] != "inactive":
            raise UpdaterError("certificate_service_not_quiescent")

        return {
            "system_state": state,
            "failed_units": failed_units,
            "relevant_failed_units": relevant_failed,
            "systemd_units": units,
        }

    def _running_project_services_v2(self) -> list[str]:
        result = self._run(
            (
                *self._compose_argv(),
                "--profile",
                "application",
                "ps",
                "--status",
                "running",
                "--services",
            ),
            timeout=30,
        )
        services = sorted(
            line.strip()
            for line in result.stdout.decode().splitlines()
            if line.strip()
        )
        expected = sorted(("broker", "homeassistant", "manager"))
        if services != expected:
            raise UpdaterError("runtime_service_set_invalid")
        return services

    def _observe_running_base_v2(self) -> dict[str, Any]:
        system_health = self._system_health_v2()
        runtime_services = self._running_project_services_v2()
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
        return {
            "manager_image": env_image,
            "compose_env_sha256": sha256_bytes(env_payload),
            "compose_render": rendered,
            "compose_render_sha256": sha256_bytes(canonical(rendered)),
            "services_unit": unit,
            "runtime": runtime,
            "listeners": self._listener_snapshot(),
            "runtime_services": runtime_services,
            "system_health": system_health,
        }

    def inspect(self) -> dict[str, Any]:
        snapshot = self._observe_running_base_v2()
        if snapshot["listeners"] != EXPECTED_LISTENERS:
            raise UpdaterError("listener_contract_drift")
        return snapshot

    def _image_binding_authority_v2(
        self,
        rendered: dict[str, Any] | None = None,
    ) -> tuple[dict[str, str], dict[str, str]]:
        if COMPOSE_ENV.is_symlink() or not COMPOSE_ENV.is_file():
            raise UpdaterError("compose_env_invalid")
        try:
            text = COMPOSE_ENV.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise UpdaterError("compose_env_invalid") from error
        document = rendered if rendered is not None else self.render_compose()
        services = document.get("services")
        if not isinstance(services, dict):
            raise UpdaterError("compose_services_invalid")

        bindings: dict[str, str] = {}
        modes: dict[str, str] = {}
        for component in COMPONENTS:
            key = IMAGE_BINDINGS[component]
            matches = [
                line.split("=", 1)[1]
                for line in text.splitlines()
                if line.startswith(f"{key}=")
            ]
            service = services.get(component)
            if not isinstance(service, dict):
                raise UpdaterError(f"{component}_compose_service_missing")
            rendered_image = service.get("image")
            if not isinstance(rendered_image, str) or not rendered_image.startswith(
                IMAGE_PREFIXES[component]
            ):
                raise UpdaterError(f"{component}_compose_image_invalid")

            if len(matches) == 1:
                if (
                    not matches[0].startswith(IMAGE_PREFIXES[component])
                    or matches[0] != rendered_image
                ):
                    raise UpdaterError(
                        f"{component}_compose_env_image_drift"
                    )
                bindings[component] = matches[0]
                modes[component] = "dynamic"
                continue

            if len(matches) == 0 and component != "manager":
                bindings[component] = rendered_image
                modes[component] = "legacy_static"
                continue

            raise UpdaterError(
                f"{component}_image_binding_authority_invalid"
            )
        return bindings, modes

    def image_bindings_v2(self) -> dict[str, str]:
        return self._image_binding_authority_v2()[0]

    def image_binding_modes_v2(self) -> dict[str, str]:
        return self._image_binding_authority_v2()[1]

    def component_binding_v2(self, component: str) -> str:
        if component not in COMPONENTS:
            raise UpdaterError("component_invalid")
        return self.image_bindings_v2()[component]

    def component_container_residue(
        self,
        component: str,
    ) -> list[dict[str, str]]:
        if component not in COMPONENTS:
            raise UpdaterError("component_invalid")
        result = self._run(
            (
                "docker",
                "ps",
                "-aq",
                "--no-trunc",
                "--filter",
                f"label=com.docker.compose.project={PROJECT}",
                "--filter",
                f"label=com.docker.compose.service={component}",
            ),
            check=False,
        )
        if result.returncode:
            raise UpdaterError(f"{component}_container_residue_lookup_failed")
        container_ids = [
            line.strip()
            for line in result.stdout.decode().splitlines()
            if line.strip()
        ]
        residue: list[dict[str, str]] = []
        for container_id in container_ids:
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
            labels = config.get("Labels") if isinstance(config, dict) else None
            if (
                not isinstance(state, dict)
                or not isinstance(config, dict)
                or not isinstance(labels, dict)
                or labels.get("com.docker.compose.project") != PROJECT
                or labels.get("com.docker.compose.service") != component
            ):
                raise UpdaterError(f"{component}_container_residue_invalid")
            if state.get("Running") is True:
                continue
            image_ref = config.get("Image")
            image_id = item.get("Image")
            status = state.get("Status")
            name = item.get("Name")
            replace = labels.get("com.docker.compose.replace")
            if (
                not isinstance(image_ref, str)
                or not isinstance(image_id, str)
                or not isinstance(status, str)
                or not isinstance(name, str)
            ):
                raise UpdaterError(f"{component}_container_residue_invalid")
            residue.append(
                {
                    "container_id": container_id,
                    "image_ref": image_ref,
                    "image_id": image_id,
                    "status": status,
                    "name": name,
                    "replace": replace if isinstance(replace, str) else "",
                }
            )
        return residue

    def assert_component_upgradeable(self, component: str) -> None:
        if component not in COMPONENTS:
            raise UpdaterError("component_invalid")
        if self.component_container_residue(component):
            raise UpdaterError(f"{component}_container_residue_present")
        mode = self.image_binding_modes_v2()[component]
        if mode == "dynamic":
            return
        if component == "homeassistant" and mode == "legacy_static":
            return
        raise UpdaterError(
            f"{component}_runtime_template_convergence_required"
        )

    def _mqtt_authenticated(self, service: str) -> bool:
        if service not in MQTT_IDENTITY_FILES:
            raise UpdaterError("mqtt_service_invalid")
        path = MQTT_IDENTITY_FILES[service]
        if path.is_symlink() or not path.is_file():
            raise UpdaterError(f"{service}_mqtt_identity_invalid")
        try:
            raw_identity = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise UpdaterError(f"{service}_mqtt_identity_invalid") from error
        if service == "manager":
            values = {}
            for line in raw_identity.splitlines():
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key in {"GH_MQTT_CLIENT_ID", "GH_MQTT_USERNAME"}:
                    if key in values:
                        raise UpdaterError(
                            "manager_mqtt_identity_duplicate"
                        )
                    values[key] = value
            client_id = values.get("GH_MQTT_CLIENT_ID")
            username = values.get("GH_MQTT_USERNAME")
        else:
            try:
                identity = json.loads(raw_identity)
            except json.JSONDecodeError as error:
                raise UpdaterError(
                    "homeassistant_mqtt_identity_invalid"
                ) from error
            if not isinstance(identity, dict):
                raise UpdaterError(
                    "homeassistant_mqtt_identity_invalid"
                )
            client_id = identity.get("client_id")
            username = identity.get("username")
        if not all(
            isinstance(value, str)
            and re.fullmatch(r"[A-Za-z0-9_.:-]+", value)
            for value in (client_id, username)
        ):
            raise UpdaterError(f"{service}_mqtt_identity_invalid")

        broker = self._runtime("broker")
        logs = self._run(
            (
                "docker",
                "logs",
                "--timestamps",
                "--since",
                broker["started_at"],
                "--tail",
                "10000",
                broker["container_id"],
            ),
            timeout=30,
        ).stdout.decode(errors="replace")
        lines = logs.splitlines()
        if len(lines) >= 10000:
            raise UpdaterError("broker_log_coverage_insufficient")
        connected = re.compile(
            r"New client connected from .+ as "
            + re.escape(client_id)
            + r" \(p5, c[01], k[0-9]+, u'"
            + re.escape(username)
            + r"'\)\."
        )
        any_connection = re.compile(
            r"New client connected from .+ as "
            + re.escape(client_id)
            + r" \("
        )
        terminal = re.compile(
            r"(?:Client|client) "
            + re.escape(client_id)
            + r"(?: \[[^\]\r\n]+\] disconnected(?:\.|:)"
            + r"| disconnected\b| closed its connection\b"
            + r"| already connected, closing old connection\b"
            + r"| has exceeded timeout, disconnecting\b)"
        )
        current = False
        for line in lines:
            if any_connection.search(line):
                if connected.search(line) is None:
                    raise UpdaterError(
                        f"{service}_mqtt_authenticated_identity_mismatch"
                    )
                current = True
                continue
            if terminal.search(line):
                current = False
        return current

    def _homeassistant_http_status(
        self,
        *,
        allow_unavailable: bool = False,
    ) -> int | None:
        connection = http.client.HTTPConnection("127.0.0.1", 8123, timeout=5)
        try:
            try:
                connection.request("GET", "/api/")
                response = connection.getresponse()
                response.read(1024)
                return int(response.status)
            except (OSError, http.client.HTTPException):
                if allow_unavailable:
                    return None
                raise UpdaterError("homeassistant_http_unavailable")
        finally:
            connection.close()

    @staticmethod
    def _converged_health_v2(snapshot: dict[str, Any]) -> bool:
        authenticated = snapshot.get("mqtt_authenticated")
        return (
            snapshot.get("listeners") == EXPECTED_LISTENERS
            and isinstance(authenticated, dict)
            and authenticated.get("manager") is True
            and authenticated.get("homeassistant") is True
            and snapshot.get("homeassistant_http_status") in {200, 401}
        )

    @staticmethod
    def _validate_converged_health_v2(snapshot: dict[str, Any]) -> None:
        if snapshot.get("listeners") != EXPECTED_LISTENERS:
            raise UpdaterError("listener_contract_drift")
        authenticated = snapshot.get("mqtt_authenticated")
        if (
            not isinstance(authenticated, dict)
            or authenticated.get("manager") is not True
            or authenticated.get("homeassistant") is not True
        ):
            raise UpdaterError("mqtt_current_authentication_missing")
        if snapshot.get("homeassistant_http_status") not in {200, 401}:
            raise UpdaterError("homeassistant_http_not_ready")

    def observe_v2(self) -> dict[str, Any]:
        snapshot = self._observe_running_base_v2()
        rendered = snapshot["compose_render"]
        bindings, binding_modes = self._image_binding_authority_v2(rendered)
        services = rendered.get("services")
        if not isinstance(services, dict):
            raise UpdaterError("compose_services_invalid")
        for component in COMPONENTS:
            service = services.get(component)
            if not isinstance(service, dict):
                raise UpdaterError(f"{component}_compose_service_missing")
            if service.get("image") != bindings[component]:
                raise UpdaterError(f"{component}_compose_env_image_drift")
            runtime = snapshot["runtime"].get(component)
            if not isinstance(runtime, dict):
                raise UpdaterError(f"{component}_runtime_missing")
            if runtime.get("image_ref") != bindings[component]:
                raise UpdaterError(f"{component}_runtime_image_drift")
        authenticated = {
            service: self._mqtt_authenticated(service)
            for service in ("manager", "homeassistant")
        }
        return {
            **snapshot,
            "image_bindings": bindings,
            "image_binding_modes": binding_modes,
            "mqtt_authenticated": authenticated,
            "homeassistant_http_status": self._homeassistant_http_status(
                allow_unavailable=True
            ),
        }

    def observe_state_v2(self) -> dict[str, Any]:
        owner_state = self._systemctl("is-active", SERVICES_UNIT)
        counts = {
            name: self._running_count(name)
            for name in ("manager", "homeassistant", "broker")
        }
        bindings, binding_modes = self._image_binding_authority_v2()
        base = {
            "services_owner_state": owner_state,
            "running_counts": counts,
            "image_bindings": bindings,
            "image_binding_modes": binding_modes,
            "listeners": self._listener_snapshot(),
        }
        if (
            owner_state in {"inactive", "failed"}
            and counts["manager"] == 0
            and counts["homeassistant"] == 0
            and counts["broker"] == 1
        ):
            return {
                **base,
                "application_state": "stopped",
                "snapshot": None,
                "health_state": "NOT_RUNNING",
            }
        if (
            owner_state == "active"
            and counts == {"manager": 1, "homeassistant": 1, "broker": 1}
        ):
            snapshot = self.observe_v2()
            return {
                **base,
                "application_state": "running",
                "snapshot": snapshot,
                "health_state": (
                    "HEALTHY"
                    if self._converged_health_v2(snapshot)
                    else "CONVERGING"
                ),
            }
        return {
            **base,
            "application_state": "unresolved",
            "snapshot": None,
            "health_state": "FAILED",
        }

    def inspect_v2(self) -> dict[str, Any]:
        snapshot = self.observe_v2()
        self._validate_converged_health_v2(snapshot)
        return snapshot

    def assert_mutation_safe(self, component: str) -> None:
        if component not in COMPONENTS:
            raise UpdaterError("component_invalid")
        if self._listener_count("tcp", 47112) != 0:
            raise UpdaterError("pairing_or_registration_active")
        if (
            component == "broker"
            and self._systemctl("is-active", CERT_LIFECYCLE_UNIT) == "active"
        ):
            raise UpdaterError("broker_certificate_lifecycle_active")


    def _image_document(self, reference: str) -> dict[str, Any] | None:
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
        if (
            not isinstance(document, list)
            or len(document) != 1
            or not isinstance(document[0], dict)
        ):
            raise UpdaterError("image_inspect_shape_invalid")
        return document[0]

    def image_id(self, reference: str) -> str | None:
        document = self._image_document(reference)
        if document is None:
            return None
        value = document.get("Id")
        if not isinstance(value, str) or IMAGE_ID.fullmatch(value) is None:
            raise UpdaterError("image_id_invalid")
        return value

    def verify_image_archive(
        self,
        reference: str,
        tar_path: Path,
        expected_sha256: str,
    ) -> str:
        try:
            identity = parse_image_archive(
                tar_path,
                expected_archive_sha256=expected_sha256,
                expected_tag=reference,
                platform_os="linux",
                platform_architecture="arm64",
            )
        except PortableImageIdentityError as error:
            raise UpdaterError(
                "target_archive_portable_identity_invalid"
            ) from error
        document = self._image_document(reference)
        if document is None:
            raise UpdaterError("target_image_missing")
        verdict = verify_runtime_document(identity, document)
        if verdict.status != "VERIFIED":
            raise UpdaterError(
                f"target_image_portable_identity_invalid:{verdict.reason}"
            )
        value = verdict.runtime_image_id
        if not isinstance(value, str) or IMAGE_ID.fullmatch(value) is None:
            raise UpdaterError("target_image_runtime_id_invalid")
        return value

    def load_image(self, tar_path: Path) -> None:
        self._run(("docker", "load", "-i", str(tar_path)), timeout=1800)

    def _listener_snapshot(self) -> dict[str, int]:
        return {
            "tcp_8883": self._listener_count("tcp", 8883),
            "tcp_47110": self._listener_count("tcp", 47110),
            "udp_47111": self._listener_count("udp", 47111),
            "tcp_47112": self._listener_count("tcp", 47112),
        }

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
        if self._systemctl("is-active", SERVICES_UNIT) not in {
            "inactive",
            "failed",
        }:
            raise UpdaterError("services_not_inactive")
        if self._running_count("manager") or self._running_count("homeassistant"):
            raise UpdaterError("application_container_still_running")

    def start_services(
        self,
        *,
        readiness_timeout: int = DEFAULT_SERVICES_READINESS_TIMEOUT_SECONDS,
    ) -> None:
        if not isinstance(readiness_timeout, int) or isinstance(readiness_timeout, bool) or readiness_timeout <= 0:
            raise UpdaterError("services_readiness_timeout_invalid")
        self._run(("systemctl", "start", SERVICES_UNIT), timeout=180)
        self.wait_services(timeout=readiness_timeout)

    def wait_services(
        self,
        timeout: int = DEFAULT_SERVICES_READINESS_TIMEOUT_SECONDS,
    ) -> None:
        deadline = time.monotonic() + timeout
        last_soft_state = "services_not_ready"
        while time.monotonic() < deadline:
            unit_state = self._systemctl("is-active", SERVICES_UNIT)
            if unit_state != "active":
                last_soft_state = "services_unit=" + unit_state
                time.sleep(2)
                continue
            try:
                self._container_id("manager")
                self._container_id("homeassistant")
            except UpdaterError:
                last_soft_state = "application_containers_not_ready"
                time.sleep(2)
                continue

            listeners = self._listener_snapshot()
            if listeners != EXPECTED_LISTENERS:
                last_soft_state = "listeners=" + json.dumps(
                    listeners,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                time.sleep(2)
                continue

            snapshot = self.observe_v2()
            if self._converged_health_v2(snapshot):
                return
            authenticated = snapshot.get("mqtt_authenticated") or {}
            last_soft_state = (
                "mqtt_manager="
                + str(authenticated.get("manager"))
                + ",mqtt_homeassistant="
                + str(authenticated.get("homeassistant"))
                + ",ha_http="
                + str(snapshot.get("homeassistant_http_status"))
            )
            time.sleep(2)
        raise UpdaterError(
            "services_readiness_timeout:" + last_soft_state[:120]
        )

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

    def _replace_product_file(
        self,
        path: Path,
        updated: bytes,
        *,
        verify_error: str,
    ) -> str:
        if path.is_symlink() or not path.is_file():
            raise UpdaterError("compose_authority_invalid")
        original = path.read_bytes()
        if original == updated:
            return sha256_bytes(original)
        meta = path.stat()
        fd, raw = tempfile.mkstemp(
            prefix=f".{path.name}.",
            dir=path.parent,
        )
        temporary = Path(raw)
        try:
            os.fchmod(fd, stat.S_IMODE(meta.st_mode))
            with os.fdopen(fd, "wb") as stream:
                stream.write(updated)
                stream.flush()
                os.fsync(stream.fileno())
            os.chown(temporary, meta.st_uid, meta.st_gid)
            os.replace(temporary, path)
            directory = os.open(
                path.parent,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)
        observed = path.read_bytes()
        if observed != updated:
            raise UpdaterError(verify_error)
        return sha256_bytes(observed)

    def _converge_homeassistant_binding(
        self,
        expected: str,
    ) -> str:
        if (
            COMPOSE.is_symlink()
            or not COMPOSE.is_file()
            or COMPOSE_ENV.is_symlink()
            or not COMPOSE_ENV.is_file()
        ):
            raise UpdaterError("compose_authority_invalid")
        original_compose = COMPOSE.read_bytes()
        original_env = COMPOSE_ENV.read_bytes()
        try:
            updated_env = converge_homeassistant_env(
                original_env,
                expected,
                expected,
            )
            updated_compose = converge_homeassistant_compose(
                original_compose,
                expected,
            )
        except Exception as error:
            raise UpdaterError(
                "homeassistant_binding_convergence_invalid"
            ) from error
        try:
            env_sha = self._replace_product_file(
                COMPOSE_ENV,
                updated_env,
                verify_error="compose_env_replace_verify_failed",
            )
            self._replace_product_file(
                COMPOSE,
                updated_compose,
                verify_error="compose_replace_verify_failed",
            )
            return env_sha
        except Exception as error:
            try:
                self._replace_product_file(
                    COMPOSE,
                    original_compose,
                    verify_error="compose_restore_verify_failed",
                )
                self._replace_product_file(
                    COMPOSE_ENV,
                    original_env,
                    verify_error="compose_env_restore_verify_failed",
                )
            except Exception as restore_error:
                raise UpdaterError(
                    "homeassistant_binding_convergence_restore_failed"
                ) from restore_error
            raise UpdaterError(
                "homeassistant_binding_convergence_failed"
            ) from error

    def rewrite_component_image(
        self,
        component: str,
        expected: str,
        replacement: str,
    ) -> str:
        if component not in COMPONENTS:
            raise UpdaterError("component_invalid")
        mode = self.image_binding_modes_v2()[component]
        if mode == "legacy_static":
            if component != "homeassistant":
                raise UpdaterError(
                    f"{component}_runtime_template_convergence_required"
                )
            self._converge_homeassistant_binding(expected)
            original = COMPOSE_ENV.read_bytes()
            try:
                updated = rewrite_component_env(
                    original,
                    component,
                    expected,
                    replacement,
                )
            except Exception as error:
                raise UpdaterError(
                    "component_image_env_rewrite_invalid"
                ) from error
            return self._replace_product_file(
                COMPOSE_ENV,
                updated,
                verify_error="compose_env_replace_verify_failed",
            )
        if mode != "dynamic":
            raise UpdaterError(
                f"{component}_runtime_template_convergence_required"
            )
        if COMPOSE_ENV.is_symlink() or not COMPOSE_ENV.is_file():
            raise UpdaterError("compose_env_invalid")
        original = COMPOSE_ENV.read_bytes()
        try:
            updated = rewrite_component_env(
                original,
                component,
                expected,
                replacement,
            )
        except Exception as error:
            raise UpdaterError("component_image_env_rewrite_invalid") from error
        return self._replace_product_file(
            COMPOSE_ENV,
            updated,
            verify_error="compose_env_replace_verify_failed",
        )

    def restore_component_binding(
        self,
        component: str,
        expected_current: str,
        predecessor: str,
        predecessor_mode: str,
    ) -> None:
        if predecessor_mode == "dynamic":
            if self.component_binding_v2(component) == expected_current:
                self.rewrite_component_image(
                    component,
                    expected_current,
                    predecessor,
                )
            return
        if predecessor_mode != "legacy_static" or component != "homeassistant":
            raise UpdaterError("predecessor_binding_mode_unsupported")
        if (
            COMPOSE.is_symlink()
            or not COMPOSE.is_file()
            or COMPOSE_ENV.is_symlink()
            or not COMPOSE_ENV.is_file()
        ):
            raise UpdaterError("compose_authority_invalid")
        original_compose = COMPOSE.read_bytes()
        original_env = COMPOSE_ENV.read_bytes()
        try:
            restored_compose = restore_homeassistant_compose(
                original_compose,
                predecessor,
            )
            restored_env = restore_homeassistant_env(
                original_env,
                predecessor,
                expected_current,
            )
        except Exception as error:
            raise UpdaterError(
                "homeassistant_binding_restore_invalid"
            ) from error
        try:
            self._replace_product_file(
                COMPOSE,
                restored_compose,
                verify_error="compose_restore_verify_failed",
            )
            self._replace_product_file(
                COMPOSE_ENV,
                restored_env,
                verify_error="compose_env_restore_verify_failed",
            )
            rendered = self.render_compose()
            services = rendered.get("services")
            service = (
                services.get("homeassistant")
                if isinstance(services, dict)
                else None
            )
            if (
                not isinstance(service, dict)
                or service.get("image") != predecessor
            ):
                raise UpdaterError(
                    "homeassistant_binding_restore_render_invalid"
                )
        except Exception as error:
            try:
                self._replace_product_file(
                    COMPOSE,
                    original_compose,
                    verify_error="compose_recovery_verify_failed",
                )
                self._replace_product_file(
                    COMPOSE_ENV,
                    original_env,
                    verify_error="compose_env_recovery_verify_failed",
                )
            except Exception as restore_error:
                raise UpdaterError(
                    "homeassistant_binding_restore_recovery_failed"
                ) from restore_error
            raise UpdaterError("homeassistant_binding_restore_failed") from error

    def stop_broker(self) -> None:
        self._run(("systemctl", "stop", BROKER_UNIT), timeout=120)
        if self._systemctl("is-active", BROKER_UNIT) not in {
            "inactive",
            "failed",
        }:
            raise UpdaterError("broker_not_inactive")
        if self._running_count("broker"):
            raise UpdaterError("broker_container_still_running")

    def wait_broker(self, timeout: int = 120) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if (
                self._systemctl("is-active", BROKER_UNIT) == "active"
                and self._listener_count("tcp", 8883) == 1
            ):
                try:
                    self._container_id("broker")
                    return
                except UpdaterError:
                    pass
            time.sleep(2)
        raise UpdaterError("broker_readiness_timeout")

    def start_broker(self) -> None:
        self._run(("systemctl", "start", BROKER_UNIT), timeout=120)
        self.wait_broker()

    def _acquire_broker_certificate_guard(self) -> None:
        if self._component_guard_fd is not None:
            return
        path = BROKER_CERT_LIFECYCLE_LOCK
        if path.is_symlink() or not path.is_file():
            raise UpdaterError("broker_certificate_lifecycle_lock_missing")
        descriptor = os.open(path, os.O_RDWR)
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) & 0o077
            ):
                raise UpdaterError(
                    "broker_certificate_lifecycle_lock_unsafe"
                )
            try:
                fcntl.flock(
                    descriptor,
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
            except BlockingIOError as error:
                raise UpdaterError(
                    "broker_certificate_lifecycle_busy"
                ) from error
            self._component_guard_fd = descriptor
        except Exception:
            os.close(descriptor)
            raise

    def release_component_guard(self) -> None:
        descriptor = self._component_guard_fd
        self._component_guard_fd = None
        if descriptor is None:
            return
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    def quiesce_component(self, component: str) -> None:
        if component not in COMPONENTS:
            raise UpdaterError("component_invalid")
        if component == "broker":
            self._acquire_broker_certificate_guard()
            self.stop_services()
            self.stop_broker()
            return
        self.stop_services()

    def activate_component(self, component: str) -> None:
        if component not in COMPONENTS:
            raise UpdaterError("component_invalid")
        if component == "broker":
            self.start_broker()
            self.start_services()
            return
        if component == "homeassistant":
            self.start_services(
                readiness_timeout=HOMEASSISTANT_SERVICES_READINESS_TIMEOUT_SECONDS,
            )
            return
        self.start_services()

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
