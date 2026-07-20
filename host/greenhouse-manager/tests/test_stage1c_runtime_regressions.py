from __future__ import annotations

import importlib.util
import json
import queue
import sys
import threading
import time
import types
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import Mock

from greenhouse_manager import dynsec_api
from greenhouse_manager.dynsec_api import (
    CONTROL_TOPIC,
    RESPONSE_TOPIC,
    DynsecError,
    DynsecProvisioner,
    DynsecRollbackError,
    PahoDynsecTransport,
    baseline_commands,
    create_client_command,
    legacy_anonymous_shadow_commands,
    set_client_password_command,
)
from greenhouse_manager.dynsec_plan import (
    build_node_provisioning_plan,
    generate_node_credentials,
)
from greenhouse_manager.service_identity_plan import (
    build_service_identity_plan,
    generate_service_credentials,
)


class FakeReasonCode:
    def __init__(self, *, failure: bool, label: str) -> None:
        self.is_failure = failure
        self.label = label

    def __str__(self) -> str:
        return self.label


def load_verify_module() -> Any:
    fake_client_module = types.ModuleType("paho.mqtt.client")
    fake_client_module.MQTT_ERR_SUCCESS = 0
    fake_client_module.MQTTv5 = 5

    class CallbackAPIVersion:
        VERSION2 = 2

    fake_client_module.CallbackAPIVersion = CallbackAPIVersion
    fake_client_module.Client = object
    fake_client_module.ConnectFlags = object
    fake_client_module.DisconnectFlags = object
    fake_client_module.ReasonCode = FakeReasonCode
    fake_client_module.Properties = object
    fake_client_module.MQTTMessage = object

    fake_mqtt_package = types.ModuleType("paho.mqtt")
    fake_mqtt_package.client = fake_client_module
    fake_paho_package = types.ModuleType("paho")
    fake_paho_package.mqtt = fake_mqtt_package

    previous = {
        name: sys.modules.get(name)
        for name in ("paho", "paho.mqtt", "paho.mqtt.client")
    }
    sys.modules["paho"] = fake_paho_package
    sys.modules["paho.mqtt"] = fake_mqtt_package
    sys.modules["paho.mqtt.client"] = fake_client_module
    try:
        repository_root = Path(__file__).resolve().parents[3]
        verify_path = (
            repository_root
            / "infra"
            / "compose"
            / "m2-dynsec"
            / "verify.py"
        )
        spec = importlib.util.spec_from_file_location(
            "stage1c_verify_under_test",
            verify_path,
        )
        if spec is None or spec.loader is None:
            raise AssertionError("unable to load verify.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


class Stage1CExistingContractTests(unittest.TestCase):
    def plan_and_credentials(self) -> tuple[Any, Any]:
        plan = build_node_provisioning_plan(
            system_id="greenhouse",
            node_id="gh-n1-a9f2f8",
            generation=1,
        )
        credentials = generate_node_credentials(
            plan,
            random_bytes=lambda size: bytes(range(size)),
        )
        return plan, credentials

    def test_baseline_and_identity_contracts(self) -> None:
        plan, credentials = self.plan_and_credentials()
        defaults = {
            entry["acltype"]: entry["allow"]
            for entry in baseline_commands(plan)[0]["acls"]
        }
        self.assertEqual(
            defaults,
            {
                "publishClientSend": False,
                "publishClientReceive": False,
                "subscribe": False,
                "unsubscribe": True,
            },
        )
        command = create_client_command(plan, credentials)
        self.assertEqual(command["username"], "ghn_gh-n1-a9f2f8")
        self.assertEqual(command["clientid"], "gh-n1-a9f2f8")
        self.assertEqual(
            command["roles"],
            [{"rolename": plan.role_name, "priority": 100}],
        )

        for service in ("provisioning", "manager", "homeassistant"):
            service_plan = build_service_identity_plan(
                system_id="greenhouse",
                service=service,
                generation=1,
            )
            service_credentials = generate_service_credentials(
                service_plan,
                random_bytes=lambda size: bytes(range(size)),
            )
            self.assertEqual(
                create_client_command(
                    service_plan,
                    service_credentials,
                )["clientid"],
                f"gh-{service}-greenhouse",
            )
            self.assertNotIn(
                service_credentials.password,
                repr(service_credentials),
            )

    def test_legacy_shadow_contract(self) -> None:
        role, group, anonymous = legacy_anonymous_shadow_commands()
        acl_map = {
            (acl["acltype"], acl["topic"]): acl["allow"]
            for acl in role["acls"]
        }
        self.assertTrue(
            acl_map[("publishClientSend", "#")]
        )
        self.assertTrue(
            acl_map[("subscribePattern", "#")]
        )
        self.assertFalse(
            acl_map[("publishClientSend", "$CONTROL/#")]
        )
        self.assertFalse(
            acl_map[("subscribePattern", "$CONTROL/#")]
        )
        self.assertEqual(
            group["roles"],
            [
                {
                    "rolename": "gh-legacy-anonymous-shadow",
                    "priority": 100,
                }
            ],
        )
        self.assertEqual(
            anonymous["command"],
            "setAnonymousGroup",
        )

    def test_provision_and_rotation_success_and_rollback(self) -> None:
        plan, current = self.plan_and_credentials()
        replacement_plan = build_node_provisioning_plan(
            system_id=plan.system_id,
            node_id=plan.node_id,
            generation=2,
        )
        replacement = generate_node_credentials(
            replacement_plan,
            random_bytes=lambda size: bytes(reversed(range(size))),
        )

        class Transport:
            def __init__(self) -> None:
                self.calls: list[tuple[dict[str, Any], ...]] = []
                self.fail_create = False

            def execute(
                self,
                commands: tuple[dict[str, Any], ...],
            ) -> tuple[dict[str, Any], ...]:
                self.calls.append(commands)
                if (
                    self.fail_create
                    and commands[0]["command"] == "createClient"
                ):
                    raise DynsecError("injected failure")
                return tuple(
                    {"command": command["command"]}
                    for command in commands
                )

        transport = Transport()
        transport.fail_create = True
        with self.assertRaisesRegex(
            DynsecError,
            "injected failure",
        ):
            DynsecProvisioner(transport).provision(
                plan,
                current,
            )
        self.assertEqual(
            [
                call[0]["command"]
                for call in transport.calls
            ],
            [
                "createRole",
                "createClient",
                "deleteClient",
                "deleteRole",
            ],
        )

        transport = Transport()
        verified: list[Any] = []
        DynsecProvisioner(transport).rotate_password(
            plan,
            current,
            replacement,
            verified.append,
        )
        self.assertEqual(verified, [replacement])
        self.assertEqual(
            transport.calls,
            [
                (
                    set_client_password_command(
                        plan,
                        replacement,
                    ),
                )
            ],
        )

        transport = Transport()

        def reject(_credentials: Any) -> None:
            raise RuntimeError("probe rejected")

        with self.assertRaisesRegex(
            RuntimeError,
            "probe rejected",
        ):
            DynsecProvisioner(transport).rotate_password(
                plan,
                current,
                replacement,
                reject,
            )
        self.assertEqual(
            transport.calls,
            [
                (
                    set_client_password_command(
                        plan,
                        replacement,
                    ),
                ),
                (
                    set_client_password_command(
                        plan,
                        current,
                    ),
                ),
            ],
        )

    def test_rotation_rejects_generation_and_sanitizes_errors(self) -> None:
        plan, current = self.plan_and_credentials()

        class Transport:
            def __init__(self) -> None:
                self.calls: list[Any] = []

            def execute(self, commands: Any) -> tuple[Any, ...]:
                self.calls.append(commands)
                return ()

        transport = Transport()
        with self.assertRaisesRegex(
            ValueError,
            "generation must increase",
        ):
            DynsecProvisioner(transport).rotate_password(
                plan,
                current,
                current,
                lambda _credentials: None,
            )
        self.assertEqual(transport.calls, [])

        payload = (
            b'{"responses":[{"command":"createClient",'
            b'"error":"secret details"}]}'
        )
        with self.assertRaises(DynsecError) as captured:
            PahoDynsecTransport._decode_response(payload)
        self.assertIn("createClient", str(captured.exception))
        self.assertNotIn("secret details", str(captured.exception))


class Stage1CDynsecTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_mqtt = dynsec_api.mqtt
        dynsec_api.mqtt = types.SimpleNamespace(
            MQTT_ERR_SUCCESS=0,
        )

    def tearDown(self) -> None:
        dynsec_api.mqtt = self.previous_mqtt

    def test_ignores_unrelated_response_then_accepts_correlated(self) -> None:
        client = Mock()
        client.subscribe.return_value = (0, 1)
        transport = PahoDynsecTransport(client, timeout_s=0.1)

        def publish_side_effect(*args: Any, **kwargs: Any) -> Any:
            payload = json.loads(kwargs["payload"])
            correlation = payload["commands"][0]["correlationData"]
            transport.on_message(
                client,
                None,
                Mock(
                    topic=RESPONSE_TOPIC,
                    payload=json.dumps(
                        {
                            "responses": [
                                {
                                    "command": "listClients",
                                    "correlationData": "healthcheck",
                                }
                            ]
                        }
                    ).encode(),
                ),
            )
            transport.on_message(
                client,
                None,
                Mock(
                    topic=RESPONSE_TOPIC,
                    payload=json.dumps(
                        {
                            "responses": [
                                {
                                    "command": "listClients",
                                    "correlationData": correlation,
                                }
                            ]
                        }
                    ).encode(),
                ),
            )
            return Mock(rc=0)

        client.publish.side_effect = publish_side_effect

        result = transport.execute(({"command": "listClients"},))

        self.assertEqual(result[0]["command"], "listClients")
        self.assertEqual(transport.ignored_response_count, 1)
        published = json.loads(client.publish.call_args.kwargs["payload"])
        self.assertTrue(
            published["commands"][0]["correlationData"]
        )
        self.assertEqual(client.publish.call_args.args[0], CONTROL_TOPIC)

    def test_rejects_wrong_command_count_and_correlation(self) -> None:
        cases = (
            [
                {
                    "command": "getClient",
                    "correlationData": "{correlation}",
                }
            ],
            [
                {
                    "command": "listClients",
                    "correlationData": "{correlation}",
                },
                {
                    "command": "listClients",
                    "correlationData": "{correlation}",
                },
            ],
            [
                {
                    "command": "listClients",
                    "correlationData": "wrong",
                }
            ],
        )

        for responses in cases:
            with self.subTest(responses=responses):
                client = Mock()
                client.subscribe.return_value = (0, 1)
                transport = PahoDynsecTransport(
                    client,
                    timeout_s=0.01,
                )

                def publish_side_effect(
                    *args: Any,
                    **kwargs: Any,
                ) -> Any:
                    payload = json.loads(kwargs["payload"])
                    correlation = (
                        payload["commands"][0]["correlationData"]
                    )
                    rendered = [
                        {
                            key: (
                                correlation
                                if value == "{correlation}"
                                else value
                            )
                            for key, value in response.items()
                        }
                        for response in responses
                    ]
                    transport.on_message(
                        client,
                        None,
                        Mock(
                            topic=RESPONSE_TOPIC,
                            payload=json.dumps(
                                {"responses": rendered}
                            ).encode(),
                        ),
                    )
                    return Mock(rc=0)

                client.publish.side_effect = publish_side_effect

                with self.assertRaisesRegex(
                    DynsecError,
                    "correlated response timed out ignored=1",
                ):
                    transport.execute(
                        ({"command": "listClients"},)
                    )

    def test_forbids_caller_owned_correlation(self) -> None:
        client = Mock()
        client.subscribe.return_value = (0, 1)
        transport = PahoDynsecTransport(client, timeout_s=0.1)

        with self.assertRaisesRegex(
            ValueError,
            "caller supplied correlationData",
        ):
            transport.execute(
                (
                    {
                        "command": "listClients",
                        "correlationData": "caller-owned",
                    },
                )
            )

        client.publish.assert_not_called()


class Stage1CRollbackContractTests(unittest.TestCase):
    def test_provisioning_preserves_primary_and_rollback_contract(self) -> None:
        plan = build_node_provisioning_plan(
            system_id="greenhouse",
            node_id="gh-stage1c-regression",
            generation=1,
        )
        credentials = generate_node_credentials(
            plan,
            random_bytes=lambda size: bytes(range(size)),
        )

        class Transport:
            def __init__(self) -> None:
                self.commands: list[str] = []

            def execute(
                self,
                commands: tuple[dict[str, Any], ...],
            ) -> tuple[dict[str, Any], ...]:
                command = str(commands[0]["command"])
                self.commands.append(command)
                if command == "createClient":
                    raise DynsecError("primary secret")
                if command == "deleteClient":
                    raise DynsecError("rollback secret")
                return ({"command": command},)

        transport = Transport()

        with self.assertRaises(DynsecRollbackError) as captured:
            DynsecProvisioner(transport).provision(
                plan,
                credentials,
            )

        self.assertEqual(
            captured.exception.rollback_failures,
            (("deleteClient", "DynsecError"),),
        )
        self.assertIsInstance(
            captured.exception.__cause__,
            DynsecError,
        )
        self.assertNotIn("primary secret", str(captured.exception))
        self.assertNotIn("rollback secret", str(captured.exception))


class Stage1CVerifySessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verify = load_verify_module()

    def make_session(self) -> Any:
        session = self.verify.Session.__new__(self.verify.Session)
        session.connected = threading.Event()
        session.connection_allowed = None
        session.messages = queue.Queue()
        session.subscriptions = {}
        session.subscription_lock = threading.Lock()
        session.publishes = {}
        session.publish_lock = threading.Lock()
        session.disconnected = threading.Event()
        session.disconnect_reason = None
        session.unexpected_disconnect = False
        session._closing = False
        session.message_hook = None
        return session

    def test_suback_arriving_before_subscribe_returns_is_not_lost(
        self,
    ) -> None:
        session = self.make_session()
        callback_started = threading.Event()
        callback_done = threading.Event()

        class Client:
            def subscribe(
                client_self,
                _topic: str,
                qos: int,
            ) -> tuple[int, int]:
                self.assertEqual(qos, 1)

                def deliver() -> None:
                    callback_started.set()
                    session._on_subscribe(
                        client_self,
                        None,
                        41,
                        [
                            FakeReasonCode(
                                failure=False,
                                label="Granted QoS 1",
                            )
                        ],
                        None,
                    )
                    callback_done.set()

                threading.Thread(
                    target=deliver,
                    daemon=True,
                ).start()
                self.assertTrue(callback_started.wait(1))
                return (0, 41)

        session.client = Client()

        self.assertTrue(session.subscribe("gh/#"))
        self.assertTrue(callback_done.wait(1))
        self.assertEqual(session.subscriptions, {})

    def test_suback_denial_and_timeout(self) -> None:
        for denied in (True, False):
            with self.subTest(denied=denied):
                session = self.make_session()

                class Client:
                    def subscribe(
                        client_self,
                        _topic: str,
                        qos: int,
                    ) -> tuple[int, int]:
                        mid = 51

                        if denied:
                            def deliver() -> None:
                                time.sleep(0.001)
                                session._on_subscribe(
                                    client_self,
                                    None,
                                    mid,
                                    [
                                        FakeReasonCode(
                                            failure=True,
                                            label="Not authorized",
                                        )
                                    ],
                                    None,
                                )

                            threading.Thread(
                                target=deliver,
                                daemon=True,
                            ).start()
                        return (0, mid)

                session.client = Client()

                if denied:
                    self.assertFalse(session.subscribe("$CONTROL/#"))
                else:
                    original_wait = threading.Event.wait

                    def short_wait(
                        event_self: threading.Event,
                        timeout: float | None = None,
                    ) -> bool:
                        return original_wait(event_self, 0.01)

                    session.subscriptions = {}
                    with unittest.mock.patch.object(
                        threading.Event,
                        "wait",
                        short_wait,
                    ):
                        with self.assertRaisesRegex(
                            AssertionError,
                            "SUBACK timed out",
                        ):
                            session.subscribe("gh/#")

    def test_puback_not_authorized_is_checked(self) -> None:
        session = self.make_session()

        class Info:
            rc = 0
            mid = 61

        class Client:
            def publish(
                client_self,
                _topic: str,
                *,
                payload: bytes,
                qos: int,
                retain: bool,
            ) -> Info:
                def deliver() -> None:
                    time.sleep(0.001)
                    session._on_publish(
                        client_self,
                        None,
                        61,
                        FakeReasonCode(
                            failure=True,
                            label="Not authorized",
                        ),
                        None,
                    )

                threading.Thread(
                    target=deliver,
                    daemon=True,
                ).start()
                return Info()

        session.client = Client()

        self.assertFalse(
            session.publish(
                "$CONTROL/dynamic-security/v1",
                expect_allowed=False,
            )
        )
        with self.assertRaisesRegex(
            AssertionError,
            "was not allowed",
        ):
            session.publish(
                "$CONTROL/dynamic-security/v1",
                expect_allowed=True,
            )

    def test_disconnect_state_is_recorded(self) -> None:
        session = self.make_session()
        session._on_disconnect(
            Mock(),
            None,
            Mock(),
            FakeReasonCode(
                failure=True,
                label="Server unavailable",
            ),
            None,
        )

        self.assertTrue(session.disconnected.is_set())
        self.assertTrue(session.unexpected_disconnect)
        self.assertEqual(
            session.disconnect_reason,
            "Server unavailable",
        )

    def test_legacy_probe_uses_manager_state_topic(self) -> None:
        calls: list[tuple[str, str]] = []

        class Legacy:
            def drain(self) -> None:
                calls.append(("legacy", "drain"))

            def wait_for(self, topic: str) -> bool:
                calls.append(("legacy", topic))
                return True

        class Manager:
            def publish(self, topic: str) -> bool:
                calls.append(("manager", topic))
                return True

        self.verify.assert_legacy_post_rollback_delivery(
            Legacy(),
            Manager(),
        )

        expected = self.verify.LEGACY_POST_ROLLBACK_TOPIC
        self.assertEqual(
            expected,
            "gh/v1/greenhouse/state/legacy-node/rollback-probe",
        )
        self.assertIn(("manager", expected), calls)
        self.assertIn(("legacy", expected), calls)

    def test_cleanup_closes_sessions_and_deprovisions_plans(self) -> None:
        cleanup = self.verify.VerificationCleanup()
        calls: list[str] = []

        class Session:
            def __init__(self, name: str) -> None:
                self.name = name

            def close(self) -> None:
                calls.append(f"close:{self.name}")

        class Plan:
            role_name = "gh-stage1c-role"

        class Provisioner:
            def deprovision(self, _plan: Any) -> None:
                calls.append("deprovision")

        admin = Session("admin")
        worker = Session("worker")
        plan = Plan()
        cleanup.admin_session = admin
        cleanup.sessions = [admin, worker]
        cleanup.provisioned_plans = [plan]
        cleanup.provisioner = Provisioner()

        cleanup.cleanup()

        self.assertEqual(
            calls,
            ["close:worker", "deprovision", "close:admin"],
        )
        self.assertEqual(cleanup.provisioned_plans, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
