# trending 重构方案

> 状态：待审阅
> 日期：2026-10-03
> 仓库：github.com/Terrylol/trending

---

## 一、共识决策（拷问已锁定）

以下每一项都由你拍板，不再是开放问题。

| 维度 | 决策 | 关键推论 |
|---|---|---|
| **定位** | 个人日更号 | 量取胜，稳定 > 惊艳，流水线可靠性优先级最高 |
| **渲染路线** | MoviePy/Pillow 纯渲染 | 放弃 Remotion，砍掉 Node/Chromium 整条依赖链 |
| **样式重点** | 静态排版优先 | 接受 MoviePy 动画上限（位移/透明度/时长），不做动态效果迭代 |
| **成片规格** | 1920×1080 横屏 | 24fps，需要响应式缩放（当前布局是 720p 硬编码绝对像素） |
| **取数** | Trending HTML 为主 + 降级兜底 | 已完成数据源调研，结论见第三节 |
| **TTS** | edge-tts | 完全免费、无需 API key |
| **Star 趋势图** | 继续用 star-history.com | 但必须加超时 + 并发预取 + 失败降级，不能同步阻塞 |
| **编排** | 单命令 pipeline | 5 步串成一个命令，Agent 只负责写文案那一步 |
| **上传** | 保留但显式开关 | 默认不上传，`--upload` 才触发；上传前做完整校验 |
| **去重** | 保持 7 天冷却 | 不调整 |
| **凭据** | 立即吊销 + 改写 git 历史 | 用户本人立即吊销，我同步做代码侧防护 |
| **交付** | 先出 PLAN.md 审阅 | 本文档 |

### 明确不做的事

- 不做竖屏版本（当前所有布局为横屏设计，改竖屏是内容重做）
- 不做动态效果迭代（spring 弹性、clip-path 文字揭示、光晕呼吸、旋转圆环全部移除）
- 不加第三层降级源（RSSHub 实测公共实例全挂，自建不划算）
- 不自动上传到 B 站（必须显式 `--upload`）
- 不改去重冷却天数（保持 7 天）

---

## 二、当前代码的真实状态（实测，非推测）

这一节是重构的判断依据。**以下全部经过实测验证，不是代码阅读推测。**

### 2.1 数据已经静默失效（最紧急）

| 数据 | 现有代码 | 实测结果 |
|---|---|---|
| fork 数 | `a[href*='/network/members']` | **19 个项目全部命中 0**，GitHub 已改为 `/forks` |
| 日增 star | `span(string=re.compile('stars today'))` | **19 个项目全部命中 0**，因文本被包在 `<svg>` 兄弟节点，`find(string=)` 必然返回 None |

这两个字段一直恒为 0，而流程无任何报错。**视频里的"今日新增"数字从来没正确显示过。**

修复：
- fork → `a[href$="/forks"]`（实测 19/19 命中）
- 日增 star → `re.search(r'([\d,]+)\s+stars\s+today', article.get_text(' ', strip=True))`（实测 19/19）

### 2.2 macOS 字体问题（实测）

| 项 | 实测结果 |
|---|---|
| `/System/Library/Fonts/PingFang.ttc` | **不存在**（现代 macOS 已移除），macOS 首选字体是死的 |
| `STHeiti Medium.ttc` face 0 | 加载成功，但返回 `('Heiti TC', 'Medium')` — **繁体字形** |
| `STHeiti Medium.ttc` face 1 | 返回 `('Heiti SC', 'Medium')` — 简体，这才是该用的 |

`card_generator.py:58` 的裸 `except:` + 不指定 `index` ⇒ **卡片上的中文一直是繁体字形**。

### 2.3 静默失败链（最危险）

1. GitHub 改版 → `articles = []`
2. `trending_fetcher.py:52` 打印 `✓ 获取 0 个项目` 并**正常 return**
3. `history_deduper.py` 写入 `selected: []`
4. `remotion_composer.py:47` 校验 `len(audio_files) != len(projects) + 2` → `2 != 2` → **通过**
5. `_validate_video` 只检查流存在性 → **通过**
6. `bilibili_uploader.py` 生成标题 `GitHub 今日热榜 Top 0 (20261003)` → **上传成功**

