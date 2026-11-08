# R28 ordinary-host runtime audit procedure 03

Status: **DRAFT FOR INDEPENDENT REVIEW. NOT AUTHORIZED FOR EXECUTION.**

Successor to Procedure 02, SHA-256
`ff6e6b01b69ec7bd6a2008694b30512b4d5e8c1c9f7f779918fb79ddafae1bad`.
This revision removes one duplicate, misleading `file_status` output from
Section 3. It otherwise preserves the retained Procedure 02 text and all
unresolved execution gates.

This version turns the retained digest draft into a bounded, fail-closed audit
sequence and identifies the exact host evidence needed to finish static ELF
closure. It does not run the checker, inspect the runtime from the agent
sandbox, execute the pinned Python 3.12 runtime, execute candidate code, or
change the host. It preserves draft 01 unchanged.

## 1. Scope and exact bindings

The audit subject is only the ordinary-Ubuntu-host source tree at:

```text
/home/GodOfAgents/vams-evidence/toolchains/python
```

The reviewed checker is:

```text
/home/GodOfAgents/vams-evidence/m7_f04_offline_check_differential_r7_20261010/corrections/r7-namespace-setup/qualification-13/prospective-f04-check-20261014/resume-20261014-01/current-review/amendment-06/R28-RUNTIME-DIGEST-CHECKER-REVIEW-01/r28_runtime_digest_checker_02.py
SHA-256 c06610990c110c8ce4fa2141a08da976aed6ca6b47ec58ea00bfdec41dc71956
```

The normative algorithm is:

```text
/home/GodOfAgents/vams-evidence/m7_f04_offline_check_differential_r7_20261010/corrections/r7-namespace-setup/qualification-13/prospective-f04-check-20261014/resume-20261014-01/current-review/amendment-06/R28-EXECUTION-BOUNDARY-PACKET-01/R28-RUNTIME-TREE-DIGEST-ALGORITHM-01.md
SHA-256 5f44a1eb66abe46b853cd8b35c8c9bddf76cf6fc38655889b22ea5f667306020
```

The bound ordinary-host auditor is `/usr/bin/python3.14`, Python 3.14.4,
SHA-256 `b8d8288faefdd300201f43fcf00f6f539a27218eeed3a3dff5ab10b9c4c99700`.
The accepted fixture record observed `/usr/bin/env` at
`/usr/lib/cargo/bin/coreutils/env` and `/usr/bin/timeout` at
`/usr/lib/cargo/bin/coreutils/timeout`, both SHA-256
`48893b0fb21436b54619db80486e83ef39dfccaf1aefe83dfa00c02d6146e8c0`.
Those are prior ordinary-host observations, not fresh audit-time bindings. All
paths, versions, metadata, hashes, capabilities, package identities, and
required dependency records must be rechecked on the ordinary host immediately
before the audit.

Expected source-tree result:

- Descendant digest: `70b237e84f1b29ea3eb02a19c7cbbe3e6c504b00ded3893b42166f1c0e485275`.
- 5,019 entries: 225 directories, 3,746 regular files, 1,048 symlinks.
- Regular-file bytes: `362962888`.
- Root metadata, checked separately with no-follow semantics: directory, mode
  `0700`, UID/GID `1000`, no xattrs. Root size and link count are not bound.

The optional full auditor import inventory is not a mandatory gate. Direct
review of the bound checker source and fresh binding of the `/usr/bin/python3.14`
auditor remain required. No source-tree result establishes external DSO
closure, runtime `dlopen()` behavior, effective host enforcement, staging
integrity, or launch approval.

## 2. Required execution authority and evidence destination

The host commands below are for an ordinary Ubuntu host terminal only. Do not
run them from Codex, the agent sandbox, PowerShell, or against the Windows
checkout. No `sudo`, installation, package update, mount, service change,
staging, or candidate command is part of this procedure. A permission error,
missing helper, path or hash mismatch, incomplete read, or unresolved
dependency is a stop; preserve the output and do not retry.

After exact-procedure independent review and separate owner authorization, the
only proposed additive evidence directory is:

```text
/home/GodOfAgents/vams-evidence/m7_f04_offline_check_differential_r7_20261010/corrections/r7-namespace-setup/qualification-13/prospective-f04-check-20261014/resume-20261014-01/current-review/amendment-06/R28-RUNTIME-DIGEST-CHECKER-REVIEW-01/R28-RUNTIME-AUDIT-01
```

Before creating it, confirm the exact path is absent without following links.
After authorization, create it once with mode `0700`. Never overwrite an
existing path. Keep every capture outside the measured runtime tree. Retain
the exact commands and environment, helper bindings, complete raw stdout and
stderr, immediate status, copy hashes, and cleanup observations. If capture,
status, timeout, signal, or process completion is uncertain, retain all state.

