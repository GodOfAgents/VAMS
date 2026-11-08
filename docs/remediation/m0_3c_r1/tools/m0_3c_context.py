"""Production custom-error execution-context proof for M0.3c.

This module is used only by the adjudicator.  The independent semantic oracle
implements its own parser, target catalog, graph walk, and selector oracle.
"""
from __future__ import annotations

from collections import deque
import hashlib
from pathlib import PurePosixPath
import re

from Crypto.Hash import keccak


class ContextError(RuntimeError):
    pass


ERROR_POLICY = {
    "ERC20InsufficientBalance": ("contracts/interfaces/draft-IERC6093.sol", "interface", "IERC20Errors", "ERC20InsufficientBalance(address,uint256,uint256)"),
    "ERC20InsufficientAllowance": ("contracts/interfaces/draft-IERC6093.sol", "interface", "IERC20Errors", "ERC20InsufficientAllowance(address,uint256,uint256)"),
    "ERC20InvalidReceiver": ("contracts/interfaces/draft-IERC6093.sol", "interface", "IERC20Errors", "ERC20InvalidReceiver(address)"),
    "ERC20InvalidSpender": ("contracts/interfaces/draft-IERC6093.sol", "interface", "IERC20Errors", "ERC20InvalidSpender(address)"),
    "ERC721InvalidOwner": ("contracts/interfaces/draft-IERC6093.sol", "interface", "IERC721Errors", "ERC721InvalidOwner(address)"),
    "ERC721IncorrectOwner": ("contracts/interfaces/draft-IERC6093.sol", "interface", "IERC721Errors", "ERC721IncorrectOwner(address,uint256,address)"),
    "ERC721InvalidReceiver": ("contracts/interfaces/draft-IERC6093.sol", "interface", "IERC721Errors", "ERC721InvalidReceiver(address)"),
    "ERC721InsufficientApproval": ("contracts/interfaces/draft-IERC6093.sol", "interface", "IERC721Errors", "ERC721InsufficientApproval(address,uint256)"),
    "ERC721InvalidOperator": ("contracts/interfaces/draft-IERC6093.sol", "interface", "IERC721Errors", "ERC721InvalidOperator(address)"),
    "ERC1155InsufficientBalance": ("contracts/interfaces/draft-IERC6093.sol", "interface", "IERC1155Errors", "ERC1155InsufficientBalance(address,uint256,uint256,uint256)"),
    "ERC1155InvalidReceiver": ("contracts/interfaces/draft-IERC6093.sol", "interface", "IERC1155Errors", "ERC1155InvalidReceiver(address)"),
    "ERC1155MissingApprovalForAll": ("contracts/interfaces/draft-IERC6093.sol", "interface", "IERC1155Errors", "ERC1155MissingApprovalForAll(address,address)"),
    "ERC1155InvalidOperator": ("contracts/interfaces/draft-IERC6093.sol", "interface", "IERC1155Errors", "ERC1155InvalidOperator(address)"),
    "ERC6909InsufficientBalance": ("contracts/token/ERC6909/ERC6909.sol", "contract", "ERC6909", "ERC6909InsufficientBalance(address,uint256,uint256,uint256)"),
    "ERC6909InsufficientAllowance": ("contracts/token/ERC6909/ERC6909.sol", "contract", "ERC6909", "ERC6909InsufficientAllowance(address,uint256,uint256,uint256)"),
    "ERC6909InvalidReceiver": ("contracts/token/ERC6909/ERC6909.sol", "contract", "ERC6909", "ERC6909InvalidReceiver(address)"),
    "ERC6909InvalidSpender": ("contracts/token/ERC6909/ERC6909.sol", "contract", "ERC6909", "ERC6909InvalidSpender(address)"),
    "ERC1363InvalidReceiver": ("contracts/token/ERC20/utils/ERC1363Utils.sol", "library", "ERC1363Utils", "ERC1363InvalidReceiver(address)"),
    "ERC1363InvalidSpender": ("contracts/token/ERC20/utils/ERC1363Utils.sol", "library", "ERC1363Utils", "ERC1363InvalidSpender(address)"),
    "ERC1363ApproveFailed": ("contracts/token/ERC20/extensions/ERC1363.sol", "contract", "ERC1363", "ERC1363ApproveFailed(address,uint256)"),
    "ERC3156InvalidReceiver": ("contracts/token/ERC20/extensions/ERC20FlashMint.sol", "contract", "ERC20FlashMint", "ERC3156InvalidReceiver(address)"),
    "ERC3156ExceededMaxLoan": ("contracts/token/ERC20/extensions/ERC20FlashMint.sol", "contract", "ERC20FlashMint", "ERC3156ExceededMaxLoan(uint256)"),
    "ERC2612InvalidSigner": ("contracts/token/ERC20/extensions/ERC20Permit.sol", "contract", "ERC20Permit", "ERC2612InvalidSigner(address,address)"),
    "ERC20ExceededSafeSupply": ("contracts/token/ERC20/extensions/ERC20Votes.sol", "contract", "ERC20Votes", "ERC20ExceededSafeSupply(uint256,uint256)"),
    "ERC2981InvalidDefaultRoyalty": ("contracts/token/common/ERC2981.sol", "contract", "ERC2981", "ERC2981InvalidDefaultRoyalty(uint256,uint256)"),
    "ERC2981InvalidDefaultRoyaltyReceiver": ("contracts/token/common/ERC2981.sol", "contract", "ERC2981", "ERC2981InvalidDefaultRoyaltyReceiver(address)"),
}

