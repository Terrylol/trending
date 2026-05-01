# GitHub Trending Video Skill

自动化GitHub Trending视频生成工作流。Agent自主探索项目，生成高质量总结，并制作视频。

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/github-trending-video.git
cd github-trending-video
```

### 2. 安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv

# 安装依赖
venv/bin/pip install Pillow edge-tts moviepy requests beautifulsoup4 lxml bilibili-api-python
```

### 3. 配置 B站 Cookie（可选）

如果要上传到 B站，需要配置 Cookie：

```bash
# 复制配置模板
cp config/config.example.json config/config.json

# 编辑配置文件
nano config/config.json
```

**获取 Cookie 方法**：
1. 登录 B站 (bilibili.com)
2. 打开浏览器开发者工具 (F12)
3. 切换到 Application/Storage → Cookies
4. 复制以下三个值：
   - `SESSDATA`
   - `bili_jct`
   - `buvid3`

### 4. 生成视频

```bash
# 采集 GitHub Trending
venv/bin/python src/trending_fetcher.py --limit 3 --output output/trending.json

# 生成视频（使用 Mock 数据演示）
venv/bin/python src/workflow.py --projects '{"projects": [{"name": "Test", "url": "https://github.com/test/test", "language": "Python", "stars": 100, "narrative": {"hook": "测试项目", "body": "这是一个测试项目", "call_to_action": "试试吧"}}]}'
```

## 架构

**Agent负责（智能部分）：**
- 深度探索GitHub项目（README、代码、commits等）
- 多轮推理分析项目特点
- 生成口语化的项目总结（JSON格式）

**脚本负责（自动化部分）：**
- 生成幻灯片（Pillow）
- 生成语音（Edge-TTS）
- 合成视频（MoviePy）
- 上传B站（可选）

## 工作流程

```
┌─────────────────────────────────────────────────────────┐
│  Step 1: 获取 GitHub Trending 列表                      │
│  trending_fetcher.py                                    │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Step 2: Agent 深度探索每个项目                         │
│  - 访问 README.md                                       │
│  - 分析代码结构                                         │
│  - 查看技术栈                                           │
│  - 评估项目质量                                         │
│  - 获取项目预览图                                       │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Step 3: Agent 生成结构化总结                           │
│  {                                                      │
│    "name": "project-name",                             │
│    "url": "https://github.com/owner/repo",             │
│    "preview_image": "screenshots/project.png",         │
│    "narrative": {                                      │
│      "hook": "吸引人的开场白",                          │
│      "body": "详细介绍（150-200字）",                  │
│      "call_to_action": "引导行动的结尾"                │
│    }                                                   │
│  }                                                     │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Step 4: 脚本生成视频                                   │
│  workflow.py                                            │
│  - 幻灯片（card_generator.py）                          │
│  - 语音（tts_generator.py）                             │
│  - 视频合成（video_composer.py）                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Step 5: 上传到 B站（可选）                             │
│  upload.py                                              │
└─────────────────────────────────────────────────────────┘
```

## 使用方式

### 方式1: 命令行手动执行

适合开发调试：

```bash
# Step 1: 采集 Trending
venv/bin/python src/trending_fetcher.py --limit 3 --since daily --output output/trending.json

# Step 2-3: 手动创建项目总结（参考 output/trending.json）
# 编辑 output/projects_summary.json

# Step 4: 生成视频
venv/bin/python src/workflow.py --projects "$(cat output/projects_summary.json)"

# Step 5: 上传（可选）
venv/bin/python upload.py
```

### 方式2: OpenCode Agent 自动执行

适合自动化生成：

```
用户: 使用 github-trending-video skill 生成今天的视频

Agent:
[加载 skill]
[执行 Step 1-5 全流程]
✓ 视频已生成: output/trending_video.mp4
```

### 方式3: 仅生成视频（已有总结）

如果已有项目总结，直接生成视频：

```bash
venv/bin/python src/workflow.py --projects '{"projects": [
  {
    "name": "DeepSeek-R1",
    "url": "https://github.com/deepseek-ai/DeepSeek-R1",
    "language": "Python",
    "stars": 45000,
    "preview_image": "screenshots/DeepSeek-R1.png",
    "narrative": {
      "hook": "开源模型也能媲美GPT了！",
      "body": "DeepSeek-R1 是一款开源的深度推理模型...",
      "call_to_action": "快去试试吧！"
    }
  }
]}'
```

