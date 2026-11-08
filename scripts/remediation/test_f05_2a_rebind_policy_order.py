"""Regression checks for synthetic F05 policy-ID rebinding and Value map order."""

import copy

import pytest

from scripts.remediation.test_f05_2a_authority_bootstrap_public import (
    AUTHORITY_NFT_NAME,
    _base_context,
    _rebind_policy_id,
    _set_output_value,
    _value,
    byte_string,
    integer,
    map_data,
)


EXTRA_ID = bytes.fromhex("ef" * 28)
OLD_ID = bytes.fromhex("dd" * 28)
UNRELATED_ID = bytes.fromhex("aa" * 28)


def _policy_pairs(value):
    return value["map"]


def _policy_keys(value):
    return [bytes.fromhex(pair["k"]["bytes"]) for pair in _policy_pairs(value)]


def _native_tokens(value):
    return {
        bytes.fromhex(pair["k"]["bytes"]): copy.deepcopy(pair["v"])
        for pair in _policy_pairs(value)
    }


@pytest.mark.parametrize("new_id", [bytes.fromhex("e0" * 28), bytes.fromhex("f0" * 28)])
def test_rebind_sorts_every_output_value_around_fixed_extra_policy(new_id):
    context = _base_context(
        OLD_ID, bytes.fromhex("77" * 28), bytes.fromhex("55" * 32), 0,
        [bytes.fromhex("11" * 32)], [],
    )
    # The authority output contains the fixed ef*28 extra-asset fixture.
    # The sponsor output contains an unrelated native asset too; both outputs
    # must retain canonical Value map order after a policy-ID replacement.
    _set_output_value(context, 0, _value(5_000_000, [
        (OLD_ID, AUTHORITY_NFT_NAME, 1), (EXTRA_ID, b"x", 1),
    ]))
    _set_output_value(context, 1, _value(6_000_000, [
        (OLD_ID, b"secondary", 2), (UNRELATED_ID, b"other", 3),
    ]))
    tx_fields = context["fields"][0]["fields"]
    before = [_native_tokens(output["fields"][1]) for output in tx_fields[2]["list"]]
    old_inner = [entry[OLD_ID] for entry in before]
    unrelated = [
        {key: val for key, val in entry.items() if key != OLD_ID}
        for entry in before
    ]
    _rebind_policy_id(context, OLD_ID, new_id)

    for index, output in enumerate(tx_fields[2]["list"]):
        value = output["fields"][1]
        keys = _policy_keys(value)
        assert keys == sorted(keys)
        assert len(keys) == len(set(keys))
        actual = _native_tokens(value)
        assert OLD_ID not in actual
        assert actual[new_id] == old_inner[index]
        assert {key: val for key, val in actual.items() if key != new_id} == unrelated[index]

    authority_keys = _policy_keys(tx_fields[2]["list"][0]["fields"][1])
    assert (authority_keys.index(new_id) < authority_keys.index(EXTRA_ID)) == (new_id < EXTRA_ID)


@pytest.mark.parametrize("new_id", [bytes.fromhex("e0" * 28), bytes.fromhex("f0" * 28)])
def test_rebind_updates_mint_and_purpose_without_changing_other_assets(new_id):
    context = _base_context(
        OLD_ID, bytes.fromhex("77" * 28), bytes.fromhex("55" * 32), 0,
        [bytes.fromhex("11" * 32)], [],
    )
    tx_fields = context["fields"][0]["fields"]
    mint = tx_fields[4]
    mint["map"].append({"k": byte_string(EXTRA_ID), "v": map_data([
        (byte_string(b"q"), integer(4)),
    ])})
    original = _native_tokens(mint)
    purpose_before = copy.deepcopy(context["fields"][2])
    _rebind_policy_id(context, OLD_ID, new_id)

    keys = _policy_keys(mint)
    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))
    actual = _native_tokens(mint)
    assert OLD_ID not in actual
    assert actual[new_id] == original[OLD_ID]
    assert actual[EXTRA_ID] == original[EXTRA_ID]
    assert context["fields"][2] == {"constructor": purpose_before["constructor"], "fields": [byte_string(new_id)]}
