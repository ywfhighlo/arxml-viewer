 # ARXML 编辑器前端PB徽章设计

## 1. 概述

本文档旨在为 ARXML 编辑器前端的**参数配置类型**功能，制定清晰的设计规范和实施计划。

- **核心目标**: 根据参数的变体配置数据，在用户界面上展示其配置类型（如 PC, PB, LK）。
- **前提假设**: 后端解析器已按 `AUTOSAR_Variant_Management_Guide.md` 中定义的规范，为每个参数提供了精确的 `configClasses` 数组。该数组完整地保留了 `CONFIG-CLASS` 与 `CONFIG-VARIANT` 的配对关系。

  *示例数据结构:*
```json
"configClasses": [
  { "class": "PRE-COMPILE", "variant": "VARIANT-LINK-TIME" },
  { "class": "PRE-COMPILE", "variant": "VARIANT-POST-BUILD" },
  { "class": "PRE-COMPILE", "variant": "VARIANT-PRE-COMPILE" }
]
```

## 2. 实现阶段

### 阶段一：简单文本显示（当前目标）

在参数名称后附加配置类型文本：

- **显示格式**: `参数名称 [配置类型]`（例如：`WdgMaxTimeout [PB]`）
- **配置类型显示规则**:
  - 根据 `configClasses` 中 `variant` 为 `VARIANT-PRE-COMPILE` 的条目的 `class` 值显示
  - POST-BUILD → "[PB]"
  - PRE-COMPILE → "[PC]"
  - LINK-TIME → "[LK]"
  - 找不到对应条目 → 不显示任何标记
- **实现重点**:
  - 保持现有的两列布局（参数名+值）不变
  - 配置类型作为参数名的一部分显示
  - 使用方括号确保视觉区分

### 阶段二：徽章设计（后续优化）

在验证阶段一数据流通正常后，进行UI美化：

- **徽章样式**: 将方括号文本升级为带样式的徽章
- **位置**: 保持在参数名称后面
- **颜色方案**:
  - PB: 蓝色系
  - PC: 绿色系
  - LK: 橙色系

## 3. 调试支持

为了便于开发和调试：

- **工具提示 (Tooltip)**: 当用户鼠标悬停在参数上时，显示：
  1. 参数的 `description`（描述）
  2. 换行后显示 "Config Classes:"
  3. 完整的 `configClasses` 数组的格式化 JSON
- **控制台日志**: 在更新参数时输出调试信息，包含：
  1. 参数名称
  2. 完整的 configClasses 数组
  3. 最终选择的配置类型

## 4. 验证标准

### 阶段一验证：
1. 确认配置类型正确显示在参数名称后
2. 验证方括号格式统一
3. 确认现有的值列显示不受影响
4. 确认工具提示正确显示完整信息

### 阶段二验证：
1. 确认徽章样式正确应用
2. 验证不同配置类型的颜色区分
3. 确认徽章位置紧跟参数名称
4. 验证长参数名称下的显示效果