## 输入输出格式

### Step 1 输出格式（trending.json）

```json
{
  "projects": [
    {
      "name": "project-name",
      "author": "owner",
      "url": "https://github.com/owner/repo",
      "description": "简短描述",
      "language": "Python",
      "stars": 1000,
      "preview_image": "screenshots/project-name.png",
      "readme": "README前500字符..."
    }
  ]
}
```

### Step 3 输出格式（projects_summary.json）

**重要**：必须合并 Step 1 的数据，包含 `preview_image`！

```json
{
  "projects": [
    {
      "name": "DeepSeek-R1",
      "url": "https://github.com/deepseek-ai/DeepSeek-R1",
      "language": "Python",
      "stars": 45000,
      "preview_image": "screenshots/DeepSeek-R1.png",
      "narrative": {
        "hook": "开源模型也能媲美GPT了！",
        "body": "DeepSeek-R1 是一款开源的深度推理模型，采用强化学习技术，让模型学会像人一样一步步思考。完全开源，支持本地部署。",
        "call_to_action": "想在自己的电脑上跑AI？快去试试吧！"
      }
    }
  ]
}
```

**关键要求**：
- `preview_image` 字段必须有（从 Step 1 获取）
- `hook` 30字左右，吸引人
- `body` 150-200字，口语化
- `call_to_action` 30字左右，引导行动

## 依赖

**必须依赖：**
- Python 3.8+
- Pillow（图片处理）
- Edge-TTS（语音生成）
- MoviePy（视频合成）

**可选依赖：**
- requests（爬取 GitHub Trending）
- beautifulsoup4（解析 HTML）
- lxml（HTML 解析）
- bilibili-api-python（上传 B站）

## 文件结构

```
github-trending-video/
├── README.md                    # 用户文档
├── SKILL.md                     # Agent指令
├── upload.py                    # 上传脚本
├── test_upload.py               # 上传测试
├── .gitignore                   # Git忽略规则
├── config/
│   ├── config.example.json      # 配置模板
│   └── config.json              # 实际配置（不提交）
├── src/
│   ├── trending_fetcher.py      # 采集脚本
│   ├── workflow.py              # 视频生成工作流
│   ├── card_generator.py        # 幻灯片生成
│   ├── tts_generator.py         # 语音生成
│   ├── video_composer.py        # 视频合成
│   └── bilibili_uploader.py     # B站上传核心
├── screenshots/                 # 项目截图（运行时生成）
└── output/                      # 输出文件（运行时生成）
    ├── trending.json
    ├── projects_summary.json
    ├── slide_*.png
    ├── audio_*.mp3
    └── trending_video.mp4
```

## 常见问题

### Q: 采集超时怎么办？

```bash
# 超时时间已设置为20秒
# 如果仍然超时，检查网络连接
# 重试最多3次
venv/bin/python src/trending_fetcher.py --limit 3 --output output/trending.json
```

### Q: 视频文字显示不全？

字号已经优化为：
- 项目名称：80px
- 正文内容：42px
- 标签文字：34px

文字会自动换行，充分利用屏幕空间。

### Q: 项目截图未显示？

检查 `preview_image` 字段：
```bash
cat output/projects_summary.json | jq '.projects[0].preview_image'
```

应该输出类似：`"screenshots/ProjectName.png"`

### Q: B站上传失败？

1. 检查 Cookie 配置：
```bash
cat config/config.json | jq '.bilibili'
```

2. 测试上传：
```bash
venv/bin/python test_upload.py
```

3. Cookie 有效期约30天，过期需要重新获取

## 开发调试

### 测试单个模块

```bash
# 测试采集
venv/bin/python src/trending_fetcher.py --limit 1 --output /tmp/test.json

# 测试幻灯片生成
venv/bin/python -c "
import sys; sys.path.insert(0, 'src')
from card_generator import CardGenerator
gen = CardGenerator({})
gen.generate_title_card('2026.05.01', '/tmp/test_title.png')
"

# 测试上传（使用测试账号）
venv/bin/python test_upload.py
```

### 查看生成过程

视频生成时会显示：
- 每张幻灯片的生成进度
- 每段语音的时长
- 视频合成进度

## 许可证

MIT