# R28 runtime audit resolver-method appendix 01

Status: **ADDITIVE DESIGN FOR STATIC REVIEW. NOT AUTHORIZED FOR EXECUTION.**

Date: 2026-10-18. This appendix supplements, and does not modify, Procedure 03.
It records the concrete static-inspection method and its current feasibility
limits for the frozen R28 runtime and invocation. It does not bind a resolver,
complete a closure, authorize a host change, or authorize either audit stage.

## 1. Frozen subjects and authority

The governing procedure is
`docs/remediation/R28_RUNTIME_AUDIT_PROCEDURE_03_20261018.md`, SHA-256
`4eef1a4b60401f0573c0d39743955f00cd8c1bc932e29e345a6e3bc94203207a`.
Its Section 5 requirements remain normative. The subject runtime root is
`/home/GodOfAgents/vams-evidence/toolchains/python`. Its tree digest checker is
the exact reviewed `r28_runtime_digest_checker_02.py`, SHA-256
`c06610990c110c8ce4fa2141a08da976aed6ca6b47ec58ea00bfdec41dc71956`; the
normative tree algorithm is `R28-RUNTIME-TREE-DIGEST-ALGORITHM-01.md`, SHA-256
`5f44a1eb66abe46b853cd8b35c8c9bddf76cf6fc38655889b22ea5f667306020`. The
expected tree digest is
`70b237e84f1b29ea3eb02a19c7cbbe3e6c504b00ded3893b42166f1c0e485275`.

The host execution subject includes the bound `/usr/bin/python3.14` auditor,
the `/usr/bin/env` and timeout chain, and the static-closure inspection tools.
Previously supplied Python 3.14 and helper observations are historical and
must be refreshed under Procedure 03 Section 3 before any later audit. The
owner previously reported that `readelf`, `file`, `namei`, and `ldconfig` were
found on the ordinary Ubuntu host. Their resolved paths, executable/source
hashes, versions, package identities, interpreters, dependencies, metadata,
and capability results are not bound in this appendix. Do not use agent-sandbox
values as host values.

Packet 05 is the inactive execution-boundary design. Its manifest is
`/home/GodOfAgents/vams-evidence/m7_f04_offline_check_differential_r7_20261010/corrections/r7-namespace-setup/qualification-13/prospective-f04-check-20261014/resume-20261014-01/current-review/amendment-06/R28-EXECUTION-BOUNDARY-PACKET-05/R28-EXECUTION-BOUNDARY-PACKET-05-MANIFEST.json`, SHA-256
`bc5b99bfc3b375a6f72d4d88a7189e76f6a7fdc879c4beb3268d00e52f698ef7`. The
profile to compare with every selected object is the manifest-bound
`vams-a06-r28-slot08.apparmor`, SHA-256
`6a70b30032fc5d6cff1ed1c3ccec6da0bd55c2adb2b57483017a1403e644752d`. The
bound unit is `vams-a06-r28-slot08.service`, SHA-256
`2899dbcd7d9ece4f93ab6d99646885e15161fa559d1d6ebfab5fdf21e0997683`.
The invocation is `R28-BOUNDARY-INVOCATION-05.json`, SHA-256
`fbedd59b4856db232ff696bf6295399d57e3b1401f575d31e66cf55ae97a1b25`. It
binds the future chain `/usr/bin/setpriv` → `/usr/bin/env -i` →
`/home/GodOfAgents/vams-evidence/toolchains/python/bin/python3.12 -s -B` →
the frozen revision-28 `qualification_controller_q13.py`, and the unit's
`UnsetEnvironment=` loader-variable list. Its recorded systemd start command
has not been executed; Slot 08 remains NOT RUN and launch remains separately
gated.

These hashes identify reviewed inactive bytes; they do not prove installed or
effective host state. The packet manifest, profile, unit, invocation, freeze,
candidate, fixture evidence, and historical records are inputs only and must
remain unchanged by this appendix.

## 2. Proposed static method and evidence records

This is an operational inspection design and evidence schema, not a runnable
closure command. The ordinary-host `find`, `file`, `readelf`, and `ldconfig`
path/hash bindings are not present in the retained readbacks, and the resolver
required for selected-object decisions is unbound. Do not run a partial
inventory and label it Section 5 closure.