# Each tuple is (test caller path, deployed artifact).  Behavior files bind all
# callers that execute the shared suite, rather than inferring safety from the
# behavior filename.
TARGETS = {
    "test/token/ERC20/ERC20.behavior.js": (
        ("test/token/ERC20/ERC20.test.js", "$ERC20"),
        ("test/token/ERC20/ERC20.test.js", "$ERC20ApprovalMock"),
        ("test/token/ERC20/extensions/draft-ERC20Bridgeable.test.js", "$ERC20BridgeableMock"),
        ("test/token/ERC20/extensions/ERC1363.test.js", "$ERC1363"),
        ("test/token/ERC20/extensions/draft-ERC20TemporaryApproval.test.js", "$ERC20TemporaryApproval"),
        ("test/token/ERC20/extensions/ERC20Wrapper.test.js", "$ERC20Wrapper"),
    ),
    "test/token/ERC721/ERC721.behavior.js": (
        ("test/token/ERC721/ERC721.test.js", "$ERC721"),
        ("test/token/ERC721/ERC721Enumerable.test.js", "$ERC721Enumerable"),
        ("test/token/ERC721/extensions/ERC721Wrapper.test.js", "$ERC721Wrapper"),
    ),
    "test/token/ERC1155/ERC1155.behavior.js": (("test/token/ERC1155/ERC1155.test.js", "$ERC1155"),),
    "test/token/ERC6909/ERC6909.behavior.js": (
        ("test/token/ERC6909/ERC6909.test.js", "$ERC6909"),
        ("test/token/ERC6909/extensions/ERC6909TokenSupply.test.js", "$ERC6909TokenSupply"),
    ),
    "test/token/common/ERC2981.behavior.js": (("test/token/ERC721/extensions/ERC721Royalty.test.js", "$ERC721Royalty"),),
    "test/token/ERC20/ERC20.test.js": (
        ("test/token/ERC20/ERC20.test.js", "$ERC20"),
        ("test/token/ERC20/ERC20.test.js", "$ERC20ApprovalMock"),
    ),
    "test/token/ERC20/extensions/ERC1363.test.js": (("test/token/ERC20/extensions/ERC1363.test.js", "$ERC1363"),),
    "test/token/ERC20/extensions/ERC20Burnable.test.js": (("test/token/ERC20/extensions/ERC20Burnable.test.js", "$ERC20Burnable"),),
    "test/token/ERC20/extensions/ERC20FlashMint.test.js": (("test/token/ERC20/extensions/ERC20FlashMint.test.js", "$ERC20FlashMintMock"),),
    "test/token/ERC20/extensions/ERC20Permit.test.js": (("test/token/ERC20/extensions/ERC20Permit.test.js", "$ERC20Permit"),),
    "test/token/ERC20/extensions/ERC20Votes.test.js": (
        ("test/token/ERC20/extensions/ERC20Votes.test.js", "$ERC20Votes"),
        ("test/token/ERC20/extensions/ERC20Votes.test.js", "$ERC20VotesTimestampMock"),
    ),
    "test/token/ERC20/extensions/ERC20Wrapper.test.js": (("test/token/ERC20/extensions/ERC20Wrapper.test.js", "$ERC20Wrapper"),),
    "test/token/ERC20/extensions/draft-ERC20TemporaryApproval.test.js": (("test/token/ERC20/extensions/draft-ERC20TemporaryApproval.test.js", "$ERC20TemporaryApproval"),),
    "test/token/ERC20/utils/SafeERC20.test.js": (("test/token/ERC20/utils/SafeERC20.test.js", "$ERC1363"),),
    "test/token/ERC721/extensions/ERC721Burnable.test.js": (("test/token/ERC721/extensions/ERC721Burnable.test.js", "$ERC721Burnable"),),
    "test/token/ERC721/extensions/ERC721Consecutive.test.js": (("test/token/ERC721/extensions/ERC721Consecutive.test.js", "$ERC721ConsecutiveMock"),),
    "test/token/ERC721/extensions/ERC721Wrapper.test.js": (("test/token/ERC721/extensions/ERC721Wrapper.test.js", "$ERC721Wrapper"),),
    "test/token/ERC1155/ERC1155.test.js": (("test/token/ERC1155/ERC1155.test.js", "$ERC1155"),),
    "test/token/ERC1155/extensions/ERC1155Burnable.test.js": (("test/token/ERC1155/extensions/ERC1155Burnable.test.js", "$ERC1155Burnable"),),
    "test/token/ERC6909/ERC6909.test.js": (("test/token/ERC6909/ERC6909.test.js", "$ERC6909"),),
    "test/governance/extensions/GovernorTimelockAccess.test.js": (
        ("test/governance/extensions/GovernorTimelockAccess.test.js", "$ERC20Votes"),
        ("test/governance/extensions/GovernorTimelockAccess.test.js", "$ERC20VotesTimestampMock"),
    ),
}


