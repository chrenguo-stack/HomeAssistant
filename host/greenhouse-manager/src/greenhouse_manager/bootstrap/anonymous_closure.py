from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

ANONYMOUS_CLOSURE_SCHEMA = "gh.h0h1.anonymous-closure-policy/1"
ANONYMOUS_CLOSURE_REPORT_SCHEMA = "gh.h0h1.anonymous-closure-report/1"
REQUIRED_SINGLETON_ROLES = frozenset({"manager", "home_assistant"})
NODE_ROLE = "node"
FORBIDDEN_KEY_FRAGMENTS = ("password", "secret", "token", "private_key")


class AnonymousClosureError(RuntimeError):
    pass


@dataclass(frozen=True)
class AnonymousClosureReport:
    schema: str
    system_id: str
    anonymous_enabled: bool
    authenticated_client_count: int
    node_client_count: int
    all_required_clients_authenticated: bool
    legacy_anonymous_publish_allowed: bool
    legacy_anonymous_subscribe_allowed: bool
    isolated_probe_count: int
    live_apply_enabled: bool
    production_services_modified: bool
    network_operation: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in FORBIDDEN_KEY_FRAGMENTS):
                return True
            if _contains_forbidden_key(nested):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _valid_filter(topic_filter: str) -> bool:
    if not topic_filter or topic_filter.startswith("$CONTROL/"):
        return False
    levels = topic_filter.split("/")
    for index, level in enumerate(levels):
        if "#" in level and (level != "#" or index != len(levels) - 1):
            return False
        if "+" in level and level != "+":
            return False
    return True


def _topic_matches(topic_filter: str, topic: str) -> bool:
    filter_levels = topic_filter.split("/")
    topic_levels = topic.split("/")
    for index, level in enumerate(filter_levels):
        if level == "#":
            return True
        if index >= len(topic_levels):
            return False
        if level != "+" and level != topic_levels[index]:
            return False
    return len(filter_levels) == len(topic_levels)


