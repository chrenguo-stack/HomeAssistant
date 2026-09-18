import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"


def test_recovery_exit_policy_behavior(tmp_path: Path) -> None:
    compiler = shutil.which("g++")
    assert compiler is not None
    source = ROOT / "tests/n3w_phase4/n3w_recovery_exit_policy_host_test.cpp"
    executable = tmp_path / "n3w-recovery-exit-policy-host-test"
    subprocess.run(
        [
            compiler,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(CORE),
            str(source),
            "-o",
            str(executable),
        ],
        check=True,
    )
    subprocess.run([str(executable)], check=True)


def test_component_uses_bounded_recovery_exits() -> None:
    component = (CORE / "n3w_simple_product_component.cpp").read_text(encoding="utf-8")
    runtime = (CORE / "n3w_simple_product_runtime.cpp").read_text(encoding="utf-8")
    driver_h = (CORE / "n3w_espnow_driver.h").read_text(encoding="utf-8")
    driver = (CORE / "n3w_espnow_driver.cpp").read_text(encoding="utf-8")

    # BSSID provenance: the explicit-lock decision must come from ESPHome's
    # selected configuration, never from the mutable IDF connection params
    # where scan_connecting may set bssid_set for a user-unlocked network.
    bssid_start = component.index(
        "bool SimpleProductComponent::explicit_bssid_lock_active_() const"
    )
    bssid_end = component.index(
        "void SimpleProductComponent::invalidate_direct_ap_hint_", bssid_start
    )
    bssid = component[bssid_start:bssid_end]
    assert "global_wifi_component->get_sta().has_bssid()" in bssid
    assert "esp_wifi_get_config" not in bssid
    assert "config.sta.bssid_set" not in bssid
    assert "direct_ap_hint_lease_.note_not_found(now)" in component
    assert "invalidate_direct_ap_hint_();" in component

    # A missing completion is fenced by teardown and a fresh-boot boundary.
    # It must not return to begin_relay_restore_ in the same boot.
    timeout_start = component.index(
        "void SimpleProductComponent::handle_pending_unicast_timeout_"
    )
    timeout_end = component.index(
        "void SimpleProductComponent::request_safe_reboot_", timeout_start
    )
    timeout = component[timeout_start:timeout_end]
    shutdown = timeout.index("radio_.shutdown()")
    deadline_clear = timeout.index("pending_unicast_deadline_.on_drained()", shutdown)
    purge = timeout.index("clear_tx_completion_ring_()", deadline_clear)
    reboot = timeout.index("request_safe_reboot_", purge)
    assert shutdown < deadline_clear < purge < reboot
    assert "begin_relay_restore_" not in timeout

    reboot_start = component.index(
        "void SimpleProductComponent::request_safe_reboot_"
    )
    reboot_end = component.index(
        "void SimpleProductComponent::drain_radio_", reboot_start
    )
    reboot_body = component[reboot_start:reboot_end]
    assert "App.safe_reboot()" in reboot_body

    # Driver teardown has a semantic result and failed teardown blocks reinit.
    assert "ESPNOW_TEARDOWN_UNCONFIRMED" in driver_h
    assert "bool shutdown();" in driver_h
    assert "teardown_confirmed_" in driver_h
    init_start = driver.index("DriverError EspNowDriver::initialize_(")
    init_end = driver.index("bool EspNowDriver::shutdown()", init_start)
    init = driver[init_start:init_end]
    assert "!teardown_confirmed_" in init
    assert "DriverError::ESPNOW_TEARDOWN_UNCONFIRMED" in init

    shutdown_start = driver.index("bool EspNowDriver::shutdown()")
    shutdown_end = driver.index(
        "void EspNowDriver::complete_unicast_send_", shutdown_start
    )
    shutdown_body = driver[shutdown_start:shutdown_end]
    detach = shutdown_body.index("active_.compare_exchange_strong")
    unregister = shutdown_body.index("esp_now_unregister_send_cb", detach)
    deinit = shutdown_body.index("esp_now_deinit", unregister)
    confirm = shutdown_body.index("teardown_confirmed_", deinit)
    pending_clear = shutdown_body.index("pending_unicast_sends_.store(0", confirm)
    assert detach < unregister < deinit < confirm < pending_clear
    assert "if (teardown_confirmed_)" in shutdown_body

    # Callback entry is counted before active-session lookup. This protects
    # callbacks already entering while teardown detaches the global target.
    assert "std::atomic<EspNowDriver *> active_" in driver_h
    assert "std::atomic<EspNowEventSink *> sink_" in driver_h
    assert "static std::atomic<uint16_t> callbacks_inflight_" in driver_h
    callback = driver[driver.index("void EspNowDriver::send_cb_("):]
    enter = callback.index("callbacks_inflight_.fetch_add")
    active_lookup = callback.index("active_.load", enter)
    sink_snapshot = callback.index("sink_.load", active_lookup)
    leave = callback.index("callbacks_inflight_.fetch_sub", sink_snapshot)
    assert enter < active_lookup < sink_snapshot < leave

    # Waiting for callback quiescence uses the same 30 s restore budget and
    # escalates to reboot instead of looping forever every 25 ms.
    restore_start = component.index(
        "void SimpleProductComponent::advance_relay_restore_()"
    )
    restore_end = component.index(
        "bool SimpleProductComponent::enqueue_telemetry_", restore_start
    )
    restore = component[restore_start:restore_end]
    decision = restore.index("callback_quiesce_action(")
    wait = restore.index("CallbackQuiesceAction::WAIT", decision)
    reboot_action = restore.index("CallbackQuiesceAction::REBOOT", wait)
    purge_after = restore.index("clear_tx_completion_ring_()", reboot_action)
    reinit = restore.index("restore_relay_radio_()", purge_after)
    assert decision < wait < reboot_action < purge_after < reinit

    assert "relay_restore_budget_.exhausted(now)" in component
    assert "exit_relay_restore_failure_(now)" in component
    assert "reset_to_discovery_after_radio_fault()" in component
    assert "SimpleProductRuntime::reset_to_discovery_after_radio_fault()" in runtime
    assert "begin_direct_probe_after_restore_exit_(now)" in component

    # Keep synchronous scan in scope as an observed physical boundary.
    assert "esp_wifi_scan_start(&scan, true)" in component
    assert "Direct AP presence scan channel=%u elapsed_ms=%llu" in component
