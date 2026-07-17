# Credential Incident Closure Runbook

This runbook covers incident `VAMS-PEM-2026-001`. It prepares the repository
for a coordinated history rewrite without treating preparation as closure.

## Non-Negotiable Stop Conditions

- Never send a private key, PEM body, seed phrase, API token, DSN password, or
  provider credential through chat, Git, issue trackers, or CI artifacts.
- Rotate or revoke credentials before rewriting history.
- Use an encrypted disposable mirror, not a working checkout.
- Do not force-push until the exact rewritten ref set has been independently
  reviewed and the repository owner approves that specific push.
- Do not allow collaborators to merge or push branches from old clones.
- Do not create `credential-incident-report.json` until every referenced
  artifact exists and its SHA-256 is known.

## 1. Provider Credential Evidence

Revoke or rotate the legacy Infura/provider credential in the provider
dashboard. Do not copy the credential value. Produce a sanitized JSON or PDF
record containing only:

- a non-sensitive provider/project identifier or SHA-256 fingerprint;
- the UTC revocation and replacement timestamps;
- the access-log and billing-review interval;
- whether unauthorized use, billing, or configuration changes were found;
- the affected public application/node identifiers, if any;
- the Architect reviewer name, organization, `review_mode=architect-owner`,
  `independent_review=false`, UTC review time, and disposition.

The newest CI result showing zero verified TruffleHog findings is supporting
evidence only. It does not replace the dashboard record.

An RPC response such as `invalid project id` is also supporting endpoint
behavior only. It cannot prove the owning account, revocation actor, revocation
timestamp, replacement status, access-log review, billing review, or impact.
Do not derive `revoked_at` from a CI timestamp, commit timestamp, failed probe,
or file creation time. A SHA-256 of the exposed identifier is a safe reference
but is not independent revocation evidence.

## 2. PEM Identity Rotation and Impact Review

The live all-ref inventory contains three historical finding occurrences but
only two unique key identities: two occurrences at `node_identity.pem` resolve
to the same public key, while the `neuron/node_identity.pem` occurrence resolves
to the other key. Record occurrence provenance separately from identity-level
rotation and impact evidence. For each unique identity:

1. Derive the SHA-256 fingerprint from the public key or certificate
   representation. Never hash or publish the raw private PEM body as evidence.
2. Record the public key type and any public account/node identifiers.
3. Revoke or decommission the old identity and create a replacement using the
   approved key-management system.
4. Record the replacement public fingerprint and UTC timestamps.
5. Prove the old identity controls none of these seven classes:
   `deployment_signer`, `funded_account`, `node`, `provider`, `safe`,
   `timelock`, and `validator`.
6. For Polygon Amoy and Cardano Pre-Prod, record either:
   - a real public account identifier, block/slot observation, and zero balance;
     or
   - public cryptographic proof that the key type cannot derive a valid account
     for that network. Do not invent an address.

Store only sanitized, non-secret evidence in the protected evidence intake.

## 3. Freeze Repository Writes

Before cloning the rewrite mirror:

- announce a maintenance window;
- pause merges and repository writes;
- inventory open PRs, branches, tags, forks, and active collaborators;
- export sanitized PR/ref metadata;
- confirm credential rotations are complete;
- obtain a written maintenance approval naming the repository and incident ID.

## 4. Install the Rewrite Dependency

Install `git-filter-repo` 2.47.0 or newer in an isolated operator environment.
Example PowerShell commands:

```powershell
py -m pip install --user "git-filter-repo>=2.47.0"
py -m pip show git-filter-repo
git filter-repo -h
```

If `py` is unavailable, install a supported Python runtime or use an approved
isolated environment. Do not lower the minimum version.

## 5. Create an Encrypted Disposable Mirror

Use a BitLocker-protected or equivalently encrypted volume. The directory must
not be inside the VAMS working checkout.

```powershell
$incidentRoot = "D:\VAMS-incident-VAMS-PEM-2026-001"
$mirror = Join-Path $incidentRoot "VAMS-cleanup.git"
$evidence = Join-Path $incidentRoot "sanitized-evidence"

New-Item -ItemType Directory -Path $incidentRoot -Force
git clone --mirror https://github.com/GodOfAgents/VAMS.git $mirror
New-Item -ItemType Directory -Path $evidence -Force
```

