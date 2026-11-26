"""Regression tests: review gates, correction lifecycle, caching, real FFmpeg IO.
Synthetic video tests verify mechanics, not tennis-recognition accuracy.
"""
import array
import argparse
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tenniscut', HERE / 'scripts/tenniscut.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def annotated(p, ident, start, end, contact_times):
    evidence = [e for e in p['evidence'].values() if start <= e['source_time'] <= end]
    evidence.sort(key=lambda e: e['source_time'])
    contacts = []
    for i, t in enumerate(contact_times):
        e = min(evidence, key=lambda e: abs(e['source_time'] - t))
        contacts.append({'time': t, 'side': 'near' if i % 2 == 0 else 'far',
                         'status': 'confirmed', 'evidence_ids': [e['id']]})
    return {'id': ident, 'source_id': p['sources'][0]['id'], 'start': start, 'end': end,
            'revision': 1, 'status': 'reviewed', 'contacts': contacts, 'resets': [],
            'uncertainties': [], 'continuity': {'confirmed': True,
                'note': 'Synthetic test annotations, not a real tennis review.',
                'reviewed_evidence_ids': [e['id'] for e in evidence],
                'start_evidence_ids': [evidence[0]['id']],
                'end_evidence_ids': [evidence[-1]['id']]}, 'history': []}

def fixture():
    p = {'schema_version': 1, 'sources': [{'id': 'video', 'duration': 40}], 'evidence': {}}
    for i in range(81):
        ident = 'e%d' % i
        p['evidence'][ident] = {'id': ident, 'source_id': 'video', 'source_time': i / 2,
             'purpose': 'review', 'sampling_fps': 2, 'crop': None}
    return p

