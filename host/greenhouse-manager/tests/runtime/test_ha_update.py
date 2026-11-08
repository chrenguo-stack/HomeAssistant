from __future__ import annotations

import json
from pathlib import Path

from greenhouse_manager.runtime.ha_update import HomeAssistantUpdateSurface
from greenhouse_manager.runtime.service_identity_plan import (
    build_service_identity_plan,
)
from greenhouse_manager.runtime.t1_ota_manager import (
    OtaRuntimeSnapshot,
    T1OtaManager,
)


def approved_manifest() -> dict:
    target_path = (
        Path(__file__).resolve().parents[4]
        / "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json"
    )
    return {
        "schema": "gh.n3w-t1-ota-approved-manifest/1",
        "approval_status": "APPROVED",
        "signature_status": "VERIFIED",
        "validity_status": "VALID",
        "verification_status": "PASS",
        "version": "2026.10.4",
        "release_identity": "homeassistant-2026.10.4",
        "target_archive_size_bytes": 835309535,
        "target": json.loads(target_path.read_text(encoding="utf-8")),
    }


class Provider:
    def get_approved_homeassistant_manifest(self):
        return approved_manifest()


class Runtime:
    def __init__(
        self,
        phase: str,
        progress: int | None = None,
        *,
        installed_version: str | None = None,
        usb_model: str | None = None,
        usb_capacity: int | None = None,
        usb_confirmation_required: bool = False,
    ) -> None:
        self.phase = phase
        self.progress = progress
        self.installed_version = installed_version
        self.usb_model = usb_model
        self.usb_capacity = usb_capacity
        self.usb_confirmation_required = usb_confirmation_required

    def get_homeassistant_ota_runtime_state(self) -> OtaRuntimeSnapshot:
        return OtaRuntimeSnapshot(
            phase=self.phase,
            progress_percent=self.progress,
            installed_version=self.installed_version,
            usb_candidate_model=self.usb_model,
            usb_candidate_capacity_bytes=self.usb_capacity,
            usb_confirmation_required=self.usb_confirmation_required,
        )


def projection(phase: str):
    runtime = Runtime(phase)
    ota = T1OtaManager(
        installed_version="2026.10.0",
        manifest_provider=Provider(),
        runtime_state_provider=runtime,
    )
    return ota.project()


def by_topic(messages):
    return {message.topic: message for message in messages}


def test_update_and_prepare_discovery_are_separate_before_prepare() -> None:
    surface = HomeAssistantUpdateSurface(system_id="system-001")
    projected = projection("DISCOVERED")

    messages = by_topic(
        surface.messages(
            manifest=projected.manifest,
            status=projected.status,
        )
    )

    update = messages["homeassistant/update/n3w_t1_homeassistant/config"]
    prepare = messages["homeassistant/button/n3w_t1_homeassistant_prepare/config"]
    assert "device_class" not in update.payload
    assert "command_topic" not in update.payload
    assert prepare.payload["command_topic"] == (
        "gh/v1/system-001/control/t1/homeassistant/ota"
    )
    assert '"action":"PREPARE"' in prepare.payload["payload_press"]
    assert update.retain is True
    assert prepare.retain is True


def test_r7a_ready_to_install_is_status_only_without_install_command() -> None:
    surface = HomeAssistantUpdateSurface(system_id="system-001")
    projected = projection("READY_TO_INSTALL")

    messages = by_topic(
        surface.messages(
            manifest=projected.manifest,
            status=projected.status,
        )
    )

    update = messages["homeassistant/update/n3w_t1_homeassistant/config"]
    prepare = messages["homeassistant/button/n3w_t1_homeassistant_prepare/config"]
    assert "command_topic" not in update.payload
    assert "payload_install" not in update.payload
    assert prepare.payload == b""