Immediately confirm that `remote.origin.mirror=true` and the fetch refspec is
`+refs/*:refs/*`:

```powershell
git -C $mirror config --bool remote.origin.mirror
git -C $mirror config --get remote.origin.fetch
git -C $mirror show-ref
```

## 6. Run the Non-Destructive Inventory

From the source checkout, use Git Bash explicitly on Windows:

```powershell
& "C:\Program Files\Git\bin\bash.exe" scripts/audit/history_rewrite.sh `
  --mirror "D:/VAMS-incident-VAMS-PEM-2026-001/VAMS-cleanup.git" `
  --evidence-dir "D:/VAMS-incident-VAMS-PEM-2026-001/sanitized-evidence"
```

This inventories all mirror refs and affected-path commit counts. It does not
rewrite or push anything. Review `pre-refs.tsv`, `pre-target-paths.tsv`,
`rewrite-metadata.txt`, and `evidence-sha256.txt`.

## 7. Execute Only After Rotation and Approval

Prepare two non-secret files outside Git:

- `rotation-evidence.json`: sanitized provider/PEM rotation summary;
- `maintenance-approval.txt`: repository-owner approval for this incident and
  maintenance window.

Then run:

```powershell
& "C:\Program Files\Git\bin\bash.exe" scripts/audit/history_rewrite.sh `
  --mirror "D:/VAMS-incident-VAMS-PEM-2026-001/VAMS-cleanup.git" `
  --evidence-dir "D:/VAMS-incident-VAMS-PEM-2026-001/sanitized-evidence" `
  --execute `
  --confirm-incident VAMS-PEM-2026-001 `
  --rotation-evidence "D:/VAMS-incident-VAMS-PEM-2026-001/rotation-evidence.json" `
  --maintenance-approval "D:/VAMS-incident-VAMS-PEM-2026-001/maintenance-approval.txt"
```

The script refuses non-mirror clones, mirrors inside the source checkout,
incomplete refspecs, wrong origins, missing approvals, and old
`git-filter-repo` versions. It never pushes.

## 8. Independently Review Before Force-Push

Review at least:

- every pre/post ref and the ref diff;
- `filter-repo-changed-refs.txt`;
- zero remaining commits for every targeted path;
- the original origin URL;
- the evidence hash manifest;
- open PR/fork handling and rollback communications.

Only after explicit transaction-specific approval for the exact ref set,
restore the public origin if `git-filter-repo` removed it and push the mirror:

```powershell
git -C $mirror remote add origin https://github.com/GodOfAgents/VAMS.git
git -C $mirror push --force --mirror origin
```

Do not run those commands until approval is given immediately before the push.

## 9. Complete Remote and Collaborator Cleanup

- restore branch protections immediately;
- recreate affected PRs from rewritten branches;
- ask GitHub Support to clear cached sensitive views and unreachable PR refs;
- coordinate every fork owner;
- require every collaborator to discard the old clone and clone again;
- prohibit hard-reset reuse of old clones because it can reintroduce the old
  objects or merge bases;
- destroy the encrypted disposable mirror after independent acceptance.

## 10. Run Clean Full-History Scans

Run the repository-pinned CI workflow against the frozen post-rewrite SHA. The
effective commands must remain equivalent to:

```text
gitleaks git . --redact=100 --report-format json \
  --report-path raw-gate/gitleaks-report.json --log-opts=--all --exit-code 1

trufflehog git "file://$PWD" --json --fail --no-update \
  --results=verified,unknown,unverified
```

Acceptance requires zero Gitleaks findings and zero TruffleHog findings. A
verified-only scan is insufficient.

## 11. Build the Closure Report

Freeze the post-rewrite release SHA. Place the final report and every referenced
artifact under the protected operational-evidence intake for that SHA. The
report must:

- use schema version `3.0.0` and the real 40-character target SHA;
- bind exactly three historical path/commit occurrences to exactly two real
  unique public-key fingerprints;
- bind all role, funding, revocation, rewrite, Support, and scanner artifacts;
- use actual SHA-256 values computed from non-empty files;
- name the Architect reviewer and organization without claiming independence;
- report zero open blockers.

Validate it through `credential_incident_evidence.py` and the canary readiness
command. Never use patterned placeholder hashes, invented timestamps, or
`*-FILL` identities.
