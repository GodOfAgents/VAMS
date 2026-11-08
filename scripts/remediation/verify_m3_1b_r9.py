#!/usr/bin/env python3
"""M3.1b-R11 closed Aiken dependency/source provenance verifier."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import tomllib
from pathlib import Path
from typing import Any, Iterable

MANIFEST_NAME = "aiken-dependency-manifest.json"
EXPECTED_SCHEMA = "m3.1b-r11-dependency-manifest-v1"
R3_SCHEMA = "m3.2b-r3-dependency-manifest-v1"
EXPECTED_MANIFEST_VERSION = 3
R3_MANIFEST_VERSION = 4
R4_MANIFEST_VERSION = 5
F04_MANIFEST_VERSION = 6
F04_SCHEMA = "m3-f04-option-b-forward-v1"
M7_MANIFEST_VERSION = 7
M7_SCHEMA = "m7-f05-current-forward-v1"
M7_APPROVED_COMMITS = {
    "aiken-lang/fuzz": "06874926ec70747f3fc4e2b9364ee9e1393441cc",
    "aiken-lang/stdlib": "33376da0c274e41f52e69e4769a0e7878a24efba",
}
F04_BASELINE = "m3-f04-option-b-r1"
F04_HISTORICAL_LOCK = "8fc8bf1ccf3cf0c91acc94232646ebabb23469eb7c2d4acb1f4f0b0b67f8213b"
DEFAULT_AIKEN = Path("/home/GodOfAgents/vams-evidence/toolchains/aiken-1.1.21/aiken")
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOOL_BYTES = 256 * 1024 * 1024
MAX_FILES = 20_000
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
PACKAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*$")
DIR_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SOURCE_ROOTS = ("lib", "validators")
PROJECT_INPUTS = ("aiken.toml", "aiken.lock", "build/packages/packages.toml")
MANIFEST_KEYS = {"schema_version", "manifest_version", "compiler", "project", "compilation_sources", "project_inputs", "package_cache", "dependencies", "blueprint", "volatile_lock_fields"}
R3_MANIFEST_KEYS = MANIFEST_KEYS | {"forward_provenance"}
DEP_KEYS = {"name", "version", "requirement", "source", "repository", "revision", "revision_kind", "integrity", "package_dir", "package_tree_sha256", "package_file_count", "files"}
FILE_KEYS = {"path", "type", "size", "sha256"}
LOCK_TIMESTAMP_FIELDS = ("secs_since_epoch", "nanos_since_epoch")
LOCK_TIMESTAMP_RE = re.compile(rb"(?P<prefix>(?:secs_since_epoch|nanos_since_epoch) = )(?P<value>[0-9]+)")


class VerificationError(RuntimeError):
    pass


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_pairs_no_duplicates)
    except (OSError, UnicodeError, ValueError) as exc:
        raise VerificationError(f"invalid JSON: {path.name}") from exc


def _expect_keys(value: Any, expected: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise VerificationError(f"unexpected {label} fields")


def _strict_int(value: Any) -> bool:
    return type(value) is int


def _validate_hash(value: Any, label: str) -> None:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise VerificationError(f"malformed {label}")


def _regular_stat(path: Path, max_bytes: int = MAX_FILE_BYTES) -> os.stat_result:
    try:
        value = path.lstat()
    except OSError as exc:
        raise VerificationError(f"unreadable file: {path.name}") from exc
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise VerificationError(f"unsafe source file: {path.name}")
    if value.st_size > max_bytes:
        raise VerificationError(f"file is too large: {path.name}")
    return value


def _hash_file(path: Path, max_bytes: int = MAX_FILE_BYTES) -> str:
    _regular_stat(path, max_bytes)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise VerificationError(f"unreadable file: {path.name}") from exc
    try:
        value = os.fstat(fd)
        if stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode) or value.st_nlink != 1 or value.st_size > max_bytes:
            raise VerificationError(f"unsafe source file: {path.name}")
        digest = hashlib.sha256()
        while block := os.read(fd, 1024 * 1024):
            digest.update(block)
        return digest.hexdigest()
    finally:
        os.close(fd)


def _read_file(path: Path, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    _regular_stat(path, max_bytes)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise VerificationError(f"unreadable file: {path.name}") from exc
    try:
        value = os.fstat(fd)
        if stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode) or value.st_nlink != 1 or value.st_size > max_bytes:
            raise VerificationError(f"unsafe source file: {path.name}")
        data = bytearray()
        while block := os.read(fd, 1024 * 1024):
            data.extend(block)
        return bytes(data)
    finally:
        os.close(fd)


def _walk_regular(root: Path) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise VerificationError(f"unsafe directory: {root.name}")
    files: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                path = Path(entry.path)
                if entry.is_symlink():
                    raise VerificationError(f"symlink is not allowed: {path.name}")
                if entry.is_dir(follow_symlinks=False):
                    stack.append(path)
                elif entry.is_file(follow_symlinks=False):
                    _regular_stat(path)
                    files.append(path)
                else:
                    raise VerificationError(f"special file is not allowed: {path.name}")
                if len(files) > MAX_FILES:
                    raise VerificationError("file-count limit exceeded")
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def _tree_digest(root: Path) -> tuple[str, int]:
    records = []
    for path in _walk_regular(root):
        rel = path.relative_to(root).as_posix()
        records.append(f"{rel}\0{path.stat().st_size}\0{_hash_file(path)}\n")
    return hashlib.sha256("".join(records).encode()).hexdigest(), len(records)


def _safe_relative(value: Any, label: str, allow_slash: bool = True) -> str:
    if not isinstance(value, str) or not value or not value.isascii() or "\\" in value or "\x00" in value:
        raise VerificationError(f"unsafe {label}")
    path = Path(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise VerificationError(f"unsafe {label}")
    if not allow_slash and len(path.parts) != 1:
        raise VerificationError(f"unsafe {label}")
    if any(not re.fullmatch(r"[A-Za-z0-9._-]+", part) for part in path.parts):
        raise VerificationError(f"unsafe {label}")
    return value


def _validate_package_name(value: Any) -> str:
    if not isinstance(value, str) or not PACKAGE_RE.fullmatch(value):
        raise VerificationError("unsafe dependency identifier")
    return value


def _validate_file_records(records: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(records, list) or not records:
        raise VerificationError(f"{label} must be non-empty")
    paths: list[str] = []
    for record in records:
        _expect_keys(record, FILE_KEYS, f"{label} file")
        path = _safe_relative(record["path"], f"{label} path")
        if record["type"] != "regular" or not _strict_int(record["size"]) or record["size"] < 0:
            raise VerificationError(f"malformed {label} file")
        _validate_hash(record["sha256"], f"{label} file hash")
        paths.append(path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise VerificationError(f"unordered or duplicate {label} files")
    return records


def validate_manifest(path: Path) -> dict[str, Any]:
    manifest = _read_json(path)
    if not isinstance(manifest, dict) or not _strict_int(manifest.get("manifest_version")):
        raise VerificationError("unsupported manifest schema")
    if manifest["manifest_version"] in (R3_MANIFEST_VERSION, R4_MANIFEST_VERSION, F04_MANIFEST_VERSION, M7_MANIFEST_VERSION):
        _expect_keys(manifest, R3_MANIFEST_KEYS, "manifest")
        expected_schema = M7_SCHEMA if manifest["manifest_version"] == M7_MANIFEST_VERSION else (F04_SCHEMA if manifest["manifest_version"] == F04_MANIFEST_VERSION else R3_SCHEMA)
        if manifest["schema_version"] != expected_schema:
            raise VerificationError("unsupported manifest schema")
        forward = manifest["forward_provenance"]
        _expect_keys(forward, {"baseline", "historical_r1_raw_lock_sha256", "current_canonical_raw_lock_sha256", "raw_lock_continuity", "allowed_volatile_fields", "isolated_build_policy", "network"}, "forward provenance")
        allowed_baselines = ("m3.2b-r3", "m3-f04-r3", F04_BASELINE)
        if forward["baseline"] not in allowed_baselines or forward["raw_lock_continuity"] != "historically unresolved; R1 bytes unavailable" or forward["network"] != "disabled":
            raise VerificationError("invalid forward provenance baseline")
        if manifest["manifest_version"] in (F04_MANIFEST_VERSION, M7_MANIFEST_VERSION) and (forward["baseline"] != F04_BASELINE or forward["historical_r1_raw_lock_sha256"] != F04_HISTORICAL_LOCK):
            raise VerificationError("invalid F04 forward reset attribution")
        _validate_hash(forward["historical_r1_raw_lock_sha256"], "historical lock hash")
        _validate_hash(forward["current_canonical_raw_lock_sha256"], "current lock hash")
        if forward["allowed_volatile_fields"] != ["etags.*[0].secs_since_epoch", "etags.*[0].nanos_since_epoch"]:
            raise VerificationError("unexpected forward volatile lock fields")
    else:
        _expect_keys(manifest, MANIFEST_KEYS, "manifest")
        if manifest["schema_version"] != EXPECTED_SCHEMA or manifest["manifest_version"] != EXPECTED_MANIFEST_VERSION:
            raise VerificationError("unsupported manifest schema")
    _expect_keys(manifest["compiler"], {"version", "binary_sha256"}, "compiler")
    if manifest["compiler"]["version"] != "v1.1.21":
        raise VerificationError("unsupported compiler version")
    _validate_hash(manifest["compiler"]["binary_sha256"], "compiler hash")
    _expect_keys(manifest["project"], {"aiken_toml_path", "aiken_toml_sha256", "lock_path", "lock_sha256", "lock_normalized_sha256"}, "project")
    if manifest["project"]["aiken_toml_path"] != "aiken.toml" or manifest["project"]["lock_path"] != "aiken.lock":
        raise VerificationError("unexpected project paths")
    _validate_hash(manifest["project"]["aiken_toml_sha256"], "aiken.toml hash")
    _validate_hash(manifest["project"]["lock_sha256"], "lock hash")
    _validate_hash(manifest["project"]["lock_normalized_sha256"], "normalized lock hash")
    if manifest["manifest_version"] in (F04_MANIFEST_VERSION, M7_MANIFEST_VERSION) and manifest["forward_provenance"]["current_canonical_raw_lock_sha256"] != manifest["project"]["lock_sha256"]:
        raise VerificationError("forward reset lock binding mismatch")
    if manifest["volatile_lock_fields"] != ["etags.*[0].secs_since_epoch", "etags.*[0].nanos_since_epoch"]:
        raise VerificationError("unexpected volatile lock fields")
    sources = manifest["compilation_sources"]
    if not isinstance(sources, list) or not sources:
        raise VerificationError("missing compilation sources")
    source_paths = []
    for record in sources:
        _expect_keys(record, {"path", "size", "sha256"}, "compilation source")
        rel = _safe_relative(record["path"], "compilation source path")
        if not rel.endswith(".ak") or not rel.split("/", 1)[0] in SOURCE_ROOTS:
            raise VerificationError("unexpected compilation source path")
        if not _strict_int(record["size"]) or record["size"] < 0:
            raise VerificationError("malformed compilation source")
        _validate_hash(record["sha256"], "compilation source hash")
        source_paths.append(rel)
    if source_paths != sorted(source_paths) or len(source_paths) != len(set(source_paths)):
        raise VerificationError("unordered or duplicate compilation sources")
    inputs = manifest["project_inputs"]
    if not isinstance(inputs, list) or len(inputs) != len(PROJECT_INPUTS):
        raise VerificationError("malformed project inputs")
    for record in inputs:
        _expect_keys(record, FILE_KEYS, "project input")
        _safe_relative(record["path"], "project input path")
        if record["type"] != "regular" or not _strict_int(record["size"]) or record["size"] < 0:
            raise VerificationError("malformed project input")
        _validate_hash(record["sha256"], "project input hash")
    if [record["path"] for record in inputs] != list(PROJECT_INPUTS):
        raise VerificationError("unexpected project input ordering")
    cache = manifest["package_cache"]
    _expect_keys(cache, {"root", "index", "directories"}, "package cache")
    if cache["root"] != "build/packages" or not isinstance(cache["index"], dict):
        raise VerificationError("unexpected package cache paths")
    _expect_keys(cache["index"], {"path", "sha256", "packages"}, "package index")
    if cache["index"]["path"] != "build/packages/packages.toml":
        raise VerificationError("unexpected package index path")
    _validate_hash(cache["index"]["sha256"], "package index hash")
    index_packages = cache["index"]["packages"]
    if not isinstance(index_packages, list):
        raise VerificationError("malformed package index")
    canonical_index = []
    for item in index_packages:
        _expect_keys(item, {"name", "version", "source"}, "package index item")
        _validate_package_name(item["name"])
        if not all(isinstance(item[k], str) and item[k] for k in ("version", "source")):
            raise VerificationError("malformed package index item")
        canonical_index.append(item)
    if canonical_index != sorted(canonical_index, key=lambda x: (x["name"], x["version"], x["source"])):
        raise VerificationError("unordered package index")
    if len({item["name"] for item in canonical_index}) != len(canonical_index):
        raise VerificationError("duplicate package index item")
    deps = manifest["dependencies"]
    if not isinstance(deps, list) or not deps:
        raise VerificationError("missing dependencies")
    names = []
    for dep in deps:
        _expect_keys(dep, DEP_KEYS, "dependency")
        name = _validate_package_name(dep["name"])
        names.append(name)
        if not isinstance(dep["version"], str) or not dep["version"] or dep["requirement"] != [] or dep["source"] != "github":
            raise VerificationError(f"malformed dependency: {name}")
        if dep["repository"] != "https://github.com/" + name or dep["revision"] != dep["version"]:
            raise VerificationError(f"unexpected dependency revision: {name}")
        if manifest["schema_version"] == M7_SCHEMA:
            if dep["revision_kind"] != "commit" or dep["revision"] != M7_APPROVED_COMMITS.get(name):
                raise VerificationError(f"unverified dependency commit: {name}")
        elif dep["revision_kind"] != "tag":
            raise VerificationError(f"unexpected dependency revision: {name}")
        if not isinstance(dep["package_dir"], str) or not DIR_RE.fullmatch(dep["package_dir"]):
            raise VerificationError(f"unsafe package directory: {name}")
        if dep["package_dir"] != name.replace("/", "-"):
            raise VerificationError(f"ambiguous package directory: {name}")
        _validate_hash(dep["integrity"], f"{name} integrity")
        _validate_hash(dep["package_tree_sha256"], f"{name} package hash")
        if not _strict_int(dep["package_file_count"]) or dep["package_file_count"] <= 0:
            raise VerificationError(f"invalid package file count: {name}")
        _validate_file_records(dep["files"], name)
        if dep["package_file_count"] != len(dep["files"]):
            raise VerificationError(f"package file count mismatch: {name}")
    if names != sorted(names) or len(names) != len(set(names)):
        raise VerificationError("unordered or duplicate dependencies")
    if canonical_index != [{"name": d["name"], "version": d["version"], "source": d["source"]} for d in deps]:
        raise VerificationError("package index does not match dependencies")
    dirs = cache["directories"]
    expected_dirs = [d["package_dir"] for d in deps]
    if dirs != expected_dirs or len(dirs) != len(set(dirs)):
        raise VerificationError("package directory topology mismatch")
    _expect_keys(manifest["blueprint"], {"path", "sha256", "programs"}, "blueprint")
    if manifest["blueprint"]["path"] != "plutus.json":
        raise VerificationError("unexpected blueprint path")
    _validate_hash(manifest["blueprint"]["sha256"], "blueprint hash")
    programs = manifest["blueprint"]["programs"]
    if not isinstance(programs, list) or not programs:
        raise VerificationError("missing blueprint programs")
    titles = []
    for program in programs:
        _expect_keys(program, {"title", "sha256"}, "blueprint program")
        if not isinstance(program["title"], str) or not program["title"]:
            raise VerificationError("malformed blueprint program")
        _validate_hash(program["sha256"], "blueprint program hash")
        titles.append(program["title"])
    expected_program_count = 26 if manifest["manifest_version"] == M7_MANIFEST_VERSION else (22 if manifest["manifest_version"] in (R4_MANIFEST_VERSION, F04_MANIFEST_VERSION) else (21 if manifest["manifest_version"] == R3_MANIFEST_VERSION else 11))
    if titles != sorted(titles) or len(titles) != len(set(titles)) or len(titles) != expected_program_count:
        raise VerificationError("invalid blueprint program set")
    return manifest


def _parse_lock_bytes(data: bytes) -> dict[str, Any]:
    if b"\r" in data or not data.endswith(b"\n") or data.endswith(b"\n\n") or any(line.endswith((b" ", b"\t")) for line in data.splitlines()):
        raise VerificationError("invalid lockfile: aiken.lock")
    try:
        lock = tomllib.loads(data.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise VerificationError("invalid lockfile: aiken.lock") from exc
    if set(lock) != {"requirements", "packages", "etags"} or not isinstance(lock["requirements"], list) or not isinstance(lock["packages"], list):
        raise VerificationError("unexpected lockfile structure")
    for item in lock["requirements"]:
        _expect_keys(item, {"name", "version", "source"}, "lock requirement")
        _validate_package_name(item["name"])
    for item in lock["packages"]:
        _expect_keys(item, {"name", "version", "requirements", "source"}, "lock package")
        _validate_package_name(item["name"])
        if not isinstance(item["requirements"], list) or not all(isinstance(v, str) for v in item["requirements"]):
            raise VerificationError("malformed package requirements")
    if not isinstance(lock["etags"], dict):
        raise VerificationError("malformed lock etags")
    for key, value in lock["etags"].items():
        if not isinstance(key, str) or not isinstance(value, list) or len(value) != 2:
            raise VerificationError("malformed lock etag")
        timestamp, integrity = value
        _expect_keys(timestamp, {"secs_since_epoch", "nanos_since_epoch"}, "lock timestamp")
        if not all(_strict_int(timestamp[field]) and timestamp[field] >= 0 for field in timestamp):
            raise VerificationError("malformed lock timestamp")
        _validate_hash(integrity, f"{key} integrity")
    return lock


def parse_lock(path: Path) -> dict[str, Any]:
    return _parse_lock_bytes(_read_file(path))


def normalized_lock_digest(path: Path) -> str:
    data = _read_file(path)
    lock = _parse_lock_bytes(data)
    expected_occurrences = len(lock["etags"]) * len(LOCK_TIMESTAMP_FIELDS)
    matches = list(LOCK_TIMESTAMP_RE.finditer(data))
    if len(matches) != expected_occurrences:
        raise VerificationError("unrecognized lock timestamp encoding")
    normalized = LOCK_TIMESTAMP_RE.sub(lambda match: match.group("prefix") + b"0", data)
    return hashlib.sha256(normalized).hexdigest()


def _parse_project(path: Path) -> list[dict[str, str]]:
    try:
        project = tomllib.loads(_read_file(path).decode())
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise VerificationError("invalid aiken.toml") from exc
    deps = project.get("dependencies")
    if not isinstance(deps, list):
        raise VerificationError("missing project dependencies")
    result = []
    for dep in deps:
        _expect_keys(dep, {"name", "version", "source"}, "project dependency")
        _validate_package_name(dep["name"])
        if not all(isinstance(dep[k], str) and dep[k] for k in ("version", "source")):
            raise VerificationError("malformed project dependency")
        result.append(dep)
    return sorted(result, key=lambda x: (x["name"], x["version"], x["source"]))


def _parse_package_index(path: Path) -> list[dict[str, str]]:
    try:
        value = tomllib.loads(_read_file(path).decode())
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise VerificationError("invalid package index") from exc
    if set(value) != {"packages"} or not isinstance(value["packages"], list):
        raise VerificationError("unexpected package index fields")
    result = []
    for item in value["packages"]:
        _expect_keys(item, {"name", "version", "source"}, "package index item")
        _validate_package_name(item["name"])
        if not all(isinstance(item[k], str) and item[k] for k in ("version", "source")):
            raise VerificationError("malformed package index item")
        result.append(item)
    result.sort(key=lambda x: (x["name"], x["version"], x["source"]))
    if len({item["name"] for item in result}) != len(result):
        raise VerificationError("duplicate package index item")
    return result


def semantic_projection(lock: dict[str, Any]) -> dict[str, Any]:
    return {"requirements": sorted((i["name"], i["version"], i["source"]) for i in lock["requirements"]), "packages": sorted((i["name"], i["version"], tuple(i["requirements"]), i["source"]) for i in lock["packages"]), "etags": {key: value[1] for key, value in sorted(lock["etags"].items())}}


def manifest_projection(manifest: dict[str, Any]) -> dict[str, Any]:
    return {"requirements": sorted((d["name"], d["version"], d["source"]) for d in manifest["dependencies"]), "packages": sorted((d["name"], d["version"], tuple(d["requirement"]), d["source"]) for d in manifest["dependencies"]), "etags": {f'{d["name"]}@{d["version"]}': d["integrity"] for d in manifest["dependencies"]}}


def validate_semantic_lock(lock: dict[str, Any], manifest: dict[str, Any]) -> None:
    if semantic_projection(lock) != manifest_projection(manifest):
        raise VerificationError("lock semantic projection does not match manifest")


def _program_map(doc: dict[str, Any]) -> dict[str, str]:
    validators = doc.get("validators")
    if not isinstance(validators, list):
        raise VerificationError("blueprint validators missing")
    result: dict[str, str] = {}
    for validator in validators:
        if not isinstance(validator, dict):
            raise VerificationError("malformed blueprint validator")
        title, compiled = validator.get("title"), validator.get("compiledCode")
        if not isinstance(title, str) or not isinstance(compiled, str) or title in result:
            raise VerificationError("malformed or duplicate blueprint validator")
        try:
            result[title] = hashlib.sha256(bytes.fromhex(compiled)).hexdigest()
        except ValueError as exc:
            raise VerificationError(f"malformed compiled program: {title}") from exc
    return result


def verify_blueprint(authoritative: Path, generated: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if _hash_file(authoritative) != manifest["blueprint"]["sha256"] or _hash_file(generated) != manifest["blueprint"]["sha256"]:
        raise VerificationError("blueprint hash mismatch")
    auth = _program_map(_read_json(authoritative)); built = _program_map(_read_json(generated))
    expected = {p["title"]: p["sha256"] for p in manifest["blueprint"]["programs"]}
    if auth != built or auth != expected:
        raise VerificationError("blueprint or compiled-program drift")
    return {"sha256": manifest["blueprint"]["sha256"], "program_count": len(built), "program_hashes": built}


def _discover_sources(cardano: Path) -> list[dict[str, Any]]:
    result = []
    for root_name in SOURCE_ROOTS:
        root = cardano / root_name
        if not root.is_dir() or root.is_symlink():
            raise VerificationError(f"missing source root: {root_name}")
        for path in _walk_regular(root):
            rel = path.relative_to(cardano).as_posix()
            if path.suffix == ".ak":
                result.append({"path": rel, "size": path.stat().st_size, "sha256": _hash_file(path)})
    return sorted(result, key=lambda x: x["path"])


def _verify_package_cache(cardano: Path, manifest: dict[str, Any]) -> dict[str, list[Any]]:
    cache = cardano / manifest["package_cache"]["root"]
    if cache.is_symlink() or not cache.is_dir():
        raise VerificationError("missing package cache")
    expected_dirs = set(manifest["package_cache"]["directories"])
    actual = {entry.name for entry in cache.iterdir()}
    if actual != expected_dirs | {"packages.toml"}:
        raise VerificationError("package cache topology mismatch")
    index_path = cache / "packages.toml"
    if _hash_file(index_path) != manifest["package_cache"]["index"]["sha256"] or _parse_package_index(index_path) != manifest["package_cache"]["index"]["packages"]:
        raise VerificationError("package index drift")
    result = {}
    for dep in manifest["dependencies"]:
        package = cache / dep["package_dir"]
        if package.is_symlink() or not package.is_dir():
            raise VerificationError(f"missing package directory: {dep['name']}")
        actual_files = _walk_regular(package)
        actual_paths = [p.relative_to(package).as_posix() for p in actual_files]
        expected_files = [p["path"] for p in dep["files"]]
        if actual_paths != expected_files:
            raise VerificationError(f"package file set drift: {dep['name']}")
        for path, expected in zip(actual_files, dep["files"]):
            if path.stat().st_size != expected["size"] or _hash_file(path) != expected["sha256"]:
                raise VerificationError(f"package file drift: {dep['name']}/{expected['path']}")
        tree, count = _tree_digest(package)
        if tree != dep["package_tree_sha256"] or count != dep["package_file_count"]:
            raise VerificationError(f"dependency package hash mismatch: {dep['name']}")
        result[dep["name"]] = [tree, count]
    return result


def _input_snapshot(cardano: Path, manifest: dict[str, Any], *, normalized_lock: bool = False) -> dict[str, str]:
    paths = [s["path"] for s in manifest["compilation_sources"]] + [p["path"] for p in manifest["project_inputs"]]
    for dep in manifest["dependencies"]:
        paths.extend(f"{manifest['package_cache']['root']}/{dep['package_dir']}/{f['path']}" for f in dep["files"])
    result = {}
    for path in sorted(set(paths)):
        result[path] = normalized_lock and path == "aiken.lock" and normalized_lock_digest(cardano / path) or _hash_file(cardano / path)
    return result


def validate_repository_inputs(repo_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    repo = repo_root.resolve(); cardano = repo / "cardano"
    if _hash_file(cardano / "aiken.toml") != manifest["project"]["aiken_toml_sha256"] or _hash_file(cardano / "aiken.lock") != manifest["project"]["lock_sha256"] or normalized_lock_digest(cardano / "aiken.lock") != manifest["project"]["lock_normalized_sha256"]:
        raise VerificationError("authoritative project hash mismatch")
    source_actual = _discover_sources(cardano)
    if source_actual != manifest["compilation_sources"]:
        raise VerificationError("compilation source set or digest mismatch")
    inputs = {p["path"]: p for p in manifest["project_inputs"]}
    for path, expected in inputs.items():
        value = cardano / path
        if _hash_file(value) != expected["sha256"] or value.stat().st_size != expected["size"]:
            raise VerificationError(f"project input drift: {path}")
    if _parse_project(cardano / "aiken.toml") != manifest["package_cache"]["index"]["packages"]:
        raise VerificationError("aiken.toml dependency drift")
    lock = parse_lock(cardano / "aiken.lock"); validate_semantic_lock(lock, manifest)
    if _parse_package_index(cardano / "build/packages/packages.toml") != manifest["package_cache"]["index"]["packages"]:
        raise VerificationError("package index does not match project")
    packages = _verify_package_cache(cardano, manifest)
    blueprint = verify_blueprint(cardano / "plutus.json", cardano / "plutus.json", manifest)
    return {"source_file_count": len(source_actual), "source_manifest_sha256": hashlib.sha256(json.dumps({x["path"]: x["sha256"] for x in source_actual}, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "dependency_packages": packages, "blueprint": blueprint}


def _copy_file(source: Path, target: Path, expected: str) -> None:
    data = _read_file(source)
    if hashlib.sha256(data).hexdigest() != expected:
        raise VerificationError(f"source changed during copy: {source.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    if _hash_file(target) != expected:
        raise VerificationError(f"copy verification failed: {source.name}")


def _copy_project(cardano: Path, manifest: dict[str, Any], target: Path) -> None:
    records = [(x["path"], x["sha256"]) for x in manifest["compilation_sources"]] + [(x["path"], x["sha256"]) for x in manifest["project_inputs"]]
    for dep in manifest["dependencies"]:
        records.extend((f"{manifest['package_cache']['root']}/{dep['package_dir']}/{f['path']}", f["sha256"]) for f in dep["files"])
    for rel, digest in records:
        _copy_file(cardano / rel, target / rel, digest)


def _isolated_env(cardano: Path, aiken: Path) -> dict[str, str]:
    home = cardano / ".home"; tmp = cardano / ".tmp"; cache = cardano / ".cache"; config = cardano / ".config"
    for path in (home, tmp, cache, config): path.mkdir()
    return {"PATH": str(aiken.parent), "HOME": str(home), "TMPDIR": str(tmp), "XDG_CACHE_HOME": str(cache), "XDG_CONFIG_HOME": str(config), "AIKEN_NO_NETWORK": "1", "LC_ALL": "C", "LANG": "C"}


def _run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=300, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise VerificationError("Aiken command could not be executed") from exc


def _verify_tool(aiken: Path, manifest: dict[str, Any]) -> Path:
    resolved = aiken.resolve()
    if resolved != DEFAULT_AIKEN.resolve():
        raise VerificationError("unapproved Aiken executable path")
    if _hash_file(resolved, MAX_TOOL_BYTES) != manifest["compiler"]["binary_sha256"]:
        raise VerificationError("Aiken binary hash mismatch")
    result = _run([str(resolved), "--version"], resolved.parent, {"PATH": str(resolved.parent), "LC_ALL": "C", "LANG": "C"})
    if result.returncode or not result.stdout.startswith("aiken " + manifest["compiler"]["version"]):
        raise VerificationError("Aiken version mismatch")
    return resolved


def verify_repository(repo_root: Path, aiken_path: Path) -> dict[str, Any]:
    repo = repo_root.resolve(); manifest = validate_manifest(repo / "cardano" / MANIFEST_NAME)
    resolved = _verify_tool(aiken_path, manifest)
    baseline = validate_repository_inputs(repo, manifest)
    before = _input_snapshot(repo / "cardano", manifest, normalized_lock=True)
    with tempfile.TemporaryDirectory(prefix="m3-r11-aiken-") as temp:
        cardano = Path(temp) / "cardano"; cardano.mkdir()
        _copy_project(repo / "cardano", manifest, cardano)
        env = _isolated_env(cardano, resolved)
        check = _run([str(resolved), "check"], cardano, env)
        if check.returncode:
            raise VerificationError("Aiken check failed")
        validate_semantic_lock(parse_lock(cardano / "aiken.lock"), manifest)
        build = _run([str(resolved), "build"], cardano, env)
        if build.returncode:
            raise VerificationError("Aiken build failed")
        validate_semantic_lock(parse_lock(cardano / "aiken.lock"), manifest)
        temp_inputs = _input_snapshot(cardano, manifest, normalized_lock=True)
        if temp_inputs != before:
            raise VerificationError("isolated compilation input drift")
        packages = _verify_package_cache(cardano, manifest)
        blueprint = verify_blueprint(repo / "cardano/plutus.json", cardano / "plutus.json", manifest)
    after = _input_snapshot(repo / "cardano", manifest, normalized_lock=True)
    if before != after or _hash_file(repo / "cardano/aiken.lock") != manifest["project"]["lock_sha256"]:
        raise VerificationError("authoritative Cardano source changed during verification")
    return {"ok": True, **baseline, "dependency_packages": packages, "check_exit": check.returncode, "build_exit": build.returncode, "blueprint": blueprint}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2]); parser.add_argument("--aiken", type=Path, default=DEFAULT_AIKEN); parser.add_argument("--output", type=Path); args = parser.parse_args(argv)
    try: result = verify_repository(args.repo_root, args.aiken)
    except VerificationError as exc: print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True)); return 1
    encoded = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output: args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end=""); return 0


if __name__ == "__main__":
    raise SystemExit(main())