class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.p = fixture()
        self.r = annotated(self.p, 'r1', 0, 29.5, [1 + i * 2 for i in range(14)])
    def test_recorded_new_feed_blocks_merged_four_plus_ten(self):
        self.r['resets'] = [7.5]
        report = m.evaluate(self.p, self.r, 10)
        self.assertFalse(report['eligible'])
        self.assertIn('new_feed_inside_rally_split_required', report['reasons'])
        with self.assertRaises(m.CutError):
            m.make_plan(Path('.'), self.p, [self.r], 10, 30)
    def test_split_short_is_excluded_long_is_kept(self):
        short = annotated(self.p, 'short', 0, 7.5, [1, 3, 5, 7])
        long = annotated(self.p, 'long', 7.5, 29.5, [8 + i * 2 for i in range(10)])
        self.assertEqual(m.evaluate(self.p, short, 10)['reasons'], ['below_threshold'])
        self.assertTrue(m.evaluate(self.p, long, 10)['eligible'])
    def test_unchecked_boundary_fails_even_if_fourteen_contacts(self):
        self.r['continuity']['confirmed'] = False
        self.assertIn('continuity_not_confirmed', m.evaluate(self.p, self.r, 10)['reasons'])
    def test_sparse_overview_not_valid_evidence(self):
        for e in self.p['evidence'].values():
            e.update(purpose='overview', sampling_fps=.25)
        self.assertFalse(m.evaluate(self.p, self.r, 10)['eligible'])
    def test_missing_middle_review_fails(self):
        self.r['continuity']['reviewed_evidence_ids'] = ['e0', 'e59']
        self.assertIn('review_coverage_gap', m.evaluate(self.p, self.r, 10)['reasons'])
    def test_threshold_counts_confirmed_contacts_only(self):
        self.r['contacts'] = self.r['contacts'][:10]
        self.r['contacts'][-1]['status'] = 'uncertain'
        self.assertEqual(m.evaluate(self.p, self.r, 10)['minimum_contacts'], 9)
        self.assertFalse(m.evaluate(self.p, self.r, 10)['eligible'])
    def test_duplicate_contacts_and_nonfinite_time_rejected(self):
        self.r['contacts'][1]['time'] = self.r['contacts'][0]['time']
        self.assertIn('contacts_not_strictly_ordered', m.evaluate(self.p, self.r, 10)['reasons'])
        self.r['start'] = float('nan')
        self.assertIn('invalid_range', m.evaluate(self.p, self.r, 10)['reasons'])
    def test_other_source_evidence_rejected(self):
        self.p['evidence']['e0']['source_id'] = 'other'
        self.assertIn('evidence_from_other_source', m.evaluate(self.p, self.r, 10)['reasons'])
    def test_covered_only_by_player_crop_rejected(self):
        for e in self.p['evidence'].values():
            e['crop'] = [0, 0, 100, 100]
        self.assertIn('full_interval_not_covered', m.evaluate(self.p, self.r, 10)['reasons'])
    def test_high_count_does_not_overrule_uncertainty(self):
        self.r['uncertainties'] = ['Possibly a new feed near 7.5s']
        self.assertFalse(m.evaluate(self.p, self.r, 10)['eligible'])
    def test_review_gate_cannot_detect_a_falsely_attested_feed(self):
        # Explicitly document the boundary: annotations with a missed reset can pass.
        # This is why real, independent visual benchmarking is still required.
        self.assertTrue(m.evaluate(self.p, self.r, 10)['eligible'])
    def test_changed_source_interval_and_encoding_change_cache_key(self):
        s = {'sha256': 'abc', 'color_transfer': 'bt709', 'audio_stream': 1}
        e = {'source_start': 7.5, 'frames': 660}
        key = m.stable(m.cache_spec(s, e, 2560, 1440, 30, 'version'))
        for ss, ee, w, h in [(dict(s, sha256='xyz'), e, 2560, 1440),
                             (s, dict(e, source_start=8), 2560, 1440),
                             (s, dict(e, frames=600), 2560, 1440),
                             (s, e, 1920, 1080)]:
            self.assertNotEqual(key, m.stable(m.cache_spec(ss, ee, w, h, 30, 'version')))
    def test_corrupt_existing_part_is_not_a_cache_hit(self):
        with tempfile.TemporaryDirectory() as td:
            part = Path(td) / 'part.mkv';part.write_bytes(b'original')
            m.save(str(part) + '.json', {'spec': {'a': 1}, 'sha256': m.sha(part)})
            self.assertTrue(m.cached_part_valid(part, {'a': 1}))
            part.write_bytes(b'wrong part')
            self.assertFalse(m.cached_part_valid(part, {'a': 1}))
    def test_corrupt_cache_metadata_is_a_miss(self):
        with tempfile.TemporaryDirectory() as td:
            part = Path(td) / 'part.mkv';part.write_bytes(b'original')
            Path(str(part) + '.json').write_text('{broken json')
            self.assertFalse(m.cached_part_valid(part, {'a': 1}))
    def test_locate_uses_export_snapshot_and_half_open_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'manifest.json'
            m.save(path, {'rallies': [dict(id='a', revision=1, source_id='v', source_start=10,
                source_end=12, output_start=0, output_end=2), dict(id='b', revision=3,
                source_id='v', source_start=30, source_end=33, output_start=2, output_end=5)]})
            args = type('A', (), {'manifest': str(path), 'time': '00:02'})()
            found = m.locate(args)
            self.assertEqual((found['rally_id'], found['source_time'], found['revision']), ('b', 30, 3))
    def test_initialization_never_overwrites_an_existing_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'rallies.json';p.write_text('[{"private_record": true}]')
            before = p.read_bytes()
            args = type('A', (), {'project': td, 'videos': []})()
            with self.assertRaises(m.CutError):
                m.init_project(args)
            self.assertEqual(before, p.read_bytes())
    def test_revision_retains_history_but_invalidates_review(self):
        with tempfile.TemporaryDirectory() as td:
            m.save(Path(td) / 'project.json', self.p)
            m.save(Path(td) / 'rallies.json', [self.r])
            args = type('A', (), {'project': td, 'id': 'r1', 'reason': 'Split at new feed',
                'start': '7.5', 'end': None, 'exclude': False})()
            revised = m.revise(args)
            self.assertEqual(revised['revision'], 2)
            self.assertEqual(revised['status'], 'draft')
            self.assertFalse(revised['continuity']['confirmed'])
            self.assertEqual(revised['history'][0]['previous']['start'], 0)

