import * as vscode from 'vscode';
import { TreeDataService, TreeNode, ParseResult } from '../services/TreeDataService';
import { PropertyPanelProvider } from './PropertyPanelProvider';

export class TreePreviewProvider implements vscode.TreeDataProvider<TreeNode> {
    private _onDidChangeTreeData: vscode.EventEmitter<TreeNode | undefined | null | void> = new vscode.EventEmitter<TreeNode | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<TreeNode | undefined | null | void> = this._onDidChangeTreeData.event;

    private treeData: TreeNode | null = null;
    private treeDataService: TreeDataService;
    private propertyPanelProvider: PropertyPanelProvider;

    constructor() {
        this.treeDataService = new TreeDataService();
        this.propertyPanelProvider = new PropertyPanelProvider();
        
        // 注册TreePreviewProvider特有的命令
        vscode.commands.registerCommand('arxml.expandAllFromNode', (node: TreeNode) => this.expandAllFromNode(node));
        vscode.commands.registerCommand('arxml.collapseAllFromNode', (node: TreeNode) => this.collapseAllFromNode(node));
        vscode.commands.registerCommand('arxml.selectNode', (node: TreeNode) => this.selectNode(node));
        vscode.commands.registerCommand('arxml.gotoSource', (node: TreeNode) => this.gotoSource(node));
        
        // 监听活动编辑器变化
        vscode.window.onDidChangeActiveTextEditor(() => {
            console.log('📝 Active editor changed, loading current file...');
            this.loadCurrentFile();
        });
        
        // 强制初始化 - 延迟执行以确保插件完全激活
        setTimeout(() => {
            console.log('🔄 Force initial load...');
            this.loadCurrentFile();
        }, 1000);
    }

    getTreeItem(element: TreeNode): vscode.TreeItem {
        const item = new vscode.TreeItem(element.name);
        
        // DaVinci风格：仅容器可展开，过滤非容器子节点
        const containerChildren = (element.children || [])
            .filter(child => this.isContainerType(child.type));
        
        if (this.isContainerType(element.type) && containerChildren.length > 0) {
            // 默认展开根节点和第一级容器
            if (element.type === 'root' || element.path?.split('/').length <= 5) {
                item.collapsibleState = vscode.TreeItemCollapsibleState.Expanded;
            } else {
                item.collapsibleState = vscode.TreeItemCollapsibleState.Collapsed;
            }
        } else {
            item.collapsibleState = vscode.TreeItemCollapsibleState.None;
        }
            
        // 设置图标
        if (element.type === 'container' || element.type === 'root') {
            item.iconPath = new vscode.ThemeIcon('folder');
        } else if (element.type === 'package') {
            item.iconPath = new vscode.ThemeIcon('package');
        } else if (element.type === 'module') {
            item.iconPath = new vscode.ThemeIcon('symbol-module');
        } else {
            item.iconPath = new vscode.ThemeIcon('file');
        }
        
        // 设置工具提示
        let tooltip = `名称: ${element.name}`;
        if (element.path) {
            tooltip += `\n路径: ${element.path}`;
        }
        
        // 显示参数数量信息
        const paramCount = element.parameters?.length || 0;
        if (paramCount > 0) {
            tooltip += `\n参数数量: ${paramCount}`;
        }
        
        if (element.metadata?.description) {
            tooltip += `\n描述: ${element.metadata.description}`;
        }
        item.tooltip = tooltip;
        
        // 设置描述（显示参数数量）
        if (paramCount > 0) {
            item.description = `(${paramCount}个参数)`;
        }
        
        // 设置上下文值（用于右键菜单）
        if (this.isContainerType(element.type)) {
            item.contextValue = 'container';
        } else {
            item.contextValue = element.type;
        }
        
        // DaVinci风格：为容器添加选择命令，用于更新属性面板
        // 注意：这里不设置command，让箭头和名字有不同的行为
        if (this.isContainerType(element.type)) {
            // 仅当点击名字时才触发选择，箭头点击由TreeView默认处理
            item.command = {
                command: 'arxml.selectNode',
                title: '选择容器查看参数',
                arguments: [element]
            };
        }
        
        return item;
    }

    private isContainerType(nodeType: string): boolean {
        const containerTypes = ['container', 'root', 'package', 'module'];
        return containerTypes.includes(nodeType);
    }

