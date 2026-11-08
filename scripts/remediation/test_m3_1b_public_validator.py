#!/usr/bin/env python3
"""Evaluate M3.1b fixtures through the fully applied Plutus V3 entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


def con(index, *fields):
    return ("con", index, list(fields))


def integer(value):
    return ("int", value)


def byte_string(value):
    return ("bytes", bytes.fromhex(value) if isinstance(value, str) else value)


def listing(*items):
    return ("list", list(items))


def mapping(*pairs):
    return ("map", list(pairs))


def uplc(data):
    kind = data[0]
    if kind == "con":
        return f"Constr {data[1]} [{', '.join(uplc(x) for x in data[2])}]"
    if kind == "int":
        return f"I {data[1]}"
    if kind == "bytes":
        return f"B #{data[1].hex()}"
    if kind == "list":
        return f"List [{', '.join(uplc(x) for x in data[1])}]"
    if kind == "map":
        return "Map [" + ", ".join(f"({uplc(k)}, {uplc(v)})" for k, v in data[1]) + "]"
    raise ValueError(kind)


def _head(major, value):
    if value < 24:
        return bytes([(major << 5) | value])
    if value < 256:
        return bytes([(major << 5) | 24, value])
    if value < 65536:
        return bytes([(major << 5) | 25]) + value.to_bytes(2, "big")
    if value < 2**32:
        return bytes([(major << 5) | 26]) + value.to_bytes(4, "big")
    return bytes([(major << 5) | 27]) + value.to_bytes(8, "big")


def _tag(value):
    return _head(6, value)


def cbor(data):
    kind = data[0]
    if kind == "int":
        value = data[1]
        if 0 <= value < 2**64:
            return _head(0, value)
        if -2**64 <= value < 0:
            return _head(1, -1 - value)
        magnitude = abs(value if value >= 0 else value + 1)
        raw = magnitude.to_bytes((magnitude.bit_length() + 7) // 8, "big")
        return _tag(2 if value >= 0 else 3) + _head(2, len(raw)) + raw
    if kind == "bytes":
        return _head(2, len(data[1])) + data[1]
    if kind == "list":
        return b"\x80" if not data[1] else b"\x9f" + b"".join(cbor(x) for x in data[1]) + b"\xff"
    if kind == "map":
        return b"\xa0" if not data[1] else b"\xbf" + b"".join(cbor(k) + cbor(v) for k, v in data[1]) + b"\xff"
    if kind == "con":
        index, fields = data[1], data[2]
        encoded_fields = b"\x80" if not fields else b"\x9f" + b"".join(cbor(x) for x in fields) + b"\xff"
        if index < 7:
            return _tag(121 + index) + encoded_fields
        if index < 128:
            return _tag(1280 + index - 7) + encoded_fields
        return _tag(102) + _head(4, 2) + cbor(integer(index)) + encoded_fields
    raise ValueError(kind)


POLICY = "11" * 28
OTHER_POLICY = "22" * 28
STATE_NAME = "VAMS_INSURANCE_STATE".encode().hex()
G1, G2, G3 = "aa" * 28, "bb" * 28, "cc" * 28
CLAIMANT, EVIDENCE = "dd" * 28, "ee" * 32
TXID = "01" * 32
BALANCE, CLAIM_AMOUNT = 20_000_000, 4_000_000
START, EXPIRY = 1_700_000_000_000, 1_700_604_800_000
MAX_INTERVAL = 300_000
EXPECTED_PARAMETER_TITLES = ("genesis_ref", "state_asset_name", "configured_guardians", "configured_threshold", "configured_policy_epoch", "configured_max_payout_bps")
EXPECTED_SCHEMA_DIGEST = "c78bc241904d20320b9ce74bbbdcd0892f7da0c905e1b5a68373a78508b3f251"
EXPECTED_COMPILED_SHA256 = "4bdefcf0731c54e39b1cf97d29c06d465cd7e503a6f524f4d486dcd5309f0e38"


def none(): return con(1)
def some(value): return con(0, value)
def boolean(value): return con(1 if value else 0)
def credential(script, digest): return con(1 if script else 0, byte_string(digest))
def address(script, digest): return con(0, credential(script, digest), none())
def out_ref(index): return con(0, byte_string(TXID), integer(index))


def value(lovelace, extra_assets=1, state=True, state_name=STATE_NAME):
    policies = [(byte_string(""), mapping((byte_string(""), integer(lovelace))))]
    if state:
        policies.append((byte_string(POLICY), mapping((byte_string(state_name), integer(1)))))
    if extra_assets:
        assets = tuple((byte_string(index.to_bytes(2, "big")), integer(1)) for index in range(1, extra_assets + 1))
        policies.append((byte_string(OTHER_POLICY), mapping(*assets)))
    return mapping(*policies)


def guardians(count=3):
    known = [G1, G2, G3]
    return [known[i] if i < len(known) else (i + 1).to_bytes(28, "big").hex() for i in range(count)]


def payout_address(staked=False, claimant=CLAIMANT):
    return con(0, credential(False, claimant), some(con(0, credential(False, claimant))) if staked else none())


def claim(nonce=0, approvers=(), epoch=7, staked=False, claimant=CLAIMANT, evidence=EVIDENCE, state_name=STATE_NAME):
    payload = con(
        0, byte_string(b"VAMS_INSURANCE_CLAIM_V2"), byte_string(POLICY),
        byte_string(state_name), integer(epoch), integer(nonce), byte_string(claimant),
        payout_address(staked, claimant), integer(CLAIM_AMOUNT), byte_string(evidence), integer(START), integer(EXPIRY),
    )
    claim_id = hashlib.blake2b(cbor(payload), digest_size=32).digest()
    return con(
        0, byte_string(claim_id), integer(nonce), byte_string(claimant), payout_address(staked, claimant),
        integer(CLAIM_AMOUNT), byte_string(evidence), integer(START), integer(EXPIRY),
        integer(epoch), listing(*(byte_string(x) for x in approvers)),
    )


def datum(balance=BALANCE, nonce=0, claims=(), guardian_count=3, threshold=2, epoch=7, payout_bps=5000, schema_version=2):
    return con(
        0, integer(schema_version), integer(balance), integer(nonce), listing(*claims), integer(epoch),
        integer(payout_bps), integer(threshold), listing(*(byte_string(x) for x in guardians(guardian_count))),
    )


def malformed_datum_without_schema():
    return con(
        0, integer(BALANCE), integer(0), listing(), integer(7), integer(5000),
        integer(2), listing(*(byte_string(x) for x in guardians(3))),
    )


def output(addr, output_value, output_datum=None):
    encoded_datum = con(0) if output_datum is None else con(2, output_datum)
    return con(0, addr, output_value, encoded_datum, none())


def tx(inputs, outputs, minted, signers, lower, upper):
    lower_bound = con(0, con(1, integer(lower)) if lower is not None else con(0), boolean(True))
    upper_bound = con(0, con(1, integer(upper)) if upper is not None else con(2), boolean(True))
    return con(
        0, listing(*inputs), listing(), listing(*outputs), integer(0), minted, listing(), mapping(),
        con(0, lower_bound, upper_bound), listing(*(byte_string(x) for x in signers)), mapping(),
        mapping(), byte_string("00" * 32), mapping(), listing(), none(), none(),
    )


def input_(index, addr, input_value, input_datum=None):
    return con(0, out_ref(index), output(addr, input_value, input_datum))


def submit_redeemer(nonce=0, claimant=CLAIMANT, evidence=EVIDENCE, payout=None):
    return con(1, integer(nonce), byte_string(claimant), payout_address(claimant=claimant) if payout is None else payout, integer(CLAIM_AMOUNT), byte_string(evidence))


def deposit_redeemer():
    return con(0, integer(5_000_000), byte_string("ab" * 64), byte_string("cd" * 32))


def spend_context(before, after, redeemer, signers=(), lower=START, upper=START + 1, extras=(), input_padding=0, output_padding=0, extra_assets=1, worst_positions=False, state_name=STATE_NAME):
    state_addr = address(True, POLICY)
    own = input_(0, state_addr, value(before[2][1][1], extra_assets, state_name=state_name), before)
    padding_in = [input_(100 + i, address(False, G3), value(2_000_000, 0, False)) for i in range(input_padding)]
    fund_balance = after[2][1][1]
    continuing = output(state_addr, value(fund_balance, extra_assets, state_name=state_name), after)
    padding_out = [output(address(False, G3), value(2_000_000, 0, False)) for _ in range(output_padding)]
    inputs = [*padding_in, own] if worst_positions else [own, *padding_in]
    outputs = [*padding_out, *extras, continuing] if worst_positions else [continuing, *extras, *padding_out]
    transaction = tx(inputs, outputs, mapping(), signers, lower, upper)
    return con(0, transaction, redeemer, con(1, out_ref(0), some(before)))


def genesis_context(guardian_count=3, lower=START, upper=START + 300_000, input_padding=0, output_padding=0, extra_assets=1):
    state_addr = address(True, POLICY)
    initial = datum(guardian_count=guardian_count)
    seed = input_(9, address(False, G1), value(2_000_000, 0, False))
    padding_in = [input_(100 + i, address(False, G3), value(2_000_000, 0, False)) for i in range(input_padding)]
    fund = output(state_addr, value(BALANCE, extra_assets), initial)
    padding_out = [output(address(False, G3), value(2_000_000, 0, False)) for _ in range(output_padding)]
    minted = mapping((byte_string(POLICY), mapping((byte_string(STATE_NAME), integer(1)))))
    transaction = tx([seed, *padding_in], [fund, *padding_out], minted, (), lower, upper)
    return con(0, transaction, con(0), con(0, byte_string(POLICY)))


class Evaluator:
    def __init__(self, aiken: Path, blueprint: Path):
        self.aiken = aiken
        doc = json.loads(blueprint.read_text())
        validators = {v.get("title"): v for v in doc.get("validators", [])}
        required = {
            "insurance_fund.insurance_fund.mint",
            "insurance_fund.insurance_fund.spend",
            "insurance_fund.insurance_fund.else",
        }
        if set(validators) & required != required:
            raise RuntimeError("blueprint is missing an insurance entrypoint")
        entries = [validators[name] for name in sorted(required)]
        compiled = [entry.get("compiledCode") for entry in entries]
        if not all(isinstance(code, str) and code for code in compiled) or len(set(compiled)) != 1:
            raise RuntimeError("insurance blueprint compiled bytes are stale or inconsistent")
        for entry in entries:
            titles = tuple(item.get("title") for item in entry.get("parameters", []))
            if titles != EXPECTED_PARAMETER_TITLES:
                raise RuntimeError("insurance blueprint parameter order drift")
        mint = validators["insurance_fund.insurance_fund.mint"]
        spend = validators["insurance_fund.insurance_fund.spend"]
        if mint.get("redeemer", {}).get("schema", {}).get("$ref") != "#/definitions/vams~1types~1InsuranceStateRedeemer":
            raise RuntimeError("insurance mint redeemer schema drift")
        if spend.get("datum", {}).get("schema", {}).get("$ref") != "#/definitions/vams~1types~1FundDatumV2":
            raise RuntimeError("insurance datum schema drift")
        if spend.get("redeemer", {}).get("schema", {}).get("$ref") != "#/definitions/vams~1types~1InsuranceFundRedeemer":
            raise RuntimeError("insurance spend redeemer schema drift")
        schema_keys = ("vams/types/FundDatumV2", "vams/types/ClaimRecord", "vams/types/InsuranceFundRedeemer", "vams/types/InsuranceStateRedeemer")
        schema = {key: doc.get("definitions", {}).get(key) for key in schema_keys}
        digest = hashlib.sha256(json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if digest != EXPECTED_SCHEMA_DIGEST:
            raise RuntimeError("insurance blueprint schema drift")
        self.compiled = bytes.fromhex(compiled[0])
        if hashlib.sha256(self.compiled).hexdigest() != EXPECTED_COMPILED_SHA256:
            raise RuntimeError("stale insurance blueprint bytes")

    def evaluate(self, context, guardian_count=3, threshold=2, state_asset_name=STATE_NAME):
        params = [out_ref(9), byte_string(state_asset_name), listing(*(byte_string(x) for x in guardians(guardian_count))), integer(threshold), integer(7), integer(5000), context]
        with tempfile.TemporaryDirectory(prefix="m3-public-") as folder:
            folder = Path(folder)
            code = folder / "validator.cbor"
            code.write_bytes(self.compiled)
            decoded = subprocess.run([str(self.aiken), "uplc", "decode", "-c", str(code)], text=True, capture_output=True, check=True).stdout
            prefix = "(program\n  1.1.0\n"
            if not decoded.startswith(prefix) or not decoded.endswith("\n)\n"):
                raise RuntimeError("unexpected decoded UPLC wrapper")
            term = decoded[len(prefix):-2]
            for argument in params:
                term = f"[ {term} (con data ({uplc(argument)})) ]"
            program = folder / "applied.uplc"
            program.write_text(prefix + term + "\n)\n")
            run = subprocess.run([str(self.aiken), "uplc", "eval", "-d", str(program)], text=True, capture_output=True)
            stdout = run.stdout.strip()
            payload = json.JSONDecoder().raw_decode(stdout)[0] if stdout.startswith("{") else {}
            payload["context_cbor_bytes"] = len(cbor(context))
            payload["script_cbor_bytes"] = len(self.compiled)
            if run.stderr.strip():
                payload["evaluation_error"] = " | ".join(run.stderr.strip().splitlines()[:24])
            return run.returncode == 0 and payload.get("result", "").replace("\n", " ").strip() == "(con unit ())", payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aiken", required=True, type=Path)
    parser.add_argument("--blueprint", required=True, type=Path)
    parser.add_argument("--only", action="append", default=None)
    args = parser.parse_args()
    evaluator = Evaluator(args.aiken, args.blueprint)

    approved = claim()
    two_approved = claim(approvers=(G1, G2))
    payout = output(payout_address(), value(CLAIM_AMOUNT, 0, False))
    valid_submit = spend_context(datum(), datum(nonce=1, claims=(approved,)), submit_redeemer(), signers=(CLAIMANT,))
    valid_approve = spend_context(datum(nonce=1, claims=(approved,)), datum(nonce=1, claims=(claim(approvers=(G1,)),)), con(2, approved[2][0]), signers=(G1,))
    valid_payout = spend_context(datum(nonce=1, claims=(two_approved,)), datum(balance=BALANCE - CLAIM_AMOUNT, nonce=1), con(3, two_approved[2][0]), extras=(payout,))
    valid_cancel = spend_context(datum(nonce=1, claims=(approved,)), datum(nonce=1), con(4, approved[2][0]), signers=(CLAIMANT,))
    valid_expire = spend_context(datum(nonce=1, claims=(approved,)), datum(nonce=1), con(5, approved[2][0]), lower=EXPIRY, upper=EXPIRY + 1)

    retained = spend_context(datum(nonce=1, claims=(two_approved,)), datum(balance=BALANCE - CLAIM_AMOUNT, nonce=1, claims=(two_approved,)), con(3, two_approved[2][0]), extras=(payout,))
    duplicate = spend_context(datum(nonce=1, claims=(claim(approvers=(G1,)),)), datum(nonce=1, claims=(claim(approvers=(G1, G1)),)), con(2, approved[2][0]), signers=(G1,))
    mutations = {
        "guardian_mutation": datum(nonce=1, claims=(approved,), guardian_count=4, threshold=2),
        "threshold_mutation": datum(nonce=1, claims=(approved,), threshold=1),
        "payout_cap_mutation": datum(nonce=1, claims=(approved,), payout_bps=4000),
        "policy_epoch_mutation": datum(nonce=1, epoch=8),
    }
    full = tuple(guardians(5))
    first_full = claim(0, full)
    second_full = claim(1, full)
    pending_at = spend_context(
        datum(nonce=1, claims=(claim(0),)),
        datum(nonce=2, claims=(claim(0), claim(1))),
        submit_redeemer(1), signers=(CLAIMANT,),
    )
    pending_above = spend_context(
        datum(nonce=2, claims=(claim(0), claim(1))),
        datum(nonce=3, claims=(claim(0), claim(1), claim(2))),
        submit_redeemer(2), signers=(CLAIMANT,),
    )
    approver_below_claim = claim(approvers=tuple(guardians(4)))
    approver_at_claim = claim(approvers=full)
    approver_above_claim = claim(approvers=(*full, "99" * 28))
    max_common = {"input_padding": 15, "output_padding": 15, "extra_assets": 15, "worst_positions": True}
    max_submit = spend_context(
        datum(nonce=1, claims=(first_full,), guardian_count=5),
        datum(nonce=2, claims=(first_full, claim(1)), guardian_count=5),
        submit_redeemer(1), signers=(CLAIMANT, *full), **max_common,
    )
    target_four = claim(0, tuple(guardians(4)))
    max_approve = spend_context(
        datum(nonce=2, claims=(second_full, target_four), guardian_count=5),
        datum(nonce=2, claims=(second_full, first_full), guardian_count=5),
        con(2, target_four[2][0]), signers=(guardians(5)[4],), **max_common,
    )
    max_payout = spend_context(
        datum(nonce=2, claims=(first_full, second_full), guardian_count=5),
        datum(balance=BALANCE - CLAIM_AMOUNT, nonce=2, claims=(first_full,), guardian_count=5),
        con(3, second_full[2][0]), extras=(payout,), output_padding=14,
        input_padding=15, extra_assets=15, worst_positions=True,
    )
    max_cancel = spend_context(
        datum(nonce=2, claims=(first_full, second_full), guardian_count=5),
        datum(nonce=2, claims=(first_full,), guardian_count=5),
        con(4, second_full[2][0]), signers=(CLAIMANT,), **max_common,
    )
    max_expire = spend_context(
        datum(nonce=2, claims=(first_full, second_full), guardian_count=5),
        datum(nonce=2, claims=(first_full,), guardian_count=5),
        con(5, second_full[2][0]), lower=EXPIRY, upper=EXPIRY + 1, **max_common,
    )
    datum_size_cases = {}
    sized_first = claim(0, full, staked=True)
    sized_second = claim(1, full, staked=True)
    for label, integer_bytes in (("below", 10), ("at", 11), ("above", 12)):
        large_balance = 1 << (8 * (integer_bytes - 1))
        sized_before = datum(balance=large_balance, nonce=2, claims=(sized_first, sized_second), guardian_count=5)
        sized_length = len(cbor(sized_before))
        expected_size = {"below": 895, "at": 896, "above": 897}[label]
        assert sized_length == expected_size, (label, sized_length)
        sized_after = datum(balance=large_balance, nonce=2, claims=(sized_first,), guardian_count=5)
        datum_size_cases[f"datum_bytes_{label}"] = (
            spend_context(sized_before, sized_after, con(4, sized_second[2][0]), signers=(CLAIMANT,)),
            label != "above",
        )
    cases = {
        "genesis_valid": (genesis_context(), True),
        "genesis_interval_below": (genesis_context(upper=START + 299_999), True),
        "genesis_interval_at": (genesis_context(upper=START + 300_000), True),
        "genesis_interval_above": (genesis_context(upper=START + 300_001), False),
        "genesis_unbounded_lower": (genesis_context(lower=None), False),
        "genesis_unbounded_upper": (genesis_context(upper=None), False),
        "genesis_reversed": (genesis_context(lower=START + 1, upper=START), False),
        "submit_valid": (valid_submit, True),
        "pending_claims_at": (pending_at, True),
        "pending_claims_above": (pending_above, False),
        "submit_missing_signature": (spend_context(datum(), datum(nonce=1, claims=(approved,)), submit_redeemer()), False),
        "approve_valid": (valid_approve, True),
        "approve_duplicate_actual_state": (duplicate, False),
        "payout_valid": (valid_payout, True),
        "payout_retains_claim": (retained, False),
        "cancel_valid": (valid_cancel, True),
        "expire_valid": (valid_expire, True),
        "guardians_below": (genesis_context(guardian_count=4), True),
        "guardians_at": (genesis_context(guardian_count=5), True),
        "guardians_above": (genesis_context(guardian_count=6), False),
        "inputs_below": (genesis_context(input_padding=14), True),
        "inputs_at": (genesis_context(input_padding=15), True),
        "inputs_above": (genesis_context(input_padding=16), False),
        "outputs_below": (genesis_context(output_padding=14), True),
        "outputs_at": (genesis_context(output_padding=15), True),
        "outputs_above": (genesis_context(output_padding=16), False),
        "assets_below": (genesis_context(extra_assets=14), True),
        "assets_at": (genesis_context(extra_assets=15), True),
        "assets_above": (genesis_context(extra_assets=16), False),
        "approvers_below": (spend_context(datum(nonce=1, claims=(approver_below_claim,), guardian_count=5), datum(nonce=1, guardian_count=5), con(4, approver_below_claim[2][0]), signers=(CLAIMANT,)), True),
        "approvers_at": (spend_context(datum(nonce=1, claims=(approver_at_claim,), guardian_count=5), datum(nonce=1, guardian_count=5), con(4, approver_at_claim[2][0]), signers=(CLAIMANT,)), True),
        "approvers_above": (spend_context(datum(nonce=1, claims=(approver_above_claim,), guardian_count=5), datum(nonce=1, guardian_count=5), con(4, approver_above_claim[2][0]), signers=(CLAIMANT,)), False),
        "budget_genesis_max": (genesis_context(guardian_count=5, input_padding=15, output_padding=15, extra_assets=15), True),
        "budget_submit_max": (max_submit, True),
        "budget_approve_max": (max_approve, True),
        "budget_payout_max": (max_payout, True),
        "budget_cancel_max": (max_cancel, True),
        "budget_expire_max": (max_expire, True),
    }
    # Independent control mutations: each context changes one reviewed field only.
    cases.update({
        "deposit_unconditionally_rejected": (
            spend_context(datum(), datum(), deposit_redeemer()), False
        ),
        "schema_version_mutation": (
            spend_context(datum(), datum(nonce=1, claims=(approved,), schema_version=3), submit_redeemer(), signers=(CLAIMANT,)), False
        ),
        "schema_version_missing": (
            spend_context(malformed_datum_without_schema(), datum(), submit_redeemer()), False
        ),
        "claimant_hash_length_mutation": (
            spend_context(datum(), datum(nonce=1, claims=(claim(claimant="dd" * 27),)), submit_redeemer(claimant="dd" * 27), signers=("dd" * 27,)), False
        ),
        "evidence_hash_length_mutation": (
            spend_context(datum(), datum(nonce=1, claims=(claim(evidence="ee" * 31),)), submit_redeemer(evidence="ee" * 31), signers=(CLAIMANT,)), False
        ),
        "state_asset_name_bound_mutation": (
            spend_context(datum(), datum(nonce=1, claims=(claim(state_name="00" * 33),)), submit_redeemer(), signers=(CLAIMANT,), state_name="00" * 33), False, "00" * 33
        ),
        "signer_duplicate_rejected": (
            spend_context(datum(), datum(nonce=1, claims=(approved,)), submit_redeemer(), signers=(CLAIMANT, CLAIMANT)), False
        ),
        "signer_count_above_bound_rejected": (
            spend_context(datum(), datum(nonce=1, claims=(approved,)), submit_redeemer(), signers=(*full, CLAIMANT, "99" * 28)), False
        ),
    })
    # Every enabled transition shares the finite five-minute contract.  The
    # deadline-specific predicates are kept inside their transition fixtures.
    interval_fixtures = {
        "submit": (datum(), datum(nonce=1, claims=(approved,)), submit_redeemer(), (CLAIMANT,), START, START + 1),
        "approve": (datum(nonce=1, claims=(approved,)), datum(nonce=1, claims=(claim(approvers=(G1,)),)), con(2, approved[2][0]), (G1,), START, START + 1),
        "payout": (datum(nonce=1, claims=(two_approved,)), datum(balance=BALANCE - CLAIM_AMOUNT, nonce=1), con(3, two_approved[2][0]), (), START, START + 1),
        "cancel": (datum(nonce=1, claims=(approved,)), datum(nonce=1), con(4, approved[2][0]), (CLAIMANT,), START, START + 1),
        "expire": (datum(nonce=1, claims=(approved,)), datum(nonce=1), con(5, approved[2][0]), (), EXPIRY, EXPIRY + 1),
    }
    for label, (before, after, redeemer, signers, lower, upper) in interval_fixtures.items():
        cases[f"{label}_interval_below"] = (spend_context(before, after, redeemer, signers=signers, lower=lower, upper=lower + MAX_INTERVAL - 1, extras=(payout,) if label == "payout" else ()), True)
        cases[f"{label}_interval_at"] = (spend_context(before, after, redeemer, signers=signers, lower=lower, upper=lower + MAX_INTERVAL, extras=(payout,) if label == "payout" else ()), True)
        cases[f"{label}_interval_above"] = (spend_context(before, after, redeemer, signers=signers, lower=lower, upper=lower + MAX_INTERVAL + 1, extras=(payout,) if label == "payout" else ()), False)
        cases[f"{label}_unbounded_lower"] = (spend_context(before, after, redeemer, signers=signers, lower=None, upper=upper, extras=(payout,) if label == "payout" else ()), False)
        cases[f"{label}_unbounded_upper"] = (spend_context(before, after, redeemer, signers=signers, lower=lower, upper=None, extras=(payout,) if label == "payout" else ()), False)
        cases[f"{label}_reversed"] = (spend_context(before, after, redeemer, signers=signers, lower=lower + 1, upper=lower, extras=(payout,) if label == "payout" else ()), False)
    for name, changed in mutations.items():
        if name == "policy_epoch_mutation":
            cases[name] = (
                spend_context(datum(nonce=1, claims=(approved,)), changed, con(4, approved[2][0]), signers=(CLAIMANT,)),
                False,
            )
        else:
            cases[name] = (spend_context(datum(), changed, submit_redeemer(), signers=(CLAIMANT,)), False)
    cases.update(datum_size_cases)
    if args.only:
        cases = {name: cases[name] for name in args.only}

    failures = []
    results = {}
    for name, entry in cases.items():
        context, expected = entry[:2]
        state_asset_name = entry[2] if len(entry) > 2 else STATE_NAME
        guardian_count = 5 if name.startswith("approvers_") or name.startswith("datum_bytes_") or name.startswith("budget_") and name != "budget_genesis_max" else {"guardians_below": 4, "guardians_at": 5, "guardians_above": 6, "budget_genesis_max": 5}.get(name, 3)
        accepted, payload = evaluator.evaluate(context, guardian_count=guardian_count, state_asset_name=state_asset_name)
        tx_fields = context[2][0][2]
        results[name] = {
            "accepted": accepted,
            "expected": expected,
            "cpu": payload.get("cpu"),
            "mem": payload.get("mem"),
            "context_cbor_bytes": payload.get("context_cbor_bytes"),
            "script_cbor_bytes": payload.get("script_cbor_bytes"),
            "input_count": len(tx_fields[0][1]),
            "output_count": len(tx_fields[2][1]),
            "extra_signatory_count": len(tx_fields[8][1]),
            "error": payload.get("evaluation_error"),
        }
        if accepted != expected:
            failures.append(name)
    print(json.dumps({"cases": results, "failed": failures}, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
