"""Synthetic byte/value reference for proposed governance asset cases.

No Aiken predicate evaluation, signature, ledger, custody or execution authority.
All malformed identifiers are proposed v2 refinements of underspecified labels.
"""
from collections import Counter
import hashlib

def h(data):
    return hashlib.blake2b(data, digest_size=32).digest()

def vector(document, name):
    return next(row for row in document['asset_vectors'] if row['id'] == name)

def parts(golden):
    c, p = golden['fixture']['config'], golden['fixture']['proposal']
    raw = lambda name: bytes.fromhex(c[name])
    target = bytes.fromhex(p['target_domain'])
    items = [b'VAMS/proposal/v2\0', raw('authority_policy_id'),
        bytes.fromhex(vector(golden, 'authority_name')['digest_hex']), raw('proposal_policy_id'),
        p['epoch'].to_bytes(4, 'big'), p['nonce'].to_bytes(8, 'big'),
        bytes.fromhex(p['proposer']), bytes.fromhex(p['description_hash']),
        bytes.fromhex(p['action_hash']), bytes.fromhex(p['payload_hash']),
        bytes([len(target)]) + target, p['quorum'].to_bytes(8, 'big'), p['deadline'].to_bytes(8, 'big')]
    row = vector(golden, 'proposal_name')
    assert b''.join(items).hex() == row['preimage_hex']
    assert h(b''.join(items)).hex() == row['digest_hex']
    return items

def definitions(golden, timing):
    original = parts(golden)
    proposal = bytes.fromhex(vector(golden, 'proposal_name')['digest_hex'])
    intent_row = vector(timing, 'queued_alice_intent_upper')
    intent_preimage = bytes.fromhex(intent_row['preimage_hex'])
    assert intent_preimage.startswith(b'VAMS/intent/v2\0')
    assert h(intent_preimage).hex() == intent_row['digest_hex']
    specifications = [
        ('intent_legacy_domain', 'Replace only the intent v2 domain with v1 while retaining the upper-bound2100 payload'),
        ('proposal_legacy_domain', 'Replace only the proposal v2 domain with v1'),
        ('proposal_domain_without_nul', 'Omit the proposal domain terminal NUL'),
        ('proposal_authority_policy_substitution', 'Flip the final byte of the authority policy in the proposal preimage'),
        ('proposal_authority_asset_substitution', 'Flip the final byte of the authority singleton name in the preimage'),
        ('proposal_policy_substitution', 'Flip the final byte of the proposal policy in the preimage'),
        ('proposal_epoch_little_endian', 'Encode policy epoch2 as little-endian u32'),
        ('proposal_epoch_width8', 'Encode policy epoch2 as big-endian u64 instead of u32'),
        ('proposal_nonce_width4', 'Encode nonce0 as big-endian u32 instead of u64'),
        ('proposal_nonce_substitution', 'Hash nonce1 while the proposal datum retains nonce0'),
        ('proposal_proposer_substitution', 'Flip the final proposer hash byte in the preimage'),
        ('proposal_description_substitution', 'Flip the final description hash byte in the preimage'),
        ('proposal_action_substitution', 'Flip the final action hash byte in the preimage'),
        ('proposal_payload_substitution', 'Flip the final payload hash byte in the preimage'),
        ('proposal_target_substitution', 'Hash length-prefixed preprod/other while the datum retains preprod/test'),
        ('proposal_target_without_length', 'Omit the target-domain length byte'),
        ('proposal_target_wrong_length', 'Increase the target length prefix by one without adding data'),
        ('proposal_quorum_width4', 'Encode quorum10 as big-endian u32 instead of u64'),
        ('proposal_quorum_little_endian', 'Encode quorum10 as little-endian u64'),
        ('proposal_deadline_little_endian', 'Encode deadline2000 as little-endian u64'),
        ('proposal_deadline_width4', 'Encode deadline2000 as big-endian u32 instead of u64'),
        ('proposal_action_payload_swapped', 'Swap the action and payload hash positions'),
        ('proposal_authority_asset_omitted', 'Omit the32byte authority singleton name'),
        ('proposal_epoch_omitted', 'Omit the4byte policy epoch'),
        ('proposal_digest_truncated31', 'Truncate the correct proposal digest to31bytes'),
    ]
    rows = []
    flip = lambda value: value[:-1] + bytes([value[-1] ^ 1])
    for index, (name, description) in enumerate(specifications):
        value = list(original)
        if index == 0:
            preimage = b'VAMS/intent/v1\0' + intent_preimage[len(b'VAMS/intent/v2\0'):]
        else:
            if index == 1: value[0] = b'VAMS/proposal/v1\0'
            elif index == 2: value[0] = value[0][:-1]
            elif index in (3,4,5): value[index - 2] = flip(value[index - 2])
            elif index == 6: value[4] = int.from_bytes(value[4], 'big').to_bytes(4, 'little')
            elif index == 7: value[4] = int.from_bytes(value[4], 'big').to_bytes(8, 'big')
            elif index == 8: value[5] = int.from_bytes(value[5], 'big').to_bytes(4, 'big')
            elif index == 9: value[5] = (int.from_bytes(value[5], 'big') + 1).to_bytes(8, 'big')
            elif index in (10,11,12,13): value[index - 4] = flip(value[index - 4])
            elif index == 14: value[10] = bytes([len(b'preprod/other')]) + b'preprod/other'
            elif index == 15: value[10] = value[10][1:]
            elif index == 16: value[10] = bytes([value[10][0] + 1]) + value[10][1:]
            elif index == 17: value[11] = int.from_bytes(value[11], 'big').to_bytes(4, 'big')
            elif index == 18: value[11] = int.from_bytes(value[11], 'big').to_bytes(8, 'little')
            elif index == 19: value[12] = int.from_bytes(value[12], 'big').to_bytes(8, 'little')
            elif index == 20: value[12] = int.from_bytes(value[12], 'big').to_bytes(4, 'big')
            elif index == 21: value[8], value[9] = value[9], value[8]
            elif index == 22: value[2] = b''
            elif index == 23: value[4] = b''
            preimage = b''.join(value)
        malformed = h(preimage)[:31] if index == 24 else h(preimage)
        correct = bytes.fromhex(intent_row['digest_hex']) if index == 0 else proposal
        assert malformed != correct
        rows.append({'parent_id': f'asset_boundary_{index:02d}', 'index': index,
            'parent_transition': 'Queue' if index % 2 == 0 else 'Vote',
            'parent_reference': 'asset:intent_fixture_v1' if index == 0 else 'asset:proposal_fixture_v1',
            'definition': name, 'description': description, 'mutated_preimage_hex': preimage.hex(),
            'mutated_asset_hex': malformed.hex(), 'correct_asset_hex': correct.hex(),
            'asset_name_bytes': len(malformed), 'prestate': ('Existing valid proposal; wrong newly minted intent name'
                if index == 0 else 'Synthetic forged proposal identifier; no reachable-prestate provenance claim'),
            'amendment_status': 'PROPOSED_V2_REFINEMENT_REVIEW_PENDING',
            'native_status': 'NOT_RUN', 'ledger_status': 'NOT_RUN', 'budget_status': 'NOT_RUN',
            'acceptance_credit': False})
    assert len(rows) == 25 and len({row['mutated_asset_hex'] for row in rows}) == 25
    return rows

