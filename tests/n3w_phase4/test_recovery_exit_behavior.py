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
    driver = (CORE / "n3w_espnow_driver.cpp").read_text(encoding="utf-8")

    assert "config.sta.bssid_set" in component
    assert "explicit_bssid_lock_active_()" in component
    assert "direct_ap_hint_lease_.note_not_found(now)" in component
    assert "invalidate_direct_ap_hint_();" in component

    timeout_start = component.index(
        "void SimpleProductComponent::handle_pending_unicast_timeout_"
    )
    timeout_end = component.index(
        "void SimpleProductComponent::drain_radio_", timeout_start
    )
    timeout = component[timeout_start:timeout_end]
    shutdown = timeout.index("radio_.shutdown()")
    deadline_clear = timeout.index("pending_unicast_deadline_.on_drained()", shutdown)
    restore = timeout.index("begin_relay_restore_", deadline_clear)
    assert shutdown < deadline_clear < restore

    shutdown_start = driver.index("void EspNowDriver::shutdown()")
    shutdown_end = driver.index(
        "void EspNowDriver::complete_unicast_send_", shutdown_start
    )
    shutdown_body = driver[shutdown_start:shutdown_end]
    detach = shutdown_body.index("active_ = nullptr")
    unregister = shutdown_body.index("esp_now_unregister_send_cb", detach)
    deinit = shutdown_body.index("esp_now_deinit", unregister)
    clear = shutdown_body.index("pending_unicast_sends_.store(0", deinit)
    assert detach < unregister < deinit < clear

    assert "relay_restore_budget_.exhausted(now)" in component
    assert "exit_relay_restore_failure_(now)" in component
    assert "reset_to_discovery_after_radio_fault()" in component
    assert "SimpleProductRuntime::reset_to_discovery_after_radio_fault()" in runtime
    assert "begin_direct_probe_after_restore_exit_(now)" in component

    # Keep the synchronous scan in scope as an observed boundary, not a hidden
    # claim of non-blocking behavior.
    assert "esp_wifi_scan_start(&scan, true)" in component
    assert "Direct AP presence scan channel=%u elapsed_ms=%llu" in component
