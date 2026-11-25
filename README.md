# tenniscut · 网球多拍剪辑

**Beta 0.7.0-beta.1：让 AI 助手筛选固定机位网球视频的连续多拍回合，逐拍留证，用 FFmpeg 本地导出。**

用户可以指定“双方合计至少 10 次击球”，合并多个视频，也可以指出“成片 00:25 这轮有问题”，仅修正相关回合。默认按原片分辨率导出，保留原声，提供回合时间清单和可选剪映草稿；明确要求时可另设2K等尺寸。默认直接交付成片；HTML 复核页面暂缓。

这不是独立的自动数拍模型。CLI 不会识别网球、击球或重新喂球；需要支持图片查看与文件操作的 AI 助手完成视觉复核。程序能阻止缺少证据、已记录换球、未完成复核等情况进入正式导出，但不能识别一条被错误填写为“已确认”的记录。**尚未完成独立的真实网球准确率评测。**

## 不用先上传原视频，可以直接选文件夹

在能够访问本机文件的 Codex／WorkBuddy 桌面环境中，**不必把原视频上传成聊天附件**。可以在客户端选择视频文件夹，也可以直接提供文件或目录路径；需要时允许客户端访问该目录。例如：

> 使用 tenniscut，视频在“下载/tennis cut”，只剪其中7503和7505两个文件，保留8拍以上。

可以先在 Codex 中选择本地项目目录，或在 WorkBuddy 新建任务时选择工作空间，然后说“剪这个目录里的网球视频”。已经选好目录时，不必再描述完整路径。技能还提供按需打开本机文件夹选择窗的辅助脚本；是否能弹窗取决于本地桌面环境及客户端权限。

选目录是素材准备步骤，与后面的两个设置问题分开。取消选择不会开始扫描；选择本身不上传视频，也不自动授予客户端文件访问权限。弹窗受限时使用客户端的目录选择入口或粘贴路径。详见 [目录选择](references/source-selection.md)。

也可以提供完整文件路径。助手会先检查文件是否可读；给目录时，会列出视频并按你指定的文件名筛选。缺少访问权限时，先协助授权目录，而不是要求重新上传大视频。已经提供可访问路径时，不会重复要求上传。

这需要脚本运行环境确实能访问该目录。云端或远程运行模式可能看不到你电脑上的文件，此时需要可访问的工作目录／挂载，或者按需上传，不能仅凭一个本机路径直接读取。

**原片不由本脚本上传，抽帧和渲染在本机执行；AI 助手查看截图时，截图可能由模型服务处理。** 因此“无需上传原片附件”不等于“整个分析完全离线”。

## 直接用自然语言

按钮只是输入方式之一，可以直接说：

- “这次只保留10拍以上，不要剪映草稿，导出2K。”
- “保留9拍以上。”（直接使用自定义值，不必再选一次自定义。）
- “这次按8拍，不生成草稿。”
- “成片00:25那轮删掉。”

当前明确要求优先于项目配置、长期偏好和默认值；已经说清的选项视为已回答，只询问剩余项目。“这次”的改动只影响当前任务，“以后都这样”的改动才更新长期偏好。自然语言由 AI 助手理解，再调用脚本，不是脚本内置一个能处理任意请求的语言模型。模糊、冲突或暂不支持的要求会说明并确认。

## 启动时的选择

只输入 `tenniscut` 或 `$tenniscut` 时，先选择本机视频文件夹，再从文件列表里选择这次要剪的视频，最后展示剪辑设置。目录里只有一个视频也会先让你选定；不会因为以前聊过某个路径就自动剪旧视频。若已经说清路径和具体文件，或明确说“该目录全部视频”，就直接采用，不重复确认。明确续剪或修改旧任务时沿用原素材。

文件选定后展示尚未回答的两个设置，优先使用客户端的原生选择卡：

| 设置 | 选项 | 默认 |
| --- | --- | --- |
| 拍数下限 | 6 拍、8 拍、10 拍、自定义正整数 | **8 拍** |
| 是否同时生成剪映草稿 | 是、否 | **否** |

每个新任务固定询问拍数下限和是否生成剪映草稿，不再询问“是否每次询问”。上次设置只作为当前建议值；自然语言已明确的项目不重复问。当前任务的修正和重试沿用已确认设置。旧配置中的“不再询问”不再跳过新任务的两个问题。

