#!/usr/bin/env bash
# Prepare or execute the local portion of the VAMS credential-history rewrite.
#
# This tool is deliberately incapable of pushing to GitHub. It accepts only a
# disposable bare mirror clone and writes sanitized preparation evidence to a
# directory outside both the mirror and the source checkout.

set -euo pipefail

# Direct invocation of Git Bash from PowerShell may inherit a Windows-only
# PATH. Restore Git for Windows coreutils without changing Linux/macOS PATHs.
if [[ -d /usr/bin && -d /mingw64/bin ]]; then
  export PATH="/usr/bin:/mingw64/bin:${PATH}"
fi

readonly INCIDENT_ID="VAMS-PEM-2026-001"
readonly MIN_FILTER_REPO_VERSION="2.47.0"
readonly EXPECTED_ORIGIN_DEFAULT="https://github.com/GodOfAgents/VAMS.git"

readonly -a TARGET_PATHS=(
  "node_identity.pem"
  "neuron/node_identity.pem"
  "simulate-request.mjs"
  "simulate-request-v2.mjs"
  "simulate-request-v3.mjs"
  "register-agent.mjs"
  "verify-escrow.mjs"
  "contracts/test_output_cmd.json"
  "contracts/clean_output.json"
)

EXECUTE=false
MIRROR_PATH=""
EVIDENCE_DIR=""
EXPECTED_ORIGIN="${EXPECTED_ORIGIN_DEFAULT}"
CONFIRM_INCIDENT=""
ROTATION_EVIDENCE=""
MAINTENANCE_APPROVAL=""
PYTHON_BIN="${PYTHON_BIN:-python}"

usage() {
  cat <<'EOF'
Usage:
  history_rewrite.sh --mirror PATH --evidence-dir PATH [options]

Default behavior is a non-destructive inventory. No remote push is ever run.

Required:
  --mirror PATH              Fresh disposable `git clone --mirror` directory.
  --evidence-dir PATH        External directory for sanitized local evidence.

Execution-only requirements:
  --execute
  --confirm-incident VAMS-PEM-2026-001
  --rotation-evidence PATH   Non-empty sanitized rotation/revocation record.
  --maintenance-approval PATH
                              Non-empty signed/approved maintenance record.

Optional:
  --expected-origin URL      Defaults to the public VAMS GitHub URL.
  --help

The caller must separately review the rewritten mirror, obtain explicit
force-push approval, coordinate GitHub protection/support, and run clean scans.
EOF
}

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_value() {
  local option="$1"
  local value="${2:-}"
  [[ -n "${value}" ]] || fail "${option} requires a value"
}

normalize_origin() {
  local value="$1"
  value="${value#git@github.com:}"
  value="${value#https://github.com/}"
  value="${value#http://github.com/}"
  value="${value%.git}"
  printf '%s\n' "${value,,}"
}

normalize_local_path() {
  local value="$1"
  if command -v cygpath >/dev/null 2>&1 \
    && [[ "${value}" =~ ^[A-Za-z]:[\\/].* ]]; then
    cygpath -u "${value}"
  else
    printf '%s\n' "${value}"
  fi
}

canonical_existing_dir() {
  local path="$1"
  [[ -d "${path}" ]] || fail "directory does not exist: ${path}"
  (cd "${path}" && pwd -P)
}

canonical_output_dir() {
  local path="$1"
  mkdir -p "${path}"
  (cd "${path}" && pwd -P)
}

is_within() {
  local child="$1"
  local parent="$2"
  [[ "${child}" == "${parent}" || "${child}" == "${parent}/"* ]]
}

version_at_least() {
  local actual="$1"
  local minimum="$2"
  [[ "$(printf '%s\n%s\n' "${minimum}" "${actual}" | sort -V | head -n 1)" == "${minimum}" ]]
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mirror)
        require_value "$1" "${2:-}"
        MIRROR_PATH="$2"
        shift 2
        ;;
      --evidence-dir)
        require_value "$1" "${2:-}"
        EVIDENCE_DIR="$2"
        shift 2
        ;;
      --expected-origin)
        require_value "$1" "${2:-}"
        EXPECTED_ORIGIN="$2"
        shift 2
        ;;
      --confirm-incident)
        require_value "$1" "${2:-}"
        CONFIRM_INCIDENT="$2"
        shift 2
        ;;
      --rotation-evidence)
        require_value "$1" "${2:-}"
        ROTATION_EVIDENCE="$2"
        shift 2
        ;;
      --maintenance-approval)
        require_value "$1" "${2:-}"
        MAINTENANCE_APPROVAL="$2"
        shift 2
        ;;
      --execute)
        EXECUTE=true
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        fail "unknown argument: $1"
        ;;
    esac
  done
}

