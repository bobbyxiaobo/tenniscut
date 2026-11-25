#!/usr/bin/env python3
"""Persist intake choices and inspect optional dependencies without installing them."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tenniscut as core

DEFAULTS = {'minimum_contacts': 8, 'generate_jianying_draft': False, 'ask_every_time': True}
OPTION_KEYS = tuple(DEFAULTS)

def preferences_path():
    override = os.environ.get('TENNISCUT_PREFERENCES') or os.environ.get('TENNIS_RALLY_CUT_PREFERENCES')
    if override:
        return Path(override).expanduser().resolve()
    if platform.system() == 'Windows' and os.environ.get('APPDATA'):
        base = Path(os.environ['APPDATA'])
    else:
        base = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    return base / 'tenniscut' / 'preferences.json'

def read_preferences():
    path = preferences_path()
    if path.exists():
        return core.load(path)
    if not (os.environ.get('TENNISCUT_PREFERENCES') or os.environ.get('TENNIS_RALLY_CUT_PREFERENCES')):
        legacy = path.parent.parent / 'tennis-rally-cut' / 'preferences.json'
        if legacy.exists():
            return core.load(legacy)
    return {}

def project_choices(root):
    path = Path(root) / 'settings.json'
    return core.load(path) if path.exists() else {}

def choices(root):
    # Execution uses the project's confirmed snapshot before machine preferences.
    return dict(read_preferences(), **project_choices(root))

def complete(settings):
    n = settings.get('minimum_contacts')
    return (isinstance(n, int) and not isinstance(n, bool) and n > 0
            and isinstance(settings.get('generate_jianying_draft'), bool))

def configure(args):
    root = Path(args.project).expanduser().resolve()
    profile = read_preferences()
    previous = project_choices(root)
    baseline = choices(root) if getattr(args, 'resume', False) else (profile or previous)
    settings = {k: baseline[k] for k in OPTION_KEYS if k in baseline}
    if getattr(args, 'use_defaults', False):
        settings = dict(DEFAULTS, **settings)
    threshold = getattr(args, 'threshold', None)
    draft = getattr(args, 'jianying', None)
    asking = getattr(args, 'ask_every_time', None)
    core.require(any(v is not None for v in [threshold, draft, asking]) or getattr(args, 'use_defaults', False),
                 'Provide submitted answers or explicitly accept the displayed defaults with --use-defaults')
    if threshold is not None:
        core.require(isinstance(threshold, int) and not isinstance(threshold, bool) and threshold > 0,
                     'Threshold must be a positive integer')
        settings['minimum_contacts'] = threshold
    for value, key in [(draft, 'generate_jianying_draft'), (asking, 'ask_every_time')]:
        if value is not None:
            core.require(value in ('yes', 'no'), 'Boolean choices must be yes or no')
            settings[key] = value == 'yes'
    # Fixed policy. Keep the legacy field/CLI flag readable for old projects,
    # but do not let an old opt-out suppress the two questions on a new task.
    settings['ask_every_time'] = True
    settings.update(schema_version=2, counting_rule='both_players_combined_in_one_continuous_ball', updated=core.now())
    if complete(settings):
        # Persist only choices, never media paths/evidence, across future tasks/hosts.
        preference = {k: settings[k] for k in OPTION_KEYS}
        preference.update(schema_version=2, updated=core.now())
        try:
            if not getattr(args, 'project_only', False):
                core.save(preferences_path(), preference)
        except OSError as e:
            raise core.CutError('Cannot save reusable preferences at %s; choose a writable TENNISCUT_PREFERENCES path. No project snapshot was changed. %s' % (preferences_path(), e)) from e
        settings['intake_confirmed_at'] = core.now()
    core.save(root / 'settings.json', settings)
    return settings

def resolve_threshold(root, explicit=None):
    value = explicit if explicit is not None else choices(root).get('minimum_contacts')
    if not (isinstance(value, int) and not isinstance(value, bool) and value > 0):
        raise ValueError('Choose a minimum contact count first: session.py configure PROJECT --threshold N')
    return value

def startup_questions(settings):
    return [
        {'key': 'minimum_contacts', 'title': '拍数下限：双方合计至少几拍才保留？',
         'options': [{'label': '6 拍', 'value': 6}, {'label': '8 拍', 'value': 8},
                     {'label': '10 拍', 'value': 10}, {'label': '自定义', 'value': 'custom'}],
         'default': settings['minimum_contacts'], 'factory_default': 8,
         'custom_positive_integer': True},
        {'key': 'generate_jianying_draft', 'title': '是否同时生成剪映草稿？',
         'options': [{'label': '是', 'value': True}, {'label': '否', 'value': False}],
         'default': settings['generate_jianying_draft'], 'factory_default': False}]

def inspect(root, resume=False, overrides=None, intake_only=False):
    profile = read_preferences()
    local = project_choices(root)
    recorded = choices(root) if resume else (profile or local)
    settings = dict(DEFAULTS, **{k: recorded[k] for k in OPTION_KEYS if k in recorded})
    explicit = dict(overrides or {})
    core.require(set(explicit).issubset(OPTION_KEYS), 'Unknown option override')
    for key, value in explicit.items():
        if key == 'minimum_contacts':
            core.require(isinstance(value, int) and not isinstance(value, bool) and value > 0, 'Threshold must be a positive integer')
        else:
            core.require(isinstance(value, bool), 'Boolean option override must be true or false')
    settings.update(explicit)
    settings['ask_every_time'] = True
    ask = not resume
    questions = startup_questions(settings) if ask else []
    if resume and not complete(recorded):
        questions = [q for q in startup_questions(settings) if q['key'] not in recorded]
    questions = [q for q in questions if q['key'] not in explicit]
    snapshot_required = not resume and not questions and complete(settings)
    if intake_only:
        return {'settings': settings, 'questions': questions,
                'preferences_path': str(preferences_path()),
                'context': 'resume' if resume else 'new_task', 'explicit_overrides': explicit,
                'project_snapshot_required': snapshot_required,
                'dependency_check': 'deferred', 'installation_performed': False,
                'next_step': 'collect_missing_choices' if questions else
                             'snapshot_saved_choices' if snapshot_required else 'prepare_dependencies'}
    missing = []
    tools = {}
    for name in ['ffmpeg', 'ffprobe']:
        try:
            tools[name] = core.tool(name)
        except core.CutError:
            tools[name] = None
            missing.append(name)
    if not importlib.util.find_spec('PIL'):
        missing.append('Pillow')
    optional = None
    if settings.get('generate_jianying_draft'):
        optional = {'package': 'pyJianYingDraft',
                    'installed': importlib.util.find_spec('pyJianYingDraft') is not None,
                    'app_compatibility': 'Must verify on the user target Jianying version; file generation is not app acceptance.'}
        if not optional['installed']:
            missing.append('pyJianYingDraft (only for requested Jianying draft)')
    system = platform.system()
    manager = next((x for x in (['brew'] if system == 'Darwin' else
                   ['winget', 'choco'] if system == 'Windows' else ['apt-get', 'dnf', 'pacman']) if shutil.which(x)), None)
    commands = {'brew': ['brew', 'install', 'ffmpeg'],
                'winget': ['winget', 'install', '--exact', '--id', 'Gyan.FFmpeg'],
                'choco': ['choco', 'install', 'ffmpeg'],
                'apt-get': ['apt-get', 'install', 'ffmpeg'],
                'dnf': ['dnf', 'install', 'ffmpeg'],
                'pacman': ['pacman', '-S', 'ffmpeg']}
    return {'settings': settings, 'questions': questions, 'preferences_path': str(preferences_path()),
            'context': 'resume' if resume else 'new_task', 'explicit_overrides': explicit,
            'project_snapshot_required': snapshot_required, 'tools': tools,
            'missing_dependencies': missing, 'jianying': optional,
            'platform': system, 'existing_package_manager': manager,
            'ffmpeg_install_command_candidate': commands.get(manager),
            'installation_performed': False,
            'next_step': 'collect_missing_choices' if questions else 'snapshot_saved_choices' if snapshot_required else 'prepare_dependencies' if missing else 'verify_tools'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    q = sub.add_parser('inspect');q.add_argument('project');q.add_argument('--resume', action='store_true')
    q.add_argument('--threshold', type=int);q.add_argument('--jianying', choices=['yes', 'no']);q.add_argument('--ask-every-time', choices=['yes', 'no'])
    q.add_argument('--intake-only', action='store_true', help='Read choices only; defer dependency and package-manager discovery until after the question card')
    q = sub.add_parser('configure');q.add_argument('project')
    q.add_argument('--threshold', type=int);q.add_argument('--jianying', choices=['yes', 'no'])
    q.add_argument('--ask-every-time', choices=['yes', 'no']);q.add_argument('--use-defaults', action='store_true')
    q.add_argument('--resume', action='store_true');q.add_argument('--project-only', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'configure':
            result = configure(args)
        else:
            overrides = {}
            if args.threshold is not None: overrides['minimum_contacts'] = args.threshold
            if args.jianying is not None: overrides['generate_jianying_draft'] = args.jianying == 'yes'
            if args.ask_every_time is not None: overrides['ask_every_time'] = args.ask_every_time == 'yes'
            result = inspect(args.project, args.resume, overrides, intake_only=args.intake_only)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (core.CutError, OSError, ValueError) as e:
        print(json.dumps({'error': str(e)}, ensure_ascii=False), file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