客户端的按钮样式和自定义输入方式可能不同。宿主不支持选择卡时使用文字询问。默认选中不等于提交答案，首次不会直接采用默认值开工。目前不提供 CapCut 草稿选项。

```bash
python3 scripts/session.py inspect /path/to/private-project --intake-only
python3 scripts/session.py configure /path/to/private-project --threshold 8 --jianying no
```

当前任务配置保存在项目的 `settings.json`；长期偏好保存在本机用户配置目录下的 `tenniscut/preferences.json`，因此换一个项目也能记住。同一电脑的 Codex、WorkBuddy 可共用该文件，另一台电脑不自动同步。可用 `TENNISCUT_PREFERENCES` 指定可写的保存位置。

`inspect` 不会安装软件或保存答案。助手会协助安装缺失依赖并验证，安装被阻止时会在准备阶段说明。详见 [启动配置和安装流程](references/setup-and-options.md)。

## 耗时与当前限制

目录和文件选择只读取文件名、大小和修改时间，不应等待视频数拍、全文件哈希或全部视频时长扫描。选好文件后一次询问两个剪辑设置，再开始处理选中的素材。

0.6.6 默认采用自适应截图：**稀疏概览 → 判断捡球、准备、对拉和状态切换 → 按需补看中间帧 → 对可能保留的回合密集复核**。捡球后可以向前探看；出现准备或对拉时回查边界，不能从一帧捡球倒推前后整段都没比赛。连续发接球练习仍可能需要较多补看，不会仅凭时长或稀疏姿势删除回合。

