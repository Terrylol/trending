#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时脚本：从文件读取项目数据并运行视频生成工作流"""
import json
import sys
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from workflow import VideoWorkflow

def main():
    # 从文件读取项目数据
    with open('output/projects_summary.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    projects = data.get('projects', [])
    
    if not projects:
        print("错误：没有找到项目数据")
        sys.exit(1)
    
    print(f"加载了 {len(projects)} 个项目")
    
    # 执行工作流
    workflow = VideoWorkflow()
    video_path = workflow.run(projects)
    
    print(f"\n✓ 视频已生成: {video_path}")

if __name__ == '__main__':
    main()