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

1. 在 VS Code 资源管理器中右键点击文件或文件夹
2. 在上下文菜单中选择相应的转换选项
3. 转换完成后会在配置的输出目录中生成文件

## ⚙️ 配置选项

- `office-docs-converter.outputDirectory`: 输出目录路径（默认: `./converted`）
- `office-docs-converter.pythonPath`: Python 解释器路径（默认: `python3`）

## 🏗️ 开发状态

当前处于**阶段一**完成状态：
- ✅ 项目框架搭建完成
- ✅ 前端 TypeScript 代码实现
- ✅ 后端 Python 架构设计
- ✅ 基础转换器类定义

**下一步**: 从 `/tools` 目录迁移成熟的转换逻辑到对应的转换器类中。

## 📦 技术架构

- **前端**: TypeScript + VS Code Extension API
- **后端**: Python + 面向对象转换器架构
- **通信**: JSON 格式的命令行接口

## 🔧 开发说明

本项目将 `/tools` 目录中的成熟转换脚本重构为结构化的 VS Code 扩展。所有转换逻辑都来源于经过验证的工具，确保转换质量和稳定性。 