def _strip_noncode(data: bytes) -> str:
    text = data.decode("utf-8")
    out = list(text)
    i = 0
    state = "code"
    quote = ""
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if state == "code" and c == "/" and n in {"/", "*"}:
            state = "line" if n == "/" else "block"
            out[i] = out[i + 1] = " "
            i += 2
        elif state == "code" and c in {"'", '"'}:
            state, quote = "string", c
            out[i] = " "
            i += 1
        elif state == "line":
            if c == "\n":
                state = "code"
            else:
                out[i] = " "
            i += 1
        elif state == "block":
            if c == "*" and n == "/":
                out[i] = out[i + 1] = " "
                state = "code"
                i += 2
            else:
                if c != "\n":
                    out[i] = " "
                i += 1
        elif state == "string":
            if c == "\\":
                out[i] = " "
                if i + 1 < len(out):
                    out[i + 1] = " "
                i += 2
            elif c == quote:
                out[i] = " "
                state = "code"
                i += 1
            else:
                if c != "\n":
                    out[i] = " "
                i += 1
        else:
            i += 1
    if state in {"block", "string"}:
        raise ContextError("unterminated source token")
    return "".join(out)


def _container_graph(pinned: dict[str, bytes]):
    nodes = {}
    header = re.compile(r"\b(abstract\s+)?(contract|interface|library)\s+([A-Za-z_]\w*)(?:\s+is\s+([^\{]+))?\s*\{")
    for path, raw in pinned.items():
        if not path.startswith("contracts/") or not path.endswith(".sol"):
            continue
        code = _strip_noncode(raw)
        for match in header.finditer(code):
            depth = 1
            i = match.end()
            while i < len(code) and depth:
                depth += (code[i] == "{") - (code[i] == "}")
                i += 1
            if depth:
                raise ContextError("unbalanced Solidity container")
            name = match.group(3)
            if name in nodes:
                raise ContextError("ambiguous Solidity container")
            bases = []
            for item in (match.group(4) or "").split(","):
                base = re.match(r"\s*([A-Za-z_]\w*)", item)
                if base:
                    bases.append(base.group(1))
            nodes[name] = {
                "path": path,
                "kind": match.group(2),
                "bases": bases,
                "body": code[match.end():i - 1],
            }
    for name, node in nodes.items():
        libraries = sorted(other for other, target in nodes.items() if target["kind"] == "library" and re.search(rf"\b{re.escape(other)}\s*[.]", node["body"]))
        node["edges"] = list(dict.fromkeys(node["bases"] + libraries))
    return nodes


