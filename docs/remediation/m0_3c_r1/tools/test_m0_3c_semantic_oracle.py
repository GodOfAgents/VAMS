"""M0.3c-R5 independent semantic oracle regressions."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

SPEC = importlib.util.spec_from_file_location(
    "m03c_oracle", Path(__file__).with_name("m0_3c_semantic_oracle.py")
)
O = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(O)


class M03CSemanticOracleTests(unittest.TestCase):
    assertion = (
        b".to.be.revertedWithCustomError(this.token, "
        b"'ERC20InvalidReceiver')\n"
    )
    path = O.PREFIX + "/test/token/ERC20/ERC20.test.js"

    def test_undeclared_error_rejects(self):
        self.assertFalse(O.assertion_semantics(
            self.assertion, 1, {}, self.path
        ))

    def test_comment_and_string_declarations_do_not_count(self):
        blobs = {
            "contracts/Probe.sol": (
                b'// error ERC20InvalidReceiver(address);\\n'
                b'string constant X = "error ERC20InvalidReceiver(address)";\\n'
            )
        }
        self.assertEqual(O.declarations(blobs), {})

    def test_wrong_contract_context_rejects(self):
        declared = {
            "ERC20InvalidReceiver": [
                ("contracts/interfaces/draft-IERC6093.sol", "20")
            ]
        }
        wrong = O.PREFIX + "/test/token/ERC721/ERC721.test.js"
        self.assertFalse(O.assertion_semantics(
            self.assertion, 1, declared, wrong
        ))

    def test_ambiguous_duplicate_declarations_reject(self):
        declared = {
            "ERC20InvalidReceiver": [
                ("contracts/interfaces/A.sol", "20"),
                ("contracts/interfaces/B.sol", "20"),
            ]
        }
        self.assertFalse(O.assertion_semantics(
            self.assertion, 1, declared, self.path
        ))

    def test_renamed_or_stale_declaration_rejects(self):
        declared = {
            "ERC20InvalidRecipient": [
                ("contracts/interfaces/draft-IERC6093.sol", "20")
            ]
        }
        self.assertFalse(O.assertion_semantics(
            self.assertion, 1, declared, self.path
        ))

    def test_valid_declared_error_accepts(self):
        declared = {
            "ERC20InvalidReceiver": [
                ("contracts/interfaces/draft-IERC6093.sol", "20")
            ]
        }
        self.assertTrue(O.assertion_semantics(
            self.assertion, 1, declared, self.path
        ))

    @staticmethod
    def document(der):
        return (
            json.dumps({
                "algorithm": "ECDSA",
                "testGroups": [{
                    "type": "EcdsaP1363Verify",
                    "key": {"type": "EcPublicKey"},
                    "keyDer": der.hex(),
                }],
            }, indent=2) + "\n"
        ).encode()

    @staticmethod
    def key_line(document):
        lines = document.decode().splitlines()
        return next(index for index, line in enumerate(lines, 1)
                    if '"keyDer"' in line)

    def test_malformed_der_rejects(self):
        document = self.document(b"malformed")
        self.assertFalse(O.der_semantics(
            document, self.key_line(document)
        ))

    def test_private_key_der_rejects(self):
        private = ec.generate_private_key(ec.SECP256R1())
        der = private.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        document = self.document(der)
        self.assertFalse(O.der_semantics(
            document, self.key_line(document)
        ))

    def test_non_ec_public_der_rejects(self):
        public = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        ).public_key()
        der = public.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        document = self.document(der)
        self.assertFalse(O.der_semantics(
            document, self.key_line(document)
        ))

    def test_valid_public_ec_der_accepts(self):
        public = ec.generate_private_key(ec.SECP256R1()).public_key()
        der = public.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        document = self.document(der)
        self.assertTrue(O.der_semantics(
            document, self.key_line(document)
        ))


if __name__ == "__main__":
    unittest.main()
