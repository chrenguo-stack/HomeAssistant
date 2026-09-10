#include <cassert>
#include <cstdint>
#include <fstream>

#include "n3w_lab_diagnostics.h"

using namespace esphome::greenhouse_n3w_core;

int main(int argc, char **argv) {
  assert(argc == 2);

  N3wLabDiagnostics diagnostics;
  diagnostics.set_enabled(true);
  diagnostics.begin_boot_session();
  assert(!diagnostics.boot_session_bound());
  assert(diagnostics.persist_count() == 0);

  constexpr uint64_t kBootSession = 0x1122334455667788ULL;
  diagnostics.bind_boot_session(kBootSession, 0);
  assert(diagnostics.boot_session_bound());
  assert(diagnostics.snapshot().boot_session == kBootSession);
  assert(diagnostics.persist_count() == 1);

  constexpr uint8_t kChannels[] = {1, 6, 11};
  for (uint32_t cycle = 0; cycle < 720; ++cycle) {
    const uint64_t now_ms = static_cast<uint64_t>(cycle) * 250U;
    const uint8_t channel = kChannels[cycle % 3U];
    diagnostics.on_scan_attempt(channel, now_ms);
    diagnostics.note_channel_result(channel, true, channel, 0, now_ms);
    diagnostics.on_scan_result(channel, true, channel, 0, now_ms);
    diagnostics.observe_runtime(1, channel, 0, 0, false, now_ms);
  }
  assert(diagnostics.snapshot().scan_attempts == 720);
  assert(diagnostics.snapshot().scan_successes == 720);
  assert(diagnostics.snapshot().scan_failures == 0);
  assert(diagnostics.snapshot().current_channel == 11);
  assert(diagnostics.snapshot().direct_channel_hint == 0);
  assert(diagnostics.persist_count() <= 40);

  N3wLabDiagnostics repeated_failures;
  repeated_failures.set_enabled(true);
  repeated_failures.begin_boot_session();
  repeated_failures.bind_boot_session(10, 0);
  for (uint32_t cycle = 0; cycle < 720; ++cycle) {
    const uint64_t now_ms = static_cast<uint64_t>(cycle) * 250U;
    const uint8_t channel = kChannels[cycle % 3U];
    repeated_failures.on_scan_attempt(channel, now_ms);
    repeated_failures.note_channel_result(channel, false, 0, -1, now_ms);
    repeated_failures.on_scan_result(channel, false, 0, -1, now_ms);
    repeated_failures.observe_runtime(1, channel, 0, 0, false, now_ms);
  }
  assert(repeated_failures.snapshot().scan_attempts == 720);
  assert(repeated_failures.snapshot().scan_failures == 720);
  assert(repeated_failures.persist_count() <= 40);

  N3wLabDiagnostics advertisements;
  advertisements.set_enabled(true);
  advertisements.begin_boot_session();
  advertisements.bind_boot_session(11, 0);
  for (uint64_t now_ms = 0; now_ms < 180000; now_ms += 2000) {
    advertisements.on_relay_advertisement(true, now_ms);
    advertisements.on_broadcast_completion((now_ms % 4000U) == 0U, now_ms);
    advertisements.emit_summary(now_ms);
  }
  assert(advertisements.snapshot().relay_advertisement_attempts == 90);
  assert(advertisements.snapshot().relay_advertisement_submit_success == 90);
  assert(advertisements.snapshot().relay_advertisement_submit_failure == 0);
  assert(advertisements.snapshot().broadcast_completion_count == 90);
  assert(advertisements.snapshot().broadcast_completion_success == 45);
  assert(advertisements.snapshot().broadcast_completion_failure == 45);
  assert(advertisements.persist_count() <= 40);

  N3wLabDiagnostics direct;
  direct.set_enabled(true);
  direct.begin_boot_session();
  direct.bind_boot_session(9, 100);
  direct.note_channel_result(1, true, 1, 0, 100);
  direct.observe_runtime(0, 1, 1, 0, false, 100);
  assert(direct.snapshot().scan_attempts == 0);
  assert(direct.snapshot().scan_successes == 0);
  assert(direct.snapshot().scan_failures == 0);
  direct.on_scan_attempt(1, 250);
  direct.on_scan_result(1, true, 1, 0, 250);
  assert(direct.snapshot().scan_attempts == 1);

  N3wLabDiagnostics completions;
  completions.set_enabled(true);
  completions.begin_boot_session();
  completions.bind_boot_session(12, 0);
  completions.on_unicast_completion(true, 0);
  completions.on_unicast_completion(true, 0);
  completions.on_unicast_completion(false, 0);
  completions.on_compact_rx(100);
  completions.on_compact_state_rejected(100);
  completions.on_compact_child_binding_failure(100);
  completions.on_compact_decode(true, 100);
  completions.on_compact_decode(false, 100);
  completions.on_compact_wrap_failure(100);
  completions.on_compact_forward_attempt(100);
  completions.on_compact_forward_submit(true, 100);
  completions.on_compact_forward_submit(false, 100);
  assert(completions.snapshot().unicast_completion_count == 0);
  completions.emit_summary(10000);
  assert(completions.snapshot().unicast_completion_count == 3);
  assert(completions.snapshot().unicast_completion_success == 2);
  assert(completions.snapshot().unicast_completion_failure == 1);
  assert(completions.snapshot().unicast_completion_success +
             completions.snapshot().unicast_completion_failure ==
         completions.snapshot().unicast_completion_count);
  assert(completions.snapshot().compact_rx_count == 1);
  assert(completions.snapshot().compact_state_reject_count == 1);
  assert(completions.snapshot().compact_child_binding_failure == 1);
  assert(completions.snapshot().compact_decode_success == 1);
  assert(completions.snapshot().compact_decode_failure == 1);
  assert(completions.snapshot().compact_wrap_failure == 1);
  assert(completions.snapshot().compact_forward_attempts == 1);
  assert(completions.snapshot().compact_forward_submit_success == 1);
  assert(completions.snapshot().compact_forward_submit_failure == 1);

  const auto &snapshot = diagnostics.snapshot();
  assert(snapshot.magic == N3wLabDiagnostics::kMagic);
  assert(snapshot.schema_version == N3wLabDiagnostics::kSchemaVersion);
  assert(snapshot.size == sizeof(N3wLabDiagnostics::Snapshot));
  assert(snapshot.snapshot_uptime_ms == 179750);
  std::ofstream output(argv[1], std::ios::binary | std::ios::trunc);
  output.write(
      reinterpret_cast<const char *>(&snapshot),
      static_cast<std::streamsize>(sizeof(snapshot)));
  assert(output.good());
  return 0;
}
