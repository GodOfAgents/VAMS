# Incident VAMS-PEM-2026-001 — current state and closure plan (2026-11-08)

Status: **PLAN ONLY.** Nothing was rewritten, pushed, deleted or sent while
preparing it. It updates `docs/audit/CREDENTIAL_INCIDENT_RUNBOOK.md` with what
has already happened; the runbook's stop conditions still apply. No private
key, PEM body or replacement-map value is reproduced here; identities are
named only by public address and public-key fingerprint prefix.

## 1. What is already done (verified today)

| Runbook step | State | Evidence |
|---|---|---|
| 1. Preparation PR | Done | Merged as PR #6 below `829ab54` |
| 2–8. Rewrite and one force-push | **Done 2026-09-01** | `.tmp-history-tests/post-remote-rewrite-residue-classification.json`: six authoritative branches force-updated; Gitleaks 0 and TruffleHog 0 on all six; `main` = `829ab544…` |
| Local history now | Clean | Canonical clone (98 commits, all refs incl. today's local branches): complete-history Gitleaks 8.30.1 with `--log-opts="--all -m"` → **0 findings**; zero commits touch any runbook target path; pre-rewrite SHA `31929a2` absent. The only PEM header in history is a test assertion that artifacts contain no key (`scripts/remediation/test_f05_2a_proof_other_network_mutant_r1.py:139`) |
| Collaborator reclone | Recorded for the sole collaborator | `.tmp-history-tests/collaborator-reclone-verification.json` (2026-09-01) |
| Credentials | Revoked / permanently decommissioned before the rewrite | Residue record `credential_disposition` |

No further history rewrite is needed for the source repository. Today's local
branches (`remediation/phase1`, `backup/remediation-snapshot-20261108`) are
built on the rewritten `829ab54` and carry none of the removed paths.

## 2. What still blocks closure

### R1 — GitHub-managed pull-request refs (external)

The residue record lists `refs/pull/1/head`, `refs/pull/2/head`,
`refs/pull/3/head` and `refs/pull/6/head` as still advertising old-lineage
commits (861 Gitleaks / 19 TruffleHog findings at the time). A push cannot
change them; GitHub Support must dereference them and garbage-collect. A
request is drafted at `.tmp-history-tests/github-support-pull-ref-cleanup-request.md`.
Whether it was sent, and GitHub's answer, is UNKNOWN.

### R2 — Pre-rewrite copies on this workstation (found today)

| Item | What it holds |
|---|---|
| `VAMS-mono/VAMS-main/` | Pre-rewrite clone; 12 commits touch removed paths; has `31929a2` |
| `VAMS-mono/VAMS-main-baseline/` | Pre-rewrite clone; 7 commits touch removed paths |
| `VAMS-mono/VAMS-main-verification/` | Pre-rewrite clone; 7 commits touch removed paths |
| `VAMS-mono/VAMS-implementation-20260825/` | Pre-rewrite clone; 7 commits touch removed paths |
| `VAMS-mono/VAMS-main.zip` (506 MB) | Pre-rewrite repository with `.git`, 19 removed-path entries, and a plaintext `.data/node_identity.pem` |
| `VAMS-mono/.data/node_identity.pem` and `VAMS-mono/VAMS-main/.data/node_identity.pem` | **Plaintext private key of leaked identity #1** (secp256k1, address `0x72b67e5a2bb6e45b6032d7d195f8b8db9331203b`, public-key SHA-256 `16fb7771…`), identical to the `node_identity.pem` committed in old history. Neuron reads its identity from `.data/`, so running it from these folders would reuse a leaked key |

Leaked identity #2 (`0x03d2172fa5e6f22f8fb7efdb4d9b61ed177ecdf0`,
public-key SHA-256 `45bfe091…`) appears only inside the old clone histories.
Neither address was found in the retained incident records on this machine;
the closure report must bind both.

Per the runbook ("Old clones must never be merged into rewritten history";
"discard old clones"), these copies must be disposed of. The canonical clone,
`VAMS-post-rewrite-prep-20260901` and `VAMS-reclone-20260901` are clean and
stay.

### R3 — Fresh scanner evidence on the exact closure commit

Complete-history Gitleaks passes locally today. All-category TruffleHog
3.95.9 has not been run here: it is not installed and its download is not yet
approved. Both must pass against the exact commit used for closure, in CI.

### R4 — Closure report

`scripts/audit/credential_incident_evidence.py` builds the schema 4.0.1
report. Owner-supplied facts still needed: the real UTC decommission decision
time for each identity; role checks (deployment signer, funded account, node,
provider, Safe, timelock, validator); Polygon Amoy public observations of
both addresses at recorded block heights; Cardano non-applicability; the
Infura revocation dashboard observation; GitHub Support confirmation; reclone
evidence (exists).

