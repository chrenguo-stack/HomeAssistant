from __future__ import annotations

import json
from pathlib import Path

from greenhouse_manager.runtime.ha_update import HomeAssistantUpdateSurface
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
    def __init__(self, phase: str, progress: int | None = None) -> None:
        self.phase = phase
        self.progress = progress

    def get_homeassistant_ota_runtime_state(self) -> OtaRuntimeSnapshot:
        return OtaRuntimeSnapshot(
            phase=self.phase,
            progress_percent=self.progress,
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


def test_install_command_appears_only_when_ready_to_install() -> None:
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
    assert update.payload["command_topic"] == (
        "gh/v1/system-001/control/t1/homeassistant/ota"
    )
    assert '"action":"INSTALL"' in update.payload["payload_install"]
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
