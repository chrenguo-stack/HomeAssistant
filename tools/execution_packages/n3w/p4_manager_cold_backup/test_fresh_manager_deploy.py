from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import fresh_manager_deploy as deploy
from test_cutover_contract import image, old_manager


def broker() -> dict:
    return {
        "Id": "broker-id",
        "Image": "broker-image",
        "RestartCount": 0,
        "State": {"Running": True, "StartedAt": "same-start"},
        "NetworkSettings": {"Networks": {"n3wfc4-private": {}, "n3wfc4-services": {}}},
        "HostConfig": {"PortBindings": {"8883/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8883"}]}},
    }


class FakeOps:
    def __init__(self, fail: str | None = None) -> None:
        self.fail = fail
        self.calls: list[str] = []
        self.context = deploy.DeployContext(
            old_manager(),
            broker(),
            image(),
            123,
            456,
        )
        self.sources = {
            "/var/lib/greenhouse-manager-registration": "/tmp/fresh-registration",
            "/var/lib/greenhouse-manager/n3w": "/tmp/fresh-n3w",
            "/var/lib/greenhouse-manager/n3w/relay-keys": "/tmp/fresh-relay",
        }

    def _step(self, name: str) -> None:
        self.calls.append(name)
        if self.fail == name:
            raise deploy.DeployStop("INJECTED_" + name)

    def preflight(self):
        self._step("preflight")
        return self.context

    def prepare_fresh(self):
        self._step("prepare_fresh")
        return dict(self.sources)

    def shadow_create_and_verify(self):
        self._step("shadow")

    def stop_old(self):
        self._step("stop_old")

    def park_old(self):
        self._step("park_old")

    def create_candidate(self):
        self._step("create_candidate")
        return "candidate-id"

    def start_candidate(self, candidate_id: str):
        self.assert_candidate(candidate_id)
        self._step("start_candidate")

    def postflight(self, candidate_id: str):
        self.assert_candidate(candidate_id)
        self._step("postflight")

    def commit_restart_policy(self, candidate_id: str):
        self.assert_candidate(candidate_id)
        self._step("commit_restart")

    @staticmethod
    def assert_candidate(candidate_id: str):
        if candidate_id != "candidate-id":
            raise AssertionError(candidate_id)


class FreshManagerDeployTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.private = Path(self.temp.name)

    def test_exact_transaction_sequence_commits_only_after_postflight(self) -> None:
        ops = FakeOps()
        state = deploy.execute_transaction(self.private, ops)
        self.assertTrue(state.document["committed"])
        self.assertEqual(
            ops.calls,
            [
                "preflight",
                "prepare_fresh",
                "shadow",
                "stop_old",
                "park_old",
                "create_candidate",
                "start_candidate",
                "postflight",
                "commit_restart",
            ],
        )
        stored = json.loads((self.private / deploy.STATE_FILE).read_text())
        self.assertTrue(stored["committed"])
        self.assertEqual(
            stored["phase"],
            "SUCCESS_COMMIT_KEEP_ORIGINAL_FOR_ROLLBACK",
        )

    def test_each_mutating_failure_stops_before_false_commit(self) -> None:
        failures = (
            "shadow",
            "stop_old",
            "park_old",
            "create_candidate",
            "start_candidate",
            "postflight",
            "commit_restart",
        )
        for step in failures:
            with self.subTest(step=step):
                with tempfile.TemporaryDirectory() as path:
                    private = Path(path)
                    with self.assertRaisesRegex(deploy.DeployStop, "INJECTED_"):
                        deploy.execute_transaction(private, FakeOps(step))
                    state = json.loads((private / deploy.STATE_FILE).read_text())
                    self.assertFalse(state["committed"])

    def test_preflight_failure_creates_no_transaction_state(self) -> None:
        with self.assertRaisesRegex(deploy.DeployStop, "INJECTED_preflight"):
            deploy.execute_transaction(self.private, FakeOps("preflight"))
        self.assertFalse((self.private / deploy.STATE_FILE).exists())

    def test_transaction_state_is_nonreplayable(self) -> None:
        deploy.execute_transaction(self.private, FakeOps())
        with self.assertRaisesRegex(deploy.DeployStop, "TRANSACTION_ALREADY_EXISTS_NO_REPLAY"):
            deploy.execute_transaction(self.private, FakeOps())

    def test_broker_started_at_or_restart_drift_blocks(self) -> None:
        before = broker()
        changed = broker()
        changed["State"]["StartedAt"] = "different"
        with self.assertRaisesRegex(deploy.DeployStop, "BROKER_STARTED_AT_CHANGED"):
            deploy.broker_unchanged(before, changed)
        changed = broker()
        changed["RestartCount"] = 1
        with self.assertRaisesRegex(deploy.DeployStop, "BROKER_RESTART_COUNT_CHANGED"):
            deploy.broker_unchanged(before, changed)

    def test_create_command_uses_fresh_rw_sources_and_preserves_ro_secrets(self) -> None:
        old = old_manager()
        sources = {
            "/var/lib/greenhouse-manager-registration": "/fresh/registration",
            "/var/lib/greenhouse-manager/n3w": "/fresh/n3w",
            "/var/lib/greenhouse-manager/n3w/relay-keys": "/fresh/relay",
        }
        env = self.private / "env"
        env.write_text("GH_MQTT_TLS=1\n")
        command = deploy.create_command(old, image()["Id"], "shadow", sources, env)
        joined = "\n".join(command)
        for source in sources.values():
            self.assertIn("src=" + source, joined)
        original = {
            mount["Destination"]: mount["Source"]
            for mount in old["Mounts"]
        }
        for destination in sources:
            self.assertNotIn("src=" + original[destination] + ",dst=" + destination, joined)
        for destination in (
            "/run/secrets/provisioning_password",
            "/run/secrets/broker-ca.pem",
            "/run/secrets/gh_manager_mqtt_password",
        ):
            self.assertIn(
                "src=" + original[destination] + ",dst=" + destination,
                joined,
            )

    def test_tls_contract_rejects_non_tls_or_wrong_port(self) -> None:
        old = old_manager()
        deploy._tls_port_contract(old)
        old["Config"]["Env"][0] = "GH_MQTT_TLS=0"
        with self.assertRaisesRegex(deploy.DeployStop, "MANAGER_MQTT_TLS_NOT_ENABLED"):
            deploy._tls_port_contract(old)
        old = old_manager()
        old["Config"]["Env"] = [
            "GH_MQTT_PORT=1883" if item.startswith("GH_MQTT_PORT=") else item
            for item in old["Config"]["Env"]
        ]
        with self.assertRaisesRegex(deploy.DeployStop, "MANAGER_MQTT_PORT_NOT_8883"):
            deploy._tls_port_contract(old)


if __name__ == "__main__":
    unittest.main()