The method has two layers. First, use only freshly identity-bound host tools to
make a complete, no-follow file and ELF inventory. Second, apply the exact
ordinary-host glibc selection rules to each `DT_NEEDED` edge and recursively
inspect the selected objects. The second layer needs a resolver that actually
implements the host's cache, hwcaps, secure-execution, dynamic-token and
RPATH/RUNPATH rules. A candidate list is not a selected-object answer.

For every input and selected object, the evidence row must retain: input name;
canonical resolved path and each symlink hop; object role (runtime, auditor,
helper, interpreter, preload, or external DSO); file classification and
command status; ELF class, endianness, machine and OS ABI; `PT_INTERP`; every
dynamic tag including `DT_NEEDED`, `DT_RPATH`, `DT_RUNPATH`, audit/depaudit,
filter/auxiliary and search flags; source tag and unexpanded bytes; expanded
search components without normalizing away empty or relative entries; ordered
search-directory candidates; each candidate's compatibility result; selected
path and selection reason; selected-object metadata, SHA-256, capability
output/status and package/version where available. Preserve complete raw
`file` and `readelf -W -h -l -d -V` outputs and statuses. A missing field,
nonzero command, parse warning, unreadable file, unresolved path, or ambiguous
selection is a failure, not an omission.

An ELF feature may be recorded as inapplicable only when bound raw evidence
proves the relevant input is absent or the exact loader rule excludes it for
this invocation. For example, a `readelf` record with no `DT_RUNPATH`
establishes that object has no RUNPATH tag; it does not establish that
inherited RPATH or the environment is irrelevant. A missing candidate in
`ldconfig -p` alone does not establish that the cache cannot select an object.
Unknown, unsupported, or unobserved inputs remain unresolved.

The root inventory is built from the exact Section 1 runtime path without
following symlinks. Enumerate all regular files, classify every file with the
bound `file`, and inspect every ELF with the bound `readelf`. The implementation
must preserve arbitrary path bytes (NUL-delimited path transport), detect
inventory changes while reading, and fail if any regular file is unreadable,
malformed, unclassified, or of unsupported form. Do not run an ELF or loader
against a target. `readelf` output provides declarations and compatibility
metadata; it does not itself resolve dependencies.

For each ELF and each non-slash `DT_NEEDED` name, the resolver must calculate
the search order under the exact ordinary-host loader implementation and
effective invocation context, then report the first compatible object. A
name containing `/` is resolved as the path named by that dependency, with
its symlink chain and compatibility checked. Apply dynamic-string expansion
to the object that owns each tag: `$ORIGIN` is based on that object's path,
and `$LIB` and `$PLATFORM` use the bound loader's definitions and host
platform. Preserve colon/empty/relative search entries exactly until the
loader rule gives them meaning; do not collapse or deduplicate them early.
Apply legacy `DT_RPATH` inheritance only when that object has no
`DT_RUNPATH`; apply `DT_RUNPATH` only to direct dependencies. Include effective
all observed `LD_*` values and `GLIBC_TUNABLES` after systemd manager
composition, `UnsetEnvironment=`, the trusted launcher and `env -i`
transitions. Resolve documented loader variables such as `LD_LIBRARY_PATH`,
`LD_PRELOAD`, and `LD_AUDIT`; treat a literal `LD_DEPAUDIT` environment
variable as unrecognized/unverified unless the exact installed Ubuntu loader
source documents it. `DT_DEPAUDIT` is an ELF dynamic tag and must be handled
as such. Evaluate
secure-execution filtering per relevant executable from the invocation's
credential/capability context and the applicable security-module behavior.
If that context cannot establish the `AT_SECURE` branch, both possible
branches must be reported and the requested *selected* closure remains
unresolved.

Use the exact cache bytes and fresh `ldconfig -p` output as cache evidence, not
as proof of selection. Apply cache precedence and compatibility, glibc-hwcaps
priority, `DF_1_NODEFLIB`, configured loader directories, and built-in default
directories according to the bound loader. Record relevant CPU/auxiliary
vector inputs (`AT_HWCAP`, `AT_HWCAP2`, and `AT_PLATFORM` where applicable),
loader tunables, enabled hwcaps subdirectories and flags used to interpret
each decision. Resolve every object named by environment preload/audit values
and `/etc/ld.so.preload` as part of the graph. Recursively inspect the
selected external objects until every edge closes. Include the ELF
interpreter, every `/etc/ld.so.preload` object, and the selected dependencies
of the auditor, `/usr/bin/env` resolved target, and any resolver/helper ELF.
Mark each selected object as bundled under the frozen runtime root or external
to it.

