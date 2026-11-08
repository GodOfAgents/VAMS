# R28 ordinary-host runtime audit procedure — draft

Status: **DRAFT FOR INDEPENDENT REVIEW. NOT OWNER-AUTHORIZED FOR EXECUTION.**
This procedure audits runtime files and static ELF metadata only. It does not
execute the pinned Python 3.12 runtime, candidate code, a service, or a test.

## Bound artifacts and scope

- Candidate runtime root: `/home/GodOfAgents/vams-evidence/toolchains/python`
- Reviewed inventory checker:
  `/home/GodOfAgents/vams-evidence/m7_f04_offline_check_differential_r7_20261010/corrections/r7-namespace-setup/qualification-13/prospective-f04-check-20261014/resume-20261014-01/current-review/amendment-06/R28-RUNTIME-DIGEST-CHECKER-REVIEW-01/r28_runtime_digest_checker_02.py`
  SHA-256 `c06610990c110c8ce4fa2141a08da976aed6ca6b47ec58ea00bfdec41dc71956`
- Normative inventory algorithm:
  `current-review/amendment-06/R28-EXECUTION-BOUNDARY-PACKET-01/R28-RUNTIME-TREE-DIGEST-ALGORITHM-01.md`
  SHA-256 `5f44a1eb66abe46b853cd8b35c8c9bddf76cf6fc38655889b22ea5f667306020`
- Bound ordinary-host auditor: `/usr/bin/python3.14`, Python 3.14.4,
  SHA-256 `b8d8288faefdd300201f43fcf00f6f539a27218eeed3a3dff5ab10b9c4c99700`.
- Tree expectation: SHA-256
  `70b237e84f1b29ea3eb02a19c7cbbe3e6c504b00ded3893b42166f1c0e485275`;
  5,019 entries (225 directories, 3,746 regular files, 1,048 symlinks);
  362,962,888 regular-file bytes.
- Separate root expectation: directory, mode `0700`, UID/GID `1000`, no
  xattrs. Root size and link count are deliberately excluded.

This first audit covers the exact ordinary-host source root only. The packet
requires repeating the same digest, symlink-containment, and root-metadata
checks on the staged tree and mounted read-only target after separately
authorized provisioning. No staging or mount occurs in this procedure.

## Preconditions and evidence destination

Run only in an ordinary Ubuntu host terminal, outside the Codex sandbox. Do not
install tools or change host configuration. Before any later authorized run,
recheck the checker, algorithm, `/usr/bin/python3.14`, `/usr/bin/env`, and
`/usr/bin/timeout` resolved paths and hashes. The prior host values for the
auditor, `env`, and `timeout` are historical bindings from fixture execution
02 and must be freshly read before the runtime audit.

Bind the resolved path, version, file type, mode, owner/group, link count,
size, SHA-256, and capability result for each inspection helper actually used:
`find`, `file`, `readelf`, `ldconfig`, `stat`, `sha256sum`, `readlink`, and
`/usr/sbin/getcap`. Do not install a missing helper. If an ELF parser/resolver
is not present or its binding cannot be verified, stop with closure incomplete.

The proposed additive record directory is
`.../current-review/amendment-06/R28-RUNTIME-DIGEST-CHECKER-REVIEW-01/R28-RUNTIME-AUDIT-01/`.
Its exact path must be confirmed absent with no-follow checks before creation.
After separate owner authorization, create it mode `0700`; do not overwrite
anything. Keep all captures outside the measured runtime root. Preserve the
exact command/environment, helper bindings, raw stdout and stderr, immediate
exit status, hashes, and any uncertain state. The checker gets one invocation
with TERM at 120 seconds and KILL escalation 5 seconds later. On any mismatch,
read error, timeout, signal, or capture error, retain the record and stop; no
retry.

## Descendant-tree digest and root metadata

After binding checks pass, the single proposed checker command is:

