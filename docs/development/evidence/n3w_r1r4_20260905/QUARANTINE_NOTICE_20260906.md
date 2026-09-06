# R1R4 Historical Evidence Quarantine Notice — 2026-09-06

Status: `NON_AUTHORITATIVE_FOR_ROOT_CAUSE`

This notice applies to the historical file in this evidence branch:

`CI_JOB_101283085978_FAILURE_EXCERPT.log`

The excerpt claims to describe GitHub Actions job `101283085978`, Step 8, using a `pio run` command surface and an `esp_app_desc.h` compile failure.

The exact workflow frozen at R1R4 commit `1b89639f9454ea725da1fef32564f5cdfa006289` defines the same Step 8 (`Build CONTROL diagnostic image`) with a different command surface: `idf.py set-target esp32c6`, `idf.py reconfigure`, `idf.py build`, followed by sdkconfig assertions.

Because those command surfaces cannot both be the exact Step 8 runtime body for the same job authority, and the original raw job log body has not been independently rebound with sufficient authority, the historical excerpt is quarantined.

Rules:

- preserve the excerpt as historical material;
- do not use it to claim the original R1R4 root cause;
- do not use it to claim that `pio run` or `esp_app_desc.h` caused job `101283085978`;
- do not use it to authorize source/product repair;
- exact workflow/run/job evidence takes precedence;
- the historical CI forensic route remains closed.

Current progress authority is maintained on `main` by:

`docs/development/N3W_CURRENT_DEVELOPMENT_PROGRESS_ALIGNMENT_20260906.md`