This is one audit attempt: one digest-checker invocation and one bounded
static-closure collection. Any mismatch or failure ends the attempt; no retry,
partial-result stitching, or altered expected value is allowed. The checker
stage is bounded by TERM at 120 seconds and KILL escalation five seconds later.
The static-closure stage has a proposed aggregate 1,800-second TERM deadline
and five-second KILL escalation. It must run as one reviewed command under the
bound timeout helper; if a reviewed single-command collector cannot enforce
that aggregate bound, stop and return the procedure for revision before
execution. These are wall-clock limits, not process-count or memory ceilings.

## 3. Ordinary-host read-only preflight

This preflight prints to the terminal and creates no files. Run it only in an
ordinary Ubuntu Bash terminal. Preserve each command's exit status with its
output. It is intended to return the missing host evidence; it does not run
the runtime checker or any ELF resolver.

```bash
(
  set +e
  set +u
  set -o pipefail
  printf '%s\n' '=== tool paths visible to this host shell ==='
  for name in env timeout python3.14 bash find file readelf ldconfig stat sha256sum readlink namei getcap dpkg-query systemctl systemd-analyze lddtree; do
    printf '\n--- %s ---\n' "$name"
    type -aP "$name"
    printf 'type_status=%s\n' "$?"
  done

  printf '\n%s\n' '=== selected helper identities ==='
  READLINK=$(type -P readlink)
  STAT=$(type -P stat)
  SHA256=$(type -P sha256sum)
  GETCAP=$(type -P getcap)
  DPKG_QUERY=$(type -P dpkg-query)
  FILE=$(type -P file)
  NAMEI=$(type -P namei)
  for name in env timeout python3.14 bash find file readelf ldconfig stat sha256sum readlink namei getcap dpkg-query systemctl systemd-analyze lddtree; do
    selected=$(type -P "$name")
    printf '\n--- identity: %s ---\n' "$name"
    if [[ -z $selected ]]; then
      printf 'selected_path=ABSENT\n'
      continue
    fi
    printf 'selected_path=%s\n' "$selected"
    if [[ -z $READLINK || -z $STAT || -z $SHA256 || -z $GETCAP || -z $DPKG_QUERY || -z $FILE ]]; then
      printf '%s\n' 'identity_status=INCOMPLETE required inspection helper absent'
      continue
    fi
    resolved=$("$READLINK" -e -- "$selected")
    resolve_status=$?
    printf 'resolved_path=%s\nresolve_status=%s\n' "$resolved" "$resolve_status"
    if (( resolve_status != 0 )); then
      printf '%s\n' 'identity_status=INCOMPLETE resolution failed'
      continue
    fi
    file_description=$("$FILE" --brief -- "$resolved")
    file_status=$?
    printf 'file_description=%s\nfile_status=%s\n' "$file_description" "$file_status"
    if [[ -n $NAMEI ]]; then
      "$NAMEI" -l -- "$selected"
      printf 'symlink_chain_status=%s\n' "$?"
    else
      printf '%s\n' 'symlink_chain_status=UNVERIFIED namei absent'
    fi
    "$STAT" -Lc 'metadata=%F|%a|%u|%g|%h|%s' -- "$resolved"
    printf 'stat_status=%s\n' "$?"
    "$SHA256" -- "$resolved"
    printf 'sha256_status=%s\n' "$?"
    "$GETCAP" -n -- "$resolved"
    printf 'getcap_status=%s\n' "$?"
    owner=$("$DPKG_QUERY" -S -- "$resolved")
    owner_status=$?
    printf 'package_owner_status=%s\n%s\n' "$owner_status" "$owner"
    if (( owner_status == 0 )); then
      package=${owner%%: *}
      "$DPKG_QUERY" -W -f='package_version=${binary:Package}\t${Version}\n' -- "$package"
      printf 'package_version_status=%s\n' "$?"
    fi
    case "$name" in
      lddtree|getcap) printf '%s\n' 'version_status=NOT_INVOKED during identity preflight' ;;
      *) "$resolved" --version 2>&1; printf 'version_status=%s\n' "$?" ;;
    esac
    if [[ $name == lddtree && $file_description == *script* ]]; then
      IFS= read -r resolver_shebang < "$resolved"
      shebang_status=$?
      printf 'resolver_shebang=%s\nresolver_shebang_status=%s\n' "$resolver_shebang" "$shebang_status"
    fi
  done

  printf '\n%s\n' '=== actual Bash process for this preflight subshell ==='
  printf 'bash_subshell_pid=%s\nparent_shell_pid=%s\n' "$BASHPID" "$$"
  if [[ -n $READLINK && -n $STAT && -n $SHA256 ]]; then
    for pid in "$BASHPID" "$$"; do
      bash_exe=$("$READLINK" -e -- "/proc/$pid/exe")
      bash_exe_status=$?
      printf 'bash_pid=%s\nbash_exe=%s\nbash_exe_status=%s\n' "$pid" "$bash_exe" "$bash_exe_status"
      if (( bash_exe_status == 0 )); then
        "$STAT" -Lc 'bash_metadata=%F|%a|%u|%g|%h|%s' -- "$bash_exe"
        printf 'bash_stat_status=%s\n' "$?"
        "$SHA256" -- "$bash_exe"
        printf 'bash_sha256_status=%s\n' "$?"
      fi
    done
  else
    printf '%s\n' 'Bash executable readback incomplete: readlink/stat/sha256sum helper absent'
  fi

  printf '\n%s\n' '=== current shell loader variables ==='
  found_loader_var=0
  for name in "${!LD_@}"; do
    printf '%s=%q\n' "$name" "${!name}"
    found_loader_var=1
  done
  if [[ ${GLIBC_TUNABLES+x} ]]; then
    printf 'GLIBC_TUNABLES=%q\n' "$GLIBC_TUNABLES"
    found_loader_var=1
  fi
  if (( found_loader_var == 0 )); then
    printf '%s\n' 'no LD_* or GLIBC_TUNABLES variables exported in this shell'
  fi

  printf '\n%s\n' '=== system manager loader variables ==='
  systemctl_path=$(type -P systemctl)
  if [[ -n $systemctl_path ]]; then
    "$systemctl_path" show-environment |
    while IFS= read -r assignment; do
      variable=${assignment%%=*}
      case "$variable" in
        LD_*|GLIBC_TUNABLES) printf '%s\n' "$assignment" ;;
      esac
    done
    printf 'systemctl_show_environment_pipeline_status=%s\n' "$?"
  else
    printf '%s\n' 'systemctl=ABSENT'
  fi

  printf '\n%s\n' '=== system-manager effective configuration ==='
  systemd_analyze_path=$(type -P systemd-analyze)
  if [[ -n $systemd_analyze_path ]]; then
    "$systemd_analyze_path" cat-config systemd/system.conf
    printf 'systemd_analyze_cat_config_status=%s\n' "$?"
    printf '%s\n' 'Inspect this output locally. Return only DefaultEnvironment/ManagerEnvironment assignments that set LD_* or GLIBC_TUNABLES; do not paste unrelated manager values.'
  else
    printf '%s\n' 'systemd-analyze=ABSENT'
  fi

  printf '\n%s\n' '=== kernel systemd.setenv arguments ==='
  kernel_cmdline=
  IFS= read -r kernel_cmdline < /proc/cmdline
  read_status=$?
  printf 'proc_cmdline_read_status=%s\n' "$read_status"
  if (( read_status == 0 )); then
    found_setenv=0
    for token in $kernel_cmdline; do
      case "$token" in
        systemd.setenv=*) printf '%s\n' "$token"; found_setenv=1 ;;
      esac
    done
    if (( found_setenv == 0 )); then printf '%s\n' 'no systemd.setenv= argument'; fi
  fi

  printf '\n%s\n' '=== loader cache and preload ==='
  if [[ -n $READLINK && -n $STAT && -n $SHA256 ]]; then
    "$READLINK" -e -- /etc/ld.so.cache
    printf 'cache_resolve_status=%s\n' "$?"
    "$STAT" -Lc '%F|%a|%u|%g|%h|%s' -- /etc/ld.so.cache
    printf 'cache_stat_status=%s\n' "$?"
    "$SHA256" -- /etc/ld.so.cache
    printf 'cache_hash_status=%s\n' "$?"
    ldconfig_path=$(type -P ldconfig)
    if [[ -n $ldconfig_path ]]; then
      "$ldconfig_path" -p
      printf 'ldconfig_cache_list_status=%s\n' "$?"
    else
      printf '%s\n' 'ldconfig=ABSENT'
    fi
    if [[ -e /etc/ld.so.preload || -L /etc/ld.so.preload ]]; then
      "$READLINK" -e -- /etc/ld.so.preload
      printf 'preload_resolve_status=%s\n' "$?"
      "$STAT" -Lc '%F|%a|%u|%g|%h|%s' -- /etc/ld.so.preload
      printf 'preload_stat_status=%s\n' "$?"
      "$SHA256" -- /etc/ld.so.preload
      printf 'preload_hash_status=%s\n' "$?"
      while IFS= read -r preload_line || [[ -n $preload_line ]]; do
        printf 'preload_entry=%s\n' "$preload_line"
      done < /etc/ld.so.preload
      printf 'preload_read_status=%s\n' "$?"
    else
      printf '%s\n' '/etc/ld.so.preload=ABSENT'
    fi
  else
    printf '%s\n' 'cache/preload readback=NOT_RUN; readlink/stat/sha256sum helper absent'
  fi
)
```

