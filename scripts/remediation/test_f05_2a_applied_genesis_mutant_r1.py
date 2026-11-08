"""Focused structural assertions for applied-genesis synthetic candidate; never simulates."""
from __future__ import annotations
import hashlib, importlib.util, json, os, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BUILDER=ROOT/"scripts/remediation/build_f05_2a_applied_genesis_mutant_r1.py"
SPEC=importlib.util.spec_from_file_location("applied_genesis_candidate_builder",BUILDER)
b=importlib.util.module_from_spec(SPEC);sys.modules[SPEC.name]=b;SPEC.loader.exec_module(b)
BASE_SPEC=importlib.util.spec_from_file_location("applied_genesis_candidate_base",b.BASE_PATH)
base=importlib.util.module_from_spec(BASE_SPEC);sys.modules[BASE_SPEC.name]=base;BASE_SPEC.loader.exec_module(base)
h=base.h; cb=base.cb
OUT=b.OUT
def sha(raw): return hashlib.sha256(raw).hexdigest()

def decode_key_data(raw: bytes) -> list[bytes]:
    # Harness serialization for a Plutus list of byte strings is 9f (58 20 + 32 bytes)*5 ff.
    assert raw[:1]==b"\x9f" and raw[-1:]==b"\xff"
    values=[];pos=1
    while pos<len(raw)-1:
        assert raw[pos:pos+2]==b"\x58\x20"
        values.append(raw[pos+2:pos+34]);pos+=34
    assert pos==len(raw)-1 and len(values)==5 and all(len(x)==32 for x in values)
    return values

