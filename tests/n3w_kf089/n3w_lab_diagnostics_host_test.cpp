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
