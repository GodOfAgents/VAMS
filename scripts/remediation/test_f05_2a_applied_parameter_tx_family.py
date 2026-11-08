"""Structural tests for the applied-parameter CBOR candidate builder; no simulator runs."""
from __future__ import annotations
import hashlib
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDER_PATH = ROOT / "scripts/remediation/build_f05_2a_applied_parameter_tx_family.py"
SPEC = importlib.util.spec_from_file_location("f05_applied_family_tested", BUILDER_PATH)
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)


def test_source_hashes_and_r4_1_owner_choice_are_pinned():
    raws = {name: (builder.FIX / name).read_bytes() for name in builder.HASHES}
    for name, raw in raws.items():
        assert hashlib.sha256(raw).hexdigest() == builder.HASHES[name]
        assert builder.cb.dumps(builder.cb.roundtrip(raw)) == raw
    contract = builder.json.loads(builder.R41.read_text())
    assert contract["owner_decisions"]["applied_parameter"]["choice"] == "C"


def test_original_case_ids_and_parameter_transformations_are_explicit():
    source_keys = [bytes([i]) * 32 for i in range(1, 6)]
    expected = {
        "applied_genesis_parameter": ("ab" * 32, 7, source_keys),
        "applied_keys_parameter": ("aa" * 32, 7, [bytes(32), *source_keys[:4]]),
        "applied_keys_bad_count": ("aa" * 32, 7, [*source_keys, bytes.fromhex("ff" * 32)]),
        "applied_keys_bad_length": ("aa" * 32, 7, [bytes(31), *source_keys[1:]]),
        "applied_keys_duplicate": ("aa" * 32, 7, [source_keys[0], source_keys[0], *source_keys[2:]]),
        "applied_keys_unsorted": ("aa" * 32, 7, [source_keys[0], source_keys[2], source_keys[1], *source_keys[3:]]),
    }
    assert tuple(expected) == builder.CASES
    for case_id, (seed_hex, seed_ix, keys) in expected.items():
        params, changed, seed = builder.params_for(case_id, source_keys)
        assert seed == (bytes.fromhex(seed_hex), seed_ix)
        assert changed == keys
        assert params["initial_keys"]["list"] == [builder.h.byte_string(key) for key in keys]


def test_policy_rename_rebinds_only_policy_keys_and_keeps_map_order():
    old = bytes.fromhex("11" * 28)
    new = bytes.fromhex("22" * 28)
    sentinel = bytes.fromhex("33" * 28)
    value = builder.cb.Map([
        (sentinel, builder.cb.Map([(b"x", 9)])),
        (old, builder.cb.Map([(b"VAMS-F05-AUTH-V3", 1)])),
        (b"", 10_000_000),
    ])
    rebound = builder.rename(value, old, new)
    assert builder.cb.map_get(rebound, new) == builder.cb.Map([(b"VAMS-F05-AUTH-V3", 1)])
    assert builder.cb.map_get(rebound, sentinel) == builder.cb.Map([(b"x", 9)])
    assert [key for key, _ in rebound.pairs] == sorted(key for key, _ in rebound.pairs)


def test_policy_case_surface_has_no_case_ledger_promotion_or_simulator_path():
    source = BUILDER_PATH.read_text(encoding="utf-8")
    assert "tx-sim-not-run" in source
    assert "CASE-STATUS.json" not in source
    assert "run_typed_tx_case(" not in source
    assert "choices=CASES" in source
    assert "remove_key_uniqueness_order_guard" in source
    assert "remove_key_order_guard" in source


def _openssl_verify(public: bytes, signature: bytes, message: bytes) -> None:
    import os
    import subprocess
    prefix = bytes.fromhex("302a300506032b6570032100")
    fds=[]
    try:
        for label, data in (("pub",prefix+public),("sig",signature),("msg",message)):
            fd=os.memfd_create("vams-f05-review-"+label,flags=0); fds.append(fd)
            if os.write(fd,data)!=len(data): raise AssertionError("short memfd write")
            os.lseek(fd,0,os.SEEK_SET)
        pubfd,sigfd,msgfd=fds
        result=subprocess.run(["openssl","pkeyutl","-verify","-rawin","-pubin","-inkey",f"/proc/self/fd/{pubfd}","-keyform","DER","-in",f"/proc/self/fd/{msgfd}","-sigfile",f"/proc/self/fd/{sigfd}"],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,pass_fds=tuple(fds),check=False)
        assert result.returncode == 0
    finally:
        for fd in fds: os.close(fd)


