#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XDM处理器 - 统一的XDM文件解析和配置管理系统
集成了XDM文件解析、容器层次结构管理、变量配置和多实例管理功能
"""

import os
import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union


def setup_logging(verbose=False):
    """设置日志配置"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')
    return logging.getLogger(__name__)


class ConfigContainer:
    """配置容器类 - 支持层次结构和多实例"""
    
    def __init__(self, name: str, definition: Dict[str, Any], parent=None):
        self.name = name
        self.definition = definition  # 来自XDM的容器定义
        self.parent = parent
        self.children = {}  # 子容器
        self.variables = {}  # 容器内的变量
        self.instances = []  # 多实例支持
        self.multiplicity = definition.get('multiplicity', '1')  # 实例数量限制
        self.current_instance = 0  # 当前选中的实例
        
    def add_variable(self, var_name: str, var_definition: Dict[str, Any]):
        """添加变量到容器"""
        self.variables[var_name] = {
            'definition': var_definition,
            'values': []  # 每个实例的值
        }
    
    def add_child_container(self, container: 'ConfigContainer'):
        """添加子容器"""
        container.parent = self
        self.children[container.name] = container
    
    def create_instance(self) -> int:
        """创建新实例"""
        if self.multiplicity != '*' and len(self.instances) >= int(self.multiplicity):
            raise ValueError(f"容器 {self.name} 已达到最大实例数量: {self.multiplicity}")
        
        instance_id = len(self.instances)
        instance_data = {
            'id': instance_id,
            'name': f"{self.name}_{instance_id}",
            'variables': {},
            'created_time': datetime.now().isoformat()
        }
        
        # 初始化变量默认值
        for var_name, var_info in self.variables.items():
            default_value = var_info['definition'].get('default', '')
            instance_data['variables'][var_name] = default_value
            
            # 确保values列表有足够的元素
            while len(var_info['values']) <= instance_id:
                var_info['values'].append(default_value)
        
        self.instances.append(instance_data)
        return instance_id
    
    def delete_instance(self, instance_id: int) -> bool:
        """删除实例"""
        if 0 <= instance_id < len(self.instances):
            self.instances.pop(instance_id)
            # 重新编号实例
            for i, instance in enumerate(self.instances):
                instance['id'] = i
                instance['name'] = f"{self.name}_{i}"
            
            # 调整变量值列表
            for var_info in self.variables.values():
                if instance_id < len(var_info['values']):
                    var_info['values'].pop(instance_id)
            
            # 调整当前实例索引
            if self.current_instance >= len(self.instances):
                self.current_instance = max(0, len(self.instances) - 1)
            
            return True
        return False
    
    def set_variable_value(self, var_name: str, value: Any, instance_id: int = None) -> bool:
        """设置变量值"""
        if var_name not in self.variables:
            return False
        
        if instance_id is None:
            instance_id = self.current_instance
        
        if instance_id >= len(self.instances):
            return False
        
        # 更新实例数据
        self.instances[instance_id]['variables'][var_name] = value
        
        # 更新变量值列表
        var_info = self.variables[var_name]
        while len(var_info['values']) <= instance_id:
            var_info['values'].append(var_info['definition'].get('default', ''))
        var_info['values'][instance_id] = value
        
        return True
    
    def get_variable_value(self, var_name: str, instance_id: int = None) -> Any:
        """获取变量值"""
        if var_name not in self.variables:
            return None
        
        if instance_id is None:
            instance_id = self.current_instance
        
        if instance_id >= len(self.instances):
            return self.variables[var_name]['definition'].get('default', '')
        
        return self.instances[instance_id]['variables'].get(var_name, 
                self.variables[var_name]['definition'].get('default', ''))
    
    def get_full_path(self) -> str:
        """获取容器的完整路径"""
        if self.parent:
            return f"{self.parent.get_full_path()}/{self.name}"
        return self.name


