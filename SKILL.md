---
name: github-trending-video
description: 生成 GitHub Trending 视频。采集当日热榜项目、轻量探索后撰写口播文案、配音、渲染成 1080p 横屏视频，可选上传 B站。触发词：做今天的视频、GitHub 热榜、trending 视频、出今天的视频
version: 2.0.0
license: MIT
---

# GitHub Trending 视频生成

## 这个 Skill 做什么

把 GitHub 当日热榜项目做成一条约 3 分钟的横屏视频。

**关键前提：视频里唯一有价值的部分是你写的文案。** 采集、配音、渲染都是自动的，
它们只是把文案变成视频。如果文案在复述屏幕上的数字，整条视频就是零信息量——
观众的眼睛已经在卡片右边看到那些数字了。

## 完整流程

### 第 1 步：采集

```bash
cd /Users/chengshang/WorkBuddy/trending
export GITHUB_TOKEN=xxx        # 可选，但强烈建议：配额从 60/hr 变 5000/hr
PATH="$PWD/bin:$PATH" venv/bin/python pipeline.py --draft
```

`--draft` 只采集 + 生成文案模板，不配音不渲染。

输出：
- `output/trending.json` — 项目数据，含 `readme`（清洗后的正文，3000 字符内）、
  `topics`、`stars`、`forks`、`currentPeriodStars`、`preview_image`、`license`
- `output/projects_summary.json` — 文案模板，`narrative` 三个字段是空的
- `output/screenshots/*.png` — 项目预览图

### 第 2 步：撰写文案 ← 你的核心工作

读 `output/trending.json` 里每个项目的 `readme` 和 `topics`，然后填写
`output/projects_summary.json` 的 `narrative`：

```json
{
  "narrative": {
    "hook": "约 20 字，用最抓眼的事实开场",
    "body": "110-190 字，回答「这项目是干什么的」",
    "call_to_action": "约 20 字，引导行动"
  }
}
```

**判断标准（只有一条）**：

> 每句话都必须是观众听 GitHub 榜单听不到的。

- ✅「现在的 AI Agent 想读推特、看 B站，都得一个个接 API，还得付费」
- ✅「这是 Google 工程师把团队的工程规范打包给 AI 用了」
- ❌「这是一个面向 AI 智能体的工具，用 Python 编写」—— 对任何 AI 项目都成立
- ❌「目前 89,533 星，7,877 个 fork」—— 卡片右边就写着

**风格要求**：
- 口语化，像跟朋友讲，不要书面语
- 要说清**它解决什么问题**，不是它用了什么技术
- 不确定的就别编。数据以 `trending.json` 里的为准
- 英文描述需要转成中文概述，**不要直接念英文，也不要硬翻**
  （按关键词判断项目类型后用中文重组：这是一个面向 AI 智能体的工具 / 前端设计工具 /
  构建生产级应用的库 / 命令行工具）

### 第 3 步：校验文案

```bash
venv/bin/python -m src.narrative_validator output/projects_summary.json
```

不通过就按提示改。这个校验会拦住套话和数字复述。

### 第 4 步：渲染

```bash
PATH="$PWD/bin:$PATH" venv/bin/python pipeline.py
```

约 6 分钟（有动效，逐帧缩放较慢）。产出 `output/trending_video.mp4`
和 `output/cover.png`。

### 第 5 步：上传（仅在用户明确要求时）

```bash
export BILIBILI_SESSDATA=xxx BILIBILI_BILI_JCT=xxx BILIBILI_BUVID3=xxx
venv/bin/python pipeline.py --upload
```

**上传是外部发布动作。没有用户明确指示，不要执行。**

## 硬性约束

1. **不要伪造数据。** 拿不到 Star 趋势图就显示占位，不要用推测的曲线冒充真实数据。
2. **不要跳过采集健康度断言。** 采集结果为空或全 0 时必须报错降级，
   绝不能让它一路走到「产出 Top 0 视频」。
3. **不要上传未经用户确认的内容。**
4. **不要展开 config.json 或环境变量里的凭据原文**（SESSDATA / bili_jct / buvid3）。
5. **字体不要退回 `load_default()`** —— 那是 6px 位图字体，中文会变方块。
   macOS 上 `PingFang.ttc` 已不存在，用 `STHeiti Medium.ttc` 的 face 1（简体）。

## 常见问题

**Q：渲染要 6 分钟，能不能更快？**
关掉动效：`config.json` 里 `"animate": false`，降到 1 分钟。

**Q：文案校验报错说「没有说明项目能做什么」**
说明 body 在堆砌标签和数字。重读 README，找出**它替用户省了什么麻烦**
或**它让原本做不到的事变成了可能**，写进 body。

**Q：Star 趋势图显示占位**
star-history.com 对超大仓库会返回错误页（实测 27 万星的 ECC 偶发）。
这是正常的，不影响视频产出。绝不能用装饰曲线替代。

**Q：想去重（同一项目连续几天上榜）**
去重逻辑在 `src/history_deduper.py`，7 天冷却。不需要手动干预。

**Q：为什么改了风格但视频没变**
文案是 TTS 输入。改完 `projects_summary.json` 需要重跑 pipeline
才会重新配音渲染。只改 JSON 不会生效。