一条 5 步静默链把"采集全失败"变成"发布一条只有片头片尾的 Top 0 视频"。

### 2.4 元数据请求浪费（实测）

- `GET /repos/{o}/{r},{o2}/{r2}` 逗号批量端点**已废弃，实测 2/11/31 个仓库全部 404**，不要按文档写
- GraphQL alias（`r0`..`r14`）**一次请求拉 24 个仓库元数据，cost=1，~2s**，实测 23/24 解析成功
- 当前实现：15 项目 × 3 请求 = **45 次 core 调用**，匿名配额 60/hr，两跑即触限
- README 走 `raw.githubusercontent.com/{o}/{r}/HEAD/README.md` **零配额**
- `github.personal_access_token` 从未生效（`trending_fetcher.py:292` 传空字典），且用了 `token ` 前缀而非 `Bearer`

### 2.5 其他已确认缺陷

| 问题 | 位置 |
|---|---|
| `renderer` 默认值 `moviepy` 但 `config.example.json` 缺该键 | `workflow.py:56` |
| config 缺失时静默降级而非报错 | `workflow.py:65-75` |
| 预览图按 `repo` 命名不含 owner，跨 owner 撞名 + macOS 大小写不敏感双重覆盖 | `trending_fetcher.py:164` |
| `_enrich_projects` 的 name 兜底匹配与其 docstring（明确要防同名串数据）直接矛盾 | `workflow.py:137` |
| `select_projects` 补足时不从 `skipped_ids` 移除，写出自相矛盾的 history | `history_deduper.py:148-153` |
| `preview_image` 兜底回退到项目根相对路径，`staticFile()` 必然 404 | `ProjectScene.tsx:68` |
| `tts.voice` / `tts.speed` / `video.limit` 全是死配置 | 多处 |
| 日期格式 4 处独立硬编码（`%Y.%m.%d` ×2 / `%Y%m%d` / `%Y年%m月%d日`），跨零点会不一致 | 多处 |
| 日期传给 `generate_intro_audio(date)` 但函数从未使用该参数 | `tts_generator.py:59` |
| `star_history_chart` 是纯死字段（Python 从不写，TS 读它做兜底） | `types.ts:18` |
| fetcher 产出 `languageColor`/`forks`/`currentPeriodStars`/`avatar`/`readme` 5 字段在 MoviePy 路线下全被丢弃 | 多处 |
| `render.mjs` 是坏掉的死代码（分辨率逻辑已废）；`still.mjs:12` 缺 `existsSync` 守卫 | `remotion/` |
| `README.md:54` 的 `python -m src.bilibili_uploader` 是空操作（无 `__main__` 守卫） | README |
| SKILL.md 硬编码 Linux 路径 `/root/.agents/skills/...`（macOS 上不存在） | SKILL.md |
| SKILL.md 文件树漏了 `run_workflow.py` 和 `tts/volcengine.py` | SKILL.md |
| `remotion/package.json` 6 个依赖全钉 `latest`，且 `npm install` 被代码自动触发 | `package.json` |
| 零单元测试；唯一 `test_*.py` 是会真实投稿的脚本 | 全仓库 |

---

## 三、取数方案（基于实测调研）

### 3.1 关键结论

1. **GitHub 从未提供 Trending 官方 API**，2026 年状态未变。
2. **第三方源实测全部不可用**：RSSHub 公共实例（超时/503）、`api.ghloc.com`（502）、`github-trending-api.now.sh`（308 后无服务）、`bonfy/github-trending`（已停更）。唯一可用的 `antonkomarev/github-trending-archive` 也是爬 HTML，**不独立于 GitHub DOM**，且同日 Top5 顺序与实时榜完全不同（集合重叠仅 9/19）。
3. **search API 无法替代 Trending**：实测 Top10 **零重叠**。根本原因是 GitHub search 索引里没有 star 时间序列 —— 存量排序 ≠ 增速排序。且 Trending 有"老项目翻红"（实测 `affaan-m/ECC` 27 万星突然爆发），`created:>DATE` 永远抓不到。
4. **star-history.com 只有 SVG，5 个 JSON 路径全 404**，延迟 2.5–25s，偶发 403，`cli/cli` 直接拒。

### 3.2 三层架构

