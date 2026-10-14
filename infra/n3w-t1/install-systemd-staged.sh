#!/bin/sh
set -eu

GUARD=n3wfc4-broker-ingress-guard.service
PROVISION=n3wfc4-provision-resume.service
ACTIVATION=n3wfc4-broker-activation.service
SERVICES=n3wfc4-services-activation.service
CERT_TIMER=n3wfc4-broker-certificate-lifecycle.timer

/usr/bin/systemctl enable "$GUARD" "$PROVISION"

guard_state="$(/usr/bin/systemctl is-enabled "$GUARD")"
provision_state="$(/usr/bin/systemctl is-enabled "$PROVISION")"
activation_state="$(/usr/bin/systemctl is-enabled "$ACTIVATION" 2>/dev/null || true)"
services_state="$(/usr/bin/systemctl is-enabled "$SERVICES" 2>/dev/null || true)"
cert_timer_state="$(/usr/bin/systemctl is-enabled "$CERT_TIMER" 2>/dev/null || true)"

printf 'GUARD_ENABLED=%s\n' "$guard_state"
printf 'PROVISION_RESUME_ENABLED=%s\n' "$provision_state"
printf 'ACTIVATION_ENABLED=%s\n' "$activation_state"
printf 'SERVICES_ACTIVATION_ENABLED=%s\n' "$services_state"
printf 'CERTIFICATE_LIFECYCLE_TIMER_ENABLED=%s\n' "$cert_timer_state"

[ "$guard_state" = "enabled" ]
[ "$provision_state" = "enabled" ]
[ "$activation_state" != "enabled" ]
[ "$services_state" != "enabled" ]
[ "$cert_timer_state" != "enabled" ]

printf 'FRESH_STAGED_SYSTEMD_INSTALL=PASS\n'
