# GitHub Trending 视频任务：历史去重功能需求文档

版本：v0.2
日期：2026-05-11
状态：待 Review

## 1. 背景

当前 GitHub Trending 视频任务每天生成 Top 5 视频。部分项目会连续多天上榜，如果每天都重复介绍，会降低内容新鲜度。

需要增加一个简单的历史去重功能：

- 记录每天采集到的项目和最终选中的项目。
- 生成新视频时，跳过最近一段时间已经成功生成视频的项目。
- 如果某天任务失败或想重试，可以删除当天历史记录，避免被错误过滤。

## 2. 目标

第一版只解决一个问题：**最近介绍过的项目不要重复进入视频**。

不做复杂项目画像，不做趋势分析，不做长期项目聚合统计。

## 3. History 文件

新增文件：

```text
data/projects_history.json
```

推荐结构：

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

### 字段说明

- `version`：历史文件版本，第一版为 `1`。
- `runs`：按日期记录每天任务结果。
- 日期 key：格式 `YYYY-MM-DD`。
- `status`：当天任务状态。
- `fetched`：当天采集到的候选项目 repo id 列表。
- `selected`：当天最终进入视频的项目 repo id 列表。
- `skipped_duplicates`：当天因为历史去重被跳过的项目 repo id 列表。

### repo id 格式

统一使用：

```text
owner/repo
```

优先从项目的 `author + name` 获取；如果没有 `author`，从 GitHub URL 解析。

## 4. 状态定义

`status` 支持：

- `selected`：已完成去重选择，但视频还没生成成功。
- `video_succeeded`：视频生成成功。
- `upload_succeeded`：上传 B站成功。
- `failed`：任务失败。

参与去重的状态只有：

```text
video_succeeded
upload_succeeded
```

不参与去重的状态：

```text
selected
failed
```

这样可以避免任务失败后污染历史。

## 5. 去重策略

默认配置：

```json
{
  "cooldown_days": 7,
  "target_count": 5,
  "fetch_count": 15,
  "allow_repeat_if_insufficient": true
}
```

含义：

- 每天先采集 Top 15 候选项目。
- 从最近 7 天成功 run 的 `selected` 中构建去重集合。
- 候选项目如果命中去重集合，则跳过。
- 最终选择 5 个项目进入视频。
- 如果去重后不足 5 个，允许从重复项目里补足。

补足重复项目时，按原始 Trending 顺序补回即可，不做复杂排序。

## 6. 执行流程

### Step 1：采集候选

```bash
venv/bin/python src/trending_fetcher.py \
  --limit 15 \
  --since daily \
  --output output/trending_candidates.json
```

### Step 2：历史去重

新增脚本：

```text
src/history_deduper.py
```

命令：

```bash
venv/bin/python src/history_deduper.py \
  --input output/trending_candidates.json \
  --output output/trending.json \
  --history data/projects_history.json \
  --target-count 5 \
  --cooldown-days 7 \
  --allow-repeat-if-insufficient
```

执行后：

1. 读取历史文件，不存在则自动创建。
2. 读取最近 7 天成功 run 的 selected。
3. 对候选项目去重。
4. 输出最终项目到 `output/trending.json`。
5. 写入当天 run，状态为 `selected`。

### Step 3：生成项目总结

Agent 基于 `output/trending.json` 继续探索并生成：

```text
output/projects_summary.json
```

### Step 4：生成视频

```bash
venv/bin/python src/workflow.py --projects "$(cat output/projects_summary.json)"
```

视频生成成功后，更新当天 run：

```json
"status": "video_succeeded"
```

### Step 5：上传 B站

```bash
venv/bin/python upload.py
```

上传成功后，可选更新当天 run：

```json
"status": "upload_succeeded"
```

如果上传失败但视频已生成成功，仍保留 `video_succeeded`，因为项目已经被视频介绍过。

## 7. 失败与重试

### history 文件不存在

自动创建：

```json
{
  "version": 1,
  "runs": {}
}
```

### history 文件损坏

备份损坏文件，然后创建新文件：

```text
data/projects_history.json.bak.YYYYMMDD-HHMMSS
```

### 任务失败

如果任务失败，将当天 run 标记为：

```json
"status": "failed"
```

`failed` 不参与后续去重。

### 想重试某一天

可以直接删除当天记录，例如：

```json
"2026-05-11": { ... }
```

删除后重新运行，不会因为当天历史而过滤项目。

## 8. 验收标准

1. 首次运行时能自动创建 `data/projects_history.json`。
2. 能从 Top 15 候选中选择 5 个项目。
3. 最近 7 天 `video_succeeded/upload_succeeded` 的 selected 项目会被跳过。
4. `selected/failed` 状态不参与去重。
5. 去重后不足 5 个时，能从重复项目中按原始顺序补足。
6. 输出的 `output/trending.json` 兼容现有后续流程。
7. 视频生成成功后，当天 run 状态能更新为 `video_succeeded`。
8. 删除当天 run 后，重试不会受当天历史影响。

## 9. 需要修改的地方

1. 新增 `src/history_deduper.py`。
2. 新增 `data/` 目录和 history 文件自动创建逻辑。
3. 更新 `SKILL.md` 执行流程：采集 Top 15 → 去重 → 生成视频。
4. 更新 cron prompt：要求启用历史去重。

第一版不修改 `workflow.py`、`upload.py`、视频合成逻辑。
