"""Folder selection behavior; subprocess-backed GUI calls are mocked, not shown."""
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import select_source as source

class SourceSelectionTests(unittest.TestCase):
    def test_directory_listing_is_nonrecursive_and_filters_known_exports(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            for name in ['A.MOV', '网球 2.mp4', '.hidden.mp4', 'notes.txt', 'export.mp4']:
                (root/name).write_bytes(b'fixture')
            (root/'nested').mkdir();(root/'nested/other.mp4').write_bytes(b'fixture')
            result=source.inspect_path(root,exclude=[root/'export.mp4'])
            self.assertEqual([v['name'] for v in result['videos']],['A.MOV','网球 2.mp4'])
            self.assertFalse(result['recursive']);self.assertFalse(result['media_uploaded'])
    def test_selected_path_preserves_unicode_apostrophes_and_trailing_space(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)/"网球 'video' ";folder.mkdir();(folder/'one.mov').write_bytes(b'fixture')
            completed=types.SimpleNamespace(returncode=0,stdout=json.dumps([str(folder)])+'\n',stderr='')
            with patch.object(source,'available_backends',return_value=['macos']),patch.object(source.shutil,'which',return_value='/usr/bin/osascript'),patch.object(source.subprocess,'run',return_value=completed):
                with patch.object(source, 'read_duration', return_value=(None, False)):
                    result=source.choose(kind='source')
            self.assertEqual(result['directory'],str(folder.resolve()))
            self.assertEqual(result['videos'][0]['name'],'one.mov')
    def test_cancel_does_not_fall_back_to_current_directory(self):
        completed=types.SimpleNamespace(returncode=0,stdout='',stderr='')
        with patch.object(source,'available_backends',return_value=['macos']),patch.object(source.shutil,'which',return_value='/usr/bin/osascript'),patch.object(source.subprocess,'run',return_value=completed):
            result=source.choose()
        self.assertEqual(result['status'],'cancelled');self.assertIsNone(result['directory'])
    def test_failure_or_no_gui_does_not_become_a_selection(self):
        with patch.object(source,'available_backends',return_value=[]):
            with self.assertRaises(source.SelectionError):source.choose()
        completed=types.SimpleNamespace(returncode=1,stdout='',stderr='operation not permitted')
        with patch.object(source,'available_backends',return_value=['macos']),patch.object(source.shutil,'which',return_value='/usr/bin/osascript'),patch.object(source.subprocess,'run',return_value=completed):
            with self.assertRaises(source.SelectionError):source.choose()
    def test_windows_initial_path_is_data_not_interpolated_script(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)/"video 'quoted'";folder.mkdir()
            completed=types.SimpleNamespace(returncode=0,stdout=str(folder),stderr='')
            with patch.object(source,'available_backends',return_value=['windows']),patch.object(source.shutil,'which',return_value='powershell.exe'),patch.object(source.subprocess,'run',return_value=completed) as call:
                source.choose(initial=folder)
            self.assertNotIn(str(folder),call.call_args.args[0][-1])
            self.assertEqual(call.call_args.kwargs['env']['TENNISCUT_PICKER_INITIAL_DIR'],str(folder.resolve()))
    def test_headless_zenity_error_is_not_a_user_cancellation(self):
        completed=types.SimpleNamespace(returncode=1,stdout='',stderr='cannot open display')
        with patch.object(source,'available_backends',return_value=['zenity']),patch.object(source.shutil,'which',return_value='zenity'),patch.object(source.subprocess,'run',return_value=completed):
            with self.assertRaises(source.SelectionError):source.choose()
    def test_empty_folder_requires_another_selection(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(source.inspect_path(td)['next_step'],'choose_another_folder')
    def test_invalid_path_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(source.SelectionError):source.inspect_path(Path(td)/'missing')

    def test_directory_can_list_large_files_without_metadata_tools(self):
        with tempfile.TemporaryDirectory() as td:
            video=Path(td)/'large.mp4'
            with video.open('wb') as f:f.truncate(5_000_000_000)
            with patch.object(source.shutil, 'which', return_value=None), patch.object(Path, 'open', side_effect=AssertionError('Do not read video contents')):
                listing=source.inspect_path(td)
                selected=source.inspect_path(video)
            self.assertEqual(listing['videos'][0]['size_bytes'],5_000_000_000)
            self.assertFalse(listing['files_selected'])
            self.assertEqual(listing['next_step'],'select_source_files')
            self.assertTrue(selected['files_selected'])
            self.assertEqual(selected['next_step'],'collect_editing_settings')
            self.assertFalse(selected['media_content_read'])
            self.assertGreaterEqual(selected['elapsed_seconds'],0)

    def test_multi_file_picker_skips_folder_and_probes(self):
        with tempfile.TemporaryDirectory() as td:
            files = [Path(td)/name for name in ["One '录像'.MOV", "Two.mp4"]]
            for f in files:
                f.touch()
            reply = types.SimpleNamespace(stdout=json.dumps([str(f) for f in files]), stderr='', returncode=0)
            for backend, kind in [('macos', 'source'), ('macos', 'files'), ('windows', 'files')]:
                with self.subTest(backend=backend, kind=kind), patch.object(source, 'available_backends', return_value=[backend]), \
                     patch.object(source.shutil, 'which', return_value='/picker'), \
                     patch.object(source.subprocess, 'run', return_value=reply), \
                     patch.object(source, 'read_duration', side_effect=AssertionError('No sibling probes')), \
                     patch.object(Path, 'iterdir', side_effect=AssertionError('No folder listing')):
                    result = source.choose(kind=kind)
                    self.assertEqual([v['path'] for v in result['videos']], [str(f.resolve()) for f in files])
                    self.assertEqual(result['next_step'], 'collect_editing_settings')

    def test_list_formats_real_fields_and_unavailable_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            for name in ['A.MOV', 'B.mov']:
                (Path(td)/name).touch()
            def probe(path, *args):
                return (3661.2, True) if path.endswith('A.MOV') else (None, True)
            with patch.object(source, 'date_added', side_effect=[1700000000, None]), \
                 patch.object(source, 'read_duration', side_effect=probe):
                result = source.inspect_path(td)
            a,b = result['videos']
            self.assertEqual(a['added_epoch'], 1700000000)
            self.assertIn('时长 1:01:01', a['choice_label'])
            self.assertIn('添加时间未知', b['choice_label'])
            self.assertIn('时长未知', b['choice_label'])
            self.assertTrue(result['media_content_read'])
            self.assertFalse(result['files_selected'])

    def test_budget_and_probe_errors_leave_candidate_selectable(self):
        with patch.object(source.subprocess, 'run', side_effect=AssertionError('deadline expired')):
            self.assertEqual(source.read_duration('x.mov', '/ffprobe', None, 0), (None, False))
        with patch.object(source.subprocess, 'run', side_effect=source.subprocess.TimeoutExpired('ffprobe', 1)):
            self.assertEqual(source.read_duration('x.mov', '/ffprobe', None, source.time.monotonic()+1), (None, True))
        with patch.object(source.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0, stdout='nan')):
            self.assertEqual(source.read_duration('x.mov', '/ffprobe', None, source.time.monotonic()+1), (None, True))

    def test_mixed_folder_and_file_is_not_treated_as_all_files(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td)/'A.mp4'
            f.touch()
            with self.assertRaises(source.SelectionError):
                source.inspect_selection([td, f])

if __name__=='__main__':unittest.main(verbosity=2)
