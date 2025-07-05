#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARXML处理器 - 基于autosar44库的ARXML文件解析器

专门用于读取和解析ARXML文件，提取配置容器和参数信息，
将其转换为与XDM处理器兼容的数据结构。
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
try:
    from .xml_processor import XMLProcessor
except ImportError:
    from xml_processor import XMLProcessor
import xml.etree.ElementTree as ET
import re

# 导入autosar44库
# 添加third_party目录到Python路径
third_party_path = Path(__file__).parent / 'third_party'
if third_party_path.exists():
    sys.path.insert(0, str(third_party_path))

try:
    from autosar44 import autosar44
except ImportError:
    raise ImportError("无法导入autosar44库。请确保autosar44已安装或存在于third_party目录中。")


class ARXMLProcessor:
    """ARXML文件处理器"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.logger = self._setup_logging()
        self.is_definition_file = False  # 默认不是定义文件
        
        # 解析结果存储
        self.root_element = None
        self.packages = {}
        self.containers = {}
        self.variables = {}
        self.module_configurations = {}
        
        # 统计信息
        self.parse_statistics = {
            'total_packages': 0,
            'total_containers': 0,
            'total_parameters': 0,
            'parse_errors': 0,
            'parse_time': 0
        }
    
    def _setup_logging(self) -> logging.Logger:
        """设置日志系统"""
        logger = logging.getLogger('ARXMLProcessor')
        if not logger.handlers:
            level = logging.DEBUG if self.verbose else logging.INFO
            handler = logging.StreamHandler(sys.stderr) # 输出到stderr
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(level)
        return logger
    
    def parse_arxml_file(self, arxml_file_path: str) -> bool:
        """
        解析ARXML文件，智能选择解析器。
        - 优先使用autosar44处理配置值文件。
        - 对模块定义(BSWMD)文件或autosar44解析失败的情况，使用XMLProcessor。
        """
        try:
            start_time = datetime.now()
            self.logger.info(f"开始解析ARXML文件: {arxml_file_path}")

            if not os.path.exists(arxml_file_path):
                self.logger.error(f"ARXML文件不存在: {arxml_file_path}")
                return False

            # 智能解析策略
            is_bswmd = 'bswmd' in arxml_file_path.lower()
            
            # 优先使用autosar44
            self.root_element = autosar44.parse(arxml_file_path, silence=not self.verbose)

            # 检查autosar44的解析结果是否有效
            # 如果是BSWMD，autosar44在非详细模式下可能返回空结果，这是正常的
            # 如果是verbose模式，它可能返回一个字符串，这是我们需要处理的
            is_string_output = isinstance(self.root_element, str)

            if is_bswmd or is_string_output:
                self.logger.info("检测到BSWMD文件或autosar44返回原始XML，切换到XMLProcessor。")
                self.is_definition_file = True  # 明确这是一个定义文件
                return self._parse_with_xml_processor(arxml_file_path, start_time)

            if not self.root_element:
                self.logger.warning("autosar44解析失败或返回空，尝试使用XMLProcessor作为备用。")
                return self._parse_with_xml_processor(arxml_file_path, start_time)

            # --- 如果autosar44成功解析 ---
            self.logger.info("使用autosar44解析器成功。")
            self._extract_packages()
            self._extract_module_configurations()
            self._build_container_hierarchy()
            
            # 检查是否提取到了内容，如果没有，也尝试备用解析器
            if not self.containers and not self.variables:
                self.logger.warning("autosar44解析成功但未提取到有效内容，尝试备用解析器。")
                return self._parse_with_xml_processor(arxml_file_path, start_time)

            self.parse_statistics['total_parameters'] = len(self.variables)
            self._finalize_parsing(start_time)
            return True

        except Exception as e:
            self.logger.error(f"解析ARXML文件时发生未知错误: {e}", exc_info=self.verbose)
            return False

    def _parse_with_xml_processor(self, arxml_file_path: str, start_time: datetime) -> bool:
        """使用备用XMLProcessor进行解析"""
        self.logger.info("检测到BSWMD文件或autosar44返回原始XML，切换到XMLProcessor。")
        self.is_definition_file = True  # 明确这是一个定义文件
        xml_parser = XMLProcessor(verbose=self.verbose)
        root = xml_parser.parse(arxml_file_path)
        if not root:
            self.logger.error("XMLProcessor也无法解析此文件。")
            return False

        structure = xml_parser.extract_structure(root)
        
        # 将XMLProcessor提取的数据转换为ARXMLProcessor的格式
        self.containers = structure.get('containers', {})
        self.variables = structure.get('parameters', {})
        
        # 更新统计数据
        self.parse_statistics['total_containers'] = len(self.containers)
        self.parse_statistics['total_parameters'] = len(self.variables)
        
        # 由于是直接解析，包信息可能需要模拟
        if not self.packages:
            self.parse_statistics['total_packages'] = 1
            # 可以根据文件名创建一个虚拟的包
            file_name = os.path.basename(arxml_file_path)
            self.packages[file_name] = {'name': file_name, 'path': file_name, 'elements': []}

        self._finalize_parsing(start_time)
        return True

    def _finalize_parsing(self, start_time: datetime):
        """完成解析的收尾工作，如计算时间和打印日志。"""
        end_time = datetime.now()
        self.parse_statistics['parse_time'] = (end_time - start_time).total_seconds()
        self.logger.info(f"ARXML解析完成，用时 {self.parse_statistics['parse_time']:.2f} 秒")
        self._log_statistics()

    def _extract_packages(self):
        """提取AR包信息"""
        try:
            # autosar44使用大写属性名
            ar_packages_attr = None
            if hasattr(self.root_element, 'AR_PACKAGES') and self.root_element.AR_PACKAGES:
                ar_packages_attr = self.root_element.AR_PACKAGES
            elif hasattr(self.root_element, 'ar_packages') and self.root_element.ar_packages:
                ar_packages_attr = self.root_element.ar_packages
            
            if ar_packages_attr:
                # 尝试获取AR_PACKAGE
                packages_list = None
                if hasattr(ar_packages_attr, 'AR_PACKAGE'):
                    packages_list = ar_packages_attr.AR_PACKAGE
                elif hasattr(ar_packages_attr, 'ar_package'):
                    packages_list = ar_packages_attr.ar_package
                
                if packages_list:
                    if not isinstance(packages_list, list):
                        packages_list = [packages_list]
                    
                    for package in packages_list:
                        self._process_package(package, [])
            
            self.parse_statistics['total_packages'] = len(self.packages)
            
        except Exception as e:
            self.logger.error(f"提取包信息失败: {e}")
            self.parse_statistics['parse_errors'] += 1
    
    def _process_package(self, package, parent_path: List[str]):
        """处理单个AR包"""
        try:
            # 使用专用方法提取SHORT_NAME，避免XML标签问题
            package_name = self._extract_short_name(package)
            if not package_name or package_name == 'unknown':
                package_name = 'unknown'
            
            current_path = parent_path + [package_name]
            package_full_path = '/'.join(current_path)
            
            self.packages[package_full_path] = {
                'name': package_name,
                'path': package_full_path,
                'parent_path': '/'.join(parent_path) if parent_path else None,
                'elements': []
            }
            
            # 递归处理子包
            ar_packages_attr = None
            if hasattr(package, 'AR_PACKAGES') and package.AR_PACKAGES:
                ar_packages_attr = package.AR_PACKAGES
            elif hasattr(package, 'ar_packages') and package.ar_packages:
                ar_packages_attr = package.ar_packages
            
            if ar_packages_attr:
                sub_packages_list = None
                if hasattr(ar_packages_attr, 'AR_PACKAGE'):
                    sub_packages_list = ar_packages_attr.AR_PACKAGE
                elif hasattr(ar_packages_attr, 'ar_package'):
                    sub_packages_list = ar_packages_attr.ar_package
                
                if sub_packages_list:
                    if not isinstance(sub_packages_list, list):
                        sub_packages_list = [sub_packages_list]
                    
                    for sub_package in sub_packages_list:
                        self._process_package(sub_package, current_path)
            
            # 处理包中的元素
            elements_attr = None
            if hasattr(package, 'ELEMENTS') and package.ELEMENTS:
                elements_attr = package.ELEMENTS
            elif hasattr(package, 'elements') and package.elements:
                elements_attr = package.elements
            
            if elements_attr:
                self._process_package_elements(elements_attr, current_path)
                
        except Exception as e:
            self.logger.error(f"处理包失败: {e}")
            self.parse_statistics['parse_errors'] += 1
    
    def _process_package_elements(self, elements, package_path: List[str]):
        """处理包中的元素"""
        try:
            package_full_path = '/'.join(package_path)
            
            # elements可能是一个包含不同类型元素的对象
            element_list = []
            if hasattr(elements, '__iter__') and not isinstance(elements, (str, dict)):
                element_list = list(elements)
            else:
                # For cases where elements is an object with various lists as attributes (e.g., silent mode in autosar44)
                for attr_name in dir(elements):
                    if not attr_name.startswith('_'):
                        attr_value = getattr(elements, attr_name)
                        # 确保我们只处理列表形式的属性值
                        if isinstance(attr_value, list):
                            element_list.extend(attr_value)
            
            for element in element_list:
                element_info = self._extract_element_info(element)
                if element_info:
                    element_info['package_path'] = package_full_path
                    self.packages[package_full_path]['elements'].append(element_info)
                    
                    # 如果是模块配置或模块定义，都单独存储并处理
                    element_type = element_info.get('type', '')
                    if ('ModuleConfiguration' in element_type or 
                        element_type == 'ECUC_MODULE_CONFIGURATION_VALUES' or
                        element_type == 'ECUC-MODULE-DEF' or
                        element_type == 'BSW-IMPLEMENTATION' or
                        element_type == 'BSW_MODULE_DESCRIPTION'):
                        element_info['raw_element'] = element
                        self.module_configurations[element_info['name']] = element_info
                        
        except Exception as e:
            self.logger.error(f"处理包元素失败: {e}")
            self.parse_statistics['parse_errors'] += 1
    
    def _extract_element_info(self, element) -> Optional[Dict[str, Any]]:
        """提取元素信息"""
        try:
            # 获取名称
            element_name = self._extract_short_name(element)
            
            # 获取类型
            element_type_name = "unknown"
            if hasattr(element, 'tag'):
                element_type_name = element.tag
            elif hasattr(element, '__class__'):
                element_type_name = element.__class__.__name__

            # 修正类型名称
            if element_type_name == 'ECUC_MODULE_CONFIGURATION_VALUES':
                element_type_name = 'ECUC_MODULE_CONFIGURATION_VALUES'
            
            # 如果没有有效名称，则跳过
            if not element_name or element_name == 'unknown':
                return None
            
            # 获取UUID
            uuid = getattr(element, 'uuid', None) or getattr(element, 'UUID', None)
            
            # 提取描述信息
            desc = None
            if hasattr(element, 'DESC') and element.DESC:
                desc = self._extract_text_content(element.DESC)
            elif hasattr(element, 'desc') and element.desc:
                desc = self._extract_text_content(element.desc)
            
            # 获取introduction
            introduction = None
            if hasattr(element, 'INTRODUCTION') and element.INTRODUCTION:
                introduction = self._extract_text_content(element.INTRODUCTION)
            elif hasattr(element, 'introduction') and element.introduction:
                introduction = self._extract_text_content(element.introduction)
            
            element_info = {
                'name': element_name,
                'uuid': uuid,
                'description': desc,
                'type': element_type_name,
                'introduction': introduction
            }
            
            return element_info
            
        except Exception as e:
            self.logger.debug(f"提取元素信息失败: {e}")
            return None
    
    def _extract_short_name(self, element) -> str:
        """提取SHORT_NAME元素的文本内容"""
        try:
            if hasattr(element, 'SHORT_NAME') and element.SHORT_NAME is not None:
                short_name = element.SHORT_NAME
                # 如果是字符串，直接返回
                if isinstance(short_name, str):
                    return short_name
                # 如果是对象，尝试提取文本内容
                elif hasattr(short_name, 'text'):
                    return str(short_name.text)
                elif hasattr(short_name, '_text'):
                    return str(short_name._text)
                else:
                    # 尝试获取对象的字符串值，并清理XML标签
                    short_name_str = str(short_name)
                    # 移除XML标签，提取实际内容
                    import re
                    match = re.search(r'<SHORT-NAME[^>]*>(.*?)</SHORT-NAME>', short_name_str, re.IGNORECASE)
                    if match:
                        return match.group(1).strip()
                    # 如果没有匹配到，尝试直接提取
                    return short_name_str.strip()
            
            elif hasattr(element, 'short_name') and element.short_name is not None:
                short_name = element.short_name
                if isinstance(short_name, str):
                    return short_name
                elif hasattr(short_name, 'text'):
                    return str(short_name.text)
                elif hasattr(short_name, '_text'):
                    return str(short_name._text)
                else:
                    return str(short_name).strip()
            
            # 如果没有SHORT_NAME，尝试其他可能的名称属性
            for attr_name in ['name', 'Name', 'NAME']:
                if hasattr(element, attr_name):
                    attr_value = getattr(element, attr_name)
                    if attr_value:
                        if isinstance(attr_value, str):
                            return attr_value.strip()
                        else:
                            return str(attr_value).strip()
            
            # 最后尝试从元素类型推断名称
            element_type = element.__class__.__name__
            if element_type != '_Element':
                return f"unnamed_{element_type}"
            
            # 对于_Element类型，返回None表示应该跳过
            return None
        except Exception as e:
            self.logger.debug(f"提取SHORT_NAME失败: {e}, 元素类型: {type(element).__name__}")
            return 'unknown'

    def _extract_parameter_value(self, param_element) -> str:
        """提取参数值"""
        try:
            if hasattr(param_element, 'VALUE') and param_element.VALUE is not None:
                value = param_element.VALUE
                # 如果是字符串，直接返回
                if isinstance(value, str):
                    return value.strip()
                # 如果是对象，尝试提取文本内容
                elif hasattr(value, 'text'):
                    return str(value.text).strip()
                elif hasattr(value, '_text'):
                    return str(value._text).strip()
                else:
                    # 尝试获取对象的字符串值，并清理XML标签
                    value_str = str(value)
                    # 移除XML标签，提取实际内容
                    import re
                    # 尝试匹配VALUE标签
                    match = re.search(r'<VALUE[^>]*>(.*?)</VALUE>', value_str, re.IGNORECASE)
                    if match:
                        content = match.group(1).strip()
                        # 进一步清理各种XML标签（包括跨行的标签）
                        content = re.sub(r'<VERBATIM_STRING[^>]*>(.*?)</VERBATIM_STRING>', r'\1', content, flags=re.IGNORECASE | re.DOTALL)
                        content = re.sub(r'<NUMERICAL_VALUE_VARIATION_POINT[^>]*>(.*?)</NUMERICAL_VALUE_VARIATION_POINT>', r'\1', content, flags=re.IGNORECASE | re.DOTALL)
                        content = re.sub(r'VERBATIM_STRING[^>]*>(.*?)<', r'\1', content, flags=re.IGNORECASE | re.DOTALL)
                        return content.strip()
                    
                    # 如果没有VALUE标签，尝试直接清理各种XML标签（包括跨行的标签）
                    content = re.sub(r'<VERBATIM_STRING[^>]*>(.*?)</VERBATIM_STRING>', r'\1', value_str, flags=re.IGNORECASE | re.DOTALL)
                    content = re.sub(r'<NUMERICAL_VALUE_VARIATION_POINT[^>]*>(.*?)</NUMERICAL_VALUE_VARIATION_POINT>', r'\1', content, flags=re.IGNORECASE | re.DOTALL)
                    content = re.sub(r'VERBATIM_STRING[^>]*>(.*?)<', r'\1', content, flags=re.IGNORECASE | re.DOTALL)
                    return content.strip()
            
            elif hasattr(param_element, 'value') and param_element.value is not None:
                value = param_element.value
                if isinstance(value, str):
                    # 清理字符串中的XML标签（包括跨行的标签）
                    import re
                    content = re.sub(r'<VERBATIM_STRING[^>]*>(.*?)</VERBATIM_STRING>', r'\1', value, flags=re.IGNORECASE | re.DOTALL)
                    content = re.sub(r'<NUMERICAL_VALUE_VARIATION_POINT[^>]*>(.*?)</NUMERICAL_VALUE_VARIATION_POINT>', r'\1', content, flags=re.IGNORECASE | re.DOTALL)
                    content = re.sub(r'VERBATIM_STRING[^>]*>(.*?)<', r'\1', content, flags=re.IGNORECASE | re.DOTALL)
                    return content.strip()
                elif hasattr(value, 'text'):
                    return str(value.text).strip()
                elif hasattr(value, '_text'):
                    return str(value._text).strip()
                else:
                    value_str = str(value)
                    # 清理XML标签（包括跨行的标签）
                    import re
                    content = re.sub(r'<VERBATIM_STRING[^>]*>(.*?)</VERBATIM_STRING>', r'\1', value_str, flags=re.IGNORECASE | re.DOTALL)
                    content = re.sub(r'<NUMERICAL_VALUE_VARIATION_POINT[^>]*>(.*?)</NUMERICAL_VALUE_VARIATION_POINT>', r'\1', content, flags=re.IGNORECASE | re.DOTALL)
                    content = re.sub(r'VERBATIM_STRING[^>]*>(.*?)<', r'\1', content, flags=re.IGNORECASE | re.DOTALL)
                    return content.strip()
            
            return ''
        except Exception as e:
            self.logger.debug(f"提取参数值失败: {e}")
            return ''

    def _extract_definition_ref(self, element) -> str:
        """提取DEFINITION_REF元素的文本内容"""
        try:
            if hasattr(element, 'DEFINITION_REF') and element.DEFINITION_REF is not None:
                def_ref = element.DEFINITION_REF
                # 如果是字符串，直接返回
                if isinstance(def_ref, str):
                    return def_ref.strip()
                # 如果是对象，尝试提取文本内容
                elif hasattr(def_ref, 'text'):
                    return str(def_ref.text).strip()
                elif hasattr(def_ref, '_text'):
                    return str(def_ref._text).strip()
                else:
                    # 尝试获取对象的字符串值，并清理XML标签
                    def_ref_str = str(def_ref)
                    # 移除XML标签，提取实际内容
                    import re
                    # 尝试匹配DEFINITION-REF标签
                    match = re.search(r'<DEFINITION-REF[^>]*>(.*?)</DEFINITION-REF>', def_ref_str, re.IGNORECASE)
                    if match:
                        return match.group(1).strip()
                    
                    # 如果没有XML标签，可能def_ref本身就包含路径，尝试提取末尾部分
                    if 'DEST=' in def_ref_str:
                        # 提取DEST属性中的值
                        dest_match = re.search(r'DEST="[^"]*">([^<]*)', def_ref_str)
                        if dest_match:
                            return dest_match.group(1).strip()
                    
                    # 如果仍然没有找到，尝试从对象的其他属性中获取
                    if hasattr(def_ref, '__dict__'):
                        for attr_name, attr_value in def_ref.__dict__.items():
                            if isinstance(attr_value, str) and '/' in attr_value:
                                return attr_value.strip()
                    
                    return def_ref_str.strip()
            
            elif hasattr(element, 'definition_ref') and element.definition_ref is not None:
                def_ref = element.definition_ref
                if isinstance(def_ref, str):
                    return def_ref.strip()
                elif hasattr(def_ref, 'text'):
                    return str(def_ref.text).strip()
                elif hasattr(def_ref, '_text'):
                    return str(def_ref._text).strip()
                else:
                    return str(def_ref).strip()
            
            return ''
        except Exception as e:
            self.logger.debug(f"提取DEFINITION_REF失败: {e}")
            return ''

    def _extract_text_content(self, text_element) -> str:
        """提取文本内容"""
        try:
            if hasattr(text_element, 'p') and text_element.p:
                if isinstance(text_element.p, list):
                    return ' '.join([str(p) for p in text_element.p])
                else:
                    return str(text_element.p)
            return str(text_element)
        except:
            return ""
    
    def _extract_module_configurations(self):
        """提取模块配置信息"""
        try:
            for config_name, config_info in self.module_configurations.items():
                self.logger.debug(f"处理模块配置: {config_name}")
                # 这里可以根据具体的ARXML结构提取更详细的配置信息
                
        except Exception as e:
            self.logger.error(f"提取模块配置失败: {e}")
            self.parse_statistics['parse_errors'] += 1
    
    def _build_container_hierarchy(self):
        """构建容器层次结构"""
        try:
            # 遍历所有模块配置，提取容器结构
            for config_name, config_info in self.module_configurations.items():
                self._extract_containers_from_config(config_info)
            
            self.parse_statistics['total_containers'] = len(self.containers)
            
        except Exception as e:
            self.logger.error(f"构建容器层次结构失败: {e}")
            self.parse_statistics['parse_errors'] += 1
    
    def _extract_containers_from_config(self, config_info: Dict[str, Any]):
        """从模块配置中提取容器信息"""
        try:
            raw_element = config_info.get('raw_element')
            if not raw_element:
                return
            
            module_name = config_info['name']
            element_type = config_info.get('type', '')
            
            self.logger.debug(f"处理模块: {module_name}, 类型: {element_type}")
            
            # 处理模块配置值 (ECUC-MODULE-CONFIGURATION-VALUES)
            if (element_type == 'ECUC_MODULE_CONFIGURATION_VALUES' or 
                'ModuleConfiguration' in element_type):
                
                # 查找CONTAINERS元素
                containers_element = None
                if hasattr(raw_element, 'CONTAINERS') and raw_element.CONTAINERS:
                    containers_element = raw_element.CONTAINERS
                elif hasattr(raw_element, 'containers') and raw_element.containers:
                    containers_element = raw_element.containers
                
                if containers_element:
                    self._extract_ecuc_containers(containers_element, module_name)
                    
            # 处理模块定义 (ECUC-MODULE-DEF)
            elif element_type == 'ECUC-MODULE-DEF':
                self.logger.debug(f"处理模块定义: {module_name}")
                
                # 为模块定义创建根容器
                if module_name not in self.containers:
                    self.containers[module_name] = {
                        'name': module_name,
                        'path': module_name,
                        'type': 'module_definition',
                        'parent_path': None,
                        'children': [],
                        'parameters': [],
                        'description': config_info.get('description', ''),
                        'multiplicity': '1'
                    }
                    self.parse_statistics['total_containers'] += 1
                
                # 查找CONTAINERS元素（定义而非值）
                containers_element = None
                if hasattr(raw_element, 'CONTAINERS') and raw_element.CONTAINERS:
                    containers_element = raw_element.CONTAINERS
                elif hasattr(raw_element, 'containers') and raw_element.containers:
                    containers_element = raw_element.containers
                
                if containers_element:
                    self._extract_container_defs(containers_element, module_name)
                    
            # 处理BSW实现
            elif element_type == 'BSW_IMPLEMENTATION' or element_type == 'BSW-IMPLEMENTATION':
                self.logger.debug(f"处理BSW实现: {module_name}")
                # BSW实现通常包含行为规范，暂时跳过
                pass
                
        except Exception as e:
            self.logger.error(f"提取容器信息失败: {e}")
            self.parse_statistics['parse_errors'] += 1

    def _extract_ecuc_containers(self, containers_element, module_name: str):
        """从ECUC模块配置中提取容器值"""
        try:
            if not containers_element:
                return

            self.logger.debug(f"开始提取ECUC容器，模块: {module_name}")
            
            # 查找所有可能的容器值标签
            container_values = []
            
            # 尝试不同的访问方式
            possible_attrs = [
                'ECUC_CONTAINER_VALUE', 'ecuc_container_value',
                'ECUC-CONTAINER-VALUE', 'EcucContainerValue'
            ]
            
            for attr_name in possible_attrs:
                if hasattr(containers_element, attr_name):
                    values = getattr(containers_element, attr_name)
                    if values:
                        if not isinstance(values, list):
                            values = [values]
                        container_values.extend(values)
                        self.logger.debug(f"通过属性 {attr_name} 找到 {len(values)} 个容器值")
                        break

            # 如果没找到，尝试遍历所有属性
            if not container_values:
                for attr_name in dir(containers_element):
                    if not attr_name.startswith('_') and 'CONTAINER' in attr_name.upper():
                        attr_value = getattr(containers_element, attr_name)
                        if attr_value and hasattr(attr_value, '__iter__') and not isinstance(attr_value, str):
                            if isinstance(attr_value, list):
                                container_values.extend(attr_value)
                            else:
                                container_values.append(attr_value)
                            self.logger.debug(f"通过遍历属性 {attr_name} 找到容器值")

            self.logger.debug(f"总共找到 {len(container_values)} 个容器值")

            # 处理每个容器值
            for i, container_value in enumerate(container_values):
                self.logger.debug(f"处理第 {i+1} 个容器值")
                self._process_container_value(container_value, module_name)

        except Exception as e:
            self.logger.error(f"提取ECUC容器失败: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            self.parse_statistics['parse_errors'] += 1

    def _process_container_value(self, container_value, parent_path: str):
        """处理单个容器值"""
        try:
            container_name = self._extract_short_name(container_value)
            if not container_name or container_name == 'unknown':
                self.logger.debug(f"跳过无名称容器值")
                return

            container_path = f"{parent_path}/{container_name}"
            self.logger.debug(f"处理容器值: {container_path}")
            
            # 提取定义引用
            definition_ref = self._extract_definition_ref(container_value)

            container_info = {
                'name': container_name,
                'path': container_path,
                'type': 'container_value',
                'parent_path': parent_path,
                'children': [],
                'parameters': [],
                'definition_ref': definition_ref,
                'description': f"Container value: {container_name}"
            }
            self.containers[container_path] = container_info
            self.parse_statistics['total_containers'] += 1

            # 更新父容器的子容器列表
            if parent_path in self.containers:
                if 'children' not in self.containers[parent_path]:
                    self.containers[parent_path]['children'] = []
                self.containers[parent_path]['children'].append(container_name)

            # 提取参数值
            params_attr = self._get_attribute(container_value, ['PARAMETER_VALUES', 'parameter_values'])
            if params_attr:
                self.logger.debug(f"开始提取容器 {container_path} 的参数值")
                self._extract_parameter_values(params_attr, container_path)

            # 提取引用值
            refs_attr = self._get_attribute(container_value, ['REFERENCE_VALUES', 'reference_values'])
            if refs_attr:
                self.logger.debug(f"开始提取容器 {container_path} 的引用值")
                self._extract_reference_values(refs_attr, container_path)

            # 递归提取子容器值
            sub_containers_attr = self._get_attribute(container_value, ['SUB_CONTAINERS', 'sub_containers'])
            if sub_containers_attr:
                self.logger.debug(f"开始提取容器 {container_path} 的子容器值")
                self._extract_ecuc_containers(sub_containers_attr, container_path)

            self.logger.debug(f"容器值 {container_path} 处理完成")

        except Exception as e:
            self.logger.error(f"处理容器值失败: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            self.parse_statistics['parse_errors'] += 1

    def _get_attribute(self, element, attr_names, default=None):
        """通用属性获取方法"""
        for attr_name in attr_names:
            if hasattr(element, attr_name):
                attr_value = getattr(element, attr_name)
                if attr_value is not None:
                    return attr_value
        return default

    def _extract_parameter_values(self, params_element, container_path: str):
        """从容器值中提取参数值"""
        try:
            if not params_element:
                return

            # 查找所有可能的参数值类型
            param_value_types = [
                'ECUC_NUMERICAL_PARAM_VALUE', 'ECUC_TEXTUAL_PARAM_VALUE',
                'ecuc_numerical_param_value', 'ecuc_textual_param_value'
            ]
            
            param_values_found = []
            
            for param_type in param_value_types:
                if hasattr(params_element, param_type):
                    param_values = getattr(params_element, param_type)
                    if param_values:
                        if not isinstance(param_values, list):
                            param_values = [param_values]
                        for param_value in param_values:
                            param_values_found.append((param_value, param_type))

            # 处理每个参数值
            for param_value, param_type in param_values_found:
                self._process_parameter(param_value, container_path, param_type)

        except Exception as e:
            self.logger.error(f"提取参数值失败: {e}")
            self.parse_statistics['parse_errors'] += 1

    def _extract_reference_values(self, refs_element, container_path: str):
        """从容器值中提取引用值"""
        try:
            if not refs_element:
                return
            
            self.logger.debug(f"开始提取引用值，容器路径: {container_path}")
            
            ref_values = []
            
            # 尝试多种可能的属性名
            possible_attrs = [
                'ECUC_REFERENCE_VALUE', 'ecuc_reference_value',
                'ECUC-REFERENCE-VALUE', 'EcucReferenceValue'
            ]
            
            # 方式1: 直接属性访问
            for attr_name in possible_attrs:
                if hasattr(refs_element, attr_name):
                    values = getattr(refs_element, attr_name)
                    if values:
                        if not isinstance(values, list):
                            values = [values]
                        ref_values.extend(values)
                        self.logger.debug(f"通过属性 {attr_name} 找到 {len(values)} 个引用值")
                        break
            
            # 方式2: 遍历所有属性查找引用值
            if not ref_values:
                for attr_name in dir(refs_element):
                    if not attr_name.startswith('_') and 'REFERENCE' in attr_name.upper() and 'VALUE' in attr_name.upper():
                        attr_value = getattr(refs_element, attr_name)
                        if attr_value:
                            if isinstance(attr_value, list):
                                ref_values.extend(attr_value)
                            else:
                                ref_values.append(attr_value)
                            self.logger.debug(f"通过遍历属性 {attr_name} 找到引用值")
            
            # 方式3: 直接迭代
            if not ref_values and hasattr(refs_element, '__iter__'):
                try:
                    for item in refs_element:
                        if hasattr(item, 'tag') and 'REFERENCE' in str(item.tag).upper() and 'VALUE' in str(item.tag).upper():
                            ref_values.append(item)
                        elif hasattr(item, '__class__') and 'REFERENCE' in str(item.__class__.__name__).upper() and 'VALUE' in str(item.__class__.__name__).upper():
                            ref_values.append(item)
                    if ref_values:
                        self.logger.debug(f"通过直接迭代找到 {len(ref_values)} 个引用值")
                except Exception as iter_error:
                    self.logger.debug(f"引用值直接迭代失败: {iter_error}")
            
            self.logger.debug(f"容器 {container_path} 总共找到 {len(ref_values)} 个引用值")
            
            # 处理每个引用值
            for i, ref_value in enumerate(ref_values):
                self.logger.debug(f"处理第 {i+1} 个引用值")
                self._process_parameter(ref_value, container_path, 'reference')

        except Exception as e:
            self.logger.error(f"提取引用值失败: {e}")
            self.parse_statistics['parse_errors'] += 1

    def _extract_container_defs(self, containers_element, parent_path: str):
        """
        改进方法: 从ECUC-MODULE-DEF中提取容器定义
        (ECUC-PARAM-CONF-CONTAINER-DEF, etc.)
        """
        try:
            if not containers_element:
                return

            self.logger.debug(f"开始提取容器定义，父路径: {parent_path}")
            
            # 查找所有可能的容器定义标签
            container_defs = []
            
            # 尝试不同的访问方式
            # 方式1: 直接属性访问
            possible_attrs = [
                'ECUC_PARAM_CONF_CONTAINER_DEF', 'ecuc_param_conf_container_def',
                'ECUC-PARAM-CONF-CONTAINER-DEF', 'EcucParamConfContainerDef'
            ]
            
            for attr_name in possible_attrs:
                if hasattr(containers_element, attr_name):
                    defs = getattr(containers_element, attr_name)
                    if defs:
                        if not isinstance(defs, list):
                            defs = [defs]
                        container_defs.extend(defs)
                        self.logger.debug(f"通过属性 {attr_name} 找到 {len(defs)} 个容器定义")
                        break

            # 方式2: 如果没找到，尝试遍历所有属性
            if not container_defs:
                for attr_name in dir(containers_element):
                    if not attr_name.startswith('_') and 'CONTAINER' in attr_name.upper():
                        attr_value = getattr(containers_element, attr_name)
                        if attr_value and hasattr(attr_value, '__iter__') and not isinstance(attr_value, str):
                            if isinstance(attr_value, list):
                                container_defs.extend(attr_value)
                            else:
                                container_defs.append(attr_value)
                            self.logger.debug(f"通过遍历属性 {attr_name} 找到容器定义")

            # 方式3: 如果仍然没找到，尝试直接迭代
            if not container_defs and hasattr(containers_element, '__iter__'):
                try:
                    for item in containers_element:
                        if hasattr(item, 'tag') and 'CONTAINER' in str(item.tag).upper():
                            container_defs.append(item)
                        elif hasattr(item, '__class__') and 'CONTAINER' in str(item.__class__.__name__).upper():
                            container_defs.append(item)
                    if container_defs:
                        self.logger.debug(f"通过直接迭代找到 {len(container_defs)} 个容器定义")
                except Exception as iter_error:
                    self.logger.debug(f"直接迭代失败: {iter_error}")

            self.logger.debug(f"总共找到 {len(container_defs)} 个容器定义")

            # 处理每个容器定义
            for i, container_def in enumerate(container_defs):
                self.logger.debug(f"处理第 {i+1} 个容器定义")
                self._process_container_def(container_def, parent_path)

        except Exception as e:
            self.logger.error(f"提取容器定义失败: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            self.parse_statistics['parse_errors'] += 1

    def _process_container_def(self, container_def, parent_path: str):
        """处理单个容器定义"""
        try:
            container_name = self._extract_short_name(container_def)
            if not container_name or container_name == 'unknown':
                self.logger.debug(f"跳过无名称容器定义")
                return

            container_path = f"{parent_path}/{container_name}"
            self.logger.debug(f"处理容器定义: {container_path}")
            
            # 提取描述
            description = ""
            desc_attr = self._get_attribute(container_def, ['DESC', 'desc'])
            if desc_attr:
                description = self._extract_text_content(desc_attr)

            # 提取出现次数
            multiplicity = self._get_attribute(container_def, ['MULTIPLICITY', 'multiplicity'], '1')

            container_info = {
                'name': container_name,
                'path': container_path,
                'type': 'container_definition',
                'parent_path': parent_path,
                'children': [],
                'parameters': [],
                'multiplicity': str(multiplicity) if multiplicity else '1',
                'description': description
            }
            self.containers[container_path] = container_info
            self.parse_statistics['total_containers'] += 1

            # 更新父容器的子容器列表
            if parent_path in self.containers:
                self.containers[parent_path]['children'].append(container_name)

            # 提取参数定义
            params_attr = self._get_attribute(container_def, ['PARAMETERS', 'parameters'])
            if params_attr:
                self.logger.debug(f"开始提取容器 {container_path} 的参数定义")
                self._extract_parameter_defs(params_attr, container_path)

            # 提取引用定义
            refs_attr = self._get_attribute(container_def, ['REFERENCES', 'references'])
            if refs_attr:
                self.logger.debug(f"开始提取容器 {container_path} 的引用定义")
                self._extract_reference_defs(refs_attr, container_path)

            # 递归提取子容器定义
            sub_containers_attr = self._get_attribute(container_def, ['SUB_CONTAINERS', 'sub_containers', 'SUB-CONTAINERS'])
            if sub_containers_attr:
                self.logger.debug(f"开始提取容器 {container_path} 的子容器定义")
                self._extract_container_defs(sub_containers_attr, container_path)

            self.logger.debug(f"容器定义 {container_path} 处理完成，参数数: {len(container_info['parameters'])}")

        except Exception as e:
            self.logger.error(f"处理容器定义失败: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            self.parse_statistics['parse_errors'] += 1

    def _extract_reference_defs(self, refs_element, container_path: str):
        """从容器定义中提取引用定义(ECUC-REFERENCE-DEF)"""
        try:
            if not refs_element:
                return
            
            self.logger.debug(f"开始提取引用定义，容器路径: {container_path}")
            
            ref_defs = []
            
            # 尝试多种可能的属性名
            possible_attrs = [
                'ECUC_REFERENCE_DEF', 'ecuc_reference_def',
                'ECUC-REFERENCE-DEF', 'EcucReferenceDef'
            ]
            
            # 方式1: 直接属性访问
            for attr_name in possible_attrs:
                if hasattr(refs_element, attr_name):
                    defs = getattr(refs_element, attr_name)
                    if defs:
                        if not isinstance(defs, list):
                            defs = [defs]
                        ref_defs.extend(defs)
                        self.logger.debug(f"通过属性 {attr_name} 找到 {len(defs)} 个引用定义")
                        break
            
            # 方式2: 遍历所有属性查找引用定义
            if not ref_defs:
                for attr_name in dir(refs_element):
                    if not attr_name.startswith('_') and 'REFERENCE' in attr_name.upper():
                        attr_value = getattr(refs_element, attr_name)
                        if attr_value:
                            if isinstance(attr_value, list):
                                ref_defs.extend(attr_value)
                            else:
                                ref_defs.append(attr_value)
                            self.logger.debug(f"通过遍历属性 {attr_name} 找到引用定义")
            
            # 方式3: 直接迭代
            if not ref_defs and hasattr(refs_element, '__iter__'):
                try:
                    for item in refs_element:
                        if hasattr(item, 'tag') and 'REFERENCE' in str(item.tag).upper():
                            ref_defs.append(item)
                        elif hasattr(item, '__class__') and 'REFERENCE' in str(item.__class__.__name__).upper():
                            ref_defs.append(item)
                    if ref_defs:
                        self.logger.debug(f"通过直接迭代找到 {len(ref_defs)} 个引用定义")
                except Exception as iter_error:
                    self.logger.debug(f"引用定义直接迭代失败: {iter_error}")
            
            self.logger.debug(f"容器 {container_path} 总共找到 {len(ref_defs)} 个引用定义")
            
            # 处理每个引用定义
            for i, ref_def in enumerate(ref_defs):
                self.logger.debug(f"处理第 {i+1} 个引用定义")
                self._process_parameter_def(ref_def, container_path)

        except Exception as e:
            self.logger.error(f"提取引用定义失败: {e}", exc_info=self.verbose)
            self.parse_statistics['parse_errors'] += 1

    def _extract_parameter_defs(self, params_element, container_path: str):
        """
        改进方法: 从容器定义中提取参数定义
        (ECUC-INTEGER-PARAM-DEF, ECUC-BOOLEAN-PARAM-DEF, etc.)
        """
        try:
            if not params_element:
                return

            self.logger.debug(f"开始提取参数定义，容器路径: {container_path}")

            # 定义所有可能的参数定义类型
            param_def_types = [
                'ECUC_INTEGER_PARAM_DEF', 'ECUC_BOOLEAN_PARAM_DEF',
                'ECUC_FLOAT_PARAM_DEF', 'ECUC_ENUMERATION_PARAM_DEF',
                'ECUC_TEXTUAL_PARAM_DEF', 'ECUC_FUNCTION_NAME_DEF',
                'ECUC-INTEGER-PARAM-DEF', 'ECUC-BOOLEAN-PARAM-DEF',
                'ECUC-FLOAT-PARAM-DEF', 'ECUC-ENUMERATION-PARAM-DEF',
                'ECUC-TEXTUAL-PARAM-DEF', 'ECUC-FUNCTION-NAME-DEF'
            ]
            
            param_defs_found = []
            
            # 方式1: 直接通过属性名查找
            for param_type in param_def_types:
                if hasattr(params_element, param_type):
                    param_defs = getattr(params_element, param_type)
                    if param_defs:
                        if not isinstance(param_defs, list):
                            param_defs = [param_defs]
                        param_defs_found.extend(param_defs)
                        self.logger.debug(f"通过属性 {param_type} 找到 {len(param_defs)} 个参数定义")

            # 方式2: 遍历所有属性查找参数定义
            if not param_defs_found:
                for attr_name in dir(params_element):
                    if not attr_name.startswith('_'):
                        attr_upper = attr_name.upper()
                        if ('PARAM' in attr_upper and 'DEF' in attr_upper) or 'FUNCTION' in attr_upper:
                            attr_value = getattr(params_element, attr_name)
                            if attr_value:
                                if isinstance(attr_value, list):
                                    param_defs_found.extend(attr_value)
                                else:
                                    param_defs_found.append(attr_value)
                                self.logger.debug(f"通过遍历属性 {attr_name} 找到参数定义")

            # 方式3: 如果仍然没找到，尝试直接迭代
            if not param_defs_found and hasattr(params_element, '__iter__'):
                try:
                    for item in params_element:
                        if hasattr(item, 'tag') and 'PARAM' in str(item.tag).upper():
                            param_defs_found.append(item)
                        elif hasattr(item, '__class__') and 'PARAM' in str(item.__class__.__name__).upper():
                            param_defs_found.append(item)
                    if param_defs_found:
                        self.logger.debug(f"通过直接迭代找到 {len(param_defs_found)} 个参数定义")
                except Exception as iter_error:
                    self.logger.debug(f"参数定义直接迭代失败: {iter_error}")

            self.logger.debug(f"容器 {container_path} 总共找到 {len(param_defs_found)} 个参数定义")

            # 处理每个参数定义
            for i, param_def in enumerate(param_defs_found):
                self.logger.debug(f"处理第 {i+1} 个参数定义")
                self._process_parameter_def(param_def, container_path)
        
        except Exception as e:
            self.logger.error(f"提取参数定义失败: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            self.parse_statistics['parse_errors'] += 1

    def _process_parameter(self, param_element, container_path: str, param_type: str):
        """处理单个参数"""
        try:
            # 使用专门的方法提取参数名称
            param_name = self._extract_short_name(param_element)
            
            # 如果没有找到SHORT_NAME，尝试从DEFINITION_REF提取参数名
            if param_name is None or param_name == 'unknown' or param_name.startswith('unnamed_'):
                definition_ref = self._extract_definition_ref(param_element)
                if definition_ref:
                    # 从定义路径中提取参数名称 (最后一个路径段)
                    param_name = definition_ref.split('/')[-1]
                    self.logger.debug(f"从DEFINITION_REF提取参数名: {param_name}")
                    
            # 如果仍然没有有效名称，跳过这个参数
            if param_name is None or param_name == 'unknown':
                self.logger.debug(f"跳过无效参数: {type(param_element).__name__}")
                return
            
            # 提取参数值
            param_value = self._extract_parameter_value(param_element)
            if param_value is None:
                param_value = ""
            
            # 提取定义路径
            definition_path = self._extract_definition_ref(param_element)
            
            param_full_path = f"{container_path}/{param_name}"
            
            # 根据定义路径推断参数类型
            param_data_type = self._infer_parameter_type(definition_path, param_type, param_value)
            
            param_info = {
                'name': param_name,
                'path': param_full_path,
                'container_path': container_path,
                'type': param_data_type,
                'default': param_value,
                'current_value': param_value,
                'description': f'{param_type.title()} parameter',
                'source': 'arxml',
                'definition_path': definition_path
            }
            
            self.variables[param_full_path] = param_info
            
            # 添加到容器的参数列表
            if container_path in self.containers:
                # 确保容器有parameters列表
                if 'parameters' not in self.containers[container_path]:
                    self.containers[container_path]['parameters'] = []
                # 添加完整的参数信息而不是仅仅参数名
                self.containers[container_path]['parameters'].append(param_info)
                
            self.parse_statistics['total_parameters'] += 1
                
        except Exception as e:
            self.logger.error(f"处理参数失败: {e}")
            self.parse_statistics['parse_errors'] += 1

    def _infer_parameter_type(self, definition_path: str, param_type: str, value: str) -> str:
        """根据定义路径和值推断参数类型"""
        # 从定义路径推断类型
        if 'INTEGER' in definition_path.upper() or 'Int' in definition_path:
            return 'INTEGER'
        elif 'FLOAT' in definition_path.upper() or 'Float' in definition_path:
            return 'FLOAT'
        elif 'BOOLEAN' in definition_path.upper() or 'Bool' in definition_path:
            return 'BOOLEAN'
        elif 'ENUMERATION' in definition_path.upper() or 'Enum' in definition_path:
            return 'ENUMERATION'
        elif 'STRING' in definition_path.upper() or 'String' in definition_path:
            return 'STRING'
        
        # 根据值推断类型
        if param_type == 'numerical':
            if '.' in value:
                return 'FLOAT'
            else:
                return 'INTEGER'
        elif param_type == 'textual':
            if value.lower() in ['true', 'false']:
                return 'BOOLEAN'
            else:
                return 'STRING'
        
        return 'STRING'  # 默认类型
    
    def _process_parameter_def(self, param_def, container_path: str):
        """处理参数定义（包括引用定义）"""
        try:
            # 获取参数名称
            param_name = self._extract_short_name(param_def)
            if not param_name or param_name == 'unknown':
                self.logger.debug(f"跳过无名称参数定义")
                return
            
            # 获取参数定义的类型
            param_def_type = self._get_parameter_def_type(param_def)
            
            # 提取描述
            description = ""
            if hasattr(param_def, 'DESC') and param_def.DESC:
                description = self._extract_text_content(param_def.DESC)
            elif hasattr(param_def, 'desc') and param_def.desc:
                description = self._extract_text_content(param_def.desc)
            
            # 提取默认值
            default_value = ""
            if hasattr(param_def, 'DEFAULT_VALUE') and param_def.DEFAULT_VALUE:
                default_value = self._extract_text_content(param_def.DEFAULT_VALUE)
            elif hasattr(param_def, 'default_value') and param_def.default_value:
                default_value = self._extract_text_content(param_def.default_value)
            
            # 对于引用类型，提取引用目标
            reference_target = ""
            if param_def_type == 'REFERENCE':
                if hasattr(param_def, 'DESTINATION_REF') and param_def.DESTINATION_REF:
                    reference_target = self._extract_text_content(param_def.DESTINATION_REF)
                elif hasattr(param_def, 'destination_ref') and param_def.destination_ref:
                    reference_target = self._extract_text_content(param_def.destination_ref)
                elif hasattr(param_def, 'DESTINATION_TYPE') and param_def.DESTINATION_TYPE:
                    reference_target = self._extract_text_content(param_def.DESTINATION_TYPE)
            
            param_full_path = f"{container_path}/{param_name}"
            
            # 创建参数信息
            param_info = {
                'name': param_name,
                'path': param_full_path,
                'container_path': container_path,
                'type': param_def_type,
                'default': default_value,
                'current_value': default_value,
                'description': description or f'{param_def_type} parameter definition',
                'source': 'arxml',
                'definition_path': param_full_path,
                'is_definition': True  # 标记这是参数定义
            }
            
            # 如果是引用类型，添加引用目标信息
            if param_def_type == 'REFERENCE' and reference_target:
                param_info['reference_target'] = reference_target
                param_info['description'] = f"Reference to {reference_target}"
            
            # 存储参数信息
            self.variables[param_full_path] = param_info
            
            # 添加到容器的参数列表
            if container_path in self.containers:
                if 'parameters' not in self.containers[container_path]:
                    self.containers[container_path]['parameters'] = []
                self.containers[container_path]['parameters'].append(param_info)
            
            self.parse_statistics['total_parameters'] += 1
            self.logger.debug(f"处理参数定义: {param_name} ({param_def_type})")
            
        except Exception as e:
            self.logger.error(f"处理参数定义失败: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
            self.parse_statistics['parse_errors'] += 1
    
    def _get_parameter_def_type(self, param_def) -> str:
        """获取参数定义的类型"""
        try:
            # 从类名或标签名推断类型
            if hasattr(param_def, 'tag'):
                tag_name = param_def.tag
            elif hasattr(param_def, '__class__'):
                tag_name = param_def.__class__.__name__
            else:
                tag_name = str(type(param_def))
            
            tag_upper = tag_name.upper()
            
            if 'REFERENCE' in tag_upper:
                return 'REFERENCE'
            elif 'INTEGER' in tag_upper:
                return 'INTEGER'
            elif 'FLOAT' in tag_upper:
                return 'FLOAT'
            elif 'BOOLEAN' in tag_upper:
                return 'BOOLEAN'
            elif 'ENUMERATION' in tag_upper:
                return 'ENUMERATION'
            elif 'STRING' in tag_upper or 'TEXTUAL' in tag_upper:
                return 'STRING'
            elif 'FUNCTION' in tag_upper:
                return 'FUNCTION'
            else:
                return 'UNKNOWN'
                
        except Exception as e:
            self.logger.debug(f"获取参数定义类型失败: {e}")
            return 'UNKNOWN'
    
    def _extract_parameters(self):
        """提取参数信息"""
        try:
            # 遍历容器，提取参数
            for container_path, container_info in self.containers.items():
                self._extract_parameters_from_container(container_info)
            
            self.parse_statistics['total_parameters'] = len(self.variables)
            
        except Exception as e:
            self.logger.error(f"提取参数失败: {e}")
            self.parse_statistics['parse_errors'] += 1
    
    def _extract_parameters_from_container(self, container_info: Dict[str, Any]):
        """从容器中提取参数"""
        try:
            # 参数已经在容器提取过程中处理了，这里不需要额外处理
            # 这个方法保留是为了与现有架构兼容
            pass
            
        except Exception as e:
            self.logger.error(f"从容器提取参数失败: {e}")
            self.parse_statistics['parse_errors'] += 1
    
    def _log_statistics(self):
        """记录统计信息"""
        stats = self.parse_statistics
        self.logger.info("=== ARXML解析统计 ===")
        self.logger.info(f"总包数: {stats['total_packages']}")
        self.logger.info(f"总容器数: {stats['total_containers']}")
        self.logger.info(f"总参数数: {stats['total_parameters']}")
        self.logger.info(f"解析错误数: {stats['parse_errors']}")
        self.logger.info(f"解析时间: {stats['parse_time']:.2f} 秒")
    
    def get_compatible_data(self) -> Dict[str, Any]:
        """获取与XDM处理器兼容的数据结构
        
        Returns:
            Dict: 兼容的数据结构
        """
        try:
            compatible_data = {
                'variables': self.variables,
                'containers': self.containers,
                'packages': self.packages,
                'module_configurations': self.module_configurations,
                'statistics': self.parse_statistics,
                'source_type': 'arxml'
            }
            
            # 构建扁平化的容器映射（与XDM处理器兼容）
            all_containers = {}
            for container_path, container_info in self.containers.items():
                all_containers[container_path] = {
                    'name': container_info['name'],
                    'definition': {
                        'path': container_path,
                        'multiplicity': container_info.get('multiplicity', '1'),
                        'description': container_info.get('description', ''),
                        'type': container_info.get('type', 'container')
                    },
                    'variables': {},
                    'instances': [{}],  # 默认创建一个实例
                    'current_instance': 0
                }
                
                # 添加变量到容器
                for var_path, var_info in self.variables.items():
                    if var_info['container_path'] == container_path:
                        var_name = var_info['name']
                        all_containers[container_path]['variables'][var_name] = {
                            'definition': {
                                'type': var_info['type'],
                                'default': var_info['default'],
                                'description': var_info['description']
                            },
                            'values': [var_info['current_value']]
                        }
            
            compatible_data['all_containers'] = all_containers
            
            return compatible_data
            
        except Exception as e:
            self.logger.error(f"生成兼容数据失败: {e}")
            return {}
    
    def get_tree_structure(self) -> Dict[str, Any]:
        """获取树形结构数据"""
        try:
            tree_data = {
                'packages': self.packages,
                'containers': self.containers,
                'variables': self.variables,
                'statistics': self.parse_statistics
            }
            
            return tree_data
            
        except Exception as e:
            self.logger.error(f"生成树形结构失败: {e}")
            return {}


def main():
    """测试函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ARXML处理器测试')
    parser.add_argument('arxml_file', help='ARXML文件路径')
    parser.add_argument('--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 创建处理器并解析文件
    processor = ARXMLProcessor(verbose=args.verbose)
    
    if processor.parse_arxml_file(args.arxml_file):
        print("ARXML文件解析成功!")
        
        # 获取兼容数据
        compatible_data = processor.get_compatible_data()
        print(f"提取到 {len(compatible_data.get('variables', {}))} 个变量")
        print(f"提取到 {len(compatible_data.get('containers', {}))} 个容器")
        
    else:
        print("ARXML文件解析失败!")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 