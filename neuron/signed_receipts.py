"""Asymmetric v3 receipt primitives; no local v2 MAC receipt is accepted.

Uses the installed cryptography implementation of secp256k1 ECDSA. Public
verification keys are separate types and cannot issue authority. These wire
primitives do not qualify an issuer, a policy source, or a durable provider.
"""
from dataclasses import dataclass
import hashlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

DOMAIN=b'VAMS:SIGNED-RECEIPT:v3\0'
ORDER=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
PURPOSES={1,2,3,4,5} # admission, fence update, fence acknowledgement, effect, fenced absence

class ReceiptError(ValueError):pass

@dataclass(frozen=True)
class ReceiptV3:
    purpose: int
    issuer_id: bytes
    subject_digest: bytes
    provider_id: bytes
    authority_epoch: int
    policy_version: int
    fencing_token: int
    issued_at: int
    expires_at: int

    def canonical_bytes(self):
        if type(self.purpose) is not int or self.purpose not in PURPOSES:raise ReceiptError('invalid purpose')
        for value in (self.issuer_id,self.subject_digest,self.provider_id):
            if type(value) is not bytes or len(value)!=32 or value==b'\0'*32:raise ReceiptError('invalid receipt identity')
        integers=(self.purpose,self.authority_epoch,self.policy_version,self.fencing_token,self.issued_at,self.expires_at)
        if any(type(x) is not int or not 0<=x<(1<<256) for x in integers):raise ReceiptError('invalid receipt integer')
        if not all(integers[1:4]) or self.expires_at<=self.issued_at:raise ReceiptError('invalid receipt scope')
        return DOMAIN+self.issuer_id+self.subject_digest+self.provider_id+b''.join(x.to_bytes(32,'big') for x in integers)

    @property
    def digest(self):return hashlib.sha256(self.canonical_bytes()).digest()

@dataclass(frozen=True)
class ReceiptVerifierV3:
    public_key_bytes: bytes

    def __post_init__(self):
        if type(self.public_key_bytes) is not bytes or len(self.public_key_bytes)!=65 or self.public_key_bytes[0]!=4:
            raise ReceiptError('canonical uncompressed public key required')
        try:ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(),self.public_key_bytes)
        except ValueError:raise ReceiptError('invalid public key') from None

    @property
    def issuer_id(self):return hashlib.sha256(b'VAMS:RECEIPT-KEY:secp256k1:v3\0'+self.public_key_bytes).digest()

    def verify(self, receipt, signature, *, purpose, subject_digest, provider_id,
               authority_epoch, policy_version, fencing_token, now):
        for value in (purpose,authority_epoch,policy_version,fencing_token,now):
            if type(value) is not int or not 0<=value<(1<<256):raise ReceiptError('invalid expected scope')
        for value in (subject_digest,provider_id):
            if type(value) is not bytes or len(value)!=32:raise ReceiptError('invalid expected digest')
        if type(receipt) is not ReceiptV3 or type(signature) is not bytes or len(signature)!=64:
            raise ReceiptError('unsupported receipt or signature version')
        if (receipt.issuer_id!=self.issuer_id or receipt.purpose!=purpose or
            receipt.subject_digest!=subject_digest or receipt.provider_id!=provider_id or
            receipt.authority_epoch!=authority_epoch or receipt.policy_version!=policy_version or
            receipt.fencing_token!=fencing_token):raise ReceiptError('receipt context mismatch')
        if type(now) is not int or not receipt.issued_at<=now<receipt.expires_at:
            raise ReceiptError('receipt is not current')
        r,s=int.from_bytes(signature[:32],'big'),int.from_bytes(signature[32:],'big')
        if not 0<r<ORDER or not 0<s<=ORDER//2:raise ReceiptError('noncanonical signature')
        key=ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(),self.public_key_bytes)
        try:key.verify(utils.encode_dss_signature(r,s),receipt.digest,ec.ECDSA(utils.Prehashed(hashes.SHA256())))
        except InvalidSignature:raise ReceiptError('invalid signature') from None
        return receipt.digest

    def verify_evidence(self, receipt, signature, *, now, **expected):
        """Authenticate historical effect/absence records; never dispatch authority.

        Expected epochs/fences must come from the retained operation, followed by
        independent provider reconciliation. A signature alone is not finality.
        """
        if type(receipt) is not ReceiptV3 or receipt.purpose not in (4,5):
            raise ReceiptError('not an effect evidence receipt')
        if type(now) is not int or now<receipt.issued_at:raise ReceiptError('future evidence')
        return self.verify(receipt,signature,now=receipt.issued_at,**expected)

class ReceiptSignerV3:
    def __init__(self, key):
        if not isinstance(key,ec.EllipticCurvePrivateKey) or not isinstance(key.curve,ec.SECP256K1):
            raise ReceiptError('secp256k1 private signing key required')
        self.__key=key

    def verifier(self):
        return ReceiptVerifierV3(self.__key.public_key().public_bytes(
            serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint))

    def sign(self, receipt):
        if type(receipt) is not ReceiptV3 or receipt.issuer_id!=self.verifier().issuer_id:
            raise ReceiptError('receipt issuer mismatch')
        signature=self.__key.sign(receipt.digest,ec.ECDSA(utils.Prehashed(hashes.SHA256())))
        r,s=utils.decode_dss_signature(signature)
        s=min(s,ORDER-s)
        return r.to_bytes(32,'big')+s.to_bytes(32,'big')