Return the complete selected-helper identity records above, including each
command status and the `namei -l` path-chain output. `lddtree` and `getcap` are
identified but not executed for a version string in this preflight; provide
their package/version from installed package metadata and their source or
binary bytes. If `lddtree` is a script, its first line identifies the
interpreter, whose own metadata/hash/capability/package record is also required.
Also provide the exact parent interactive Bash executable identity if it
differs from the recorded preflight subshell. A failed inspection command is
missing evidence, not an empty capability set or absent dependency. A missing
tool is not permission to install or substitute one.

Identify any already-installed static ELF resolver by exact path, source or
binary hash, version/package, interpreter if it is a script, metadata,
capabilities, and dependencies. Do not execute it during preflight. A name or
version string alone is not sufficient. In particular, do not assume
`lddtree` is adequate: the upstream implementation must be checked for the
host's cache selection, glibc-hwcaps, `$ORIGIN`/`$LIB`/`$PLATFORM` expansion,
secure-execution behavior, and RPATH/RUNPATH inheritance. If no existing
resolver is present or its exact implementation cannot be reviewed against
those requirements, stop. Do not install it, invoke `ldd`, invoke a loader
against a target ELF, or invent a replacement in this procedure.

The preflight also must return fresh ordinary-host readbacks for the exact
auditor and its declared ELF dependencies (`libm`, `libz`, `libexpat`, `libc`,
and interpreter), plus the resolved `/usr/bin/env` target and its selected
DSO closure. Prior observations of those values are historical references
only. For each loader or selected external DSO, bind the resolved path and
symlink chain, file type, mode, numeric UID/GID, link count, bytes, SHA-256,
capability output/status, and package/version when available.

