#!/usr/bin/env python3
"""History-based dedupe for GitHub Trending video workflow.

Keeps a minimal per-day history:
{
  "version": 1,
  "runs": {
    "YYYY-MM-DD": {
      "status": "selected|video_succeeded|upload_succeeded|failed",
      "fetched": ["owner/repo"],
      "selected": ["owner/repo"],
      "skipped_duplicates": ["owner/repo"]
    }
  }
}
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

SUCCESS_STATUSES = {"video_succeeded", "upload_succeeded"}
DEFAULT_HISTORY = {"version": 1, "runs": {}}


def repo_id(project: Dict) -> Optional[str]:
    """Return normalized owner/repo id for a project."""
    author = (project.get("author") or project.get("owner") or "").strip().strip("/")
    name = (project.get("name") or "").strip().strip("/")
    if author and name:
        return f"{author}/{name}"

    url = (project.get("url") or "").strip().rstrip("/")
    if "github.com/" in url:
        parts = url.split("github.com/", 1)[1].split("/")
        if len(parts) >= 2 and parts[0] and parts[1]:
            return f"{parts[0]}/{parts[1]}"

    return None


def load_json_file(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json_file(path: Path, data: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_history(path: Path) -> Dict:
    if not path.exists():
        history = dict(DEFAULT_HISTORY)
        history["runs"] = {}
        write_json_file(path, history)
        return history

    try:
        history = load_json_file(path)
    except json.JSONDecodeError:
        backup = path.with_suffix(path.suffix + f".bak.{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(backup))
        print(f"⚠ history JSON 损坏，已备份到: {backup}")
        history = dict(DEFAULT_HISTORY)
        history["runs"] = {}
        write_json_file(path, history)
        return history

    if not isinstance(history, dict):
        history = dict(DEFAULT_HISTORY)
        history["runs"] = {}
    history.setdefault("version", 1)
    if not isinstance(history.get("runs"), dict):
        history["runs"] = {}
    return history


def parse_day(day: Optional[str]) -> str:
    if day:
        # Validate format.
        datetime.strptime(day, "%Y-%m-%d")
        return day
    return date.today().isoformat()


def successful_selected_in_window(history: Dict, today: str, cooldown_days: int) -> Set[str]:
    today_date = datetime.strptime(today, "%Y-%m-%d").date()
    start = today_date - timedelta(days=cooldown_days)
    dedupe: Set[str] = set()

    for day, run in history.get("runs", {}).items():
        try:
            run_date = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            continue

        # Look back previous cooldown_days, exclude today's run so failed/retry cleanup is simple.
        if not (start <= run_date < today_date):
            continue

        if not isinstance(run, dict) or run.get("status") not in SUCCESS_STATUSES:
            continue

        for rid in run.get("selected", []) or []:
            if isinstance(rid, str) and rid:
                dedupe.add(rid)

    return dedupe


def load_projects(input_path: Path) -> List[Dict]:
    data = load_json_file(input_path)
    if isinstance(data, dict) and isinstance(data.get("projects"), list):
        return data["projects"]
    if isinstance(data, list):
        return data
    raise ValueError(f"输入文件格式错误: {input_path}")


def select_projects(projects: List[Dict], dedupe_ids: Set[str], target_count: int, allow_repeat: bool) -> Tuple[List[Dict], List[str], List[str], List[str]]:
    selected: List[Dict] = []
    skipped_projects: List[Tuple[Dict, str]] = []
    fetched_ids: List[str] = []
    selected_ids: List[str] = []
    skipped_ids: List[str] = []

    for project in projects:
        rid = repo_id(project)
        if rid:
            fetched_ids.append(rid)
        if rid and rid in dedupe_ids:
            skipped_projects.append((project, rid))
            skipped_ids.append(rid)
            continue
        if len(selected) < target_count:
            selected.append(project)
            if rid:
                selected_ids.append(rid)

    if allow_repeat and len(selected) < target_count:
        for project, rid in skipped_projects:
            if len(selected) >= target_count:
                break
            selected.append(project)
            selected_ids.append(rid)

    return selected, fetched_ids, selected_ids, skipped_ids


def run_select(args) -> int:
    today = parse_day(args.date)
    history_path = Path(args.history)
    history = load_history(history_path)
    projects = load_projects(Path(args.input))

    dedupe_ids = successful_selected_in_window(history, today, args.cooldown_days)
    selected, fetched_ids, selected_ids, skipped_ids = select_projects(
        projects,
        dedupe_ids,
        args.target_count,
        args.allow_repeat_if_insufficient,
    )

    output_data = {"projects": selected}
    if not args.dry_run:
        write_json_file(Path(args.output), output_data)
        history["runs"][today] = {
            "status": "selected",
            "fetched": fetched_ids,
            "selected": selected_ids,
            "skipped_duplicates": skipped_ids,
        }
        write_json_file(history_path, history)

    print(f"✓ 候选项目: {len(projects)}")
    print(f"✓ 去重集合: {len(dedupe_ids)}")
    print(f"✓ 选中项目: {len(selected)}")
    print(f"✓ 跳过重复: {len(skipped_ids)}")
    if args.dry_run:
        print("dry-run: 未写入输出和历史文件")
    return 0


def update_status(args) -> int:
    today = parse_day(args.date)
    history_path = Path(args.history)
    history = load_history(history_path)
    runs = history.setdefault("runs", {})
    run = runs.setdefault(today, {"fetched": [], "selected": [], "skipped_duplicates": []})
    run["status"] = args.status
    write_json_file(history_path, history)
    print(f"✓ 已更新 {today} status={args.status}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="GitHub Trending history deduper")
    parser.add_argument("--history", default="data/projects_history.json", help="history JSON path")
    parser.add_argument("--date", help="run date YYYY-MM-DD, default today")

    sub = parser.add_subparsers(dest="command")

    select_cmd = sub.add_parser("select", help="dedupe candidates and write selected trending.json")
    select_cmd.add_argument("--input", required=True, help="candidate JSON path")
    select_cmd.add_argument("--output", required=True, help="selected JSON path")
    select_cmd.add_argument("--target-count", type=int, default=5)
    select_cmd.add_argument("--cooldown-days", type=int, default=7)
    select_cmd.add_argument("--allow-repeat-if-insufficient", action="store_true")
    select_cmd.add_argument("--dry-run", action="store_true")
    select_cmd.set_defaults(func=run_select)

    status_cmd = sub.add_parser("status", help="update today's run status")
    status_cmd.add_argument("--status", required=True, choices=["selected", "video_succeeded", "upload_succeeded", "failed"])
    status_cmd.set_defaults(func=update_status)

    args = parser.parse_args()

    # Backward-compatible shorthand: allow options without explicit "select".
    if args.command is None:
        parser.print_help()
        return 2

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
