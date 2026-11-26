# Selecting local tennis footage

Use a local desktop picker or accept pasted paths. For a fresh run on a local interactive Mac, launch `choose --kind source` immediately and wait on the same process for its result. The modal system panel stays available while the process runs. Use this one panel where the user can select one or more video files (Command-click for multiple) or a single folder. A recent directory may be passed as the initial location. On hosts with separate dialogs offer **直接选视频** and **选择文件夹** side by side. An explicit request to open a picker already selects the action. Prefer a host picker which returns local paths. A workspace-only selector can serve the folder branch.

From the skill directory:

```bash
python3 scripts/select_source.py choose --kind source   # macOS combined panel
python3 scripts/select_source.py choose --kind files    # direct video selection
python3 scripts/select_source.py choose --kind folder   # browse a folder
python3 scripts/select_source.py inspect "/path/to/one.mov" "/path/to/two.mp4"
python3 scripts/select_source.py inspect "/path/to/folder" --exclude "/path/to/folder/old-cut.mp4"
```

The optional `--initial-dir` sets the starting location. Windows supports multiple files in the file dialog, Tk supports multiselect, and the Linux zenity file dialog returns a single video. Typed paths can specify several files. `capabilities` reports candidate local backends without opening a window. In a headless or permission-limited host, accept paths in an accessible workspace. Picking a path and granting host filesystem access are separate actions. On cancellation, end source selection without scanning a fallback directory.

Follow the helper's result:

- `files_selected: true`: use exactly the selected paths and go straight to unanswered editing settings. A direct file selection does not enumerate siblings or look up their durations.
- `next_step: select_source_files`: show each video's `choice_label` immediately. It contains the filename, size, local date added and duration (MM:SS or H:MM:SS). Preserve all four fields. Publish the numbered list with its full metadata in ordinary chat text even when offering a clickable card; the user can answer from the message later. Accept numbers, names, multiple files or “全部”. Apply current explicit file restrictions and skip the question if they already identify the source(s).
- `next_step: choose_another_folder`: the directory has no supported candidates. Offer file and folder selection again.
- `status: cancelled` or an error: no source was selected. Report access errors directly. A user may choose a different source or supply a path.

Directory inspection lists immediate, nonhidden video files, sorted by filename. Exclude known exports using repeatable `--exclude`. On macOS the helper reads the filesystem's date added to that directory. When unavailable, the label can show the filesystem creation time explicitly as a fallback. Duration uses a bounded local ffprobe lookup (macOS Spotlight when ffprobe is absent); a missing or slow lookup is marked unknown. Opening the candidate list needs no software install, media hashing, frame extraction or project setup. Listing time excludes host and user interaction.

The local helper does not upload media. A hosted model may receive screenshots when it later reviews play.
