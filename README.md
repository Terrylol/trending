# GitHub Trending Video

> AI Agent Skill - 自动化 GitHub Trending 视频生成

Agent 自主探索 GitHub Trending 项目，生成口语化总结，制作视频并上传到 B站。

## 功能

- **采集**：自动获取 GitHub Trending 热门项目
- **探索**：Agent 深度分析项目（README、代码、技术栈）
- **总结**：生成口语化、结构化的项目介绍
- **制作**：使用 Remotion 分段渲染动态视频（默认 720p，可配置）
- **上传**：自动上传到 B站（可选）

## 安装

```bash
# Python 依赖
python3 -m venv venv
venv/bin/pip install Pillow edge-tts moviepy requests beautifulsoup4 lxml bilibili-api-python

# 可选：SVG → PNG 转换（Star 历史趋势图需要，三选一）
venv/bin/pip install cairosvg          # 方案1：Python 库（推荐）
# sudo apt install librsvg2-bin        # 方案2：rsvg-convert
# sudo apt install inkscape            # 方案3：Inkscape

# Remotion npm 依赖（首次或依赖缺失时自动安装）
cd remotion && npm install && cd ..
```

## 使用

在 AI Agent 中调用：

```
使用 github-trending-video skill 生成今天的视频，不上传 B 站
```

或手动执行：

```bash
# Step 1: 采集候选
venv/bin/python src/trending_fetcher.py --limit 15 --since daily --output output/trending_candidates.json

# Step 1.5: 历史去重
venv/bin/python src/history_deduper.py --history data/projects_history.json select --input output/trending_candidates.json --output output/trending.json --target-count 5

# Step 2-3: Agent 探索与总结（写入 output/projects_summary.json）

# Step 4: 生成视频
venv/bin/python src/workflow.py --projects "$(cat output/projects_summary.json)"

# Step 5: 上传 B站（需明确授权）
venv/bin/python -m src.bilibili_uploader
```

## 输出

- 视频文件：`output/trending_video.mp4`（默认 720p，约2分钟）
- Remotion 分段：`output/remotion_segments/segment_*.mp4`
- 日志：`output/logs/workflow_*.log`

## 配置

编辑 `config/config.json`：

```json
{
  "bilibili": {
    "sessdata": "你的SESSDATA",
    "bili_jct": "你的bili_jct",
    "buvid3": "你的buvid3"
  },
  "video": {
    "limit": 5,
    "resolution": "1280x720",
    "fps": 24,
    "renderer": "remotion"
  },
  "tts": {
    "engine": "vectorengine",
    "apikey": "你的API密钥",
    "voice": "Aoede",
    "speed": 1.3
  },
  "github": {
    "personal_access_token": ""
  }
}
```

### 配置项说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `video.resolution` | 视频分辨率，格式 `WIDTHxHEIGHT` | `1280x720` |
| `video.fps` | 帧率 | `24` |
| `tts.engine` | TTS 引擎 | `vectorengine` |
| `tts.voice` | 语音音色 | `Aoede` |
| `tts.speed` | 语速倍率（1.0=正常，通过 ffmpeg atempo 实现） | `1.3` |
| `github.personal_access_token` | GitHub Token（提高 API 限额，可选） | 空 |

### 获取 B站 Cookie

1. 在浏览器登录 [bilibili.com](https://www.bilibili.com)
2. 按 `F12` 打开开发者工具
3. 切换到 **Application**（Chrome）或 **存储**（Firefox）标签
4. 左侧找到 **Cookies** → `https://www.bilibili.com`
5. 复制以下三个值：
   - `SESSDATA` → 填入 `sessdata`
   - `bili_jct` → 填入 `bili_jct`
   - `buvid3` → 填入 `buvid3`

> Cookie 有效期约 30 天，过期后需重新获取。

### TTS 配置

默认使用 VectorEngine TTS（基于 Gemini TTS）。如需使用其他 TTS 引擎，修改 `tts.engine` 并实现对应的 `BaseTTS` 子类（见 `src/tts/` 目录）。

## 许可证

MIT
