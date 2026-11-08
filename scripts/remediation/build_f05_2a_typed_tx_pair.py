#!/usr/bin/env python3
"""Test-only canonical CBOR builder for one signed F05.2a tx pair."""
from __future__ import annotations
import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

ROOT = Path(__file__).resolve().parents[2]
from cryptography.exceptions import InvalidSignature
SOURCE = ROOT / "docs/remediation/m3_f05_2a/tx_sim_r1"
DEST = ROOT / "docs/remediation/m3_f05_2a/tx_sim_typed_r1"
INPUT_HASHES = {
    "valid.tx.cbor": "765c717f16b543c746b88742e8b775cd3ecabca4fef6edd16702184683780a28",
    "raw_inputs.cbor": "4b20e2b2cf4bd58b1f6e385c90ffd098d583df69d95fbc7b1fcc2591da72b9fe",
    "raw_outputs.cbor": "9cdf345a785f51763bdb43f1b1ba0c20b5545051f03051e6a7bf726ea128c56a",
}
POLICY_ID = "9d669aafdc912fde12f7b6e47cd0010dfa48ea9766e60af220608731"

@dataclass(frozen=True)
class B: value: bytes
@dataclass(frozen=True)
class T: tag: int; value: Any
@dataclass(frozen=True)
class M: pairs: tuple[tuple[Any, Any], ...]

class Reader:
    def __init__(self, data: bytes): self.d, self.i = data, 0
    def take(self, n: int) -> bytes:
        if n < 0 or self.i + n > len(self.d): raise ValueError("truncated CBOR")
        v = self.d[self.i:self.i+n]; self.i += n; return v
    def arg(self, a: int) -> int:
        if a < 24: return a
        width = {24: 1, 25: 2, 26: 4, 27: 8}.get(a)
        if width is None: raise ValueError("indefinite/reserved CBOR not supported")
        n = int.from_bytes(self.take(width), "big")
        if n < {1:24, 2:256, 4:65536, 8:4294967296}[width]: raise ValueError("noncanonical CBOR")
        return n
    def item(self) -> Any:
        x = self.take(1)[0]; major, a = x >> 5, x & 31
        if major in (0,1):
            n=self.arg(a); return n if major == 0 else -1-n
        if major in (2,3):
            raw=self.take(self.arg(a)); return B(raw) if major == 2 else raw.decode("utf-8")
        if major == 4: return [self.item() for _ in range(self.arg(a))]
        if major == 5: return M(tuple((self.item(),self.item()) for _ in range(self.arg(a))))
        if major == 6: return T(self.arg(a),self.item())
        if major == 7 and a in (20,21,22): return {20:False,21:True,22:None}[a]
        raise ValueError("unsupported CBOR item")

def head(m: int, n: int) -> bytes:
    if n < 24: return bytes([m*32+n])
    if n < 256: return bytes([m*32+24,n])
    if n < 65536: return bytes([m*32+25])+n.to_bytes(2,"big")
    if n < 2**32: return bytes([m*32+26])+n.to_bytes(4,"big")
    if n < 2**64: return bytes([m*32+27])+n.to_bytes(8,"big")
    raise ValueError("CBOR integer too large")

def enc(v: Any) -> bytes:
    if v is None: return b"\xf6"
    if v is False: return b"\xf4"
    if v is True: return b"\xf5"
    if isinstance(v,int): return head(0,v) if v>=0 else head(1,-1-v)
    if isinstance(v,B): return head(2,len(v.value))+v.value
    if isinstance(v,str):
        b=v.encode(); return head(3,len(b))+b
    if isinstance(v,list): return head(4,len(v))+b"".join(enc(x) for x in v)
    if isinstance(v,M): return head(5,len(v.pairs))+b"".join(enc(k)+enc(x) for k,x in v.pairs)
    if isinstance(v,T): return head(6,v.tag)+enc(v.value)
    raise TypeError(type(v).__name__)

