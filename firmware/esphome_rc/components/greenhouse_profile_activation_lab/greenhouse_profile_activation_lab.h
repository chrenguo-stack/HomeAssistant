#pragma once

#include "esphome/core/component.h"
#include "esphome/components/greenhouse_pairing_client/pairing_profile_activation_coordinator.h"

namespace esphome::greenhouse_profile_activation_lab {

using greenhouse_pairing_client::ProfileActivationCoordinator;

class GreenhouseProfileActivationLab final : public Component {
 public:
  void setup() override;
  void dump_config() override;
  float get_setup_priority() const override;

  const char *phase_name() const;
  bool reboot_required() const;

 protected:
  // Compile-only assembly. No runtime or persistence adapter is present, so the
  // activation transaction cannot be armed or executed from this component.
  ProfileActivationCoordinator coordinator_{};
};

}  // namespace esphome::greenhouse_profile_activation_lab
