"""Bounded Jianying-only draft-root discovery; never edits the app's index."""
import os
from pathlib import Path
import platform
import tempfile
import tenniscut as core
from session import preferences_path


def profile_path():
    value = os.environ.get('TENNISCUT_JIANYING_PROFILE')
    return Path(value).expanduser().resolve() if value else preferences_path().parent / 'jianying.json'


def default_candidates(home=None, system=None):
    home = Path(home) if home is not None else Path.home()
    system = system or platform.system()
    suffix = Path('User Data/Projects/com.lveditor.draft')
    if system == 'Darwin':
        return [home / 'Movies/JianyingPro' / suffix]
    if system == 'Windows':
        base = Path(os.environ.get('LOCALAPPDATA', str(home / 'AppData/Local')))
        return [base / 'JianyingPro' / suffix]
    return []


def inspect_root(path, check_write=False):
    path = Path(path).expanduser().resolve()
    result = {'path': str(path), 'directory_verified': False, 'write_checked': False,
              'writable': None, 'evidence': []}
    try:
        # scandir reports permission failures rather than treating them as absence.
        with os.scandir(path) as entries:
            for i, entry in enumerate(entries):
                if i >= 128:
                    result['scan_limited'] = True
                    break
                if entry.name == 'root_meta_info.json' and entry.is_file(follow_symlinks=False):
                    if isinstance(core.load(Path(entry.path)), dict):
                        result['evidence'].append('root_meta_info.json')
                elif entry.is_dir(follow_symlinks=False):
                    child = Path(entry.path)
                    if (child / 'draft_meta_info.json').is_file() and (child / 'draft_content.json').is_file():
                        result['evidence'].append('existing_draft_files')
                        break
        result['directory_verified'] = bool(result['evidence'])
        result['status'] = 'verified' if result['directory_verified'] else 'unverified_structure'
        if check_write:
            result['write_checked'] = True
            # A fresh probe only; no existing draft or index is written.
            with tempfile.TemporaryFile(prefix='.tenniscut-write-check-', dir=path):
                pass
            result['writable'] = True
    except FileNotFoundError:
        result['status'] = 'not_found'
    except NotADirectoryError:
        result['status'] = 'not_directory'
    except PermissionError as e:
        result.update(status='permission_denied', error=str(e))
        if check_write:
            result['writable'] = False
    except (OSError, ValueError) as e:
        result.update(status='inspection_failed', error=str(e))
    return result


def discover(explicit=None, check_write=False, candidates=None):
    attempts, warnings = [], []
    def inspect(path, origin):
        r = inspect_root(path, check_write)
        r['origin'] = origin
        attempts.append(r)
        return r
    def usable(r):
        return r['status'] == 'verified' and (not check_write or r['writable'] is True)
    if explicit:
        r = inspect(explicit, 'user_supplied')
        return {'status': 'selected' if usable(r) else r['status'],
                'selected_root': r['path'] if usable(r) else None, 'attempts': attempts, 'warnings': warnings}
    try:
        profile = core.load(profile_path())
        if profile.get('draft_root'):
            r = inspect(profile['draft_root'], 'remembered')
            if usable(r):
                return {'status': 'selected', 'selected_root': r['path'], 'attempts': attempts, 'warnings': warnings}
            warnings.append('Remembered root failed revalidation; checking standard locations.')
    except FileNotFoundError:
        pass
    except (OSError, ValueError, AttributeError) as e:
        warnings.append('Cannot read saved draft root: ' + str(e))
    seen = {r['path'] for r in attempts}
    for path in default_candidates() if candidates is None else candidates:
        path = str(Path(path).expanduser().resolve())
        if path not in seen:
            inspect(path, 'standard_location')
            seen.add(path)
    matches = [r for r in attempts if usable(r)]
    selected = matches[0]['path'] if len(matches) == 1 else None
    status = 'selected' if selected else ('ambiguous' if len(matches) > 1 else 'unresolved')
    return {'status': status, 'selected_root': selected, 'attempts': attempts, 'warnings': warnings}


def remember(path):
    result = inspect_root(path, check_write=True)
    core.require(result['status'] == 'verified' and result['writable'] is True,
                 'Cannot remember an unverified or unwritable draft root: ' + result['status'])
    core.save(profile_path(), {'draft_root': result['path'], 'verified_at': core.now(),
                               'app_open_verified': False})
    return {'saved': True, 'profile_path': str(profile_path()), 'draft_root': result['path']}
