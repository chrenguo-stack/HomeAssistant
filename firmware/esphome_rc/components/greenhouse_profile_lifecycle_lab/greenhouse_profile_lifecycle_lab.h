#pragma once

#include "esphome/core/component.h"
#include "esphome/components/greenhouse_pairing_client/pairing_profile_lifecycle_integration.h"

namespace esphome::greenhouse_profile_lifecycle_lab {

class GreenhouseProfileLifecycleLab final : public Component {
 public:
  void setup() override;
  void dump_config() override;
  float get_setup_priority() const override;

  const char *phase_name() const;
  bool reboot_required() const;

 protected:
  greenhouse_pairing_client::PairingProfileLifecycleIntegration integration_{};
};

}  // namespace esphome::greenhouse_profile_lifecycle_lab