**第一层 — 主路径：Trending HTML（重写解析层 + 强制断言）**

- 修两个失效选择器（见 2.1）
- **双断言硬门槛**：`len(projects) >= 5` **且** `any(p['currentPeriodStars'] > 0)`。不满足即抛异常降级，**绝不允许返回空列表或全 0**
- 选择器 + 断言收敛为单一 `parse()` 入口
- 配一份**真实 HTML 快照黄金测试**（存 3 份不同日期的 HTML），下次改版是测试失败报警，而不是线上静默错误

**第二层 — 降级：search API 算 trending**

```
q=created:>{今天-30天}+stars:>200&sort=stars&per_page=20
```
- 过滤 `fork:true` / `archived:true`
- 按 `stars / age_days` 排序近似增速，取 Top 5
- 1 次请求，~0.9s
- **必须在文案和口播里标注"按 star 增速排序"**，不能假装是 GitHub 日榜
- 触发条件是"解析断言失败"，不是"网络错误"

**第三层 — 兜底：本地缓存**

读上次成功的采集结果，并在视频里标注日期。降级时给用户看昨天的项目，比给错项目更糟。

**不要指望 RSSHub 当降级源** —— 公共实例实测全挂，自建是重运维负担，收益不抵成本。

### 3.3 元数据瘦身（重构最大收益）

| 项 | 现在 | 改后 |
|---|---|---|
| 元数据 | 45 次 core 调用 | **1 次 GraphQL**（alias `r0`..`r14`，cost=1，~2s） |
| README | 15 次 API + base64 解码 | `raw.githubusercontent.com` **零配额** |
| 预览图 | 15 次（opengraph，不限配额） | 不变 |
| PAT | 从未生效 + 错用 `token ` 前缀 | `Authorization: Bearer`，真正接上 |

删除 `_fetch_repo_metadata` 和 `_fetch_readme` 的 API 调用部分。GraphQL 坑：alias 不能含 `-`，必须用 `r0/r1/r2` 下标。

### 3.4 Star 趋势图实现约束

按你的决策保留 star-history.com，但**必须**：

1. **超时**（5s 硬超时，失败即降级）
2. **并发预取**（5 个项目并发拉，不串行阻塞）
3. **失败降级为占位图**（复用现有 `Star history unavailable` 样式）

理由：实测延迟 2.5–25s，而当前 `remotion_composer.py:218` 是同步阻塞调用，一个 25 秒请求会卡住渲染。改为 MoviePy 后这个位置变成 `card_generator` 的图片准备阶段，同样不能阻塞。

---

## 四、分阶段任务

### 阶段 0：安全（立即，独立于其他阶段）

| # | 任务 | 验收标准 |
|---|---|---|
| 0.1 | 用户在 B 站登出设备、重置会话 | 旧 SESSDATA 失效 |
| 0.2 | 凭据改走环境变量 / `.env`（`gitignore` 覆盖），删除 `test_upload.py` | 代码中无任何硬编码凭据 |
| 0.3 | 重写 git 历史清除凭据 | `git log -p \| grep -i sessdata` 无命中 |
| 0.4 | 加 pre-commit secret 扫描钩子 | 尝试提交含 `sessdata` 的文件被拦截 |
| 0.5 | 修 `bilibili_uploader.py:125` 的 `test_credential` 命名 | 不再被 pytest 误收集 |

> ⚠️ 0.3 需 force push。所有已有 clone 需重新克隆。这是不可逆操作。

### 阶段 1：取数层

| # | 任务 | 验收标准 |
|---|---|---|
| 1.1 | 重写 `trending_fetcher.parse()`，修两个失效选择器 | fork 和日增 star 实测均有非零值 |
| 1.2 | 加双断言 + 降级到 search API | 模拟改版时不返回空列表 |
| 1.3 | 加第三层本地缓存兜底 | 前两层全失败时仍能出片 |
| 1.4 | 元数据改 GraphQL 批量，README 走 raw | core 调用从 45 降到 0-1 |
| 1.5 | 真正接上 PAT（`Bearer` 前缀） | 配额从 60/hr 变 5000/hr |
| 1.6 | 预览图文件名加 owner 前缀 + 小写归一 | 同名仓库不互相覆盖 |
| 1.7 | 存 3 份真实 HTML 快照做黄金测试 | `pytest` 通过 |

