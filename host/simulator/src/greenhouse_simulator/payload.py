from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

CAP_HASH = "sha256:simulator-m0-v1"
FW_VERSION = "SIM-M0.1"


def _sampled_at(now: datetime) -> str:
    return now.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_telemetry(
    *,
    node_id: str,
    boot_id: str,
    seq: int,
    uptime_ms: int,
    now: datetime,
    invalid: bool = False,
) -> dict[str, Any]:
    phase = seq % 10
    air_temperature = 24.0 + phase * 0.2
    air_humidity = 62.0 + phase * 0.3
    soil_moisture = 38.0 + phase * 0.1

    if invalid:
        air_humidity = 140.0

    measurements = {
        "air_temperature_c": round(air_temperature, 1),
        "air_humidity_pct": round(air_humidity, 1),
        "co2_ppm": 620 + phase * 7,
        "illuminance_lx": 14800 + phase * 120,
        "soil_temperature_c": round(22.8 + phase * 0.1, 1),
        "soil_moisture_pct": round(soil_moisture, 1),
        "soil_ec_us_cm": 790 + phase * 3,
        "vpd_kpa": round(1.05 + phase * 0.02, 2),
        "dew_point_c": round(17.0 + phase * 0.1, 1),
        "absolute_humidity_g_m3": round(14.8 + phase * 0.1, 1),
        "ppfd_umol_m2_s": 274 + phase * 2,
        "dli_today_mol_m2_d": round(4.2 + phase * 0.05, 2),
        "dli_yesterday_mol_m2_d": 6.1,
        "battery_v": 3.94,
        "battery_pct": 74,
    }

    quality = {name: "ok" for name in measurements}

    return {
        "schema": "gh.telemetry/1",
        "node_id": node_id,
        "boot_id": boot_id,
        "seq": seq,
        "uptime_ms": uptime_ms,
        "sampled_at": _sampled_at(now),
        "cap_hash": CAP_HASH,
        "fw_version": FW_VERSION,
        "measurements": measurements,
        "quality": quality,
        "power": {
            "source": "battery",
            "battery_v": 3.94,
            "battery_pct": 74,
            "low": False,
        },
    }