## 4. Digest and separate root-metadata stage

Only after the read-only preflight is reviewed, the exact procedure has
independent approval, and the owner authorizes the audit, recheck immediately
before launch the checker, algorithm, interpreter, `env`, `timeout`, and
selected helper hashes. Confirm the evidence directory is still absent before
creating it. Record the exact invocation and environment; capture stdout and
stderr to two exclusive no-clobber files and retain the immediate exit status.

The only proposed checker command is:

```bash
/usr/bin/env -i LANG=C LC_ALL=C \
  /usr/bin/timeout --signal=TERM --kill-after=5s 120s \
  /usr/bin/python3.14 -I -S -B \
  /home/GodOfAgents/vams-evidence/m7_f04_offline_check_differential_r7_20261010/corrections/r7-namespace-setup/qualification-13/prospective-f04-check-20261014/resume-20261014-01/current-review/amendment-06/R28-RUNTIME-DIGEST-CHECKER-REVIEW-01/r28_runtime_digest_checker_02.py \
  /home/GodOfAgents/vams-evidence/toolchains/python
```

This command invokes only the reviewed checker under the ordinary-host
Python 3.14 auditor. It must not import or execute the pinned Python 3.12 tree,
the candidate, or tests. The operator must use the separately reviewed
capture wrapper so both raw streams are exclusive, separate, and outside the
measured tree; it must not redirect over an existing path. The capture wrapper
must record the checker status before running any further command. No checker
retry is authorized.

Accept this stage only if exit is zero and JSON output matches the exact
descendant digest, counts, byte total, and separate root metadata above. Any
read error, incomplete xattr result, race, unsupported entry, symlink escape,
hard-link mismatch, mismatch, timeout, signal, capture error, or ambiguous
completion blocks the stage. Do not interpret an error as an empty inventory.

## 5. Static ELF and external-library closure stage

This stage is required; the tree digest does not cover host DSOs. It may not
start until the installed resolver's exact identity and implementation have
passed independent review and the resolver's use is bound in the exact audit
authorization. No inspected ELF is executed. Do not use `ldd`, run the pinned
loader with a target, or use loader `--list` as a substitute for static
inspection.

