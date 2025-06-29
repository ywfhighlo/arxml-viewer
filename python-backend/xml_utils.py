# xml_utils.py
"""
通用XML解析与树结构工具，供cli_wrapper.py和simple_cli.py复用
"""
import xml.etree.ElementTree as ET
from typing import Dict, Any

def build_xml_tree(element, file_type: str, path="") -> Dict[str, Any]:
    current_path = f"{path}/{element.tag}" if path else element.tag
    element_id = f"{file_type}_{abs(hash(current_path))}"
    node_type = determine_node_type(element.tag, file_type)
    node = {
        "id": element_id,
        "name": get_display_name(element),
        "type": node_type,
        "path": current_path,
        "attributes": dict(element.attrib) if element.attrib else {},
        "value": element.text.strip() if element.text and element.text.strip() else "",
        "children": [],
        "metadata": {
            "description": f"{file_type.upper()}元素: {element.tag}",
            "tooltip": create_xml_tooltip(element),
            "icon": get_icon_for_type(node_type),
            "isExpandable": len(list(element)) > 0,
            "hasChildren": len(list(element)) > 0
        }
    }
    if file_type == "arxml":
        short_name = extract_short_name(element)
        if short_name:
            node["shortName"] = short_name
    for child in element:
        child_node = build_xml_tree(child, file_type, current_path)
        node["children"].append(child_node)
    return node

def determine_node_type(tag: str, file_type: str) -> str:
    tag_upper = tag.upper()
    if file_type == "arxml":
        if tag_upper in ["AUTOSAR"]:
            return "root"
        elif "PACKAGE" in tag_upper:
            return "package"
        elif any(x in tag_upper for x in ["CONTAINER", "MODULE", "DEF"]):
            return "container"
        elif any(x in tag_upper for x in ["PARAM", "VARIABLE"]):
            return "variable"
        elif "INSTANCE" in tag_upper:
            return "instance"
    elif file_type == "xdm":
        if any(x in tag_upper for x in ["MODEL", "ROOT"]):
            return "root"
        elif "CONTAINER" in tag_upper:
            return "container"
        elif any(x in tag_upper for x in ["VARIABLE", "PARAMETER"]):
            return "variable"
        elif "INSTANCE" in tag_upper:
            return "instance"
    return "element"

def get_display_name(element) -> str:
    short_name = extract_short_name(element)
    if short_name:
        return short_name
    return element.tag

def extract_short_name(element) -> str:
    for child in element:
        if child.tag.upper() in ["SHORT-NAME", "SHORT_NAME", "SHORTNAME"]:
            return child.text.strip() if child.text else ""
    return ""

def get_icon_for_type(node_type: str) -> str:
    icon_map = {
        "root": "file-code",
        "package": "package",
        "container": "folder",
        "variable": "symbol-variable",
        "instance": "symbol-class",
        "element": "symbol-field"
    }
    return icon_map.get(node_type, "circle-outline")

def create_xml_tooltip(element) -> str:
    tooltip = f"标签: {element.tag}"
    short_name = extract_short_name(element)
    if short_name:
        tooltip += f"\n短名称: {short_name}"
    if element.attrib:
        tooltip += f"\n属性: {element.attrib}"
    if element.text and element.text.strip():
        text = element.text.strip()
        if len(text) > 50:
            text = text[:50] + "..."
        tooltip += f"\n内容: {text}"
    return tooltip