    getChildren(element?: TreeNode): Thenable<TreeNode[]> {
        if (!element) {
            // 根级别：DaVinci风格，直接返回模块节点
            if (this.treeData) {
                // 如果根节点是虚拟根节点且包含多个模块，直接返回模块节点
                if (this.treeData.type === 'root' && this.treeData.name === 'AUTOSAR配置' && this.treeData.children) {
                    const moduleChildren = this.treeData.children.filter(child => child.type === 'module' || child.type === 'container');
                    if (moduleChildren.length > 0) {
                        console.log(`🎯 DaVinci风格：直接返回${moduleChildren.length}个模块节点:`, moduleChildren.map(m => m.name));
                        return Promise.resolve(moduleChildren);
                    }
                }
                // 如果是单个模块，检查它是否应该作为根级显示
                if (this.treeData.type === 'module' || this.treeData.type === 'container') {
                    console.log(`🎯 DaVinci风格：单个模块作为根级显示: ${this.treeData.name}`);
                    return Promise.resolve([this.treeData]);
                }
                // 否则返回原始根节点
                return Promise.resolve([this.treeData]);
            } else {
                return Promise.resolve([]);
            }
        } else {
            // DaVinci风格：返回所有子节点，包括容器和参数组
            const children = element.children || [];
            return Promise.resolve(children);
        }
    }

    private async loadCurrentFile() {
        const activeEditor = vscode.window.activeTextEditor;
        console.log('🔍 loadCurrentFile called, activeEditor:', !!activeEditor);
        
        if (!activeEditor) {
            console.log('⚠️ No active editor, creating sample data for testing...');
            // 创建示例数据以便测试TreeView和PropertyPanel
            this.createSampleData();
            return;
        }

        const document = activeEditor.document;
        const filePath = document.fileName;
        console.log('📂 Current file:', filePath);
        
        // 检查文件类型
        if (!this.isSupported(filePath)) {
            console.log('❌ File type not supported, creating sample data...');
            this.createSampleData();
            return;
        }

        try {
            vscode.window.withProgress({
                location: vscode.ProgressLocation.Window,
                title: "正在解析ARXML/XDM文件...",
                cancellable: false
            }, async (progress) => {
                progress.report({ increment: 0, message: "连接Python后端..." });
                
                const result = await this.treeDataService.parseFile(filePath);
                
                progress.report({ increment: 50, message: "处理解析结果..." });
                
                if (result.success && result.treeStructure) {
                    this.treeData = result.treeStructure;
                    console.log(`✅ Tree data loaded successfully. Root: ${this.treeData.name}, Children: ${this.treeData.children?.length || 0}`);
                    
                    // 刷新树视图
                    this._onDidChangeTreeData.fire();
                    
                    // 等待树视图渲染完成后自动选择第一个模块节点
                    setTimeout(() => {
                        if (this.treeData) {
                            // 如果是简化的结构，选择第一个模块
                            if (this.treeData.type === 'root' && this.treeData.name === 'AUTOSAR配置' && this.treeData.children) {
                                const moduleChildren = this.treeData.children.filter(child => child.type === 'module');
                                if (moduleChildren.length > 0) {
                                    this.selectNode(moduleChildren[0]);
                                    console.log(`🔍 First module "${moduleChildren[0].name}" auto-selected for property panel`);
                                    return;
                                }
                            }
                            // 否则选择根节点
                            this.selectNode(this.treeData);
                            console.log('🔍 Root node auto-selected for property panel');
                        }
                    }, 500);
                    
                    vscode.window.showInformationMessage(
                        `✅ 解析成功: ${result.metadata?.totalContainers || 0}个容器, ${result.metadata?.totalParameters || 0}个参数`
                    );
                } else {
                    this.treeData = null;
                    console.log(`❌ Tree data load failed: ${result.error}`);
                    
                    // 清空参数面板
                    this.propertyPanelProvider.clearParameters();
                    
                    vscode.window.showErrorMessage(`❌ 解析失败: ${result.error || '未知错误'}`);
                }
                
                progress.report({ increment: 100, message: "完成" });
            });
            
        } catch (error) {
            vscode.window.showErrorMessage(`解析文件时发生错误: ${error}`);
            this.treeData = null;
            this._onDidChangeTreeData.fire();
        }
    }

    private isSupported(filePath: string): boolean {
        const ext = filePath.toLowerCase();
        return ext.endsWith('.arxml') || ext.endsWith('.xdm');
    }

    refresh(): void {
        this.loadCurrentFile();
    }

    showLogs(): void {
        this.treeDataService.showOutput();
        vscode.window.showInformationMessage('📋 通信日志已在输出面板中显示');
        }

