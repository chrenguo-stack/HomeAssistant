#pragma once

#include <cstdint>

namespace esphome::greenhouse_n3w_core {

// Production successor placeholder for instrumentation hooks that are still
// called by the frozen PR #437 product state machine. It deliberately owns no
// NVS state, emits no logs, and never enables ESP-NOW diagnostic readback.
class N3wProductNoopDiagnostics {
 public:
  void set_enabled(bool) {}
  bool enabled() const { return false; }
  void begin_boot_session() {}
  void bind_boot_session(uint64_t, uint64_t) {}

  template<typename... Args> void observe_connectivity(Args &&...) {}
  template<typename... Args> void observe_runtime(Args &&...) {}
  template<typename... Args> void emit_summary(Args &&...) {}
  template<typename... Args> void note_recovery_schedule(Args &&...) {}
  template<typename... Args> void note_recovery_probe_deferral(Args &&...) {}
  template<typename... Args> void note_presence_probe(Args &&...) {}
  template<typename... Args> void note_full_verify_terminal(Args &&...) {}
  template<typename... Args> void note_full_verify_start(Args &&...) {}
  template<typename... Args> void note_channel_result(Args &&...) {}
  template<typename... Args> void note_relay_restore(Args &&...) {}
  template<typename... Args> void note_rx_dropped(Args &&...) {}
  template<typename... Args> void on_broadcast_completion(Args &&...) {}
  template<typename... Args> void on_unicast_completion(Args &&...) {}
  template<typename... Args> void note_peer_install(Args &&...) {}
  template<typename... Args> void note_unicast_submit(Args &&...) {}
};

}  // namespace esphome::greenhouse_n3w_core
