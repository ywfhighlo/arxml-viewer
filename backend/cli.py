#!/usr/bin/env python3
"""
Office & Docs Converter - 命令行接口
作为 VS Code 扩展前端调用的统一入口，使用工厂模式选择并实例化正确的转换器
"""

import argparse
import sys
import json
import os
import logging
from typing import Dict, Type

# 添加当前目录到路径，以便导入 converters 包
sys.path.insert(0, os.path.dirname(__file__))

from converters.base_converter import BaseConverter
# 从 __init__.py 导入注册表
from converters import CONVERTER_REGISTRY

def setup_logging():
    """配置日志系统"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stderr)]
    )

def get_converter(conversion_type: str, output_dir: str, **kwargs) -> BaseConverter:
    """Converter factory"""
    if conversion_type not in CONVERTER_REGISTRY:
        raise ValueError(f"不支持的转换类型: {conversion_type}")
    
    converter_class = CONVERTER_REGISTRY[conversion_type]
    
    # 为 MdToOfficeConverter 传递输出格式
    if conversion_type.startswith('md-to-'):
        output_format = conversion_type.split('-')[-1]  # 提取 docx/pdf/html
        kwargs['output_format'] = output_format
    
    return converter_class(output_dir, **kwargs)

def main():
    parser = argparse.ArgumentParser(
        description="Markdown Hub - 文档转换工具",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--conversion-type', required=True, 
                       choices=list(CONVERTER_REGISTRY.keys()),
                       help='转换类型')
    parser.add_argument('--input-path', required=True, 
                       help='输入文件或目录路径')
    parser.add_argument('--output-dir', required=True, 
                       help='输出目录')
    parser.add_argument('--docx-template-path', 
                       help='可选的 DOCX 模板文件路径')
    parser.add_argument('--pptx-template-path', 
                       help='可选的 PPTX 模板文件路径')
    parser.add_argument('--project-name', help='项目名称 (可选)')
    parser.add_argument('--author', help='作者名称 (可选)')
    parser.add_argument('--mobilephone', help='联系电话 (可选)')
    parser.add_argument('--email', help='电子邮箱 (可选)')
    parser.add_argument('--promote-headings', action='store_true',
                       help='将Markdown标题提升一级（例如## -> 1级标题）')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='启用详细日志输出')
    parser.add_argument('--poppler-path',
                       help='Poppler工具的路径 (用于PDF OCR)')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        setup_logging()

    # 创建进度报告函数
    def report_progress(stage: str, percentage: int = None):
        progress = {
            "type": "progress",
            "stage": stage
        }
        if percentage is not None:
            progress["percentage"] = percentage
        print(json.dumps(progress, ensure_ascii=False), flush=True)

    try:
        # 报告开始转换
        report_progress("开始转换...")

        # 获取转换器类
        converter_class = CONVERTER_REGISTRY.get(args.conversion_type)
        if not converter_class:
            raise ValueError(f"不支持的转换类型: {args.conversion_type}")

        # 准备传递给转换器的参数
        converter_kwargs = {
            'output_dir': args.output_dir,
            'docx_template_path': args.docx_template_path,
            'pptx_template_path': args.pptx_template_path,
            'project_name': args.project_name,
            'author': args.author,
            'email': args.email,
            'mobilephone': args.mobilephone,
            'promote_headings': args.promote_headings,
            'poppler_path': args.poppler_path
        }
        
        # 从 conversion_type 中提取并传递 output_format
        if args.conversion_type.startswith('md-to-'):
            output_format = args.conversion_type.split('-')[-1]
            converter_kwargs['output_format'] = output_format

        # 创建转换器实例
        converter = converter_class(**converter_kwargs)

        # 报告准备阶段完成
        report_progress("正在分析文件...", 25)

        # 执行转换
        report_progress("正在转换...", 50)
        output_files = converter.convert(args.input_path)
        success = len(output_files) > 0

        # 报告完成
        report_progress("转换完成", 100)

        # 返回最终结果
        result = {
            "type": "result",
            "success": success,
            "outputFiles": output_files
        }
        print(json.dumps(result, ensure_ascii=False), flush=True)

    except Exception as e:
        # 报告错误
        error_result = {
            "type": "result",
            "success": False,
            "error": str(e)
        }
        print(json.dumps(error_result, ensure_ascii=False), flush=True)
        sys.exit(1)

if __name__ == '__main__':
    main() 