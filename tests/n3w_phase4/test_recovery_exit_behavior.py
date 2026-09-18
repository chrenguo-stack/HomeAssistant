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

    advance_start = component.index("void SimpleProductComponent::advance_recovery_()")
    advance_end = component.index(
        "bool SimpleProductComponent::claim_relay_radio_()", advance_start
    )
    advance = component[advance_start:advance_end]
    expiry_check = advance.index("direct_ap_hint_policy_.expired(now)")
    invalidate = advance.index("invalidate_direct_ap_hint_()", expiry_check)
    full_direct = advance.index("begin_direct_probe_()", invalidate)
    scan = advance.index("probe_direct_ap_presence_()", full_direct)
    assert expiry_check < invalidate < full_direct < scan

    schedule_start = component.index(
        "void SimpleProductComponent::schedule_recovery_probe_"
    )
    schedule_end = component.index(
        "void SimpleProductComponent::begin_relay_restore_", schedule_start
    )
    schedule = component[schedule_start:schedule_end]
    assert "direct_ap_hint_policy_.active()" in schedule
    assert "direct_ap_hint_policy_.expires_at_ms()" in schedule

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
    assert "bool espnow_started_{false};" in driver_h
    init_start = driver.index("DriverError EspNowDriver::initialize_(")
    init_end = driver.index("bool EspNowDriver::shutdown()", init_start)
    init = driver[init_start:init_end]
    assert "!teardown_confirmed_" in init
    assert "DriverError::ESPNOW_TEARDOWN_UNCONFIRMED" in init
    assert "initialized_ || espnow_started_" in init
    espnow_init = init.index("esp_now_init()")
    started = init.index("espnow_started_ = true", espnow_init)
    pmk = init.index("esp_now_set_pmk", started)
    assert espnow_init < started < pmk

    shutdown_start = driver.index("bool EspNowDriver::shutdown()")
    shutdown_end = driver.index(
        "void EspNowDriver::complete_unicast_send_", shutdown_start
    )
    shutdown_body = driver[shutdown_start:shutdown_end]
    detach = shutdown_body.index("active_.compare_exchange_strong")
    unregister = shutdown_body.index("esp_now_unregister_send_cb", detach)
    sdk_started_gate = shutdown_body.index("if (espnow_started_)", unregister)
    deinit = shutdown_body.index("esp_now_deinit", sdk_started_gate)
    clear_started = shutdown_body.index("espnow_started_ = false", deinit)
    confirm = shutdown_body.index("teardown_confirmed_", clear_started)
    pending_clear = shutdown_body.index("pending_unicast_sends_.store(0", confirm)
    assert detach < unregister < sdk_started_gate < deinit < clear_started < confirm < pending_clear
    assert "if (teardown_confirmed_)" in shutdown_body


    # Startup failures with an unconfirmed teardown must request the existing
    # fail-safe reboot immediately instead of falling back to the 1 s retry loop.
    start_begin = component.index(
        "bool SimpleProductComponent::start_runtime_if_ready_()"
    )
    start_end = component.index(
        "void SimpleProductComponent::advance_pairing_", start_begin
    )
    startup = component[start_begin:start_end]
    init_failure = startup.index("ESP-NOW initialization failed error=%u teardown_confirmed=%s")
    teardown_check = startup.index("!radio_.teardown_confirmed()", init_failure)
    reboot_startup = startup.index("request_safe_reboot_(", teardown_check)
    return_after_reboot = startup.index("return false;", reboot_startup)
    assert init_failure < teardown_check < reboot_startup < return_after_reboot
    assert "ESP-NOW broadcast-peer failure left teardown unconfirmed" in startup
    assert "N3-W runtime start failure left ESP-NOW teardown unconfirmed" in startup

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
