#!/usr/bin/env python3
"""Apply the reviewed Stage 2D-9R source corrections exactly once."""
from __future__ import annotations

from pathlib import Path

SOURCE = Path(
    "firmware/esphome_rc/components/"
    "greenhouse_profile_isolated_device_g3r_executor/"
    "stage2d9r_g3r_prepare_executor_20260723_v1.cpp"
)

OLD_CA = """  const bool valid = parsed == 0 && certificate.raw.len > 0 &&
                     certificate.next == nullptr && certificate.ca_istrue != 0 &&
                     (certificate.key_usage & MBEDTLS_X509_KU_KEY_CERT_SIGN) != 0;"""
NEW_CA = """  const bool valid =
      parsed == 0 && certificate.raw.len > 0 && certificate.next == nullptr &&
      mbedtls_x509_crt_get_ca_istrue(&certificate) == 1 &&
      mbedtls_x509_crt_check_key_usage(
          &certificate, MBEDTLS_X509_KU_KEY_CERT_SIGN) == 0;"""

OLD_ORDER = """  if (!this->authorization_binder_.grant(
          IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE, 0, 1,
          envelope->authorization_digest)) {
    config.clear();
    return this->fail_step_(\"prepare_authorization_grant\");
  }
  if (!this->package_.load_test_configuration(std::move(config))) {
    config.clear();
    this->authorization_binder_.clear();
    return this->fail_step_(\"prepare_config_load\");
  }
"""
NEW_ORDER = """  if (!this->package_.load_test_configuration(std::move(config))) {
    config.clear();
    return this->fail_step_(\"prepare_config_load\");
  }
  if (!this->authorization_binder_.grant(
          IsolatedAcceptanceWriteOperation::PREPARE_CANDIDATE, 0, 1,
          envelope->authorization_digest)) {
    return this->fail_step_(\"prepare_authorization_grant\");
  }
"""

OLD_WIPE = """  this->mqtt_.quiesce();
  this->persistence_.quiesce();
  this->test_key_provider_.destroy();
  secure_clear(&this->input_buffer_);
"""
NEW_WIPE = """  this->mqtt_.quiesce();
  this->persistence_.quiesce();
  this->test_key_provider_.destroy();
  (void) this->package_.configure(
      &this->driver_, &this->test_key_provider_, &this->evidence_sink_);
  (void) this->authorization_binder_.configure(
      &this->package_, &this->driver_);
  secure_clear(&this->input_buffer_);
"""


def apply() -> bool:
    text = SOURCE.read_text(encoding="utf-8")
    if OLD_CA not in text:
        if (
            "mbedtls_x509_crt_get_ca_istrue(&certificate) == 1" in text
            and "certificate.ca_istrue" not in text
            and "certificate.key_usage" not in text
        ):
            return False
        raise RuntimeError("opaque X.509 replacement target missing")

    replacements = (
        (OLD_CA, NEW_CA, "opaque X.509"),
        (OLD_ORDER, NEW_ORDER, "PREPARE phase order"),
        (OLD_WIPE, NEW_WIPE, "sensitive runtime wipe"),
    )
    for old, new, label in replacements:
        if text.count(old) != 1:
            raise RuntimeError(f"{label} replacement target count mismatch")
        text = text.replace(old, new)

    if "certificate.ca_istrue" in text or "certificate.key_usage" in text:
        raise RuntimeError("opaque X.509 fields remain")
    load = text.index("package_.load_test_configuration(std::move(config))")
    grant = text.index("authorization_binder_.grant(", load)
    prepare = text.index("package_.prepare_candidate()", grant)
    if not load < grant < prepare:
        raise RuntimeError("PREPARE phase order remains invalid")
    if text.count("(void) this->package_.configure(") != 1:
        raise RuntimeError("sensitive package wipe binding is not exact")

    SOURCE.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    changed = apply()
    print("STAGE2D9R_SOURCE_PATCH=PASS")
    print(f"SOURCE_CHANGED={str(changed).lower()}")
    print("BOARD_OPERATION=false")
    print("NETWORK_OPERATION=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
