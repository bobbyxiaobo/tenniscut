#!/usr/bin/env python3
"""Local, evidence-gated tennis editing. Does not automatically recognize hits."""
import argparse
import copy
import csv
from argparse import Namespace
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import quote

VERSION = '0.7.2-beta.1'
PIPELINE_VERSION = 1

class CutError(Exception):
    pass

def require(ok, message):
    if not ok:
        raise CutError(message)

def now():
    return datetime.now(timezone.utc).isoformat()

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.writing')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)

def stable(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def seconds(value):
    try:
        parts = str(value).split(':')
        require(1 <= len(parts) <= 3, 'Time must be seconds, MM:SS or HH:MM:SS')
        result = 0.0
        for part in parts:
            n = float(part)
            require(math.isfinite(n) and n >= 0, 'Time must be finite and nonnegative')
            result = result * 60 + n
        return result
    except ValueError as e:
        raise CutError('Invalid time: ' + str(value)) from e

def number(n):
    return isinstance(n, (int, float)) and not isinstance(n, bool) and math.isfinite(n)

def tool(name):
    configured = os.environ.get(name.upper())
    candidates = [configured] if configured else [shutil.which(name),
        str(Path.home() / '.local/bin' / name), '/opt/homebrew/bin/' + name,
        '/usr/local/bin/' + name]
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return str(Path(candidate).resolve())
    raise CutError(name + ' not found; install it or set ' + name.upper())

def run(args, log=None):
    result = subprocess.run([str(a) for a in args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    if log:
        Path(log).write_text(result.stderr, encoding='utf-8')
    if result.returncode:
        # Keep full diagnostics local; do not dump source metadata (e.g. GPS).
        tail = '\n'.join(result.stderr.splitlines()[-8:])
        raise CutError('Command failed (' + Path(str(args[0])).name + '):\n' + tail)
    return result

def probe(path, count=False):
    args = [tool('ffprobe'), '-v', 'error']
    if count:
        args += ['-count_frames']
    return json.loads(run(args + ['-show_streams', '-show_format', '-of', 'json', path]).stdout)

def source_info(path, index):
    path = Path(path).expanduser().resolve()
    require(path.is_file(), 'Missing source: ' + str(path))
    info = probe(path)
    streams = info['streams']
    video = next((s for s in streams if s['codec_type'] == 'video'), None)
    require(video is not None, 'No video stream: ' + path.name)
    duration = float(info['format'].get('duration', video.get('duration', 0)))
    require(duration > 0, 'Unknown or empty source duration')
    digest = sha(path)
    return {'id': 'v%02d-%s' % (index, digest[:8]), 'path': str(path),
            'sha256': digest, 'size_bytes': path.stat().st_size,
            'duration': duration, 'timeline_origin': float(info['format'].get('start_time', 0)),
            'video_stream': video['index'],
            'audio_stream': next((s['index'] for s in streams if s['codec_type'] == 'audio'
                                  and s.get('codec_name') not in (None, 'none')), None),
            'width': video['width'], 'height': video['height'],
            'color_transfer': video.get('color_transfer', 'unknown'),
            'rotation': next((s.get('rotation', 0) for s in video.get('side_data_list', [])
                              if 'rotation' in s), 0)}

def project(path):
    root = Path(path).expanduser().resolve()
    p = load(root / 'project.json')
    require(p.get('schema_version') == 1, 'Unsupported project schema')
    return root, p, load(root / 'rallies.json')

def get_source(p, ident):
    match = next((s for s in p['sources'] if s['id'] == ident), None)
    require(match is not None, 'Unknown source ID: ' + ident)
    return match

def verify_sources(p):
    for s in p['sources']:
        path = Path(s['path'])
        require(path.is_file() and sha(path) == s['sha256'],
                'Source changed or missing: ' + s['id'] + '; initialize a new project')

def doctor():
    f = tool('ffmpeg')
    filters = run([f, '-hide_banner', '-filters']).stdout
    encoders = run([f, '-hide_banner', '-encoders']).stdout
    require('libx264' in encoders, 'FFmpeg needs the libx264 encoder')
    pillow = True
    try:
        import PIL  # noqa
    except ImportError:
        pillow = False
    return {'ffmpeg': f, 'ffprobe': tool('ffprobe'),
            'version': run([f, '-version']).stdout.splitlines()[0],
            'pillow_available': pillow, 'hdr_tonemap_available': all(
                name in filters for name in ['zscale', 'tonemap']),
            'automatic_hit_recognition': False}

def init_project(args):
    root = Path(args.project).expanduser().resolve()
    require(not any((root / name).exists() for name in ('project.json', 'rallies.json')), 'Project or ledger already exists; refusing to replace it')
    paths = [str(Path(p).expanduser().resolve()) for p in args.videos]
    require(len(paths) == len(set(paths)), 'Duplicate source paths')
    sources = [source_info(path, i + 1) for i, path in enumerate(paths)]
    save(root / 'project.json', {'schema_version': 1, 'created': now(),
         'counting_rule': 'Both players racket contacts in one continuous ball; new feeds reset; bounces, misses and hand tosses do not count.',
         'sources': sources, 'evidence': {}})
    save(root / 'rallies.json', [])
    return {'project': str(root), 'sources': [{'id': s['id'], 'file': Path(s['path']).name,
            'duration': s['duration']} for s in sources]}

def color_filter(source, width=None, height=None):
    if height:
        scale = 'scale=%d:%d:force_original_aspect_ratio=decrease:force_divisible_by=2' % (width, height)
    else:
        # Do not upscale analysis frames; autorotation is applied by FFmpeg.
        scale = "scale=w='min(%d,iw)':h=-2" % width
    hdr = source['color_transfer'] in ('arib-std-b67', 'smpte2084')
    if hdr:
        require(doctor()['hdr_tonemap_available'], 'HDR input needs FFmpeg zscale and tonemap filters')
        scale += ',zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,' \
                 'tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv'
    scale += ',format=yuv420p'
    if height:
        scale += ',pad=%d:%d:(ow-iw)/2:(oh-ih)/2,setsar=1' % (width, height)
    return scale

def source_fingerprint(path):
    stat = Path(path).stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)

def verify_extraction_source(source, verified=None):
    path = Path(source['path'])
    require(path.is_file(), 'Source changed or missing')
    fingerprint = source_fingerprint(path)
    if verified is not None and source['id'] in verified:
        require(verified[source['id']] == (source['sha256'], fingerprint), 'Source changed during extraction batch')
    else:
        require(sha(path) == source['sha256'] and source_fingerprint(path) == fingerprint, 'Source changed')
        if verified is not None:
            verified[source['id']] = (source['sha256'], fingerprint)

def overview_key_packets(source, first, last):
    """Read container timestamps without decoding images or assuming a constant frame rate."""
    packet_rows = run([tool('ffprobe'), '-v', 'error', '-select_streams', str(source['video_stream']),
                       '-read_intervals', '%.9f%%%.9f' % (first, last),
                       '-show_packets', '-show_entries', 'packet=pts_time,dts_time,flags',
                       '-of', 'csv=p=0', source['path']]).stdout
    key_times = set()
    same_decode_order = True
    for row in csv.reader(packet_rows.splitlines()):
        if len(row) < 3:
            continue
        pts, dts, flags = row[:3]
        if pts != dts or pts == 'N/A':
            same_decode_order = False
        if 'K' in flags and pts != 'N/A':
            key_times.add(float(pts))
    require(key_times, 'No timestamped key packets in the overview window')
    # Discarding packets before a decoder with reordered pictures can misassign their PTS.
    option = '-discard' if same_decode_order else '-skip_frame'
    return [option + ':%d' % source['video_stream'], 'nokey'], key_times

def decode_samples(source, start, end, fps, image_filters, stage, log, keyframes=False):
    origin = source['timeline_origin']
    first, last = start + origin, end + origin
    select = "isnan(prev_selected_t)+gte(t-prev_selected_t,%.9f)" % (1 / fps)
    input_options = []
    if keyframes:
        # Anchor each sample to the requested grid, so keyframe spacing cannot accumulate drift.
        bucket = 'floor((%s-(%.9f))*%.12g)'
        current, previous = (bucket % (name, first, fps) for name in ('t', 'prev_selected_t'))
        select = 'eq(key,1)*(isnan(prev_selected_t)+gt(%s,%s))' % (current, previous)
        input_options, key_times = overview_key_packets(source, first, last)
    filters = "trim=start=%.9f:end=%.9f,select='%s',%s,showinfo,setpts=PTS-STARTPTS" % (
        first, last, select, image_filters)
    result = run([tool('ffmpeg'), '-hide_banner', '-nostdin', '-copyts', '-ss', start,
                  '-t', end - start, *input_options, '-i', source['path'],
                  '-map', '0:%d' % source['video_stream'], '-vf', filters,
                  '-fps_mode', 'vfr', '-q:v', '2', '-an', str(stage / 'f-%06d.jpg')], log=log)
    packet_times = [float(x) for x in re.findall(
        r'\bn:\s*\d+\s+pts:\s*-?\d+\s+pts_time:([-+\d.eE]+)', result.stderr)]
    times = [t - origin for t in packet_times]
    files = sorted(stage.glob('f-*.jpg'))
    require(files and len(times) == len(files), 'Frame/PTS mismatch; inspect local extraction log')
    if keyframes:
        require(all(round(t, 6) in key_times for t in packet_times),
                'Decoded overview timestamps differ from source key packet timestamps')
        expected = math.ceil((end - start) * fps - 1e-9)
        tolerance = min(1.05, .25 / fps + .05)
        require(len(times) == expected and all(
            start <= t < end and -.000001 <= t - (start + i / fps) <= tolerance
            for i, t in enumerate(times)), 'Keyframes do not cover the requested overview grid')
    return files, times

def extract(args, _verified=None):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        raise CutError('Install Pillow: python3 -m pip install -r requirements.txt') from e
    root, p, _ = project(args.project)
    s = get_source(p, args.source)
    start, end = seconds(args.start), seconds(args.end)
    require(0 <= start < end <= s['duration'] + .001, 'Invalid extraction range')
    require(0 < args.fps <= 30 and 160 <= args.width <= 3840, 'Invalid fps or width')
    require(1 <= args.sheet_frames <= (30 if args.purpose == 'overview' else 6),
            'Review sheets allow at most 6 frames; overview sheets at most 30')
    require(args.purpose != 'review' or args.fps >= 2, 'Review evidence requires at least 2 fps')
    fast = getattr(args, 'fast_overview', False)
    require(not fast or (args.purpose == 'overview' and args.fps <= .5 and not args.crop),
            '--fast-overview requires full-court overview sampling at 0.5 fps or less')
    estimate = math.ceil((end - start) * args.fps)
    require(estimate <= args.max_frames, 'Frame budget exceeded (%d); narrow the range or explicitly increase --max-frames' % estimate)
    verify_extraction_source(s, _verified)
    crop = None
    if args.crop:
        try:
            crop = [int(v) for v in args.crop.split(',')]
        except ValueError as e:
            raise CutError('Crop is x,y,width,height in the displayed, autorotated source') from e
        require(len(crop) == 4 and min(crop[:2]) >= 0 and min(crop[2:]) > 0, 'Invalid crop')
    spec = {'source_sha256': s['sha256'], 'start': start, 'end': end, 'fps': args.fps,
            'width': args.width, 'crop': crop, 'purpose': args.purpose,
            'sheet_frames': args.sheet_frames, 'pipeline_version': PIPELINE_VERSION,
            'ffmpeg': run([tool('ffmpeg'), '-version']).stdout.splitlines()[0]}
    # A valid conventional overview already satisfies a fast request, including pre-upgrade caches.
    requested = dict(spec, overview_grid_version=1) if fast else spec
    for lookup in ([spec, requested] if fast else [spec]):
        key = stable(lookup)
        directory = root / 'cache/frames' / key
        manifest_path = directory / 'frames.json'
        if not manifest_path.exists():
            continue
        m = load(manifest_path)
        if (m['frames'] and m['sheets'] and all((directory / name).is_file() for name in m['sheets'])
                and all((root / f['path']).is_file() and sha(root / f['path']) == f['sha256'] for f in m['frames'])):
            p['evidence'].update({f['id']: f for f in m['frames']})
            save(root / 'project.json', p)
            return {'cache_hit': True, 'manifest': str(manifest_path), 'frames': len(m['frames']),
                    'decode_mode': m.get('decode_mode', 'full'),
                    'sheets': [str(directory / x) for x in m['sheets']]}
    directory.mkdir(parents=True, exist_ok=True)
    # Regenerate in staging; an interrupted extraction can never become a valid cache.
    with tempfile.TemporaryDirectory(prefix='extract-', dir=str(directory)) as td:
        stage = Path(td)
        filters = color_filter(s, args.width)
        if crop:
            x, y, width, height = crop
            filters = 'crop=%d:%d:%d:%d,' % (width, height, x, y) + filters
        mode = 'full'
        if fast:
            key_stage = stage / 'keyframes'
            key_stage.mkdir()
            try:
                files, pts = decode_samples(s, start, end, args.fps, filters, key_stage,
                                            directory / 'keyframes.log', keyframes=True)
                mode = 'keyframes'
            except CutError:
                mode = 'full_fallback'
        if mode != 'keyframes':
            files, pts = decode_samples(s, start, end, args.fps, filters, stage, directory / 'extract.log')
        frames = []
        for i, (file, t) in enumerate(zip(files, pts)):
            dest = directory / file.name
            os.replace(file, dest)
            with Image.open(dest) as im:
                dims = list(im.size)
            frames.append({'id': key[:16] + ':' + str(i + 1), 'source_id': s['id'],
                 'source_time': round(t, 6), 'path': str(dest.relative_to(root)),
                 'sha256': sha(dest), 'purpose': args.purpose, 'sampling_fps': args.fps,
                 'dimensions': dims, 'crop': crop})
    sheets = []
    font = ImageFont.load_default(size=18)
    for page in range(math.ceil(len(frames) / args.sheet_frames)):
        subset = frames[page * args.sheet_frames:(page + 1) * args.sheet_frames]
        columns = 2 if args.purpose == 'review' else min(4, len(subset))
        cell = 640 if args.purpose == 'review' else 400
        rows = math.ceil(len(subset) / columns)
        canvas = Image.new('RGB', (cell * columns, 400 * rows if args.purpose == 'review' else 260 * rows), '#17202b')
        draw = ImageDraw.Draw(canvas)
        ch = 400 if args.purpose == 'review' else 260
        for i, frame in enumerate(subset):
            x, y = i % columns * cell, i // columns * ch
            with Image.open(root / frame['path']) as im:
                im.thumbnail((cell, ch - 34))
                canvas.paste(im, (x + (cell - im.width) // 2, y + 32))
            draw.text((x + 6, y + 6), '%s SOURCE %.3fs #%s' % (s['id'], frame['source_time'], frame['id'].split(':')[-1]), font=font, fill='white')
        name = 'sheet-%04d.jpg' % (page + 1)
        canvas.save(directory / name, quality=94)
        sheets.append(name)
    m = {'spec': requested, 'decode_mode': mode, 'frames': frames, 'sheets': sheets}
    save(manifest_path, m)
    p['evidence'].update({f['id']: f for f in frames})
    save(root / 'project.json', p)
    return {'cache_hit': False, 'manifest': str(manifest_path), 'frames': len(frames), 'decode_mode': mode,
            'sheets': [str(directory / x) for x in sheets]}

def extract_batch(args):
    """One bounded request, with full source hashing at both batch boundaries."""
    root, p, _ = project(args.project)
    source = get_source(p, args.source)
    windows = load(args.windows)
    require(isinstance(windows, list) and 1 <= len(windows) <= 100, 'Windows must be a list of 1–100 ranges')
    jobs, estimate = [], 0
    for window in windows:
        require(isinstance(window, dict) and {'start', 'end'} <= set(window)
                and set(window) <= {'start', 'end', 'fps'}, 'Each window accepts start, end and optional fps only')
        start, end = seconds(window['start']), seconds(window['end'])
        fps = window.get('fps', args.fps)
        require(number(fps) and 0 < fps <= 30, 'Invalid window fps')
        require(0 <= start < end <= source['duration'] + .001, 'Invalid batch extraction range')
        require(args.purpose != 'review' or fps >= 2, 'Review evidence requires at least 2 fps')
        estimate += math.ceil((end - start) * fps)
        jobs.append(Namespace(project=str(root), source=args.source, start=start, end=end,
                             fps=fps, width=args.width, purpose=args.purpose,
                             sheet_frames=args.sheet_frames, max_frames=args.max_frames, crop=None))
    require(estimate <= args.max_frames, 'Batch frame budget exceeded (%d); narrow the candidate ranges' % estimate)
    verified, results = {}, []
    for job in jobs:
        results.append(dict(start=job.start, end=job.end, **extract(job, _verified=verified)))
    verify_extraction_source(source, verified)
    require(sha(source['path']) == source['sha256'], 'Source changed during extraction batch')
    verify_extraction_source(source, verified)
    return {'windows': results, 'frames': sum(r['frames'] for r in results),
            'source_hash_passes': 2, 'automatically_reviewed': False}

def review_sheets(args):
    """Full-court context and optional player crops from existing evidence."""
    from PIL import Image, ImageDraw, ImageFont
    root, p, _ = project(args.project)
    manifest = Path(args.manifest).expanduser().resolve()
    require(manifest.is_relative_to(root / 'cache/frames'), 'Manifest must be in this project frame cache')
    original = load(manifest)
    frames = original['frames']
    require(frames and all(f['purpose'] == 'review' and f['sampling_fps'] >= 2 and not f['crop'] for f in frames),
            'Focus sheets need full-frame review evidence')
    regions = []
    for value in args.region or []:
        rectangle = [int(v) for v in value.split(',')]
        require(len(rectangle) == 4 and min(rectangle[:2]) >= 0 and min(rectangle[2:]) > 0,
                'Region must be x,y,width,height in cached frame pixels')
        regions.append(rectangle)
    require(len(regions) <= 2, 'Use at most two player regions')
    for frame in frames:
        record = p['evidence'].get(frame['id'])
        require(record == frame, 'Frame is not registered in this project')
        path = (root / frame['path']).resolve()
        require(path.is_relative_to(root / 'cache/frames') and path.is_file() and sha(path) == frame['sha256'],
                'Frame is missing or changed')
        w, h = frame['dimensions']
        require(all(x + cw <= w and y + ch <= h for x, y, cw, ch in regions), 'Region extends beyond cached frame')
    directory = manifest.parent / ('focus-' + stable({'regions': regions})[:12])
    directory.mkdir(exist_ok=True)
    font = ImageFont.load_default(size=17)
    cell_width, cell_height = 320 * (1 + len(regions)), 220
    sheets = []
    for page in range(math.ceil(len(frames) / 6)):
        subset = frames[page * 6:(page + 1) * 6]
        canvas = Image.new('RGB', (cell_width * 2, cell_height * math.ceil(len(subset) / 2)), '#17202b')
        draw = ImageDraw.Draw(canvas)
        for i, frame in enumerate(subset):
            x, y = i % 2 * cell_width, i // 2 * cell_height
            draw.text((x + 4, y + 4), 'SOURCE %.3fs %s' % (frame['source_time'], frame['id']), font=font, fill='white')
            with Image.open(root / frame['path']) as image:
                panels = [image.copy()] + [image.crop((a, b, a + w, b + h)) for a, b, w, h in regions]
                for index, panel in enumerate(panels):
                    panel.thumbnail((316, 184))
                    canvas.paste(panel, (x + index * 320, y + 30))
        path = directory / ('sheet-%04d.jpg' % (page + 1))
        canvas.save(path, quality=94)
        sheets.append(str(path))
    save(directory / 'layout.json', {'original_manifest': str(manifest.relative_to(root)),
         'frame_ids': [f['id'] for f in frames], 'regions': regions,
         'whole_frame_included': True, 'automatically_reviewed': False})
    return {'sheets': sheets, 'frames': len(frames), 'whole_frame_included': True,
            'automatically_reviewed': False}

def add_rally(args):
    root, p, rallies = project(args.project)
    source = get_source(p, args.source)
    require(not any(r['id'] == args.id for r in rallies), 'Rally ID already exists')
    start, end = seconds(args.start), seconds(args.end)
    require(0 <= start < end <= source['duration'], 'Invalid rally range')
    rallies.append({'id': args.id, 'revision': 1, 'source_id': args.source,
        'start': start, 'end': end, 'status': 'draft', 'contacts': [], 'resets': [],
        'uncertainties': [], 'continuity': {'confirmed': False, 'note': '',
         'reviewed_evidence_ids': [], 'start_evidence_ids': [], 'end_evidence_ids': []},
        'history': []})
    save(root / 'rallies.json', rallies)
    return rallies[-1]

def revise(args):
    root, p, rallies = project(args.project)
    r = next((r for r in rallies if r['id'] == args.id), None)
    require(r is not None, 'Unknown rally')
    require(args.reason.strip(), 'A correction reason is required')
    before = copy.deepcopy({k: v for k, v in r.items() if k != 'history'})
    if args.exclude:
        r['status'] = 'excluded'
        r['exclusion_reason'] = args.reason
    else:
        a = seconds(args.start) if args.start is not None else r['start']
        b = seconds(args.end) if args.end is not None else r['end']
        require(0 <= a < b <= get_source(p, r['source_id'])['duration'], 'Invalid revised range')
        r.update(start=a, end=b, status='draft')
        r['contacts'] = [c for c in r['contacts'] if a <= c['time'] < b]
        r['resets'] = [t for t in r['resets'] if a < t < b]
        r['continuity'] = {'confirmed': False, 'note': '', 'reviewed_evidence_ids': [],
                           'start_evidence_ids': [], 'end_evidence_ids': []}
    r['revision'] += 1
    r['history'].append({'at': now(), 'reason': args.reason, 'previous': before})
    save(root / 'rallies.json', rallies)
    return r

def manual_basis(r):
    """Human decisions apply only to the exact annotation/revision reviewed."""
    return stable({k: v for k, v in r.items() if k not in ('history', 'manual_review')})

def evaluate(p, r, threshold, evidence_root=None):
    """Validate structure/evidence; semantic correctness remains a reviewer's judgment."""
    problems = []
    def check(ok, message):
        if not ok:
            problems.append(message)
    manual = r.get('manual_review')
    if manual:
        source = next((s for s in p['sources'] if s['id'] == r.get('source_id')), None)
        check(manual.get('basis_sha256') == manual_basis(r), 'stale_human_decision')
        check(bool(source) and manual.get('source_sha256') == source.get('sha256'), 'human_decision_source_changed')
        check(bool(manual.get('at')), 'missing_human_review_time')
        check(manual.get('origin') == 'human', 'invalid_human_review_origin')
        check(manual.get('decision') in ('keep', 'exclude', 'pending'), 'invalid_human_decision')
        count = manual.get('count')
        if manual.get('decision') == 'pending':
            return {'id': r.get('id'), 'eligible': False, 'minimum_contacts': 0,
                    'review_origin': 'human', 'reasons': sorted(set(problems + ['human_review_pending']))}
        if manual.get('decision') == 'exclude':
            check(bool(manual.get('note', '').strip()), 'missing_exclusion_reason')
            return {'id': r.get('id'), 'eligible': False, 'minimum_contacts': 0,
                    'review_origin': 'human', 'reasons': problems or ['explicitly_excluded']}
        a, b = r.get('start'), r.get('end')
        valid = number(a) and number(b) and 0 <= a < b and source and b <= source['duration'] + .001
        check(bool(valid), 'invalid_range')
        check(isinstance(count, int) and not isinstance(count, bool) and 1 <= count <= 10000, 'invalid_human_count')
        check(manual.get('continuity_confirmed') is True, 'human_continuity_not_confirmed')
        check(not r.get('resets', []), 'new_feed_inside_rally_split_required')
        if isinstance(count, int) and count < threshold:
            problems.append('below_threshold')
        return {'id': r.get('id'), 'eligible': not problems, 'minimum_contacts': count,
                'review_origin': 'human', 'reasons': sorted(set(problems))}
    if r.get('status') == 'excluded':
        check(bool(r.get('exclusion_reason', '').strip()), 'missing_exclusion_reason')
        return {'id': r.get('id'), 'eligible': False, 'minimum_contacts': 0,
                'reasons': problems or ['explicitly_excluded']}
    source = next((s for s in p['sources'] if s['id'] == r.get('source_id')), None)
    check(source is not None, 'unknown_source')
    a, b = r.get('start'), r.get('end')
    valid_range = number(a) and number(b) and 0 <= a < b and source and b <= source['duration'] + .001
    check(bool(valid_range), 'invalid_range')
    check(r.get('status') == 'reviewed', 'not_reviewed')
    check(not r.get('uncertainties', []), 'unresolved_uncertainty')
    check(not r.get('resets', []), 'new_feed_inside_rally_split_required')
    continuity = r.get('continuity', {})
    check(continuity.get('confirmed') is True, 'continuity_not_confirmed')
    check(bool(continuity.get('note', '').strip()), 'missing_continuity_note')
    evidence = p.get('evidence', {})
    checked = set()
    def evidence_for(ids):
        result = []
        check(isinstance(ids, list) and bool(ids), 'missing_evidence')
        if not isinstance(ids, list):
            return result
        for ident in ids:
            e = evidence.get(ident)
            check(e is not None, 'unknown_evidence:' + str(ident))
            if not e:
                continue
            check(e['source_id'] == r.get('source_id'), 'evidence_from_other_source')
            check(e.get('purpose') == 'review' and e.get('sampling_fps', 0) >= 2,
                  'overview_cannot_prove_contacts_or_boundaries')
            if evidence_root and ident not in checked:
                if not isinstance(e.get('path'), str):
                    check(False, 'missing_evidence_path:' + str(ident))
                else:
                    ep = (Path(evidence_root) / e['path']).resolve()
                    inside = ep.is_relative_to(Path(evidence_root).resolve())
                    check(inside, 'evidence_path_outside_project')
                    check(inside and ep.is_file() and sha(ep) == e.get('sha256'), 'missing_or_changed_evidence:' + str(ident))
                checked.add(ident)
            result.append(e)
        return result
    all_evidence = evidence_for(continuity.get('reviewed_evidence_ids', []))
    # Coverage must include full displayed frames, not solely a crop of one player.
    times = sorted(set(e['source_time'] for e in all_evidence if not e.get('crop')
                       and valid_range and a - .75 <= e['source_time'] <= b + .75))
    if valid_range:
        check(bool(times) and abs(times[0] - a) <= .75 and abs(times[-1] - b) <= .75,
              'full_interval_not_covered')
        check(bool(times) and all(y - x <= .76 for x, y in zip(times, times[1:])),
              'review_coverage_gap')
        for key, t in [('start_evidence_ids', a), ('end_evidence_ids', b)]:
            ends = evidence_for(continuity.get(key, []))
            check(any(abs(e['source_time'] - t) <= .75 for e in ends), 'boundary_evidence_not_near_' + key)
    confirmed = []
    previous_time, previous_contact = -1, None
    for c in r.get('contacts', []):
        t = c.get('time')
        valid_time = number(t) and valid_range and a <= t < b
        check(bool(valid_time), 'contact_outside_rally')
        check(number(t) and t > previous_time, 'contacts_not_strictly_ordered')
        if number(t):
            previous_time = t
        check(c.get('status') in ('confirmed', 'uncertain'), 'invalid_contact_status')
        check(c.get('side') in ('near', 'far', 'unknown'), 'invalid_contact_side')
        if c.get('status') == 'confirmed':
            check(c.get('side') in ('near', 'far'), 'confirmed_contact_needs_side')
            es = evidence_for(c.get('evidence_ids', []))
            check(valid_time and any(abs(e['source_time'] - t) <= .6 for e in es),
                  'contact_evidence_too_far')
            if previous_contact and previous_contact.get('status') == 'confirmed':
                check(c.get('side') != previous_contact.get('side'), 'consecutive_confirmed_contacts_same_side')
            confirmed.append(c)
        previous_contact = c
    if len(confirmed) < threshold:
        problems.append('below_threshold')
    return {'id': r.get('id'), 'eligible': not problems,
            'minimum_contacts': len(confirmed), 'reasons': sorted(set(problems))}

def make_plan(root, p, rallies, threshold, fps, allow_pending=False):
    require(threshold >= 1 and 1 <= fps <= 120, 'Invalid threshold or frame rate')
    require(len({r.get('id') for r in rallies}) == len(rallies), 'Duplicate rally IDs')
    reviews = [evaluate(p, r, threshold, root) for r in rallies]
    unresolved = [v for v in reviews if any(x not in ('below_threshold', 'explicitly_excluded') for x in v['reasons'])]
    require(allow_pending or not unresolved,
            'Unresolved review prevents export. Run validate; finish review, exclude it explicitly, or use --allow-pending for a labeled partial export.')
    good = {v['id']: v for v in reviews if v['eligible']}
    order = {s['id']: i for i, s in enumerate(p['sources'])}
    chosen = sorted((r for r in rallies if r['id'] in good), key=lambda r: (order[r['source_id']], r['start']))
    previous = {}
    entries, offset = [], 0.0
    for r in chosen:
        require(r['start'] >= previous.get(r['source_id'], -1), 'Overlapping selected rallies: ' + r['id'])
        previous[r['source_id']] = r['end']
        frames = math.floor((r['end'] - r['start']) * fps + 1e-6)
        require(frames > 0, 'Rally shorter than one output frame')
        duration = frames / fps
        # Quantization must never remove a confirmed contact at the very end.
        require(all(c['time'] < r['start'] + duration for c in r['contacts'] if c['status'] == 'confirmed') or good[r['id']].get('review_origin') == 'human',
                'End trim would remove a confirmed contact; extend the reviewed end')
        entries.append({'id': r['id'], 'revision': r.get('revision', 1), 'source_id': r['source_id'],
              'source_start': r['start'], 'source_end': r['start'] + duration,
              'requested_source_end': r['end'], 'output_start': offset,
              'output_end': offset + duration, 'frames': frames,
              'minimum_contacts': good[r['id']]['minimum_contacts'],
              'review_origin': good[r['id']].get('review_origin', 'agent_evidence'), 'annotation_sha256': stable(r)})
        offset += duration
    return {'schema_version': 1, 'threshold': threshold, 'fps': fps,
            'duration': offset, 'rallies': entries, 'decisions': reviews,
            'partial_export': bool(unresolved), 'coverage': 'reviewed_candidates_only',
            'semantic_accuracy_proven_by_program': False}

def cache_spec(source, entry, width, height, fps, ffmpeg_version):
    return {'source_sha256': source['sha256'], 'source_start': entry['source_start'],
            'frames': entry['frames'], 'fps': fps, 'width': width, 'height': height,
            'color_transfer': source['color_transfer'], 'audio_stream': source['audio_stream'],
            'crf': 18, 'preset': 'fast', 'audio': 'PCM 48000 stereo',
            'ffmpeg': ffmpeg_version, 'pipeline_version': PIPELINE_VERSION}

def cached_part_valid(path, spec):
    meta = Path(str(path) + '.json')
    try:
        record = load(meta) if meta.is_file() else {}
        return path.is_file() and record.get('spec') == spec and record.get('sha256') == sha(path)
    except (OSError, ValueError, TypeError):
        return False

def resolve_resolution(value, project_info, entries):
    """Use selected source display dimensions unless a canvas was requested."""
    if value is None or str(value).lower() in ('source', 'original'):
        dimensions = set()
        for ident in {entry['source_id'] for entry in entries}:
            source = get_source(project_info, ident)
            width, height = int(source['width']), int(source['height'])
            rotation = float(source.get('rotation', 0)) % 360
            require(any(abs(rotation - angle) < .01 for angle in (0, 90, 180, 270, 360)),
                    'Source rotation needs an explicit --resolution WIDTHxHEIGHT')
            if abs(rotation - 90) < .01 or abs(rotation - 270) < .01:
                width, height = height, width
            dimensions.add((width, height))
        require(len(dimensions) == 1,
                'Selected sources have different resolutions; export separately to preserve each source, '
                'or explicitly choose --resolution WIDTHxHEIGHT for a combined video')
        width, height = next(iter(dimensions))
    else:
        match = re.fullmatch(r'(\d+)[xX](\d+)', str(value))
        require(match is not None, 'Resolution must be source or WIDTHxHEIGHT')
        width, height = map(int, match.groups())
    require(width >= 160 and height >= 160 and width % 2 == height % 2 == 0,
            'Resolution must have even dimensions >=160; choose an explicit canvas if the source is unsupported')
    return width, height

def render(args):
    root, p, rallies = project(args.project)
    verify_sources(p)
    from session import resolve_threshold
    args.threshold = resolve_threshold(root, args.threshold)
    plan = make_plan(root, p, rallies, args.threshold, args.fps, args.allow_pending)
    require(plan['rallies'], 'No eligible rallies')
    width, height = resolve_resolution(args.resolution, p, plan['rallies'])
    output = Path(args.out).expanduser().resolve()
    require(output.suffix.lower() == '.mp4', 'Output must be an MP4 path')
    require(str(output) not in {s['path'] for s in p['sources']}, 'Cannot overwrite a source')
    viewer = getattr(args, 'viewer', False)
    artifacts = [output, output.with_suffix('.manifest.json'), output.with_suffix('.csv')]
    if viewer:
        artifacts.append(output.with_suffix('.html'))
    require(args.overwrite or not any(x.exists() for x in artifacts), 'Output artifacts exist; use a new name or --overwrite')
    output.parent.mkdir(parents=True, exist_ok=True)
    f = tool('ffmpeg');version = run([f, '-version']).stdout.splitlines()[0]
    cache = root / 'cache/render';cache.mkdir(parents=True, exist_ok=True)
    parts, hits = [], 0
    for entry in plan['rallies']:
        source = get_source(p, entry['source_id'])
        spec = cache_spec(source, entry, width, height, args.fps, version)
        part = cache / (stable(spec) + '.mkv')
        if cached_part_valid(part, spec):
            hits += 1
        else:
            duration = entry['frames'] / args.fps
            with tempfile.TemporaryDirectory(prefix='part-', dir=str(cache)) as td:
                tmp = Path(td) / 'part.mkv'
                cmd = [f, '-hide_banner', '-v', 'error', '-nostdin', '-ss', entry['source_start'], '-i', source['path']]
                if source['audio_stream'] is None:
                    cmd += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
                    audio = '1:a:0'
                else:
                    audio = '0:%d' % source['audio_stream']
                cmd += ['-map', '0:%d' % source['video_stream'], '-map', audio, '-t', duration,
                        '-vf', 'fps=%d:start_time=0,' % args.fps + color_filter(source, width, height),
                        '-af', 'aresample=48000:async=1:first_pts=0,aformat=sample_fmts=s16:channel_layouts=stereo,apad=whole_dur=%.9f,atrim=duration=%.9f' % (duration, duration),
                        '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-threads', '2',
                        '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
                        '-c:a', 'pcm_s16le', '-map_metadata', '-1', str(tmp)]
                run(cmd, log=cache / (stable(spec) + '.log'))
                pi = probe(tmp, count=True)
                vs = next(s for s in pi['streams'] if s['codec_type'] == 'video')
                require(int(vs['nb_read_frames']) == entry['frames'], 'Unexpected rendered frame count')
                os.replace(tmp, part)
                save(str(part) + '.json', {'spec': spec, 'sha256': sha(part)})
        parts.append(part)
    with tempfile.TemporaryDirectory(prefix='export-', dir=str(output.parent)) as td:
        stage = Path(td)
        # Use generated safe basenames; do not interpolate user paths into ffconcat syntax.
        local = []
        for i, part in enumerate(parts):
            link = stage / ('part-%05d.mkv' % i)
            try:
                os.link(part, link)
            except OSError:
                shutil.copy2(part, link)
            local.append(link.name)
        (stage / 'concat.txt').write_text(''.join("file '%s'\nduration %.9f\n" % (name, e['frames'] / args.fps) for name, e in zip(local, plan['rallies'])))
        chapters = ';FFMETADATA1\n' + ''.join('[CHAPTER]\nTIMEBASE=1/1000\nSTART=%d\nEND=%d\ntitle=Rally %d - at least %d contacts\n' %
              (round(e['output_start'] * 1000), round(e['output_end'] * 1000), i + 1, e['minimum_contacts']) for i, e in enumerate(plan['rallies']))
        (stage / 'chapters.txt').write_text(chapters)
        tmp = stage / 'video.mp4'
        run([f, '-hide_banner', '-v', 'error', '-nostdin', '-f', 'concat', '-safe', '1', '-i', stage / 'concat.txt',
             '-i', stage / 'chapters.txt', '-map', '0:v:0', '-map', '0:a:0', '-map_metadata', '1', '-map_chapters', '1',
             '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-t', plan['duration'], '-movflags', '+faststart', tmp])
        actual = probe(tmp, count=True)
        video = next(s for s in actual['streams'] if s['codec_type'] == 'video')
        require((video['width'], video['height']) == (width, height), 'Output dimension mismatch')
        require(int(video['nb_read_frames']) == sum(e['frames'] for e in plan['rallies']), 'Final frame count mismatch')
        require(abs(float(actual['format']['duration']) - plan['duration']) <= .05, 'Final duration mismatch')
        decoded = run([f, '-v', 'error', '-nostdin', '-i', tmp, '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'])
        require(not decoded.stderr.strip(), 'Final full decode reported errors')
        from session import choices
        requested_draft = choices(root).get('generate_jianying_draft', False)
        plan.update(jianying_draft_requested=requested_draft, jianying_draft_generated_by_render=False)
        plan.update(created=now(), skill_version=VERSION, resolution=[width, height],
                    output_file=output.name, output_sha256=sha(tmp), render_cache_hits=hits,
                    source_files=[{'id': s['id'], 'file': Path(s['path']).name, 'sha256': s['sha256'], 'original_audio_present': s['audio_stream'] is not None} for s in p['sources']],
                    technical_validation={'full_decode_errors': 0, 'frames': int(video['nb_read_frames']),
                    'audio': 'original or documented silence; AAC stereo; PCM segment concatenation',
                    'does_not_verify_hit_recognition': True})
        os.replace(tmp, output)
    save(output.with_suffix('.manifest.json'), plan)
    with output.with_suffix('.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(plan['rallies'][0]))
        writer.writeheader();writer.writerows(plan['rallies'])
    if viewer:
        buttons = ''.join('<tr><td><button onclick="seek(%s)">%s</button></td><td>%s</td><td>%.3f–%.3f</td><td>%d</td></tr>' %
             (e['output_start'], html.escape(str(e['id'])), html.escape(e['source_id']), e['source_start'], e['source_end'], e['minimum_contacts']) for e in plan['rallies'])
        page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>网球剪辑清单</title><style>body{max-width:1000px;margin:24px auto;font:16px system-ui}video{width:100%%}td,th{padding:12px;text-align:left}button{cursor:pointer}</style><h1>网球剪辑清单</h1><p>双方合计至少 %d 拍；仅包含已复核候选。程序检查不证明识别准确率。</p>%s<video id="v" controls src="%s"></video><table><tr><th>跳转回合</th><th>来源</th><th>原片秒数</th><th>确认至少拍数</th></tr>%s</table><script>function seek(t){const v=document.getElementById("v");v.currentTime=t;v.play()}</script></html>' % (args.threshold, '<p><strong>Partial export: some candidates remain unresolved.</strong></p>' if plan['partial_export'] else '', html.escape(quote(output.name), quote=True), buttons)
        output.with_suffix('.html').write_text(page, encoding='utf-8')
    save(root / 'last_export.json', {'output': str(output), 'manifest': str(output.with_suffix('.manifest.json'))})
    return {'output': str(output), 'manifest': str(output.with_suffix('.manifest.json')),
            'duration': plan['duration'], 'rallies': len(parts), 'cache_hits': hits,
            'next_action': 'generate_jianying_draft' if requested_draft else 'none'}

def locate(args):
    manifest = load(args.manifest)
    t = seconds(args.time)
    for e in manifest['rallies']:
        if e['output_start'] <= t < e['output_end']:
            return {'rally_id': e['id'], 'revision': e['revision'], 'source_id': e['source_id'],
                    'output_time': t, 'source_time': e['source_start'] + t - e['output_start'],
                    'source_range': [e['source_start'], e['source_end']]}
    raise CutError('Time outside exported video')

def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor')
    q = commands.add_parser('init');q.add_argument('project');q.add_argument('videos', nargs='+')
    q = commands.add_parser('extract');q.add_argument('project');q.add_argument('--source', required=True)
    q.add_argument('--start', required=True);q.add_argument('--end', required=True)
    q.add_argument('--fps', type=float, default=2);q.add_argument('--width', type=int, default=1280)
    q.add_argument('--purpose', choices=['overview', 'review'], default='review')
    q.add_argument('--sheet-frames', type=int, default=6);q.add_argument('--max-frames', type=int, default=600)
    q.add_argument('--crop')
    q.add_argument('--fast-overview', action='store_true', help='Use keyframes for sparse overview if every sampling slot is covered')
    q = commands.add_parser('extract-batch');q.add_argument('project');q.add_argument('--source', required=True)
    q.add_argument('--windows', required=True, help='JSON list of start/end ranges, optionally with fps')
    q.add_argument('--fps', type=float, default=2);q.add_argument('--width', type=int, default=1280)
    q.add_argument('--purpose', choices=['overview', 'review'], default='review')
    q.add_argument('--sheet-frames', type=int, default=6);q.add_argument('--max-frames', type=int, default=600)
    q = commands.add_parser('review-sheets');q.add_argument('project');q.add_argument('--manifest', required=True)
    q.add_argument('--region', action='append', help='Player crop x,y,width,height in cached-frame pixels (max 2)')
    q = commands.add_parser('add');q.add_argument('project');q.add_argument('--id', required=True)
    q.add_argument('--source', required=True);q.add_argument('--start', required=True);q.add_argument('--end', required=True)
    q = commands.add_parser('revise');q.add_argument('project');q.add_argument('--id', required=True)
    q.add_argument('--start');q.add_argument('--end');q.add_argument('--exclude', action='store_true');q.add_argument('--reason', required=True)
    for command in ['validate', 'plan', 'render']:
        q = commands.add_parser(command);q.add_argument('project');q.add_argument('--threshold', type=int)
        if command != 'validate':
            q.add_argument('--fps', type=int, default=30);q.add_argument('--allow-pending', action='store_true')
        if command == 'render':
            q.add_argument('--resolution', default='source', help='source (default) or an explicit WIDTHxHEIGHT');q.add_argument('--out', required=True);q.add_argument('--overwrite', action='store_true')
            q.add_argument('--viewer', action='store_true', help='Also generate the optional legacy HTML viewer')
    q = commands.add_parser('locate');q.add_argument('manifest');q.add_argument('--time', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'doctor':
            result = doctor()
        elif args.command == 'init':
            result = init_project(args)
        elif args.command == 'extract':
            result = extract(args)
        elif args.command == 'extract-batch':
            result = extract_batch(args)
        elif args.command == 'review-sheets':
            result = review_sheets(args)
        elif args.command == 'add':
            result = add_rally(args)
        elif args.command == 'revise':
            result = revise(args)
        elif args.command == 'locate':
            result = locate(args)
        elif args.command == 'render':
            result = render(args)
        else:
            root, p, rallies = project(args.project)
            from session import resolve_threshold
            args.threshold = resolve_threshold(root, args.threshold)
            if args.command == 'validate':
                result = {'rallies': [evaluate(p, r, args.threshold, root) for r in rallies],
                          'semantic_accuracy_proven_by_program': False}
            else:
                result = make_plan(root, p, rallies, args.threshold, args.fps, args.allow_pending)
                save(root / 'plan.json', result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (CutError, OSError, ValueError, KeyError, TypeError) as e:
        print(json.dumps({'error': str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    sys.exit(cli())
