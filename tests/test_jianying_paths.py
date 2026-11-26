import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import jianying_paths as paths
import tenniscut as core


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.profile = self.root / 'profile.json'
        self.env = patch.dict(os.environ, {'TENNISCUT_JIANYING_PROFILE': str(self.profile)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def draft_root(self, name='drafts'):
        root = self.root / name
        (root / 'existing').mkdir(parents=True)
        (root / 'existing/draft_meta_info.json').write_text('{}')
        (root / 'existing/draft_content.json').write_text('{}')
        return root

    def test_existing_root_discovered_without_modifying_existing_drafts(self):
        root = self.draft_root()
        before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        r = paths.discover(candidates=[root], check_write=True)
        self.assertEqual(r['selected_root'], str(root))
        self.assertTrue(r['attempts'][0]['writable'])
        after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(self.profile.exists())

    def test_root_index_is_only_read(self):
        root = self.root / 'indexed'; root.mkdir()
        index = root / 'root_meta_info.json'; index.write_text('{"all_draft_store": []}')
        self.assertTrue(paths.inspect_root(root)['directory_verified'])
        self.assertEqual(index.read_text(), '{"all_draft_store": []}')

    def test_empty_and_missing_folders_are_not_automatically_created_or_selected(self):
        empty = self.root / 'empty'; empty.mkdir()
        missing = self.root / 'absent'
        r = paths.discover(candidates=[empty, missing])
        self.assertIsNone(r['selected_root'])
        self.assertEqual([x['status'] for x in r['attempts']], ['unverified_structure', 'not_found'])
        self.assertFalse(missing.exists())

    def test_permission_failure_is_not_reported_as_absence(self):
        with patch.object(paths.os, 'scandir', side_effect=PermissionError('blocked')):
            r = paths.discover(explicit=self.root, check_write=True)
        self.assertEqual(r['status'], 'permission_denied')
        self.assertFalse(r['attempts'][0]['writable'])

    def test_write_denial_prevents_selection(self):
        root = self.draft_root()
        with patch.object(paths.tempfile, 'TemporaryFile', side_effect=PermissionError('read only')):
            r = paths.discover(explicit=root, check_write=True)
        self.assertIsNone(r['selected_root'])
        self.assertEqual(r['status'], 'permission_denied')

    def test_ambiguous_candidates_require_selection(self):
        r = paths.discover(candidates=[self.draft_root('one'), self.draft_root('two')])
        self.assertEqual(r['status'], 'ambiguous')
        self.assertIsNone(r['selected_root'])

    def test_explicit_failure_does_not_silently_switch_roots(self):
        valid = self.draft_root()
        r = paths.discover(explicit=self.root / 'missing', candidates=[valid])
        self.assertIsNone(r['selected_root'])
        self.assertEqual(len(r['attempts']), 1)

    def test_remembered_root_revalidated_and_stale_root_can_recover(self):
        root = self.draft_root()
        paths.remember(root)
        self.assertEqual(paths.discover(candidates=[])['selected_root'], str(root))
        (root / 'existing/draft_content.json').unlink()
        replacement = self.draft_root('replacement')
        r = paths.discover(candidates=[replacement])
        self.assertEqual(r['selected_root'], str(replacement))
        self.assertTrue(r['warnings'])
        self.assertFalse(json.loads(self.profile.read_text())['app_open_verified'])

    def test_unverified_root_cannot_be_remembered(self):
        with self.assertRaises(core.CutError):
            paths.remember(self.root)
        self.assertFalse(self.profile.exists())

    def test_default_search_does_not_include_capcut_or_scan_entire_home(self):
        mac = paths.default_candidates(self.root, 'Darwin')
        self.assertEqual(mac, [self.root / 'Movies/JianyingPro/User Data/Projects/com.lveditor.draft'])
        with patch.dict(os.environ, {'LOCALAPPDATA': str(self.root / 'local')}):
            win = paths.default_candidates(self.root, 'Windows')
        self.assertEqual(win, [self.root / 'local/JianyingPro/User Data/Projects/com.lveditor.draft'])
        self.assertEqual(paths.default_candidates(self.root, 'Linux'), [])


if __name__ == '__main__':
    unittest.main()
