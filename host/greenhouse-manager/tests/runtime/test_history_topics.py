from __future__ import annotations

import pytest

from greenhouse_manager.runtime.topics import (
    history_replay_ack_topic,
    history_replay_subscription,
    parse_history_replay_topic,
)


def test_history_topics_are_isolated_from_canonical_and_match_node_acl() -> None:
    ingress = history_replay_subscription("system-001")
    ack = history_replay_ack_topic("system-001", "node-0001")

    assert ingress == "gh/v1/system-001/ingress/node/+/history"
    assert ack == "gh/v1/system-001/out/node/node-0001/history/ack"
    assert "/state/" not in ingress
    assert "/state/" not in ack
    assert "/command/" not in ack
    assert ack.startswith("gh/v1/system-001/out/node/node-0001/")


def test_history_topic_parser_requires_exact_ingress_shape() -> None:
    parsed = parse_history_replay_topic(
        "gh/v1/system-001/ingress/node/node-0001/history"
    )
    assert parsed.system_id == "system-001"
    assert parsed.node_id == "node-0001"

    with pytest.raises(ValueError):
        parse_history_replay_topic(
            "gh/v1/system-001/state/node-0001/history"
        )
    with pytest.raises(ValueError):
        parse_history_replay_topic(
            "gh/v1/system-001/ingress/node/node-0001/history/extra"
        )
