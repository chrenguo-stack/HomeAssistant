# D2-17 G11 read-only preclaim forensic re-export R2 contract

The first read-only forensic package was started, but its terminal window was closed before the single-line JSON could be retained. The first package is retired and must not be replayed or reused.

The operator explicitly requested regeneration. Decision `D1-H3N2-STAGE2D9R-G3R-D2-17-G11-READ-ONLY-PRECLAIM-FORENSIC-REEXPORT-R2-20260731-01` authorizes creation and one execution of a new R2 package. R2 performs the same read-only inspection of the immutable G11 Target Mac runtime and additionally writes the exact public-safe JSON line to a package-local result file so loss of terminal scrollback does not lose the evidence again.

R2 does not connect to or query a board, enumerate USB or serial devices, invoke esptool, read or write NVS/Flash, access the network, start a Broker, execute PREPARE/VERIFY/recovery, or mutate the G11 runtime. The only authorized write is the package-local public-safe result JSON.

Bindings:

- lost-output disposition: `6570684c6470e9614f241b61946e41a21c341d209edef0d7a9fd5dda7cec2060`;
- R2 authorization: `66d316f7736cf8466144421a8721606b4adcda4bbdb57c9da2572f762d4e07d9`;
- G11 terminal disposition: `101f96fc0c09f71ccf022e931fcaf07b0e962b09fdd8b76f86008e75e28c4bb9`;
- forensic pending lineage: `307112236b4bb5d668e7be3d9ef41d3fb904cd5b04a362c4de4831c7730078b4`;
- G11 physical terminal: `a413862a6bd769d20687a5f4d5b2ebd16a855486c270d22d5a1eeb15d174ddc3`.

Ready, merge, release, tag and deployment remain forbidden.
