import esphome.config_validation as cv

DEPENDENCIES = ["greenhouse_n3w_core"]

# Phase 5-B quarantine component. It is opt-in only for frozen legacy regression
# targets; active product configs must not load it.
CONFIG_SCHEMA = cv.Schema({})
