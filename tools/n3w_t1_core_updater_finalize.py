from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from n3w_t1_core_updater_v2_common import (
    COMPONENTS,
    IMAGE_PREFIXES,
    SHA256,
    TX_SCHEMA_V2,
    UpdaterV2Error,
    canonical,
    sha256_bytes,
)

PRODUCT_ACCEPTANCE_SCHEMA_V1 = "gh.n3w-t1-core-updater-product-acceptance/1"
FINALIZE_CONFIRMATION_V2 = "T1_CORE_UPDATER_FINALIZE"
ACCEPTANCE_AUTHORITY_ID = re.compile(r"^N3W_[A-Za-z0-9_-]{1,190}$")


@dataclass(frozen=True)
class ProductAcceptance:
    component: str
    transaction_sha256: str
    target_image_ref: str
    authority_id: str
    accepted_at_unix: int

    def __post_init__(self) -> None:
        if not isinstance(self.component, str) or self.component not in COMPONENTS:
            raise UpdaterV2Error("product_acceptance_component_invalid")
        if (
            not isinstance(self.transaction_sha256, str)
            or SHA256.fullmatch(self.transaction_sha256) is None
        ):
            raise UpdaterV2Error("product_acceptance_transaction_sha256_invalid")
        if (
            not isinstance(self.target_image_ref, str)
            or not self.target_image_ref.startswith(IMAGE_PREFIXES[self.component])
        ):
            raise UpdaterV2Error("product_acceptance_target_invalid")
        if (
            not isinstance(self.authority_id, str)
            or ACCEPTANCE_AUTHORITY_ID.fullmatch(self.authority_id) is None
        ):
            raise UpdaterV2Error("product_acceptance_authority_invalid")
        if (
            not isinstance(self.accepted_at_unix, int)
            or isinstance(self.accepted_at_unix, bool)
            or self.accepted_at_unix <= 0
        ):
            raise UpdaterV2Error("product_acceptance_time_invalid")

    @classmethod
    def load(cls, path: Path) -> "ProductAcceptance":
        if path.is_symlink() or not path.is_file():
            raise UpdaterV2Error("product_acceptance_invalid")
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise UpdaterV2Error("product_acceptance_invalid") from error
        if not isinstance(doc, dict) or set(doc) != {
            "schema",
            "component",
            "result",
            "transaction_sha256",
            "target_image_ref",
            "authority_id",
            "accepted_at_unix",
        }:
            raise UpdaterV2Error("product_acceptance_shape_invalid")
        if doc.get("schema") != PRODUCT_ACCEPTANCE_SCHEMA_V1:
            raise UpdaterV2Error("product_acceptance_schema_invalid")
        if doc.get("result") != "PASS":
            raise UpdaterV2Error("product_acceptance_not_pass")
        return cls(
            component=doc.get("component"),
            transaction_sha256=doc.get("transaction_sha256"),
            target_image_ref=doc.get("target_image_ref"),
            authority_id=doc.get("authority_id"),
            accepted_at_unix=doc.get("accepted_at_unix"),
        )

    def public(self) -> dict[str, Any]:
        return {
            "schema": PRODUCT_ACCEPTANCE_SCHEMA_V1,
            "component": self.component,
            "result": "PASS",
            "transaction_sha256": self.transaction_sha256,
            "target_image_ref": self.target_image_ref,
            "authority_id": self.authority_id,
            "accepted_at_unix": self.accepted_at_unix,
        }


def committed_transaction_authority(document: dict[str, Any]) -> dict[str, Any]:
    if document.get("schema") != TX_SCHEMA_V2 or document.get("status") != "COMMITTED":
        raise UpdaterV2Error("committed_transaction_required")
    required = (
        "component",
        "post_acceptance_cleanup_required",
        "authorization_id_sha256",
        "authorization_consumed",
        "predecessor_image",
        "predecessor_image_id",
        "predecessor_binding_mode",
        "predecessor_network_mode",
        "predecessor_runtime_contract_sha256",
        "pre_peer_runtime",
        "pre_a1_policy",
        "baseline_sha256",
        "target",
        "target_runtime_image_id",
        "committed_at_unix",
    )
    if any(key not in document for key in required):
        raise UpdaterV2Error("committed_transaction_authority_invalid")
    return {
        "schema": TX_SCHEMA_V2,
        "status": "COMMITTED",
        **{key: copy.deepcopy(document[key]) for key in required},
    }


def committed_transaction_sha256(document: dict[str, Any]) -> str:
    return sha256_bytes(canonical(committed_transaction_authority(document)))


def cleanup_pending_for_successor(document: dict[str, Any] | None) -> bool:
    return (
        isinstance(document, dict)
        and document.get("status") == "COMMITTED"
        and document.get("component") in {"manager", "broker"}
        and document.get("post_acceptance_cleanup_required") is True
        and document.get("cleanup_state") != "ACCEPTED_CLEANUP_COMPLETE"
    )