### 阶段 2：编排层

| # | 任务 | 验收标准 |
|---|---|---|
| 2.1 | 新建 `pipeline.py`，串起 5 步 | 单命令跑完采集→渲染 |
| 2.2 | 上传改为显式 `--upload` 开关 | 默认不上传 |
| 2.3 | 上传前完整性校验（项目数≥5、时长>0、音视频流齐全） | 校验不过则拒绝上传 |
| 2.4 | 日期统一由单一模块产出 | 全流程日期一致 |
| 2.5 | config 缺失时显式报错并提示模板路径 | 不再静默降级 |

### 阶段 3：渲染层

| # | 任务 | 验收标准 |
|---|---|---|
| 3.1 | 删除 Remotion 整条链（`remotion/` 目录、`remotion_composer.py`） | 无 Node 依赖 |
| 3.2 | 分辨率改 1080p，布局做响应式缩放 | 1920×1080 下内容不挤在左上角 |
| 3.3 | 字体修复：显式指定 face index=1（Heiti SC），移除裸 `except` | 中文简体字形，非方块 |
| 3.4 | 字体路径适配现代 macOS（PingFang 已移除） | 自动探测可用字体 |
| 3.5 | 时长一致性校验（`abs(frames/fps - audio_dur) < 1/fps`） | 不允许音频被静默截断 |
| 3.6 | `ffprobe` 缺失处理（补 Remotion 侧漏掉的另一半） | 无 ffprobe 时明确警告而非崩溃 |

### 阶段 4：样式层

| # | 任务 | 验收标准 |
|---|---|---|
| 4.1 | 重写 `card_generator` 排版：配色体系、字体层级、版式对齐 | 1080p 下版式均衡 |
| 4.2 | 移除 720p 假设的硬编码尺寸 | 布局与分辨率解耦 |
| 4.3 | 补齐被丢弃的字段（forks、日增 star 修复后要在卡片上显示） | 数据完整呈现 |
| 4.4 | star-history 加超时 + 并发预取 + 降级 | 单项目不阻塞超过 5s |
| 4.5 | 中英文混排宽度处理（避免文字溢出/重叠） | 长短名称都不破版 |

### 阶段 5：清理与文档

| # | 任务 | 验收标准 |
|---|---|---|
| 5.1 | 删除死代码：`render.mjs`、`still.mjs`、`card_generator` 私有方法跨类调用 | 无未引用模块 |
| 5.2 | 抽离 `_fetch_star_history_image` 为独立模块 | 无 `_private` 跨类调用 |
| 5.3 | 数据模型收敛（消除 `preview_image`/`public_preview_image`、`star_history_image`/`star_history_chart` 双重命名） | 每语义单一字段 |
| 5.4 | 补单元测试：`repo_id`、窗口边界、`select_projects` 补足分支、`parse_day` | `pytest` 全绿 |
| 5.5 | 重写 README / SKILL.md：修正所有与代码不一致处 | 文档零错误命令 |
| 5.6 | 更新 frontmatter 与文件树 | 文档完整 |

---

## 五、风险与取舍

| 风险 | 应对 |
|---|---|
| **force push 会打断你其他工作** | 阶段 0.3 单独执行，执行前我会再次确认 |
| **1080p + PIL 渲染变慢** | 已确认 `ImageClip` 走 ffmpeg 底层合成不逐帧迭代像素，可行 |
| **去掉动态效果后观感下降** | 这是你明确接受的取舍。用配色/排版/信息密度补偿 |
| **search API 降级时名单与日榜不符** | 视频与文案明确标注"按 star 增速排序"，不伪装成日榜 |
| **star-history 偶发失败** | 三重降级 + 5s 超时 + 占位图，最坏情况是图缺失而非流程中断 |
| **MoviePy 首次使用需装依赖** | `moviepy>=2.0`（注意代码用的是 2.x 的 `from moviepy import` 导入风格），README 写明 |

---

## 六、待你确认

1. 本文档是否认可？
2. 阶段 0.3 的 force push 是否可以执行？何时执行？
3. 是否需要在每个阶段完成后暂停给你验收，还是全部做完一起看？
