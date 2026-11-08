# Current-tree scan and public evidence metadata

Status: current-tree gate FAILS; review preparation only. No readiness promotion.

Current-tree scan follow-up, 2026-10-31 (checkpoint22): the unchanged pinned
Gitleaks8.30.1 narrow-allowlist regression passes. The unchanged M0.4 current-tree
gate exits1 for first-party matches. A separate metadata-only diagnostic scans
all6,690 manifest files:640 first-party matches across70paths (636 in retained
remediation documents,4 in3remediation helpers), all generic-api-key. Its479 vendor
identities exactly match the existing baseline (161/160/158). This diagnostic is
not an adjudication or a substitute for the failing gate. Current public file
digests explain59 matches by exact source-hash equality;581 remain unresolved by
the initial shape analysis. All640 initial records remain UNREVIEWED.

The newest decoder campaign field is a verified public report digest. Represent
it explicitly as focused_scan_evidence {artifact,algorithm,digest}, preserving its
value and all other campaign fields. The unchanged scanner reproduces1 match on
the original and0 on the proposed record. Preserve both originals and exact run
identities; this one correction does not accept the other639 initial matches or
complete T06. Historical evidence and its hashes stay intact. No allowlist, vendor,
workflow or official finding/track disposition changes. No private value, match,
snippet, entropy or scanner fingerprint is retained in the diagnostic packet.

Full-history Gitleaks, all-category TruffleHog, credential-impact/rotation/history
coordination, independent disposition and the other frozen gates remain required.
No history rewrite, provider request, external service, dependency acquisition,
Aiken/Slot08/R28, signing, role/fund operation or deployment occurred. Product
source/855Solidity/7Python results keep their prior source identity; these metadata
checks do not repeat or enlarge them. F16 remains open; all18 finding records,
13open findings/0of36verified tracks and all INV-1--INV-10 controls are unchanged.
The full A--G program still requires BOTH PolygonAmoy and CardanoPre-Prod.

The canonical source before this follow-up is the6,690-file checkpoint21 manifest.
The report is tied to HEAD829ab544571f12efe50ecb5740f129c8acb3e16f and its dirty
manifest; a commit alone does not identify that source. Exact command/tool/source
hashes and terminal exits are retained in VAMS-implementation-20261029:

- SOURCE-SCAN-INPUTS-22.json: unchanged rules and reviewed source instructions.
- SOURCE-SCAN-22.json: unchanged narrow-allowlist regression and failed M0.4 gate.
- SOURCE-SCAN-INVENTORY-22.json: metadata-only1,119 matches, including479vendor.
- SOURCE-SCAN-TRIAGE-22.json:640 UNREVIEWED source-shape records; no matched values.
- SCAN-EVIDENCE-PREPARATION-22.json: exact public digest and semantic equivalence.
- SCAN-EVIDENCE-REGRESSION-22.json: original1/candidate0 with unchanged rules.
- SOURCE-SCAN-INTEGRATION-22.json: guarded publication and original-source archive.

Next acceptance requirements

1. Resolve every remaining first-party identity against its exact source version.
   Field names, fixture labels and hexadecimal length alone cannot establish that
   a candidate is a noncredential. Independent disposition authority is UNKNOWN.
2. Preserve historical manifests/results. Any eventual release-source extraction
   or coordinated history change needs its own reviewed mapping and authority;
   deleting evidence, blanket allowlisting or scanner-rule relaxation cannot close
   this gate. Existing exact vendor adjudication remains limited to its pinned set.
3. Run unchanged current-tree and complete-history gates on the final candidate;
   reconcile all reachable refs with the credential-incident closure record.
4. Obtain actual provider/identity impact, revocation/decommission and independent
   acceptance records through the existing D5/D7 process. Do not probe or use keys.

The local runs used the retained approved binary in a network-unshared, read-only
environment with a private temporary directory. Raw reports/streams were transient;
durable metadata contains no secret, matched text, snippet, entropy or scanner
fingerprint. Public source-file/record digests are integrity identities, not proofs
of privacy, complete credential closure, native CI parity or independent review.
