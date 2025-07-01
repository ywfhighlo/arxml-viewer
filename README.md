# Markdown Hub - VSCode 扩展

Markdown文档转换的瑞士军刀。

## 👨‍💻 作者信息

**作者**: 余文锋  
**邮箱**: 909188787@qq.com  

## 🎯 功能特性

### Markdown 转换
- **Markdown → DOCX**: 将 `.md` 文件转换为带有自定义模板的 Word 文档。
- **Markdown → PDF**: 将 `.md` 文件转换为 PDF 文档。
- **Markdown → HTML**: 将 `.md` 文件转换为带样式的 HTML 网页。

### Office 与其他格式转换
- **DOCX → Markdown**: 将 Word 文档转换为 `.md` 文件。
- **XLSX → Markdown**: 将 Excel 表格转换为 `.md` 文件。
- **PDF → Markdown**: 将 PDF 文档转换为 `.md` 文件。
- **SVG/Draw.io → PNG**: 将矢量图或流程图转换为PNG图片。

## 🚀 使用方法

1. 在 VS Code 的资源管理器中，右键点击任何支持的文件或包含这些文件的文件夹。
2. 在弹出的上下文菜单中，选择您需要的转换命令 (例如 "Convert to DOCX")。
3. 转换后的文件将出现在您配置的输出目录中。
4. 若要配置模板、作者信息等，请右键选择 **"Template Settings..."**，这会直接带您到 VS Code 的设置页面。

## ⚙️ 配置选项

您可以在 VS Code 的 `设置(Settings)` 中搜索 `markdown-hub` 来找到所有配置项。

- **`markdown-hub.outputDirectory`**: 所有转换后文件的输出目录。
- **`markdown-hub.pythonPath`**: Python 解释器的路径或命令。
- **`markdown-hub.useTemplate`**: 是否为 `Markdown → DOCX` 的转换启用模板功能。
- **`markdown-hub.templatePath`**: 自定义 `.docx` 模板文件的完整路径。
- **`markdown-hub.projectName`**: 模板中使用的项目名称。
- **`markdown-hub.author`**: 模板中使用的作者姓名。
- **`markdown-hub.email`**: 模板中使用的邮箱地址。
- **`markdown-hub.mobilephone`**: 模板中使用的联系电话。
- **`markdown-hub.promoteHeadings`**: 自动提升Markdown文档的标题级别，以适配"封面页"式的写作习惯。
