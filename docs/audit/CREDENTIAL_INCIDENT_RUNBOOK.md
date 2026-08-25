# Credential Incident Closure Runbook

This runbook governs incident `VAMS-PEM-2026-001`. Preparation, local
rewriting, remote mutation, and closure are separate approval boundaries.
Preparation does not close the incident.

## Stop Conditions

- Never place a private key, PEM body, seed phrase, API token, provider
  credential, DSN password, or replacement-map value in Git, chat, CI logs,
  issue trackers, or public evidence.
- Rotate or permanently decommission affected identities before rewriting.
- Use a disposable mirror on an encrypted external volume with at least 2 GB
  free. Do not use the source checkout or an encryption-unverified system drive.
- The repository script cannot push. Stop after local verification and obtain
  explicit approval for the exact rewritten ref set before the one remote
  force-push.
- Old clones must never be merged into rewritten history.
- Scanner cleanup does not promote a readiness track or authorize deployment.

## 1. Land the Preparation PR

Create `GodOfAgents/credential-history-prep` from current `main`. The PR
must:

- remove tracked `.foundry/`;
- refactor credential-shaped example URIs;
- add only the rule-targeted `.gitleaks.toml` adjudications;
- add replacement-map, path, and evidence-leak prevention;
- add schema v4 and the local rewrite test harness;
- keep complete-history Gitleaks and all-category TruffleHog fail-closed.

All non-history jobs must pass. The two secret jobs are expected to fail until
the all-ref rewrite. The Architect must record this incident-only exception in
the PR; it is not a scanner waiver or a deployment exception.

## 2. Record Truthful Credential Impact

### PEM identities

The history contains three PEM occurrences representing two unique secp256k1
identities. Derive fingerprints from the public keys, never from private PEM
bytes. For each identity, record:

- the public-key SHA-256 fingerprint and public EVM identifier;
- `decommission_disposition=permanently-decommissioned-no-replacement`;
- the real UTC decommission decision time;
- clear checks for deployment signer, funded account, node, provider, Safe,
  timelock, and validator roles;
- Polygon Amoy public observations at recorded block heights;
- Cardano Pre-Prod cryptographic non-applicability without inventing an address;
- a content-hashed sanitized evidence artifact.

No replacement fingerprint exists because neither identity had a role, funds,
or dependency.

### Infura credential

Record only a non-sensitive project identifier or fingerprint. The evidence
must state:

- `revocation_status=revoked`;
- `exact_revocation_time_unavailable=true`;
- the credential was revoked before the recorded dashboard observation;
- the real dashboard observation timestamp;
- clear access and billing review results;
- `review_mode=architect-owner` and `independent_review=false`.

A failed endpoint probe such as `invalid project id` cannot prove owning
account status, revocation action, or impact. A commit timestamp, file
timestamp, endpoint response, or CI timestamp cannot establish the exact
revocation time.

## 3. Provision the Encrypted Rewrite Root

The Architect supplies an encrypted external path as `VAMS_REWRITE_ROOT`.
On Windows:

```powershell
$env:VAMS_REWRITE_ROOT = "X:\VAMS-incident-VAMS-PEM-2026-001"
Get-BitLockerVolume -MountPoint X:
Get-PSDrive -Name X
```

Acceptance:

- `ProtectionStatus` is `On` (or equivalent full-volume encryption is
  independently verified);
- at least 2 GB is free;
- the path is outside every VAMS clone;
- access is limited to the Architect operator account.

Install under that root, not into the repository:

- `git-filter-repo==2.47.0`;
- Gitleaks `8.30.1`;
- TruffleHog `3.95.9`.

Download the scanner checksum files from their official release pages and
verify the exact archives before extraction.

## 4. Freeze and Inventory GitHub

Immediately before the mirror clone:

1. freeze writes and announce the maintenance window;
2. export sanitized PR 1-4 metadata, descriptions, comments, and review state;
3. close draft PR 4;
4. record and delete the two approved stale branches;
5. recheck forks, tags, LFS objects, rulesets, and protected branches;
6. record every branch/ref SHA and the maintenance approval.

Do not rely on earlier observations; GitHub state must be checked again at
execution time.

## 5. Create the Disposable Mirror and Replacement Map

