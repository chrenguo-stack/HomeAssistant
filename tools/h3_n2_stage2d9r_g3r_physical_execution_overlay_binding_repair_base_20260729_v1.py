#!/usr/bin/env python3
"""Base validation helpers for corrected-baseline physical overlay."""
from h3_n2_stage2d9r_g3r_physical_execution_overlay_binding_repair_common_20260729_v1 import *

class ContractError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractError(code)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_json_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def validate_sha40(value: object, code: str) -> str:
    require(isinstance(value, str) and HEX40.fullmatch(value) is not None, code)
    return value


def validate_sha256(value: object, code: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value) is not None, code)
    return value


def utc(value: object, code: str) -> datetime:
    require(isinstance(value, str), code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(code) from exc
    require(parsed.tzinfo is not None, code)
    return parsed.astimezone(timezone.utc)


def marker_name_sha256() -> str:
    marker_name = sha256_bytes(REQUEST_06_ID.encode("utf-8")) + ".json"
    return sha256_bytes(marker_name.encode("utf-8"))


def request_05_invalidation_disposition() -> dict[str, Any]:
    return {
        "schema": "gh.h3.n2.stage2d9r-g3r-invalidated-physical-d2-request/1",
        "d2_request_id": REQUEST_05_ID,
        "state": REQUEST_05_INVALID_STATE,
        "request_binding_sha256": REQUEST_05_BINDING_SHA256,
        "request_file_sha256": REQUEST_05_FILE_SHA256,
        "authorization_created": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_request_authorized": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "reason": "FROZEN_EXECUTION_PACKAGE_REMAINS_BOUND_TO_REQUEST_04_POLICY_V1_AND_CANNOT_VALIDATE_REQUEST_05",
        "replacement_request_id": REQUEST_06_ID,
    }


def overlay_binding(*, source_sha: str, wrapper_sha256: str, launcher_sha256: str) -> dict[str, Any]:
    validate_sha40(source_sha, "SOURCE_SHA_INVALID")
    validate_sha256(wrapper_sha256, "WRAPPER_SHA_INVALID")
    validate_sha256(launcher_sha256, "LAUNCHER_SHA_INVALID")
    return {
        "schema": OVERLAY_BINDING_SCHEMA,
        "policy_version": 1,
        "state": "CORRECTED_BASELINE_PHYSICAL_EXECUTION_OVERLAY_FROZEN_UNAUTHORIZED",
        "stage": STAGE,
        "decision_id": DECISION_ID,
        "source_sha": source_sha,
        "base_pr": BASE_PR,
        "base_head_sha": BASE_HEAD_SHA,
        "upstream_artifact_id": UPSTREAM_ARTIFACT_ID,
        "upstream_artifact_sha256": UPSTREAM_ARTIFACT_SHA256,
        "upstream_review_binding_sha256": UPSTREAM_REVIEW_BINDING_SHA256,
        "upstream_execution_package_sha256": UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "upstream_execution_closure_sha256": UPSTREAM_EXECUTION_CLOSURE_SHA256,
        "upstream_execution_wrapper_sha256": UPSTREAM_EXECUTION_WRAPPER_SHA256,
        "upstream_execution_launcher_sha256": UPSTREAM_EXECUTION_LAUNCHER_SHA256,
        "execution_wrapper_sha256": wrapper_sha256,
        "execution_launcher_sha256": launcher_sha256,
        "physical_request_id": REQUEST_06_ID,
        "authorization_schema": AUTH_SCHEMA,
        "result_schema": RESULT_SCHEMA,
        "marker_schema": MARKER_SCHEMA,
        "corrected_baseline_sha256": CORRECTED_BASELINE_SHA256,
        "corrected_path_neutral_baseline_sha256": CORRECTED_PATH_NEUTRAL_BASELINE_SHA256,
        "invalid_baseline_sha256": INVALID_BASELINE_SHA256,
        "invalid_baseline_reuse_permitted": False,
        "predecessor_03_state": PREDECESSOR_03_STATE,
        "predecessor_03_failure_code": PREDECESSOR_03_FAILURE,
        "predecessor_04_state": PREDECESSOR_04_STATE,
        "predecessor_05_state": REQUEST_05_INVALID_STATE,
        "immutable_payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
        "recovery_payload_tar_sha256": RECOVERY_PAYLOAD_TAR_SHA256,
        "locked_recovery_scope": "TEST_PARTITION_ONLY",
        "recovery_write_flash_permitted": False,
        "whole_chip_recovery_erase_permitted": False,
        **FALSE_BOUNDARY,
    }


def overlay_manifest(*, binding_sha256: str, contract_sha256: str, wrapper_sha256: str,
                     launcher_sha256: str, upstream_sums_sha256: str) -> dict[str, Any]:
    for value, code in ((binding_sha256, "BINDING"), (contract_sha256, "CONTRACT"),
                        (wrapper_sha256, "WRAPPER"), (launcher_sha256, "LAUNCHER"),
                        (upstream_sums_sha256, "UPSTREAM_SUMS")):
        validate_sha256(value, code + "_SHA_INVALID")
    provisional = {
        "schema": OVERLAY_MANIFEST_SCHEMA,
        "policy_version": 1,
        "execution_overlay_role": "BLOCKING_CORRECTED_BASELINE",
        "upstream_execution_package_sha256": UPSTREAM_EXECUTION_PACKAGE_SHA256,
        "corrected_baseline_sha256": CORRECTED_BASELINE_SHA256,
        "physical_request_id": REQUEST_06_ID,
        "files": [
            {"name": OVERLAY_BINDING_FILE, "sha256": binding_sha256},
            {"name": OVERLAY_CONTRACT_FILE, "sha256": contract_sha256},
            {"name": OVERLAY_WRAPPER_FILE, "sha256": wrapper_sha256},
            {"name": OVERLAY_LAUNCHER_FILE, "sha256": launcher_sha256},
            {"name": UPSTREAM_SUMS_FILE, "sha256": upstream_sums_sha256},
        ],
    }
    result = dict(provisional)
    result["execution_overlay_sha256"] = canonical_json_sha256(provisional)
    return result


def canonical_package_digest(root: Path) -> str:
    entries = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_file():
            entries.append({"name": path.name, "sha256": sha256_file(path)})
    return canonical_json_sha256({
        "schema": "gh.h3.n2.stage2d9r-successor-d2-execution-package-set/1",
        "files": entries,
    })


def parse_sums(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        parts = raw.split("  ", 1)
        require(len(parts) == 2 and HEX64.fullmatch(parts[0]) is not None, "SUMS_FORMAT_INVALID")
        name = parts[1]
        pure = PurePosixPath(name)
        require(name not in result and name not in {"", ".", ".."} and not pure.is_absolute() and ".." not in pure.parts, "SUMS_NAME_INVALID")
        result[name] = parts[0]
    return result


def verify_sums(root: Path, sums_name: str = ROOT_SUMS_FILE) -> dict[str, str]:
    sums = parse_sums(root / sums_name)
    for name, expected in sums.items():
        path = root / name
        require(path.is_file() and not path.is_symlink(), "SUMS_MEMBER_INVALID")
        require(sha256_file(path) == expected, "SUMS_MEMBER_SHA256_MISMATCH")
    return sums


def load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeYXЫЩQ\њ›Ь‹њЫЫ‹’”УУ‘XЫЩQ\њ›ЬЉH\И^О‚€Z\ЩHЫЫќXЭ\њ›ЬЉЫЩJHњ›ЫH^В€™\]Z\™J\Ъ[њЭ[ЩJ[YKXЭ
KЫЩJB€™]\›€[YB‚‚™Y€[Y]WЩ^XЭ][Ы—ЫЭ™\›^JXЪШYЩWЬ›ЫЭ€]
HO€XЭЬЭ‹[ћWN‚€™\љYћWЬЭ[\КXЪШYЩWЬ›ЫЭ
B€\Э™X[WЬЭ[\ИH™\љYћWЬЭ[\КXЪШYЩWЬ›ЫЭTХ‘PSWФХSTЧС’SJB€™\]Z\™J“УХФХSTЧС’SH›Э[€\Э™X[WЬЭ[\Л•TХ‘PSWФХSTЧФСS—Ф‘Q‘T‘SђСHЉB€\Э™X[WЩ[ќљY\ИHЮИ›[YHЋ€[YKњЪLЌM€Ћ€\Э™X[WЬЭ[\ЦЫ[YW_H›Ь€[YH[€ЫЬќY
\Э™X[WЬЭ[\КWB€\Э™X[WЩ[ќљY\Л\[™
И›[YHЋ€“УХФХSTЧС’SKњЪLЌM€Ћ€ЪLЌM—Щљ[JXЪШYЩWЬ›ЫЭИTХ‘PSWФХSTЧС’SJ_JB€\Э™X[WЩ[ќљY\ЛњЫЬќ
Щ^O[[X™H][N€][VИ›[YH—JB€™\]Z\™JШ[›ЫљXШ[ЪњЫЫ—ЬЪLЌMЉВ€њШЪ[XHЋ€™ЪљЛ›Њ‹њЭYЩL™\‹\ЭXШЩ\ЬЫЬ‹Y‹Y^XЭ][Ы‹\XЪШYЩK\Щ]МH‹€™љ[\ИЋ€\Э™X[WЩ[ќљY\Л€JHOHTХ‘PSWСVPХUSУ—ФPТРQСWФТLЌM‹•TХ‘PSWСVPХUSУ—ФPТРQСWСQСTХУRTУPUТЉB€љ[™[™ИHШYЪњЫЫЉXЪШYЩWЬ›ЫЭИХ‘T“VWР’S‘S‘ЧС’SK“Х‘T“VWР’S‘S‘ЧТS•ђSQЉB€X[љY™\ЭHШYЪњЫЫЉXЪШYЩWЬ›ЫЭИХ‘T“VWУPS’Q‘TХС’SK“Х‘T“VWУPS’Q‘TХТS•ђSQЉB€ШњЩ\ќ™YЫЭ™\›^WЬЪHHX[љY™\ЭњЬ
™^XЭ][Ы—ЫЭ™\›^WЬЪLЌM€‹›Ы™JB€™\]Z\™JШњЩ\ќ™YЫЭ™\›^WЬЪHOHШ[›ЫљXШ[ЪњЫЫ—ЬЪLЌMЉX[љY™\Э
K“Х‘T“VWУPS’Q‘TХСQСTХУRTУPUТЉB€X[љY™\ЭИ™^XЭ][Ы—ЫЭ™\›^WЬЪLЌM€—HHШњЩ\ќ™YЫЭ™\›^WЬЪB€™\]Z\™Jљ[™[™Л™Щ]
њШЪ[XHЉHOHХ‘T“VWР’S‘S‘ЧФРТSPKХ‘T“VWР’S‘S‘ЧФРТSPWУRTУPUТЉB€™\]Z\™Jљ[™[™Л™Щ]
њ\ЪXШ[Ь™\]Y\ЭЪYЉHOH‘TUQTХМ—ТQ“Х‘T“VWР’S‘S‘ЧФ‘TUQTХТQУRTУPUТЉB€™\]Z\™Jљ[™[™Л™Щ]
ЫЬњ™XЭYШ\Щ[[™WЬЪLЌM€ЉHOHУФ”‘PХQРђTСSS‘WФТLЌM‹“Х‘T“VWР’S‘S‘ЧРђTСSS‘WУRTУPUТЉB€™\]Z\™Jљ[™[™Л™Щ]
љ[ќ[YШ\Щ[[™WЬЪLЌM€ЉHOHS•ђSQРђTСSS‘WФТLЌM‹“Х‘T“VWР’S‘S‘ЧТS•ђSQРђTСSS‘WУRTУPUТЉB€™\]Z\™Jљ[™[™Л™Щ]
њ™YXЩ\ЬЫЬ—МWЬЭ]HЉHOH‘TUQTХМWТS•ђSQФХUK“Х‘T“VWР’S‘S‘ЧФ‘QPСTФУФ—МWУRTУPUТЉB€™\]Z\™JX[љY™\Э™Щ]
™^XЭ][Ы—ЫЭ™\›^WЬ›ЫHЉHOHђ“РТТS‘ЧРУФ”‘PХQРђTСSS‘H‹“Х‘T“VWФ“УWУRTУPUТЉB€™\]Z\™JX[љY™\Э™Щ]
ќ\Э™X[WЩ^XЭ][Ы—ЬXЪШYЩWЬЪLЌM€ЉHOHTХ‘PSWСVPХUSУ—ФPТРQСWФТLЌM‹“Х‘T“VWХTХ‘PSWФPТРQСWУRTУPUТЉB€›Ь€[ќћH[€X[љY™\Э™Щ]
™љ[\И‹ЧJN‚€™\]Z\™J\Ъ[њЭ[ЩJ[ќћKXЭ
K“Х‘T“VWС’SWСS•–WТS•ђSQЉB€[YHH[ќћK™Щ]
›[YHЉB€^XЭYH[ќћK™Щ]
њЪLЌM€ЉB€™\]Z\™J\Ъ[њЭ[ЩJ[YKЭЉH[™\Ъ[њЭ[ЩJ^XЭYЭЉK“Х‘T“VWС’SWСS•–WТS•ђSQЉB€™\]Z\™JЪLЌM—Щљ[JXЪШYЩWЬ›ЫЭИ[YJHOH^XЭY“Х‘T“VWС’SWФТLЌM—УRTУPUТЉB€™]\›€Иљ[™[™ИЋ€љ[™[™Л›X[љY™\ЭЋ€X[љY™\ЭB‚‚