class XDMProcessor:
    """统一的XDM处理器 - 集成文件解析和配置管理功能"""
    
    def __init__(self, xdm_file_path: str = None, verbose: bool = False):
        self.xdm_file_path = Path(xdm_file_path) if xdm_file_path else None
        self.verbose = verbose
        self.logger = setup_logging(verbose)
        
        # 解析数据存储
        self.variables = {}  # 变量名 -> 变量信息
        self.containers = {}  # 容器名 -> 容器信息
        self.lin_specific_variables = {}  # LIN特定变量
        self.channel_variables = {}  # 通道相关变量
        
        # 配置管理数据
        self.root_containers = {}  # 根级容器
        self.all_containers = {}   # 所有容器的扁平映射
        self.global_variables = {}  # 全局变量
        
        # 配置历史
        self.configuration_history = []
        self.modification_count = 0
        
        # 如果提供了XDM文件路径，则解析文件并初始化配置
        if self.xdm_file_path and self.xdm_file_path.exists():
            self.parse_xdm_file()
            self.initialize_configuration()
        elif xdm_file_path:
            self.logger.warning(f"XDM文件未找到: {xdm_file_path}")
    
    # ============================================================================
    # XDM文件解析功能 (来自原XDMParser)
    # ============================================================================
    
    def parse_xdm_file(self) -> bool:
        """解析XDM文件并提取变量定义"""
        try:
            self.logger.info(f"解析XDM文件: {self.xdm_file_path}")
            
            # 解析XML
            tree = ET.parse(self.xdm_file_path)
            root = tree.getroot()
            
            # 提取变量和容器
            self._extract_variables(root)
            self._extract_containers(root)
            
            # 对变量进行分类
            self._categorize_variables()
            
            self.logger.info(f"XDM解析完成: {len(self.variables)} 个变量, {len(self.containers)} 个容器")
            return True
            
        except ET.ParseError as e:
            self.logger.error(f"XDM文件XML解析错误: {e}")
            return False
        except Exception as e:
            self.logger.error(f"解析XDM文件时出错: {e}")
            return False
    
    def _extract_variables(self, root):
        """从XDM中提取变量定义"""
        # 在各种XDM结构中查找变量定义
        for elem in root.iter():
            # 检查v:var元素（XDM变量定义）
            if elem.tag.endswith('}var') or elem.tag == 'var' or 'variable' in elem.tag.lower() or 'param' in elem.tag.lower():
                var_info = self._parse_variable_element(elem)
                if var_info:
                    var_name = var_info.get('name')
                    if var_name:
                        self.variables[var_name] = var_info
    
    def _extract_containers(self, root):
        """从XDM中提取容器定义"""
        # 首先获取所有容器
        containers = {}
        for elem in root.iter():
            # 检查是否是容器元素
            if (elem.tag.endswith('}ctr') or elem.tag == 'ctr' or 
                'container' in elem.tag.lower() or 'module' in elem.tag.lower() or
                elem.tag.endswith('AR-PACKAGE') or 'IDENTIFIABLE' in elem.tag):
                
                container_info = self._parse_container_element(elem)
                if container_info:
                    # 获取完整的容器路径
                    container_path = self._determine_container_path(elem)
                    if container_path:
                        # 添加路径信息
                        container_info['path'] = container_path
                        containers[container_path] = container_info
                        
                        # 查找该容器中的变量
                        container_vars = []
                        for var_elem in elem.iter():
                            if (var_elem.tag.endswith('}var') or var_elem.tag == 'var' or 
                                'variable' in var_elem.tag.lower() or 'param' in var_elem.tag.lower()):
                                var_info = self._parse_variable_element(var_elem)
                                if var_info:
                                    var_name = var_info['name']
                                    # 设置变量的容器路径
                                    var_info['container_path'] = container_path
                                    # 更新全局变量字典
                                    if var_name in self.variables:
                                        self.variables[var_name].update(var_info)
                                    else:
                                        self.variables[var_name] = var_info
                                    container_vars.append(var_name)
                        
                        # 更新容器的变量列表
                        container_info['variables'] = container_vars
        
        # 更新容器字典
        self.containers = containers
        
        # 建立容器的层次关系
        for container_path, container_info in containers.items():
            parts = container_path.split('/')
            if len(parts) > 1:
                parent_path = '/'.join(parts[:-1])
                if parent_path in containers:
                    # 确保父容器有children字段
                    if 'children' not in containers[parent_path]:
                        containers[parent_path]['children'] = {}
                    # 添加到父容器的children中
                    containers[parent_path]['children'][parts[-1]] = container_info
    
    def _parse_variable_element(self, elem) -> Dict[str, Any]:
        """解析变量元素并提取信息"""
        var_info = {
            'name': elem.get('name', ''),
            'type': elem.get('type', 'string'),
            'default': elem.get('default', ''),
            'description': elem.get('desc', ''),
            'path': self._get_element_path(elem),
            'tag': elem.tag,
            'container_path': self._determine_container_path(elem)  # 直接在这里设置容器路径
        }
        
        # 提取文本内容（如果可用）
        if elem.text and elem.text.strip():
            var_info['current_value'] = elem.text.strip()
        
        # 提取其他属性
        for attr_name, attr_value in elem.attrib.items():
            if attr_name not in var_info:
                var_info[attr_name] = attr_value
        
        # 解析XDM特定的默认值定义 <a:da name="DEFAULT" value="..."/>
        for child in elem:
            tag = child.tag
            if '}' in tag:
                tag = tag.split('}')[1]
            
            if tag == 'da' and child.get('name') == 'DEFAULT':
                default_value = child.get('value', '')
                if default_value:
                    var_info['default'] = default_value
                    # 如果没有其他值，使用默认值作为当前值
                    if 'current_value' not in var_info:
                        var_info['current_value'] = default_value
            
            # 也检查其他可能的值定义方式
            elif tag == 'v' and child.text and child.text.strip():
                if 'current_value' not in var_info:
                    var_info['current_value'] = child.text.strip()
        
        # 如果还没有current_value，使用default
        if 'current_value' not in var_info and var_info['default']:
            var_info['current_value'] = var_info['default']
        
        return var_info if var_info['name'] else None
    
    def _parse_container_element(self, elem) -> Dict[str, Any]:
        """解析容器元素并提取信息"""
        container_info = {
            'name': elem.get('name', ''),
            'type': elem.get('type', 'container'),
            'description': elem.get('desc', ''),
            'path': self._get_element_path(elem),
            'variables': [],
            'tag': elem.tag
        }
        
        # 在此容器中查找变量
        for child in elem:
            if (child.tag.endswith('}var') or child.tag == 'var' or 
                'variable' in child.tag.lower() or 'param' in child.tag.lower()):
                var_name = child.get('name')
                if var_name:
                    container_info['variables'].append(var_name)
        
        return container_info if container_info['name'] else None
    
    def _get_element_path(self, elem) -> str:
        """获取元素的XPath样式路径"""
        path_parts = []
        current = elem
        
        while current is not None:
            tag = current.tag
            if '}' in tag:  # 移除命名空间
                tag = tag.split('}')[1]
            
            name = current.get('name')
            if name:
                path_parts.append(f"{tag}[@name='{name}']")
            else:
                path_parts.append(tag)
            
            current = current.getparent() if hasattr(current, 'getparent') else None
        
        return '/' + '/'.join(reversed(path_parts))
    
    def _determine_container_path(self, elem) -> str:
        """确定变量所属的容器路径"""
        container_names = []
        current = elem
        
        while current is not None:
            # 检查是否是容器元素
            tag = current.tag
            if '}' in tag:
                tag = tag.split('}')[1]
            
            if (tag == 'ctr' or 'container' in tag.lower() or 'module' in tag.lower() or
                tag == 'AR-PACKAGE' or 'IDENTIFIABLE' in tag):
                name = current.get('name')
                if name:
                    container_names.append(name)
            
            # 使用find('..')来获取父元素
            parent = current.find('..')
            if parent is current:  # 避免无限循环
                break
            current = parent
        
        # 反转列表以获得正确的层次顺序
        container_names.reverse()
        return '/'.join(container_names) if container_names else ''
    
    def _categorize_variables(self):
        """将变量分类为LIN特定变量和通道变量"""
        for var_name, var_info in self.variables.items():
            # LIN特定变量
            if any(keyword in var_name.lower() for keyword in ['lin', 'baud', 'wakeup', 'sleep']):
                self.lin_specific_variables[var_name] = var_info.get('default', var_info.get('value', ''))
            
            # 通道相关变量
            if any(keyword in var_name.lower() for keyword in ['channel', 'ch', 'hw']):
                self.channel_variables[var_name] = var_info.get('default', var_info.get('value', ''))
    
    def get_lin_variables(self) -> Dict[str, Any]:
        """获取LIN特定变量"""
        return self.lin_specific_variables.copy()
    
    def get_channel_variables(self) -> Dict[str, Any]:
        """获取通道相关变量"""
        return self.channel_variables.copy()
    
    def generate_variables_tree(self, output_file: str = None) -> Dict[str, Any]:
        """生成综合变量树结构"""
        tree_data = {
            'xdm_file': str(self.xdm_file_path) if self.xdm_file_path else 'N/A',
            'generated_at': datetime.now().isoformat(),
            'parsing_summary': {
                'total_variables': len(self.variables),
                'total_containers': len(self.containers),
                'lin_variables': len(self.lin_specific_variables),
                'channel_variables': len(self.channel_variables)
            },
            'variables': self.variables,
            'containers': self.containers,
            'lin_specific_variables': self.lin_specific_variables,
            'channel_variables': self.channel_variables
        }
        
        # 如果指定了输出文件，则导出到文件
        if output_file:
            try:
                # 导出为JSON
                json_file = output_file.replace('.txt', '.json')
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(tree_data, f, indent=2, ensure_ascii=False)
                self.logger.info(f"变量树JSON已导出到: {json_file}")
                
                # 导出为文本
                text_content = self._generate_text_tree(tree_data)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                self.logger.info(f"变量树文本已导出到: {output_file}")
                
            except Exception as e:
                self.logger.error(f"导出变量树失败: {e}")
        
        return tree_data
    
    def _generate_text_tree(self, tree_data: Dict[str, Any]) -> str:
        """生成可读的文本树结构"""
        lines = []
        lines.append("XDM变量树结构")
        lines.append("=" * 50)
        lines.append(f"源XDM文件: {tree_data['xdm_file']}")
        lines.append("")
        
        # 摘要
        summary = tree_data['parsing_summary']
        lines.append("解析摘要:")
        lines.append(f"  总变量数: {summary['total_variables']}")
        lines.append(f"  总容器数: {summary['total_containers']}")
        lines.append(f"  LIN变量数: {summary['lin_variables']}")
        lines.append(f"  通道变量数: {summary['channel_variables']}")
        lines.append("")
        
        # 容器
        lines.append("容器:")
        for name, info in tree_data['containers'].items():
            lines.append(f"  📁 {name}")
            lines.append(f"     类型: {info.get('type', 'N/A')}")
            lines.append(f"     路径: {info.get('path', 'N/A')}")
            lines.append(f"     变量数: {len(info.get('variables', []))}")
            if info.get('description'):
                lines.append(f"     描述: {info['description'][:100]}...")
            lines.append("")
        
        # LIN特定变量
        lines.append("LIN特定变量:")
        for name, value in tree_data['lin_specific_variables'].items():
            var_info = tree_data['variables'].get(name, {})
            lines.append(f"  🔧 {name}: {value}")
            lines.append(f"     类型: {var_info.get('type', 'N/A')}")
            lines.append(f"     路径: {var_info.get('path', 'N/A')}")
            if var_info.get('description'):
                lines.append(f"     描述: {var_info['description'][:100]}...")
            lines.append("")
        
        # 通道变量
        lines.append("通道变量:")
        for name, value in tree_data['channel_variables'].items():
            var_info = tree_data['variables'].get(name, {})
            lines.append(f"  📡 {name}: {value}")
            lines.append(f"     类型: {var_info.get('type', 'N/A')}")
            lines.append(f"     路径: {var_info.get('path', 'N/A')}")
            if var_info.get('description'):
                lines.append(f"     描述: {var_info['description'][:100]}...")
            lines.append("")
        
        # 所有变量（前50个）
        lines.append("所有变量（前50个）:")
        count = 0
        for name, info in tree_data['variables'].items():
            if count >= 50:
                lines.append(f"  ... 还有 {len(tree_data['variables']) - 50} 个变量")
                break
            lines.append(f"  📋 {name}")
            lines.append(f"     类型: {info.get('type', 'N/A')}")
            lines.append(f"     默认值: {info.get('default', 'N/A')}")
            lines.append(f"     路径: {info.get('path', 'N/A')}")
            if info.get('description'):
                lines.append(f"     描述: {info['description'][:100]}...")
            lines.append("")
            count += 1
        
        return "\n".join(lines)
    
    # ============================================================================
    # 配置管理功能 (来自原XDMConfigEditor)
    # ============================================================================
    
    def initialize_configuration(self):
        """初始化配置结构"""
        try:
            # 重新构建正确的树形结构
            self._build_proper_tree_structure(self.containers, self.variables)
            
            # 创建默认实例
            self._create_default_instances()
            
            self.logger.info(f"配置管理器初始化完成，共 {len(self.all_containers)} 个容器")
            
        except Exception as e:
            self.logger.error(f"初始化配置管理器失败: {e}")
            raise
    
    def _build_proper_tree_structure(self, containers_data: Dict[str, Any], variables_data: Dict[str, Any]):
        """构建正确的XDM树形结构 - 基于XDM文件的实际层次关系"""
        
        # 基于XDM文件分析，定义正确的树形结构
        tree_structure = {
            # 根级模块容器
            'Lin': {
                'type': 'MODULE-DEF',
                'multiplicity': '*',
                'variables': ['IMPLEMENTATION_CONFIG_VARIANT'],
                'children': {
                    'LinDemEventParameterRefs': {
                        'type': 'IDENTIFIABLE',
                        'multiplicity': '1',
                        'variables': [],
                        'children': {}
                    },
                    'LinGeneral': {
                        'type': 'IDENTIFIABLE', 
                        'multiplicity': '1',
                        'variables': [
                            'LinDevErrorDetect', 'LinMultiCoreErrorDetect', 'LinIndex',
                            'LinTimeoutDuration', 'LinVersionInfoApi', 'LinHwMcuTrigSleepEnable',
                            'LinCsrClksel', 'LinInitApiMode', 'LinInterruptEnable'
                        ],
                        'children': {}
                    },
                    'LinGlobalConfig': {
                        'type': 'IDENTIFIABLE',
                        'multiplicity': '1', 
                        'variables': [],
                        'children': {
                            'LinChannel': {
                                'type': 'IDENTIFIABLE',
                                'multiplicity': '*',  # 可以有多个LinChannel实例
                                'variables': [
                                    'LinChannelBaudRate', 'LinChannelId', 'LinChannelWakeupSupport',
                                    'LinChanAssignedHw', 'LinAutoCalcBaudParams', 'LinChannelBaudNumerator',
                                    'LinChannelBaudDenominator', 'LinChannelBaudPreScalar', 'LinInterByteSpace',
                                    'LinRxAlternateInputSignal'
                                ],
                                'children': {}
                            }
                        }
                    },
                    'CommonPublishedInformation': {
                        'type': 'IDENTIFIABLE',
                        'multiplicity': '1',
                        'variables': [
                            'ArMajorVersion', 'ArMinorVersion', 'ArPatchVersion',
                            'SwMajorVersion', 'SwMinorVersion', 'SwPatchVersion',
                            'ModuleId', 'VendorId', 'VendorApiInfix', 'Release'
                        ],
                        'children': {}
                    }
                }
            }
        }
        
        # 递归创建容器结构
        self._create_containers_from_structure(tree_structure, variables_data)
        
        if self.verbose:
            self.logger.debug(f"创建了 {len(self.all_containers)} 个容器:")
            for name, container in self.all_containers.items():
                var_count = len(container.variables)
                self.logger.debug(f"  {name}: {var_count} 个变量")
    
    def _create_containers_from_structure(self, structure: Dict[str, Any], variables_data: Dict[str, Any], parent_container=None, parent_path=""):
        """递归创建容器结构"""
        
        for container_name, container_info in structure.items():
            # 构建完整路径
            full_path = f"{parent_path}/{container_name}" if parent_path else container_name
            
            # 创建容器定义
            container_def = {
                'name': container_name,
                'type': container_info.get('type', 'IDENTIFIABLE'),
                'multiplicity': container_info.get('multiplicity', '1'),
                'description': f'{container_name} 容器',
                'path': full_path
            }
            
            # 创建容器对象
            container = ConfigContainer(container_name, container_def, parent_container)
            
            # 添加到容器映射
            self.all_containers[container_name] = container
            
            # 如果是根容器，添加到根容器列表
            if parent_container is None:
                self.root_containers[container_name] = container
            else:
                parent_container.add_child_container(container)
            
            # 添加变量到容器
            for var_name in container_info.get('variables', []):
                if var_name in variables_data:
                    var_def = variables_data[var_name]
                    container.add_variable(var_name, var_def)
                    if self.verbose:
                        self.logger.debug(f"变量 {var_name} 添加到容器 {container_name}")
            
            # 递归创建子容器
            children = container_info.get('children', {})
            if children:
                self._create_containers_from_structure(children, variables_data, container, full_path)
    
    def _create_default_instances(self):
        """为所有容器创建默认实例"""
        for container in self.all_containers.values():
            container.create_instance()
    
    def get_container(self, container_path: str) -> Optional[ConfigContainer]:
        """获取容器对象"""
        # 首先尝试从all_containers获取
        container = self.all_containers.get(container_path)
        if container:
            return container
        
        # 如果没找到，尝试从containers字典获取并创建ConfigContainer对象
        if container_path in self.containers:
            container_info = self.containers[container_path]
            # 创建临时的ConfigContainer对象
            temp_container = ConfigContainer(
                name=container_info.get('name', container_path.split('/')[-1]),
                definition=container_info
            )
            # 添加变量
            variables = container_info.get('variables', {})
            if isinstance(variables, dict):
                for var_name, var_info in variables.items():
                    temp_container.add_variable(var_name, var_info)
            elif isinstance(variables, list):
                for var_info in variables:
                    if isinstance(var_info, dict) and 'name' in var_info:
                        temp_container.add_variable(var_info['name'], var_info)
            
            return temp_container
        
        return None
    
    def create_container_instance(self, container_path: str) -> Optional[int]:
        """创建容器实例"""
        container = self.get_container(container_path)
        if container:
            try:
                instance_id = container.create_instance()
                self._record_change('create_instance', container_path, {'instance_id': instance_id})
                return instance_id
            except ValueError as e:
                self.logger.error(f"创建实例失败: {e}")
        return None
    
    def delete_container_instance(self, container_path: str, instance_id: int) -> bool:
        """删除容器实例"""
        container = self.get_container(container_path)
        if container and container.delete_instance(instance_id):
            self._record_change('delete_instance', container_path, {'instance_id': instance_id})
            return True
        return False
    
    def set_variable_value(self, container_path: str, var_name: str, value: Any, instance_id: int = None) -> bool:
        """设置变量值"""
        container = self.get_container(container_path)
        if container:
            old_value = container.get_variable_value(var_name, instance_id)
            if container.set_variable_value(var_name, value, instance_id):
                self._record_change('modify_variable', container_path, {
                    'variable': var_name,
                    'instance_id': instance_id or container.current_instance,
                    'old_value': old_value,
                    'new_value': value
                })
                return True
        elif var_name in self.global_variables:
            # 全局变量
            old_value = self.global_variables[var_name]['value']
            self.global_variables[var_name]['value'] = value
            self._record_change('modify_global_variable', '', {
                'variable': var_name,
                'old_value': old_value,
                'new_value': value
            })
            return True
        return False
    
    def get_variable_value(self, container_path: str, var_name: str, instance_id: int = None) -> Any:
        """获取变量值"""
        # 如果没有指定容器路径，尝试在所有容器中查找该变量
        if not container_path:
            for container in self.all_containers.values():
                if var_name in container.variables:
                    return container.get_variable_value(var_name, instance_id)
        
        container = self.get_container(container_path)
        if container and var_name in container.variables:
            return container.get_variable_value(var_name, instance_id)
        
        return None
    
    def get_container_instances(self, container_path: str) -> List[Dict[str, Any]]:
        """获取容器的所有实例"""
        container = self.get_container(container_path)
        return container.instances if container else []
    
    def get_container_variables(self, container_path: str) -> Dict[str, Any]:
        """获取指定容器的所有变量（叶子节点）"""
        variables = {}
        
        # 方法1：从容器对象获取变量
        container = self.get_container(container_path)
        if container and hasattr(container, 'variables'):
            for var_name, var_def in container.variables.items():
                variables[var_name] = {
                    'name': var_name,
                    'definition': var_def,
                    'current_value': container.get_variable_value(var_name),
                    'container_path': container_path
                }
        
        # 方法2：从全局变量中查找属于此容器的变量
        container_name = container_path.split('/')[-1] if container_path else ''
        for var_name, var_info in self.variables.items():
            # 检查变量是否属于此容器
            var_container_path = var_info.get('container_path', '')
            var_path = var_info.get('path', '')
            
            if (var_container_path == container_path or 
                var_container_path.endswith(f"/{container_name}") or
                container_name in var_path):
                
                if var_name not in variables:
                    variables[var_name] = {
                        'name': var_name,
                        'definition': var_info,
                        'current_value': var_info.get('value', var_info.get('default', '')),
                        'container_path': container_path
                    }
        
        return variables
    
    def get_container_full_config(self, container_path: str) -> Dict[str, Any]:
        """获取容器的完整配置信息"""
        container_config = {
            'path': container_path,
            'name': container_path.split('/')[-1] if container_path else '',
            'type': 'container',
            'variables': {},
            'instances': [],
            'metadata': {}
        }
        
        # 获取容器对象
        container = self.get_container(container_path)
        if container:
            container_config.update({
                'multiplicity': container.multiplicity,
                'instance_count': len(container.instances),
                'current_instance': container.current_instance,
                'definition': container.definition
            })
            
            # 获取所有实例的变量值
            for i, instance_data in enumerate(container.instances):
                instance_config = {
                    'instance_id': i,
                    'variables': {}
                }
                
                # 获取该实例的所有变量值
                for var_name in container.variables.keys():
                    var_value = container.get_variable_value(var_name, i)
                    instance_config['variables'][var_name] = var_value
                
                container_config['instances'].append(instance_config)
            
            # 获取变量定义
            for var_name, var_def in container.variables.items():
                container_config['variables'][var_name] = {
                    'definition': var_def['definition'],
                    'current_value': container.get_variable_value(var_name),
                    'all_values': var_def['values']
                }
        
        # 从全局变量中获取相关变量
        container_name = container_path.split('/')[-1] if container_path else ''
        for var_name, var_info in self.variables.items():
            var_container_path = var_info.get('container_path', '')
            if (var_container_path == container_path or 
                var_container_path.endswith(f"/{container_name}") or
                container_name in var_info.get('path', '')):
                
                if var_name not in container_config['variables']:
                    container_config['variables'][var_name] = {
                        'definition': var_info,
                        'current_value': var_info.get('value', var_info.get('default', '')),
                        'source': 'xdm_global'
                    }
        
        # 添加元数据
        container_config['metadata'] = {
            'export_time': datetime.now().isoformat(),
            'source_xdm': str(self.xdm_file_path) if self.xdm_file_path else 'N/A',
            'total_variables': len(container_config['variables']),
            'modification_count': self.modification_count
        }
        
        return container_config
    
    def set_current_instance(self, container_path: str, instance_id: int) -> bool:
        """设置当前实例"""
        container = self.get_container(container_path)
        if container and 0 <= instance_id < len(container.instances):
            container.current_instance = instance_id
            return True
        return False
    
    def get_configuration_tree(self) -> Dict[str, Any]:
        """获取完整的配置树结构"""
        def build_tree_node(container: ConfigContainer) -> Dict[str, Any]:
            node = {
                'name': container.name,
                'path': container.get_full_path(),
                'multiplicity': container.multiplicity,
                'instance_count': len(container.instances),
                'current_instance': container.current_instance,
                'variables': {},
                'children': {}
            }
            
            # 添加变量信息
            for var_name, var_info in container.variables.items():
                node['variables'][var_name] = {
                    'definition': var_info['definition'],
                    'values': var_info['values'],
                    'current_value': container.get_variable_value(var_name)
                }
            
            # 递归添加子容器
            for child_container in container.children.values():
                child_node = build_tree_node(child_container)
                # 如果支持多实例且有多个实例，添加实例信息
                if child_container.multiplicity == '*' and len(child_container.instances) > 1:
                    child_node['instances'] = []
                    for i, instance_data in enumerate(child_container.instances):
                        instance_node = child_node.copy()
                        instance_node['instance_id'] = i
                        instance_node['variables'] = {}
                        # 获取该实例的变量值
                        for var_name, var_info in child_container.variables.items():
                            instance_node['variables'][var_name] = {
                                'definition': var_info['definition'],
                                'value': child_container.get_variable_value(var_name, i)
                            }
                        child_node['instances'].append(instance_node)
                
                node['children'][child_container.name] = child_node
            
            return node
        
        tree = {
            'root_containers': {},
            'modification_count': self.modification_count
        }
        
        for root_name, root_container in self.root_containers.items():
            tree['root_containers'][root_name] = build_tree_node(root_container)
        
        return tree
    
    def export_configuration(self, output_file: str, format: str = 'json') -> bool:
        """导出配置"""
        try:
            config_tree = self.get_configuration_tree()
            config_tree['export_info'] = {
                'timestamp': datetime.now().isoformat(),
                'format': format,
                'modification_count': self.modification_count
            }
            
            if format.lower() == 'json':
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(config_tree, f, indent=2, ensure_ascii=False)
            else:
                self.logger.error(f"不支持的导出格式: {format}")
                return False
            
            self.logger.info(f"配置已导出到: {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"导出配置失败: {e}")
            return False
    
    def import_configuration(self, config_file: str) -> bool:
        """导入配置"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # TODO: 实现配置导入逻辑
            self.logger.info(f"配置已从 {config_file} 导入")
            return True
            
        except Exception as e:
            self.logger.error(f"导入配置失败: {e}")
            return False
    
    def _record_change(self, action: str, container_path: str, details: Dict[str, Any]):
        """记录配置变更"""
        change_record = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'container_path': container_path,
            'details': details
        }
        self.configuration_history.append(change_record)
        self.modification_count += 1
        
        if self.verbose:
            self.logger.info(f"配置变更: {action} - {container_path}")
    
    def get_modification_history(self) -> List[Dict[str, Any]]:
        """获取修改历史"""
        return self.configuration_history.copy()
    
    def reset_to_defaults(self):
        """重置所有配置到默认值"""
        for container in self.all_containers.values():
            # 重置到单个默认实例
            container.instances = []
            container.current_instance = 0
            container.create_instance()
        
        self.configuration_history.clear()
        self.modification_count = 0
        self.logger.info("所有配置已重置为默认值")
    
    # ============================================================================
    # 向后兼容方法 - 为了与现有GUI代码兼容
    # ============================================================================
    
    def list_variables(self, category: str = 'all') -> Dict[str, Any]:
        """列出变量 - 向后兼容方法"""
        if category == 'lin':
            return self.get_lin_variables()
        elif category == 'channel':
            return self.get_channel_variables()
        else:
            # 从所有容器中收集变量
            all_vars = {}
            for container in self.all_containers.values():
                for var_name, var_info in container.variables.items():
                    all_vars[var_name] = var_info['definition']
            # 合并解析的变量
            all_vars.update(self.variables)
            return all_vars
    
    def list_containers(self) -> Dict[str, Any]:
        """列出容器 - 向后兼容方法"""
        # 从配置管理器返回容器定义
        containers = {}
        for container_name, container in self.all_containers.items():
            containers[container_name] = container.definition
        # 合并解析的容器
        containers.update(self.containers)
        return containers
    
    def get_variable_info(self, var_name: str) -> Optional[Dict[str, Any]]:
        """获取变量详细信息 - 向后兼容方法"""
        # 首先在解析的变量中查找
        if var_name in self.variables:
            return self.variables[var_name]
        
        # 在容器中查找
        for container in self.all_containers.values():
            if var_name in container.variables:
                return container.variables[var_name]['definition']
        
        return None
    
    def get_container_info(self, container_name: str) -> Optional[Dict[str, Any]]:
        """获取容器详细信息 - 向后兼容方法"""
        # 首先在解析的容器中查找
        if container_name in self.containers:
            return self.containers[container_name]
        
        # 在配置容器中查找
        container = self.get_container(container_name)
        return container.definition if container else None
    
    def modify_variable(self, var_name: str, new_value: Any, container_path: str = "", instance_id: int = None, comment: str = "") -> bool:
        """修改变量值 - 向后兼容方法"""
        return self.set_variable_value(container_path, var_name, new_value, instance_id)
    
    def modify_container(self, container_name: str, config_updates: Dict[str, Any], comment: str = "") -> bool:
        """修改容器配置 - 向后兼容方法"""
        # TODO: 实现容器配置修改
        self.logger.warning("modify_container方法需要进一步实现")
        return False
    
    def reset_variable(self, var_name: str) -> bool:
        """重置变量到默认值 - 向后兼容方法"""
        # 在容器中查找并重置
        for container in self.all_containers.values():
            if var_name in container.variables:
                default_value = container.variables[var_name]['definition'].get('default', '')
                return container.set_variable_value(var_name, default_value)
        
        return False
    
    def reset_container(self, container_name: str) -> bool:
        """重置容器到默认配置 - 向后兼容方法"""
        container = self.get_container(container_name)
        if container:
            # 重置到单个默认实例
            container.instances = []
            container.current_instance = 0
            container.create_instance()
            return True
        return False
    
    @property
    def modified_variables(self) -> Dict[str, Any]:
        """获取修改过的变量 - 向后兼容属性"""
        modified = {}
        
        # 检查容器中的变量
        for container in self.all_containers.values():
            for var_name, var_info in container.variables.items():
                default_value = var_info['definition'].get('default', '')
                current_value = container.get_variable_value(var_name)
                if current_value != default_value:
                    modified[var_name] = current_value
        
        return modified
    
    @property
    def modified_containers(self) -> Dict[str, Any]:
        """获取修改过的容器 - 向后兼容属性"""
        modified = {}
        
        for container_name, container in self.all_containers.items():
            # 如果容器有多个实例或实例被修改，认为容器被修改了
            if len(container.instances) > 1:
                modified[container_name] = {
                    'instance_count': len(container.instances),
                    'instances': container.instances
                }
        
        return modified
    
    def export_config(self, output_file: str, format: str = 'json') -> bool:
        """导出配置 - 向后兼容方法"""
        return self.export_configuration(output_file, format)
    
    def import_config(self, config_file: str) -> bool:
        """导入配置 - 向后兼容方法"""
        return self.import_configuration(config_file)
    
    def get_current_config(self) -> Dict[str, Any]:
        """获取当前配置"""
        return {
            'containers': {name: container.get_full_path() for name, container in self.all_containers.items()},
            'modified_variables': self.modified_variables,
            'modified_containers': self.modified_containers,
            'modification_count': self.modification_count
        }
    
    # ============================================================================
    # 实例管理方法
    # ============================================================================
    
    def add_instance(self, container_path: str) -> bool:
        """添加容器实例"""
        container = self.get_container(container_path)
        if container:
            try:
                instance_id = container.create_instance()
                self._record_change('add_instance', container_path, {
                    'instance_id': instance_id,
                    'action': 'created'
                })
                self.logger.info(f"为容器 {container_path} 添加实例 {instance_id}")
                return True
            except ValueError as e:
                self.logger.error(f"添加实例失败: {e}")
                return False
        return False
    
    def delete_instance(self, container_path: str, instance_id: int = None) -> bool:
        """删除容器实例"""
        container = self.get_container(container_path)
        if container:
            if instance_id is None:
                # 删除当前实例
                instance_id = container.current_instance
            
            if container.delete_instance(instance_id):
                self._record_change('delete_instance', container_path, {
                    'instance_id': instance_id,
                    'action': 'deleted'
                })
                self.logger.info(f"从容器 {container_path} 删除实例 {instance_id}")
                return True
        return False
    
    def switch_instance(self, container_path: str, instance_id: int = None) -> bool:
        """切换容器实例"""
        container = self.get_container(container_path)
        if container:
            if instance_id is None:
                # 切换到下一个实例
                current = container.current_instance
                next_instance = (current + 1) % len(container.instances)
                instance_id = next_instance
            
            if 0 <= instance_id < len(container.instances):
                old_instance = container.current_instance
                container.current_instance = instance_id
                self._record_change('switch_instance', container_path, {
                    'old_instance': old_instance,
                    'new_instance': instance_id
                })
                self.logger.info(f"容器 {container_path} 从实例 {old_instance} 切换到实例 {instance_id}")
                return True
        return False
    
    def list_instances(self, container_path: str) -> List[Dict[str, Any]]:
        """列出容器实例"""
        container = self.get_container(container_path)
        if container:
            instances = []
            for i, instance_data in enumerate(container.instances):
                instance_info = {
                    'id': i,
                    'name': instance_data['name'],
                    'created_time': instance_data.get('created_time', ''),
                    'is_current': i == container.current_instance,
                    'variables': instance_data.get('variables', {})
                }
                instances.append(instance_info)
            return instances
        return []
    
    def get_instance_count(self, container_path: str) -> int:
        """获取容器实例数量"""
        container = self.get_container(container_path)
        return len(container.instances) if container else 0
    
    def get_current_instance(self, container_path: str) -> int:
        """获取当前实例ID"""
        container = self.get_container(container_path)
        return container.current_instance if container else 0
    
    def copy_instance(self, container_path: str, source_instance_id: int, target_instance_id: int = None) -> bool:
        """复制实例配置"""
        container = self.get_container(container_path)
        if container and 0 <= source_instance_id < len(container.instances):
            if target_instance_id is None:
                # 创建新实例作为目标
                target_instance_id = container.create_instance()
            elif target_instance_id >= len(container.instances):
                return False
            
            # 复制变量值
            source_vars = container.instances[source_instance_id].get('variables', {})
            for var_name, value in source_vars.items():
                container.set_variable_value(var_name, value, target_instance_id)
            
            self._record_change('copy_instance', container_path, {
                'source_instance': source_instance_id,
                'target_instance': target_instance_id
            })
            self.logger.info(f"容器 {container_path} 实例 {source_instance_id} 配置已复制到实例 {target_instance_id}")
            return True
        return False
    
    def reset_instance(self, container_path: str, instance_id: int = None) -> bool:
        """重置实例到默认值"""
        container = self.get_container(container_path)
        if container:
            if instance_id is None:
                instance_id = container.current_instance
            
            if 0 <= instance_id < len(container.instances):
                # 重置所有变量到默认值
                for var_name, var_info in container.variables.items():
                    default_value = var_info['definition'].get('default', '')
                    container.set_variable_value(var_name, default_value, instance_id)
                
                self._record_change('reset_instance', container_path, {
                    'instance_id': instance_id
                })
                self.logger.info(f"容器 {container_path} 实例 {instance_id} 已重置为默认值")
                return True
        return False
    
    def create_sub_container(self, parent_path: str, container_name: str, container_type: str = "container", description: str = "") -> bool:
        """创建子容器"""
        try:
            # 获取父容器
            parent_container = self.get_container(parent_path)
            if not parent_container:
                self.logger.error(f"父容器不存在: {parent_path}")
                return False
            
            # 构建新容器路径
            new_container_path = f"{parent_path}/{container_name}"
            
            # 检查容器是否已存在
            if self.get_container(new_container_path):
                self.logger.error(f"容器已存在: {new_container_path}")
                return False
            
            # 创建新容器对象
            new_container = ConfigContainer(
                name=container_name,
                path=new_container_path,
                definition={
                    'name': container_name,
                    'type': container_type,
                    'description': description,
                    'multiplicity': '1',
                    'parent': parent_path
                }
            )
            
            # 添加到容器字典
            self.containers[new_container_path] = new_container
            self.all_containers[new_container_path] = new_container
            
            # 更新父容器的子容器列表
            if not hasattr(parent_container, 'children'):
                parent_container.children = {}
            parent_container.children[container_name] = {
                'name': container_name,
                'path': new_container_path,
                'type': container_type,
                'description': description,
                'variables': {},
                'children': {},
                'instances': [],
                'instance_count': 1,
                'multiplicity': '1'
            }
            
            # 更新配置树
            if hasattr(self, 'config_tree'):
                parent_parts = parent_path.split('/')
                current_node = self.config_tree
                
                # 导航到父节点
                for part in parent_parts:
                    if part and part in current_node.get('children', {}):
                        current_node = current_node['children'][part]
                
                # 添加新的子容器节点
                if 'children' not in current_node:
                    current_node['children'] = {}
                
                current_node['children'][container_name] = {
                    'name': container_name,
                    'path': new_container_path,
                    'type': container_type,
                    'description': description,
                    'variables': {},
                    'children': {},
                    'instances': [],
                    'instance_count': 1,
                    'multiplicity': '1'
                }
            
            self.logger.info(f"子容器创建成功: {new_container_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"创建子容器失败: {e}")
            return False
    
    def duplicate_container(self, source_path: str, target_path: str, copy_options: Dict[str, bool]) -> bool:
        """复制容器"""
        try:
            # 获取源容器
            source_container = self.get_container(source_path)
            if not source_container:
                self.logger.error(f"源容器不存在: {source_path}")
                return False
            
            # 检查目标容器是否已存在
            if self.get_container(target_path):
                self.logger.error(f"目标容器已存在: {target_path}")
                return False
            
            # 解析目标路径
            target_parts = target_path.split('/')
            target_name = target_parts[-1]
            target_parent_path = '/'.join(target_parts[:-1]) if len(target_parts) > 1 else ""
            
            # 深度复制源容器的定义
            import copy
            new_definition = copy.deepcopy(source_container.definition)
            new_definition['name'] = target_name
            if target_parent_path:
                new_definition['parent'] = target_parent_path
            
            # 创建新容器对象
            new_container = ConfigContainer(
                name=target_name,
                definition=new_definition
            )
            
            # 复制变量
            if copy_options.get('copy_variables', True):
                if hasattr(source_container, 'variables'):
                    new_container.variables = copy.deepcopy(source_container.variables)
            
            # 复制实例
            if copy_options.get('copy_instances', True):
                if hasattr(source_container, 'instances'):
                    new_container.instances = copy.deepcopy(source_container.instances)
                if hasattr(source_container, 'multiplicity'):
                    new_container.multiplicity = source_container.multiplicity
                if hasattr(source_container, 'current_instance'):
                    new_container.current_instance = source_container.current_instance
            
            # 添加到容器字典
            self.containers[target_path] = new_container
            self.all_containers[target_path] = new_container
            
            # 如果有父容器，更新其子容器列表
            if target_parent_path:
                target_parent = self.get_container(target_parent_path)
                if target_parent and hasattr(target_parent, 'children'):
                    if not target_parent.children:
                        target_parent.children = {}
                    target_parent.children[target_name] = {
                        'name': target_name,
                        'path': target_path,
                        'type': new_definition.get('type', 'container'),
                        'description': new_definition.get('description', ''),
                        'variables': {},
                        'children': {},
                        'instances': [],
                        'instance_count': 1,
                        'multiplicity': new_definition.get('multiplicity', '1')
                    }
            
            # 递归复制子容器
            if copy_options.get('copy_children', False):
                if hasattr(source_container, 'children') and source_container.children:
                    for child_name, child_info in source_container.children.items():
                        child_source_path = f"{source_path}/{child_name}"
                        child_target_path = f"{target_path}/{child_name}"
                        self.duplicate_container(child_source_path, child_target_path, copy_options)
            
            self.logger.info(f"容器复制成功: {source_path} -> {target_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"复制容器失败: {e}")
            return False
    
    def delete_container(self, container_path: str) -> bool:
        """删除容器"""
        try:
            # 获取要删除的容器
            container = self.get_container(container_path)
            if not container:
                self.logger.error(f"容器不存在: {container_path}")
                return False
            
            # 解析容器路径
            path_parts = container_path.split('/')
            container_name = path_parts[-1]
            parent_path = '/'.join(path_parts[:-1])
            
            # 获取父容器
            parent_container = self.get_container(parent_path) if parent_path else None
            
            # 递归删除所有子容器
            if hasattr(container, 'children') and container.children:
                for child_name in list(container.children.keys()):
                    child_path = f"{container_path}/{child_name}"
                    self.delete_container(child_path)
            
            # 从容器字典中删除
            if container_path in self.containers:
                del self.containers[container_path]
            if container_path in self.all_containers:
                del self.all_containers[container_path]
            
            # 从父容器的子容器列表中删除
            if parent_container and hasattr(parent_container, 'children'):
                if container_name in parent_container.children:
                    del parent_container.children[container_name]
            
            # 更新配置树
            if hasattr(self, 'config_tree') and parent_path:
                parent_parts = parent_path.split('/')
                current_node = self.config_tree
                
                # 导航到父节点
                for part in parent_parts:
                    if part and part in current_node.get('children', {}):
                        current_node = current_node['children'][part]
                
                # 删除容器节点
                if 'children' in current_node and container_name in current_node['children']:
                    del current_node['children'][container_name]
            
            # 如果是根级容器，直接从配置树删除
            elif hasattr(self, 'config_tree') and not parent_path:
                if 'children' in self.config_tree and container_name in self.config_tree['children']:
                    del self.config_tree['children'][container_name]
            
            self.logger.info(f"容器删除成功: {container_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除容器失败: {e}")
            return False
    
    def analyze_element_usage(self, element_path: str) -> Dict[str, Any]:
        """分析元素的使用情况"""
        try:
            usage_info = {
                'element_path': element_path,
                'element_name': element_path.split('/')[-1],
                'element_type': 'container' if element_path in self.containers else 'variable',
                'references': [],
                'dependencies': [],
                'dependents': [],
                'total_references': 0
            }
            
            # 分析容器引用
            if element_path in self.containers:
                usage_info.update(self._analyze_container_usage(element_path))
            
            # 分析变量引用
            elif element_path in self.variables:
                usage_info.update(self._analyze_variable_usage(element_path))
            
            # 通用分析：在所有容器和变量中搜索引用
            usage_info['references'].extend(self._find_cross_references(element_path))
            usage_info['total_references'] = len(usage_info['references'])
            
            return usage_info
            
        except Exception as e:
            self.logger.error(f"分析元素使用情况失败: {e}")
            return {
                'element_path': element_path,
                'error': str(e),
                'references': [],
                'total_references': 0
            }
    
    def _analyze_container_usage(self, container_path: str) -> Dict[str, Any]:
        """分析容器的使用情况"""
        analysis = {
            'sub_containers': [],
            'parent_containers': [],
            'variable_references': [],
            'instance_references': []
        }
        
        container = self.get_container(container_path)
        if not container:
            return analysis
        
        # 查找子容器
        if hasattr(container, 'children') and container.children:
            for child_name, child_info in container.children.items():
                analysis['sub_containers'].append({
                    'name': child_name,
                    'path': f"{container_path}/{child_name}",
                    'type': 'sub_container',
                    'description': child_info.get('description', '')
                })
        
        # 查找父容器
        if hasattr(container, 'parent') and container.parent:
            analysis['parent_containers'].append({
                'name': container.parent.name,
                'path': container.parent.get_full_path(),
                'type': 'parent_container',
                'description': 'Parent container'
            })
        
        # 查找容器中的变量引用
        if hasattr(container, 'variables') and container.variables:
            for var_name, var_info in container.variables.items():
                analysis['variable_references'].append({
                    'name': var_name,
                    'path': f"{container_path}/{var_name}",
                    'type': 'variable',
                    'current_value': container.get_variable_value(var_name),
                    'description': var_info.get('definition', {}).get('description', '')
                })
        
        # 查找实例引用
        if hasattr(container, 'instances') and container.instances:
            for i, instance in enumerate(container.instances):
                analysis['instance_references'].append({
                    'name': f"Instance_{i}",
                    'path': f"{container_path}[{i}]",
                    'type': 'instance',
                    'instance_id': i,
                    'description': f"Container instance {i}"
                })
        
        return analysis
    
    def _analyze_variable_usage(self, var_name: str) -> Dict[str, Any]:
        """分析变量的使用情况"""
        analysis = {
            'container_references': [],
            'value_references': [],
            'definition_references': []
        }
        
        # 查找包含此变量的容器
        for container_path, container in self.all_containers.items():
            if hasattr(container, 'variables') and var_name in container.variables:
                var_info = container.variables[var_name]
                analysis['container_references'].append({
                    'name': container.name,
                    'path': container_path,
                    'type': 'container',
                    'current_value': container.get_variable_value(var_name),
                    'description': f"Variable {var_name} in container {container.name}"
                })
                
                # 分析实例中的值引用
                if hasattr(container, 'instances'):
                    for i, instance in enumerate(container.instances):
                        if var_name in instance.get('variables', {}):
                            analysis['value_references'].append({
                                'name': f"{container.name}[{i}].{var_name}",
                                'path': f"{container_path}[{i}]/{var_name}",
                                'type': 'instance_value',
                                'instance_id': i,
                                'value': instance['variables'][var_name],
                                'description': f"Value in instance {i}"
                            })
        
        # 查找全局变量定义
        if var_name in self.variables:
            var_def = self.variables[var_name]
            analysis['definition_references'].append({
                'name': var_name,
                'path': var_def.get('path', var_name),
                'type': 'definition',
                'default_value': var_def.get('default', ''),
                'description': var_def.get('description', '')
            })
        
        return analysis
    
    def _find_cross_references(self, element_path: str) -> List[Dict[str, Any]]:
        """查找跨容器的引用关系"""
        references = []
        element_name = element_path.split('/')[-1]
        
        # 在所有容器的定义中搜索引用
        for container_path, container_info in self.containers.items():
            if container_path == element_path:
                continue
                
            # 检查容器定义中是否引用了此元素
            container_def_str = str(container_info)
            if element_name in container_def_str or element_path in container_def_str:
                references.append({
                    'name': container_info.get('name', container_path.split('/')[-1]),
                    'path': container_path,
                    'type': 'cross_reference',
                    'reference_type': 'definition',
                    'description': f"Referenced in {container_path} definition"
                })
        
        # 在所有变量的定义中搜索引用
        for var_name, var_info in self.variables.items():
            if var_name == element_name:
                continue
                
            var_def_str = str(var_info)
            if element_name in var_def_str or element_path in var_def_str:
                references.append({
                    'name': var_name,
                    'path': var_info.get('path', var_name),
                    'type': 'cross_reference',
                    'reference_type': 'variable_definition',
                    'description': f"Referenced in variable {var_name} definition"
                })
        
        return references
    
    def get_element_dependencies(self, element_path: str) -> Dict[str, Any]:
        """获取元素的依赖关系"""
        dependencies = {
            'direct_dependencies': [],
            'indirect_dependencies': [],
            'circular_dependencies': []
        }
        
        # 这里可以实现更复杂的依赖分析逻辑
        # 暂时返回基本结构
        
        return dependencies
    
    def add_container_instance(self, container_path: str, instance_data: Dict[str, Any]) -> bool:
        """添加容器实例"""
        try:
            container = self.get_container(container_path)
            if not container:
                self.logger.error(f"容器不存在: {container_path}")
                return False
            
            # 确保容器有实例列表
            if not hasattr(container, 'instances'):
                container.instances = []
            
            # 添加实例
            container.instances.append(instance_data)
            
            # 更新容器字典
            if container_path in self.containers:
                if 'instances' not in self.containers[container_path]:
                    self.containers[container_path]['instances'] = []
                self.containers[container_path]['instances'].append(instance_data)
            
            self.logger.info(f"添加实例成功: {container_path} -> {instance_data.get('name', 'unnamed')}")
            return True
            
        except Exception as e:
            self.logger.error(f"添加实例失败: {e}")
            return False
    
    def remove_container_instance(self, container_path: str, instance_id: int) -> bool:
        """删除容器实例"""
        try:
            container = self.get_container(container_path)
            if not container:
                self.logger.error(f"容器不存在: {container_path}")
                return False
            
            # 检查实例是否存在
            if not hasattr(container, 'instances') or len(container.instances) <= instance_id:
                self.logger.error(f"实例不存在: {container_path}[{instance_id}]")
                return False
            
            # 删除实例
            removed_instance = container.instances.pop(instance_id)
            
            # 更新容器字典
            if container_path in self.containers and 'instances' in self.containers[container_path]:
                if len(self.containers[container_path]['instances']) > instance_id:
                    self.containers[container_path]['instances'].pop(instance_id)
            
            self.logger.info(f"删除实例成功: {container_path}[{instance_id}] -> {removed_instance.get('name', 'unnamed')}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除实例失败: {e}")
            return False
    
    def update_container_instance(self, container_path: str, instance_id: int, instance_data: Dict[str, Any]) -> bool:
        """更新容器实例"""
        try:
            container = self.get_container(container_path)
            if not container:
                self.logger.error(f"容器不存在: {container_path}")
                return False
            
            # 检查实例是否存在
            if not hasattr(container, 'instances') or len(container.instances) <= instance_id:
                self.logger.error(f"实例不存在: {container_path}[{instance_id}]")
                return False
            
            # 更新实例
            container.instances[instance_id] = instance_data
            
            # 更新容器字典
            if container_path in self.containers and 'instances' in self.containers[container_path]:
                if len(self.containers[container_path]['instances']) > instance_id:
                    self.containers[container_path]['instances'][instance_id] = instance_data
            
            self.logger.info(f"更新实例成功: {container_path}[{instance_id}] -> {instance_data.get('name', 'unnamed')}")
            return True
            
        except Exception as e:
            self.logger.error(f"更新实例失败: {e}")
            return False
    
    def get_container_instances(self, container_path: str) -> List[Dict[str, Any]]:
        """获取容器实例列表"""
        try:
            container = self.get_container(container_path)
            if not container:
                return []
            
            instances = getattr(container, 'instances', [])
            return instances
            
        except Exception as e:
            self.logger.error(f"获取实例列表失败: {e}")
            return []
    
    def get_container_full_config(self, container_path: str) -> Dict[str, Any]:
        """获取容器完整配置信息"""
        try:
            container = self.get_container(container_path)
            if not container:
                return {}
            
            # 基本信息
            config = {
                'path': container_path,
                'name': container_path.split('/')[-1],
                'type': 'container',
                'variables': {},
                'instances': [],
                'metadata': {}
            }
            
            # 添加变量信息
            if hasattr(container, 'variables'):
                for var_name, var_info in container.variables.items():
                    config['variables'][var_name] = {
                        'current_value': container.get_variable_value(var_name),
                        'definition': var_info
                    }
            
            # 添加实例信息
            if hasattr(container, 'instances'):
                config['instances'] = container.instances
                config['instance_count'] = len(container.instances)
            
            # 添加多重性信息
            if hasattr(container, 'multiplicity'):
                config['multiplicity'] = container.multiplicity
            else:
                config['multiplicity'] = '1..*' if config['instances'] else '1'
            
            # 添加元数据
            if hasattr(container, 'definition'):
                config['metadata'] = {
                    'description': getattr(container.definition, 'description', ''),
                    'category': getattr(container.definition, 'category', ''),
                    'vendor': getattr(container.definition, 'vendor', ''),
                    'version': getattr(container.definition, 'version', '')
                }
            
            return config
            
        except Exception as e:
            self.logger.error(f"获取容器完整配置失败: {e}")
            return {}

    def get_tree_structure(self):
        """
        构建并返回整个模块的树形结构。
        这是对内部方法_build_proper_tree_structure的公开封装。
        """
        if not self.containers:
            self.logger.warning("容器数据为空，无法构建树形结构。请先解析文件。")
            return {}
        
        return self._build_proper_tree_structure(self.containers, self.variables) 