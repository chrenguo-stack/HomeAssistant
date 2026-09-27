#!/bin/sh
set -eu

GUARD=n3wfc4-broker-ingress-guard.service
ACTIVATION=n3wfc4-broker-activation.service

/usr/bin/systemctl enable "$GUARD" "$ACTIVATION"

guard_state="$(/usr/bin/systemctl is-enabled "$GUARD")"
activation_state="$(/usr/bin/systemctl is-enabled "$ACTIVATION")"

printf 'GUARD_ENABLED=%s\n' "$guard_state"
printf 'ACTIVATION_ENABLED=%s\n' "$activation_state"

[ "$guard_state" = "enabled" ]
[ "$activation_state" = "enabled" ]

printf 'SYSTEMD_PERSISTENCE_INSTALL=PASS\n'
