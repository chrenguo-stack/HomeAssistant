#include "greenhouse_profile_activation_lab.h"

#include "esphome/core/log.h"

namespace esphome::greenhouse_profile_activation_lab {
namespace {
constexpr const char *TAG = "gh_profile_activation_lab";
}

void GreenhouseProfileActivationLab::setup() {
  // There is intentionally no active profile mutation, MQTT client control, or
  // persistence adapter in Stage 2D-3's compile-only laboratory assembly.
  this->coordinator_.configure(0);
}

void GreenhouseProfileActivationLab::dump_config() {
  ESP_LOGCONFIG(TAG, "Greenhouse Profile Activation Lab");
  ESP_LOGCONFIG(TAG, "  Phase: %s", this->phase_name());
  ESP_LOGCONFIG(TAG, "  Runtime adapter: absent");
  ESP_LOGCONFIG(TAG, "  Persistence adapter: absent");
  ESP_LOGCONFIG(TAG, "  Startup mutation: disabled");
}

float GreenhouseProfileActivationLab::get_setup_priority() const {
  return setup_priority::LATE;
}

const char *GreenhouseProfileActivationLab::phase_name() const {
  return ProfileActivationCoordinator::phase_name(
      this->coordinator_.snapshot().phase);
}

bool GreenhouseProfileActivationLab::reboot_required() const {
  return this->coordinator_.snapshot().reboot_required;
}

}  // namespace esphome::greenhouse_profile_activation_lab