def test_generated_candidate_bundles_have_independent_byte_bindings_and_conservation():
    import json
    import hashlib
    baseline=builder.cb.roundtrip((builder.FIX/"valid.tx.cbor").read_bytes())
    baseline_output=builder.cb.map_get(builder.cb.map_get(baseline[0],1)[0],2)
    assert isinstance(baseline_output,list) and len(baseline_output)==2 and baseline_output[0]==1
    assert isinstance(baseline_output[1],builder.cb.Tag) and baseline_output[1].number==24
    baseline_redeemer=builder.cb.map_get(builder.cb.map_get(baseline[1],5),[1,0])
    assert isinstance(baseline_redeemer,list) and len(baseline_redeemer)==2
    assert isinstance(baseline_redeemer[0],builder.cb.Tag) and baseline_redeemer[0].number==121
    baseline_ex_units=baseline_redeemer[1]
    for case_id in builder.CASES:
        directory=builder.OUT/case_id
        manifest=json.loads((directory/"FIXTURE-MANIFEST.json").read_text())
        assert manifest["case_id"] == case_id
        assert manifest["status"].startswith("candidate-awaiting-independent-byte-review")
        assert manifest["negative"]["status"] == "PENDING"
        assert manifest["credit"] == {"negative_case":None,"original_policy":False,
                                     "ledger_admission":False,"live_network":False}
        conservation=manifest["conservation"]
        assert conservation["inputs_lovelace"]==17_000_000
        assert conservation["authority_output_lovelace"]==10_000_000
        assert conservation["sponsor_change_output_lovelace"]==6_000_000
        assert conservation["fee_lovelace"]==1_000_000
        assert conservation["collateral"]=={"present":False,"lovelace":0}
        for line in (directory/"SHA256SUMS").read_text().splitlines():
            digest,name=line.split("  ",1)
            assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==digest
        labels=["negative","positive-control"]
        if manifest["one_guard_mutant_control"] is not None: labels.append("one-guard-mutant-control")
        assert set(manifest["policy_applications"]) == set(labels)
        for label in labels:
            application=manifest["policy_applications"][label]
            parameter=application["parameter_cbor"]
            seed_meta=parameter["genesis_ref"]
            seed_raw=(directory/seed_meta["file"]).read_bytes()
            assert hashlib.sha256(seed_raw).hexdigest()==seed_meta["sha256"]
            assert len(seed_raw)==seed_meta["bytes"]
            seed_value=seed_meta["value"]
            seed_rebuilt=builder.h._output_reference(bytes.fromhex(seed_value["tx_hash"]),seed_value["output_index"])
            assert builder.h.cbor(seed_rebuilt)==seed_raw
            key_meta=parameter["initial_keys"]
            keys_raw=(directory/key_meta["file"]).read_bytes()
            assert hashlib.sha256(keys_raw).hexdigest()==key_meta["sha256"]
            assert len(keys_raw)==key_meta["bytes"]
            key_bytes=[bytes.fromhex(value) for value in key_meta["values_hex"]]
            assert key_meta["count"]==len(key_bytes)
            assert key_meta["key_byte_lengths"]==[len(key) for key in key_bytes]
            assert key_meta["strictly_increasing"]==all(key_bytes[i]<key_bytes[i+1] for i in range(len(key_bytes)-1))
            assert key_meta["unique"]==(len(set(key_bytes))==len(key_bytes))
            rebuilt_keys=builder.h.list_data([builder.h.byte_string(key) for key in key_bytes])
            assert builder.h.cbor(rebuilt_keys)==keys_raw
            txraw=(directory/(label+".tx.cbor")).read_bytes()
            inraw=(directory/(label+".raw_inputs.cbor")).read_bytes()
            outraw=(directory/(label+".raw_outputs.cbor")).read_bytes()
            code=(directory/(label+".applied-policy.cbor")).read_bytes()
            tx=builder.cb.roundtrip(txraw); inputs=builder.cb.roundtrip(inraw); outputs=builder.cb.roundtrip(outraw)
            body,wits=tx[0],tx[1]
            output_datum=builder.cb.map_get(builder.cb.map_get(body,1)[0],2)
            assert isinstance(output_datum,list) and len(output_datum)==2
            assert output_datum[0]==baseline_output[0]==1
            assert isinstance(output_datum[1],builder.cb.Tag)
            assert output_datum[1].number==baseline_output[1].number==24
            if label=="positive-control":
                params_meta=application["parameter_cbor"]
                seed_value=params_meta["genesis_ref"]["value"]
                datum_seed=(bytes.fromhex(seed_value["tx_hash"]),seed_value["output_index"])
                datum_keys=[bytes.fromhex(key) for key in params_meta["initial_keys"]["values_hex"]]
            else:
                datum_meta=manifest["negative"]["datum_state"]
                seed_value=manifest["negative"]["datum_seed_ref"]
                datum_seed=(bytes.fromhex(seed_value["tx_hash"]),seed_value["output_index"])
                datum_keys=[bytes.fromhex(key) for key in datum_meta["keys_hex"]]
            datum_state=builder.h._authority_state(datum_seed[0],datum_seed[1],datum_keys)
            assert builder.h.cbor(datum_state)==output_datum[1].value
            if label!="positive-control":
                assert hashlib.sha256(output_datum[1].value).hexdigest()==datum_meta["plutus_data_sha256"]
            redeemer_pair=builder.cb.map_get(builder.cb.map_get(wits,5),[1,0])
            assert isinstance(redeemer_pair,list) and len(redeemer_pair)==2
            assert isinstance(redeemer_pair[0],builder.cb.Tag) and redeemer_pair[0].number==121
            assert redeemer_pair[1]==baseline_ex_units
            assert not (isinstance(redeemer_pair[0],builder.cb.Tag) and redeemer_pair[0].number==24)
            redeemer_meta=manifest["artifacts"][label+".validation"]["mint0_redeemer"]
            intended_redeemer=builder.cb.Tag(121,[[bytes.fromhex(signature) for signature in
                                                     redeemer_meta["proof_signatures_hex"]]])
            assert redeemer_pair[0]==intended_redeemer
            assert len(intended_redeemer.value)==1 and len(intended_redeemer.value[0])==5
            assert redeemer_meta["constructor_tag"]==121 and redeemer_meta["proof_count"]==5
            assert hashlib.sha256(builder.cb.dumps(redeemer_pair[0])).hexdigest()==redeemer_meta["cbor_sha256"]
            assert builder.cb.map_get(body,0).value==inputs
            expected_policy=hashlib.blake2b(b"\x03"+code,digest_size=28).digest()
            mint=builder.cb.map_get(body,9)
            assert [pid for pid,_ in mint.pairs]==[expected_policy]
            scripts=builder.cb.map_get(wits,7)
            assert scripts.value==[code]
            assert hashlib.blake2b(b"\x03"+scripts.value[0],digest_size=28).digest()==expected_policy
            assert application["applied_policy_id"]==expected_policy.hex()
            assert application["program_sha256"]==hashlib.sha256(code).hexdigest()
            body_hash=hashlib.blake2b(builder.cb.dumps(body),digest_size=32).digest()
            witnesses=builder.cb.map_get(wits,0)
            assert isinstance(witnesses,builder.cb.Tag) and witnesses.number==258
            public_hashes=set()
            for pub,sig in witnesses.value:
                _openssl_verify(pub,sig,body_hash)
                public_hashes.add(hashlib.blake2b(pub,digest_size=28).digest())
            output_hashes={builder.cb.map_get(o,0)[1:] for o in outputs}
            assert public_hashes==output_hashes
            input_coin=sum(builder.cb.map_get(o,1) for o in outputs)
            output_coin=0; native={}
            for out in builder.cb.map_get(body,1):
                value=builder.cb.map_get(out,1)
                if isinstance(value,int): output_coin+=value
                else:
                    output_coin+=value[0]
                    for pid,assets in value[1].pairs:
                        for asset,qty in assets.pairs: native[(pid,asset)]=native.get((pid,asset),0)+qty
            minted={(pid,asset):qty for pid,assets in mint.pairs for asset,qty in assets.pairs}
            fee=builder.cb.map_get(body,2)
            assert (input_coin,output_coin,fee)==(17_000_000,16_000_000,1_000_000)
            assert 13 not in [key for key,_ in body.pairs]  # no collateral input/return fields
            values=[builder.cb.map_get(out,1) for out in builder.cb.map_get(body,1)]
            assert values[0][0]==10_000_000 and values[1]==6_000_000  # authority plus sponsor/change
            assert native==minted=={(expected_policy,b"VAMS-F05-AUTH-V3"):1}