validate_boundaries() {
  [[ -n "${MIRROR_PATH}" ]] || fail "--mirror is required"
  [[ -n "${EVIDENCE_DIR}" ]] || fail "--evidence-dir is required"

  MIRROR_PATH="$(normalize_local_path "${MIRROR_PATH}")"
  EVIDENCE_DIR="$(normalize_local_path "${EVIDENCE_DIR}")"
  if [[ -n "${ROTATION_EVIDENCE}" ]]; then
    ROTATION_EVIDENCE="$(normalize_local_path "${ROTATION_EVIDENCE}")"
  fi
  if [[ -n "${MAINTENANCE_APPROVAL}" ]]; then
    MAINTENANCE_APPROVAL="$(normalize_local_path "${MAINTENANCE_APPROVAL}")"
  fi

  MIRROR_PATH="$(canonical_existing_dir "${MIRROR_PATH}")"
  EVIDENCE_DIR="$(canonical_output_dir "${EVIDENCE_DIR}")"

  local script_root
  script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"

  is_within "${MIRROR_PATH}" "${script_root}" \
    && fail "the disposable mirror must be outside the source checkout"
  is_within "${EVIDENCE_DIR}" "${script_root}" \
    && fail "operational evidence must be outside the source checkout"
  is_within "${EVIDENCE_DIR}" "${MIRROR_PATH}" \
    && fail "evidence must be outside the disposable mirror"

  [[ "$(git -C "${MIRROR_PATH}" rev-parse --is-bare-repository 2>/dev/null)" == "true" ]] \
    || fail "--mirror must reference a bare mirror clone"

  [[ "$(git -C "${MIRROR_PATH}" config --bool remote.origin.mirror 2>/dev/null || true)" == "true" ]] \
    || fail "remote.origin.mirror=true is required; use git clone --mirror"

  local fetch_spec
  fetch_spec="$(git -C "${MIRROR_PATH}" config --get remote.origin.fetch 2>/dev/null || true)"
  [[ "${fetch_spec}" == "+refs/*:refs/*" ]] \
    || fail "mirror must fetch every ref namespace (+refs/*:refs/*)"

  local actual_origin
  actual_origin="$(git -C "${MIRROR_PATH}" remote get-url origin)"
  [[ "$(normalize_origin "${actual_origin}")" == "$(normalize_origin "${EXPECTED_ORIGIN}")" ]] \
    || fail "mirror origin does not match the approved repository"

  if git -C "${MIRROR_PATH}" for-each-ref --format='%(refname)' refs/original/ | grep -q .; then
    fail "refs/original exists; create a fresh disposable mirror"
  fi
}

capture_inventory() {
  local prefix="$1"
  git -C "${MIRROR_PATH}" for-each-ref \
    --format='%(refname)%09%(objectname)' | LC_ALL=C sort \
    > "${EVIDENCE_DIR}/${prefix}-refs.tsv"

  {
    printf 'path\tcommit_count\n'
    local path count
    for path in "${TARGET_PATHS[@]}"; do
      count="$(git -C "${MIRROR_PATH}" log --all --format='%H' -- "${path}" | wc -l | tr -d ' ')"
      printf '%s\t%s\n' "${path}" "${count}"
    done
  } > "${EVIDENCE_DIR}/${prefix}-target-paths.tsv"
}

write_plan_metadata() {
  local origin_url="$1"
  {
    printf 'incident_id=%s\n' "${INCIDENT_ID}"
    printf 'mode=%s\n' "$([[ "${EXECUTE}" == true ]] && printf execute || printf inventory)"
    printf 'origin=%s\n' "${origin_url}"
    printf 'target_path_count=%s\n' "${#TARGET_PATHS[@]}"
    printf 'pre_commit_count=%s\n' "$(git -C "${MIRROR_PATH}" rev-list --all --count)"
  } > "${EVIDENCE_DIR}/rewrite-metadata.txt"
}

