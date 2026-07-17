# M2 native board-lab local preflight result — 2026-07-17

The operator-local preflight reported:

- repository head matched `main` at the native board-lab merge point;
- the clean local worktree had no changes;
- Python 3.11.9, Ruff, pytest and ESPHome 2026.4.3 were available;
- native `mosquitto` and `mosquitto_passwd` were not installed;
- the dedicated laboratory LAN bind candidate was identified as a private IPv4 address;
- no board flashing, production mutation or credential generation occurred.

The literal private address is intentionally omitted from this public record. The next local gate is dependency installation and a native non-production Broker smoke sequence after Mosquitto 2.1 compatibility is merged.
