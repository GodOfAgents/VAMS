# Private VDSO Shadow Worker Runbook

Last verified: 2026-07-14

## Status and boundary

The worker in `neuron/vdso/shadow_worker.py` is a private, read-only
conformance lane. It is not a public Gateway route, validator, deployment, or
authoritative VDSO backend. It permits only commitment-only `READ` transitions
and has no settlement, sidecar, reserve, consume, object-mutation, or external
write interface. Its only durable writes are PostgreSQL checkpoints, replay
state, transition audits, chunk checkpoints, and stop conditions.

This runbook does **not** claim that the required seven-day or
`1 × 10^5`-transition run has occurred. The report command refuses to emit
report material until the durable run satisfies every bound, including a
verified restart/replay.

## Build the three evaluator artifacts

Run these against the exact clean commit that will be measured:

```powershell
cargo build --locked --release --manifest-path vams-vm/Cargo.toml --package vir-conformance --bin shadow_eval
python -m neuron.vdso.shadow_worker prepare-aiken `
  --cardano-project cardano `
  --output docs/audit/evidence/vdso-shadow-aiken-evaluator.cbor
```

The Aiken command invokes `aiken export` for
`vams/vdso.shadow_read_commitment`. During every transition the worker invokes
`aiken uplc eval --cbor` against that exported program. The Aiken module remains
a conformance library; the export does not make it a Cardano validator.

Copy the exact Python and Rust artifacts into the same evidence directory
without changing their bytes:

```powershell
Copy-Item neuron/vdso/shadow_worker.py docs/audit/evidence/vdso-shadow-python-evaluator.py
Copy-Item vams-vm/target/release/shadow_eval.exe docs/audit/evidence/vdso-shadow-rust-evaluator.bin
```

On Linux, copy `vams-vm/target/release/shadow_eval` to the same fixed `.bin`
evidence filename. The worker hashes all three runtime artifacts when the run
starts. The final report verifies byte-identical files beside the report.

## Commitment-only input contract

The baseline mirror appends canonical UTF-8 JSON Lines records to
`vdso-shadow-input.jsonl`. Each line has exactly these fields:

```json
{
  "schema_version": "1.0.0",
  "source_sequence": 0,
  "source_cursor_hash": "<64 lowercase hex characters>",
  "input_commitment": "<64 lowercase hex characters>",
  "previous_source_record_sha256": "<64 lowercase hex characters>",
  "source_record_sha256": "<64 lowercase hex characters>"
}
```

The first `previous_source_record_sha256` is 64 zeroes. For every record:

\[
H_i = \operatorname{SHA256}(\operatorname{CanonicalJSON}(R_i \setminus \{H_i\}))
\]

Canonical JSON means keys sorted lexicographically, compact separators, ASCII
encoding, and no trailing newline in the hash preimage. The on-disk JSONL line
is newline-terminated. `source_sequence` must be a contiguous unsigned 64-bit
integer. Cursor hashes and input commitments must be nonzero 32-byte values.
Every record after genesis binds `previous_source_record_sha256` to the prior
record. Extra keys—including payload, plaintext, prompt, content, data,
message, sidecar, or secret fields—fail closed.

The worker rescans the source chain through the durable checkpoint on every
restart. It rejects truncation, gaps, reordering, duplicates, partial lines,
cursor reuse, record-hash mismatch, and trailing unmeasured records at report
time.

## Run the private lane

Public Gateway instances remain a separate process with `VDSO_MODE=off`. The
private worker requires this exact fail-closed environment:

```powershell
$env:VAMS_ENV = "testnet"
$env:VAMS_NETWORK = "polygon-amoy"
$env:VDSO_MODE = "shadow"
$env:VDSO_PUBLIC_MODE = "off"
$env:VDSO_POSTGRES_DSN = "postgresql://..."

python -m neuron.vdso.shadow_worker run `
  --repo . `
  --input-jsonl docs/audit/evidence/vdso-shadow-input.jsonl `
  --rust-evaluator docs/audit/evidence/vdso-shadow-rust-evaluator.bin `
  --aiken-program docs/audit/evidence/vdso-shadow-aiken-evaluator.cbor `
  --interval-seconds 6 `
  --max-gap-seconds 60
```

Remote PostgreSQL DSNs must use `sslmode=verify-full` and an explicit
`sslrootcert`. Each transition is evaluated by Python, Rust, and Aiken before
one atomic PostgreSQL checkpoint is committed. Any unavailable backend,
divergence, root mismatch, source-chain failure, unsupported action, plaintext
field, or continuity gap permanently records a stop condition.

## Export unsigned evidence

The progress stream prints the deterministic `run_id`. Evidence export is
read-only and writes canonical, record-hash-chained JSONL to stdout:

```powershell
python -m neuron.vdso.shadow_worker export-evidence `
  --run-id <64-hex-run-id> `
  --postgres-dsn $env:VDSO_POSTGRES_DSN |
  Set-Content -Encoding utf8NoBOM docs/audit/evidence/vdso-shadow-audit.jsonl
```

The artifact contains one run header, contiguous 1,000-transition chunk
records, and one summary. Chunk records bind source cursors, source-chain roots,
starting/ending transition roots, separate backend evaluation counts, and
separate Python/Rust/Aiken transcript roots. The summary binds the exact final
source and transition checkpoints.

After the final input and all five evaluator/audit artifacts are together in
the evidence directory, emit unsigned report material to stdout:

```powershell
python -m neuron.vdso.shadow_worker report `
  --repo . `
  --run-id <64-hex-run-id> `
  --postgres-dsn $env:VDSO_POSTGRES_DSN `
  --audit-jsonl docs/audit/evidence/vdso-shadow-audit.jsonl |
  Set-Content -Encoding utf8NoBOM docs/audit/evidence/vdso-shadow-report.json
```

The worker does not sign the report. Signing and immutable evidence-run binding
remain promotion-pipeline responsibilities after independent review.
