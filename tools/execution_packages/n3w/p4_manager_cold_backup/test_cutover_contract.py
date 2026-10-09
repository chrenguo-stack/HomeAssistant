from __future__ import annotations

import copy
import unittest

import cutover_contract as contract

OLD_ID = "sha256:" + "a" * 64
NEW_ID = "sha256:" + "b" * 64
OLD_BASE = "/srv/original"
NEW_BASE = "/srv/p4-fresh"
EXPECTED_DESTS = tuple(sorted(contract.ALL_TARGETS))


def old_manager():
    mounts = []
    for i, dst in enumerate(EXPECTED_DESTS):
        mounts.append({
            "Destination": dst,
            "Source": OLD_BASE + "/mount" + str(i),
            "Type": "bind",
            "RW": dst in contract.RW_TARGETS,
            "Propagation": "rprivate",
        })
    return {
        "Id": "old-manager-id",
        "Name": "/greenhouse-manager",
        "Image": OLD_ID,
        "State": {"Running": True},
        "Config": {
            "Env": ["GH_MQTT_TLS=1", "GH_SECRET=not-to-print", "GH_MQTT_PORT=8883"],
            "User": "greenhouse",
            "Entrypoint": ["greenhouse-manager"],
            "Cmd": [],
            "WorkingDir": "/app",
            "Healthcheck": None,
            "StopSignal": None,
            "OpenStdin": False,
            "StdinOnce": False,
            "Tty": False,
            "Labels": {"org.opencontainers.image.revision": "old"},
        },
        "HostConfig": {
            "NetworkMode": "host",
            "PortBindings": {},
            "ReadonlyRootfs": True,
            "RestartPolicy": {"Name": "unless-stopped"},
            "SecurityOpt": None,
            "Tmpfs": {"/tmp": "rw,nosuid,size=16777216"},
            "CapAdd": None,
            "CapDrop": None,
            "Privileged": False,
            "LogConfig": {"Type": "json-file", "Config": {}},
            "Devices": [],
            "DeviceRequests": None,
            "PidsLimit": None,
            "Memory": 0,
            "MemorySwap": 0,
            "NanoCpus": 0,
            "Ulimits": None,
            "IpcMode": "private",
            "PidMode": "",
            "ShmSize": 67108864,
            "CgroupnsMode": "private",
            "Dns": [],
            "ExtraHosts": None,
            "Init": None,
            "OomKillDisable": None,
        },
        "Mounts": mounts,
    }


def image():
    return {
        "Os": "linux",
        "Architecture": "arm64",
        "Id": NEW_ID,
        "Config": {"Labels": {"org.opencontainers.image.revision": contract.CANDIDATE_SOURCE}},
    }


def fresh_sources():
    return {
        dest: NEW_BASE + "/mount" + str(i)
        for i, dest in enumerate(sorted(contract.RW_TARGETS))
    }


def stopped_shadow(old):
    new = copy.deepcopy(old)
    new["State"]["Running"] = False
    new["Image"] = NEW_ID
    new["Config"]["Labels"]["org.opencontainers.image.revision"] = contract.CANDIDATE_SOURCE
    new["HostConfig"]["RestartPolicy"] = {"Name": "no"}
    desired = contract.plan_isolated_bindings(old, fresh_sources())
    new["Mounts"] = list(desired.values())
    return new


