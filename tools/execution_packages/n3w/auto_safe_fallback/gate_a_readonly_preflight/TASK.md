# N3-W auto safe fallback Gate A read-only preflight

Status: `PREPARATION_ONLY`

This package performs the first live gate before any Gate A firmware build or flash.

It reads:

- T1 default-route IPv4/interface/prefix;
- host IPv4 TCP/8883 wildcard listener state;
- Broker/Manager runtime state;
- two same-subnet addresses that do not answer duplicate-address ARP probes;
- Board B ROM identity, flash size, security state and partition-table hash.

It does not:

- add/remove an IP address;
- restart Broker or Manager;
- edit T1 files;
- open the ESP32 application serial console;
- write flash;
- erase flash;
- write product NVS.

The T1 probe emits ARP duplicate-address probes only. Candidate addresses remain unassigned during this gate.

Frozen Board B authority:

```text
BOARD_B_HARDWARE_ID_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
PARTITION_TABLE_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

Frozen rollback authority:

```text
KF099_ARTIFACT_ID=10959875986
KF099_ARTIFACT_NAME=n3w-kf099-c578bcb-boardb-exact-source
KF099_ARTIFACT_ZIP_SHA256=56abb5267ee1786f77930837d6a660745ee64f320d1c6ad64aac7c852aa115cb
KF099_APPLICATION_SHA256=d0875ca692f7bd4349fd7d8bcdab69318e6c8b737b69a48f667b6e72cb89cb60
KF099_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

The private output JSON contains the actual T1/LAN addresses. It must not be committed to the public repository.
