#!/usr/bin/env python3
"""Optional Jianying draft output from the same reviewed selection plan.
The target application must independently accept the generated draft.
"""
import argparse
import importlib
import json
import os
import sys
from pathlib import Path
import tempfile
import time
import uuid
import tenniscut as core
from session import resolve_threshold

def generate(args):
    root, project, rallies = core.project(args.project)
    threshold = resolve_threshold(root, args.threshold)
    core.verify_sources(project)
    plan = core.make_plan(root, project, rallies, threshold, args.fps, args.allow_pending)
    core.require(plan['rallies'], 'No eligible rallies')
    width, height = core.resolve_resolution(args.resolution, project, plan['rallies'])
    core.require(bool(args.name) and args.name not in ('.', '..') and not any(x in args.name for x in '/\\\x00'), 'Draft name must be a single folder name')
    destination = Path(args.draft_root).expanduser().resolve()
    final = destination / args.name
    core.require(not final.exists(), 'Draft already exists; choose a new name')
    try:
        draft = importlib.import_module('pyJianYingDraft')
    except ImportError as e:
        raise core.CutError('Optional draft dependency missing: install requirements-jianying.txt in the active Python environment') from e
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='tenniscut-draft-', dir=str(destination)) as td:
        folder = draft.DraftFolder(td)
        script = folder.create_draft(args.name, width, height, fps=args.fps, allow_replace=False)
        if hasattr(script, 'append_track'):
            script.append_track(draft.TrackSpec(draft.TrackType.video, 'tennis'))
        else:
            script.add_track(draft.TrackType.video, 'tennis')
        materials = {}
        for entry in plan['rallies']:
            source = core.get_source(project, entry['source_id'])
            if source['id'] not in materials:
                materials[source['id']] = draft.VideoMaterial(source['path'])
            start = round(entry['output_start'] * 1_000_000)
            end = round(entry['output_end'] * 1_000_000)
            source_start = round(entry['source_start'] * 1_000_000)
            segment = draft.VideoSegment(materials[source['id']], draft.trange(start, end - start),
                       source_timerange=draft.trange(source_start, end - start), volume=1.0)
            script.add_segment(segment, 'tennis')
        script.save()
        stage = Path(td) / args.name
        content = core.load(stage / 'draft_content.json')
        video_tracks = [t for t in content['tracks'] if t['type'] == 'video']
        core.require(len(video_tracks) == 1, 'Unexpected draft video track count')
        segments = video_tracks[0]['segments']
        core.require(len(segments) == len(plan['rallies']), 'Draft rally count mismatch')
        for segment, entry in zip(segments, plan['rallies']):
            target, source = segment['target_timerange'], segment['source_timerange']
            a, b = round(entry['output_start'] * 1e6), round(entry['output_end'] * 1e6)
            core.require(target == {'start': a, 'duration': b - a}, 'Draft placement mismatch')
            core.require(source == {'start': round(entry['source_start'] * 1e6), 'duration': b - a}, 'Draft source trim mismatch')
        core.require(content['duration'] == round(plan['duration'] * 1e6), 'Draft duration mismatch')
        meta_path = stage / 'draft_meta_info.json'
        meta = core.load(meta_path)
        stamp = round(time.time() * 1e6)
        meta.update(draft_id=str(uuid.uuid4()).upper(), draft_name=args.name,
                    draft_fold_path=str(final), draft_root_path=str(destination),
                    tm_duration=round(plan['duration'] * 1e6), tm_draft_create=stamp, tm_draft_modified=stamp)
        core.save(meta_path, meta)
        plan.update(output_kind='jianying_draft', resolution=[width, height],
                    draft_name=args.name, app_open_verified=False,
                    notes=['Uses original source media and embedded audio.',
                           'Generated draft is not automatically installed or guaranteed accepted by every Jianying version.',
                           'HDR appearance and final export settings must be verified in Jianying.'])
        core.save(stage / 'tenniscut-manifest.json', plan)
        # Atomic promotion of a new folder only; existing drafts are never replaced.
        core.require(not final.exists(), 'Draft destination appeared during generation; refusing to replace')
        os.rename(stage, final)
    return {'draft_folder': str(final), 'rallies': len(plan['rallies']),
            'duration': plan['duration'], 'structure_checks': 'passed', 'app_open_verified': False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project');parser.add_argument('--threshold', type=int)
    parser.add_argument('--fps', type=int, default=30);parser.add_argument('--resolution', default='source', help='source (default) or an explicit WIDTHxHEIGHT')
    parser.add_argument('--draft-root', required=True);parser.add_argument('--name', required=True)
    parser.add_argument('--allow-pending', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(generate(args), ensure_ascii=False, indent=2))
        return 0
    except (core.CutError, OSError, ValueError, KeyError, TypeError) as e:
        print(json.dumps({'error': str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