class ResolutionTests(unittest.TestCase):
    def setUp(self):
        self.p = {'sources': [
            {'id': 'landscape', 'width': 1920, 'height': 1080, 'rotation': 0},
            {'id': 'portrait', 'width': 1920, 'height': 1080, 'rotation': -90},
            {'id': 'unused', 'width': 3840, 'height': 2160}]}

    def test_source_default_uses_only_selected_sources(self):
        self.assertEqual(m.resolve_resolution('source', self.p, [{'source_id': 'landscape'}]), (1920, 1080))
        self.assertEqual(m.resolve_resolution(None, self.p, [{'source_id': 'portrait'}]), (1080, 1920))

    def test_mixed_sizes_require_a_deliberate_canvas(self):
        entries = [{'source_id': 'landscape'}, {'source_id': 'portrait'}]
        with self.assertRaisesRegex(m.CutError, 'different resolutions'):
            m.resolve_resolution('source', self.p, entries)
        self.assertEqual(m.resolve_resolution('2560x1440', self.p, entries), (2560, 1440))

    def test_invalid_size_is_rejected(self):
        for value in ('2K', '1921x1080', '0x1080'):
            with self.assertRaises(m.CutError):
                m.resolve_resolution(value, self.p, [{'source_id': 'landscape'}])

