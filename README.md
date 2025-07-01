# Markdown Docs Converter

> A powerful VS Code extension to convert files between Markdown, Office formats (DOCX), PDF, and HTML right from the context menu.

Created with ❤️ by **余文锋**

## 🎯 功能特性

### Markdown 转换
- **Markdown → DOCX**: 将 `.md` 文件转换为 Word 文档
- **Markdown → PDF**: 将 `.md` 文件转换为 PDF 文档  
- **Markdown → HTML**: 将 `.md` 文件转换为 HTML 网页

### Office 文档转换
- **DOCX → Markdown**: 将 Word 文档转换为 `.md` 文件
- **XLSX → Markdown**: 将 Excel 表格转换为 `.md` 文件
- **PDF → Markdown**: 将 PDF 文档转换为 `.md` 文件

### 图表转换
- **SVG → PNG**: 将矢量图转换为位图
- **Draw.io → PNG**: 将 Draw.io 图表转换为 PNG 图片

## 🚀 使用方法

### 基础转换
1. 在 VS Code 资源管理器中右键点击文件或文件夹
2. 在上下文菜单中选择相应的转换选项
3. 转换完成后会在配置的输出目录中生成文件

### 模板设置 🆕
1. 右键点击 Markdown 文件或文件夹，选择 **"Template Settings..."**
2. 系统会打开 VS Code 设置页面的模板配置区域
3. 在设置页面中可以配置：
   - **Enable template usage**: 启用/禁用模板功能
   - **Template path**: 选择自定义 DOCX 模板文件路径
   - **Project name**: 项目名称
   - **Author name**: 作者姓名
   - **Email/Mobile phone**: 联系信息
4. 配置保存后，所有 **"Convert to DOCX"** 操作都会自动使用这些设置

## ⚙️ 配置选项

您可以在 VS Code 的 `设置(Settings)` 中搜索 `markdown-docs-converter` 来找到所有配置项。

- **`markdown-docs-converter.outputDirectory`**: 所有转换后文件的输出目录。
  - *默认值*: `./converted_markdown_files`

- **`markdown-docs-converter.pythonPath`**: Python 解释器的路径或命令。
  - *默认值*: 在 Windows 上为 `python`，在 macOS/Linux 上为 `python3`。如果您的 Python 安装在非标准位置，请在此处指定完整路径。

### 模板配置 🆕
- **`markdown-docs-converter.useTemplate`**: 是否为 `Markdown → DOCX` 的转换启用模板功能。
- **`markdown-docs-converter.templatePath`**: 自定义 `.docx` 模板文件的完整路径。如果留空，将使用插件内置的默认模板。
- **`markdown-docs-converter.projectName`**: 模板中使用的项目名称。
- **`markdown-docs-converter.author`**: 模板中使用的作者姓名。
- **`markdown-docs-converter.email`**: 模板中使用的邮箱地址。
- **`markdown-docs-converter.mobilephone`**: 模板中使用的联系电话。

## 🏗️ 开发状态

**核心功能已完成**
- ✅ **Markdown 转换**: `md` -> `docx`/`pdf`/`html`，完全支持带自定义模板的 DOCX 转换。
- ✅ **Office 转换**: `docx`/`xlsx`/`pdf` -> `md`。
- ✅ **图表转换**: `svg`/`drawio` -> `png`。
- ✅ **配置系统**: 所有功能均可通过 VS Code 标准设置页面进行配置。

项目当前处于稳定维护阶段。

## 📦 技术架构

- **前端**: TypeScript + VS Code Extension API
- **后端**: Python + 面向对象转换器架构
- **通信**: JSON 格式的命令行接口

## 🔧 开发说明

本项目将 `/tools` 目录中的成熟转换脚本重构为结构化的 VS Code 扩展。所有转换逻辑都来源于经过验证的工具，确保转换质量和稳定性。 