    expandAll(): void {
        console.log('🔍 expandAll called');
        console.log('📊 currentTreeView:', !!this.currentTreeView);
        console.log('📊 treeData:', !!this.treeData);
        
        // 检查TreeView是否已初始化
        if (!this.currentTreeView) {
            console.log('❌ TreeView not initialized');
            vscode.window.showWarningMessage('⚠️ 树视图未初始化，请稍后再试');
            return;
        }
        
        // 检查是否有数据
        if (!this.treeData) {
            console.log('❌ No tree data available');
            vscode.window.showWarningMessage('⚠️ 没有可展开的数据，请先打开一个ARXML/XDM文件');
            return;
        }
        
        // 显示进度并执行展开
        vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: "展开所有节点",
            cancellable: false
        }, async (progress) => {
            progress.report({ increment: 0, message: "正在展开..." });
            
            try {
                await this.expandAllRecursively(this.treeData);
                progress.report({ increment: 100, message: "完成" });
                vscode.window.showInformationMessage('✅ 已展开所有节点');
            } catch (error) {
                console.error('❌ Error during expand all:', error);
                vscode.window.showErrorMessage(`展开失败: ${error}`);
            }
        });
    }

    collapseAll(): void {
        // 刷新树来折叠所有节点
        this._onDidChangeTreeData.fire();
        vscode.window.showInformationMessage('📁 已折叠所有节点');
    }

    private currentTreeView: vscode.TreeView<TreeNode> | undefined;

    setTreeView(treeView: vscode.TreeView<TreeNode>): void {
        console.log('🔧 Setting TreeView reference');
        this.currentTreeView = treeView;
        console.log('✅ TreeView reference set successfully');
        
        // 添加TreeView事件监听器
        treeView.onDidChangeVisibility(e => {
            console.log('👀 TreeView visibility changed:', e.visible);
        });
        
        treeView.onDidExpandElement(e => {
            console.log('📂 TreeView element expanded:', e.element.name);
        });
        
        treeView.onDidCollapseElement(e => {
            console.log('📁 TreeView element collapsed:', e.element.name);
        });
    }

    private async expandAllRecursively(node: TreeNode | null): Promise<void> {
        if (!node || !this.currentTreeView) {
            console.log('⚠️ expandAllRecursively: node or currentTreeView is null');
            return;
        }

        console.log(`🔍 Expanding node: ${node.name} (type: ${node.type})`);

        try {
            // 先展开当前节点（如果它是容器类型）
            if (this.isContainerType(node.type)) {
                console.log(`📂 Revealing container node: ${node.name}`);
                await this.currentTreeView.reveal(node, { expand: true, select: false, focus: false });
                
                // 等待一小段时间让界面更新
                await new Promise(resolve => setTimeout(resolve, 50));
            }
            
            // 然后展开所有容器类型的子节点
            if (node.children && node.children.length > 0) {
                const containerChildren = node.children.filter(child => this.isContainerType(child.type));
                console.log(`📁 Found ${containerChildren.length} container children for ${node.name}`);
                
                for (const child of containerChildren) {
                    await this.expandAllRecursively(child);
                }
            }
        } catch (error) {
            // 记录错误但继续处理其他节点
            console.log(`⚠️ Error expanding node ${node.name}:`, error);
        }
    }

    search(): void {
        vscode.window.showInputBox({
            placeHolder: '输入搜索关键字...',
            prompt: '搜索树节点'
        }).then(query => {
            if (query) {
                // 实现搜索功能
                vscode.window.showInformationMessage(`搜索功能待实现: ${query}`);
            }
        });
    }

    expandAllFromNode(node: TreeNode): void {
        // 使用现有的TreeView引用展开节点
        if (!this.currentTreeView) {
            vscode.window.showErrorMessage('TreeView未初始化');
            return;
        }

        const expandRecursively = async (currentNode: TreeNode) => {
            try {
                if (currentNode.children && currentNode.children.length > 0) {
                    await this.currentTreeView!.reveal(currentNode, { expand: true, select: false, focus: false });
                    await new Promise(resolve => setTimeout(resolve, 10));
                    
                    const containerChildren = currentNode.children.filter(child => this.isContainerType(child.type));
                    for (const child of containerChildren) {
                        await expandRecursively(child);
                    }
                }
            } catch (error) {
                console.log('展开子节点时发生错误:', error);
            }
        };
        
        expandRecursively(node).then(() => {
            vscode.window.showInformationMessage(`已展开节点 "${node.name}" 及其所有子节点`);
        }).catch(error => {
            vscode.window.showErrorMessage(`展开节点失败: ${error}`);
        });
    }

    collapseAllFromNode(node: TreeNode): void {
        // 使用现有的TreeView引用折叠节点
        if (!this.currentTreeView) {
            vscode.window.showErrorMessage('TreeView未初始化');
            return;
        }

        const collapseRecursively = async (currentNode: TreeNode) => {
            try {
                if (currentNode.children && currentNode.children.length > 0) {
                    const containerChildren = currentNode.children.filter(child => this.isContainerType(child.type));
                    for (const child of containerChildren) {
                        await collapseRecursively(child);
                    }
                    await this.currentTreeView!.reveal(currentNode, { expand: false, select: false, focus: false });
                    await new Promise(resolve => setTimeout(resolve, 10));
                }
            } catch (error) {
                console.log('折叠子节点时发生错误:', error);
            }
        };
        
        collapseRecursively(node).then(() => {
            vscode.window.showInformationMessage(`已折叠节点 "${node.name}" 及其所有子节点`);
        }).catch(error => {
            vscode.window.showErrorMessage(`折叠节点失败: ${error}`);
        });
    }

    selectNode(node: TreeNode): void {
        console.log(`🎯 Selecting node: ${node.name}, type: ${node.type}, parameters: ${node.parameters?.length || 0}`);
        
        // 更新属性面板显示选中容器的参数
        if (node.parameters && node.parameters.length > 0) {
            this.propertyPanelProvider.updateParameters(node);
            console.log(`📋 Property panel updated with ${node.parameters.length} parameters`);
            vscode.window.showInformationMessage(
                `✅ 选择了容器: ${node.name}，包含 ${node.parameters.length} 个参数`
            );
        } else {
            // 即使没有参数，也要更新面板（显示为空）
            this.propertyPanelProvider.updateParameters(node);
            console.log(`📋 Property panel updated (no parameters)`);
            vscode.window.showInformationMessage(
                `📁 选择了容器: ${node.name}，无参数`
            );
        }
        
        // 可选：在输出面板显示详细信息
        this.treeDataService.logNodeSelection(node);
    }

    gotoSource(node: TreeNode): void {
        // 跳转到源文件位置
        if (node.metadata?.sourceLocation) {
            const { line, column } = node.metadata.sourceLocation;
            const activeEditor = vscode.window.activeTextEditor;
            if (activeEditor) {
                const position = new vscode.Position(line - 1, column - 1);
                activeEditor.selection = new vscode.Selection(position, position);
                activeEditor.revealRange(new vscode.Range(position, position));
            }
        } else {
            vscode.window.showInformationMessage(`节点 "${node.name}" 没有源位置信息`);
        }
    }

    getPropertyPanelProvider(): PropertyPanelProvider {
        return this.propertyPanelProvider;
    }

    private createSampleData(): void {
        console.log('🎭 Creating sample data for testing...');
        
        // 创建示例TreeNode结构
        const sampleData: TreeNode = {
            id: 'sample_root',
            name: 'Sample AUTOSAR Root',
            type: 'root',
            path: '/AUTOSAR',
            children: [
                {
                    id: 'sample_packages',
                    name: 'AR-PACKAGES',
                    type: 'package',
                    path: '/AUTOSAR/AR-PACKAGES',
                    children: [
                        {
                            id: 'sample_can_config',
                            name: 'CanConfigSet',
                            type: 'container',
                            path: '/AUTOSAR/AR-PACKAGES/CanConfigSet',
                            children: [
                                {
                                    id: 'sample_can_controller',
                                    name: 'CanController',
                                    type: 'container',
                                    path: '/AUTOSAR/AR-PACKAGES/CanConfigSet/CanController',
                                    children: [],
                                    parameters: [
                                        {
                                            id: 'can_controller_id',
                                            name: 'CanControllerId',
                                            type: 'integer',
                                            value: '0',
                                            description: 'CAN控制器标识符'
                                        },
                                        {
                                            id: 'can_baudrate',
                                            name: 'CanBaudRate',
                                            type: 'integer',
                                            value: '500000',
                                            description: 'CAN波特率(bps)'
                                        }
                                    ]
                                }
                            ],
                            parameters: [
                                {
                                    id: 'config_set_name',
                                    name: 'ConfigSetName',
                                    type: 'string',
                                    value: 'DefaultConfig',
                                    description: '配置集名称'
                                }
                            ]
                        }
                    ],
                    parameters: []
                }
            ],
            parameters: [
                {
                    id: 'schema_version',
                    name: 'SchemaVersion',
                    type: 'string',
                    value: '4.0',
                    description: 'AUTOSAR架构版本'
                }
            ]
        };
        
        this.treeData = sampleData;
        console.log('✅ Sample data created');
        
        // 刷新树视图
        this._onDidChangeTreeData.fire();
        
        // 自动选择根节点
        setTimeout(() => {
            if (this.treeData) {
                this.selectNode(this.treeData);
                console.log('🔍 Sample root node auto-selected');
            }
        }, 300);
        
        vscode.window.showInformationMessage('📊 显示示例数据 - 请打开ARXML/XDM文件查看实际内容');
    }
} 