def _declared_signature(body: str, error: str) -> str | None:
    match = re.search(rf"\berror\s+{re.escape(error)}\s*\(([^)]*)\)\s*;", body)
    if not match:
        return None
    types = []
    for raw in match.group(1).split(","):
        raw = raw.strip()
        if not raw:
            continue
        parts = [p for p in raw.split() if p not in {"memory", "calldata", "storage", "payable"}]
        if not parts:
            return None
        value_type = parts[0]
        if "payable" in raw and value_type == "address":
            value_type = "address"
        types.append(value_type)
    return f"{error}({','.join(types)})"


def _chain(nodes, start: str, owner: str, error: str):
    queue = deque([(start, [start])])
    seen = set()
    matches = []
    declarations = []
    while queue:
        current, path = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        node = nodes.get(current)
        if node and _declared_signature(node["body"], error) is not None:
            declarations.append(current)
        if current == owner:
            matches.append(path)
            continue
        if node:
            for child in node["edges"]:
                queue.append((child, path + [child]))
    if len(matches) != 1 or declarations != [owner]:
        raise ContextError("ambiguous or unreachable declaration owner")
    return matches[0]


def _assertion(data: bytes, line_number: int):
    lines = data.decode("utf-8").splitlines()
    if not 1 <= line_number <= len(lines):
        raise ContextError("invalid assertion line")
    match = re.fullmatch(
        r"\s*[.]to[.]be[.]revertedWithCustomError\((this[.][A-Za-z_]\w*),\s*(['\"`])(ERC[0-9]+[A-Za-z0-9_]+)\2\)\s*",
        lines[line_number - 1],
    )
    if not match:
        raise ContextError("invalid assertion")
    window = " ".join(lines[max(0, line_number - 16):line_number])
    before = window.rsplit(".to.be.revertedWithCustomError", 1)[0]
    expect = before.rsplit("await expect(", 1)
    if len(expect) != 2:
        raise ContextError("missing invocation")
    expression = expect[1]
    call_target = "this.token"
    dot = r"\s*[.]\s*"
    direct = re.search(
        rf"this{dot}([A-Za-z_]\w*)(?:{dot}connect\s*\([^)]*\))?"
        rf"(?:{dot}getFunction\s*\((['\"])([^'\"]+)\2\)|{dot}([$A-Za-z_]\w*)\s*\()",
        expression,
    )
    deployment = re.search(r"ethers\s*[.]\s*deployContract\s*\(", expression)
    alias = re.search(r"this[.]([A-Za-z_]\w*)\s*\(", expression)
    if direct:
        call_target = "this." + direct.group(1)
        operation = direct.group(3) or direct.group(4)
    elif deployment:
        call_target = "ethers"
        operation = "deployContract"
    elif alias and alias.group(1) in {"transfer", "approve"}:
        operation = alias.group(1)
    else:
        raise ContextError("unresolved invocation")
    if not re.fullmatch(r"[$A-Za-z_][A-Za-z0-9_$]*(?:\([A-Za-z0-9_,]+\))?", operation):
        raise ContextError("unsafe operation")
    return match.group(1), match.group(3), call_target, operation


