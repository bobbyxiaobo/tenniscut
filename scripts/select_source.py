#!/usr/bin/env python3
"""Choose a local source folder or inspect an already supplied path.
Never uploads media or changes host filesystem permissions.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

VIDEO_SUFFIXES = {'.mp4', '.mov', '.m4v', '.mkv', '.avi', '.webm', '.mts', '.m2ts', '.mpg', '.mpeg'}
APPLE_SCRIPT = '''on run argv
    try
        if (count of argv) > 0 then
            set chosenFolder to choose folder with prompt "选择网球视频所在的文件夹" default location (POSIX file (item 1 of argv))
        else
            set chosenFolder to choose folder with prompt "选择网球视频所在的文件夹"
        end if
        return POSIX path of chosenFolder
    on error number -128
        return ""
    end try
end run'''
WINDOWS_SCRIPT = '''$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Select the folder containing your tennis videos'
$dialog.ShowNewFolderButton = $false
$initial = [Environment]::GetEnvironmentVariable('TENNISCUT_PICKER_INITIAL_DIR')
if ($initial) { $dialog.SelectedPath = $initial }
try {
    if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        [Console]::Write($dialog.SelectedPath)
    }
} finally { $dialog.Dispose() }'''

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

def inspect_path(path, exclude=()):
    started = time.monotonic()
    root = Path(path).expanduser().resolve()
    if root.is_file():
        if root.suffix.lower() not in VIDEO_SUFFIXES:
            raise SelectionError('Not a supported video file: ' + root.name)
        return {'status': 'selected', 'directory': str(root.parent),
                'videos': [file_entry(root)], 'files_selected': True,
                'recursive': False, 'host_permissions_changed': False,
                'media_uploaded': False, 'media_content_read': False,
                'elapsed_seconds': round(time.monotonic() - started, 6),
                'next_step': 'collect_editing_settings'}
    if not root.is_dir():
        raise SelectionError('Source directory does not exist or is not a folder: ' + str(root))
    excluded = {Path(p).expanduser().resolve() for p in exclude}
    try:
        files = sorted((p for p in root.iterdir() if not p.name.startswith('.') and p.is_file()
                        and p.suffix.lower() in VIDEO_SUFFIXES and p.resolve() not in excluded),
                       key=lambda p: p.name.casefold())
    except OSError as e:
        raise SelectionError('Cannot read this folder; request host folder/workspace access: ' + str(e)) from e
    return {'status': 'selected', 'directory': str(root),
            'videos': [file_entry(p) for p in files], 'files_selected': False,
            'recursive': False, 'host_permissions_changed': False,
            'media_uploaded': False, 'media_content_read': False,
            'elapsed_seconds': round(time.monotonic() - started, 6),
            'next_step': 'select_source_files' if files else 'choose_another_folder'}

def file_entry(path):
    """Metadata only: never probe, hash, decode, or open the media contents."""
    stat = path.stat()
    return {'name': path.name, 'path': str(path.resolve()),
            'size_bytes': stat.st_size, 'modified_epoch': stat.st_mtime}

def choose(backend='auto', initial=None):
    available = available_backends()
    if backend == 'auto':
        if not available:
            raise SelectionError('No local GUI picker is available. Use the client folder/workspace picker or provide an accessible path.')
        backend = available[0]
    if backend not in available:
        raise SelectionError('Requested folder picker is not available in this environment: ' + backend)
    initial_path = None
    if initial:
        initial_path = Path(initial).expanduser().resolve()
        if not initial_path.is_dir():
            raise SelectionError('Initial folder does not exist')
    if backend == 'tk':
        try:
            import tkinter
            from tkinter import filedialog
            window = tkinter.Tk();window.withdraw()
            try:
                selected = filedialog.askdirectory(parent=window, title='选择网球视频所在的文件夹',
                    initialdir=str(initial_path) if initial_path else None, mustexist=True)
            finally:
                window.destroy()
        except Exception as e:
            raise SelectionError('Cannot show local folder picker; use the client folder/workspace selector: ' + str(e)) from e
    else:
        environment = dict(os.environ)
        if backend == 'macos':
            command = [shutil.which('osascript'), '-e', APPLE_SCRIPT]
            if initial_path:
                command.append(str(initial_path))
        elif backend == 'windows':
            shell = next(shutil.which(x) for x in ['powershell.exe', 'powershell', 'pwsh'] if shutil.which(x))
            command = [shell, '-NoProfile', '-STA', '-Command', WINDOWS_SCRIPT]
            if initial_path:
                environment['TENNISCUT_PICKER_INITIAL_DIR'] = str(initial_path)
            else:
                environment.pop('TENNISCUT_PICKER_INITIAL_DIR', None)
        else:
            command = [shutil.which('zenity'), '--file-selection', '--directory', '--title=选择网球视频目录']
            if initial_path:
                command += ['--filename', str(initial_path) + os.sep]
        result = subprocess.run(command, env=environment, capture_output=True, text=True, encoding='utf-8')
        selected = result.stdout.rstrip('\r\n')
        if backend == 'zenity' and result.returncode == 1 and not result.stderr.strip():
            selected = ''
        elif result.returncode:
            raise SelectionError('Folder picker failed; use the client selector or supply a path: ' + result.stderr.strip())
    if not selected:
        return {'status': 'cancelled', 'directory': None, 'videos': [],
                'host_permissions_changed': False, 'media_uploaded': False}
    return inspect_path(selected)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('capabilities')
    q = sub.add_parser('inspect');q.add_argument('path');q.add_argument('--exclude', action='append', default=[])
    q = sub.add_parser('choose');q.add_argument('--initial-dir');q.add_argument('--backend',
        choices=['auto', 'macos', 'windows', 'zenity', 'tk'], default='auto')
    args = parser.parse_args()
    try:
        if args.command == 'capabilities':
            result = {'backends': available_backends(), 'requires_local_graphical_session': True,
                      'permission_to_show_dialog_not_verified': True, 'opens_dialog': False}
        elif args.command == 'inspect':
            result = inspect_path(args.path, args.exclude)
        else:
            result = choose(args.backend, args.initial_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (SelectionError, OSError, ValueError) as e:
        print(json.dumps({'status': 'error', 'error': str(e), 'media_uploaded': False}, ensure_ascii=False), file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