达到门槛后记录确认拍数下限，不强求精确总数，但仍以完整2fps以上画面检查保留回合的连续性和终点。空闲导航与数拍证据分开；CLI不会自动识别状态，也不会自动证明计数正确。不采用音频预筛作为默认入口。详见[自适应导航规则](references/review-protocol.md#adaptive-visual-navigation)。

一次熟悉素材、复用缓存的5分钟实验约10.4分钟完成；密集复核帧167→28，但计入导航后总帧展示242→195。它不是独立准确率或冷启动评测，也不能承诺新素材固定提速倍数。主要瓶颈仍是模型看图；无法保证长视频几分钟剪完。保守排除未证实达标的候选时会说明可能漏剪。

性能报告应从启动技能计时，分列交互准备、分析和导出；缺失的前期时间不能省略后称为“总耗时”。同时记录概览、导航、密集复核的总展示帧数与重复查看，不只报告密集截图减少量。

## 环境

- Python 3.9 或以上。
- FFmpeg、ffprobe；FFmpeg 需支持 libx264 和 `-fps_mode`。HDR 转 SDR 还需要 zscale、tonemap。
- Pillow 10.1 或以上：

```bash
python3 -m pip install -r requirements.txt
python3 scripts/tenniscut.py doctor
```

如果本机没有 FFmpeg，助手会根据系统和已有包管理器协助安装；不重复安装已可用的版本。安装后还会验证 ffprobe、libx264，以及需要时的 HDR 滤镜。仅当选择生成剪映草稿时，才检查和安装 `requirements-jianying.txt` 中的可选依赖。

工具优先从 `FFMPEG`、`FFPROBE` 环境变量或 PATH 查找，也检查常见安装目录。不依赖作者电脑的绝对路径。实际验证环境为 macOS；其他平台请先运行测试。

## 在 Codex 中使用

将本仓库文件夹放入自己的技能目录，并保留名称 `tenniscut`。例如 macOS/Linux 用户可复制到 `~/.codex/skills/tenniscut`；Windows 用户放入自己的 Codex 技能目录。重新打开会话后使用：

> 使用 $tenniscut，把这两个视频中双方合计至少 10 拍的连续回合保留下来，按原片分辨率合成视频，并保存逐拍记录。

若安装过旧名 `tennis-rally-cut`，更新时停用旧技能并安装 `tenniscut`，避免同时触发。项目数据可继续使用，旧的偏好文件也会兼容读取，下一次保存会使用新名称。

详细工作流由 [SKILL.md](SKILL.md) 定义。安装依赖和导出路径仍受宿主环境权限约束。

## 在 WorkBuddy 中使用（待端到端验证）

WorkBuddy 官方支持导入本地技能包，技能采用 `SKILL.md`、`scripts/` 和 `references/` 结构。本技能使用这种结构，核心脚本不依赖 Codex 专属 API；但**尚未在 WorkBuddy 中完成安装、图片审阅、长视频导出和剪映草稿的完整验收**，不能把格式兼容等同于已经跑通。

可在 WorkBuddy 的「专家·技能·连接器 → 技能 → 添加技能 → 上传技能」中尝试导入 core ZIP。在本机任务中选择视频所在工作空间，允许读取该目录，然后输入“使用 tenniscut，保留双方合计至少 8 拍的连续回合，仅生成视频”。不要使用云电脑来代替本机访问，除非已经另行提供云端可访问的素材。先用一个短视频验证依赖检查、图片查看和导出，再处理整段录像。

两端调用同一套 Python／FFmpeg 脚本；模型看图能力、耗时、权限提示和选择按钮由宿主决定，不能保证相同识别结果或速度。宿主没有选择按钮时使用简短文字问答；没有查看本机图片的能力时，应报告阻碍，不能跳过视觉复核。剪映适配器还需要目标系统、依赖和剪映版本单独验收。`agents/openai.yaml` 是 Codex 界面元数据，不是运行脚本的必需项。

这次发布到 GitHub 不等于上架 WorkBuddy 技能市场；市场元数据和审核需另行准备。参考官方的[技能导入说明](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)、[技能结构](https://open.workbuddy.cn/docs/skill)和[权限模式](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Permission-Modes)。

## 命令行流程

以下命令在仓库根目录运行；将示例路径和 `SOURCE_ID` 换成自己的值。

```bash
python3 scripts/session.py configure /path/to/private-project --threshold 8 --jianying no
python3 scripts/tenniscut.py init /path/to/private-project /path/to/video.mov
python3 scripts/tenniscut.py extract /path/to/private-project --source SOURCE_ID --start 0 --end 60 --fps 0.25 --purpose overview --sheet-frames 20
python3 scripts/tenniscut.py extract /path/to/private-project --source SOURCE_ID --start 10 --end 35 --fps 2 --purpose review
python3 scripts/tenniscut.py add /path/to/private-project --id r001 --source SOURCE_ID --start 10 --end 35
```

多个候选可以用一次 `extract-batch` 批量抽帧（窗口JSON接受 `start`、`end` 和可选 `fps`），避免每个窗口重新完整校验大视频。已有抽帧可以用 `review-sheets` 直接生成全场与双方放大图，不重新解码原片。先概览定位，只对候选及疑点加密；已确认、未变化的回合复用记录，不重复数拍。详见 [复核协议](references/review-protocol.md)。这些提速不会自动识别击球，也不会放宽连续回合标准。

接下来必须由助手或人查看图片，按 [记录格式](references/record-format.md) 填写 `rallies.json` 的边界复核、逐拍事件和证据。不能跳过这一步把 draft 直接批量标成 reviewed。

```bash
python3 scripts/tenniscut.py validate /path/to/private-project
python3 scripts/tenniscut.py plan /path/to/private-project
python3 scripts/tenniscut.py render /path/to/private-project --out /path/to/exports/highlights.mp4
```

MP4 和剪映画布默认跟随所选原片的显示分辨率（包含旋转后的横竖方向），无需增加一个设置问题。`--resolution source` 可显式指定这个默认行为；只有明确要求2K时才使用 `--resolution 2560x1440`。多段原片尺寸不同时，先选择分别按原尺寸导出，或明确指定合并画布；不会自动放大到2K。

`validate` 返回逐条诊断；`plan` 和 `render` 默认拒绝未解决的复核问题。少于门槛的已复核回合正常排除。可以明确排除不确定候选，或用 `--allow-pending` 导出标记为不完整的版本。

## 可选剪映草稿（实验性适配器）

选择生成草稿后，助手会在 MP4 之外调用：

```bash
python3 -m pip install -r requirements-jianying.txt
python3 scripts/jianying.py /path/to/private-project --draft-root /path/to/draft-output --name tennis-8plus
```

草稿引用原片，每个回合是独立片段，原片路径需要保持可访问。只创建新草稿，不读取或覆盖已有草稿。`render` 的结果会提示是否还需要生成剪映草稿，不能把 MP4 导出当成两个输出都完成。

**这个适配器尚未在目标剪映应用中完成打开、播放和编辑的端到端验收。** 已有接口契约和文件结构测试，不能据此声称生成文件夹就等于草稿已出现在应用首页；需要在用户目标版本中打开验收。详见 [剪映输出说明](references/jianying-output.md)。

## 直接交付视频与可选剪映草稿

助手完成逐拍计数、回合连续性和起止边界复核后，直接导出 MP4，并按你的选择额外生成剪映草稿。无需打开 HTML 页面或复制页面指令。遇到仍无法判断的区间，助手在对话里说明来源时间和疑点；不会把未确认片段当作符合拍数的回合。

每次保留回合记录、导出清单和 CSV 时间映射。以后可以直接说“成片00:25那轮删掉”，只重新处理受影响的片段。HTML 相关代码和已有页面暂时保留，只有明确要求恢复时才使用；普通导出默认也不生成 HTML 清单，旧版清单查看器可通过 `render --viewer` 显式生成。历史界面说明见 单独开发归档中的暂停 HTML 复核流程。

## 局部修正

```bash
python3 scripts/tenniscut.py locate /path/to/exports/highlights.manifest.json --time 00:25
python3 scripts/tenniscut.py revise /path/to/private-project --id r001 --start 18 --reason '前段属于另一轮短回合'
```

修改后相关回合回到 draft，需要补充复核。再次导出使用新文件名；未变化的片段复用缓存。缓存比较源文件 SHA-256、起止范围、导出参数、工具和处理流程版本，并验证缓存文件内容。不会仅因文件名相同就复用。

## 本地处理与用量

抽帧、转码和拼接在本机运行，脚本不上传原片、不主动调用云端 API。AI 助手查看截图时，数据处理方式取决于助手所在服务，所以整个分析流程不一定完全离线。

先用低密度概览找候选，再密集复核完整候选与疑点。生成截图本身不消耗模型 token；模型查看图片和推理会消耗用量。拼图可能损失小球和手部细节，不能以节省 token 为由省略边界复核。工具未声称能提供 Codex 套餐占用百分比。

## 测试

```bash
python3 -m unittest discover -s tests -v
RALLYCUT_INTEGRATION=1 python3 -m unittest discover -s tests -v
```

第一条运行规则与缓存测试（FFmpeg 集成和真实端口测试默认跳过）。第二条额外生成无个人内容的测试视频，检查实际 PTS、裁剪导出、帧数、声音时序、局部修改和缓存复用。前端实验及其 Node 测试只在单独开发归档中保留。允许监听本地端口的环境可另外设置 `RALLYCUT_HTTP=1` 运行实际 HTTP 测试。Windows PowerShell 可先执行 `$env:RALLYCUT_INTEGRATION="1"` 再运行测试。

完整开发源验证：92 项 Python 测试通过，1 项可选本地端口测试因环境限制未运行；另有 Node 隔离 DOM 测试验证待确认片段过滤、双按钮选择、无网络复制交接、复制失败提示和不生成虚构拍数。目录弹窗调用使用模拟测试，尚未在各平台客户端中完成真实交互验收。另对一个已知错误的真实视频区间完成重新抽帧、边界复核和 22 秒 2K 导出。真实样例仅在私人工作目录中试跑，不随仓库发布，也不代表整体准确率。

规则测试包含“4 拍＋新喂球＋10 拍”的错误合并，以及缺失边界、仅用概览、覆盖缺口、模糊事件、证据损坏、旧时间轴定位等案例。它们验证软件机制，不能代替真实网球识别评测。

## 发布范围

公开仓库只包含技能、脚本、说明和合成测试。不要提交原片、缓存截图、项目 JSON、导出视频、解码日志或个人路径。仓库内的 `.gitignore` 提供默认排除项，项目建议放在仓库外。

本技能输出 MP4 与记录，可选实验性的剪映草稿适配器；暂不实现 CapCut 草稿。清晰度取决于原片，选择 2K 不会恢复已经丢失的细节。

## 许可证

采用 [MIT License](LICENSE)，Copyright (c) 2026 YE BO。FFmpeg 和可选第三方依赖按各自许可证使用；本项目不捆绑 FFmpeg 二进制文件。

本安装包不含暂停的 HTML 交互复核脚本、页面和测试；需要开发该实验时使用 development 归档。
