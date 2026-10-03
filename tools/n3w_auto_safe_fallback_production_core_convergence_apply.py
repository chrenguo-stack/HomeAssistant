from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_product_core"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one preimage, found {count}")
    if new in text:
        raise RuntimeError(f"{label}: postimage already present")
    return text.replace(old, new, 1)


def update(path: Path, transform) -> None:
    before = path.read_text(encoding="utf-8")
    after = transform(before)
    if after == before:
        raise RuntimeError(f"{path}: no change")
    path.write_text(after, encoding="utf-8")


def patch_runtime_header(text: str) -> str:
    old = """  virtual bool send_encrypted_peer(\n      const MacAddress &peer_mac,\n      const uint8_t *data,\n      std::size_t size) = 0;\n  virtual uint8_t last_channel_observed() const { return 0; }\n"""
    new = """  virtual bool send_encrypted_peer(\n      const MacAddress &peer_mac,\n      const uint8_t *data,\n      std::size_t size) = 0;\n  virtual void on_direct_recovery_probe_tick(bool success) { (void) success; }\n  virtual void on_direct_recovery_commit_result(bool committed) { (void) committed; }\n  virtual uint8_t last_channel_observed() const { return 0; }\n"""
    return replace_once(text, old, new, "runtime-header-hooks")


def patch_runtime_cpp(text: str) -> str:
    old = """SimpleProductError SimpleProductRuntime::note_direct_recovery_probe(bool success) {\n  if (!started_) return SimpleProductError::NOT_READY;\n\n  // Direct is committed only after the concrete radio has already recovered.\n"""
    new = """SimpleProductError SimpleProductRuntime::note_direct_recovery_probe(bool success) {\n  if (!started_) return SimpleProductError::NOT_READY;\n  if (port_ != nullptr) port_->on_direct_recovery_probe_tick(success);\n\n  // Direct is committed only after the concrete radio has already recovered.\n"""
    text = replace_once(text, old, new, "runtime-probe-hook")

    start_marker = "DirectRecoveryCommitResult SimpleProductRuntime::commit_direct_recovery_before("
    end_marker = "SimpleProductError SimpleProductRuntime::note_relay_delivery_result("
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0 or end <= start:
        raise RuntimeError("runtime-commit-function: boundaries not found")
    block = text[start:end]
    if "on_direct_recovery_commit_result" in block:
        raise RuntimeError("runtime-commit-function: hook already present")
    anchor = """  DirectRecoveryCommitResult result;\n  result.completed_at_ms = clock_ != nullptr ? clock_->now_ms() : 0;\n\n"""
    if block.count(anchor) != 1:
        raise RuntimeError("runtime-commit-function: result anchor mismatch")
    block = block.replace(
        anchor,
        anchor
        + """  const auto finish = [&](bool committed) {\n    if (port_ != nullptr) port_->on_direct_recovery_commit_result(committed);\n  };\n\n""",
        1,
    )
    return_count = len(re.findall(r"(?m)^\s*return result;$", block))
    if return_count < 2:
        raise RuntimeError(
            f"runtime-commit-function: unexpected return count {return_count}"
        )
    block, replaced = re.subn(
        r"(?m)^(\s*)return result;$",
        r"\1finish(result.committed);\n\1return result;",
        block,
    )
    if replaced != return_count:
        raise RuntimeError("runtime-commit-function: return rewrite mismatch")
    return text[:start] + block + text[end:]


