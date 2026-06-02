# GitHub Trending Video

> AI Agent Skill - 自动化 GitHub Trending 视频生成

Agent 自主探索 GitHub Trending 项目，生成口语化总结，制作视频并上传到 B站。

## 功能

- **采集**：自动获取 GitHub Trending 热门项目
- **探索**：Agent 深度分析项目（README、代码、技术栈）
- **总结**：生成口语化、结构化的项目介绍
- **制作**：使用 Remotion 分段渲染动态视频（720p）
- **上传**：自动上传到 B站（可选）

## 安装

```bash
# Python 依赖
python3 -m venv venv
venv/bin/pip install Pillow edge-tts moviepy requests beautifulsoup4 lxml bilibili-api-python cairosvg

# Remotion npm 依赖（首次或依赖缺失时）
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

# Step 5: 上传（需明确授权）
venv/bin/python upload.py
```

## 输出

- 视频文件：`output/trending_video.mp4`（720p，约2分钟）
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
    "resolution": "1920x1080",
    "fps": 24,
    "renderer": "remotion"
  },
  "tts": {
    "engine": "vectorengine",
    "apikey": "你的API密钥"
  }
}
```

获取方法：
- B站 Cookie：登录 B站 → F12 → Application → Cookies
- TTS API Key：联系 VectorEngine 提供

## 许可证

MIT
