from __future__ import annotations

import unittest

from b1i1_contract import EXISTING_RO, FRESH_RW, GateStop
from b1i1_fresh_state import (
    REQUIRED_ZERO_TABLES,
    require_initialized_zero_business_state,
    validate_fresh_mount_sources,
)
from b1i1_preflight import validate_live_origin
from test_b1i1_transaction import authority


def original_sources():
    result = {}
    for i, dest in enumerate(FRESH_RW):
        result[dest] = "/private/old-rw-" + str(i)
    for i, dest in enumerate(EXISTING_RO):
        result[dest] = "/private/ro-" + str(i)
    return result


def fresh_sources():
    result = original_sources()
    for i, dest in enumerate(FRESH_RW):
        result[dest] = "/private/new-rw-" + str(i)
    return result


def manager():
    sources = original_sources()
    return {
        "Id": "original-container-id",
        "Image": "sha256:original",
        "State": {"Running": True},
        "HostConfig": {"NetworkMode": "host"},
        "Mounts": [
            {"Destination": key, "Source": value, "Type": "bind", "RW": key in FRESH_RW}
            for key, value in sources.items()
        ],
    }


def broker():
    return {
        "Id": "broker-id",
        "State": {"Running": True, "StartedAt": "2026-10-09T00:00:00Z"},
        "RestartCount": 0,
    }


class SafetyProofTests(unittest.TestCase):
    def verify(self, m=None, b=None, **flags):
        return validate_live_origin(
            authority(), manager() if m is None else m,
            broker() if b is None else b,
            ha_running=flags.get("ha_running", True),
            r5_guard_verified=flags.get("r5_guard_verified", True),
            tls_8883_verified=flags.get("tls_8883_verified", True),
        )

    def test_original_six_mount_and_broker_baseline(self):
        self.assertEqual(self.verify(), original_sources())

    def test_original_manager_or_broker_identity_drift_refused(self):
        for change in ("manager_id", "image", "broker_id", "broker_restart", "broker_started"):
            m, b = manager(), broker()
            if change == "manager_id":
                m["Id"] = "other"
            elif change == "image":
                m["Image"] = "sha256:wrong"
            elif change == "broker_id":
                b["Id"] = "other"
            elif change == "broker_restart":
                b["RestartCount"] = 1
            else:
                b["State"]["StartedAt"] = "different"
            with self.subTest(change=change):
                with self.assertRaises(GateStop):
                    self.verify(m, b)

    def test_six_mount_source_permissions_and_network(self):
        cases = ("missing", "rw_secret", "ro_business", "source_alias", "network")
        for change in cases:
            m = manager()
            if change == "missing":
                m["Mounts"].pop()
            elif change == "rw_secret":
                m["Mounts"][-1]["RW"] = True
            elif change == "ro_business":
                m["Mounts"][0]["RW"] = False
            elif change == "source_alias":
                m["Mounts"][0]["Source"] = m["Mounts"][1]["Source"]
            elif change == "network":
                m["HostConfig"]["NetworkMode"] = "bridge"
            with self.subTest(change=change):
                with self.assertRaises(GateStop):
                    self.verify(m)

    def test_other_services_and_tls_are_mandatory(self):
        for flag in ("ha_running", "r5_guard_verified", "tls_8883_verified"):
            with self.subTest(flag=flag):
                with self.assertRaises(GateStop):
                    self.verify(**{flag: False})

    def test_old_three_rw_and_three_ro_kept_separate(self):
        validate_fresh_mount_sources(original_sources(), fresh_sources())

    def test_old_rw_reuse_and_new_rw_overlap_denied(self):
        previous = original_sources()
        for path in (previous[FRESH_RW[0]], previous[FRESH_RW[0]] + "/child", "/private/new-rw-1/child"):
            current = fresh_sources()
            current[FRESH_RW[0]] = path
            with self.subTest(path=path):
                with self.assertRaises(GateStop):
                    validate_fresh_mount_sources(previous, current)

    def test_secret_ro_must_be_exact_source(self):
        current = fresh_sources()
        current[EXISTING_RO[0]] = "/private/new-secret"
        with self.assertRaisesRegex(GateStop, "RO_SECRET_SOURCE_CHANGED"):
            validate_fresh_mount_sources(original_sources(), current)

    def test_database_all_required_tables_zero(self):
        rows = {name: 0 for name in REQUIRED_ZERO_TABLES}
        require_initialized_zero_business_state(rows, 0)
        for table in REQUIRED_ZERO_TABLES:
            changed = dict(rows, **{table: 1})
            with self.subTest(table=table):
                with self.assertRaisesRegex(GateStop, "BUSINESS_ROWS_NOT_ZERO"):
                    require_initialized_zero_business_state(changed, 0)
        with self.assertRaisesRegex(GateStop, "BUSINESS_TABLE_PROOF_INCOMPLETE"):
            require_initialized_zero_business_state(dict(list(rows.items())[:-1]), 0)

    def test_relay_key_root_must_be_empty(self):
        rows = {name: 0 for name in REQUIRED_ZERO_TABLES}
        with self.assertRaisesRegex(GateStop, "RELAY_KEYS_NOT_EMPTY"):
            require_initialized_zero_business_state(rows, 1)


if __name__ == "__main__":
    unittest.main()
