from abc import ABC, abstractmethod
from typing import List, Dict, Any
import os
import logging

class BaseConverter(ABC):
    """
    所有转换器的抽象基类
    确保所有转换器都遵循统一的接口和行为规范
    """
    
    def __init__(self, output_dir: str, **kwargs):
        """
        初始化转换器
        
        Args:
            output_dir: 输出目录
            **kwargs: 其他配置参数
        """
        self.output_dir = output_dir
        self.config = kwargs
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
    
    @abstractmethod
    def convert(self, input_path: str) -> List[str]:
        """
        执行转换的抽象方法
        
        Args:
            input_path: 输入文件或目录路径
            
        Returns:
            List[str]: 生成的输出文件路径列表
            
        Raises:
            Exception: 转换过程中的任何错误
        """
        pass
    
    def _is_valid_input(self, input_path: str, expected_extensions: List[str]) -> bool:
        """
        验证输入文件是否有效
        
        Args:
            input_path: 输入文件路径
            expected_extensions: 期望的文件扩展名列表
            
        Returns:
            bool: 文件是否有效
        """
        if not os.path.exists(input_path):
            return False
            
        if os.path.isfile(input_path):
            _, ext = os.path.splitext(input_path.lower())
            return ext in expected_extensions
            
        return os.path.isdir(input_path)
    
    def _get_files_by_extension(self, directory: str, extensions: List[str]) -> List[str]:
        """
        获取目录下指定扩展名的所有文件
        
        Args:
            directory: 目录路径
            extensions: 文件扩展名列表
            
        Returns:
            List[str]: 匹配的文件路径列表
        """
        files = []
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                _, ext = os.path.splitext(filename.lower())
                if ext in extensions:
                    files.append(filepath)
        return files
    
    def _generate_output_path(self, input_file: str, new_extension: str) -> str:
        """
        生成输出文件路径
        
        Args:
            input_file: 输入文件路径
            new_extension: 新的文件扩展名（包含点号）
            
        Returns:
            str: 输出文件路径
        """
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        return os.path.join(self.output_dir, f"{base_name}{new_extension}") 