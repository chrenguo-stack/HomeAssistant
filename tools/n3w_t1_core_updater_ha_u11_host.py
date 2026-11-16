from __future__ import annotations

import json
import time
from pathlib import Path

from n3w_t1_core_updater_common import (
    BROKER_UNIT,
    SERVICES_UNIT,
    UpdaterError,
)
from n3w_t1_core_updater_ha_u11 import U11RuntimeEvidence
from n3w_t1_core_updater_host import LocalHost


PRODUCTION_HA_CONFIG = "/var/lib/n3wfc4-homeassistant"
HA_OTA_COMPOSE = (
    "/opt/HomeAssistant/infra/n3w-t1/production/docker-compose.ha-ota.yml"
)
EXPECTED_U11_EXECSTART = (
    "ExecStart=/usr/bin/docker compose "
    "--project-name ${N3WFC4_COMPOSE_PROJECT_NAME} "
    "--env-file ${N3WFC4_COMPOSE_ENV_FILE} "
    "-f ${N3WFC4_COMPOSE_FILE} "
    f"-f {HA_OTA_COMPOSE} "
    "--profile application up --no-deps --no-log-prefix "
    "--abort-on-container-exit manager homeassistant"
)
EXPECTED_U11_EXECSTOP = (
    "ExecStop=/usr/bin/docker compose "
    "--project-name ${N3WFC4_COMPOSE_PROJECT_NAME} "
    "--env-file ${N3WFC4_COMPOSE_ENV_FILE} "
    "-f ${N3WFC4_COMPOSE_FILE} "
    f"-f {HA_OTA_COMPOSE} stop homeassistant manager"
)
START_TIMEOUT_SECONDS = 180


