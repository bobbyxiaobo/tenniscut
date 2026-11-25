# Source folder selection

## Fast selection boundary

`inspect DIR` performs a single nonrecursive metadata listing. Show its result as the video-choice question immediately; do not probe all files for durations or hash their contents. The result supplies `size_bytes`, `modified_epoch` and `elapsed_seconds`. A supported exact file path is also accepted and returns `files_selected: true`, `next_step: collect_editing_settings`; it does not reopen directory/file selection. A directory result returns `files_selected: false`, so selection is still required. Both paths report `media_content_read: false`.

Do not block a directory/file question on dependency inspection, `init`, package installation, old project inspection or broad filesystem searches. Once files are selected, use `session.py inspect PROJECT --intake-only` and immediately present the unanswered editing settings together. Do not use dependency-discovering plain `inspect` before that card. Source hashing and media inspection belong after these answers. The helper timing excludes model/host latency, user wait and GUI selection time.

## User flow

Select a folder → choose the intended source files from its video list → answer the unanswered editing settings → review and export. Folder selection is not a fourth remembered preference.

A bare skill invocation starts a new source-selection flow. Do not infer a continuation from an old conversation path or from the presence of an old project. Offer the client/native directory chooser before asking editing settings. An explicitly selected source workspace or a folder supplied in the current task answers the directory step; historical folders may be suggested, not silently reused. Clear requests to continue/correct an existing task reuse that task's sources without another picker.

List the chosen folder's video filenames, remove known outputs, and ask which file(s) to process before proceeding, including a folder containing just one video. Use the host's native single/multiple choice surface when it supports the required selection. A single-select-only tool cannot stand in for arbitrary multiple selection: accept filenames in natural language or an explicit “all listed videos” choice. Include enough of each filename to distinguish it; show duration if already known. Direct file paths, exact filename restrictions and an explicit all-files request already select files and need no duplicate question. Source selection never turns saved editing preferences into authority to pick old footage.

Tell the user they can choose a folder instead of uploading original videos or typing a full path. Prefer the client’s supported folder/workspace selection:

- Codex: select a local project folder; additional folders may need project access configuration. See [local projects](https://learn.chatgpt.com/docs/projects).
- WorkBuddy: select the workspace through its file chooser when creating the task. See [task bar and workspace selection](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Task-Bar).

Do not invent a chat attachment button that grants directory access, or claim a text-choice tool opens an OS dialog. UI locations may vary by client version. A cloud/remote runtime needs an accessible mount/workspace; it cannot read the user's computer merely from a local path.

## Optional local native picker

The bundled standard-library helper can open a folder chooser when execution is on the user's interactive desktop and the host permits that operation. It uses macOS AppleScript, Windows FolderBrowserDialog, Linux zenity, or available Tk. No extra editor skill is required. It does not silently install a GUI toolkit.

Run from the skill directory:

```bash
python3 scripts/select_source.py capabilities
python3 scripts/select_source.py choose
```

`capabilities` only detects candidate backends and opens no dialog. It does not prove permission to show one. Invoke `choose` when the user actually needs to select a source, not while merely explaining the feature. Tell the user a folder chooser is opening. The command waits for selection/cancellation; use the execution tool's yield/poll mechanism and keep the user informed instead of treating elapsed time as a selection.

Optionally start within a user-specified folder:

```bash
python3 scripts/select_source.py choose --initial-dir /path/to/known-folder
```

The helper prints JSON. `status: selected` contains `directory` and a nonrecursive `videos` list of names and absolute paths; check actual file readability before initialization. `status: cancelled` means stop source intake without scanning a default folder. `status: error` means use the client selector or an accessible pasted path; do not bypass sandbox policy, retry popups repeatedly, or require a large-video upload just because a dialog failed.

A selected folder does not automatically authorize the host to read it. Use the client's real directory/workspace authorization if needed. No host permissions are changed, no preferences are saved, and no media is uploaded by this helper. Extracted images inspected by a hosted model may still leave the machine for analysis.

## Enumerate and use the selected files

For an already supplied directory, list files without opening a dialog:

```bash
python3 scripts/select_source.py inspect /path/to/videos --exclude /path/to/videos/known-export.mp4
```

`--exclude` can be repeated for known generated files. The helper lists immediate, nonhidden files with supported video suffixes. It does not automatically identify every exported video. Apply the user's filename restrictions and remove known exports, caches, and drafts before proceeding. Do not recursively scan unrelated directories. Unless the current request already identifies the files, show the short filename list and collect the file choice, even for a one-video folder. Pass actual selected video file paths to `tenniscut.py init`, not the directory itself.

An empty list is a reason to choose another folder or clarify scope, not to scan elsewhere without instruction. Keep source files intact.

## Verification limits

Automated tests cover listing, exclusions, Unicode/quoted paths, cancellation, missing GUI/errors, and argument handling through mocked dialog calls. Native dialogs have not yet completed real interactive acceptance in Codex/WorkBuddy across macOS, Windows and Linux. Report those limits separately from the tested path-handling logic.
