# 后端服务测试指南

本文档旨在指导开发者如何测试后端Python服务的解析功能，特别是针对ARXML和XDM文件的统一化JSON输出。

## 统一测试入口

所有针对文件解析的测试都应通过 `python-backend/cli_wrapper.py` 脚本进行。该脚本是VSCode前端调用后端服务的唯一入口，能够模拟前端请求并以JSON格式返回与前端`ParseResult`接口完全兼容的数据。

核心命令是 `parse`，其基本用法如下：
```bash
python3 python-backend/cli_wrapper.py parse --file <文件路径>
```

## 测试ARXML文件

使用以下命令来解析一个ARXML文件并获取其树形结构JSON。

### 示例命令
```bash
python3 python-backend/cli_wrapper.py parse --file ./log/Can_bswmd.arxml
```

### 预期输出
命令会输出一个JSON对象，其中包含以下关键字段：
- `success`: `true` 表示解析成功。
- `fileType`: `"arxml"`。
- `treeStructure`: 一个嵌套的树状对象，代表了ARXML文件的层级结构，可直接被前端渲染。

## 测试XDM文件

使用以下命令来解析一个XDM文件并获取其树形结构JSON。

### 示例命令
```bash
python3 python-backend/cli_wrapper.py parse --file ./log/Lin_17_AscLin_Aurix2G/config/Lin_17_AscLin.xdm
```

### 预期输出
命令会输出一个JSON对象，其结构与ARXML的输出非常相似，体现了后端处理的统一性：
- `success`: `true` 表示解析成功。
- `fileType`: `"xdm"`。
- `treeStructure`: 一个嵌套的树状对象，代表了XDM文件的层级结构，可直接被前端渲染。

通过使用此`cli_wrapper.py`，您可以方便地在修改后端逻辑后，快速验证其对不同文件类型的解析是否正确，以及输出是否仍然符合前端的期望格式。 