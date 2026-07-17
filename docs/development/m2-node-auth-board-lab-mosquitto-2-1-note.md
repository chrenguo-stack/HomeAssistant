# M2 native board-lab Mosquitto 2.1 compatibility note

The verified local macOS preflight found that `mosquitto` and `mosquitto_passwd` were not installed. The current Homebrew Mosquitto package is in the 2.1 release family, while the first native board-lab implementation admitted only 2.0.x.

This follow-up keeps the native laboratory fail-closed and explicitly admits only the tested contract families:

- Mosquitto 2.0.x;
- Mosquitto 2.1.x.

Versions outside these two families remain rejected until separately reviewed and tested.

This change does not install software on the operator Mac, start a Homebrew service, contact the T1, generate production credentials, flash a board, or change anonymous MQTT state.
