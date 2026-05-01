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

**示例：**
- Step 1 采集失败 → 重试 Step 1（最多3次）
- 重试3次后仍失败 → 退出任务，不执行 Step 2-5

## 环境准备

**工作目录**：所有命令都必须在项目根目录（即 `SKILL.md` 所在目录）下执行。

**虚拟环境**：所有 Python 命令必须使用 `venv/bin/python`，而不是系统的 `python3`。

**依赖安装**（首次执行前）：
```bash
python3 -m venv venv
venv/bin/pip install Pillow edge-tts moviepy requests beautifulsoup4 lxml bilibili-api-python
```

## 任务

自动化生成GitHub Trending视频，包含完整流程：采集 → 探索 → 总结 → 生成视频 → 上传。

## 完整流程

### Step 1: 采集 GitHub Trending

运行采集脚本获取今天的Trending列表（建议超时时间：120秒）：

```bash
venv/bin/python src/trending_fetcher.py --limit 3 --since daily --output output/trending.json
```

**参数说明**：
- `--limit`: 项目数量（建议3个，避免视频过长）
- `--since`: 时间范围（daily/weekly/monthly）
- `--output`: 输出文件路径

**输出内容**：
- 项目基本信息（name, url, description, language, stars）
- 项目预览图（保存在 screenshots/ 目录）
- README 前500字符

**验证输出**：
```bash
cat output/trending.json | jq '.projects[0]'
```

### Step 2: 深度探索每个项目

读取 Step 1 生成的 JSON，然后对**每个项目**进行深度探索：

**探索目标**：
1. 访问项目的 GitHub 页面
2. 理解项目的核心功能和价值
3. 分析技术栈和架构特点
4. 评估项目亮点和创新点
5. **获取 preview_image 路径**（从 Step 1 输出中）

**不要只看初始描述！** 使用 WebFetch 工具深入了解项目 README。

### Step 3: 生成项目总结

为每个项目生成口语化的介绍，用于视频配音。

**重要**：必须合并 Step 1 和 Step 2 的数据！

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
        "body": "详细口语化介绍（150-200字）",
        "call_to_action": "引导观众行动的结尾（30字左右）"
      }
    }
  ]
}
```

**关键要求**：
- **必须包含 preview_image 字段**（从 Step 1 获取）
- 口语化表达，适合视频配音
- `hook` 要吸引人，抓住观众注意力
- `body` 通俗易懂，有感染力
- `call_to_action` 引导行动（如"快去试试吧"）

将输出保存为 `output/projects_summary.json`

### Step 4: 生成视频

运行视频生成脚本（建议超时时间：180秒）：

```bash
venv/bin/python src/workflow.py --projects "$(cat output/projects_summary.json)"
```

**脚本自动执行**：
1. 生成幻灯片（PNG）- 使用项目截图和文字
2. 生成语音（MP3）- 使用 Edge-TTS
3. 合成视频（MP4）- 使用 MoviePy

**输出**：`output/trending_video.mp4`

**验证输出**：
```bash
ls -lh output/trending_video.mp4
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
- 标题：`GitHub 今日热榜 Top 3 (日期)`
- 标签：GitHub, 开源项目, 编程, 技术分享, AI
- 分区：科技区 → 知识 → 科学 → 其他

## 文件结构

```
github-trending-video/          # 项目根目录
├── SKILL.md                    # 本文件（Agent指令）
├── upload.py                   # Step 5: 上传脚本
├── config/
│   ├── config.json             # Cookie配置（已配置）
│   └── config.example.json     # 配置模板
├── src/
│   ├── trending_fetcher.py     # Step 1: 采集脚本
│   ├── workflow.py              # Step 4: 视频生成
│   ├── bilibili_uploader.py     # B站上传核心逻辑
│   ├── card_generator.py        # 幻灯片生成
│   ├── tts_generator.py         # 语音生成
│   └── video_composer.py        # 视频合成
├── screenshots/                # 项目截图目录
│   ├── Project1.png
│   ├── Project2.png
│   └── Project3.png
└── output/                     # 输出目录
    ├── trending.json           # Step 1输出
    ├── projects_summary.json   # Step 3输出
    └── trending_video.mp4      # 最终视频
```

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

**问题：B站上传失败**
- 检查 config/config.json 中的 Cookie 是否有效
- Cookie 有效期通常为30天
- 需要登录 B站后从浏览器获取新 Cookie

## 执行要求

1. **完整执行** - 不要跳过任何步骤，从Step 1到Step 5完整执行
2. **数据合并** - Step 3 必须合并 Step 1 的数据（preview_image）
3. **主动探索** - 不要依赖初始描述，深入探索每个项目
4. **准确客观** - 基于实际数据，不要编造
5. **口语表达** - 生成的文本要适合配音
6. **保持简洁** - 每个项目200字以内

开始执行吧！按照Step 1-5完整执行整个工作流。