The final path review compares each selected canonical object and the
invocation-visible path/symlink chain against the exact inactive Packet 05
profile. A selected path not allowed by the bound profile, a path alias that
escapes the reviewed mapping, or a dependency absent from the recorded path
set blocks closure and requires a separately reviewed packet successor. Do
not edit Packet 05 or broaden its allow rules in this appendix.

For runtime-dependent `dlopen()`/`dlmopen()` objects, inspect source-controlled
load sites and their inputs without importing or executing candidate code or
the pinned Python runtime. Record each literal and computed object name, call
site, condition, and possible path source. A computed or environment-derived
object name that cannot be bounded is an unresolved dynamic-load edge. The
optional full import inventory of the auditor is not required and is not a
substitute for this source-controlled dynamic-load review.

The eventual command must be one reviewed, read-only, fail-closed command
under Procedure 03's aggregate 1,800-second TERM deadline and five-second KILL
escalation. Its capture wrapper must preserve separate raw stdout/stderr,
immediate status, exact argv/environment, tool bindings, per-command statuses,
all inventory/selection records and process/cleanup observations. No partial
output may be accepted. No such final command can be bound until the resolver
implementation and dependencies are selected and independently reviewed.

## 3. Section 5 requirement crosswalk

| Section 5 requirement | Proposed inspection method and exact source/tool binding | Evidence and acceptance | Limitation / fail-closed rule |
|---|---|---|---|
| Enumerate every regular file under the frozen root without following links; classify each file. | Use the exact runtime root above; bind ordinary-host `find` and `file` by Section 3 resolved path, bytes, version/package, metadata, capabilities and dependencies. Enumerate with no-follow semantics and NUL-safe paths; call `file` once per regular file. | Complete path list, raw classification output and per-command status; every path classified, no unreadable or malformed item, and counts reconcile to the tree inventory. | Prior host observation says `file` was found, but its exact host binding is missing. Any classification uncertainty, changed inventory, unsupported file or failed status blocks. |
| Preserve ELF header, program headers, dynamic tags and symbol versions for every ELF; include auditor, `env`, resolver and helpers. | Bind `readelf`; run `readelf -W -h -l -d -V` on every classified ELF and the exact host auditor/helper objects. Bind auditor/checker/runtime identities from Procedure 03 Sections 1 and 3. | Complete raw output and status per object; every ELF has parseable class/machine/interpreter/tags/version requirements. | `readelf` is an inspector, not a resolver. Exact host executable path/hash and complete runtime closure are not supplied. A nonzero or partial stream blocks. |
| Record all dependencies, RPATH/RUNPATH, audit/depaudit/filter/auxiliary tags and search flags. | Extract all dynamic tags with bound `readelf`; interpret only through a resolver bound to the exact installed loader semantics. | Per-object tag table retains raw tag bytes and normalized meaning; no unknown tag is discarded; all names become graph edges or explicit inapplicability evidence. | Static ELF inspection cannot infer runtime `dlopen` behavior. Unknown or unsupported tags block; they cannot be labelled irrelevant from absence in a partial parser. |
| Resolve slash-containing dependency names and report exact search directories and first compatible selected object for every other name. | Resolve slash names as paths. For names, feed each declaring object, its parent-chain RPATH state, invocation context, host loader/cache/config and candidate object metadata into an exact glibc-compatible static resolver. | Ordered search trace with candidate path, compatibility result, selected first match and reason for every edge. Recursively repeat until closed. | No bound installed resolver is established. `ldconfig -p` lists candidates; `readelf` only describes ELF; neither identifies the selected file. No manual guess or `ldd`/loader execution is acceptable. This requirement is currently BLOCKED. |
| Expand `$ORIGIN`, `$LIB`, `$PLATFORM` correctly; preserve empty/relative search components. | Resolver expands each token in the context of the object owning the tag and the exact loader/platform behavior. Retain original bytes and expanded result. | Component-by-component expansion record, preserving order and empty elements; compare with exact loader specification/source. | `pax-utils` upstream `lddtree.py` v1.3.10 explicitly leaves `$LIB` and related expansion as TODO and does not establish full per-object expansion. No local installed copy/version is bound. Unsupported token context blocks. |
| Correct RPATH inheritance and RUNPATH direct-dependency semantics. | Resolver carries parent RPATH only when the owning object lacks RUNPATH; RUNPATH applies only to direct children. Validate against glibc 2.43 behavior and per-object tags. | Dependency graph annotates each inherited component with its owning object and traversal edge; direct-only RUNPATH is visible. | `lddtree` v1.3.10 upstream constructs a simplified aggregate path list for children; it has not been shown to satisfy the required inheritance semantics. A flattened search list is rejected. |
| Account for secure-execution environment filtering and the actual effective loader environment. | Bind host loader and systemd/launcher configuration; preserve only loader-affecting environment values from manager settings, `systemd.setenv=`, unit sources, launcher and `env -i` transition. Analyze the `AT_SECURE` branch for each relevant ELF. | Effective variable table by process transition, plus secure/non-secure determination and reason; filtered variables and resulting search inputs are explicit. | `AT_SECURE` is runtime-context dependent and can be affected by credentials/capabilities or an LSM. Static file metadata alone cannot prove it. Unknown branch blocks a single selected closure. |
| Include cache entries and select correctly with glibc-hwcaps, `DF_1_NODEFLIB`, configured and default directories. | Bind exact loader, `/etc/ld.so.cache` bytes, `ldconfig -p`, loader config/include files, relevant tunables and host platform inputs. Use resolver logic matching that exact loader. | Ordered cache candidates and chosen compatible file; hwcaps candidate/priority reasoning; configured/default directory order; NODEFLIB handling; raw cache hash/list/config. | `ldconfig -p` is candidate evidence only. It does not by itself prove first selected object for the effective CPU, cache flags, tunables and per-object search state. The known upstream `lddtree` does not parse the glibc cache/hwcaps selection. BLOCKED absent a suitable resolver. |
| Recursively inspect selected external DSOs to closure; include interpreter, preloads and host helper closure. | Starting from all runtime ELF objects plus exact auditor/helper roots, resolve each edge as above. Bind and inspect the loader, `/etc/ld.so.preload`, `/usr/bin/env` target, Python 3.14 auditor, resolver and all selected DSOs. | A closed graph with no unresolved edge; each node classified bundled/external and has canonical path, symlink chain, file type, metadata, hash, capabilities and package/version where available. | Earlier library observations are historical; Procedure 03 requires fresh ordinary-host readbacks. Unknown package ownership does not imply no package. Missing preload or transitive closure blocks. |
| Bind selected paths to inactive Packet 05 AppArmor policy. | Compare each canonical selected object and every invocation path alias with manifest-bound profile `vams-a06-r28-slot08.apparmor` (manifest `bc5b…98ef7`; profile `6a70…752d`). | Exact path-by-path allow/deny table, including symlink chain, mapping and access mode, reviewed against unchanged profile bytes. | Profile source/hash is static design only, not effective enforcement. Any required path not explicitly covered blocks; only a reviewed successor may change bindings. |
| Review source-controlled dynamic-load paths before provisioning. | Read-only source review of the exact relevant loader/runtime/candidate code; search and trace `dlopen`, `dlmopen`, `ctypes`, extension loading, plugin discovery and environment/config-derived names without importing or executing it. | Call-site register binds source hashes, conditions, object-name construction and resolved/bounded object set. | Search hits alone are not complete; computed names, hidden loaders, or behavior dependent on unreviewed inputs stay unresolved. The optional full auditor import inventory is not a mandatory gate. |
| Use a bounded, reviewed, captured, all-or-fail collection. | Final single command must bind every helper and resolver, run read-only under the procedure's 1,800-second TERM + 5-second KILL bound, and use the separately reviewed no-clobber capture design. | Exact argv/environment, raw streams, immediate status, complete per-command statuses, hashes, process observations and cleanup record; all outputs copied and verified. | No closure command or wrapper is currently reviewed. A timeout, signal, capture error, incomplete status, partial graph or uncertain cleanup blocks; no retry or stitched output. |

