---
name: github-trending-video
description: 自动化GitHub Trending视频生成 - 从采集到上传的完整工作流
license: MIT
compatibility: opencode
---

## 重要限制：重试机制

**所有步骤必须遵守此限制：**

- 每个步骤如果执行失败，必须进行重试
- 每个步骤最多重试 **3 次**
- 如果某个步骤重试 3 次后仍然失败，**立即退出整个任务**，不要尝试其他替代方案
- 不要跳过失败步骤继续执行后续步骤
- 重试时使用相同的命令和方法，不要改变执行方式
- **长视频渲染例外**：不要在没有日志的情况下盲目全量重跑。Step 4 已在代码内自动落盘日志；Remotion 内部会对失败的单个 segment 重试，不应手动全量重试覆盖现场。

**示例：**
- Step 1 采集失败 → 重试 Step 1（最多3次）
- 重试3次后仍失败 → 退出任务，不执行 Step 2-5
- Step 4 Remotion 渲染到 `segment_05` 浏览器崩溃 → 代码内只重试 `segment_05`，不要从 `segment_00` 全量重跑，除非整个 `workflow.py` 已退出且用户明确要求重新开始

## 环境准备

**工作目录**：所有命令都必须在项目根目录（即 `SKILL.md` 所在目录）下执行。

**虚拟环境**：所有 Python 命令必须使用 `venv/bin/python`，而不是系统的 `python3`。

**依赖安装**（首次执行前）：
```bash
python3 -m venv venv
venv/bin/pip install Pillow edge-tts moviepy requests beautifulsoup4 lxml bilibili-api-python
cd remotion && npm install && cd ..
```

**可选但推荐的 Star History 转换依赖**：Star History API 返回 SVG，流程会优先尝试 `cairosvg`，再尝试系统命令 `rsvg-convert` / `inkscape`。如果三者都没有，视频仍可生成，但项目页会显示 `Star history unavailable`。

```bash
venv/bin/pip install cairosvg
```

## 任务

自动化生成GitHub Trending视频，包含完整流程：采集候选 → 历史去重 → 探索 → 总结 → 生成视频 → 上传。

**上传边界**：Step 5 上传到 B 站属于外部发布动作。只有用户明确要求上传时才执行；如果用户要求“只生成视频 / 不上传 / 除了 B 站上传”，必须停在 Step 4 和验证，不得运行 `upload.py`。

**敏感配置边界**：`config/config.json` 可能包含 B 站 Cookie、TTS API Key 等敏感信息。可以检查字段是否存在，但不要在回复、日志摘要或截图里展开 token / cookie 原文。

## 完整流程

### Step 1: 采集 GitHub Trending 候选

运行采集脚本获取今天的 Trending 候选列表（建议超时时间：300秒）：

```bash
venv/bin/python src/trending_fetcher.py --limit 15 --since daily --output output/trending_candidates.json
```

**参数说明**：
- `--limit`: 候选项目数量。启用历史去重后使用 15，便于跳过重复项目后仍选满 Top 5。
- `--since`: 时间范围（daily/weekly/monthly）
- `--output`: 输出文件路径

**输出内容**：
- 项目基本信息（author, name, url, description, language, stars）
- 项目预览图（保存在 screenshots/ 目录）
- README 前500字符

**验证输出**：
```bash
cat output/trending_candidates.json | jq '.projects[0]'
```

### Step 1.5: 历史去重筛选

根据 `data/projects_history.json` 跳过最近 7 天已经成功生成视频/上传过的项目，输出最终 Top 5 到 `output/trending.json`：

```bash
venv/bin/python src/history_deduper.py \
  --history data/projects_history.json \
  select \
  --input output/trending_candidates.json \
  --output output/trending.json \
  --target-count 5 \
  --cooldown-days 7 \
  --allow-repeat-if-insufficient
```

**历史文件格式**：
```json
{
  "version": 1,
  "runs": {
    "2026-05-11": {
      "status": "video_succeeded",
      "fetched": ["owner/a", "owner/b"],
      "selected": ["owner/a"],
      "skipped_duplicates": ["owner/b"]
    }
  }
}
```

