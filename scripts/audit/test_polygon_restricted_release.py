"""Synthetic release metadata checks; no deployed/runtime/proof qualification."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.audit import test_audit_program as fixtures

subject = fixtures.audit_program


def errors_for(root, polygon, stage='canary'):
    commit = 'a' * 40
    cardano = fixtures._deployment_manifest(root, 'cardano-preprod', commit)
    paths = []
    for network, manifest in [('polygon-amoy', polygon), ('cardano-preprod', cardano)]:
        path = root / (network + '.json')
        path.write_text(json.dumps(manifest), encoding='utf-8')
        paths.append(path)
    with mock.patch.object(subject, 'ROOT', root):
        return subject._validate_deployment_manifests(paths, stage, commit)


class PolygonLegacyRegressionTests(unittest.TestCase):
    def test_legacy_polygon_release_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = fixtures._legacy_deployment_manifest(root, 'polygon-amoy', 'a' * 40)
            self.assertTrue(any('restricted profile' in error for error in errors_for(root, manifest)))

    def test_ordinary_governor_proposer_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = fixtures._legacy_deployment_manifest(root, 'polygon-amoy', 'a' * 40)
            self.assertTrue(any('unexpected role assignments' in error for error in errors_for(root, manifest)))


class PolygonRestrictedReleaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.manifest = fixtures._deployment_manifest(self.root, 'polygon-amoy', 'a' * 40)
        self.package = self.manifest['restricted_evm']

    def assertRejected(self, text):
        self.assertTrue(any(text in error for error in errors_for(self.root, self.manifest)),
                        errors_for(self.root, self.manifest))

    def test_consistent_synthetic_canary_metadata(self):
        self.assertEqual(errors_for(self.root, self.manifest), [])

    def test_unknown_profile_rejects(self):
        self.manifest['release_profile'] = 'unrestricted'
        self.assertRejected('restricted profile requires')

    def test_old_schema_with_new_label_rejects(self):
        self.manifest['schema_version'] = '1.0.0'
        self.assertRejected('schema_version must equal 2.0.0')

    def test_wrong_chain_rejects(self):
        self.manifest['chain_identifier'] = '137'
        self.assertRejected('chain_identifier must equal 80002')

    def test_missing_package_rejects(self):
        del self.manifest['restricted_evm']
        self.assertRejected('package is missing')

    def test_package_fields_are_closed(self):
        self.package['allow_mock_proofs'] = True
        self.assertRejected('package fields are invalid')

    def test_every_required_dependency_must_be_present(self):
        required = {'VAMSRestrictedStaking', 'ServiceBlockRegistry', 'ProviderBondRegistry',
                    'RestrictedTestnetPolicyV1', 'ActionDeliveryVerifierV1',
                    'AutomataSgxActionVerifierV1', 'EzklActionVerifierV1', 'ComposedSettlement'}
        original = copy.deepcopy(self.manifest['artifacts'])
        for name in sorted(required):
            with self.subTest(name=name):
                self.manifest['artifacts'] = [a for a in original if a['name'] != name]
                self.assertRejected('missing deployment artifacts')
        self.manifest['artifacts'] = original

    def test_unrestricted_staking_cannot_replace_restricted(self):
        artifact = next(a for a in self.manifest['artifacts'] if a['name'] == 'VAMSRestrictedStaking')
        artifact['name'] = 'VAMSStaking'
        self.assertRejected('missing deployment artifacts')

    def test_ordinary_governor_artifact_rejects(self):
        self.manifest['artifacts'].append({'name': 'VAMSGovernor'})
        self.assertRejected('unexpected deployment artifacts')

    def test_extra_proposer_rejects(self):
        role = copy.deepcopy(self.manifest['timelock_identity']['roles'][1])
        role.update(role='PROPOSER_ROLE', account=fixtures._evm_address(9999), granted=True)
        self.manifest['timelock_identity']['roles'].append(role)
        self.assertRejected('unexpected role assignments')

    def test_every_constructor_binding_must_match(self):
        original = copy.deepcopy(self.package['bindings'])
        for name, fields in original.items():
            for field in fields:
                with self.subTest(artifact=name, field=field):
                    self.package['bindings'] = copy.deepcopy(original)
                    self.package['bindings'][name][field] = 'wrong-identity'
                    self.assertRejected('constructor/configuration bindings')
        self.package['bindings'] = original

    def test_zero_runtime_identity_rejects(self):
        self.manifest['artifacts'][0]['runtime_code_hash'] = '0x' + '0' * 64
        self.assertRejected('runtime identity must be nonzero')

    def test_staking_minter_grant_rejects(self):
        staking = next(a['address'] for a in self.manifest['artifacts'] if a['name'] == 'VAMSRestrictedStaking')
        self.package['role_memberships']['VAMSToken']['MINTER_ROLE'] = [staking]
        self.assertRejected('role memberships differ')

    def test_slash_grant_rejects(self):
        self.package['role_memberships']['ProviderBondRegistry']['SLASHER_ROLE'] = [fixtures._evm_address(555)]
        self.assertRejected('role memberships differ')

    def test_other_escrow_role_rejects(self):
        self.package['role_memberships']['ProviderBondRegistry']['ESCROW_ROLE'] = [fixtures._evm_address(555)]
        self.assertRejected('exact settlement ESCROW_ROLE')

    def test_additional_escrow_role_rejects(self):
        self.package['role_memberships']['ProviderBondRegistry']['ESCROW_ROLE'].append(fixtures._evm_address(555))
        self.assertRejected('exact settlement ESCROW_ROLE')

    def test_missing_role_inventory_rejects(self):
        del self.package['role_memberships']['VAMSToken']['MINTER_ROLE']
        self.assertRejected('role memberships differ')

    def test_every_disabled_route_rejects_activation(self):
        original = dict(self.package['activation'])
        for key, value in original.items():
            with self.subTest(route=key):
                self.package['activation'] = dict(original)
                self.package['activation'][key] = True if type(value) is bool else 1
                self.assertRejected('restricted activation')
        self.package['activation'] = original

    def test_bool_float_cannot_replace_integer_zero(self):
        for value in (False, 0.0):
            with self.subTest(value=repr(value)):
                self.package['activation']['annual_emission_budget'] = value
                self.assertRejected('restricted activation')

    def test_missing_unknown_activation_fields_reject(self):
        self.package['activation']['future_permission'] = False
        self.assertRejected('restricted activation')

    def test_missing_parameters_rejects(self):
        self.package['parameters'] = None
        self.assertRejected('parameters are missing or invalid')

    def test_unknown_parameter_rejects(self):
        self.package['parameters']['hardware_fallback'] = 'tdx'
        self.assertRejected('parameters are missing or invalid')

    def test_zero_measurement_rejects(self):
        self.package['parameters']['sgx']['enclave_measurement'] = '0x' + '0' * 64
        self.assertRejected('SGX enclave_measurement is invalid')

    def test_bad_or_missing_sgx_fields_rejects(self):
        self.package['parameters']['sgx'] = []
        self.assertRejected('SGX parameters are invalid')

    def test_tcb_boolean_overflow_zero_rejects(self):
        for value in (True, 0, 2**32):
            with self.subTest(value=value):
                self.package['parameters']['sgx']['tcb_evaluation'] = value
                self.assertRejected('tcb_evaluation is invalid')

    def test_svn_boolean_negative_overflow_rejects(self):
        for value in (False, -1, 2**16):
            with self.subTest(value=value):
                self.package['parameters']['sgx']['minimum_svn'] = value
                self.assertRejected('minimum_svn is invalid')

    def test_zero_or_unknown_ezkl_model_rejects(self):
        self.package['parameters']['ezkl']['model_hash'] = 'UNKNOWN'
        self.assertRejected('EZKL model_hash is invalid')

    def test_missing_qualification_reference_rejects(self):
        del self.package['records']['dcap_qualification']
        self.assertRejected('records must cover')

    def test_substituted_record_bytes_rejects(self):
        reference = self.package['records']['ezkl_qualification']
        (self.root / reference['path']).write_bytes(b'substituted')
        self.assertRejected('ezkl_qualification record is missing')

    def test_missing_empty_record_rejects(self):
        (self.root / self.package['records']['state_readback']['path']).write_bytes(b'')
        self.assertRejected('state_readback record is missing')

    def test_record_path_escapes_and_windows_forms_reject(self):
        for path in ('../outside.json', '/tmp/outside.json', 'C:/outside.json',
                     'docs/audit/evidence/polygon-restricted-v1/../../outside.json',
                     'docs\\audit\\evidence\\polygon-restricted-v1\\build.json'):
            with self.subTest(path=path):
                self.package['records']['build']['path'] = path
                self.assertRejected('build record is missing')

    def test_same_record_cannot_cover_every_scope(self):
        self.package['records']['ezkl_qualification'] = dict(self.package['records']['dcap_qualification'])
        self.assertRejected('requires distinct scoped evidence records')

    def test_references_resolve_all_six_scopes(self):
        from scripts.audit import polygon_restricted_release as package
        paths = package.referenced_paths(self.manifest, self.root)
        self.assertEqual(len(paths), 6)
        self.assertEqual({p.stem for p in paths}, {'build', 'state_readback', 'activation_tests',
            'dcap_qualification', 'ezkl_qualification', 'insurance_custody'})

    def test_signed_aggregate_must_bind_direct_records(self):
        from scripts.audit import polygon_restricted_release as package
        paths = package.referenced_paths(self.manifest, self.root)
        manifest_path = self.root / 'aggregate.json'
        manifest_path.write_text('{"evidence_artifacts":[]}', encoding='utf-8')
        with mock.patch.object(subject, 'ROOT', self.root):
            errors = subject._validate_manifest_artifact_binding(manifest_path, paths)
        self.assertEqual(len(errors), 6)

    def test_public_keeps_additional_artifact_and_observation_requirements(self):
        errors = errors_for(self.root, self.manifest, 'public')
        self.assertTrue(any('missing deployment artifacts' in e for e in errors))
        self.assertTrue(any('deployment_status=deployed' in e for e in errors))
        self.assertTrue(any('public transaction_hash' in e for e in errors))

    def test_generator_includes_direct_record_hashes(self):
        evidence_dir = self.root / 'docs/audit/evidence'
        package_path = evidence_dir / 'polygon-amoy.json'
        package_path.write_text(json.dumps(self.manifest), encoding='utf-8')
        matrix = Path(__file__).resolve().parents[2] / 'docs/audit/control-matrix.json'
        output = evidence_dir / 'aggregate.json'
        with mock.patch.multiple(subject, ROOT=self.root, MATRIX_PATH=matrix, EVIDENCE_DIR=evidence_dir), \
             mock.patch.object(subject, '_git', return_value='a' * 40):
            subject.generate_manifest(output, [name + '=success' for name in subject.REQUIRED_EVIDENCE_RESULTS])
        aggregate = json.loads(output.read_text())
        observed = {item['path']: item['sha256'] for item in aggregate['evidence_artifacts']}
        for reference in self.package['records'].values():
            self.assertEqual(observed[reference['path']], reference['sha256'])
