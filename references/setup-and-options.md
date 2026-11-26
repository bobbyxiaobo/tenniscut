# Startup choices and dependency setup

## Source selection precedes the two settings

Start with the user's choice of local video file(s) or a folder. Exact files proceed directly to editing settings. For a folder, show the candidate names, sizes, dates added and durations unless the user already specified which files to use. Use the [source picker](source-selection.md) when needed. A previous folder is a shortcut; an explicit continuation reuses its project.

At first source intake, explicitly remind the user that a local file/directory path is enough in a local-file-capable host; uploading the original video as a chat attachment is optional. Use the short Chinese reminder in `SKILL.md`. If a readable path is already supplied, continue without asking for upload or redundant path confirmation. Enumerate directory inputs into the exact selected source files before invoking `init`; respect filename restrictions and avoid known generated outputs.

Check the actual filesystem and host permissions. Help obtain local directory/workspace access when it is missing. For cloud/remote runtimes with no local mount, explain the missing access and offer an accessible workspace or optional attachment instead of claiming a local path will work universally. Keep the distinction explicit: source-video upload is not required by these local scripts, but screenshots inspected by a hosted model can leave the machine for analysis.

## Two startup questions; ask on every new task

After source selection, run `python3 scripts/session.py inspect PROJECT --intake-only`. Every new task presents the unanswered settings together:

| Question | Choices | First-use default |
| --- | --- | --- |
| 拍数下限：双方合计至少几拍才保留？ | 6 / 8 / 10 / custom positive integer | **8** |
| 是否同时生成剪映草稿？ | yes / no | **no** |

There is no asking-frequency question. Old profiles with `ask_every_time: false` still ask both unanswered settings on new tasks. The legacy field is normalized to true; old CLI flags remain accepted for compatibility and cannot disable this fixed policy. Last saved threshold/draft values are suggestions, not permission to skip the questions.

Use the host's available native question tool, respecting option limits and its built-in custom field; use concise text if unavailable. If the host preselects the first option, put the effective default first. Preselection and silence are not answers. Wait for actual submission; prepare dependencies only after the card is displayed, and complete setup before analysis.

Current natural-language values already answer their fields. For “保留9拍以上，不生成草稿”:

```bash
python3 scripts/session.py inspect PROJECT --intake-only --threshold 9 --jianying no
python3 scripts/session.py configure PROJECT --threshold 9 --jianying no
```

With both fields supplied, no card is needed. With one supplied, ask only the other. `inspect` saves nothing. Save submitted values using `configure`; do not let `--use-defaults` replace pending answers. That option is valid only when the user explicitly accepts displayed defaults. Configuration is complete once threshold and draft choice are valid, including older two-field projects.

Continuation, correction and retry of a confirmed task use `inspect PROJECT --resume --intake-only` without another card. A partial questionnaire resumes with just its missing field. Current explicit requests override the project, remembered suggestions and factory defaults. A “this time” change uses `configure PROJECT --resume --threshold 10 --project-only`; reusable changes update local preferences. No CapCut option is offered.

## Storage and portability

`settings.json` is the current project's confirmed snapshot. Shared choices are stored in `preferences.json` under the machine user's configuration directory: `%APPDATA%/tenniscut` on Windows when available, otherwise `$XDG_CONFIG_HOME/tenniscut` or `~/.config/tenniscut`. Codex and WorkBuddy on the same account/machine can reuse that file. This is not cloud account synchronization; another computer starts with factory defaults.

Set `TENNISCUT_PREFERENCES` to an explicit writable file path where a sandbox cannot use the standard location. Do not silently claim “remembered for future tasks” if writing preferences fails. The command reports that blocker without changing the project snapshot. Never publish this preference file, source paths, or project records in the skill package.

`configure` may precede `init`; source initialization preserves the project settings. Core selection commands accept explicit `--threshold` overrides, otherwise read the confirmed project snapshot or remembered choices. Factory defaults alone do not authorize analysis before the first questionnaire is submitted.

The Jianying choice is an additional editable draft alongside the MP4 and records. No CapCut output choice is offered. Default counting is inclusive (`>= N`) across both players. An explicit “超过10次” means a minimum of 11.

## Check and help install tools

`session.py inspect --intake-only` reads settings/questions only. Use it before displaying the settings card. After the answers, run `session.py inspect PROJECT --resume` without this flag for preparation. Deferred dependency checks do not mean tools are ready.

`session.py inspect` without `--intake-only` checks ffmpeg, ffprobe, Pillow, and only when requested, pyJianYingDraft. It returns missing dependencies and an installation command candidate for an existing package manager. It does not install software itself.

- If ffmpeg/ffprobe already work, reuse them. Verify the actual binaries, not just a folder name.
- If missing, briefly explain the needed download and installation location. Where installation is already authorized by the task/session and the host permits it, perform it; do not ask for the same permission again. Otherwise offer installation and use the host's actual approval flow if required.
- Prefer an already-installed package manager. The inspect result is a candidate, not a command to execute blindly: check the platform, selected package, and needed privileges. Do not silently install a package manager, use `sudo`, or change VPN/proxy/system policy.
- On macOS with Homebrew, the usual command is `brew install ffmpeg`. With Windows winget it is `winget install --exact --id Gyan.FFmpeg`. On Linux use the distribution's available package manager, with any genuinely required authorization. If none is available, offer the official [FFmpeg download choices](https://ffmpeg.org/download.html); do not fetch binaries from an invented mirror.
- Install Python packages in a project virtual environment when possible. Use that environment's Python consistently for the CLI and optional adapter. Basic: `python -m pip install -r requirements.txt`. Only if a draft was requested: `python -m pip install -r requirements-jianying.txt`.
- For requested Jianying output, also actually import `pyJianYingDraft` and check `pymediainfo.MediaInfo.can_parse()`. A discoverable Python package is not proof that its native MediaInfo runtime works; resolve the reported native dependency before a long review.
- Then run `python scripts/tenniscut.py doctor`. For HDR inputs verify zscale and tonemap, plus libx264. Verify a tiny generated video can actually be decoded and encoded before long source analysis when tools were newly installed.
- If installation is blocked, offline, or fails, report the precise missing component and a usable install command. Stop at preparation rather than silently skipping the requested feature, pretending readiness, or starting a long review that cannot deliver the chosen outputs.

No dependency installation is performed just by activating the skill or running `inspect`.

## Optional Jianying output

Read [Jianying output](jianying-output.md) only when the user chose to generate a draft. After answers and before long analysis, run `jianying.py --discover --check-write`; resolve directory/access ambiguity along with optional dependencies. Do not add discovery before source/settings selection. Do not check or install its packages for MP4-only jobs.

Compatibility after renaming: the old `TENNIS_RALLY_CUT_PREFERENCES` environment override is accepted when the new one is absent. Without either override, an existing legacy `tennis-rally-cut/preferences.json` is read if the new file is absent; the next confirmed save writes under `tenniscut` and preserves the old file.