class LocalU11RuntimeOwner:
    """Narrow U11 adapter over the existing production host primitives.

    This adapter intentionally stops before U12 health acceptance. It uses the
    production systemd owner to start Manager + Home Assistant together, then
    proves only runtime identity and the preserved /config mount.
    """

    def __init__(
        self,
        *,
        expected_manager_container_id: str,
        expected_manager_image_ref: str,
        expected_manager_runtime_image_id: str,
        expected_broker_container_id: str,
        expected_broker_image_ref: str,
        expected_broker_runtime_image_id: str,
        host: LocalHost | None = None,
    ) -> None:
        self.host = host or LocalHost()
        self.expected_manager_container_id = expected_manager_container_id
        self.expected_manager_image_ref = expected_manager_image_ref
        self.expected_manager_runtime_image_id = (
            expected_manager_runtime_image_id
        )
        self.expected_broker_container_id = expected_broker_container_id
        self.expected_broker_image_ref = expected_broker_image_ref
        self.expected_broker_runtime_image_id = expected_broker_runtime_image_id

    def target_image_id(self, image_ref: str) -> str | None:
        return self.host.image_id(image_ref)

    def homeassistant_binding(self) -> str:
        return self.host.component_binding_v2("homeassistant")

    def load_target_archive(self, archive: Path) -> None:
        self.host.load_image(archive)

    def verify_loaded_target(
        self,
        *,
        image_ref: str,
        archive: Path,
        expected_archive_sha256: str,
    ) -> str:
        return self.host.verify_image_archive(
            image_ref,
            archive,
            expected_archive_sha256,
        )

    def publish_homeassistant_target_binding(
        self,
        *,
        expected_predecessor: str,
        target: str,
    ) -> None:
        self.host.rewrite_component_image(
            "homeassistant",
            expected_predecessor,
            target,
        )

    def _exact_peer(
        self,
        service: str,
        *,
        expected_container_id: str,
        expected_image_ref: str,
        expected_runtime_image_id: str,
    ) -> dict[str, object]:
        runtime = self.host._runtime(service)
        if (
            runtime.get("container_id") != expected_container_id
            or runtime.get("image_ref") != expected_image_ref
            or runtime.get("image_id") != expected_runtime_image_id
            or runtime.get("restart_count") != 0
        ):
            raise UpdaterError("u11_peer_identity_drift:" + service)
        return runtime

    def _production_config_mounted(self, container_id: str) -> bool:
        try:
            document = json.loads(
                self.host._run(
                    ("docker", "inspect", container_id),
                    timeout=45,
                ).stdout
            )
        except json.JSONDecodeError as error:
            raise UpdaterError("u11_homeassistant_inspect_invalid") from error
        if (
            not isinstance(document, list)
            or len(document) != 1
            or not isinstance(document[0], dict)
        ):
            raise UpdaterError("u11_homeassistant_inspect_invalid")
        mounts = document[0].get("Mounts")
        if not isinstance(mounts, list):
            raise UpdaterError("u11_homeassistant_mounts_invalid")
        matches = [
            row
            for row in mounts
            if isinstance(row, dict)
            and row.get("Type") == "bind"
            and row.get("Source") == PRODUCTION_HA_CONFIG
            and row.get("Destination") == "/config"
            and row.get("RW") is True
        ]
        return len(matches) == 1

    def _require_prestart_owner_state(self) -> None:
        self.host._activation_env()
        self.host._service_unit(
            expected_execstart=EXPECTED_U11_EXECSTART,
            expected_execstop=EXPECTED_U11_EXECSTOP,
        )
        if self.host._systemctl("is-active", BROKER_UNIT) != "active":
            raise UpdaterError("u11_broker_owner_not_active")
        if self.host._systemctl("is-active", SERVICES_UNIT) not in {
            "inactive",
            "failed",
        }:
            raise UpdaterError("u11_services_owner_not_quiesced")
        if self.host._running_count("manager") != 0:
            raise UpdaterError("u11_manager_running_before_start")
        if self.host._running_count("homeassistant") != 0:
            raise UpdaterError("u11_homeassistant_running_before_start")
        if self.host._running_count("broker") != 1:
            raise UpdaterError("u11_broker_runtime_invalid")

    def start_target_owner(
        self,
        *,
        target_image_ref: str,
        target_runtime_image_id: str,
    ) -> U11RuntimeEvidence:
        self._require_prestart_owner_state()
        self.host._run(
            ("systemctl", "start", SERVICES_UNIT),
            timeout=START_TIMEOUT_SECONDS,
        )

        deadline = time.monotonic() + START_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            owner_active = (
                self.host._systemctl("is-active", SERVICES_UNIT) == "active"
            )
            counts = {
                "manager": self.host._running_count("manager"),
                "homeassistant": self.host._running_count("homeassistant"),
                "broker": self.host._running_count("broker"),
            }
            if owner_active and counts == {
                "manager": 1,
                "homeassistant": 1,
                "broker": 1,
            }:
                break
            time.sleep(1)
        else:
            raise UpdaterError("u11_target_owner_start_timeout")

        self._exact_peer(
            "manager",
            expected_container_id=self.expected_manager_container_id,
            expected_image_ref=self.expected_manager_image_ref,
            expected_runtime_image_id=self.expected_manager_runtime_image_id,
        )
        self._exact_peer(
            "broker",
            expected_container_id=self.expected_broker_container_id,
            expected_image_ref=self.expected_broker_image_ref,
            expected_runtime_image_id=self.expected_broker_runtime_image_id,
        )

        homeassistant = self.host._runtime("homeassistant")
        if (
            homeassistant.get("image_ref") != target_image_ref
            or homeassistant.get("image_id") != target_runtime_image_id
        ):
            raise UpdaterError("u11_homeassistant_target_identity_drift")

        container_id = homeassistant.get("container_id")
        if not isinstance(container_id, str) or not self._production_config_mounted(
            container_id
        ):
            raise UpdaterError("u11_homeassistant_production_config_missing")

        return U11RuntimeEvidence(
            owner_active=True,
            manager_running=True,
            broker_running=True,
            homeassistant_running=True,
            target_image_ref=target_image_ref,
            target_runtime_image_id=target_runtime_image_id,
            production_config_mounted=True,
        )
