from __future__ import annotations

import base64
import json
from pathlib import Path

from greenhouse_manager.runtime.n3w_relay_ingress_legacy import (
    RelayEnvelope,
    aes256gcm_decrypt,
    build_aad,
    derive_nonce,
    parse_relay_envelope,
)

ROOT = Path(__file__).resolve().parents[2]
VECTOR_PATH = ROOT / "protocols/transport/n3w-p4a-test-vector-v1.json"
STAGE_PATH = (
    ROOT / "docs/decisions/n3w-esp32c6-frame-boot-keystate-core-stage-entry.json"
)
CORE_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_core.cpp"
NVS_CPP = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core/n3w_esp32_nvs.cpp"


def _vector() -> dict[str, object]:
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


def _envelope(vector: dict[str, object]) -> RelayEnvelope:
    return RelayEnvelope(
        schema="gh.relay/1",
        transport="esp_now",
        gateway_id=str(vector["gateway_id"]),
        node_id=str(vector["node_id"]),
        hop_count=1,
        key_epoch=int(vector["key_epoch"]),
        boot_id=str(vector["boot_id"]),
        seq=int(vector["seq"]),
        nonce=bytes.fromhex(str(vector["nonce_hex"])),
        ciphertext=bytes.fromhex(str(vector["ciphertext_hex"])),
        tag=bytes.fromhex(str(vector["tag_hex"])),
    )


def test_fixed_vector_matches_manager_nonce_aad_and_aes256gcm() -> None:
    vector = _vector()
    envelope = _envelope(vector)

    assert derive_nonce(envelope.boot_id, envelope.seq) == bytes.fromhex(
        str(vector["nonce_hex"])
    )
    assert build_aad(envelope).decode("utf-8") == vector["aad_utf8"]

    plaintext = aes256gcm_decrypt(
        key=bytes.fromhex(str(vector["key_hex"])),
        nonce=envelope.nonce,
        ciphertext=envelope.ciphertext,
        tag=envelope.tag,
        aad=build_aad(envelope),
    )
    assert plaintext.decode("utf-8") == vector["plaintext_json"]

    telemetry = json.loads(plaintext)
    assert telemetry["schema"] == "gh.telemetry/1"
    assert telemetry["node_id"] == vector["node_id"]
    assert telemetry["boot_id"] == vector["boot_id"]
    assert telemetry["seq"] == vector["seq"]


def test_fixed_vector_forms_manager_accepted_outer_envelope() -> None:
    vector = _vector()
    outer = {
        "schema": "gh.relay/1",
        "transport": "esp_now",
        "gateway_id": vector["gateway_id"],
        "node_id": vector["node_id"],
        "hop_count": 1,
        "key_epoch": vector["key_epoch"],
        "boot_id": vector["boot_id"],
        "seq": vector["seq"],
        "nonce_b64": vector["nonce_b64"],
        "ciphertext_b64": vector["ciphertext_b64"],
        "tag_b64": vector["tag_b64"],
    }
    parsed = parse_relay_envelope(
        json.dumps(outer, separators=(",", ":")).encode("utf-8")
    )
    assert parsed.nonce == base64.b64decode(str(vector["nonce_b64"]))
    assert parsed.ciphertext == bytes.fromhex(str(vector["ciphertext_hex"]))
    assert parsed.tag == bytes.fromhex(str(vector["tag_hex"]))


def test_stage_entry_binds_authorization_and_physical_n2_baseline() -> None:
    doc = json.loads(STAGE_PATH.read_text(encoding="utf-8"))
    assert doc["authorization_gate"] == (
        "D1-N3W-ESP32C6-SINGLEHOP-FRAME-BOOT-AND-KEYSTATE-CORE-"
        "HOSTONLY-DEVELOPMENT-20260807-01"
    )
    assert doc["base_ref"] == "main"
    assert doc["base_sha"] == "b87432cf58631c43781c403e010272b60d32fcf1"
    assert doc["preserved_pr_head"] == "239ea594c643d4990d449187f8b0cabae619e3d7"

    binding = doc["n2_physical_accepted_firmware_binding"]
    assert binding["source_pr"] == 204
    assert binding["source_head_sha"] == "8d76634adb171c6492e51a5ebd855bcd52bcf073"
    assert binding["target_blob_sha"] == "9dc8f766287e3cb47baf3e1f727635a85848e469"
    assert binding["board"] == "esp32-c6-devkitm-1"
    assert binding["variant"] == "ESP32C6"
    assert binding["framework"] == "esp-idf"
    assert binding["present_on_current_main"] is False

    assert doc["p4a_contract"]["esp_now_radio_runtime"] is False
    assert all(value is False for value in doc["safety_boundary"].values())


def test_p4a_source_has_no_esp_now_radio_api_or_embedded_production_key() -> None:
    source = CORE_CPP.read_text(encoding="utf-8")
    nvs_source = NVS_CPP.read_text(encoding="utf-8")
    combined = source + "\n" + nvs_source

    forbidden_radio_tokens = (
        "esp_now_init(",
        "esp_now_send(",
        "esp_now_add_peer(",
        "esp_now_register_recv_cb(",
        "esp_now_register_send_cb(",
    )
    assert all(token not in combined for token in forbidden_radio_tokens)

    # P4a keeps application-key persistence behind an abstract port. The only
    # ESP32 persistence adapter implemented here is the monotonic boot session.
    assert "ApplicationKeyStore" not in nvs_source
    assert "mqtt_password" not in combined
