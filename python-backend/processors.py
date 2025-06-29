# processors.py
"""
VSCodeBackend 及相关解析/业务逻辑
"""
from pathlib import Path
from typing import Dict, Any
import xml_utils
import os
import logging
import xml.etree.ElementTree as ET
import sys

# MockARXMLProcessor, MockXDMProcessor, ARXMLProcessor, XDMProcessor的导入与定义（可从cli_wrapper.py复制）...

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import xml_utils
from arxml_tree_builder import ARXMLTreeBuilder
from lib.xdm_processor import XDMProcessor

class VSCodeBackend:
    """VSCode插件后端处理器"""
    
    def __init__(self, workspace: Path = None):
        self.workspace = workspace or Path.cwd()
        self.arxml_builder = ARXMLTreeBuilder()

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """解析文件并返回结构化数据"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                return self._error_response(f"文件不存在: {file_path}")
            
            # 根据文件扩展名确定文件类型
            file_type = self._detect_file_type(file_path)
            
            if file_type == "arxml":
                return self._parse_arxml_file(str(file_path), "arxml")
            elif file_type == "bmd":
                return self._parse_arxml_file(str(file_path), "bmd")  # BMD使用ARXML解析器，但保持BMD类型
            elif file_type == "xdm":
                return self._parse_xdm_file(str(file_path))
            else:
                return self._parse_xml_file(str(file_path), "xml")
                
        except Exception as e:
            return self._error_response(f"解析文件时发生错误: {str(e)}")
    
    def _parse_arxml_file(self, file_path: str, file_type: str = "arxml") -> Dict[str, Any]:
        """解析ARXML文件，使用DaVinci风格树构建器"""
        try:
            # 文件存在性检查
            if not os.path.exists(file_path):
                return self._error_response(f"文件不存在: {file_path}")
            
            # XML格式检查
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
            except ET.ParseError as e:
                return self._error_response(f"XML格式错误: {str(e)}")
            
            # ARXML特定检查
            if not self._is_valid_arxml(root):
                return self._error_response("不是有效的ARXML文件")
            
            # 使用DaVinci风格树构建器
            tree_structure = self.arxml_builder.build_davinci_tree(root)
            
            # 确保数据格式符合前端TreeNode接口
            tree_structure = self._normalize_tree_structure(tree_structure)
            
            # 统计信息计算
            total_elements = len(list(root.iter()))
            containers_count = self._count_containers(tree_structure)
            parameters_count = self._count_parameters(tree_structure)
            
            return {
                "success": True,
                "fileType": file_type,
                "filePath": file_path,
                "treeStructure": tree_structure,
                "metadata": {
                    "rootTag": root.tag,
                    "totalElements": total_elements,
                    "totalContainers": containers_count,
                    "totalParameters": parameters_count,
                    "parseTime": 0.1
                }
            }
        except Exception as e:
            return self._error_response(f"ARXML文件解析失败: {str(e)}")

    def _parse_xdm_file(self, file_path: str) -> Dict[str, Any]:
        """解析XDM文件并构建前端兼容的树结构"""
        try:
            processor = XDMProcessor(file_path)
            # The XDMProcessor constructor already calls parse_xdm_file
            
            tree_structure = self._build_xdm_tree(processor.containers, processor.variables)
            
            return {
                "success": True,
                "fileType": "xdm",
                "filePath": file_path,
                "treeStructure": tree_structure,
                "metadata": {
                    "totalContainers": len(processor.containers),
                    "totalVariables": len(processor.variables),
                },
                "containers": processor.containers,
                "variables": processor.variables
            }
        except Exception as e:
            return self._error_response(f"XDM文件解析失败: {str(e)}")

    def _build_xdm_tree(self, containers_map: dict, variables_map: dict) -> dict:
        """从XDM processor的扁平数据构建层级树 (分离参数)"""
        root_node = {
            'id': 'root',
            'name': 'root',
            'type': 'root',
            'path': '',
            'children': [],
            'parameters': [],
            'metadata': {'isExpandable': True, 'hasChildren': True}
        }
        
        nodes = {'': root_node}

        # 先创建所有容器节点
        for path, container_data in sorted(containers_map.items()):
            parts = path.split('/')
            name = parts[-1]

            new_node = {
                'id': path,
                'name': container_data.get('name', name),
                'type': 'container',
                'path': path,
                'children': [],
                'parameters': [], # 新增
                'metadata': {
                    'description': container_data.get('description', ''),
                    'isExpandable': True,
                    'hasChildren': False 
                }
            }
            nodes[path] = new_node

        # 链接父子关系并添加变量到parameters列表
        for path, node in sorted(nodes.items()):
            if path == '': continue

            # 链接到父节点
            parts = path.split('/')
            parent_path = '/'.join(parts[:-1])
            if parent_path in nodes:
                nodes[parent_path]['children'].append(node)
                has_children = True
            else:
                root_node['children'].append(node)
                has_children = True

            # 将此容器的变量添加到parameters列表
            container_data = containers_map[path]
            container_vars = container_data.get('variables', [])
            if isinstance(container_vars, list):
                for var_name in container_vars:
                    if var_name in variables_map:
                        var_data = variables_map[var_name]
                        # 创建参数字典
                        param_node = {
                            'id': f"{path}/{var_name}",
                            'name': var_name,
                            'type': 'parameter', # 保持一致性
                            'value': var_data.get('current_value', var_data.get('default', '')),
                            'description': var_data.get('description', ''),
                            'metadata': {
                                'type': var_data.get('type', 'STRING'),
                                'default': var_data.get('default', ''),
                            }
                        }
                        node['parameters'].append(param_node)
            
            has_children = bool(node['children'] or node['parameters'])
            nodes[parent_path]['metadata']['hasChildren'] = has_children
            node['metadata']['hasChildren'] = has_children
            node['metadata']['isExpandable'] = has_children
                
        return root_node

    def _normalize_tree_structure(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """(恢复)标准化树结构，确保与前端接口匹配"""
        if not node:
            return None
            
        normalized = {
            "id": node.get("id", ""),
            "name": node.get("name", "Unnamed"),
            "type": self._normalize_node_type(node.get("type", "container")),
            "path": node.get("path", ""),
            "children": [],
            "parameters": self._normalize_parameters(node.get("parameters", []))
        }
        
        # 添加可选的元数据字段
        if "metadata" in node:
            normalized["metadata"] = node["metadata"]
        if "value" in node:
            normalized["value"] = node["value"]
        if "shortName" in node:
            normalized["shortName"] = node["shortName"]
        if "attributes" in node:
            normalized["attributes"] = node["attributes"]
        
        # 递归处理子节点
        for child in node.get("children", []):
            child_normalized = self._normalize_tree_structure(child)
            if child_normalized:
                normalized["children"].append(child_normalized)
        
        return normalized

    def _normalize_node_type(self, node_type: str) -> str:
        """标准化节点类型，确保与前端一致"""
        type_mapping = {
            "folder": "container",
            "leaf": "container",
            "module": "container",
            "package": "container",
            "root": "root",
            "parameter": "parameter",
            "variable": "parameter"
        }
        return type_mapping.get(node_type, "container")

    def _is_container_type(self, node_type: str) -> bool:
        """判断是否为容器类型节点"""
        container_types = {"container", "root", "package", "module"}
        return node_type in container_types

    def _normalize_parameters(self, parameters: list) -> list:
        """标准化参数列表"""
        normalized_params = []
        for param in parameters:
            if isinstance(param, dict):
                normalized_param = {
                    "id": param.get("id", ""),
                    "name": param.get("name", ""),
                    "type": param.get("type", "string"),
                    "value": param.get("value", ""),
                    "description": param.get("description", "")
                }
                # 保留其他字段
                for key in ["shortName", "attributes", "constraints", "metadata"]:
                    if key in param:
                        normalized_param[key] = param[key]
                normalized_params.append(normalized_param)
        return normalized_params

    def _is_valid_arxml(self, root: ET.Element) -> bool:
        """检查是否为有效的ARXML文件"""
        # 检查根元素和命名空间
        return (
            root.tag.endswith('AUTOSAR') or 
            'autosar' in root.tag.lower() or
            any('autosar' in attr.lower() for attr in root.attrib.values()) or
            # 检查是否包含AUTOSAR相关的命名空间
            any('autosar' in str(attr).lower() for attr in root.attrib.keys())
        )

    def _parse_xml_file(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """解析XML文件"""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            # 使用xml_utils中的build_xml_tree函数
            tree_structure = xml_utils.build_xml_tree(root, file_type)
            
            # 标准化树结构
            tree_structure = self._normalize_tree_structure(tree_structure)
            
            # 统计容器和参数数量
            total_elements = len(list(root.iter()))
            containers_count = self._count_containers(tree_structure)
            parameters_count = self._count_parameters(tree_structure)
            
            return {
                "success": True,
                "fileType": file_type,
                "filePath": file_path,
                "treeStructure": tree_structure,
                "metadata": {
                    "rootTag": root.tag,
                    "totalElements": total_elements,
                    "totalContainers": containers_count,
                    "totalParameters": parameters_count,
                    "parseTime": 0.1
                }
            }
        except ET.ParseError as e:
            return self._error_response(f"XML解析错误: {str(e)}")
        except Exception as e:
            return self._error_response(f"文件解析失败: {str(e)}")

    def _count_containers(self, node: Dict[str, Any]) -> int:
        """递归统计容器数量"""
        count = 1 if node.get('type') in ['container', 'package', 'module', 'root'] else 0
        
        children = node.get('children', [])
        for child in children:
            count += self._count_containers(child)
        
        return count
    
    def _count_parameters(self, node: Dict[str, Any]) -> int:
        """递归统计参数数量"""
        # 统计当前节点的参数
        count = len(node.get('parameters', []))
        
        # 递归统计子节点的参数
        children = node.get('children', [])
        for child in children:
            count += self._count_parameters(child)
        
        return count

    def _count_nodes_by_type(self, node: Dict[str, Any], target_types: list) -> int:
        """递归统计指定类型的节点数量"""
        count = 0
        if node.get('type') in target_types:
            count += 1
        
        children = node.get('children', [])
        for child in children:
            count += self._count_nodes_by_type(child, target_types)
        
        return count

    def get_node_details(self, node_path: str, file_path: str) -> Dict[str, Any]:
        """获取节点详细信息"""
        try:
            # 重新解析文件并找到指定节点
            result = self.parse_file(file_path)
            if not result["success"]:
                return result
            
            # 在树结构中查找节点
            node = self._find_node_by_path(result["treeStructure"], node_path)
            if not node:
                return self._error_response(f"未找到节点: {node_path}")
            
            return {
                "success": True,
                "nodeDetails": node,
                "parameters": node.get("parameters", [])
            }
            
        except Exception as e:
            return self._error_response(f"获取节点详情失败: {str(e)}")

    def _find_node_by_path(self, root_node: Dict[str, Any], target_path: str) -> Dict[str, Any]:
        """根据路径查找节点"""
        if root_node.get("path") == target_path:
            return root_node
        
        for child in root_node.get("children", []):
            result = self._find_node_by_path(child, target_path)
            if result:
                return result
        
        return None
    
    def _detect_file_type(self, file_path: Path) -> str:
        """检测文件类型"""
        suffix = file_path.suffix.lower()
        if suffix == ".arxml":
            return "arxml"
        elif suffix == ".bmd":
            return "bmd"
        elif suffix == ".xdm":
            return "xdm"
        else:
            return "xml"
    
    def _error_response(self, error_message: str) -> Dict[str, Any]:
        """生成标准化错误响应"""
        return {
            "success": False,
            "error": error_message,
            "fileType": "unknown",
            "filePath": "",
            "treeStructure": {
                "id": "error",
                "name": "Error",
                "type": "error",
                "path": "",
                "children": [],
                "parameters": []
            },
            "metadata": {
                "totalContainers": 0,
                "totalParameters": 0,
                "totalElements": 0
            }
        }

    def process_arxml(self, file_path: Path) -> None:
        """处理 ARXML 文件的逻辑"""
        # 处理 ARXML 文件的代码...
        pass

    def process_xdm(self, file_path: Path) -> None:
        """处理 XDM 文件的逻辑"""
        # 处理 XDM 文件的代码...
        pass

    # 其他方法...