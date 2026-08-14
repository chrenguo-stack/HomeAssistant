"""N3-W product-completion runtime support.

S3 intentionally provides reusable disconnected ESP-NOW discovery/runtime code
without activating it in a production firmware profile. S4 supplies Manager
membership/authorization integration and a later physical stage wires the
runtime into the accepted product profile.
"""

DEPENDENCIES = ["esp32"]
