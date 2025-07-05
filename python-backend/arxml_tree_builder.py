"""
ARXML树构建器 - 符合DaVinci风格显示需求
仅显示容器层级，参数存储在容器的parameters属性中
"""
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional

class ARXMLTreeBuilder:
    """ARXML树构建器，按照DaVinci风格构建树结构"""
    
    def __init__(self):
        # AUTOSAR容器类型标签 - 只包含真正的容器
        self.container_tags = {
            'ECUC-MODULE-DEF', 'ECUC-PARAM-CONF-CONTAINER-DEF', 
            'BSW-IMPLEMENTATION', 'AR-PACKAGE', 'ELEMENTS'
        }
        
        # 参数类型标签 - 包含所有参数相关的标签
        self.parameter_tags = {
            'ECUC-INTEGER-PARAM-DEF', 'ECUC-FLOAT-PARAM-DEF', 
            'ECUC-STRING-PARAM-DEF', 'ECUC-BOOLEAN-PARAM-DEF',
            'ECUC-ENUMERATION-PARAM-DEF', 'ECUC-REFERENCE-DEF',
            'ECUC-NUMERICAL-PARAM-VALUE', 'ECUC-TEXTUAL-PARAM-VALUE',
            'PARAMETER-VALUES', 'PARAMETERS', 'REFERENCES', 'REFERENCE-VALUES'
        }
        
        # 需要跳过的标签（结构性标签，但不包含参数和引用相关标签）
        self.skip_tags = {
            'DESC', 'L-2', 'RELATED-TRACE-ITEM-REF', 'LOWER-MULTIPLICITY',
            'UPPER-MULTIPLICITY', 'SCOPE', 'ORIGIN', 'POST-BUILD-VARIANT-MULTIPLICITY',
            'POST-BUILD-VARIANT-VALUE', 'REQUIRES-INDEX',
            'MULTIPLICITY-CONFIG-CLASSES', 'SYMBOLIC-NAME-VALUE', 'MAX', 'MIN',
            'CONTAINERS', 'SUB-CONTAINERS'
        }
    
    def build_davinci_tree(self, root_element: ET.Element) -> Dict[str, Any]:
        """构建DaVinci风格的树形结构"""
        # 创建根节点
        tree = {
            "id": "virtual_root",
            "name": "AUTOSAR配置",
            "type": "root",
            "path": "",
            "children": [],
            "parameters": [],
            "metadata": {
                "description": "AUTOSAR配置根节点",
                "tooltip": "包含多个模块的配置",
                "icon": "symbol-namespace",
                "isExpandable": True,
                "hasChildren": False
            }
        }
        
        # 处理所有AR-PACKAGE节点
        for package in root_element.findall('.//{*}AR-PACKAGE'):
            # 获取包名
            short_name = self._extract_short_name(package)
            if not short_name:
                continue
            
            # 创建模块节点
            module_id = f"module_{abs(hash(short_name))}"
            module_node = {
                "id": module_id,
                "name": short_name,
                "type": "container",
                "path": short_name,
                "children": [],
                "parameters": [],
                "metadata": {
                    "description": f"模块: {short_name}",
                    "tooltip": f"模块: {short_name}",
                    "icon": "symbol-module",
                    "isExpandable": True,
                    "hasChildren": False,
                    "originalTag": package.tag
                },
                "shortName": short_name
            }
            
            # 处理模块定义
            for module_def in package.findall('.//{*}ECUC-MODULE-DEF'):
                module_node = self._build_module_def_node(module_def, short_name)
                if module_node:
                    tree["children"].append(module_node)
                    tree["metadata"]["hasChildren"] = True
            
            # 处理模块配置
            for module_conf in package.findall('.//{*}ECUC-MODULE-CONFIGURATION-VALUES'):
                module_node = self._build_container_node(module_conf, short_name)
                if module_node:
                    tree["children"].append(module_node)
                    tree["metadata"]["hasChildren"] = True
        
        return tree
    
    def _build_tree(self, root_element: ET.Element) -> Dict[str, Any]:
        """构建树结构"""
        # 创建虚拟根节点
        tree = {
            "id": "virtual_root",
            "name": "AUTOSAR配置",
            "type": "root",
            "path": "",
            "children": [],
            "parameters": [],
            "metadata": {
                "description": "AUTOSAR配置根节点",
                "tooltip": "包含多个模块的配置",
                "icon": "symbol-namespace",
                "isExpandable": True,
                "hasChildren": False
            }
        }
        
        # 处理所有AR-PACKAGE节点
        for package in root_element.findall('.//{*}AR-PACKAGE'):
            # 获取包名
            short_name = self._extract_short_name(package)
            if not short_name:
                continue
            
            # 创建模块节点
            module_id = f"module_{abs(hash(short_name))}"
            module_node = {
                "id": module_id,
                "name": short_name,
                "type": "container",
                "path": short_name,
                "children": [],
                "parameters": [],
                "metadata": {
                    "description": f"模块: {short_name}",
                    "tooltip": f"模块: {short_name}",
                    "icon": "symbol-module",
                    "isExpandable": True,
                    "hasChildren": False,
                    "originalTag": package.tag
                },
                "shortName": short_name
            }
            
            # 处理模块定义
            for module_def in package.findall('.//{*}ECUC-MODULE-DEF'):
                module_node = self._build_module_def_node(module_def, short_name)
                if module_node:
                    tree["children"].append(module_node)
                    tree["metadata"]["hasChildren"] = True
            
            # 处理模块配置
            for module_conf in package.findall('.//{*}ECUC-MODULE-CONFIGURATION-VALUES'):
                module_node = self._build_container_node(module_conf, short_name)
                if module_node:
                    tree["children"].append(module_node)
                    tree["metadata"]["hasChildren"] = True
        
        return tree
    
    def _build_module_def_node(self, element: ET.Element, path: str) -> Dict[str, Any]:
        """构建模块定义节点"""
        # 获取Short Name
        short_name = self._extract_short_name(element)
        display_name = short_name if short_name else self._get_clean_tag_name(element.tag)
        
        # 构建路径
        current_path = f"{path}/{short_name}" if path else short_name
        element_id = f"module_{abs(hash(current_path))}"
        
        # 创建节点
        node = {
            "id": element_id,
            "name": display_name,
            "type": "module",
            "path": current_path,
            "shortName": short_name,
            "attributes": dict(element.attrib) if element.attrib else {},
            "children": [],
            "parameters": [],
            "metadata": {
                "description": f"模块定义: {display_name}",
                "tooltip": f"模块定义: {display_name}",
                "icon": "symbol-module",
                "isExpandable": True,
                "hasChildren": False,
                "originalTag": element.tag
            }
        }
        
        # 处理容器定义
        containers = element.find('.//{*}CONTAINERS')
        if containers is not None:
            for container_def in containers:
                if self._get_clean_tag_name(container_def.tag) == 'ECUC-PARAM-CONF-CONTAINER-DEF':
                    container_node = self._build_container_def_node(container_def, current_path)
                    if container_node:
                        node["children"].append(container_node)
                        node["metadata"]["hasChildren"] = True
        
        return node
    
    def _build_container_def_node(self, element: ET.Element, path: str) -> Dict[str, Any]:
        """构建容器定义节点"""
        # 获取Short Name
        short_name = self._extract_short_name(element)
        display_name = short_name if short_name else self._get_clean_tag_name(element.tag)
        
        # 构建路径
        current_path = f"{path}/{short_name}" if path else short_name
        element_id = f"container_{abs(hash(current_path))}"
        
        # 创建节点
        node = {
            "id": element_id,
            "name": display_name,
            "type": "container",
            "path": current_path,
            "shortName": short_name,
            "attributes": dict(element.attrib) if element.attrib else {},
            "children": [],
            "parameters": [],
            "metadata": {
                "description": f"容器定义: {display_name}",
                "tooltip": f"容器定义: {display_name}",
                "icon": "database",
                "isExpandable": True,
                "hasChildren": False,
                "originalTag": element.tag
            }
        }
        
        # 处理参数定义
        parameters = element.find('.//{*}PARAMETERS')
        if parameters is not None:
            for param_def in parameters:
                param = self._build_parameter_def_node(param_def)
                if param:
                    node["parameters"].append(param)
                    node["metadata"]["hasParameters"] = True
        
        # 处理引用定义
        references = element.find('.//{*}REFERENCES')
        if references is not None:
            for ref_def in references:
                if 'REFERENCE-DEF' in self._get_clean_tag_name(ref_def.tag):
                    param = self._build_parameter_def_node(ref_def)
                    if param:
                        node["parameters"].append(param)
                        node["metadata"]["hasParameters"] = True
        
        # 处理子容器定义
        sub_containers = element.find('.//{*}SUB-CONTAINERS')
        if sub_containers is not None:
            for container_def in sub_containers:
                if self._get_clean_tag_name(container_def.tag) == 'ECUC-PARAM-CONF-CONTAINER-DEF':
                    container_node = self._build_container_def_node(container_def, current_path)
                    if container_node:
                        node["children"].append(container_node)
                        node["metadata"]["hasChildren"] = True
        
        return node
    
    def _build_parameter_def_node(self, element: ET.Element) -> Optional[Dict[str, Any]]:
        """构建参数定义节点"""
        # 获取Short Name
        short_name = self._extract_short_name(element)
        if not short_name:
            return None
        
        # 获取参数类型
        param_type = self._get_clean_tag_name(element.tag)
        if 'INTEGER' in param_type:
            param_type = 'number'
        elif 'BOOLEAN' in param_type:
            param_type = 'boolean'
        elif 'ENUMERATION' in param_type:
            param_type = 'enum'
        elif 'REFERENCE' in param_type:
            param_type = 'reference'
        else:
            param_type = 'string'
        
        # 获取参数描述
        desc_elem = element.find('.//{*}L-2')
        description = desc_elem.text if desc_elem is not None and desc_elem.text else ''
        
        # 获取配置类别
        config_classes = self._extract_value_config_classes(element)
        
        # 生成参数ID
        param_id = f"param_{abs(hash(short_name))}"
        
        # 构建参数对象
        return {
            "id": param_id,
            "name": short_name,
            "type": param_type,
            "value": "",  # 参数定义没有实际值
            "description": description,
            "metadata": {
                "originalTag": element.tag,
                "definitionRef": "",  # 参数定义没有引用
                "tooltip": f"参数定义: {short_name}",
                "description": f"{param_type} - {short_name}",
                "configClasses": config_classes
            }
        }
    
    def _extract_value_config_classes(self, element: ET.Element) -> List[Dict[str, str]]:
        """提取参数的配置类别和变体对"""
        config_pairs = []
        vcc_element = element.find('.//{*}VALUE-CONFIG-CLASSES')
        if vcc_element is not None:
            for vcc_child in vcc_element.findall('.//{*}ECUC-VALUE-CONFIGURATION-CLASS'):
                class_elem = vcc_child.find('.//{*}CONFIG-CLASS')
                variant_elem = vcc_child.find('.//{*}CONFIG-VARIANT')

                config_class = class_elem.text.strip() if class_elem is not None and class_elem.text else None
                config_variant = variant_elem.text.strip() if variant_elem is not None and variant_elem.text else None

                if config_class and config_variant:
                    config_pairs.append({"class": config_class, "variant": config_variant})
        return config_pairs
    
    def _build_container_node(self, element: ET.Element, path: str) -> Dict[str, Any]:
        """构建容器节点"""
        # 获取Short Name
        short_name = self._extract_short_name(element)
        display_name = short_name if short_name else self._get_clean_tag_name(element.tag)
        
        # 构建路径
        current_path = f"{path}/{short_name}" if path else short_name
        element_id = f"arxml_{abs(hash(current_path))}"
        
        # 创建节点
        node = {
            "id": element_id,
            "name": display_name,
            "type": self._determine_node_type(element.tag),
            "path": current_path,
            "shortName": short_name,
            "attributes": dict(element.attrib) if element.attrib else {},
            "children": [],
            "parameters": [],  # 存储参数
            "metadata": {
                "description": self._create_description(element, display_name),
                "tooltip": self._create_tooltip(element, display_name),
                "icon": self._get_icon_for_container(element.tag),
                "isExpandable": True,
                "hasChildren": False,
                "originalTag": element.tag
            }
        }
        
        # 处理子元素
        for child in element:
            child_tag = self._get_clean_tag_name(child.tag)
            
            # 处理参数值
            if child_tag in {'ECUC-NUMERICAL-PARAM-VALUE', 'ECUC-TEXTUAL-PARAM-VALUE', 'ECUC-REFERENCE-VALUE'}:
                param = self._build_parameter_value(child)
                if param:
                    node["parameters"].append(param)
            
            # 处理子容器
            elif self._is_container(child):
                child_node = self._build_container_node(child, current_path)
                if child_node:
                    node["children"].append(child_node)
                    node["metadata"]["hasChildren"] = True
            
            # 处理参数容器
            elif child_tag == 'PARAMETER-VALUES':
                for param_child in child:
                    param = self._build_parameter_value(param_child)
                    if param:
                        node["parameters"].append(param)
            
            # 处理引用值容器
            elif child_tag == 'REFERENCE-VALUES':
                for ref_child in child:
                    ref_param = self._build_parameter_value(ref_child)
                    if ref_param:
                        node["parameters"].append(ref_param)
        
        # 递归处理子容器
        for container_tag in ['CONTAINERS', 'SUB-CONTAINERS', 'ELEMENTS']:
            container_elem = element.find(f'.//{container_tag}')
            if container_elem is not None:
                for child in container_elem:
                    if self._is_container(child):
                        child_node = self._build_container_node(child, current_path)
                        if child_node:
                            node["children"].append(child_node)
                            node["metadata"]["hasChildren"] = True
        
        # 如果有参数，设置 hasParameters 标志
        if node["parameters"]:
            node["metadata"]["hasParameters"] = True
        
        # 如果有子容器，设置 hasChildren 标志
        if node["children"]:
            node["metadata"]["hasChildren"] = True
        
        return node
    
    def _build_parameter(self, element: ET.Element) -> Dict[str, Any]:
        """构建参数对象"""
        short_name = self._extract_short_name(element)
        display_name = short_name if short_name else self._get_clean_tag_name(element.tag)
        
        param = {
            "id": f"param_{abs(hash(element.tag + str(element.attrib)))}",
            "name": display_name,
            "type": self._get_parameter_type(element.tag),
            "shortName": short_name,
            "attributes": dict(element.attrib) if element.attrib else {},
            "value": self._extract_default_value(element),
            "description": self._extract_description(element),
            "constraints": self._extract_constraints(element),
            "metadata": {
                "originalTag": element.tag,
                "tooltip": self._create_parameter_tooltip(element, display_name)
            }
        }
        
        return param
    
    def _is_container(self, element: ET.Element) -> bool:
        """判断元素是否为容器"""
        tag = self._get_clean_tag_name(element.tag)
        return tag in {
            'AR-PACKAGE',
            'ECUC-MODULE-CONFIGURATION-VALUES',
            'ECUC-CONTAINER-VALUE',
            'ELEMENTS',
            'CONTAINERS',
            'SUB-CONTAINERS'
        } or (
            tag not in self.skip_tags and
            any(child.tag.endswith(('CONTAINER-VALUE', 'CONTAINERS', 'SUB-CONTAINERS', 'ELEMENTS'))
                for child in element)
        )
    
    def _get_clean_tag_name(self, tag: str) -> str:
        """清理标签名称"""
        # 移除命名空间
        if '}' in tag:
            tag = tag.split('}')[-1]
        return tag
    
    def _extract_short_name(self, element: ET.Element) -> Optional[str]:
        """提取SHORT-NAME"""
        for child in element:
            child_tag = self._get_clean_tag_name(child.tag)
            if child_tag in ['SHORT-NAME', 'SHORT_NAME', 'SHORTNAME']:
                return child.text.strip() if child.text else None
        return None
    
    def _extract_description(self, element: ET.Element) -> str:
        """提取描述信息"""
        for child in element:
            if self._get_clean_tag_name(child.tag) == 'DESC':
                for desc_child in child:
                    if self._get_clean_tag_name(desc_child.tag) == 'L-2':
                        return desc_child.text.strip() if desc_child.text else ""
        return ""
    
    def _extract_default_value(self, element: ET.Element) -> str:
        """提取默认值"""
        for child in element:
            child_tag = self._get_clean_tag_name(child.tag)
            if child_tag in ['DEFAULT-VALUE', 'VALUE']:
                return child.text.strip() if child.text else ""
        return ""
    
    def _extract_constraints(self, element: ET.Element) -> Dict[str, Any]:
        """提取约束信息"""
        constraints = {}
        for child in element:
            child_tag = self._get_clean_tag_name(child.tag)
            if child_tag == 'MIN':
                constraints['min'] = child.text.strip() if child.text else None
            elif child_tag == 'MAX':
                constraints['max'] = child.text.strip() if child.text else None
            elif child_tag == 'LOWER-MULTIPLICITY':
                constraints['lowerMultiplicity'] = child.text.strip() if child.text else None
            elif child_tag == 'UPPER-MULTIPLICITY':
                constraints['upperMultiplicity'] = child.text.strip() if child.text else None
        return constraints
    
    def _determine_node_type(self, tag: str) -> str:
        """确定节点类型"""
        clean_tag = self._get_clean_tag_name(tag)
        if clean_tag == 'AUTOSAR':
            return 'root'
        elif 'PACKAGE' in clean_tag:
            return 'package'
        elif 'MODULE' in clean_tag:
            return 'module'
        elif 'CONTAINER' in clean_tag:
            return 'container'
        elif clean_tag in ['CONTAINERS', 'SUB-CONTAINERS']:
            return 'container_group'
        elif clean_tag == 'ELEMENTS':
            return 'elements'
        else:
            return 'container'
    
    def _get_parameter_type(self, tag: str) -> str:
        """获取参数类型"""
        clean_tag = self._get_clean_tag_name(tag)
        if 'INTEGER' in clean_tag:
            return 'integer'
        elif 'FLOAT' in clean_tag:
            return 'float'
        elif 'STRING' in clean_tag:
            return 'string'
        elif 'BOOLEAN' in clean_tag:
            return 'boolean'
        elif 'ENUMERATION' in clean_tag:
            return 'enumeration'
        elif 'REFERENCE' in clean_tag:
            return 'reference'
        else:
            return 'unknown'
    
    def _get_icon_for_container(self, tag: str) -> str:
        """获取容器的图标"""
        clean_tag = self._get_clean_tag_name(tag)
        
        # 模块图标
        if clean_tag in {'AR-PACKAGE', 'ECUC-MODULE-CONFIGURATION-VALUES'}:
            return 'symbol-module'
        
        # 容器图标
        if clean_tag in {'ECUC-CONTAINER-VALUE', 'CONTAINERS', 'SUB-CONTAINERS', 'ELEMENTS'}:
            return 'database'
        
        # 参数图标
        if clean_tag in {'ECUC-NUMERICAL-PARAM-VALUE', 'ECUC-TEXTUAL-PARAM-VALUE'}:
            return 'symbol-parameter'
        
        # 默认图标
        return 'database'
    
    def _create_tooltip(self, element: ET.Element, display_name: str) -> str:
        """创建工具提示"""
        # 获取元素类型
        element_type = self._determine_node_type(element.tag)
        
        # 获取定义引用
        definition_ref = None
        for child in element:
            if self._get_clean_tag_name(child.tag) == 'DEFINITION-REF':
                definition_ref = child.text.strip() if child.text else None
                break
        
        # 构建工具提示
        tooltip = []
        
        # 添加类型信息
        if element_type == 'module':
            tooltip.append(f"模块: {display_name}")
        elif element_type == 'container':
            tooltip.append(f"容器: {display_name}")
        elif element_type == 'parameter':
            tooltip.append(f"参数: {display_name}")
        
        # 添加定义引用
        if definition_ref:
            tooltip.append(f"定义: {definition_ref}")
        
        # 添加参数数量
        param_count = len([child for child in element.findall('.//*') if self._get_clean_tag_name(child.tag) in {'ECUC-NUMERICAL-PARAM-VALUE', 'ECUC-TEXTUAL-PARAM-VALUE'}])
        if param_count > 0:
            tooltip.append(f"参数数量: {param_count}")
        
        # 添加子容器数量
        container_count = len([child for child in element.findall('.//*') if self._is_container(child)])
        if container_count > 0:
            tooltip.append(f"子容器数量: {container_count}")
        
        return "\n".join(tooltip)
    
    def _create_parameter_tooltip(self, element: ET.Element, display_name: str) -> str:
        """创建参数工具提示"""
        tooltip = f"参数: {display_name}"
        param_type = self._get_parameter_type(element.tag)
        tooltip += f"\n类型: {param_type}"
        
        description = self._extract_description(element)
        if description:
            tooltip += f"\n描述: {description[:100]}..."
        
        return tooltip
    
    def _build_parameter_value(self, element: ET.Element) -> Optional[Dict[str, Any]]:
        """构建参数值对象"""
        try:
            # 获取参数定义引用
            definition_ref = None
            param_name = None
            param_value = None
            param_type = None
            
            # 获取参数类型
            element_tag = self._get_clean_tag_name(element.tag)
            if element_tag == 'ECUC-NUMERICAL-PARAM-VALUE':
                param_type = 'number'
            elif element_tag == 'ECUC-TEXTUAL-PARAM-VALUE':
                param_type = 'string'
            elif element_tag == 'ECUC-REFERENCE-VALUE':
                param_type = 'reference'
            else:
                return None
            
            # 获取参数定义和值
            for child in element:
                child_tag = self._get_clean_tag_name(child.tag)
                if child_tag == 'DEFINITION-REF':
                    definition_ref = child.text.strip() if child.text else None
                    # 从定义引用中提取参数名
                    if definition_ref:
                        param_name = definition_ref.split('/')[-1]
                elif child_tag == 'VALUE':
                    param_value = child.text.strip() if child.text else None
                elif child_tag == 'VALUE-REF' and param_type == 'reference':
                    # 对于引用类型，VALUE-REF包含引用的目标
                    param_value = child.text.strip() if child.text else None
            
            # 如果没有找到参数名或值，返回None
            if not param_name or param_value is None:
                return None
            
            # 如果是数值类型，尝试转换为布尔值
            if param_type == 'number':
                if 'BOOLEAN' in definition_ref:
                    param_type = 'boolean'
                    param_value = 'true' if param_value == '1' else 'false'
                else:
                    try:
                        param_value = str(int(param_value))  # 确保是整数
                    except ValueError:
                        try:
                            param_value = str(float(param_value))  # 如果不是整数，尝试浮点数
                        except ValueError:
                            param_type = 'string'  # 如果都不是，当作字符串处理
            
            # 生成参数ID
            param_id = f"param_{abs(hash(param_name + str(param_value)))}"
            
            # 获取参数描述
            param_description = self._get_param_description(definition_ref)
            
            # 构建参数对象
            return {
                "id": param_id,
                "name": param_name,
                "value": param_value,
                "type": param_type,
                "metadata": {
                    "originalTag": element.tag,
                    "definitionRef": definition_ref,
                    "tooltip": f"参数: {param_name} = {param_value}",
                    "description": param_description
                }
            }
        except Exception as e:
            print(f"构建参数值对象失败: {e}")
            return None

    def _get_param_description(self, definition_ref: str) -> str:
        """获取参数描述"""
        if not definition_ref:
            return ""
        
        # 从定义引用中提取参数类型
        parts = definition_ref.split('/')
        if len(parts) < 2:
            return ""
        
        param_type = parts[-2]  # 倒数第二个部分通常是容器名
        param_name = parts[-1]  # 最后一个部分是参数名
        
        return f"{param_type} - {param_name}"

    def _create_description(self, element: ET.Element, display_name: str) -> str:
        """创建节点描述"""
        # 获取元素类型
        element_type = self._determine_node_type(element.tag)
        
        # 根据类型生成描述
        if element_type == 'module':
            return f"模块: {display_name}"
        elif element_type == 'container':
            return f"容器: {display_name}"
        elif element_type == 'parameter':
            return f"参数: {display_name}"
        else:
            return display_name 