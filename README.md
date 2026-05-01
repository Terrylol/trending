# GitHub Trending Video

> AI Agent Skill - 自动化 GitHub Trending 视频生成

Agent 自主探索 GitHub Trending 项目，生成口语化总结，制作视频并上传到 B站。

## 功能

- **采集**：自动获取 GitHub Trending 热门项目
- **探索**：Agent 深度分析项目（README、代码、技术栈）
- **总结**：生成口语化、结构化的项目介绍
- **制作**：自动生成幻灯片、配音、视频
- **上传**：自动上传到 B站（可选）

## 安装

```bash
# 安装依赖
python3 -m venv venv
venv/bin/pip install Pillow edge-tts moviepy requests beautifulsoup4 lxml bilibili-api-python

# 配置 B站 Cookie（可选）
cp config/config.example.json config/config.json
# 编辑 config/config.json，填入 SESSDATA、bili_jct、buvid3
```

## 使用

在 AI Agent 中调用：

```
使用 github-trending-video skill 生成今天的视频
```

或手动执行：

```bash
# 采集
venv/bin/python src/trending_fetcher.py --limit 3 --output output/trending.json

# 生成视频
venv/bin/python src/workflow.py --projects "$(cat output/projects_summary.json)"

# 上传
venv/bin/python upload.py
```

## 输出

- 视频文件：`output/trending_video.mp4`（约2分钟）
- 幻灯片：`output/slide_*.png`（1920x1080）
- 配音：`output/audio_*.mp3`（中文）

## 配置

编辑 `config/config.json`：

```json
{
  "bilibili": {
    "sessdata": "你的SESSDATA",
    "bili_jct": "你的bili_jct",
    "buvid3": "你的buvid3"
  }
}
```

获取方法：登录 B站 → F12 → Application → Cookies

## 许可证

MIT
