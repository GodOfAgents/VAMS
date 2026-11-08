"""F05 ScriptContext address encoding at the synthetic harness boundary."""

from scripts.remediation.test_f05_2a_authority_bootstrap_public import _address, byte_string, constr


def test_enterprise_script_address_uses_none_stake_option():
    payment = bytes.fromhex("ab" * 28)
    assert _address(payment, script=True) == constr(
        0, constr(1, byte_string(payment)), constr(1)
    )


def test_base_script_address_uses_distinct_stake_hash():
    payment = bytes.fromhex("ab" * 28)
    stake = bytes.fromhex("cd" * 28)
    assert _address(payment, script=True, stake=stake) == constr(
        0, constr(1, byte_string(payment)),
        constr(0, constr(0, byte_string(stake))),
    )
    assert _address(payment, script=True, stake=stake) != _address(payment, script=True)


def test_enterprise_key_address_uses_none_stake_option():
    payment = bytes.fromhex("ef" * 28)
    assert _address(payment, script=False) == constr(
        0, constr(0, byte_string(payment)), constr(1)
    )