## 3. Steps and exact commands

Each step is separate; destructive ones need explicit owner approval at the
time.

**Step A (read-only): check GitHub's current pull refs.**
```bash
git -C ~/code/VAMS-testnet ls-remote https://github.com/GodOfAgents/VAMS.git 'refs/pull/*' 'refs/heads/*'
```
Expected if Support finished: `refs/pull/{1,2,3,6}/head` absent or pointing
at rewritten commits; `refs/heads/main` = `829ab544…`. If old-lineage refs
remain, send or follow up the drafted Support request (owner action).

**Step B (destructive, needs approval): dispose of local pre-rewrite copies.**
Before deleting, confirm nothing unique is needed from them (they are dated
snapshots of the same project). Then, in PowerShell:
```powershell
$root = "C:\Users\aseem\VAMS-mono"
$items = @("VAMS-main", "VAMS-main-baseline", "VAMS-main-verification",
           "VAMS-implementation-20260825", "VAMS-main.zip", ".data\node_identity.pem")
foreach ($i in $items) { Get-Item (Join-Path $root $i) | Select-Object FullName, Length, LastWriteTime }
# After review and approval only:
foreach ($i in $items) { Remove-Item -LiteralPath (Join-Path $root $i) -Recurse -Force }
```
`VAMS-main\.data\node_identity.pem` goes with `VAMS-main`. Normal deletion on
an SSD is not a secure wipe; the identity is already decommissioned, so the
goal is to stop reuse and accidental re-merge. Also empty the Recycle Bin for
these items and check backups/sync folders for copies.

**Step C (needs download approval): install and run TruffleHog 3.95.9.**
Download from the official GitHub release with its checksum file into
`~/.vams-tools`, then:
```bash
cd ~/code/VAMS-testnet
trufflehog git "file://$PWD" --json --fail --no-update --results=verified,unknown,unverified > ~/vams-baseline-logs/secrets/trufflehog.json
gitleaks git . --log-opts="--all -m" --config .gitleaks.toml --redact=100 --report-format json --report-path ~/vams-baseline-logs/secrets/history.json --exit-code 1
```
Expected: zero findings from both.

**Step D (owner facts): build the closure report** with
`scripts/audit/credential_incident_evidence.py` once R1 is confirmed and the
R4 facts are supplied. Keep supporting artifacts sanitized and content-hashed.

**Step E (separate authorization): push today's work and run hosted CI.**
Only after A–C: push `remediation/phase1` (no force needed; it descends from
`829ab54`), re-enable Actions if still disabled
(`.tmp-history-tests/enable_actions_for_exact_ci.ps1` exists), and let the
secret-scanning jobs run on the exact commit.

## 3a. Step B execution record (2026-11-08)

Owner approved Step B. Results:

| Item | Result |
|---|---|
| `VAMS-mono/VAMS-main/` (incl. its `.data/node_identity.pem`) | Deleted |
| `VAMS-mono/VAMS-main.zip` | Deleted |
| `VAMS-mono/.data/node_identity.pem` | Deleted |
| `VAMS-mono/VAMS-main-baseline/`, `VAMS-main-verification/`, `VAMS-implementation-20260825/` | All contents deleted, including each `.git` history. One empty `.pytest_cache` folder remains in each, locked by a Windows ACL the user account cannot read; removing it needs an elevated `takeown`/`icacls`. It holds pytest run state only, no key material |

Follow-up checks:

- No other VAMS clone with pre-rewrite history exists under `Desktop`,
  `Documents`, `Downloads` or the user profile root.
- A public-fingerprint scan of private-key files under `C:\Users\aseem` and
  the WSL home (15 files) found **two further copies of leaked identity #1**
  in `C:\Users\aseem\SanDisk16GB backup\VAMS-mono\` (`.data/node_identity.pem`
  and `VAMS-main/.data/node_identity.pem`). That backup (2026-08-25) also holds
  the pre-rewrite `VAMS-main` clone and `VAMS-main.zip`. It was not in the
  approved list and was left untouched. The physical SanDisk device it
  appears to mirror may hold the same files.
- The other 13 private keys found are disposable test TLS keys (pytest
  temporaries and the local PostgreSQL test CA).

## 4. Smallest owner decisions

1. Step B done except three locked empty cache folders (admin action) and the
   `SanDisk16GB backup` copies plus the physical device (owner decision).
2. Approve the TruffleHog 3.95.9 download for Step C.
3. Confirm whether the GitHub Support request was sent and its outcome (or send it).
4. Supply the R4 closure facts when ready (no secrets).

Readiness is unchanged: 13 findings open, 0 of 36 tracks verified, NOT READY.
