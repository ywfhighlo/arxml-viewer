#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VSCode扩展后端CLI包装器
提供JSON格式的API接口，包装现有的ARXML和XDM处理器
"""

import json
import sys
import argparse
import os
from pathlib import Path
from processors import VSCodeBackend

def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(description='VSCode ARXML/XDM后端处理器')
    parser.add_argument('command', choices=['parse', 'details', 'validate'])
    parser.add_argument('--file', required=True, help='文件路径')
    parser.add_argument('--node-path', help='节点路径（details命令使用）')
    parser.add_argument('--workspace', help='工作区路径')
    args = parser.parse_args()

    # 获取工作区路径，如果未提供则使用当前目录
    workspace = Path(args.workspace) if args.workspace else Path.cwd()

    backend = VSCodeBackend(workspace=workspace)
    try:
        if args.command == 'parse':
            result = backend.parse_file(args.file)
        elif args.command == 'details':
            if not args.node_path:
                result = {"success": False, "error": "details命令需要--node-path参数"}
            else:
                result = backend.get_node_details(args.node_path, args.file)
        elif args.command == 'validate':
            result = backend.validate_file(args.file)
        else:
            result = {"success": False, "error": "未知命令"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        error_result = {"success": False, "error": str(e)}
        print(json.dumps(error_result, ensure_ascii=False, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()