# H3/N2 Stage2D-9R G3R D2-11 paced-transport execution binding

Decision:
`D1-H3N2-STAGE2D9R-G3R-D2-11-PREPARE-TRANSPORT-PACING-SUCCESSOR-EXECUTION-BINDING-20260729-01`.

## Scope

This successor is stacked on Draft PR #207 at exact HEAD
`8be62eb76626a5f65f3635a02fe4ec06b0ca80c2`. It composes:

- the unchanged watchdog-repaired firmware payload and host runtime previously
  reviewed by PR #205;
- the post-claim terminalization guard from PR #206;
- the 64-byte, 100 ms paced USB Serial/JTAG transport from PR #207;
- a durable, redacted PREPARE/VERIFY delivery record for both successful and
  failed command delivery.

The review creates request draft D2-11 and a closure-bound execution package,
but it creates no authorization. The package cannot pass its authorization
contract without a later, separately approved, exact, current, one-shot record.

## Direct predecessor

D2-10 is permanently:

```text
status=CONSUMED_FAILED
terminalization_state=FORENSIC_TERMINAL_CLOSED
primary_failure_code=PREPARE_RESULT_TIMEOUT
secondary_failure_code=KeyError
prepare_count=1
verify_count=0
locked_recovery_attempted=true
locked_recovery_outcome=UNKNOWN
replay_permitted=false
automatic_retry_permitted=false
```

Its canonical terminal result is
`715079d46d8f6f02b396b519d97fb2dd77322d8f293ba3749d8337e835d7fda6`
and its canonical terminal marker is
`2bd46c499c9cbf1462c834cc8374990789aaa0f654e373ffde40304c8d818295`.
`UNKNOWN` must not be converted to recovery success or failure.

D2-10 request, authorization, package, closure and execution identity are
non-reusable. Only the independently verified unchanged firmware payload bytes
may be included in the new D2-11 closure.

## Runtime installation order

1. Bind D2-11 schemas, request and authorization validator.
2. Install paced writes on the exact realtime capture session class.
3. Install the realtime panic/reset evidence controller.
4. Install the delivery-evidence adapter.
5. Instantiate and install the terminalization guard last.

The terminalization controller captures wrapped methods in its constructor, so
constructing it earlier is a contract failure. The result timeout starts only
after paced delivery returns and is not extended.

## Delivery contract

- PREPARE and VERIFY retain their exact original bytes and single newline.
- Each write is at most 64 bytes.
- Each successful chunk is flushed.
- Inter-chunk delay is at least 100 ms.
- A short write or write/flush failure stops immediately; no chunk or command
  retry is allowed.
- Public evidence contains only schema, phase, command SHA-256 and size, chunk
  counts, written byte counts, flush count, status and failure code.
- Raw commands, CA material, secrets and private paths are never persisted.

## Authorization and live gates

The source, packager, contract-check and review workflow are inert. They do not
enumerate USB, open serial, invoke esptool, modify Flash/NVS, start a Broker,
send PREPARE/VERIFY or run recovery.

A later gate must create a new D2-11 authorization bound to the final request,
closure, package, wrapper, launcher, contract, pacing module, terminalization
module, private inputs and board identity. Authorization validity is at most
7200 seconds, one shot, non-replayable, and permits at most one PREPARE, one
VERIFY and one locked recovery.