**去重规则**：
- 只读取最近 7 天 `status` 为 `video_succeeded` 或 `upload_succeeded` 的 run。
- 这些 run 里的 `selected` 项目会被跳过。
- `selected` / `failed` 状态不参与去重，避免失败任务污染历史。
- 如果去重后不足 5 个，按原始 Trending 顺序补回重复项目。

**验证输出**：
```bash
cat output/trending.json | jq '.projects | length'
cat data/projects_history.json | jq '.runs'
```

### Step 2: 深度探索每个项目

读取 Step 1.5 生成的 `output/trending.json`，然后对**每个项目**进行深度探索：

**探索目标**：
1. 访问项目的 GitHub 页面
2. 理解项目的核心功能和价值
3. 分析技术栈和架构特点
4. 评估项目亮点和创新点
5. **获取 preview_image 路径**（从 Step 1.5 输出的 `output/trending.json` 中）

**不要只看初始描述！** 使用 WebFetch 工具深入了解项目 README。

### Step 3: 生成项目总结

为每个项目生成口语化的介绍，用于视频配音。

**重要**：必须合并 Step 1.5 和 Step 2 的数据！

**输出格式**：

```json
{
  "projects": [
    {
      "name": "project-name",
      "url": "https://github.com/owner/repo",
      "language": "Python",
      "stars": 1000,
      "preview_image": "screenshots/project-name.png",
      "narrative": {
        "hook": "吸引人的开场白（30字左右）",
        "body": "详细口语化介绍（100-150字）",
        "call_to_action": "引导观众行动的结尾（30字左右）"
      }
    }
  ]
}
```

**关键要求**：
- **必须包含 preview_image 字段**（从 Step 1.5 获取）
- 口语化表达，适合视频配音
- `hook` 要吸引人，抓住观众注意力
- `body` 严格控制在 **100-150字**，简明扼要
- `call_to_action` 引导行动（如"快去试试吧"）

将输出保存为 `output/projects_summary.json`

### Step 4: 生成视频

当前 `config/config.json` 默认使用：

```json
"renderer": "remotion"
```

运行视频生成脚本（**建议超时时间：1800秒以上**，Remotion 分段渲染耗时较长）：

```bash
venv/bin/python src/workflow.py --projects "$(cat output/projects_summary.json)"
```

**脚本自动执行**：
1. 用项目数据准备 Remotion 场景
2. 生成语音 - 根据 `config/config.json` 的 `tts.engine`，当前常用为 `vectorengine`
3. 复制静态资源到 `remotion/public/generated/`
   - `github_logo.png`
   - 项目 `preview_image`
   - Star History 图片
4. 生成 `output/remotion_input.json`
5. 调用 Remotion 分段渲染到 `output/remotion_segments/segment_*.mp4`
6. 用 ffmpeg concat 合并为 `output/trending_video.mp4`
7. 自动验证视频完整性 - 检查视频流和音频流

**输出**：`output/trending_video.mp4`

**日志与现场保留（非常重要）**：
- 每次 `workflow.py` 运行都会自动写总日志：
  ```text
  output/logs/workflow_<timestamp>_<pid>.log
  ```
- Remotion 分段渲染日志：
  ```text
  output/logs/remotion_render_<timestamp>_<pid>.log
  ```
- ffmpeg 合并日志：
  ```text
  output/logs/ffmpeg_concat_<timestamp>_<pid>.log
  ```
- 完整 workflow 开始时，旧的 `output/remotion_segments/` 会先归档到：
  ```text
  output/remotion_segments_archive/remotion_segments_<timestamp>_<pid>/
  ```
  然后新建空目录，避免上次任务的片段污染本次任务。

**Remotion 分段重试策略（重要）**：
- `src/remotion_composer.py` 调用 `remotion/render_segments.mjs` 时会传：
  ```bash
  --segment-retries 3 --clean-out-dir
  ```
