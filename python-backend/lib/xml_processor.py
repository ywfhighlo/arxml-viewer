#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用XML处理器
使用 xml.etree.ElementTree 直接解析XML文件，
专注于从复杂的、类似ARXML的结构中提取容器和参数定义。
"""

import xml.etree.ElementTree as ET
import logging
import sys
from typing import Dict, List, Any, Optional
import os

class XMLProcessor:
    """
    一个通用的XML解析器，用于从文件中提取层次化数据。
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.logger = self._setup_logging()
        self.namespaces = {}
        self.tree = None
        self.packages = {}

    def _setup_logging(self) -> logging.Logger:
        """设置日志系统"""
        logger = logging.getLogger('XMLProcessor')
        if not logger.handlers:
            level = logging.DEBUG if self.verbose else logging.INFO
            handler = logging.StreamHandler(sys.stderr)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(level)
        return logger

    def _register_namespaces(self, file_path: str):
        """从XML文件中提取所有命名空间。"""
        self.namespaces = dict([
            node for _, node in ET.iterparse(file_path, events=['start-ns'])
        ])
        # iterparse可能不总是能找到默认命名空间，手动添加
        if '' not in self.namespaces:
            # 尝试从根元素获取
            try:
                root = ET.parse(file_path).getroot()
                if root.tag.startswith('{'):
                    uri = root.tag.split('}')[0][1:]
                    if uri:
                        self.namespaces[''] = uri
            except Exception as e:
                self.logger.debug(f"无法从根元素提取默认命名空间: {e}")
        self.logger.debug(f"注册的命名空间: {self.namespaces}")

    def parse(self, file_path: str) -> Optional[ET.Element]:
        """
        解析XML文件并返回根元素。

        Args:
            file_path (str): XML文件的路径。

        Returns:
            Optional[ET.Element]: 解析成功则返回根元素，否则返回None。
        """
        self.logger.info(f"开始使用ElementTree解析XML文件: {file_path}")
        self.file_path = file_path # Store file_path
        try:
            self._register_namespaces(file_path)
            self.tree = ET.parse(file_path)
            root = self.tree.getroot()
            self.logger.info("XML文件解析成功。")
            return root
        except ET.ParseError as e:
            self.logger.error(f"XML解析错误: {e}")
            return None
        except Exception as e:
            self.logger.error(f"处理XML文件失败: {e}", exc_info=self.verbose)
            return None

    def find_elements(self, tag_name: str, parent_element: Optional[ET.Element] = None) -> List[ET.Element]:
        """
        在整个树或指定父元素下查找所有匹配的元素。
        正确处理命名空间。
        """
        if parent_element is None:
            parent_element = self.tree.getroot()
        
        # 构建正确的查询路径，处理默认命名空间
        # ElementTree的find/findall需要 {uri}tagname 格式
        parts = tag_name.split(':')
        ns_prefix = parts[0] if len(parts) > 1 else ''
        local_name = parts[-1]

        if ns_prefix in self.namespaces:
            query = f".//{{{self.namespaces[ns_prefix]}}}{local_name}"
        elif '' in self.namespaces:
            # 默认命名空间
            query = f".//{{{self.namespaces['']}}}{local_name}"
        else:
            # 无命名空间
            query = f".//{local_name}"
        
        try:
            return parent_element.findall(query)
        except Exception as e:
            self.logger.error(f"查找元素 '{tag_name}' (查询: '{query}') 失败: {e}", exc_info=self.verbose)
            return []

    def get_element_text(self, element: ET.Element) -> str:
        """安全地获取元素的文本内容，处理None的情况。"""
        return element.text.strip() if element is not None and element.text else ""

    def get_child_element_text(self, parent: ET.Element, child_tag: str) -> str:
        """获取子元素的文本内容，正确处理命名空间。"""
        parts = child_tag.split(':')
        ns_prefix = parts[0] if len(parts) > 1 else ''
        local_name = parts[-1]

        if ns_prefix in self.namespaces:
            query = f"{{{self.namespaces[ns_prefix]}}}{local_name}"
        elif '' in self.namespaces:
            query = f"{{{self.namespaces['']}}}{local_name}"
        else:
            query = local_name
            
        child = parent.find(query)
        return self.get_element_text(child)

    def _add_ns(self, tag: str) -> str:
        """如果标签没有前缀，则添加默认命名空间前缀。"""
        if ':' not in tag and '' in self.namespaces:
             return f"{self.namespaces['']}:{tag}"
        return tag

    def extract_structure(self, root: ET.Element) -> Dict[str, Any]:
        """
        从根元素开始提取结构化的容器和参数信息。
        这是为BSWMD这类定义文件设计的核心方法。
        """
        containers = {}
        parameters = {}
        
        # 查找所有模块定义
        # AR-PACKAGE -> ELEMENTS -> ECUC-MODULE-DEF
        ar_packages = self.find_elements('AR-PACKAGE', root)
        if not ar_packages:
            ar_packages = self.find_elements('AR-PACKAGES', root) # Fallback

        for pkg in ar_packages:
            elements = self.find_elements('ELEMENTS', pkg)
            for el_container in elements:
                module_defs = self.find_elements('ECUC-MODULE-DEF', el_container)
                self.logger.debug(f"找到 {len(module_defs)} 个 ECUC-MODULE-DEF 元素。")

                for mod_def in module_defs:
                    module_name = self.get_child_element_text(mod_def, 'SHORT-NAME')
                    if not module_name:
                        continue

                    self.logger.info(f"正在处理模块定义: {module_name}")
                    containers[module_name] = {
                        'name': module_name,
                        'path': module_name,
                        'type': 'module_definition',
                        'parent_path': None,
                        'children': [],
                        'parameters': {}
                    }
                    
                    # 查找顶层容器
                    containers_element = self.find_elements('CONTAINERS', mod_def)
                    if containers_element:
                        self._recursive_extract(containers_element[0], module_name, containers, parameters)

                    # Create a fake package based on the file name to hold the module definition
                    pkg_name = os.path.basename(self.file_path)
                    if pkg_name not in self.packages:
                        self.packages[pkg_name] = {'name': pkg_name, 'elements': []}

                    # Add the module definition itself as a top-level element in the package
                    module_element = {
                        'name': module_name,
                        'type': 'MODULE-DEFINITION'
                    }
                    self.packages[pkg_name]['elements'].append(module_element)

        return {'containers': containers, 'parameters': parameters}

    def _recursive_extract(self, element: ET.Element, parent_path: str, containers: Dict, parameters: Dict):
        """递归提取容器和参数定义。"""
        
        # 查找此级别下的所有容器定义
        container_defs = self.find_elements('ECUC-PARAM-CONF-CONTAINER-DEF', element)
        self.logger.debug(f"在路径 {parent_path} 下找到 {len(container_defs)} 个容器定义。")

        for container_def in container_defs:
            container_name = self.get_child_element_text(container_def, 'SHORT-NAME')
            description = self.get_child_element_text(container_def, 'DESC')
            if not container_name:
                continue

            container_path = f"{parent_path}/{container_name}"
            self.logger.debug(f"处理容器: {container_path}")

            containers[container_path] = {
                'name': container_name,
                'path': container_path,
                'type': 'container_definition',
                'description': description,
                'parent_path': parent_path,
                'children': [],
                'parameters': {}
            }
            if parent_path in containers:
                containers[parent_path]['children'].append(container_name)

            # 提取此容器的参数定义
            params_elements = self.find_elements('PARAMETERS', container_def)
            if params_elements:
                self._extract_parameter_defs(params_elements[0], container_path, containers, parameters)
            
            # 递归处理子容器
            sub_containers_elements = self.find_elements('SUB-CONTAINERS', container_def)
            if sub_containers_elements:
                self._recursive_extract(sub_containers_elements[0], container_path, containers, parameters)

    def _extract_parameter_defs(self, params_element: ET.Element, container_path: str, containers: Dict, parameters: Dict):
        """从PARAMETERS元素中提取所有类型的参数定义。"""
        
        # 遍历所有子元素，因为参数定义的标签名不同
        for param_def in params_element:
            param_tag = param_def.tag.split('}')[-1] if '}' in param_def.tag else param_def.tag
            
            if 'PARAM-DEF' in param_tag or 'REFERENCE-DEF' in param_tag:
                param_name = self.get_child_element_text(param_def, 'SHORT-NAME')
                if not param_name:
                    continue
                
                param_path = f"{container_path}/{param_name}"
                param_type = self._get_param_type_from_tag(param_tag)
                default_value = self.get_child_element_text(param_def, 'DEFAULT-VALUE')
                
                param_info = {
                    'name': param_name,
                    'path': param_path,
                    'container_path': container_path,
                    'type': param_type,
                    'default': default_value,
                    'description': self.get_child_element_text(param_def, 'DESC'),
                    'source': 'xml_def'
                }
                
                parameters[param_path] = param_info
                # 链接到所属容器
                if container_path in containers:
                    containers[container_path]['parameters'][param_name] = param_info
    
    def _get_param_type_from_tag(self, tag: str) -> str:
        """从标签名推断参数类型。"""
        tag_upper = tag.upper()
        if 'INTEGER' in tag_upper: return 'INTEGER'
        if 'BOOLEAN' in tag_upper: return 'BOOLEAN'
        if 'FLOAT' in tag_upper: return 'FLOAT'
        if 'ENUMERATION' in tag_upper: return 'ENUMERATION'
        if 'FUNCTION-NAME' in tag_upper: return 'FUNCTION_NAME'
        if 'REFERENCE' in tag_upper: return 'REFERENCE'
        if 'TEXTUAL' in tag_upper: return 'STRING'
        return 'STRING' # 默认 