## 4. Resolver feasibility finding

The owner-reported ordinary-host check found no PATH-visible `lddtree` and no
dpkg package record matching `*/lddtree`. This establishes only those two
searches, not machine-wide absence. The same owner report says `readelf`,
`file`, `namei`, and `ldconfig` were found, but does not include their exact
resolved identities. The retained record contains no other exact, reviewed
ordinary-host static-resolver identity.

The known upstream `pax-utils` `lddtree.py` v1.3.10 source is not an adequate
substitute: it marks `$LIB`/related token support TODO, its input-path logic
does not establish the required exact per-object expansion, and it builds a
simplified combined search-path list. The inspected implementation reads
`ld.so.conf` and `LD_LIBRARY_PATH`; that is not a proof of the active
`/etc/ld.so.cache` selection or glibc-hwcaps priority. Its exact source is
available at
https://github.com/gentoo/pax-utils/blob/v1.3.10/lddtree.py. That conclusion is
about this upstream version; it does not assert what files may exist elsewhere
on the host.

The required behavior is described by the GNU C Library 2.43 Dynamic Linker
manual and Diagnostics pages and Linux `ld.so(8)`:

- https://www.sourceware.org/glibc/manual/2.43/html_node/Dynamic-Linker.html
- https://www.sourceware.org/glibc/manual/2.43/html_node/Dynamic-Linker-Diagnostics.html
- https://man7.org/linux/man-pages/man8/ld.so.8.html

