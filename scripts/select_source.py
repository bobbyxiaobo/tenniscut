#!/usr/bin/env python3
"""Choose local tennis videos or a folder. Inspect only the chosen sources."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

VIDEO_SUFFIXES = {'.mp4', '.mov', '.m4v', '.mkv', '.avi', '.webm', '.mts', '.m2ts', '.mpg', '.mpeg'}
LIST_BUDGET = 3.0

MAC_PANEL = """ObjC.import('AppKit');
function run(argv) {
    const kind = argv[0];
    const app = $.NSApplication.sharedApplication;
    app.setActivationPolicy($.NSApplicationActivationPolicyAccessory);
    app.activateIgnoringOtherApps(true);
    const panel = $.NSOpenPanel.openPanel;
    panel.canChooseFiles = kind !== 'folder';
    panel.canChooseDirectories = kind !== 'files';
    panel.allowsMultipleSelection = kind !== 'folder';
    panel.canCreateDirectories = false;
    if (kind !== 'folder') panel.allowedFileTypes = $(argv[1].split(','));
    panel.message = kind === 'source' ? '选择一个或多个网球视频，或选择一个文件夹' :
                    kind === 'files' ? '选择网球视频（可多选）' : '选择网球视频所在的文件夹';
    if (argv[2]) panel.directoryURL = $.NSURL.fileURLWithPath(argv[2]);
    if (panel.runModal !== $.NSModalResponseOK) return '[]';
    const urls = panel.URLs;
    const paths = [];
    for (let i = 0; i < urls.count; i++) paths.push(ObjC.unwrap(urls.objectAtIndex(i).path));
    return JSON.stringify(paths);
}"""

WINDOWS_SCRIPT = """$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Windows.Forms
$initial = $env:TENNISCUT_PICKER_INITIAL_DIR
if ($env:TENNISCUT_PICKER_KIND -eq 'files') {
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Multiselect = $true
    $dialog.Filter = 'Videos|' + $env:TENNISCUT_PICKER_EXTENSIONS
    if ($initial) { $dialog.InitialDirectory = $initial }
} else {
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = 'Select the folder containing your tennis videos'
    $dialog.ShowNewFolderButton = $false
    if ($initial) { $dialog.SelectedPath = $initial }
}
try {
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        if ($env:TENNISCUT_PICKER_KIND -eq 'files') {
            [Console]::Write((ConvertTo-Json -Compress -InputObject @($dialog.FileNames)))
        } else { [Console]::Write($dialog.SelectedPath) }
    }
} finally { $dialog.Dispose() }"""


class SelectionError(Exception):
    pass


def available_backends():
    system = platform.system()
    backends = []
    if system == 'Darwin' and shutil.which('osascript'):
        backends.append('macos')
    elif system == 'Windows' and any(shutil.which(x) for x in ['powershell.exe', 'powershell', 'pwsh']):
        backends.append('windows')
    elif system == 'Linux' and (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')) and shutil.which('zenity'):
        backends.append('zenity')
    if importlib.util.find_spec('tkinter') and (system in ('Darwin', 'Windows') or os.environ.get('DISPLAY')):
        backends.append('tk')
    return backends


def date_added(path):
    if sys.platform != 'darwin':
        return None
    # Darwin's getattrlist returns Finder's date added to the current directory,
    # even on an unindexed volume. Test the returned attribute bitmap first.
    import ctypes
    import struct
    added, returned = 0x10000000, 0x80000000
    attrs = struct.pack('=HH5I', 5, 0, returned | added, 0, 0, 0, 0)
    data = ctypes.create_string_buffer(40)
    if ctypes.CDLL(None).getattrlist(os.fsencode(path), attrs, data, len(data), 0):
        return None
    length, common, *other, seconds, nanos = struct.unpack('=6I2q', data.raw)
    if length == len(data) and common & added and seconds > 0:
        return seconds + nanos / 1e9
    return None


def file_entry(path):
    stat = path.stat()
    created = getattr(stat, 'st_birthtime', None)
    if created is None and os.name == 'nt':
        created = stat.st_ctime  # Creation time on pre-3.12 Windows Python.
    return {'name': path.name, 'path': str(path.resolve()), 'size_bytes': stat.st_size,
            'modified_epoch': stat.st_mtime, 'added_epoch': date_added(path),
            'created_epoch': created, 'duration_seconds': None}


def read_duration(path, ffprobe, mdls, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0 or not (ffprobe or mdls):
        return None, False
    if ffprobe:
        args = [ffprobe, '-v', 'error', '-protocol_whitelist', 'file', '-probesize', '131072',
                '-analyzeduration', '100000', '-show_entries', 'format=duration',
                '-of', 'default=nw=1:nk=1', '-i', path]
    else:
        args = [mdls, '-raw', '-name', 'kMDItemDurationSeconds', path]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=min(1.5, remaining))
        if result.returncode == 0:
            seconds = float(result.stdout.strip())
            if math.isfinite(seconds) and seconds > 0:
                return seconds, bool(ffprobe)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return None, bool(ffprobe)


def choice_label(entry):
    size = entry['size_bytes']
    size_label = f'{size / 1e9:.2f} GB' if size >= 1e9 else f'{size / 1e6:.1f} MB'
    date = entry['added_epoch']
    if date:
        date_label = '添加 ' + datetime.fromtimestamp(date).strftime('%Y-%m-%d %H:%M')
    elif entry['created_epoch']:
        date_label = '添加时间未知（创建 ' + datetime.fromtimestamp(entry['created_epoch']).strftime('%Y-%m-%d %H:%M') + '）'
    else:
        date_label = '添加时间未知'
    duration = entry['duration_seconds']
    duration_label = '时长未知'
    if duration is not None:
        minutes, seconds = divmod(int(duration + 0.5), 60)
        duration_label = '时长 ' + (f'{minutes // 60}:{minutes % 60:02}:{seconds:02}' if minutes >= 60 else f'{minutes:02}:{seconds:02}')
    return ' · '.join([entry['name'], size_label, date_label, duration_label])


def inspect_selection(paths, exclude=()):
    started = time.monotonic()
    roots = [Path(p).expanduser().resolve() for p in paths]
    directory = roots[0] if len(roots) == 1 and roots[0].is_dir() else None
    if directory is not None:
        excluded = {Path(p).expanduser().resolve() for p in exclude}
        try:
            videos = sorted((p for p in directory.iterdir() if not p.name.startswith('.')
                             and p.suffix.lower() in VIDEO_SUFFIXES and p.is_file() and p.resolve() not in excluded),
                            key=lambda p: p.name.casefold())
        except OSError as e:
            raise SelectionError('Cannot read this folder: ' + str(e)) from e
        next_step = 'select_source_files' if videos else 'choose_another_folder'
    else:
        if any(p.is_dir() for p in roots):
            raise SelectionError('请选择一个文件夹，或只选视频文件（可多选）。')
        for p in roots:
            if not p.is_file() or p.suffix.lower() not in VIDEO_SUFFIXES:
                raise SelectionError('Video not found or unsupported: ' + str(p))
        videos = list(dict.fromkeys(roots))
        next_step = 'collect_editing_settings'
    entries = [file_entry(p) for p in videos]
    media_read = False
    if directory is not None and entries:
        ffprobe = shutil.which('ffprobe')
        mdls = shutil.which('mdls') if sys.platform == 'darwin' else None
        deadline = started + LIST_BUDGET
        def probe(entry):
            return read_duration(entry['path'], ffprobe, mdls, deadline)
        with ThreadPoolExecutor(max_workers=min(4, len(entries))) as workers:
            for entry, (seconds, attempted_read) in zip(entries, workers.map(probe, entries)):
                entry['duration_seconds'] = seconds
                entry['choice_label'] = choice_label(entry)
                media_read |= attempted_read
    parents = {p.parent for p in videos}
    parent = directory or (parents.pop() if len(parents) == 1 else None)
    return {'status': 'selected', 'directory': str(parent) if parent else None, 'videos': entries,
            'files_selected': directory is None, 'recursive': False, 'host_permissions_changed': False,
            'media_uploaded': False, 'media_content_read': media_read, 'next_step': next_step,
            'elapsed_seconds': round(time.monotonic() - started, 6)}


def inspect_path(path, exclude=()):
    return inspect_selection([path], exclude)


def choose(backend='auto', initial=None, kind='folder'):
    available = available_backends()
    backend = available[0] if backend == 'auto' and available else backend
    if backend not in available:
        raise SelectionError('No requested GUI picker available. Provide accessible file or folder paths.')
    if kind == 'source' and backend != 'macos':
        raise SelectionError('此选择器分别提供选视频和选文件夹，请使用 files 或 folder。')
    initial_path = Path(initial).expanduser().resolve() if initial else None
    if initial_path and not initial_path.is_dir():
        raise SelectionError('Initial folder does not exist')
    extensions = sorted(VIDEO_SUFFIXES)
    if backend == 'tk':
        import tkinter
        from tkinter import filedialog
        try:
            window = tkinter.Tk()
            window.withdraw()
            try:
                opts = {'parent': window, 'initialdir': str(initial_path) if initial_path else None}
                if kind == 'files':
                    paths = filedialog.askopenfilenames(title='选择网球视频', filetypes=[
                        ('Videos', tuple('*' + s for ext in extensions for s in (ext, ext.upper()))),
                        ('All files', '*')], **opts)
                else:
                    folder = filedialog.askdirectory(title='选择网球视频所在的文件夹', mustexist=True, **opts)
                    paths = [folder] if folder else []
            finally:
                window.destroy()
        except (tkinter.TclError, OSError) as e:
            raise SelectionError('Cannot show local picker: ' + str(e)) from e
    else:
        environment = dict(os.environ)
        if backend == 'macos':
            command = [shutil.which('osascript'), '-l', 'JavaScript', '-e', MAC_PANEL,
                       kind, ','.join(s[1:] for s in extensions), str(initial_path or '')]
        elif backend == 'windows':
            shell = next(shutil.which(x) for x in ['powershell.exe', 'powershell', 'pwsh'] if shutil.which(x))
            command = [shell, '-NoProfile', '-STA', '-Command', WINDOWS_SCRIPT]
            environment.update(TENNISCUT_PICKER_KIND=kind, TENNISCUT_PICKER_INITIAL_DIR=str(initial_path or ''),
                               TENNISCUT_PICKER_EXTENSIONS=';'.join('*'+s for s in extensions))
        else:
            command = [shutil.which('zenity'), '--file-selection']
            if kind == 'folder':
                command += ['--directory', '--title=选择网球视频所在的文件夹']
            else:
                command += ['--title=选择网球视频']
            if initial_path:
                command += ['--filename', str(initial_path) + os.sep]
        result = subprocess.run(command, env=environment, capture_output=True, text=True, encoding='utf-8')
        output = result.stdout.removesuffix('\n').removesuffix('\r') if backend == 'zenity' else result.stdout
        if backend == 'zenity' and result.returncode == 1 and not result.stderr.strip():
            paths = []
        elif result.returncode:
            raise SelectionError('Picker failed: ' + result.stderr.strip())
        elif backend == 'macos' or (backend == 'windows' and kind == 'files'):
            paths = json.loads(output) if output.strip() else []
        else:
            paths = [output] if output else []
    if not paths:
        return {'status': 'cancelled', 'directory': None, 'videos': [],
                'host_permissions_changed': False, 'media_uploaded': False}
    return inspect_selection(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('capabilities')
    q = sub.add_parser('inspect')
    q.add_argument('path', nargs='+')
    q.add_argument('--exclude', action='append', default=[])
    q = sub.add_parser('choose')
    q.add_argument('--initial-dir')
    q.add_argument('--kind', choices=['source', 'files', 'folder'], default='folder',
                   help='source opens a combined macOS file/folder panel')
    q.add_argument('--backend', choices=['auto', 'macos', 'windows', 'zenity', 'tk'], default='auto')
    args = parser.parse_args()
    try:
        if args.command == 'capabilities':
            backends = available_backends()
            result = {'backends': backends, 'combined_file_folder_picker': 'macos' in backends,
                      'requires_local_graphical_session': True,
                      'permission_to_show_dialog_not_verified': True, 'opens_dialog': False}
        elif args.command == 'inspect':
            result = inspect_selection(args.path, args.exclude)
        else:
            result = choose(args.backend, args.initial_dir, args.kind)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (SelectionError, OSError, ValueError) as e:
        print(json.dumps({'status': 'error', 'error': str(e), 'media_uploaded': False}, ensure_ascii=False), file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