```bash
/usr/bin/env -i LANG=C LC_ALL=C \
  /usr/bin/timeout --signal=TERM --kill-after=5s 120s \
  /usr/bin/python3.14 -I -S -B \
  /home/GodOfAgents/vams-evidence/m7_f04_offline_check_differential_r7_20261010/corrections/r7-namespace-setup/qualification-13/prospective-f04-check-20261014/resume-20261014-01/current-review/amendment-06/R28-RUNTIME-DIGEST-CHECKER-REVIEW-01/r28_runtime_digest_checker_02.py \
  /home/GodOfAgents/vams-evidence/toolchains/python
```

Capture stdout JSON and stderr raw bytes separately using exclusive,
no-clobber files; record the checker exit immediately. Success requires exit
zero and exact agreement with the digest, counts, regular-file byte total, and
root metadata above. A checker failure is not an empty inventory. The reviewed
checker performs two inventories and verifies stable signatures, no-follow
reads, xattrs, within-tree hard-link groups, and symlink containment; its
success is not a host ELF-closure result.

## Static ELF and external-library closure

Do not use `ldd`, invoke the inspected loader with a target, or execute any
ELF object to enumerate dependencies. Use static reads only. First enumerate
every regular file below the runtime root without following symlinks and
classify it with the host-bound `file` helper. For every ELF object, including
the interpreter, standard-library extension modules, and bundled Tcl objects,
capture `readelf -W -h -l -d <absolute-path>` output. Also inspect the
resolved `/usr/bin/env` target. Any unreadable, malformed, or unclassified
regular file makes the inventory incomplete.

For every inspected object, record its ELF class and machine, `PT_INTERP`,
`DT_NEEDED`, `DT_RPATH`, `DT_RUNPATH`, and any audit/depaudit tags. Resolve
each dependency to the exact selected file using the ordinary host loader's
search rules, not merely the set of candidates in the cache. Expand loader
tokens such as `$ORIGIN`, `$LIB`, and `$PLATFORM` against the object that
contains the tag. Respect the distinction that `DT_RUNPATH` applies only to
direct dependencies while legacy `DT_RPATH` can apply down the dependency
tree. Use `ldconfig -p` only as a read-only view of cache candidates; hash
`/etc/ld.so.cache` itself. Recursively inspect each newly selected external
DSO until every edge closes. Mark paths inside the pinned tree as bundled and
paths outside it as host dependencies.

The `env` launcher is dynamically loaded by systemd before its `-i` option
clears the environment for Python. Therefore bind the effective system-unit
inputs that can affect the launcher's loader: the exact inactive unit and
drop-ins, `DefaultEnvironment=` configuration, `systemd.setenv=` kernel
arguments, any passed `LD_*` values, and `/etc/ld.so.preload` (record absence
or bind its contents and every preloaded DSO). Do not retain unrelated manager
environment values. For the Python child, record that `env -i` supplies the
frozen environment and removes inherited `LD_*` values. If any effective
loader variable, preload, selected path, or library differs from the reviewed
profile/freeze, stop and require updated bindings and fresh review.

For the loader and every selected external DSO, record resolved path and
symlink chain, file type, mode, numeric UID/GID, link count, byte size,
SHA-256, `getcap -n` output and exit status, and owning package/version when
available. Include the exact resolved loader and current loader-cache hash.
Check each path against the inactive AppArmor profile. Any missing, ambiguous,
unresolved, unbound, or profile-unlisted dependency blocks the runtime gate.

This static closure addresses ELF-declared dependencies and the explicit
preload inputs above. It does not claim observation of runtime `dlopen()`
behavior by candidate code. Any source-level dynamic-load path that expands
the required closure must be identified and reviewed before provisioning.

## Review and stop conditions

The independent reviewer must check the exact procedure bytes, helper bindings,
loader search-order treatment, effective `env` startup environment, closure
table, profile path coverage, and evidence capture plan. This draft has not yet
received that review. Only after review and a separate owner authorization may
an operator run the one bounded read-only source-tree audit. A passing source
tree audit does not approve staging, profile installation, boundary
validation, collection, candidate execution, or Slot 08.

Relevant primary references: the retained normative algorithm above; GNU
Binutils `readelf` documentation; Linux `ld.so(8)` and `ldconfig(8)`; and
systemd 257 `systemd.exec(5)` environment construction. The operator packet
remains authoritative for profile/invocation bindings and explicitly marks
host transitive-closure hashes pending.
