from __future__ import annotations

import json
import re

_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")
_NONCE = re.compile(r"^[A-Za-z0-9_-]{3,96}$")
_REQUEST_SCHEMA = "gh.n3w-product.peer-auth-time-request/1"
_RESPONSE_SCHEMA = "gh.n3w-product.peer-auth-time-response/1"


class PeerAuthorizationTimeRejected(ValueError):
    pass


class PeerAuthorizationTimeMqttAdapter:
    """Transport-only Manager epoch exchange for the isolated S5 Relay.

    This adapter does not authorize peers. It only supplies a short-lived
    Manager-epoch anchor so the Relay can timestamp the existing S4 request.
    The S4 PeerAuthorizationService remains the sole authorization authority.
    """

    def __init__(self, *, system_id: str) -> None:
        if _ID.fullmatch(system_id) is None:
            raise ValueError("system_id_invalid")
        self.system_id = system_id

    @property
    def request_subscription(self) -> str:
        return (
            f"gh/v1/{self.system_id}/ingress/node/+/"
            "relay-peer-auth/time-request"
        )

    @staticmethod
    def response_topic(*, system_id: str, relay_node_id: str) -> str:
        if _ID.fullmatch(system_id) is None or _ID.fullmatch(relay_node_id) is None:
            raise PeerAuthorizationTimeRejected("time_topic_identity_invalid")
        return (
            f"gh/v1/{system_id}/out/node/{relay_node_id}/"
            "relay-peer-auth/time"
        )

    def is_request_topic(self, topic: str) -> bool:
        try:
            system_id, _relay_node_id = self._parse_request_topic(topic)
        except PeerAuthorizationTimeRejected:
            return False
        return system_id == self.system_id

    def handle(
        self,
        *,
        topic: str,
        payload: bytes,
        now_ms: int,
    ) -> tuple[str, bytes]:
        system_id, relay_node_id = self._parse_request_topic(topic)
        if system_id != self.system_id:
            raise PeerAuthorizationTimeRejected("cross_system_rejected")
        if type(now_ms) is not int or now_ms <= 0:
            raise PeerAuthorizationTimeRejected("authority_time_invalid")

        try:
            document = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PeerAuthorizationTimeRejected("time_request_json_invalid") from error
        if (
            not isinstance(document, dict)
            or set(document) != {"nonce", "schema"}
            or document["schema"] != _REQUEST_SCHEMA
            or not isinstance(document["nonce"], str)
            or _NONCE.fullmatch(document["nonce"]) is None
        ):
            raise PeerAuthorizationTimeRejected("time_request_fields_invalid")

        response = {
            "authority_now_ms": now_ms,
            "nonce": document["nonce"],
            "schema": _RESPONSE_SCHEMA,
        }
        return (
            self.response_topic(
                system_id=system_id,
                relay_node_id=relay_node_id,
            ),
            json.dumps(
                response,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
        )

    @staticmethod
    def _parse_request_topic(topic: str) -> tuple[str, str]:
        parts = topic.split("/")
        if (
            len(parts) != 8
            or parts[0:2] != ["gh", "v1"]
            or parts[3:5] != ["ingress", "node"]
            or parts[6:8] != ["relay-peer-auth", "time-request"]
            or _ID.fullmatch(parts[2]) is None
            or _ID.fullmatch(parts[5]) is None
        ):
            raise PeerAuthorizationTimeRejected("time_request_topic_rejected")
        return parts[2], parts[5]