def verify_ed25519(public: bytes, signature: bytes, message: bytes) -> None:
    import subprocess
    prefix=bytes.fromhex("302a300506032b6570032100")
    fds=[]
    try:
        for name,data in (("pub",prefix+public),("sig",signature),("msg",message)):
            fd=os.memfd_create("vams-genesis-fixture-"+name,0);fds.append(fd)
            assert os.write(fd,data)==len(data);os.lseek(fd,0,0)
        pub,sig,msg=fds
        result=subprocess.run(["openssl","pkeyutl","-verify","-rawin","-pubin","-inkey",f"/proc/self/fd/{pub}","-keyform","DER","-in",f"/proc/self/fd/{msg}","-sigfile",f"/proc/self/fd/{sig}"],pass_fds=tuple(fds),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
        assert result.returncode==0
    finally:
        for fd in fds: os.close(fd)

def test_applied_genesis_negative_and_one_guard_mutant_are_structural_only():
    manifest=json.loads((OUT/"FIXTURE-MANIFEST.json").read_text())
    assert manifest["case_id"]=="applied_genesis_parameter"
    assert manifest["original_case_id_preserved"] is True
    assert manifest["assertion"]["id"]=="applied_genesis_parameter"
    assert manifest["status"].startswith("candidate-awaiting-independent-byte-review")
    assert manifest["negative"]["status"]=="PENDING"
    assert manifest["positive_control"]["status"]=="not executed"
    assert manifest["one_guard_mutant_control"]["status"]=="not executed"
    assert manifest["scope"]=="synthetic alternate applied policy only; no original-policy, ledger-admission, or live-network evidence"
    assert manifest["credit"]=={"case":False,"mutation":False,"original_policy":False,"ledger_admission":False,"live_network":False}
    assert manifest["entrypoint"].endswith("mint / Mint[0]")
    patch=(OUT/"MUTANT-SOURCE.patch").read_text()
    changes=[line for line in patch.splitlines() if line.startswith(("+","-")) and not line.startswith(("+++","---"))]
    assert changes==["-  expect count_seed_input(tx.inputs, genesis_ref) == 1","+  expect True"]
    assert manifest["source_mutation"]["name"]=="remove_seed_guard"
    assert manifest["source_mutation"]["changed_lines"]==changes
    expected_seed=(bytes.fromhex("ab"*32),7)
    expected_seed_data=h.cbor(h._output_reference(*expected_seed))
    expected_keys=decode_key_data((OUT/"negative.initial_keys.cbor").read_bytes())
    assert (OUT/"negative.initial_keys.cbor").read_bytes()==h.cbor(h.list_data([h.byte_string(k) for k in expected_keys]))
    expected_state=h.cbor(h._authority_state(expected_seed[0],expected_seed[1],expected_keys))
    baseline=cb.roundtrip((base.FIX/"valid.tx.cbor").read_bytes())
    baseline_red=cb.map_get(cb.map_get(baseline[1],5),[1,0])
    assert isinstance(baseline_red,list) and len(baseline_red)==2
    expected_exunits=baseline_red[1]
    for label in ("positive-control","negative","one-guard-mutant-control"):
        code=(OUT/(label+".applied-policy.cbor")).read_bytes()
        txraw=(OUT/(label+".tx.cbor")).read_bytes()
        inraw=(OUT/(label+".raw_inputs.cbor")).read_bytes()
        outraw=(OUT/(label+".raw_outputs.cbor")).read_bytes()
        tx=cb.roundtrip(txraw);body,wit=tx[0],tx[1]
        inputs=cb.roundtrip(inraw);outputs=cb.roundtrip(outraw)
        # Mint[0] applied program identity is bound across policy id, mint, and V3 witness.
        pid=hashlib.blake2b(b"\x03"+code,digest_size=28).digest()
        app=manifest["policy_applications"][label]
        assert pid.hex()==app["policy_id"]
        mint=cb.map_get(body,9)
        assert [policy for policy,_ in mint.pairs]==[pid]
        v3=cb.map_get(wit,7)
        assert isinstance(v3,cb.Tag) and v3.number==258 and v3.value==[code]
        assert cb.map_get(body,0).value==inputs
        assert (OUT/(label+".genesis_ref.cbor")).read_bytes()==expected_seed_data
        assert (OUT/(label+".initial_keys.cbor")).read_bytes()==(OUT/"negative.initial_keys.cbor").read_bytes()
        # Applied seed remains in policy params and inline datum for all controls.
        datum=cb.map_get(cb.map_get(body,1)[0],2)
        assert isinstance(datum,list) and len(datum)==2 and datum[0]==1
        assert isinstance(datum[1],cb.Tag) and datum[1].number==24 and datum[1].value==expected_state
        refs=cb.map_get(body,0)
        has_seed=[ref for ref in refs.value if ref==[expected_seed[0],expected_seed[1]]]
        if label=="positive-control":
            assert has_seed
        else:
            assert not has_seed
        redeemer_pair=cb.map_get(cb.map_get(wit,5),[1,0])
        assert isinstance(redeemer_pair,list) and len(redeemer_pair)==2
        assert isinstance(redeemer_pair[0],cb.Tag) and redeemer_pair[0].number==121
        assert redeemer_pair[1]==expected_exunits
        proofs=redeemer_pair[0].value[0]
        assert len(proofs)==len(expected_keys)==5 and all(len(proof)==64 for proof in proofs)
        pop_message=h._canonical_pop_message(expected_seed[0],expected_seed[1],base.STATE,expected_keys)
        for pub,sig in zip(expected_keys,proofs): verify_ed25519(pub,sig,pop_message)
        # All funding witnesses are fresh, body-bound Ed25519 signatures to output payment hashes.
        body_hash=hashlib.blake2b(cb.dumps(body),digest_size=32).digest()
        ws=cb.map_get(wit,0)
        assert isinstance(ws,cb.Tag) and ws.number==258
        for pub,sig in ws.value: verify_ed25519(pub,sig,body_hash)
        assert {hashlib.blake2b(pub,digest_size=28).digest() for pub,_ in ws.value}=={cb.map_get(o,0)[1:] for o in outputs}
        # Conservation: 17M lovelace funding = 10M authority + 6M change + 1M fee,
        # and the only minted native asset is the bound authority singleton.
        incoin=sum(cb.map_get(row,1) for row in outputs)
        outcoin=0;native={}
        for output in cb.map_get(body,1):
            value=cb.map_get(output,1)
            if isinstance(value,int): outcoin+=value
            else:
                outcoin+=value[0]
                for policy,assets in value[1].pairs:
                    for asset,quantity in assets.pairs: native[(policy,asset)]=native.get((policy,asset),0)+quantity
        minted={(policy,asset):quantity for policy,assets in mint.pairs for asset,quantity in assets.pairs}
        assert (incoin,outcoin,cb.map_get(body,2))==(17_000_000,16_000_000,1_000_000)
        assert native==minted=={(pid,b"VAMS-F05-AUTH-V3"):1}
        assert app["validation"]["valid_body_bound_ephemeral_signatures"] is True
        assert app["validation"]["private_keys_persisted"] is False
        assert app["validation"]["ada_conservation"] is True and app["validation"]["native_asset_conservation"] is True
    assert manifest["policy_applications"]["negative"]["policy_id"]!=manifest["policy_applications"]["one-guard-mutant-control"]["policy_id"]
    assert manifest["one_guard_mutant_control"]["mutant_policy_id"]==manifest["policy_applications"]["one-guard-mutant-control"]["policy_id"]
    # No secret key files are part of the candidate.
    assert not any(path.suffix in {".key",".pem",".sk"} for path in OUT.iterdir())
    listed={}
    for line in (OUT/"SHA256SUMS").read_text().splitlines():
        digest,name=line.split("  ",1);listed[name]=digest
    actual={p.name for p in OUT.iterdir() if p.is_file() and p.name!="SHA256SUMS"}
    assert set(listed)==actual
    for name,digest in listed.items(): assert sha((OUT/name).read_bytes())==digest

