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
from converters.md_to_office import MdToOfficeConverter
from converters.office_to_md import OfficeToMdConverter
from converters.diagram_to_png import DiagramToPngConverter

# 转换器工厂映射表
CONVERTER_REGISTRY: Dict[str, Type[BaseConverter]] = {
    'md-to-docx': MdToOfficeConverter,
    'md-to-pdf': MdToOfficeConverter,
    'md-to-html': MdToOfficeConverter,
    'office-to-md': OfficeToMdConverter,
    'diagram-to-png': DiagramToPngConverter,
}

def setup_logging():
    """配置日志系统"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stderr)]
    )

def create_converter(conversion_type: str, output_dir: str, **kwargs) -> BaseConverter:
    """
    工厂方法：根据转换类型创建对应的转换器实例
    
    Args:
        conversion_type: 转换类型
        output_dir: 输出目录
        **kwargs: 其他配置参数
        
    Returns:
        BaseConverter: 转换器实例
        
    Raises:
        ValueError: 不支持的转换类型
    """
    if conversion_type not in CONVERTER_REGISTRY:
        raise ValueError(f"不支持的转换类型: {conversion_type}")
    
    converter_class = CONVERTER_REGISTRY[conversion_type]
    
    # 为 MdToOfficeConverter 传递输出格式
    if conversion_type.startswith('md-to-'):
        output_format = conversion_type.split('-')[-1]  # 提取 docx/pdf/html
        kwargs['output_format'] = output_format
    
    return converter_class(output_dir, **kwargs)

def main():
    """CLI for the Office & Docs Converter."""
    parser = argparse.ArgumentParser(
        description="Markdown Docs Converter - 文档转换工具",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--conversion-type', required=True, 
                       choices=list(CONVERTER_REGISTRY.keys()),
                       help='转换类型')
    parser.add_argument('--input-path', required=True, 
                       help='输入文件或目录路径')
    parser.add_argument('--output-dir', required=True, 
                       help='输出目录')
    parser.add_argument('--template-path', 
                       help='可选的模板文件路径')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='启用详细日志输出')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        setup_logging()
    
    try:
        # 验证输入路径
        if not os.path.exists(args.input_path):
            raise FileNotFoundError(f"输入路径不存在: {args.input_path}")
        
        # 创建转换器
        converter_kwargs = {}
        if args.template_path:
            converter_kwargs['template_path'] = args.template_path
        
        converter = create_converter(
            args.conversion_type, 
            args.output_dir, 
            **converter_kwargs
        )
        
        # 执行转换
        output_files = converter.convert(args.input_path)
        
        # 输出成功结果（JSON 格式）
        result = {
            "success": True,
            "outputFiles": output_files,
            "message": f"成功转换 {len(output_files)} 个文件"
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)
        
    except Exception as e:
        # 输出错误结果（JSON 格式）
        result = {
            "success": False,
            "error": str(e)
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

if __name__ == '__main__':
    main() 