- `--clean-out-dir` 只在完整 workflow 开始时清空当前输出目录。
- 同一次 `render_segments.mjs` 运行中，如果浏览器在某段崩溃，例如 `segment_05`，只会重试 `segment_05`，不会重渲 `segment_00~04`。
- 手动补渲单段时可以使用：
  ```bash
  cd remotion
  node render_segments.mjs \
    --input /root/.agents/skills/github-trending-video/output/remotion_input.json \
    --out-dir /root/.agents/skills/github-trending-video/output/remotion_segments \
    --scene-index 5 \
    --width 1280 \
    --height 720 \
    --concurrency 1 \
    --crf 18 \
    --x264-preset medium \
    --segment-retries 3
  ```
  手动补渲不要传 `--clean-out-dir`，否则会清空其它已完成片段。

**验证输出**：
```bash
ls -lh output/trending_video.mp4
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_type,codec_name,width,height,r_frame_rate,duration -of json output/trending_video.mp4
```

**Remotion 流程闭环检查（轻量）**：
```bash
cat output/remotion_input.json | jq '.scenes[] | {type, index, project: .project.name, preview: .project.public_preview_image, star_history: .project.star_history_image}'
ls -lh remotion/public/generated/github_logo.png
find remotion/public/generated/star_history -type f -maxdepth 1 -name '*.png' -print
ls -lh output/remotion_segments/segment_*.mp4
```

**⚠️ 重要**：视频渲染是逐帧处理的，非常耗时。如果进程被中断，可能输出不完整的视频。脚本已添加完整性验证，会自动检测并报错。失败时先看 `output/logs/` 里的日志，不要先猜原因。

**视频生成成功后，必须更新历史状态**：
```bash
venv/bin/python src/history_deduper.py --history data/projects_history.json status --status video_succeeded
```

如果 Step 1.5 之后任一步骤失败，且当天 run 已写入 history，都必须将当天状态标记为 failed：
```bash
venv/bin/python src/history_deduper.py --history data/projects_history.json status --status failed
```

### Step 5: 上传到B站

运行上传脚本：

```bash
venv/bin/python upload.py
```

**前提条件**：
- `config/config.json` 中已配置 B站 Cookie（sessdata, bili_jct, buvid3）
- Cookie 有效期检查：如果上传失败，可能需要更新 Cookie

**上传参数**：
- 标题：`GitHub 今日热榜 Top 5 (日期)`
- 标签：GitHub, 开源项目, 编程, 技术分享, AI
- 分区：科技区 → 知识 → 科学 → 其他

**上传成功后，可选更新历史状态**：
```bash
venv/bin/python src/history_deduper.py --history data/projects_history.json status --status upload_succeeded
```

如果上传失败但视频已生成成功，保持 `video_succeeded`，因为项目已经被视频介绍过。

## 文件结构

```
github-trending-video/          # 项目根目录
├── SKILL.md                    # Agent 执行指令
├── README.md                   # 本文件（用户文档）
├── upload.py                   # Step 5: 上传脚本（需明确授权）
├── config/
│   ├── config.json             # Cookie/API 配置（已配置，敏感）
│   └── config.example.json     # 配置模板
├── remotion/                   # Remotion 渲染器
│   ├── src/
│   │   ├── index.ts            # Remotion 入口
│   │   ├── Root.tsx            # Composition 定义
│   │   ├── SceneSegment.tsx    # 单段渲染组件（修复后）
│   │   ├── TrendingVideo.tsx  # 全片合成组件
│   │   ├── ProjectScene.tsx   # 项目页动态布局
│   │   ├── TitleScene.tsx     # 标题页
│   │   ├── EndingScene.tsx    # 结尾页
│   │   ├── types.ts            # 类型定义
│   │   └── theme.ts            # 主题色
│   ├── public/generated/      # 运行时生成的静态资源
│   ├── render_segments.mjs    # 分段渲染脚本
│   ├── still.mjs              # 静帧预览脚本
│   └── package.json           # npm 依赖
├── src/
│   ├── trending_fetcher.py    # Step 1: 采集脚本
│   ├── history_deduper.py     # Step 1.5: 历史去重
│   ├── workflow.py             # Step 4: 视频生成（Remotion/MoviePy）
│   ├── remotion_composer.py   # Remotion 合成器（含日志/归档）
│   ├── card_generator.py      # 幻灯片生成（MoviePy 路线）
│   ├── tts_generator.py       # TTS 调度
│   ├── bilibili_uploader.py   # B站上传核心逻辑
│   └── tts/
│       ├── base.py
│       ├── edge_engine.py     # Edge-TTS 引擎
│       └── vectorengine.py    # VectorEngine Gemini TTS
├── assets/
│   └── github_logo.png        # GitHub logo（会被复制到 remotion/public/generated/）
├── screenshots/               # 项目预览图（trending_fetcher 抓取）
├── data/
│   └── projects_history.json  # 历史去重记录
└── output/                    # 运行时输出（不提交 git）
    ├── trending_candidates.json
    ├── trending.json
    ├── projects_summary.json
    ├── remotion_input.json
    ├── trending_video.mp4     # 最终视频
    ├── remotion_segments/     # Remotion 分段 mp4
    ├── remotion_segments_archive/  # 历史片段归档
    ├── star_history/          # Star 历史图缓存
    ├── logs/                  # 自动日志
    └── audio_*.mp3/wav        # 配音文件
```

