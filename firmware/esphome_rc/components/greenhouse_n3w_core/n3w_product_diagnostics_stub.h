#pragma once

#include <cstdint>
#include <utility>

namespace esphome::greenhouse_n3w_core {

class N3wProductDiagnosticsStub final {
 public:
  struct LatencySnapshot {};

  void set_enabled(bool enabled) { (void) enabled; }
  bool enabled() const { return false; }
  const LatencySnapshot &latency_snapshot() const { return latency_; }

  template<typename... Args>
  void begin_boot_session(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void bind_boot_session(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void observe_connectivity(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void observe_runtime(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void emit_summary(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void note_channel_result(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void note_full_verify_start(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void note_full_verify_terminal(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void note_peer_install(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void note_presence_probe(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void note_recovery_probe_deferral(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void note_recovery_schedule(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void note_relay_restore(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void note_rx_dropped(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void note_unicast_submit(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void on_broadcast_completion(Args&&... args) { (void) sizeof...(args); }
  template<typename... Args>
  void on_unicast_completion(Args&&... args) { (void) sizeof...(args); }

 private:
  LatencySnapshot latency_{};
};

}  // namespace esphome::greenhouse_n3w_core