These references explain loader behavior; they do not bind Ubuntu's exact
installed glibc build, its downstream patches, cache format/state, selected
host paths or task's secure-execution branch. The previous host package
observation `libc6 2.43-2ubuntu2.4` is historical only, and no matching source
package or exact loader executable hash is bound here. `ldconfig -p` cannot
fill this gap, and Section 5 forbids executing the target ELF or replacing
static selection with `ldd`/loader `--list`.

**Conclusion: no feasible static-closure method is established from the
currently bound tools and evidence. Section 5's first-selected-object and
recursive-closure requirements remain BLOCKED.** The inventory and metadata
steps above are useful inputs but do not constitute a complete audit command
or satisfy the resolver gate. No expected digest or acceptance rule is
weakened.

## 5. Fail-closed conditions and smallest next decision

Stop before either audit stage if any exact host binding is missing or stale;
if the exact host loader/source semantics cannot be identified; if no resolver
passes independent review for cache, hwcaps, secure execution, tokens and
RPATH/RUNPATH; if any selected path is ambiguous/unreadable/unbound or not
covered by Packet 05; or if a single bounded, fully captured closure command
cannot be independently reviewed. Do not install `pax-utils` merely to obtain
`lddtree`; do not invoke `ldd` or a target loader; do not implement or run a
replacement under this appendix.

The smallest next owner authorization is a separate source-preparation task to
implement and independently review a standalone, version-bound static
resolver for the exact ordinary-host glibc selection semantics, including
cache and hwcaps, without executing inspected ELF files. That task would
authorize writing the helper source and independent static code review only;
it would not authorize running the helper or its tests, installing it,
changing the host, performing the runtime audit, provisioning, validation,
collection, candidate execution, or qualification. Those actions would
require separate authorization. If the owner declines a new resolver,
Section 5 remains unresolved unless a suitable already-installed
implementation is later identified and independently shown to satisfy every
row above.

No `lddtree` cross-check, complete auditor import inventory, package
installation, resolver execution, ELF execution, fixture/test run, runtime
audit, provisioning, collection, boundary validation, qualification, Aiken
command, or deployment action is authorized by this appendix.

## 6. Review and readiness state

This appendix is for independent static review against Procedure 03 Section 5.
Review approval can accept the method's limits and identify corrections; it
cannot make the unresolved resolver/closure requirement pass. Any substantive
change to the appendix requires a new additive revision and fresh review.

The fixture-validation gate remains accepted only for the complete 21-test
fixture batch. The real-runtime audit remains NOT RUN. Amendment 06 remains
two suite invocations granted, one consumed, one remaining; Slot 08 remains
NOT RUN. Slot 07 remains unsuccessful, cleanup-incomplete and
`OWNERSHIP_UNCERTAIN`. Readiness remains NOT READY. Aiken, Deployment, Deposit,
Slash activation and ExecuteIntent remain disabled.