The reviewed read-only inventory command must enumerate every regular file
under the exact runtime root without following symlinks; classify every one
with the bound `file`; and fail on an unreadable, malformed, unclassified, or
unsupported item. For each ELF, preserve `readelf -W -h -l -d -V` output. This
captures the ELF header, interpreter/program headers, dynamic tags, and symbol
version requirements. Also inspect the resolved ordinary-host `/usr/bin/env`
target, `/usr/bin/python3.14`, and the resolver/helper objects selected for
the audit. Every command must be checked for a nonzero exit; a partial stream
is not a complete inventory.

For every ELF record class, machine, `PT_INTERP`, every dynamic tag, all
`DT_NEEDED`, `DT_RPATH`, `DT_RUNPATH`, audit/depaudit/filter/auxiliary tags,
and flags affecting search. Resolve slash-containing dependency names as
paths. For other names, show the exact search directories and the first
compatible selected object under the ordinary host loader's rules. Expand
`$ORIGIN`, `$LIB`, and `$PLATFORM` for the object that owns each tag; preserve
empty and relative search components exactly. Carry legacy `DT_RPATH` down
the dependency tree only when `DT_RUNPATH` is absent; apply `DT_RUNPATH` only
to that object's direct dependencies. Account for secure-execution
environment filtering, the effective loader environment, cache entries,
glibc-hwcaps selection, `DF_1_NODEFLIB`, and the default directories. Use
`ldconfig -p` as candidate evidence, not as proof of the selected path.

Recursively resolve and inspect every selected external DSO until the graph
closes. Mark each selected object as bundled inside the pinned tree or an
external host dependency. Include the interpreter/loader and every object in
`/etc/ld.so.preload`; hash `/etc/ld.so.cache`; preserve the cache listing and
the loader-affecting configuration used to interpret it. For each selected
object, preserve canonical path and symlink chain, type, mode, numeric
UID/GID, link count, bytes, SHA-256, `getcap -n` output and exit, and package
version where available. Compare every selected path with the inactive
Packet-05 AppArmor profile. Missing, ambiguous, incompatible, unbound,
unreadable, or profile-unlisted objects block the closure.

The systemd service is not installed. Bind the exact inactive Packet-05 unit
and its `UnsetEnvironment=` list, then preserve only loader-related values
from the ordinary system manager's `DefaultEnvironment=`, manager environment,
`systemd.setenv=` kernel arguments, and any unit environment sources. Do not
copy unrelated manager environment values into evidence. For the later
`setpriv`/`env` chain, distinguish variables seen by the loader when each
helper starts from the environment that `env -i` supplies to Python. The
systemd manager composes environment from multiple sources and removes
`UnsetEnvironment=` names last; verify effective inputs instead of assuming
that `env -i` protects the earlier `setpriv` and `env` loader starts.

The static closure does not establish `dlopen()` behavior at runtime. Review
all source-controlled dynamic-load paths that could add required objects
before provisioning. The optional full import inventory of the auditor is
not required by this procedure.

## 6. Acceptance, review, and stop conditions

Independent review must approve the exact procedure bytes and the returned
ordinary-host bindings before the owner authorizes either audit stage. Review
must cover algorithm and checker identity, preflight scope, chosen resolver
implementation and search semantics, `$ORIGIN`/`$LIB`/`$PLATFORM`, cache and
hwcaps handling, unit/manager loader inputs, every selected dependency and
profile path, capture correctness, the 120-second digest bound, and the
1,800-second aggregate closure bound.

The procedure is not currently execution-ready: no exact ordinary-host
static-resolver identity or complete selected-library closure is retained.
The next owner input is the read-only preflight output in Section 3. If no
already-installed resolver passes review, stop and return that specific
blocker for a separate owner decision; do not install a tool or create a
replacement resolver under this procedure.

A successful source-tree audit still does not approve staging, installing or
loading the profile, boundary validation, collection, candidate execution,
Slot 08, or deployment. Packet 05 remains inactive and static-design only.

## 7. Primary references

- Retained normative runtime-tree specification:
  `R28-EXECUTION-BOUNDARY-PACKET-01/R28-RUNTIME-TREE-DIGEST-ALGORITHM-01.md`.
- GNU `readelf` documentation:
  <https://sourceware.org/binutils/docs/binutils/readelf.html>.
- Linux `ld.so(8)` search rules and dynamic-linker inputs:
  <https://man7.org/linux/man-pages/man8/ld.so.8.html>.
- systemd `systemd.exec(5)` environment composition and final
  `UnsetEnvironment=` handling:
  <https://www.freedesktop.org/software/systemd/man/257/systemd.exec.html>.
- `lddtree` upstream source, if encountered during preflight, for independent
  implementation review only:
  <https://github.com/gentoo/pax-utils/blob/master/lddtree.py>.