@unittest.skipUnless(os.environ.get('RALLYCUT_INTEGRATION') == '1', 'Set RALLYCUT_INTEGRATION=1 for real FFmpeg tests')
class FFmpegTests(unittest.TestCase):
    def cmd(self, *args):
        p = subprocess.run([sys.executable, str(HERE / 'scripts/tenniscut.py'), *map(str, args)], capture_output=True, text=True)
        if p.returncode:
            self.fail(p.stderr)
        return json.loads(p.stdout)
    def test_fast_overview_uses_source_pts_and_falls_back_for_sparse_keyframes(self):
        with tempfile.TemporaryDirectory(prefix='tenniscut-grid-') as td:
            root = Path(td)
            for gop, bframes, expected in [(12, 0, 'keyframes'), (12, 2, 'keyframes'),
                                           (24, 0, 'full_fallback'), (144, 2, 'full_fallback')]:
                case = '%d-%d' % (gop, bframes)
                video, project = root / (case + '.mp4'), root / case
                m.run([m.tool('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
                       'testsrc2=size=320x180:rate=24:duration=7', '-c:v', 'libx264',
                       '-g', gop, '-bf', bframes, '-sc_threshold', 0, '-threads', 2, video])
                source = self.cmd('init', project, video)['sources'][0]['id']
                args = ['extract', project, '--source', source, '--start', '.2', '--end',
                        '6.1', '--purpose', 'overview', '--fps', '.5']
                fast = self.cmd(*args, '--fast-overview')
                self.assertEqual(fast['decode_mode'], expected)
                self.assertTrue(self.cmd(*args, '--fast-overview')['cache_hit'])
                frames = m.load(fast['manifest'])['frames']
                self.assertTrue(all(f['purpose'] == 'overview' for f in frames))
                standard = self.cmd(*args)
                legacy = m.load(standard['manifest'])
                if expected == 'keyframes':
                    self.assertEqual([f['source_time'] for f in frames], [.5, 2.5, 4.5])
                else:
                    self.assertEqual([(f['source_time'], f['sha256']) for f in frames],
                                     [(f['source_time'], f['sha256']) for f in legacy['frames']])
                legacy.pop('decode_mode')
                m.save(standard['manifest'], legacy)
                restored = self.cmd(*args, '--fast-overview')
                self.assertTrue(restored['cache_hit'])
                self.assertEqual(restored['manifest'], standard['manifest'])
                self.assertEqual(restored['decode_mode'], 'full')
                denied = subprocess.run([sys.executable, str(HERE / 'scripts/tenniscut.py'),
                    'extract', str(project), '--source', source, '--start', '0', '--end', '2',
                    '--purpose', 'review', '--fps', '2', '--fast-overview'], capture_output=True, text=True)
                self.assertNotEqual(denied.returncode, 0)
                self.assertIn('--fast-overview requires', denied.stderr)

    def test_source_timestamps_incremental_render_and_audio_alignment(self):
        with tempfile.TemporaryDirectory(prefix='tenniscut-test-') as td:
            root = Path(td);video = root / "input 'with spaces'.mp4";project = root / 'project'
            m.run([m.tool('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=30:duration=8',
                '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000:duration=8',
                '-af', 'adelay=1000:all=1', '-t', '8', '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '2', '-c:a', 'aac', video])
            info = self.cmd('init', project, video);source = info['sources'][0]['id']
            extracted = self.cmd('extract', project, '--source', source, '--start', '0', '--end', '6', '--fps', '2')
            self.assertFalse(extracted['cache_hit'])
            self.assertTrue(self.cmd('extract', project, '--source', source, '--start', '0', '--end', '6', '--fps', '2')['cache_hit'])
            p = m.load(project / 'project.json')
            first = annotated(p, 'one', 0, 1.5, [.15, 1.1])
            second = annotated(p, 'two', 4, 5.5, [4.15, 5.1])
            m.save(project / 'rallies.json', [first, second])
            out = root / 'export.mp4'
            result = self.cmd('render', project, '--threshold', '2', '--out', out)
            self.assertEqual((result['rallies'], result['cache_hits'], result['duration']), (2, 0, 3))
            self.assertEqual(m.load(out.with_suffix('.manifest.json'))['resolution'], [320, 180])
            self.assertFalse(out.with_suffix('.html').exists())
            self.assertTrue(out.with_suffix('.csv').is_file())
            self.assertTrue(out.with_suffix('.manifest.json').is_file())
            again = self.cmd('render', project, '--threshold', '2', '--resolution', '320x180', '--out', root / 'again.mp4')
            self.assertEqual(again['cache_hits'], 2)
            # Verify initial source silence stays in place; resetting the first audible
            # packet to zero would incorrectly bring the tone forward by one second.
            pcm = subprocess.check_output([m.tool('ffmpeg'), '-v', 'error', '-i', str(out), '-map', '0:a:0', '-ar', '48000', '-ac', '1', '-f', 's16le', '-'])
            a = array.array('h');a.frombytes(pcm)
            def rms(t):
                values = a[int(t * 48000):int((t + .15) * 48000)]
                return math.sqrt(sum(x * x for x in values) / len(values))
            self.assertLess(rms(.25), 20)
            self.assertGreater(rms(1.2), 200)
            self.cmd('revise', project, '--id', 'one', '--start', '.5', '--reason', 'Trim start')
            records = m.load(project / 'rallies.json')
            self.assertEqual(records[0]['status'], 'draft')
            records[0] = annotated(p, 'one', .5, 1.5, [.6, 1.1]);records[0]['revision'] = 2
            m.save(project / 'rallies.json', records)
            changed = self.cmd('render', project, '--threshold', '2', '--resolution', '320x180', '--out', root / 'changed.mp4')
            self.assertEqual((changed['cache_hits'], changed['duration']), (1, 2.5))
            # A changed frame invalidates the evidence gate, not merely the cache.
            frame = min(p['evidence'].values(), key=lambda e: abs(e['source_time'] - .5))
            (project / frame['path']).write_bytes(b'corrupt')
            checks = self.cmd('validate', project, '--threshold', '2')
            self.assertFalse(checks['rallies'][0]['eligible'])
    def test_variable_frame_rate_evidence_uses_actual_pts(self):
        with tempfile.TemporaryDirectory(prefix='tenniscut-vfr-') as td:
            root = Path(td);video = root / 'vfr.mp4';project = root / 'project'
            m.run([m.tool('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=30:duration=3',
                '-vf', "select='not(mod(n,7))+not(mod(n,11))'", '-fps_mode', 'vfr', '-c:v', 'libx264', '-threads', '2', video])
            source = self.cmd('init', project, video)['sources'][0]['id']
            result = self.cmd('extract', project, '--source', source, '--start', '.3', '--end', '2.8', '--fps', '2')
            times = [f['source_time'] for f in m.load(result['manifest'])['frames']]
            raw = json.loads(m.run([m.tool('ffprobe'), '-v', 'error', '-select_streams', 'v:0', '-show_frames',
                 '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', video]).stdout)
            real = [float(f['best_effort_timestamp_time']) for f in raw['frames']]
            self.assertTrue(all(any(abs(t - x) < .00001 for x in real) for t in times))
            self.assertTrue(all(.3 <= t < 2.8 for t in times))
            self.assertTrue(any(abs((t - .3) * 2 - round((t - .3) * 2)) > .01 for t in times))
            # Denser VFR coverage, silent source, and a filename needing URL encoding.
            self.cmd('extract', project, '--source', source, '--start', '.3', '--end', '2.8', '--fps', '8')
            p = m.load(project / 'project.json')
            m.save(project / 'rallies.json', [annotated(p, 'silent', .3, 2.8, [.8, 1.8])])
            output = root / 'silent #1.mp4'
            self.cmd('render', project, '--threshold', '2', '--resolution', '320x180', '--out', output, '--viewer')
            exported = m.load(output.with_suffix('.manifest.json'))
            self.assertFalse(exported['source_files'][0]['original_audio_present'])
            self.assertIn('silent%20%231.mp4', output.with_suffix('.html').read_text())
            pcm = subprocess.check_output([m.tool('ffmpeg'), '-v', 'error', '-i', str(output), '-map', '0:a:0', '-f', 's16le', '-'])
            audio = array.array('h');audio.frombytes(pcm)
            self.assertTrue(audio and max(map(abs, audio)) <= 1)

    def test_batch_hashing_focus_sheets_and_source_change_detection(self):
        with tempfile.TemporaryDirectory(prefix='tenniscut-batch-') as td:
            root = Path(td);video = root / 'source.mp4';project = root / 'project'
            m.run([m.tool('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i',
                   'testsrc2=size=640x360:rate=30:duration=4', '-c:v', 'libx264',
                   '-preset', 'ultrafast', '-threads', '2', video])
            source = self.cmd('init', project, video)['sources'][0]['id']
            windows = root / 'windows.json'
            m.save(windows, [{'start': 0, 'end': 1}, {'start': 2, 'end': 3, 'fps': 6}])
            args = argparse.Namespace(project=str(project), source=source, windows=str(windows),
                                      fps=2, width=640, purpose='review', sheet_frames=6, max_frames=20)
            with patch.object(m, 'sha', wraps=m.sha) as hashes:
                result = m.extract_batch(args)
            source_reads = [call for call in hashes.call_args_list if Path(call.args[0]).resolve() == video.resolve()]
            self.assertEqual(len(source_reads), 2)
            self.assertEqual(len(result['windows']), 2)
            self.assertFalse(result['automatically_reviewed'])
            self.assertFalse(result['windows'][0]['cache_hit'])
            again = m.extract_batch(args)
            self.assertTrue(all(window['cache_hit'] for window in again['windows']))
            manifest = result['windows'][1]['manifest']
            focus = m.review_sheets(argparse.Namespace(project=str(project), manifest=manifest,
                                                       region=['0,0,160,180', '320,0,320,360']))
            self.assertTrue(focus['whole_frame_included'])
            self.assertFalse(focus['automatically_reviewed'])
            from PIL import Image
            with Image.open(focus['sheets'][0]) as image:
                self.assertEqual(image.width, 1920)
            self.assertEqual(len(m.load(project / 'project.json')['evidence']), result['frames'])
            # A changed original cannot reuse the batch verification, even at the same path.
            real_extract = m.extract
            def replace_source_after_first(job, _verified=None):
                value = real_extract(job, _verified)
                video.write_bytes(b'changed original')
                return value
            with patch.object(m, 'extract', side_effect=replace_source_after_first):
                with self.assertRaisesRegex(m.CutError, 'Source changed'):
                    m.extract_batch(args)


if __name__ == '__main__':
    unittest.main(verbosity=2)
