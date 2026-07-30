from __future__ import annotations

from collections.abc import Iterable


class NestedSha256SumsContractError(RuntimeError):
    pass


def normalize_paths(values: Iterable[str]) -> set[str]:
    normalized: set[str] = set()
    for raw in values:
        if not isinstance(raw, str):
            raise NestedSha256SumsContractError("PRIVATE_NESTED_SHA256SUMS_SET_INVALID")
        value = raw.replace("\\", "/").strip()
        if not value or value.startswith("/") or value.startswith("../") or "/../" in value:
            raise NestedSha256SumsContractError("PRIVATE_NESTED_SHA256SUMS_SET_INVALID")
        normalized.add(value)
    return normalized


def verify_nested_sha256sums(
    *,
    observed_nested: Iterable[str],
    root_manifest_names: Iterable[str],
    expected_nested: Iterable[str],
) -> set[str]:
    observed = normalize_paths(observed_nested)
    covered = normalize_paths(root_manifest_names)
    expected = normalize_paths(expected_nested)

    if not observed.issubset(covered):
        raise NestedSha256SumsContractError("PRIVATE_NESTED_SHA256SUMS_NOT_COVERED")
    if observed != expected:
        raise NestedSha256SumsContractError("PRIVATE_NESTED_SHA256SUMS_SET_INVALID")
    return observed


def reproduce_retired_g03_comparison(
    *,
    observed_nested: set[str],
    expected_nested_tuple: tuple[str, ...],
) -> None:
    if observed_nested != expected_nested_tuple:
        raise NestedSha256SumsContractError("PRIVATE_NESTED_SHA256SUMS_SET_INVALID")
