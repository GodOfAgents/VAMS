"""Actual local S-MMU diagnostics/file boundaries, not live storage qualification."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from neuron.sdk import semantic_mmu as module

MARK = 'PRIVATE_SYNTHETIC_MARKER_43'
ADDRESS = 'workflows/' + MARK + '/page'
CANONICAL_SOURCE_FALLBACK = None  # Isolated source-overlay runner may bind this.


class SemanticMMUBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='vams-mmu43-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'memory'
        self.root.mkdir()
        self.memory_root = patch.object(module, 'MEMORY_ROOT', self.root)
        self.memory_root.start();self.addCleanup(self.memory_root.stop)
        # Optional provider discovery is outside local file/log evidence.
        self.providers = patch.object(module.SemanticMMU, '_init_providers', return_value=None)
        self.providers.start();self.addCleanup(self.providers.stop)
        self.mmu = module.SemanticMMU(l1_capacity=1, session_id=MARK,
            review_authorizer=lambda action, reviewer: reviewer == 'local-review-fixture')

    def assert_private_absent(self, logs, *extra):
        output = '\n'.join(logs.output)
        for marker in (MARK, str(self.root), *extra):
            self.assertNotIn(marker, output)

    def trace(self):
        path = self.root / (MARK + '.trace')
        path.write_text('success done\ntx ' + MARK + '\nerror ' + MARK, encoding='utf-8')
        return path

    def test_store_flush_fetch_logs_do_not_export_identifiers_or_hash_prefixes(self):
        with self.assertLogs(module.logger, level='DEBUG') as logs:
            page = self.mmu.store(ADDRESS, {'result': MARK})
            self.mmu.store('other/page', 'other')  # Demotes ADDRESS to L2.
            self.assertEqual(self.mmu.fetch(ADDRESS).content, {'result': MARK})
            self.mmu.flush_to_l3(ADDRESS)
            self.mmu._l1_cache.clear();self.mmu._l2_store.clear();self.mmu._l3_store.clear()
            self.assertEqual(self.mmu.fetch(ADDRESS).content, {'result': MARK})
            self.assertIsNone(self.mmu.fetch('missing/' + MARK))
        self.assert_private_absent(logs, page.content_hash, page.content_hash[:12])

    def test_hipif_read_error_is_generic_in_log_and_return(self):
        trace = self.trace()
        with patch.object(Path, 'open', side_effect=OSError(MARK)), self.assertLogs(module.logger, level='ERROR') as logs:
            result = self.mmu.fold_completed_subtask(MARK, str(trace))
        self.assertEqual(result, 'HIPIF folding failed.')
        self.assertTrue(trace.exists())
        self.assert_private_absent(logs)

    def test_hipif_does_not_delete_trace_or_publish_summary_after_write_failure(self):
        trace = self.trace()
        with patch.object(module.json, 'dump', side_effect=OSError(MARK)), self.assertLogs(module.logger, level='ERROR') as logs:
            result = self.mmu.fold_completed_subtask(MARK, str(trace))
        self.assertTrue(trace.exists())
        self.assertEqual(result, 'HIPIF folding failed.')
        self.assertNotIn('workflows/' + MARK + '/folded_summary', self.mmu._l3_store)
        self.assert_private_absent(logs)

    def test_failed_replacement_preserves_previous_file_and_cached_page(self):
        old = self.mmu.store(ADDRESS, {'version': 'old'}, tier=module.MemoryTier.L3_STORAGE)
        path = self.mmu._memory_path(ADDRESS);before = path.read_bytes()
        def partial_dump(value, stream, *args, **kwargs):
            stream.write('partial ' + MARK)
            raise OSError(MARK)
        with patch.object(module.json, 'dump', side_effect=partial_dump), self.assertLogs(module.logger, level='ERROR') as logs:
            try:self.mmu.store(ADDRESS, {'version': 'new'}, tier=module.MemoryTier.L3_STORAGE)
            except RuntimeError as error:
                self.assertNotIn(MARK, str(error))
            else:self.fail('persistence failure must reject the store')
        self.assertEqual(path.read_bytes(), before)
        self.assertIs(self.mmu._l3_store[ADDRESS], old)
        self.assert_private_absent(logs)

    def test_checkpoint_content_and_access_metadata_survive_without_log_disclosure(self):
        record = SimpleNamespace(nonce=7, provider=MARK, escrow_id=b'fixture-id', amount_wei=9, expires_at=100)
        payload = {'intent': MARK}
        with self.assertLogs(module.logger, level='DEBUG') as logs:
            self.mmu.checkpoint_interrupt_state(MARK, record, payload)
            restored = self.mmu.restore_interrupt_state(MARK)
        self.assertEqual(restored['request_payload'], payload)
        self.assertEqual(restored['provider'], MARK)
        self.assertEqual(restored['escrow_id'], b'fixture-id'.hex())
        access = self.mmu.get_access_log()
        expected = hashlib.sha256(('_irq_checkpoint/' + MARK).encode()).hexdigest()
        self.assertEqual(access[0]['address_hash'], expected)
        self.assertEqual(access[0]['session_id'], MARK)
        self.assert_private_absent(logs, expected)

    def test_complete_document_encoding_and_hashes_are_preserved(self):
        page = self.mmu.store(ADDRESS, {'result': 'success', 'nested': [MARK]},
            tier=module.MemoryTier.L3_STORAGE, provenance=MARK)
        stored = json.loads(self.mmu._memory_path(ADDRESS).read_text())
        self.assertEqual(set(stored), {'address', 'content', 'content_hash', 'tier', 'provenance',
            'value_score', 'access_count', 'last_accessed', 'created_at'})
        self.assertEqual(stored['address'], ADDRESS)
        self.assertEqual(stored['content'], page.content)
        self.assertEqual(stored['content_hash'], self.mmu._hash_content(page.content))
        self.assertTrue(page.verify())
        self.assertEqual(stored['provenance'], MARK)
        self.assertEqual(list(self.mmu._memory_path(ADDRESS).parent.glob('.vams-mmu-*.tmp')), [])

    def test_fsync_failure_preserves_old_file_cache_and_removes_owned_temp(self):
        old = self.mmu.store(ADDRESS, 'old', tier=module.MemoryTier.L3_STORAGE)
        path = self.mmu._memory_path(ADDRESS);before = path.read_bytes()
        with patch.object(module.os, 'fsync', side_effect=OSError(MARK)), self.assertLogs(module.logger, level='ERROR') as logs:
            with self.assertRaises(module.MMUPersistenceError) as error:
                self.mmu.store(ADDRESS, 'new', tier=module.MemoryTier.L3_STORAGE)
        self.assertEqual(str(error.exception), 'S-MMU L3 persistence failed')
        self.assertTrue(error.exception.__suppress_context__)
        self.assertEqual(path.read_bytes(), before)
        self.assertIs(self.mmu._l3_store[ADDRESS], old)
        self.assertEqual(list(path.parent.glob('.vams-mmu-*.tmp')), [])
        self.assert_private_absent(logs)

    def test_replace_failure_preserves_old_file_and_does_not_remove_unrelated_file(self):
        old = self.mmu.store(ADDRESS, 'old', tier=module.MemoryTier.L3_STORAGE)
        path = self.mmu._memory_path(ADDRESS);before = path.read_bytes()
        unrelated = path.parent / '.vams-mmu-unrelated.tmp';unrelated.write_text(MARK)
        with patch.object(module.os, 'replace', side_effect=OSError(MARK)), self.assertLogs(module.logger, level='ERROR') as logs:
            with self.assertRaises(module.MMUPersistenceError):
                self.mmu.store(ADDRESS, 'new', tier=module.MemoryTier.L3_STORAGE)
        self.assertEqual(path.read_bytes(), before)
        self.assertIs(self.mmu._l3_store[ADDRESS], old)
        self.assertEqual(unrelated.read_text(), MARK)
        self.assertEqual(list(path.parent.glob('.vams-mmu-*.tmp')), [unrelated])
        self.assert_private_absent(logs)

    def test_flush_does_not_publish_l3_when_persistence_fails(self):
        original = self.mmu.store(ADDRESS, MARK)
        with patch.object(module.json, 'dump', side_effect=OSError(MARK)), self.assertLogs(module.logger, level='ERROR') as logs:
            with self.assertRaises(module.MMUPersistenceError):
                self.mmu.flush_to_l3(ADDRESS)
        self.assertNotIn(ADDRESS, self.mmu._l3_store)
        self.assertIs(self.mmu._l1_cache[ADDRESS], original)
        self.assert_private_absent(logs)

    def test_hipif_success_preserves_summary_content_and_deletes_trace_after_write(self):
        trace = self.trace();target = self.mmu._memory_path('workflows/' + MARK + '/folded_summary')
        original_unlink = Path.unlink
        def checked_unlink(path, *args, **kwargs):
            if path == trace:
                stored = json.loads(target.read_text())
                self.assertIn(MARK, stored['content'])
            return original_unlink(path, *args, **kwargs)
        with patch.object(Path, 'unlink', checked_unlink), self.assertLogs(module.logger, level='DEBUG') as logs:
            summary = self.mmu.fold_completed_subtask(MARK, str(trace))
        self.assertIn('Status: SUCCESS', summary)
        self.assertIn(MARK, summary)  # Actual memory content remains available.
        self.assertFalse(trace.exists())
        self.assertEqual(json.loads(target.read_text())['content'], summary)
        self.assert_private_absent(logs)

    def test_hipif_unlink_failure_keeps_trace_and_returns_generic_error(self):
        trace = self.trace()
        with patch.object(Path, 'unlink', side_effect=OSError(MARK)), self.assertLogs(module.logger, level='DEBUG') as logs:
            result = self.mmu.fold_completed_subtask(MARK, str(trace))
        self.assertEqual(result, 'HIPIF folding failed.')
        self.assertTrue(trace.exists())
        self.assertIn('workflows/' + MARK + '/folded_summary', self.mmu._l3_store)
        self.assert_private_absent(logs)

    def test_hipif_resolution_failure_returns_generic_error(self):
        trace = self.trace()
        with patch.object(Path, 'resolve', side_effect=OSError(MARK)), self.assertLogs(module.logger, level='ERROR') as logs:
            result = self.mmu.fold_completed_subtask(MARK, str(trace))
        self.assertEqual(result, 'HIPIF folding failed.')
        self.assert_private_absent(logs)

    def test_patch_review_gate_content_and_diagnostics_are_preserved(self):
        payload = dict(previous_state=MARK, new_state='reviewed', rationale_for_change='fixture', supporting_evidence=MARK)
        with self.assertLogs(module.logger, level='DEBUG') as logs:
            self.assertFalse(self.mmu.apply_memory_patch(ADDRESS, payload, review_approved=True, reviewed_by='unauthorized-fixture'))
            self.assertTrue(self.mmu.apply_memory_patch(ADDRESS, payload, review_approved=True, reviewed_by='local-review-fixture'))
        stored = json.loads((self.root / 'patches' / (ADDRESS.replace('/', '_') + '.jsonl')).read_text())
        self.assertEqual(stored['previous_state'], MARK)
        self.assertEqual(stored['supporting_evidence'], MARK)
        self.assertEqual(stored['session_id'], MARK)
        self.assert_private_absent(logs)

    def test_patch_directory_failure_is_generic(self):
        payload = dict(previous_state=MARK, new_state=MARK, rationale_for_change=MARK, supporting_evidence=MARK)
        with patch.object(Path, 'mkdir', side_effect=OSError(MARK)), self.assertLogs(module.logger, level='ERROR') as logs:
            self.assertFalse(self.mmu.apply_memory_patch(ADDRESS, payload, review_approved=True, reviewed_by='local-review-fixture'))
        self.assert_private_absent(logs)

    def test_read_failure_and_integrity_fault_logs_have_no_identifiers(self):
        self.mmu.store(ADDRESS, MARK, tier=module.MemoryTier.L3_STORAGE)
        self.mmu._l3_store.clear()
        with patch.object(Path, 'open', side_effect=OSError(MARK)), self.assertLogs(module.logger, level='DEBUG') as logs:
            self.assertIsNone(self.mmu.fetch(ADDRESS))
        self.assert_private_absent(logs)
        self.mmu.store(ADDRESS, MARK, tier=module.MemoryTier.L2_RAM).content = 'tampered'
        self.mmu._l3_store[ADDRESS] = module.MemoryPage(ADDRESS, 'bad', 'bad-hash', module.MemoryTier.L3_STORAGE)
        with self.assertLogs(module.logger, level='DEBUG') as logs:
            self.assertIsNone(self.mmu.fetch(ADDRESS))
        self.assert_private_absent(logs)

    def test_reset_and_persistent_purge_review_gate_are_unchanged(self):
        self.mmu.store(ADDRESS, MARK, tier=module.MemoryTier.L3_STORAGE)
        self.mmu.store('session/' + MARK, MARK, tier=module.MemoryTier.L2_RAM)
        with self.assertRaises(PermissionError):
            self.mmu.hard_reset_session(purge_persistent=True, review_approved=True, reviewed_by='unauthorized-fixture')
        path = self.mmu._memory_path(ADDRESS);self.assertTrue(path.exists())
        result = self.mmu.hard_reset_session()
        self.assertEqual(result['old_session_hash'], hashlib.sha256(MARK.encode()).hexdigest())
        self.assertFalse(result['persistent_purged'])
        self.assertEqual(self.mmu.get_access_log(), [])
        self.assertTrue(path.exists())
        self.assertNotEqual(self.mmu.session_id, MARK)

    def test_path_validation_and_value_filter_are_unchanged(self):
        for address in ('../outside', '/absolute', 'empty//component', 'bad\\path'):
            with self.subTest(address=address), self.assertRaises(ValueError):
                self.mmu.store(address, MARK, tier=module.MemoryTier.L3_STORAGE)
        content = 'success completed'
        expected = round(0.4 + 0.3 + 0.2 * (len(content) / 5000) + 0.1 * 0.8, 3)
        self.assertEqual(self.mmu.evaluate_memory_value(content), expected)

    def test_inventory_source_hashes_and_all_line_anchors_match(self):
        root = Path(__file__).resolve().parents[2]
        artifact = json.loads((root / 'docs/remediation/privacy-field-inventory-20261020.json').read_text())
        def source(path):
            relative = Path(path)
            self.assertFalse(relative.is_absolute())
            self.assertNotIn('..', relative.parts)
            result = root / relative
            if not result.is_file() and CANONICAL_SOURCE_FALLBACK is not None:
                result = CANONICAL_SOURCE_FALLBACK / relative
            self.assertTrue(result.is_file(), path)
            return result
        for path, record in artifact['source_files'].items():
            with self.subTest(path=path):
                self.assertEqual(set(record), {'artifact', 'algorithm', 'digest'})
                self.assertEqual(record['artifact'], path)
                self.assertEqual(record['algorithm'], 'sha256')
                self.assertEqual(hashlib.sha256(source(path).read_bytes()).hexdigest(), record['digest'])
        for name, reference in artifact['source_references'].items():
            with self.subTest(anchor=name):
                self.assertIn(reference['path'], artifact['source_files'])
                lines = source(reference['path']).read_text().splitlines()
                start, end = reference['lines']
                self.assertTrue(1 <= start <= end <= len(lines))
                self.assertIn(reference['anchor'], '\n'.join(lines[start-1:end]))

    def test_inventory_preserves_unapproved_status_and_separate_final_manifest(self):
        root = Path(__file__).resolve().parents[2]
        artifact = json.loads((root / 'docs/remediation/privacy-field-inventory-20261020.json').read_text())
        self.assertEqual(artifact['review_status'], 'UNAPPROVED_SOURCE_BACKED_DRAFT')
        self.assertEqual(artifact['review_handoff']['T33_status'], 'BLOCKED')
        self.assertFalse(artifact['current_source_binding']['release_or_privacy_approval'])
        self.assertIsNone(artifact['current_source_binding']['final_candidate_manifest_sha256'])
        self.assertIn('21 SDK', ' '.join(artifact['scope']['limits']))


if __name__ == '__main__':
    unittest.main()
