import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
LAB = ROOT / "firmware/esphome_rc/board_lab/n3w_phase4_physical"
SCHEMA = (
    ROOT
    / "host/greenhouse-manager/src/greenhouse_manager/schemas/gh.telemetry-1.schema.json"
)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_rtc_breadcrumb_is_restart_retained_and_flash_free() -> None:
    header = text(CORE / "n3w_rtc_breadcrumb.h")
    source = text(CORE / "n3w_rtc_breadcrumb.cpp")

    assert "RTC_NOINIT_ATTR" in source
    assert "0x4E335742U" in source
    assert "stage_inverse" in source
    assert "uptime_ms_inverse" in source
    assert "marker_sequence_inverse" in source
    assert "g_rtc_breadcrumb.magic = 0U;" in source
    assert "g_rtc_breadcrumb.magic = kBreadcrumbMagic;" in source
    assert source.index("g_rtc_breadcrumb.magic = 0U;") < source.index(
        "g_rtc_breadcrumb.magic = kBreadcrumbMagic;"
    )

    assert "N3wRtcBreadcrumbStage" in header
    assert "DIRECT_PUBLISH_BEGIN" in header
    assert "RADIO_CHANNEL_SET_BEGIN" in header
    assert "CHALLENGE_SUBMIT_BEGIN" in header

    lowered = source.lower()
    assert "nvs" not in lowered
    assert "flash" not in lowered


def test_core_captures_previous_boot_before_writing_current_boot_marker() -> None:
    core = text(CORE / "greenhouse_n3w_core.h")

    capture = core.index("n3w_rtc_breadcrumb_capture(&previous_rtc_breadcrumb_)")
    boot_mark = core.index("N3wRtcBreadcrumbStage::BOOT_SETUP")
    base_setup = core.index("SimpleProductComponent::setup()")
    assert capture < boot_mark < base_setup

    assert "N3wRtcBreadcrumbStage::TELEMETRY_BEGIN" in core
    assert "N3wRtcBreadcrumbStage::TELEMETRY_OK" in core
    assert "N3wRtcBreadcrumbStage::TELEMETRY_FAIL" in core
    assert "N3wRtcBreadcrumbStage::TELEMETRY_BUFFERED" in core
    assert "N3wRtcBreadcrumbStage::DIRECT_PUBLISH_BEGIN" in core
    assert "N3wRtcBreadcrumbStage::DIRECT_PUBLISH_OK" in core
    assert "N3wRtcBreadcrumbStage::DIRECT_PUBLISH_FAIL" in core
    assert "N3wRtcBreadcrumbStage::RADIO_CHANNEL_SET_BEGIN" in core
    assert "N3wRtcBreadcrumbStage::CHALLENGE_SUBMIT_BEGIN" in core

    assert "SimpleProductComponent::publish_direct(topic, payload)" in core
    assert "SimpleProductComponent::set_radio_channel(channel)" in core
    assert "SimpleProductComponent::broadcast_control_on_channel(" in core


def test_lab_telemetry_reports_previous_boot_breadcrumb_without_schema_change() -> None:
    config = text(LAB / "generic.yml")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert "wdt_breadcrumb" in config
    assert "previous_rtc_breadcrumb_valid()" in config
    assert "previous_rtc_breadcrumb_stage()" in config
    assert "previous_rtc_breadcrumb_stage_name()" in config
    assert "previous_rtc_breadcrumb_uptime_ms()" in config
    assert "previous_rtc_breadcrumb_marker_sequence()" in config

    # gh.telemetry/1 deliberately permits diagnostic extension fields, so the
    # board-lab breadcrumb does not require a protocol/schema revision.
    assert schema["additionalProperties"] is True


def test_physical_harness_mqtt_cannot_block_main_loop_or_forward_lab_logs() -> None:
    config = text(LAB / "generic.yml")

    # ESP-IDF's synchronous MQTT publish may block the ESPHome main loop for
    # network timeouts during Direct Wi-Fi loss. Keep publishes on the backend
    # task and keep lab INFO logs off the disappearing MQTT transport entirely.
    assert "idf_send_async: true" in config
    assert "log_topic: null" in config