class CutoverContractTests(unittest.TestCase):
    def setUp(self):
        self.old = old_manager()
        self.broker = {"State": {"Running": True}}
        self.image = image()

    def test_source_authority_and_shadow_contract_pass(self):
        contract.validate_source_authority(self.old, self.broker, self.image)
        shadow = stopped_shadow(self.old)
        contract.verify_stopped_shadow_matches_origin(
            self.old, shadow, NEW_ID, fresh_sources()
        )

    def test_candidate_rw_mounts_are_fresh_and_ro_secrets_preserved(self):
        mounted = contract.plan_isolated_bindings(self.old, fresh_sources())
        original = {m["Destination"]: m for m in self.old["Mounts"]}
        for dst in contract.RW_TARGETS:
            self.assertNotEqual(mounted[dst]["Source"], original[dst]["Source"])
            self.assertTrue(mounted[dst]["RW"])
        for dst in contract.RO_TARGETS:
            self.assertEqual(mounted[dst]["Source"], original[dst]["Source"])
            self.assertFalse(mounted[dst]["RW"])

    def test_duplicate_or_missing_mount_is_forbidden(self):
        self.old["Mounts"][1]["Destination"] = self.old["Mounts"][0]["Destination"]
        with self.assertRaises(contract.CutoverStop):
            contract.validate_source_authority(self.old, self.broker, self.image)

    def test_compose_bridge_or_extra_ports_are_forbidden(self):
        self.old["HostConfig"]["NetworkMode"] = "bridge"
        with self.assertRaisesRegex(contract.CutoverStop, "MANAGER_NOT_HOST_NETWORK"):
            contract.validate_source_authority(self.old, self.broker, self.image)
        self.old["HostConfig"]["NetworkMode"] = "host"
        self.old["HostConfig"]["PortBindings"] = {"8883/tcp": [{}]}
        with self.assertRaisesRegex(contract.CutoverStop, "MANAGER_PORT_PUBLICATION_FORBIDDEN"):
            contract.validate_source_authority(self.old, self.broker, self.image)

    def test_wrong_image_revision_cannot_be_used(self):
        self.image["Config"]["Labels"]["org.opencontainers.image.revision"] = "incorrect"
        with self.assertRaisesRegex(contract.CutoverStop, "CANDIDATE_REVISION_MISMATCH"):
            contract.validate_source_authority(self.old, self.broker, self.image)

    def test_candidate_must_not_write_original_state(self):
        dest = next(iter(sorted(contract.RW_TARGETS)))
        bad = fresh_sources()
        bad[dest] = next(
            m["Source"] for m in self.old["Mounts"]
            if m["Destination"] == dest
        )
        with self.assertRaisesRegex(
            contract.CutoverStop, "CANDIDATE_MUST_NOT_WRITE_OLD_STATE"
        ):
            contract.plan_isolated_bindings(self.old, bad)

    def test_candidate_must_not_overlap_any_original_tree(self):
        bad = fresh_sources()
        dest = next(iter(sorted(contract.RW_TARGETS)))
        bad[dest] = OLD_BASE + "/mount0/accidental-nested"
        with self.assertRaisesRegex(
            contract.CutoverStop, "FRESH_SOURCE_OVERLAPS_ORIGINAL_STATE"
        ):
            contract.plan_isolated_bindings(self.old, bad)

    def test_candidate_fresh_sources_must_not_overlap(self):
        bad = fresh_sources()
        a, b = sorted(contract.RW_TARGETS)[:2]
        bad[b] = bad[a] + "/nested"
        with self.assertRaisesRegex(contract.CutoverStop, "FRESH_SOURCE_OVERLAP"):
            contract.plan_isolated_bindings(self.old, bad)

    def test_candidate_shadow_must_preserve_security(self):
        shadow = stopped_shadow(self.old)
        shadow["HostConfig"]["ReadonlyRootfs"] = False
        with self.assertRaisesRegex(
            contract.CutoverStop, "CANDIDATE_HOST_SECURITY_PARITY_FAILED"
        ):
            contract.verify_stopped_shadow_matches_origin(
                self.old, shadow, NEW_ID, fresh_sources()
            )

    def test_shadow_accepts_oom_kill_disable_default_none_vs_false_only(self):
        for original, candidate in ((None, False), (False, None), (None, None), (False, False)):
            with self.subTest(original=original, candidate=candidate):
                old = old_manager()
                old["HostConfig"]["OomKillDisable"] = original
                shadow = stopped_shadow(old)
                shadow["HostConfig"]["OomKillDisable"] = candidate
                contract.verify_stopped_shadow_matches_origin(
                    old, shadow, NEW_ID, fresh_sources()
                )
                shadow["State"]["Running"] = True
                contract.verify_running_candidate_matches_origin(
                    old, shadow, NEW_ID, fresh_sources()
                )

    def test_shadow_rejects_oom_kill_disable_true_even_if_matching(self):
        for original, candidate in ((None, True), (False, True), (True, False), (True, True)):
            with self.subTest(original=original, candidate=candidate):
                old = old_manager()
                old["HostConfig"]["OomKillDisable"] = original
                shadow = stopped_shadow(old)
                shadow["HostConfig"]["OomKillDisable"] = candidate
                with self.assertRaisesRegex(
                    contract.CutoverStop, "CANDIDATE_HOST_SECURITY_PARITY_FAILED"
                ):
                    contract.verify_stopped_shadow_matches_origin(
                        old, shadow, NEW_ID, fresh_sources()
                    )

    def test_shadow_rejects_oom_kill_disable_unexpected_numeric_value(self):
        shadow = stopped_shadow(self.old)
        shadow["HostConfig"]["OomKillDisable"] = 0
        with self.assertRaisesRegex(
            contract.CutoverStop, "CANDIDATE_HOST_SECURITY_PARITY_FAILED"
        ):
            contract.verify_stopped_shadow_matches_origin(
                self.old, shadow, NEW_ID, fresh_sources()
            )

    def test_shadow_rejects_unreviewed_host_security_drift(self):
        shadow = stopped_shadow(self.old)
        shadow["HostConfig"]["PublishAllPorts"] = True
        with self.assertRaisesRegex(
            contract.CutoverStop, "CANDIDATE_HOST_SECURITY_PARITY_FAILED"
        ):
            contract.verify_stopped_shadow_matches_origin(
                self.old, shadow, NEW_ID, fresh_sources()
            )

    def test_shadow_rejects_extra_network_config_drift(self):
        shadow = stopped_shadow(self.old)
        shadow["Config"]["NetworkDisabled"] = True
        with self.assertRaisesRegex(
            contract.CutoverStop, "CANDIDATE_CONFIG_PARITY_FAILED"
        ):
            contract.verify_stopped_shadow_matches_origin(
                self.old, shadow, NEW_ID, fresh_sources()
            )

    def test_candidate_shadow_must_preserve_existing_secrets(self):
        shadow = stopped_shadow(self.old)
        shadow["Config"]["Env"][1] = "GH_SECRET=changed"
        with self.assertRaisesRegex(contract.CutoverStop, "CANDIDATE_ENV_PARITY_FAILED"):
            contract.verify_stopped_shadow_matches_origin(
                self.old, shadow, NEW_ID, fresh_sources()
            )

    def test_environment_order_does_not_change_contract(self):
        shadow = stopped_shadow(self.old)
        shadow["Config"]["Env"] = list(reversed(shadow["Config"]["Env"]))
        contract.verify_stopped_shadow_matches_origin(
            self.old, shadow, NEW_ID, fresh_sources()
        )

    def test_duplicate_environment_key_is_forbidden(self):
        shadow = stopped_shadow(self.old)
        shadow["Config"]["Env"].append("GH_MQTT_TLS=1")
        with self.assertRaisesRegex(
            contract.CutoverStop, "MANAGER_ENV_DUPLICATE_OR_EMPTY"
        ):
            contract.verify_stopped_shadow_matches_origin(
                self.old, shadow, NEW_ID, fresh_sources()
            )

    def test_shadow_log_configuration_drift_is_rejected(self):
        shadow = stopped_shadow(self.old)
        self.old["HostConfig"]["LogConfig"]["Config"] = {"max-size": "10m", "max-file": "3"}
        shadow["HostConfig"]["LogConfig"]["Config"] = {"max-size": "20m", "max-file": "3"}
        with self.assertRaisesRegex(
            contract.CutoverStop, "CANDIDATE_HOST_SECURITY_PARITY_FAILED"
        ):
            contract.verify_stopped_shadow_matches_origin(
                self.old, shadow, NEW_ID, fresh_sources()
            )

    def test_shadow_revision_only_label_change(self):
        shadow = stopped_shadow(self.old)
        shadow["Config"]["Labels"]["extra"] = "injected"
        with self.assertRaisesRegex(
            contract.CutoverStop, "CANDIDATE_NONREVISION_LABEL_DRIFT"
        ):
            contract.verify_stopped_shadow_matches_origin(
                self.old, shadow, NEW_ID, fresh_sources()
            )

    def test_shadow_stays_stopped_until_cutover(self):
        shadow = stopped_shadow(self.old)
        shadow["State"]["Running"] = True
        with self.assertRaisesRegex(
            contract.CutoverStop, "CANDIDATE_RUNNING_STATE_MISMATCH"
        ):
            contract.verify_stopped_shadow_matches_origin(
                self.old, shadow, NEW_ID, fresh_sources()
            )

    def test_running_candidate_contract_passes_before_commit(self):
        candidate = stopped_shadow(self.old)
        candidate["State"]["Running"] = True
        contract.verify_running_candidate_matches_origin(
            self.old, candidate, NEW_ID, fresh_sources()
        )

    def test_transaction_order_has_no_legacy_cold_copy(self):
        contract.assert_cutover_sequence(list(contract.TRANSACTION_PHASES))
        self.assertNotIn("FRESH_THREE_SOURCE_COLD_COPY", contract.TRANSACTION_PHASES)
        self.assertNotIn("CLONED_STATE_BUSINESS_PROOF", contract.TRANSACTION_PHASES)
        bad = list(contract.TRANSACTION_PHASES)
        bad.remove("FRESH_SOURCES_PREPARED_EMPTY")
        with self.assertRaisesRegex(contract.CutoverStop, "CUTOVER_SEQUENCE_UNSAFE"):
            contract.assert_cutover_sequence(bad)

    def test_success_never_claims_real_node_telemetry(self):
        self.assertEqual(
            contract.classify_staged_result(True, True, True, True),
            "RUNTIME_READY_NO_NODE_TRAFFIC_EXPECTED",
        )
        self.assertEqual(
            contract.classify_staged_result(True, False, True, True),
            "STOP_RESCUE_OLD_MANAGER",
        )


if __name__ == "__main__":
    unittest.main()