def patch_component_header(text: str) -> str:
    old = """#include \"n3w_esp32_pairing_nvs.h\"\n#include \"n3w_esp32_runtime_nvs.h\"\n#include \"n3w_espnow_driver.h\"\n#include \"n3w_product_noop_diagnostics.h\"\n#include \"n3w_direct_recovery_policy.h\"\n#include \"n3w_recovery_exit_policy.h\"\n"""
    new = """#include \"n3w_broker_relocation_policy.h\"\n#include \"n3w_esp32_manager_discovery.h\"\n#include \"n3w_esp32_manager_discovery_session.h\"\n#include \"n3w_esp32_pairing_nvs.h\"\n#include \"n3w_esp32_runtime_nvs.h\"\n#include \"n3w_espnow_driver.h\"\n#include \"n3w_product_noop_diagnostics.h\"\n#include \"n3w_direct_recovery_policy.h\"\n#include \"n3w_recovery_exit_policy.h\"\n"""
    text = replace_once(text, old, new, "component-includes")

    old = """  bool send_encrypted_peer(\n      const MacAddress &peer_mac,\n      const uint8_t *data,\n      std::size_t size) override;\n  uint8_t last_channel_observed() const override { return last_channel_observed_; }\n"""
    new = """  bool send_encrypted_peer(\n      const MacAddress &peer_mac,\n      const uint8_t *data,\n      std::size_t size) override;\n  void on_direct_recovery_probe_tick(bool success) override;\n  void on_direct_recovery_commit_result(bool committed) override;\n  uint8_t last_channel_observed() const override { return last_channel_observed_; }\n"""
    text = replace_once(text, old, new, "component-overrides")

    old = """  TelemetrySubmitDisposition flush_telemetry_queue_(\n      TelemetryPathAccounting accounting =\n          TelemetryPathAccounting::TRANSPORT_ONLY);\n  bool http_post_(\n"""
    new = """  TelemetrySubmitDisposition flush_telemetry_queue_(\n      TelemetryPathAccounting accounting =\n          TelemetryPathAccounting::TRANSPORT_ONLY);\n  void reset_broker_relocation_attempt_();\n  void advance_broker_relocation_();\n  bool start_broker_discovery_();\n  bool finish_broker_discovery_();\n  bool start_next_broker_candidate_();\n  bool retarget_runtime_broker_(const std::string &host, bool reconnect);\n  void rollback_broker_candidate_();\n  bool current_wifi_ipv4_(\n      std::string *local_ipv4,\n      std::string *subnet_mask) const;\n  bool http_post_(\n"""
    text = replace_once(text, old, new, "component-relocation-methods")

    old = """  ProvisionedPeerStateV2 peer_state_{};\n  ProvisionedBrokerStateV2 broker_state_{};\n  EspNowDriver radio_{};\n"""
    new = """  ProvisionedPeerStateV2 peer_state_{};\n  ProvisionedBrokerStateV2 broker_state_{};\n  bool broker_relocation_initialized_{false};\n  bool broker_discovery_attempted_{false};\n  bool broker_discovery_ever_started_{false};\n  bool broker_candidate_active_{false};\n  bool broker_candidate_verified_{false};\n  uint64_t broker_mqtt_failure_started_ms_{0};\n  uint64_t broker_candidate_started_ms_{0};\n  uint64_t broker_candidate_deadline_ms_{0};\n  uint64_t broker_discovery_completed_ms_{0};\n  uint64_t last_broker_discovery_started_ms_{0};\n  std::string stable_runtime_broker_host_{};\n  std::string pending_broker_candidate_host_{};\n  std::string broker_discovery_request_id_{};\n  std::string broker_discovery_nonce_{};\n  std::string broker_discovery_local_ipv4_{};\n  std::string broker_discovery_subnet_mask_{};\n  std::vector<SimpleBrokerRecoveryTarget> broker_relocation_targets_{};\n  std::size_t broker_relocation_target_index_{0};\n  Esp32ManagerDiscoverySession broker_discovery_session_{};\n  Esp32ManagerDiscoveryRandom broker_discovery_random_{};\n  EspNowDriver radio_{};\n"""
    return replace_once(text, old, new, "component-relocation-state")


update(CORE / "n3w_simple_product_runtime.h", patch_runtime_header)
update(CORE / "n3w_simple_product_runtime.cpp", patch_runtime_cpp)
update(CORE / "n3w_simple_product_component.h", patch_component_header)
print("N3W_AUTO_SAFE_FALLBACK_PRODUCTION_CORE_CONVERGENCE_APPLY=PASS")