def _artifact_present(caller_data: bytes, behavior_path: str, artifact: str, direct: bool):
    text = caller_data.decode("utf-8")
    if artifact not in text:
        return False
    if direct:
        return True
    behavior = PurePosixPath(behavior_path)
    return (
        (behavior.name in text or behavior.stem in text)
        and "shouldBehaveLike" in text
    )


def _selector(signature: str) -> str:
    value = keccak.new(digest_bits=256)
    value.update(signature.encode("ascii"))
    return value.hexdigest()[:8]


def build_index(pinned: dict[str, bytes]):
    return _container_graph(pinned)


def resolve_context(relative_path: str, data: bytes, line_number: int, pinned: dict[str, bytes], owned: dict[str, dict], nodes=None):
    assertion_target, error, call_target, operation = _assertion(data, line_number)
    policy = ERROR_POLICY.get(error)
    target_policy = TARGETS.get(relative_path)
    if policy is None or target_policy is None:
        raise ContextError("context policy unavailable")
    if relative_path == "test/token/ERC20/utils/SafeERC20.test.js":
        if error == "ERC1363InvalidReceiver":
            target_policy = ((relative_path, "$ERC1363"),)
        elif error == "ERC1363ApproveFailed":
            target_policy = ((relative_path, "$ERC1363ReturnFalseOnERC20Mock"),)
        else:
            raise ContextError("unsupported SafeERC20 context")
    nodes = build_index(pinned) if nodes is None else nodes
    owner_path, owner_kind, owner_name, expected_signature = policy
    owner = nodes.get(owner_name)
    if not owner or owner["path"] != owner_path or owner["kind"] != owner_kind:
        raise ContextError("declaration owner mismatch")
    signature = _declared_signature(owner["body"], error)
    if signature != expected_signature:
        raise ContextError("declaration signature mismatch")
    execution_targets = []
    chains = []
    for caller_path, artifact in target_policy:
        caller = pinned.get(caller_path)
        if caller is None or not _artifact_present(caller, relative_path, artifact, caller_path == relative_path):
            raise ContextError("execution target not proven")
        container = artifact.removeprefix("$")
        if container not in nodes:
            raise ContextError("execution target container unavailable")
        names = _chain(nodes, container, owner_name, error)
        execution_targets.append({
            "artifact": artifact,
            "caller_path": caller_path,
            "caller_sha256": hashlib.sha256(caller).hexdigest(),
            "caller_object_id": owned[caller_path]["object_id"],
        })
        chains.append({
            "artifact": artifact,
            "containers": [
                {"name": name, "kind": nodes[name]["kind"], "path": nodes[name]["path"]}
                for name in names
            ],
        })
    owner_data = pinned[owner_path]
    return {
        "kind": "custom_error_execution",
        "assertion_target": assertion_target,
        "call_target": call_target,
        "invoked_operation": operation,
        "error_name": error,
        "error_signature": signature,
        "error_selector": _selector(signature),
        "declaration_owner": {
            "name": owner_name,
            "kind": owner_kind,
            "path": owner_path,
            "source_sha256": hashlib.sha256(owner_data).hexdigest(),
            "source_object_id": owned[owner_path]["object_id"],
        },
        "execution_targets": sorted(execution_targets, key=lambda x: (x["caller_path"], x["artifact"])),
        "reachability_chains": sorted(chains, key=lambda x: x["artifact"]),
    }