**关键差异（Remotion vs MoviePy）：**
- Remotion 路线：Python 只负责准备 `remotion_input.json` 和静态资源，实际渲染由 Node 调用 Remotion
- MoviePy 路线：Python 直接合成视频，已较少使用

## 故障排查

**问题：Step 1 网络超时**
- 检查网络连接是否正常
- 增加超时时间（脚本默认20秒）
- 重试最多3次

**问题：项目截图未生成**
- trending_fetcher.py 会自动获取预览图
- 如果获取失败，card_generator.py 会自动跳过截图

**问题：视频文字太小/太大**
- 字号已优化：标题80px、正文42px
- 如需调整，修改 src/card_generator.py 的 _load_fonts() 方法

**问题：视频渲染不完整/视频流时长与音频不一致**
- 原因：进程被 SIGTERM 中断（超时或手动终止）
- 脚本会自动验证视频完整性，如果失败会抛出错误
- 先查看：
  ```bash
  ls -lt output/logs | head
  tail -200 output/logs/workflow_*.log
  tail -200 output/logs/remotion_render_*.log
  tail -200 output/logs/ffmpeg_concat_*.log
  ```
- 可用 `ffprobe -v quiet -show_streams output/trending_video.mp4` 检查时长

**问题：Remotion 在某个 segment 浏览器崩溃**
- 当前代码会在同一次 `render_segments.mjs` 运行内只重试失败 segment，默认 `--segment-retries 3`。
- 不要因为 `segment_05` 崩溃就手动从 `segment_00` 全量重跑。
- 如果需要手动补渲某段，用 `--scene-index <n>`，不要传 `--clean-out-dir`。

**问题：B站上传失败**
- 检查 config/config.json 中的 Cookie 是否有效
- Cookie 有效期通常为30天
- 需要登录 B站后从浏览器获取新 Cookie

## 执行要求

1. **完整执行** - 默认从 Step 1 到 Step 5 完整执行，包含 Step 1.5 历史去重；但 Step 5 是外部发布动作，必须以用户明确授权为准，用户说不上传就停在 Step 4。
2. **数据合并** - Step 3 必须合并 Step 1.5 的数据（preview_image）
3. **主动探索** - 不要依赖初始描述，深入探索每个项目
4. **准确客观** - 基于实际数据，不要编造
5. **口语表达** - 生成的文本要适合配音
6. **保持简洁** - 每个项目200字以内（hook 30 + body 100-150 + call_to_action 30）
7. **敏感信息保护** - 不要输出 `config/config.json` 里的 Cookie、API Key 原文；只说“已配置/未配置/字段缺失”。

开始执行吧！按照用户授权范围执行完整工作流；如果用户未授权上传，则只执行到视频生成、验证和历史状态更新。
