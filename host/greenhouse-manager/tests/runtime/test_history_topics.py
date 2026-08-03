from __future__ import annotations

import pytest

from greenhouse_manager.runtime.topics import (
    history_replay_ack_topic,
    history_replay_subscription,
    parse_history_replay_topic,
)


def test_history_topics_are_separate_from_canonical_state() -> None:
    parsed = parse_history_replay_topic("gh/v1/system-001/ingress/node/node-0001/history")

    assert parsed.system_id == "system-001"
    assert parsed.node_id == "node-0001"
    assert history_replay_subscription("system-001") == (
        "gh/v1/system-001/ingress/node/+/history"
    )
    assert history_replay_ack_topic("system-001", "node-0001") == (
        "gh/v1/system-001/command/node/node-0001/history/ack"
    )
    assert "/state/" not in history_replay_ack_topic("system-001", "node-0001")


@pytest.mark.parametrize(
    "topic",
    [
        "gh/v1/system-001/ingress/node/node-0001/telemetry",
        "gh/v1/system-001/state/node-0001/history",
        "gh/v1/system-001/ingress/node/node-0001/history/extra",
    ],
)
def test_rejects_non_history_topics(topic: str) -> None:
    with pytest.raises(ValueError, match="Unsupported history replay topic"):
        parse_history_replay_topic(topic)