def test_top_level_manifest_covers_summary_and_every_case_artifact():
    import hashlib
    import json
    root=builder.OUT
    manifest_path=root/"FAMILY-MANIFEST.json"
    manifest=json.loads(manifest_path.read_text())
    assert manifest["schema_version"]=="f05-2a-applied-parameter-family-package-r5"
    recorded=manifest["files"]
    expected={path.relative_to(root).as_posix() for path in root.rglob("*")
              if path.is_file() and path.relative_to(root).as_posix() not in {"FAMILY-MANIFEST.json","SHA256SUMS"}}
    assert set(recorded)==expected
    assert "SUMMARY.md" in recorded
    assert all(any(path.startswith(case+"/") for case in builder.CASES) for path in recorded if path!="SUMMARY.md")
    for relative,entry in recorded.items():
        raw=(root/relative).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==entry["sha256"]
        assert len(raw)==entry["bytes"]
    sum_rows={}
    for line in (root/"SHA256SUMS").read_text().splitlines():
        digest,relative=line.split("  ",1);sum_rows[relative]=digest
    all_files={path.relative_to(root).as_posix() for path in root.rglob("*")
               if path.is_file() and path.relative_to(root).as_posix()!="SHA256SUMS"}
    assert set(sum_rows)==all_files
    for relative,digest in sum_rows.items():
        assert hashlib.sha256((root/relative).read_bytes()).hexdigest()==digest
