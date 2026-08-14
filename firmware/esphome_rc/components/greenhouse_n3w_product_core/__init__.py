"""Host/firmware support for the N3-W product orchestration core.

The module is intentionally configuration-free. Loading it only makes the
C++ product core available to another explicitly selected component; it does
not initialize Wi-Fi, ESP-NOW, credentials, peers, or a product path.
"""

import esphome.config_validation as cv

DEPENDENCIES = ["esp32"]
CONFIG_SCHEMA = cv.Schema({})
