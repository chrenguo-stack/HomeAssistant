from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .ha_discovery import _manager_version
from .ingest import PublishMessage
from .t1_ota_manager import ApprovedManifest, OtaStatus
from .topics import (
    t1_homeassistant_ota_attributes_topic,
    t1_homeassistant_ota_control_topic,
    t1_homeassistant_ota_state_topic,
)


def _intent_payload(action: str, release_identity: str) -> str:
    return json.dumps(
        {
            "action": action,
            "target_release_id": release_identity,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


@dataclass(frozen=True, slots=True)
class HomeAssistantUpdateSurface:
    system_id: str
    prefix: str = "homeassistant"

    @property
    def update_discovery_topic(self) -> str:
        return f"{self.prefix}/update/n3w_t1_homeassistant/config"

    @property
    def prepare_discovery_topic(self) -> str:
        return f"{self.prefix}/button/n3w_t1_homeassistant_prepare/config"

    @property
    def confirm_usb_discovery_topic(self) -> str:
        return f"{self.prefix}/button/n3w_t1_homeassistant_confirm_usb/config"

    def _device_info(self) -> dict[str, Any]:
        return {
            "identifiers": [f"gh_{self.system_id}_t1"],
            "name": "N3-W T1",
            "manufacturer": "Greenhouse Monitoring System",
            "model": "N3-W T1 Edge Host",
        }

    @staticmethod
    def _origin() -> dict[str, str]:
        return {
            "name": "greenhouse-manager",
            "sw_version": _manager_version(),
        }

    def _update_discovery(
        self,
        *,
        manifest: ApprovedManifest | None,
        status: OtaStatus,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": "Home Assistant",
            "unique_id": f"n3w_{self.system_id}_t1_homeassistant_update",
            "device": self._device_info(),
            "origin": self._origin(),
            "state_topic": t1_homeassistant_ota_state_topic(self.system_id),
            "json_attributes_topic": t1_homeassistant_ota_attributes_topic(
                self.system_id
            ),
            "qos": 1,
            "retain": False,
        }
        return payload

    def _prepare_discovery(
        self,
        *,
        manifest: ApprovedManifest,
    ) -> dict[str, Any]:
        return {
            "name": "准备 Home Assistant 升级",
            "unique_id": f"n3w_{self.system_id}_t1_homeassistant_prepare",
            "device": self._device_info(),
            "origin": self._origin(),
            "entity_category": "config",
            "command_topic": t1_homeassistant_ota_control_topic(self.system_id),
            "payload_press": _intent_payload(
                "PREPARE",
                manifest.release_identity,
            ),
            "qos": 1,
            "retain": False,
        }

    def _confirm_usb_discovery(
        self,
        *,
        manifest: ApprovedManifest,
        status: OtaStatus,
    ) -> dict[str, Any]:
        if (
            status.usb_confirmation_required is not True
            or status.usb_candidate_model_or_null is None
            or status.usb_candidate_capacity_bytes_or_null is None
        ):
            raise ValueError("usb confirmation surface requires a visible candidate")
        gib = status.usb_candidate_capacity_bytes_or_null / (1024**3)
        return {
            "name": (
                "确认清空升级 U 盘："
                f"{status.usb_candidate_model_or_null} ({gib:.1f} GiB)"
            ),
            "unique_id": f"n3w_{self.system_id}_t1_homeassistant_confirm_usb",
            "device": self._device_info(),
            "origin": self._origin(),
            "entity_category": "config",
            "command_topic": t1_homeassistant_ota_control_topic(self.system_id),
            "payload_press": _intent_payload(
                "CONFIRM_USB_ERASE",
                manifest.release_identity,
            ),
            "qos": 1,
            "retain": False,
        }

    @staticmethod
    def _state_payload(status: OtaStatus) -> dict[str, Any]:
        return {
            "installed_version": status.installed_version,
            "latest_version": status.latest_approved_version,
            "title": "Home Assistant",
            "in_progress": status.in_progress,
            "update_percentage": status.progress_percent_or_null,
        }

    @staticmethod
    def _attributes_payload(status: OtaStatus) -> dict[str, Any]:
        return {
            "installed_version": status.installed_version,
            "latest_approved_version": status.latest_approved_version,
            "update_available": status.update_available,
            "ota_phase": status.ota_phase,
            "progress_percent_or_null": status.progress_percent_or_null,
            "ready_to_install": status.ready_to_install,
            "in_progress": status.in_progress,
            "error_code_or_null": status.error_code_or_null,
            "usb_candidate_model_or_null": status.usb_candidate_model_or_null,
            "usb_candidate_capacity_bytes_or_null": (
                status.usb_candidate_capacity_bytes_or_null
            ),
            "usb_confirmation_required": status.usb_confirmation_required,
        }

    def messages(
        self,
        *,
        manifest: ApprovedManifest | None,
        status: OtaStatus,
    ) -> tuple[PublishMessage, ...]:
        messages: list[PublishMessage] = [
            PublishMessage(
                topic=self.update_discovery_topic,
                payload=self._update_discovery(
                    manifest=manifest,
                    status=status,
                ),
                qos=1,
                retain=True,
            )
        ]

        prepare_visible = (
            manifest is not None
            and status.update_available
            and status.ota_phase
            in {"DISCOVERED", "COMMITTED", "ROLLED_BACK", "ERROR"}
            and not status.ready_to_install
            and not status.in_progress
        )
        if prepare_visible:
            assert manifest is not None
            messages.append(
                PublishMessage(
                    topic=self.prepare_discovery_topic,
                    payload=self._prepare_discovery(manifest=manifest),
                    qos=1,
                    retain=True,
                )
            )
        else:
            messages.append(
                PublishMessage(
                    topic=self.prepare_discovery_topic,
                    payload=b"",
                    qos=1,
                    retain=True,
                )
            )

        confirm_visible = (
            manifest is not None
            and status.update_available
            and status.usb_confirmation_required
            and status.ota_phase == "USB_REQUIRED_CONFIRMATION"
        )
        if confirm_visible:
            assert manifest is not None
            messages.append(
                PublishMessage(
                    topic=self.confirm_usb_discovery_topic,
                    payload=self._confirm_usb_discovery(
                        manifest=manifest,
                        status=status,
                    ),
                    qos=1,
                    retain=True,
                )
            )
        else:
            messages.append(
                PublishMessage(
                    topic=self.confirm_usb_discovery_topic,
                    payload=b"",
                    qos=1,
                    retain=True,
                )
            )

        messages.extend(
            (
                PublishMessage(
                    topic=t1_homeassistant_ota_state_topic(self.system_id),
                    payload=self._state_payload(status),
                    qos=1,
                    retain=True,
                ),
                PublishMessage(
                    topic=t1_homeassistant_ota_attributes_topic(self.system_id),
                    payload=self._attributes_payload(status),
                    qos=1,
                    retain=True,
                ),
            )
        )
        return tuple(messages)
