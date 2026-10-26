from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


MANIFEST_RELATIVE = Path("docs/development/N3W_CI_POLICY_MANIFEST_V1.json")
WORKFLOW_RELATIVE = Path(".github/workflows")

VALID_EXCEPTIONS = {
    "missing_pr_cancel",
    "missing_timeout",
    "heavy_draft_execution",
}

CI_READY_SNIPPETS = (
    "workflow_dispatch:",
    "ready_for_review",
    "converted_to_draft",
    "labeled",
    "unlabeled",
    "edited",
    "github.event.pull_request.draft == false",
    "contains(github.event.pull_request.labels.*.name, 'ci-ready')",
    "contains(github.event.pull_request.body, 'CI_READY=true')",
    "concurrency:",
    "cancel-in-progress:",
    "timeout-minutes:",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _has_pull_request(text: str) -> bool:
    return re.search(r"(?m)^\s*pull_request:\s*$", text) is not None


def _has_main_push(text: str) -> bool:
    if "push:" not in text:
        return False
    if re.search(r"(?m)^\s*-\s*main\s*$", text) is not None:
        return True
    return re.search(
        r"(?m)^\s*branches:\s*\[[^\]]*\bmain\b[^\]]*\]\s*$",
        text,
    ) is not None


def _has_cancel(text: str) -> bool:
    return "concurrency:" in text and "cancel-in-progress:" in text


def _has_timeout(text: str) -> bool:
    return "timeout-minutes:" in text


def _has_qemu_or_buildx(text: str) -> bool:
    return "docker/setup-qemu-action@" in text or "docker/setup-buildx-action@" in text


def audit(root: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    manifest_file = manifest_path or root / MANIFEST_RELATIVE
    manifest = json.loads(_read(manifest_file))
    errors: list[str] = []

    if manifest.get("schema") != "gh.n3w-ci-policy-manifest/1":
        errors.append("manifest schema must be gh.n3w-ci-policy-manifest/1")

    revision = manifest.get("policy_revision")
    if not isinstance(revision, str) or not revision:
        errors.append("manifest policy_revision is missing")
        revision = "INVALID"

    classes = set(manifest.get("valid_classes") or [])
    draft_policies = set(manifest.get("valid_draft_policies") or [])
    records = manifest.get("workflows")
    if not isinstance(records, dict):
        errors.append("manifest workflows must be an object")
        records = {}

    workflow_dir = root / WORKFLOW_RELATIVE
    actual = {
        path.name
        for path in workflow_dir.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    }
    registered = set(records)

    for name in sorted(actual - registered):
        errors.append(f"unregistered workflow: {name}")
    for name in sorted(registered - actual):
        errors.append(f"manifest points to missing workflow: {name}")

    class_counts: Counter[str] = Counter()
    debt_counts: Counter[str] = Counter()

    for name in sorted(actual & registered):
        record = records[name]
        if not isinstance(record, dict):
            errors.append(f"{name}: manifest entry must be an object")
            continue

        workflow_class = record.get("class")
        draft_policy = record.get("draft_policy")
        exceptions = record.get("exceptions") or {}

        if workflow_class not in classes:
            errors.append(f"{name}: invalid class {workflow_class!r}")
        else:
            class_counts[workflow_class] += 1

        if draft_policy not in draft_policies:
            errors.append(f"{name}: invalid draft_policy {draft_policy!r}")

        if not isinstance(exceptions, dict):
            errors.append(f"{name}: exceptions must be an object")
            exceptions = {}

        unknown = set(exceptions) - VALID_EXCEPTIONS
        for code in sorted(unknown):
            errors.append(f"{name}: unknown exception {code}")
        for code, reason in exceptions.items():
            if code in VALID_EXCEPTIONS:
                debt_counts[code] += 1
            if not isinstance(reason, str) or len(reason.strip()) < 20:
                errors.append(f"{name}: exception {code} requires a concrete reason")

        text = _read(workflow_dir / name)
        has_pr = _has_pull_request(text)
        has_cancel = _has_cancel(text)
        has_timeout = _has_timeout(text)
        heavy_runtime = _has_qemu_or_buildx(text)

        if has_pr and not has_cancel and "missing_pr_cancel" not in exceptions:
            errors.append(f"{name}: PR workflow missing concurrency/cancel-in-progress")
        if has_cancel and "missing_pr_cancel" in exceptions:
            errors.append(f"{name}: stale missing_pr_cancel exception")

        if not has_timeout and "missing_timeout" not in exceptions:
            errors.append(f"{name}: workflow missing timeout-minutes")
        if has_timeout and "missing_timeout" in exceptions:
            errors.append(f"{name}: stale missing_timeout exception")

        if heavy_runtime and workflow_class in {"FAST", "MODEL"}:
            errors.append(
                f"{name}: QEMU/Buildx workflow cannot be classified as {workflow_class}"
            )

        if heavy_runtime and has_pr and draft_policy != "ci-ready":
            if "heavy_draft_execution" not in exceptions:
                errors.append(
                    f"{name}: QEMU/Buildx PR workflow must use ci-ready or record legacy debt"
                )

        if draft_policy == "ci-ready":
            if not has_pr:
                errors.append(f"{name}: ci-ready policy requires pull_request trigger")
            for snippet in CI_READY_SNIPPETS:
                if snippet not in text:
                    errors.append(f"{name}: ci-ready contract missing {snippet!r}")
            if not _has_main_push(text):
                errors.append(f"{name}: ci-ready workflow must retain main push execution")

        if draft_policy == "legacy-run":
            if "heavy_draft_execution" not in exceptions:
                errors.append(
                    f"{name}: legacy-run requires explicit heavy_draft_execution debt"
                )
        elif "heavy_draft_execution" in exceptions:
            errors.append(f"{name}: stale heavy_draft_execution exception")

    marker = f"N3W_CI_POLICY_REVISION={revision}"
    authorities = manifest.get("authority_documents") or []
    if not authorities:
        errors.append("manifest authority_documents is empty")
    for relative in authorities:
        path = root / relative
        if not path.is_file():
            errors.append(f"authority document missing: {relative}")
            continue
        if marker not in _read(path):
            errors.append(f"authority revision marker missing in {relative}")

    return {
        "schema": manifest.get("schema"),
        "policy_revision": revision,
        "workflow_count": len(actual),
        "class_counts": dict(sorted(class_counts.items())),
        "debt_counts": dict(sorted(debt_counts.items())),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    result = audit(args.root, args.manifest)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    if result["errors"]:
        for error in result["errors"]:
            print(f"CI_POLICY_ERROR={error}", file=sys.stderr)
        print("CI_POLICY_ALIGNMENT=FAIL")
        return 1
    print("CI_POLICY_ALIGNMENT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