def get(m: M, key: int) -> Any:
    found=[v for k,v in m.pairs if k==key]
    if len(found)!=1: raise ValueError(f"map key {key} is not unique")
    return found[0]

def parse(raw: bytes) -> Any:
    r=Reader(raw); v=r.item()
    if r.i!=len(raw): raise ValueError("trailing CBOR")
    return v

def sha(raw: bytes) -> str: return hashlib.sha256(raw).hexdigest()

def build() -> dict[str,Any]:
    raw={}; value={}
    for name,digest in INPUT_HASHES.items():
        raw[name]=(SOURCE/name).read_bytes()
        if sha(raw[name])!=digest: raise ValueError(f"source digest mismatch: {name}")
        value[name]=parse(raw[name])
        if enc(value[name])!=raw[name]: raise ValueError(f"CBOR round-trip differs: {name}")
    tx=value["valid.tx.cbor"]
    if not isinstance(tx,list) or len(tx)!=4 or not isinstance(tx[0],M): raise ValueError("bad Conway envelope")
    body=tx[0]; outputs=get(body,1)
    if not isinstance(outputs,list) or len(outputs)!=2: raise ValueError("expected authority and sponsor outputs")
    auth,sponsor=outputs
    av,sv=get(auth,1),get(sponsor,1)
    if not isinstance(av,list) or av[0]!=10_000_000 or sv!=6_000_000: raise ValueError("unexpected positive ADA values")
    mint=get(body,9)
    if not isinstance(mint,M) or len(mint.pairs)!=1 or mint.pairs[0][0]!=B(bytes.fromhex(POLICY_ID)): raise ValueError("wrong mint policy")
    positive_witness_set=tx[1]
    if not isinstance(positive_witness_set,M): raise ValueError("expected positive witness map")
    positive_vkeys=get(positive_witness_set,0)
    if not isinstance(positive_vkeys,T) or positive_vkeys.tag!=258: raise ValueError("expected positive vkey witnesses")
    old_pairs=positive_vkeys.value
    positive_hash=hashlib.blake2b(enc(body),digest_size=32).digest()
    for pub,sig in old_pairs: Ed25519PublicKey.from_public_bytes(pub.value).verify(sig.value,positive_hash)
    # Keep fee/conservation unchanged: move exactly one lovelace from the
    # authority output to the sponsor output to violate only the fixed state value.
    av[0]-=1
    outputs[1]=M(tuple((k,sv+1 if k==1 else v) for k,v in sponsor.pairs))
    # New ephemeral test-only keys make the negative transaction's funding
    # witnesses valid for its changed body hash. Their private bytes stay in
    # memory and are never serialized or printed.
    resolved=value["raw_outputs.cbor"]
    if not isinstance(resolved,list) or len(resolved)!=2: raise ValueError("expected two ordered funding UTxOs")
    signers=[]; witness_pairs=[]
    for index,utxo in enumerate(resolved):
        key=Ed25519PrivateKey.generate()
        public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
        payhash=hashlib.blake2b(public,digest_size=28).digest()
        resolved[index]=M(tuple((k,B(b"\x60"+payhash) if k==0 else v) for k,v in utxo.pairs))
        signers.append((public,key))
    body_hash=hashlib.blake2b(enc(body),digest_size=32).digest()
    stale_rejected=0
    for pub,sig in old_pairs:
        try: Ed25519PublicKey.from_public_bytes(pub.value).verify(sig.value,body_hash)
        except InvalidSignature: stale_rejected+=1
    if stale_rejected!=len(old_pairs): raise ValueError("stale positive-body witness reuse was not rejected")
    witness_pairs=sorted(((B(public),B(key.sign(body_hash))) for public,key in signers),key=lambda pair:pair[0].value)
    witness_set=tx[1]
    if not isinstance(witness_set,M): raise ValueError("expected witness-set map")
    old_vkeys=get(witness_set,0)
    if not isinstance(old_vkeys,T) or old_vkeys.tag!=258: raise ValueError("expected tagged vkey witness set")
    tx[1]=M(tuple((k,T(258,[[pub,sig] for pub,sig in witness_pairs]) if k==0 else v) for k,v in witness_set.pairs))
    negative=enc(tx)
    serialized_negative=parse(negative)
    serialized_body=serialized_negative[0]
    serialized_witness_set=serialized_negative[1]
    serialized_vkeys=get(serialized_witness_set,0)
    if not isinstance(serialized_vkeys,T) or serialized_vkeys.tag!=258: raise ValueError("negative serialized witness set is malformed")
    serialized_pairs=serialized_vkeys.value
    expected_publics=sorted(pub.value for pub,sig in witness_pairs)
    actual_publics=sorted(pub.value for pub,sig in serialized_pairs)
    old_publics={pub.value for pub,sig in old_pairs}
    if actual_publics!=expected_publics or old_publics.intersection(actual_publics): raise ValueError("negative serialized witness set reused stale positive keys")
    serialized_body_hash=hashlib.blake2b(enc(serialized_body),digest_size=32).digest()
    if serialized_body_hash!=body_hash: raise ValueError("serialized negative body hash changed")
    for pub,sig in serialized_pairs:
        Ed25519PublicKey.from_public_bytes(pub.value).verify(sig.value,serialized_body_hash)
    negative_outputs=enc(resolved)
    DEST.mkdir(parents=True,exist_ok=True)
    (DEST/"valid.tx.cbor").write_bytes(raw["valid.tx.cbor"])
    (DEST/"authority_value_minus_one.tx.cbor").write_bytes(negative)
    (DEST/"raw_inputs.cbor").write_bytes(raw["raw_inputs.cbor"])
    (DEST/"raw_outputs.cbor").write_bytes(raw["raw_outputs.cbor"])
    (DEST/"negative_raw_outputs.cbor").write_bytes(negative_outputs)
    manifest={
      "schema_version":"f05-2a-typed-tx-pair-r1",
      "status":"candidate-awaiting-independent-byte-review",
      "source_sha256":INPUT_HASHES,
      "policy_id":POLICY_ID,
      "target":"single minted policy at Mint[0]",
      "cases":[
        {"id":"valid_positive_control","path":"valid.tx.cbor","sha256":sha(raw["valid.tx.cbor"]),"inputs":"raw_inputs.cbor","outputs":"raw_outputs.cbor","expected":"accept"},
        {"id":"authority_value_minus_one","registry_case_id":"authority_value_minus_one","registry_case_number":33,"classification":"ledger-reachable","intended_assertion":"authority output has exactly 10,000,000 lovelace","path":"authority_value_minus_one.tx.cbor","sha256":sha(negative),"inputs":"raw_inputs.cbor","outputs":"negative_raw_outputs.cbor","expected":"reject exact authority-output lovelace guard"}],
      "delta":{"authority_lovelace":[10000000,9999999],"sponsor_lovelace":[6000000,6000001],"output_sum":"unchanged","rebound_validity_fields":["funding vkey witnesses","resolved key-payment addresses"],"other_script_relevant_fields":"unchanged"},
      "negative_raw_outputs_sha256":sha(negative_outputs),
      "vectors":{"positive":["raw_inputs.cbor","raw_outputs.cbor"],"negative":["raw_inputs.cbor","negative_raw_outputs.cbor"]},
      "signing":"fresh ephemeral test Ed25519 keypairs; signatures cover blake2b-256(canonical tx body); private bytes are never written",
      "command":"aiken tx simulate --cbor <tx> raw_inputs.cbor <case outputs vector>"}
    (DEST/"PAIR-MANIFEST.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    return manifest

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--build",action="store_true",required=True); p.parse_args()
    print(json.dumps(build(),indent=2,sort_keys=True))
