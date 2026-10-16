# N3-W T1 F4 Reboot Successor — Source Preparation

Date: 2026-10-16

RESULT=CLOSED_PASS_SOURCE_PREPARATION_WITH_BLOCKER

The PRE_REBOOT_READY postexecution read-only closure passed. The real T1 remains transaction stage PERSISTENCE_ENABLED with pre_reboot_ready=true, Broker/Services persistence enabled, certificate timer enabled but inactive, first certificate audit passed, and no board access.

The reboot persistence boundary remains a separate explicit live subgate. The required post-reboot acceptance is:

- provisioning resume performs verify/resume-only against the already completed DEVICE_READY state;
- FACTORY_ACCEPTED remains exact;
- ingress guard precedes Broker publication;
- Broker, Manager and Home Assistant return automatically;
- certificate timer policy is correct after boot;
- identities and credentials remain unchanged;
- Home Assistant MQTT integration is not duplicated;
- Manager business state remains fresh;
- no board pairing occurs.

Current source review found one execution-authority blocker before a live reboot may be authorized:

`tools/n3w_t1_f4_activation_host.py` has no reboot command and no durable reboot authorization claim/consumption fields. Its command surface ends at `enable-certificate-timer`. Therefore a raw `systemctl reboot` issued from an ad-hoc shell would mutate host availability without a repository-owned durable one-shot reboot authorization claim. That would violate the F4 authorization model already used for activation, runtime acceptance, persistence, certificate audit and timer enablement.

The source also confirms the intended boot chain:

- `n3wfc4-provision-resume.service` runs after Docker and before Broker/Services activation;
- Broker activation requires Docker and ingress guard, and runs F4 broker eligibility before publication;
- Services activation requires Broker activation and authenticated Broker readiness;
- certificate timer is persistent, targets the lifecycle service, and is enabled via `timers.target`;
- certificate lifecycle service itself checks F4 certificate eligibility before auto-renew.

Required source repair before live reboot:

1. add a bounded reboot authorization command owned by the F4 activation host;
2. require exact PRE_REBOOT_READY contract before claim;
3. validate the new authorization ID is distinct from all prior IDs;
4. durably claim and consume the reboot authorization before invoking reboot;
5. record a reboot-pending state/binding sufficient for read-only recovery after SSH disconnect;
6. do not perform board access or any unrelated mutation;
7. provide a post-reboot read-only verifier that proves the persisted recovery contract and closes the reboot transaction without replaying the authorization;
8. preserve existing fail-closed behavior and public-safe evidence rules.

Until that source repair is reviewed, tested, built, and installed as an exact successor artifact:

LIVE_REBOOT_AUTHORIZATION_READY=false
RAW_SYSTEMCTL_REBOOT_FORBIDDEN=true
CURRENT_T1_MUTATION_REQUIRED=false
BOARD_ACCESS=false

NEXT_ONE_GATE=N3W_T1_F4_REBOOT_SUCCESSOR_SOURCE_REPAIR_20261016_01
AUTO_EXECUTE_NEXT_GATE=true