```powershell
$mirror = Join-Path $env:VAMS_REWRITE_ROOT "VAMS-cleanup.git"
$evidence = Join-Path $env:VAMS_REWRITE_ROOT "evidence"
git clone --mirror https://github.com/GodOfAgents/VAMS.git $mirror
```

Create `replacements.txt` under `VAMS_REWRITE_ROOT` with a restricted ACL.
It may contain only exact `literal:...==>...` replacements for the historical
credential-shaped URI examples. Never print, copy, attach, or commit it.

Run inventory from the source checkout:

```powershell
& "C:\Program Files\Git\bin\bash.exe" scripts/audit/history_rewrite.sh `
  --mirror $mirror `
  --evidence-dir $evidence
```

Review `pre-refs.tsv`, `pre-target-paths.tsv`, `rewrite-metadata.txt`, and
`evidence-sha256.txt`.

## 6. Execute the Local Rewrite

The target set is:

- `.foundry/`;
- `node_identity.pem` and `neuron/node_identity.pem`;
- five legacy provider helper scripts;
- `contracts/test_output_cmd.json` and `contracts/clean_output.json`;
- `neuron/eth_client/sequence_wallet.py`;
- `telegram-bot/bot.js`.

With sanitized impact and maintenance records already present outside Git:

```powershell
& "C:\Program Files\Git\bin\bash.exe" scripts/audit/history_rewrite.sh `
  --mirror $mirror `
  --evidence-dir $evidence `
  --execute `
  --confirm-incident VAMS-PEM-2026-001 `
  --rotation-evidence (Join-Path $env:VAMS_REWRITE_ROOT "credential-impact.json") `
  --maintenance-approval (Join-Path $env:VAMS_REWRITE_ROOT "maintenance-approval.json") `
  --replace-text (Join-Path $env:VAMS_REWRITE_ROOT "replacements.txt")
```

The script hashes but never prints or copies the replacement map. It rejects a
working clone, wrong origin, incomplete mirror refspec, in-repository evidence,
in-mirror evidence, missing approvals, missing replacement map, non-literal
replacement directives, and `git-filter-repo` below 2.47.0. It never pushes.

## 7. Verify Before Remote Mutation

Do all of the following locally:

- confirm every targeted path has zero commits across all refs;
- inspect the complete pre/post ref diff and changed-commit map;
- require `git fsck --full` to pass;
- review the LFS inventory;
- compare rewritten branch tips and protected executable/configuration trees;
- run complete-history Gitleaks with `--log-opts=--all`;
- run TruffleHog with
  `--results=verified,unknown,unverified`;
- require zero findings from both;
- confirm no replacement-map source literal appears in evidence or logs;
- rehearse mirror-push behavior against a local bare remote only.

Present the rewritten SHAs, first changed commits, ref diff, scanner report
hashes, and LFS result. Stop for explicit approval.

## 8. Execute the Approved Remote Rewrite Once

Only after approval for the exact reviewed ref set:

```powershell
git -C $mirror remote add origin https://github.com/GodOfAgents/VAMS.git
git -C $mirror push --force --mirror origin
```

GitHub-managed `refs/pull/*` may reject updates. Verify rewritten `main` and
the Phase 6 branch independently after the push.

## 9. Finish GitHub and Collaborator Cleanup

Open a GitHub Support request for `GodOfAgents/VAMS` naming affected PRs 1-4,
the first changed commits, and any orphaned LFS objects. Request dereferencing
of affected PR refs, cached-view removal, and server-side garbage collection.

The Architect and all three team signers must discard old clones and clone
again. Recreate PR 4 from the rewritten Phase 6 branch. Destroy the disposable
mirror and replacement map through encrypted-volume key disposal only after
GitHub Support confirms cleanup.

## 10. Build Closure Evidence

Freeze post-rewrite SHA A and run:

```text
gitleaks git . --redact=100 --report-format json \
  --report-path raw-gate/gitleaks-report.json \
  --log-opts=--all --exit-code 1

trufflehog git "file://$PWD" --json --fail --no-update \
  --results=verified,unknown,unverified
```

The protected closure report uses schema `4.0.0`, binds exactly three
occurrences to two permanently decommissioned identities, records the bounded
Infura revocation limitation, binds GitHub Support and collaborator-reclone
evidence, and reports `blocking_findings_open=0`.

Destroying local data or obtaining zero scanner findings alone is insufficient.
Closure requires the schema-valid, content-hashed report and protected CI
artifacts against the exact post-rewrite commit.
