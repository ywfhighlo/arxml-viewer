# 后端新增文件格式支持开发指南

本文档旨在为开发者提供一个清晰的流程，指导如何为后端服务添加对新配置文件格式（如`.bmd`, `.some_other_format`）的支持。我们的核心架构优势在于：**后端提供统一的JSON数据结构，前端（或测试GUI）完全无需改动**。

遵循本指南，您可以实现对新格式的"无缝兼容"。

## 核心架构理念

1.  **统一入口**: `python-backend/cli_wrapper.py` 是所有文件解析任务的唯一入口。无论是VS Code前端还是测试GUI，都通过此脚本与后端交互。
2.  **统一数据契约**: 后端无论解析何种文件（ARXML, BMD, XDM, XML），都必须输出一个标准化的JSON对象。这保证了任何消费方（前端、GUI）都使用同样的方式处理数据。
3.  **前端/GUI零改动**: 由于数据契约是统一的，当后端支持了新格式后，前端和GUI**完全不需要**任何修改就能自动支持新格式的解析和显示。

## 新增文件格式的步骤

让我们以成功添加`.bmd`文件支持的经验为例，演示添加新格式的"三步走"流程。

### 第一步：修改文件类型检测

-   **文件**: `python-backend/processors.py`
-   **方法**: `_detect_file_type(self, file_path: Path) -> str`

这是所有解析逻辑的起点。在此方法中，为新的文件扩展名添加一个识别分支。

**示例：添加`.bmd`支持**
```python
# ... in processors.py
def _detect_file_type(self, file_path: Path) -> str:
    """检测文件类型"""
    suffix = file_path.suffix.lower()
    if suffix == ".arxml":
        return "arxml"
    elif suffix == ".bmd":  # <-- 新增的分支
        return "bmd"
    elif suffix == ".xdm":
        return "xdm"
    else:
        return "xml"
```

### 第二步：添加文件处理逻辑

-   **文件**: `python-backend/processors.py`
-   **方法**: `parse_file(self, file_path: str) -> Dict[str, Any]`

在识别出文件类型后，需要在这里决定调用哪个解析函数。

**示例：为`bmd`类型指定解析器**

`.bmd`文件的结构与`.arxml`兼容，因此我们可以复用现有的`_parse_arxml_file`方法。关键在于**必须把正确的文件类型（"bmd"）传递给解析函数**，以确保最终输出的JSON中`fileType`字段正确。

```python
# ... in processors.py
def parse_file(self, file_path: str) -> Dict[str, Any]:
    # ...
    file_type = self._detect_file_type(file_path)
    
    if file_type == "arxml":
        return self._parse_arxml_file(str(file_path), "arxml")
    elif file_type == "bmd":  # <-- 新增的分支
        # BMD使用ARXML解析器，但必须传递正确的类型 "bmd"
        return self._parse_arxml_file(str(file_path), "bmd") 
    elif file_type == "xdm":
        return self._parse_xdm_file(str(file_path))
    else:
        return self._parse_xml_file(str(file_path), "xml")
    # ...
```

**注意**: 如果新格式需要一个全新的解析器，您需要：
1.  在`lib/`下创建新的`some_format_processor.py`。
2.  在`processors.py`中创建一个新的`_parse_some_format_file()`方法。
3.  在`parse_file`中调用这个新方法。

### 第三步：确保解析函数支持`file_type`参数

-   **文件**: `python-backend/processors.py`
-   **方法**: `_parse_arxml_file` (或您复用的任何解析函数)

为了让第二步的`file_type`传递生效，需要确保目标解析函数能够接收它，并在返回的JSON中正确使用。

**示例：修改`_parse_arxml_file`**

我们将它的`fileType`字段从硬编码的`"arxml"`改为了动态的`file_type`参数。

```python
# ... in processors.py
# 增加 file_type 参数，并提供默认值以保持向后兼容
def _parse_arxml_file(self, file_path: str, file_type: str = "arxml") -> Dict[str, Any]:
    # ...
    # ... 解析逻辑 ...
    # ...
    
    return {
        "success": True,
        "fileType": file_type,  # <-- 使用传入的参数
        "filePath": file_path,
        "treeStructure": tree_structure,
        "metadata": { ... }
    }
```

## 测试与验证

完成代码修改后，**必须**通过`cli_wrapper.py`进行测试。这是验证后端修改是否成功的唯一标准。

1.  **进入后端目录**:
    ```bash
    cd python-backend
    ```

2.  **执行解析命令**: 使用`jq`工具可以方便地查看关键字段。
    -   **验证解析是否成功**:
        ```bash
        python3 cli_wrapper.py parse --file <你的新格式文件路径> | jq '.success'
        # 预期输出: true
        ```
    -   **验证文件类型是否正确**:
        ```bash
        python3 cli_wrapper.py parse --file <你的新格式文件路径> | jq '.fileType'
        # 预期输出: "bmd" (或你的新格式类型)
        ```
    -   **验证基本结构树是否生成**:
        ```bash
        python3 cli_wrapper.py parse --file <你的新格式文件路径> | jq '{success, fileType, rootName: .treeStructure.name}'
        # 预期输出类似:
        # {
        #   "success": true,
        #   "fileType": "bmd",
        #   "rootName": "AUTOSAR配置"
        # }
        ```

3.  **GUI无缝兼容性测试**:
    -   直接使用`backend_test_gui.py`打开新格式的文件，它应该能够被正确解析和显示，无需对GUI脚本进行任何修改。

通过这套流程，我们保证了后端的可扩展性、可维护性和健壮性，完美实践了"关注点分离"的设计原则。 

## 第四步（可选）：更新前端（VS Code插件）配置

如果您的目标是让VS Code插件直接支持新文件格式（例如，通过双击文件直接用我们的自定义编辑器打开），您还需要更新插件的配置文件。

-   **文件**: `package.json` (位于项目根目录)
-   **配置项**: `contributes.customEditors`

在`customEditors`的`selector`数组中，为您想支持的新文件扩展名添加一个新的`filenamePattern`。

**示例：为`.bmd`和`.xml`添加编辑器支持**

```json
// ... in package.json
"customEditors": [
  {
    "viewType": "arxmlTreePreview",
    "displayName": "ARXML树形预览",
    "selector": [
      {
        "filenamePattern": "*.arxml"
      },
      {
        "filenamePattern": "*.xdm"
      },
      {
        "filenamePattern": "*.bmd" // <-- 新增
      },
      {
        "filenamePattern": "*.xml" // <-- 新增
      }
    ],
    "priority": "default"
  }
],
// ...
```

**重要提示**：修改 `package.json` 后，您需要**重新加载或重启VS Code**才能使这些更改生效。

## 总结

通过这四个步骤，您可以实现对任意新文件格式的端到端支持。整个过程的核心在于保持后端输出的**JSON格式统一**，这使得前端的适配工作变得极其简单，甚至完全不需要（如果只是在已有功能上扩展）。

我们保证了后端的可扩展性、可维护性和健壮性，完美实践了"关注点分离"的设计原则。现在，开香槟庆祝吧！🎉 