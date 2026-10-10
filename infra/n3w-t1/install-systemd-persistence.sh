#!/bin/sh
set -eu

GUARD=n3wfc4-broker-ingress-guard.service
ACTIVATION=n3wfc4-broker-activation.service
CERT_TIMER=n3wfc4-broker-certificate-lifecycle.timer

/usr/bin/systemctl enable "$GUARD" "$ACTIVATION" "$SERVICES" "$CERT_TIMER"

guard_state="$(/usr/bin/systemctl is-enabled "$GUARD")"
activation_state="$(/usr/bin/systemctl is-enabled "$ACTIVATION")"
cert_timer_state="$(/usr/bin/systemctl is-enabled "$CERT_TIMER")"

printf 'GUARD_ENABLED=%s\n' "$guard_state"
printf 'ACTIVATION_ENABLED=%s\n' "$activation_state"
printf 'CERTIFICATE_LIFECYCLE_TIMER_ENABLED=%s\n' "$cert_timer_state"

[ "$guard_state" = "enabled" ]
[ "$activation_state" = "enabled" ]
[ "$cert_timer_state" = "enabled" ]

printf 'SYSTEMD_PERSISTENCE_INSTALL=PASS\n'
