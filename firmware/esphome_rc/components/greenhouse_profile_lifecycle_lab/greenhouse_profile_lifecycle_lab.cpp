#include "greenhouse_profile_lifecycle_lab.h"

#include "esphome/core/log.h"

namespace esphome::greenhouse_profile_lifecycle_lab {
namespace {

static const char *const TAG = "gh_profile_lifecycle_lab";

}  // namespace

void GreenhouseProfileLifecycleLab::setup() {
  ESP_LOGI(TAG,
           "Stage 2D-4 lifecycle integration is compile-only; no storage, MQTT, "
           "or activation adapter is configured");
}

void GreenhouseProfileLifecycleLab::dump_config() {
  ESP_LOGCONFIG(TAG, "Greenhouse Profile Lifecycle Lab:");
  ESP_LOGCONFIG(TAG, "  Phase: %s", this->phase_name());
  ESP_LOGCONFIG(TAG, "  Runtime integration: disabled");
  ESP_LOGCONFIG(TAG, "  Persistent mutation: disabled");
}

float GreenhouseProfileLifecycleLab::get_setup_priority() const {
  return setup_priority::LATE;
}

const char *GreenhouseProfileLifecycleLab::phase_name() const {
  return greenhouse_pairing_client::PairingProfileLifecycleIntegration::phase_name(
      this->integration_.snapshot().phase);
}

bool GreenhouseProfileLifecycleLab::reboot_required() const {
  return this->integration_.snapshot().reboot_required;
}

}  // namespace esphome::greenhouse_profile_lifecycle_lab