def test_state_and_attributes_expose_only_public_projection() -> None:
    surface = HomeAssistantUpdateSurface(system_id="system-001")
    runtime = Runtime("TARGET_DOWNLOADING_VERIFYING", 37)
    ota = T1OtaManager(
        installed_version="2026.10.0",
        manifest_provider=Provider(),
        runtime_state_provider=runtime,
    )
    projected = ota.project()

    messages = by_topic(
        surface.messages(
            manifest=projected.manifest,
            status=projected.status,
        )
    )
    state = messages["gh/v1/system-001/state/t1/homeassistant/ota"].payload
    attributes = messages[
        "gh/v1/system-001/state/t1/homeassistant/ota/attributes"
    ].payload

    assert state == {
        "installed_version": "2026.10.0",
        "latest_version": "2026.10.4",
        "title": "Home Assistant",
        "in_progress": True,
        "update_percentage": 37,
    }
    assert attributes == {
        "installed_version": "2026.10.0",
        "latest_approved_version": "2026.10.4",
        "update_available": True,
        "ota_phase": "TARGET_DOWNLOADING_VERIFYING",
        "progress_percent_or_null": 37,
        "ready_to_install": False,
        "in_progress": True,
        "error_code_or_null": None,
        "usb_candidate_model_or_null": None,
        "usb_candidate_capacity_bytes_or_null": None,
        "usb_confirmation_required": False,
    }
    encoded = repr((state, attributes))
    for forbidden in (
        "/dev/",
        "/var/",
        "authorization",
        "usb_serial",
        "target_image_ref",
        "target_archive_sha256",
    ):
        assert forbidden not in encoded


def test_usb_erase_confirmation_button_names_exact_public_candidate() -> None:
    surface = HomeAssistantUpdateSurface(system_id="system-001")
    runtime = Runtime(
        "USB_REQUIRED_CONFIRMATION",
        installed_version="2026.10.0",
        usb_model="Kingston DataTraveler",
        usb_capacity=16 * 1024**3,
        usb_confirmation_required=True,
    )
    ota = T1OtaManager(
        installed_version="2026.10.0",
        manifest_provider=Provider(),
        runtime_state_provider=runtime,
    )
    projected = ota.project()

    messages = by_topic(
        surface.messages(
            manifest=projected.manifest,
            status=projected.status,
        )
    )
    prepare = messages[
        "homeassistant/button/n3w_t1_homeassistant_prepare/config"
    ]
    confirm = messages[
        "homeassistant/button/n3w_t1_homeassistant_confirm_usb/config"
    ]

    assert prepare.payload == b""
    assert "Kingston DataTraveler" in confirm.payload["name"]
    assert "16.0 GiB" in confirm.payload["name"]
    assert '"action":"CONFIRM_USB_ERASE"' in confirm.payload["payload_press"]
    encoded = json.dumps(confirm.payload, ensure_ascii=False)
    for forbidden in ("/dev/", "mount", "docker", "authorization", "serial"):
        assert forbidden not in encoded.lower()


def test_usb_confirmation_button_is_tombstoned_while_waiting_for_media() -> None:
    surface = HomeAssistantUpdateSurface(system_id="system-001")
    projected = projection("USB_REQUIRED")
    messages = by_topic(
        surface.messages(
            manifest=projected.manifest,
            status=projected.status,
        )
    )

    assert messages[
        "homeassistant/button/n3w_t1_homeassistant_prepare/config"
    ].payload == b""
    assert messages[
        "homeassistant/button/n3w_t1_homeassistant_confirm_usb/config"
    ].payload == b""


def test_ota_discovery_topics_are_authorized_by_manager_service_identity() -> None:
    surface = HomeAssistantUpdateSurface(system_id="system-001")
    projected = projection("DISCOVERED")
    messages = surface.messages(
        manifest=projected.manifest,
        status=projected.status,
    )

    discovery_topics = {
        message.topic
        for message in messages
        if message.topic.startswith("homeassistant/")
    }
    plan = build_service_identity_plan(
        system_id="system-001",
        service="manager",
        generation=1,
    )
    allowed_publish_topics = {
        acl.topic
        for acl in plan.acls
        if acl.allow and acl.acl_type == "publishClientSend"
    }

    assert discovery_topics == {
        "homeassistant/update/n3w_t1_homeassistant/config",
        "homeassistant/button/n3w_t1_homeassistant_prepare/config",
        "homeassistant/button/n3w_t1_homeassistant_confirm_usb/config",
    }
    assert discovery_topics <= allowed_publish_topics
    assert "homeassistant/#" not in allowed_publish_topics
