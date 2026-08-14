"""N3-W product-completion runtime support.

S3 provides reusable disconnected ESP-NOW discovery/runtime code without
activating it in the production firmware profile. S4 supplies Manager
membership/authorization integration. S5 makes this C++ layer loadable in an
explicit isolated physical profile while keeping normal product activation
separate.
"""

import esphome.config_validation as cv

DEPENDENCIES = ["esp32"]
AUTO_LOAD = ["greenhouse_n3w_core", "greenhouse_n3w_product_core"]
CONFIG_SCHEMA = cv.Schema({})