def _client_index(policy: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    clients = policy.get("clients")
    if not isinstance(clients, list) or not clients:
        raise AnonymousClosureError("anonymous closure clients are missing")
    by_client_id: dict[str, Mapping[str, Any]] = {}
    usernames: set[str] = set()
    role_counts: dict[str, int] = {}
    system_id = policy.get("system_id")
    for client in clients:
        if not isinstance(client, Mapping):
            raise AnonymousClosureError("anonymous closure client is invalid")
        if client.get("system_id") != system_id:
            raise AnonymousClosureError("anonymous closure client system binding drift")
        client_id = client.get("client_id")
        username = client.get("username")
        role = client.get("role")
        generation = client.get("credential_generation")
        if not all(isinstance(value, str) and value for value in (client_id, username, role)):
            raise AnonymousClosureError("anonymous closure client identity is incomplete")
        if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
            raise AnonymousClosureError("anonymous closure credential generation is invalid")
        if client_id in by_client_id or username in usernames:
            raise AnonymousClosureError("anonymous closure client identity is duplicated")
        publish = client.get("publish")
        subscribe = client.get("subscribe")
        if not isinstance(publish, list) or not isinstance(subscribe, list):
            raise AnonymousClosureError("anonymous closure ACL inventory is invalid")
        filters = [*publish, *subscribe]
        if any(not isinstance(value, str) or not _valid_filter(value) for value in filters):
            raise AnonymousClosureError("anonymous closure ACL filter is invalid")
        by_client_id[client_id] = client
        usernames.add(username)
        role_counts[role] = role_counts.get(role, 0) + 1

    for role in REQUIRED_SINGLETON_ROLES:
        if role_counts.get(role) != 1:
            raise AnonymousClosureError(f"anonymous closure requires exactly one {role} client")
    if role_counts.get(NODE_ROLE, 0) < 1:
        raise AnonymousClosureError("anonymous closure requires at least one node client")
    unknown = set(role_counts) - REQUIRED_SINGLETON_ROLES - {NODE_ROLE}
    if unknown:
        raise AnonymousClosureError(f"anonymous closure contains unsupported roles: {sorted(unknown)}")
    return by_client_id


def authorize_topic(
    policy: Mapping[str, Any],
    *,
    client_id: str | None,
    action: str,
    topic: str,
) -> bool:
    if action not in {"publish", "subscribe"}:
        raise ValueError("action must be publish or subscribe")
    if not isinstance(topic, str) or not topic:
        raise ValueError("topic must not be empty")
    anonymous_enabled = policy.get("anonymous_enabled")
    if not isinstance(anonymous_enabled, bool):
        raise AnonymousClosureError("anonymous_enabled must be boolean")
    if client_id is None:
        return anonymous_enabled
    clients = _client_index(policy)
    client = clients.get(client_id)
    if client is None:
        return False
    filters = client[action]
    return any(_topic_matches(topic_filter, topic) for topic_filter in filters)


def validate_anonymous_closure_policy(
    policy: Mapping[str, Any],
) -> AnonymousClosureReport:
    if _contains_forbidden_key(policy):
        raise AnonymousClosureError("anonymous closure policy contains secret-bearing fields")
    if policy.get("schema") != ANONYMOUS_CLOSURE_SCHEMA:
        raise AnonymousClosureError("anonymous closure policy schema is unsupported")
    system_id = policy.get("system_id")
    if not isinstance(system_id, str) or not system_id:
        raise AnonymousClosureError("anonymous closure system_id is missing")
    if policy.get("anonymous_enabled") is not False:
        raise AnonymousClosureError("anonymous closure policy must disable anonymous access")
    if policy.get("live_apply_enabled") is not False:
        raise AnonymousClosureError("anonymous closure policy must keep live apply disabled")
    clients = _client_index(policy)

    probes = policy.get("probes")
    if not isinstance(probes, list) or not probes:
        raise AnonymousClosureError("anonymous closure isolated probes are missing")
    anonymous_publish_seen = False
    anonymous_subscribe_seen = False
    for probe in probes:
        if not isinstance(probe, Mapping):
            raise AnonymousClosureError("anonymous closure probe is invalid")
        action = probe.get("action")
        topic = probe.get("topic")
        client_id = probe.get("client_id")
        expected = probe.get("expected")
        if action not in {"publish", "subscribe"}:
            raise AnonymousClosureError("anonymous closure probe action is invalid")
        if not isinstance(topic, str) or not isinstance(expected, bool):
            raise AnonymousClosureError("anonymous closure probe contract is invalid")
        actual = authorize_topic(
            policy,
            client_id=(str(client_id) if client_id is not None else None),
            action=str(action),
            topic=topic,
        )
        if actual is not expected:
            raise AnonymousClosureError("anonymous closure isolated probe failed")
        if client_id is None and action == "publish" and expected is False:
            anonymous_publish_seen = True
        if client_id is None and action == "subscribe" and expected is False:
            anonymous_subscribe_seen = True

    if not anonymous_publish_seen or not anonymous_subscribe_seen:
        raise AnonymousClosureError(
            "anonymous closure probes must prove anonymous publish and subscribe denial"
        )

    node_count = sum(1 for client in clients.values() if client["role"] == NODE_ROLE)
    return AnonymousClosureReport(
        schema=ANONYMOUS_CLOSURE_REPORT_SCHEMA,
        system_id=system_id,
        anonymous_enabled=False,
        authenticated_client_count=len(clients),
        node_client_count=node_count,
        all_required_clients_authenticated=True,
        legacy_anonymous_publish_allowed=False,
        legacy_anonymous_subscribe_allowed=False,
        isolated_probe_count=len(probes),
        live_apply_enabled=False,
        production_services_modified=False,
        network_operation=False,
    )
