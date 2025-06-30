# Office & Docs Converter - VSCode 扩展详细设计文档

## 1. 🎯 项目概述

**项目名称**: Office & Docs Converter

**核心理念**: 将一系列强大但零散的文档处理工具 (位于 `/tools` 目录) 整合到一个统一、高效、交互友好的 VS Code 扩展中。它不仅仅是一个 Markdown 转换器，而是一个**全面的、双向的文档与图表格式转换中心**。

**核心价值**: 为开发者、技术作者和内容创作者提供一个在 VS Code 内部完成多种文件格式相互转换的"一站式"解决方案，极大提升工作流效率，消除在不同专业工具间切换的成本。

## 2. ✨ 核心功能

功能将通过右键上下文菜单触发，根据所选文件或目录的类型，动态显示可用的转换选项。

### A. 对于 Markdown 文件 (`.md`)
- **目标**: 将内容发布为标准文档。
- **右键菜单项**:
    - `Convert to DOCX`
    - `Convert to PDF`
    - `Convert to HTML`

### B. 对于 Office 和 PDF 文件 (`.docx`, `.xlsx`, `.pdf`)
- **目标**: 将复杂的格式化文档反向工程为纯文本的 Markdown，便于版本控制和再编辑。
- **右键菜单项**:
    - `Convert to Markdown`

### C. 对于图表文件 (`.svg`, `.drawio`)
- **目标**: 将矢量图或可编辑图表转换为通用的位图格式，便于嵌入文档或网页。
- **右键菜单项**:
    - `Convert to PNG`

### D. 通用功能
- **批量转换**: 在目录上右键，将对目录下所有符合条件的源文件进行批量转换。
- **用户配置**: 允许用户在 `settings.json` 中自定义输出目录、转换模板等。
- **状态与通知**: 提供清晰的进度反馈和操作结果通知。

## 3. 🏗️ 技术架构

整体采用前后端分离的松耦合架构。

### 前端 (TypeScript - VSCode Extension)

- **`package.json` (插件清单)**
    - **`contributes.menus`**: 将使用更丰富的 `when` 条件句来控制菜单的显示时机：
        - `when: "resourceLangId == markdown"` (用于 .md 文件)
        - `when: "resourceExtname == .docx || resourceExtname == .pdf || resourceExtname == .xlsx"` (用于 Office/PDF 文件)
        - `when: "resourceExtname == .svg || resourceExtname == .drawio"` (用于图表文件)
        - `when: "resourceIsFolder"` (用于目录批量转换)
    - **`contributes.commands`**: 定义所有转换命令。

- **`extension.ts` (主入口)**: 负责激活插件并根据 `when` 条件注册所有命令。

- **`commandHandler.ts` (命令处理器)**: 包含每个命令的实现，负责解析输入、调用后端服务、并处理返回结果。

- **`pythonService.ts` (Python 后端服务)**: 封装 `child_process.spawn`，负责异步调用 Python 后端命令行接口，传递参数并监听返回的 JSON 结果。

### 后端 (Python)

采用**面向对象的、可扩展的架构**，将不同的转换逻辑封装在独立的类中。
**核心原则：所有转换逻辑必须来自 `/tools` 目录下的成熟脚本，本项目旨在对其进行重构和整合，而非重新创造。**

- **`cli.py` (命令行接口/工厂)**
    - 作为前端调用的统一入口。
    - 它的核心职责是**根据命令行参数，选择并实例化正确的转换器类**（工厂模式）。
    - 解析参数后，调用所选转换器实例的 `convert()` 方法。
    - 将转换结果以 **JSON 格式**打印到标准输出。

- **`converters/` (转换器包)**
    - **`base_converter.py`**: 定义一个抽象基类 `BaseConverter`，包含一个抽象方法 `convert()`，确保所有转换器都遵循统一的接口。
    - **`md_to_office.py`**: 实现 `MdToOfficeConverter(BaseConverter)` 类。**逻辑来源: `tools/md_to_docx.py` 等。**
    - **`office_to_md.py`**: 实现 `OfficeToMdConverter(BaseConverter)` 类。**逻辑来源: `tools/office_to_md.py`。**
    - **`diagram_to_png.py`**: 实现 `DiagramToPngConverter(BaseConverter)` 类。**逻辑来源: `tools/convert_figures.py`。**
    - *未来可以轻松添加新的 `Converter` 类来扩展功能。*

- **`requirements.txt`**: 包含所有 Python 依赖。

## 4. 📁 建议项目结构

```
office-docs-converter/
├── src/                      # 前端 TypeScript 源代码
│   ├── extension.ts
│   └── ...
├── backend/                  # 后端 Python 代码
│   ├── cli.py                # 命令行入口 / 工厂
│   ├── requirements.txt      # Python 依赖
│   └── converters/           # 转换器包
│       ├── __init__.py
│       ├── base_converter.py
│       ├── md_to_office.py
│       ├── office_to_md.py
│       └── diagram_to_png.py
├── package.json
└── ...
```

## 5. 🚀 开发路线图 (Milestones)

1.  **阶段一: 环境与框架搭建**
    -   [ ] 初始化项目，搭建前端和后端的基本文件结构。
    -   [ ] 完成 `package.json` 的命令和菜单项定义（包含所有 `when` 条件）。
    -   [ ] 创建 Python 虚拟环境，并定义 `BaseConverter` 抽象类。

2.  **阶段二: 实现 `Markdown -> Office` 转换**
    -   [ ] **实现 `MdToOfficeConverter` 类**，将 `md_to_docx.py` 等工具的逻辑整合进来。
    -   [ ] 在 `cli.py` 中添加对 `MdToOfficeConverter` 的调用逻辑。
    -   [ ] 联通前端，完成 `md` 文件右键菜单的完整功能。

3.  **阶段三: 实现 `Office -> Markdown` 转换**
    -   [ ] **实现 `OfficeToMdConverter` 类**，整合 `office_to_md.py` 的逻辑。
    -   [ ] 在 `cli.py` 中添加相应的调用逻辑。
    -   [ ] 联通前端，完成 Office 文件右键菜单的功能。

4.  **阶段四: 实现图表转换**
    -   [ ] **实现 `DiagramToPngConverter` 类**。
    -   [ ] 在 `cli.py` 中添加相应的调用逻辑。
    -   [ ] 联通前端，完成图表文件右键菜单的功能。

5.  **阶段五: 完善与测试**
    -   [ ] 实现目录批量转换。
    -   [ ] 实现用户自定义配置功能。
    -   [ ] 完善错误处理和用户通知。
    -   [ ] 进行全面的功能测试，确保转换结果与原 `tools` 脚本一致。

6.  **阶段六: 整合与发布**
    -   [ ] **确认所有功能已成功迁移后，删除 `/tools` 目录，使其功成身退。**
    -   [ ] 编写最终的 `README.md`。
    -   [ ] 使用 `vsce` 工具打包 `.vsix` 文件并准备发布。 