def receipt(golden, proposal, voter, amount, support=True, index=0):
    c = golden['fixture']['config']
    return h(b'VAMS/receipt/v2\0' + bytes.fromhex(c['receipt_policy_id']) + bytes.fromhex(c['proposal_policy_id'])
        + proposal + voter + amount.to_bytes(8, 'big') + bytes([support]) + index.to_bytes(4, 'big'))

def value(lovelace, *tokens):
    result = Counter({('', ''): lovelace})
    for policy, name, amount in tokens:
        assert len(policy) == 28 and 0 <= len(name) <= 32 and amount > 0
        result[(policy.hex(), name.hex())] += amount
    return result

def fixture_flow(golden, timing, row):
    c = golden['fixture']['config']
    raw = lambda name: bytes.fromhex(c[name])
    proposal = (bytes.fromhex(vector(golden, 'proposal_name')['digest_hex']) if row['index'] == 0
                else bytes.fromhex(row['mutated_asset_hex']))
    vote_receipt = receipt(golden, proposal, bytes.fromhex(c['members'][0]), 100)
    auth = bytes.fromhex(vector(golden, 'authority_name')['digest_hex'])
    vp, vn = raw('vams_policy_id'), raw('vams_asset_name')
    pp, rp, ip = raw('proposal_policy_id'), raw('receipt_policy_id'), raw('intent_policy_id')
    if row['parent_transition'] == 'Vote':
        inputs = [value(3_000_000, (pp, proposal, 1)), value(5_000_000, (vp, vn, 100))]
        outputs = [value(4_000_000, (pp, proposal, 1), (rp, vote_receipt, 1), (vp, vn, 100)), value(3_800_000)]
        mint = [(rp, vote_receipt, 1)]
    else:
        commitment = h(b'VAMS/proposal-state/v2\0' + proposal + b'\1' + (10).to_bytes(8, 'big')
            + bytes(8) + b'\1' + bytes.fromhex(c['members'][0]) + (100).to_bytes(8, 'big')
            + b'\1' + (10).to_bytes(8, 'big') + vote_receipt)
        p = golden['fixture']['proposal']
        target = bytes.fromhex(p['target_domain'])
        intent_preimage = (b'VAMS/intent/v2\0' + ip + pp + proposal + commitment
            + bytes.fromhex(p['action_hash']) + bytes.fromhex(p['payload_hash'])
            + bytes([len(target)]) + target + (2).to_bytes(4, 'big') + bytes(8)
            + (2100).to_bytes(8, 'big') + bytes.fromhex(p['proposer']))
        if row['index'] == 0:
            assert h(intent_preimage).hex() == vector(timing, 'queued_alice_intent_upper')['digest_hex']
        intent = bytes.fromhex(row['mutated_asset_hex']) if row['index'] == 0 else h(intent_preimage)
        authority = value(5_000_000, (raw('authority_policy_id'), auth, 1))
        inputs = [authority, value(4_000_000, (pp, proposal, 1), (rp, vote_receipt, 1), (vp, vn, 100)), value(1_000_000)]
        outputs = [authority, value(1_000_000, (vp, vn, 100)), value(3_000_000, (ip, intent, 1)), value(800_000)]
        mint = [(pp, proposal, -1), (rp, vote_receipt, -1), (ip, intent, 1)]
    return {'conserves_arithmetically': conserves(inputs, outputs, mint, 200_000),
        'inputs': inputs, 'outputs': outputs, 'mint': mint, 'fee': 200_000,
        'receipt_hex': vote_receipt.hex(), 'proposal_hex': proposal.hex()}

def conserves(inputs, outputs, mint, fee):
    # Signed Counter arithmetic deliberately avoids Counter subtraction dropping deficits.
    balance = Counter()
    for item in inputs:
        balance.update(item)
    for item in outputs:
        for name, amount in item.items(): balance[name] -= amount
    for policy, name, amount in mint: balance[(policy.hex(), name.hex())] += amount
    balance[('', '')] -= fee
    return all(amount == 0 for amount in balance.values())