validate_execution_inputs() {
  [[ "${CONFIRM_INCIDENT}" == "${INCIDENT_ID}" ]] \
    || fail "--confirm-incident must equal ${INCIDENT_ID}"
  [[ -s "${ROTATION_EVIDENCE}" ]] \
    || fail "sanitized rotation evidence is required and must be non-empty"
  [[ -s "${MAINTENANCE_APPROVAL}" ]] \
    || fail "maintenance approval is required and must be non-empty"

  command -v "${PYTHON_BIN}" >/dev/null 2>&1 \
    || fail "Python is required to verify git-filter-repo's installed version"
  git filter-repo -h >/dev/null 2>&1 \
    || fail "git-filter-repo is unavailable"

  local actual_version
  actual_version="$(${PYTHON_BIN} -c 'from importlib.metadata import version; print(version("git-filter-repo"))')"
  version_at_least "${actual_version}" "${MIN_FILTER_REPO_VERSION}" \
    || fail "git-filter-repo ${MIN_FILTER_REPO_VERSION} or newer is required"

  {
    printf 'git_filter_repo_version=%s\n' "${actual_version}"
    printf 'rotation_evidence_sha256=%s\n' "$(sha256sum "${ROTATION_EVIDENCE}" | awk '{print $1}')"
    printf 'maintenance_approval_sha256=%s\n' "$(sha256sum "${MAINTENANCE_APPROVAL}" | awk '{print $1}')"
  } >> "${EVIDENCE_DIR}/rewrite-metadata.txt"
}

execute_rewrite() {
  local -a args=(--sensitive-data-removal --invert-paths)
  local path
  for path in "${TARGET_PATHS[@]}"; do
    args+=(--path "${path}")
  done

  (
    cd "${MIRROR_PATH}"
    git filter-repo "${args[@]}"
  )

  capture_inventory "post"
  diff -u "${EVIDENCE_DIR}/pre-refs.tsv" "${EVIDENCE_DIR}/post-refs.tsv" \
    > "${EVIDENCE_DIR}/ref-diff.patch" || true

  local remaining=0 count
  for path in "${TARGET_PATHS[@]}"; do
    count="$(git -C "${MIRROR_PATH}" log --all --format='%H' -- "${path}" | wc -l | tr -d ' ')"
    if [[ "${count}" != "0" ]]; then
      printf 'ERROR: target remains in history: %s (%s commits)\n' "${path}" "${count}" >&2
      remaining=1
    fi
  done
  [[ "${remaining}" == "0" ]] || fail "one or more target paths remain"

  local git_dir
  git_dir="$(git -C "${MIRROR_PATH}" rev-parse --absolute-git-dir)"
  if [[ -f "${git_dir}/filter-repo/changed-refs" ]]; then
    cp "${git_dir}/filter-repo/changed-refs" "${EVIDENCE_DIR}/filter-repo-changed-refs.txt"
  fi

  printf 'post_commit_count=%s\n' "$(git -C "${MIRROR_PATH}" rev-list --all --count)" \
    >> "${EVIDENCE_DIR}/rewrite-metadata.txt"
}

hash_evidence() {
  (
    cd "${EVIDENCE_DIR}"
    find . -maxdepth 1 -type f ! -name evidence-sha256.txt -print0 \
      | LC_ALL=C sort -z \
      | xargs -0 sha256sum > evidence-sha256.txt
  )
}

main() {
  parse_args "$@"
  validate_boundaries

  local origin_url
  origin_url="$(git -C "${MIRROR_PATH}" remote get-url origin)"
  capture_inventory "pre"
  write_plan_metadata "${origin_url}"

  if [[ "${EXECUTE}" == true ]]; then
    validate_execution_inputs
    execute_rewrite
    hash_evidence
    printf 'Local mirror rewrite completed. NO REMOTE PUSH WAS PERFORMED.\n'
    printf 'Stop for independent evidence review and explicit force-push approval.\n'
  else
    hash_evidence
    printf 'Inventory complete. No history was changed and no remote push was performed.\n'
  fi
}

main "$@"
