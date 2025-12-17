import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { TreeDataService } from './services/TreeDataService';

export class ArxmlCustomEditorProvider implements vscode.CustomTextEditorProvider {
    private treeDataService: TreeDataService;
    private currentWebview: vscode.Webview | null = null;

    constructor(private readonly context: vscode.ExtensionContext) {
        this.treeDataService = new TreeDataService();
    }

    public async resolveCustomTextEditor(
        document: vscode.TextDocument,
        webviewPanel: vscode.WebviewPanel,
        _token: vscode.CancellationToken
    ): Promise<void> {
        // 保存当前webview引用
        this.currentWebview = webviewPanel.webview;
        
        // 设置webview选项
        webviewPanel.webview.options = {
            enableScripts: true,
        };

        // 创建HTML内容
        webviewPanel.webview.html = this.getWebviewContent(webviewPanel.webview, document.uri);

        // 监听文档变化
        const changeDocumentSubscription = vscode.workspace.onDidChangeTextDocument(e => {
            if (e.document.uri.toString() === document.uri.toString()) {
                this.updateWebview(webviewPanel.webview, document.uri);
            }
        });

        // 监听webview消息
        const messageSubscription = webviewPanel.webview.onDidReceiveMessage(
            async (message) => {
                switch (message.type) {
                    case 'parameterChanged':
                        await this.handleParameterChanged(document, message.data);
                        break;
                    case 'requestSave':
                        await this.saveDocument(document);
                        break;
                    case 'error':
                        vscode.window.showErrorMessage(`ARXML Viewer: ${message.message}`);
                        break;
                    case 'info':
                        vscode.window.showInformationMessage(`ARXML Viewer: ${message.message}`);
                        break;
                    case 'saveStatus':
                        // 保存状态消息直接发送给webview处理
                        break;
                }
            }
        );

        // 清理资源
        webviewPanel.onDidDispose(() => {
            changeDocumentSubscription.dispose();
            messageSubscription.dispose();
            this.currentWebview = null;
        });

        // 初始加载
        this.updateWebview(webviewPanel.webview, document.uri);
    }

    // 公共方法供extension.ts调用
    public expandAll(): void {
        if (this.currentWebview) {
            this.currentWebview.postMessage({
                type: 'expandAll'
            });
        }
    }

    public collapseAll(): void {
        if (this.currentWebview) {
            this.currentWebview.postMessage({
                type: 'collapseAll'
            });
        }
    }

    public refresh(): void {
        if (this.currentWebview) {
            this.currentWebview.postMessage({
                type: 'refresh'
            });
        }
    }

    public updateSettings(): void {
        if (this.currentWebview) {
            // 获取最新的配置
            const config = vscode.workspace.getConfiguration('arxmlTreePreviewer');
            const configVariantDisplay = config.get<string>('configVariantDisplay', 'VARIANT-POST-BUILD');
            
            // 发送配置更新消息
            this.currentWebview.postMessage({
                type: 'settings',
                settings: {
                    configVariantDisplay: configVariantDisplay
                }
            });
            
            console.log('Settings updated and sent to webview:', { configVariantDisplay });
        }
    }

    private getWebviewContent(webview: vscode.Webview, uri: vscode.Uri): string {
        return `
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>ARXML Configurator</title>
                <style>
                    body {
                        margin: 0;
                        padding: 0;
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        font-size: 12px;
                        line-height: 1.4;
                        color: var(--vscode-foreground);
                        background-color: var(--vscode-editor-background);
                        overflow: hidden;
                    }
                    
                    /* 顶部面包屑导航 */
                    .breadcrumb-bar {
                        height: 32px;
                        background-color: var(--vscode-titleBar-activeBackground);
                        border-bottom: 1px solid var(--vscode-panel-border);
                        display: flex;
                        align-items: center;
                        padding: 0 12px;
                        font-size: 11px;
                        color: var(--vscode-titleBar-activeForeground);
                    }
                    
                    .breadcrumb {
                        display: flex;
                        align-items: center;
                        gap: 4px;
                    }
                    
                    .breadcrumb-item {
                        cursor: pointer;
                        padding: 2px 6px;
                        border-radius: 2px;
                        transition: background-color 0.2s;
                    }
                    
                    .breadcrumb-item:hover {
                        background-color: var(--vscode-titleBar-hoverBackground);
                    }
                    
                    .breadcrumb-separator {
                        color: var(--vscode-descriptionForeground);
                        font-size: 10px;
                    }
                    
                    /* 主容器 */
                    .main-container {
                        display: flex;
                        height: calc(100vh - 32px);
                    }
                    
                    /* 左侧树状视图 */
                    .tree-panel {
                        width: 300px;
                        border-right: 1px solid var(--vscode-panel-border);
                        background-color: var(--vscode-sideBar-background);
                        display: flex;
                        flex-direction: column;
                    }
                    
                    .tree-header {
                        height: 28px;
                        background-color: var(--vscode-sideBarSectionHeader-background);
                        border-bottom: 1px solid var(--vscode-panel-border);
                        display: flex;
                        align-items: center;
                        padding: 0 8px;
                        font-size: 11px;
                        font-weight: 600;
                        color: var(--vscode-sideBarSectionHeader-foreground);
                    }
                    
                    .tree-content {
                        flex: 1;
                        overflow-y: auto;
                        padding: 4px;
                    }
                    
                    /* 右侧属性编辑器 */
                    .property-panel {
                        flex: 1;
                        background-color: var(--vscode-editor-background);
                        display: flex;
                        flex-direction: column;
                    }
                    
                    .property-header {
                        height: 28px;
                        background-color: var(--vscode-sideBarSectionHeader-background);
                        border-bottom: 1px solid var(--vscode-panel-border);
                        display: flex;
                        align-items: center;
                        padding: 0 12px;
                        font-size: 11px;
                        font-weight: 600;
                        color: var(--vscode-sideBarSectionHeader-foreground);
                    }
                    
                    .property-content {
                        flex: 1;
                        overflow-y: auto;
                        padding: 12px;
                    }
                    
                    /* 树节点样式 */
                    .tree-node {
                        display: flex;
                        align-items: center;
                        padding: 2px 4px;
                        margin: 1px 0;
                        cursor: pointer;
                        border-radius: 2px;
                        font-size: 11px;
                        line-height: 1.3;
                        user-select: none;
                    }
                    
                    .tree-node:hover {
                        background-color: var(--vscode-list-hoverBackground);
                    }
                    
                    .tree-node.selected {
                        background-color: var(--vscode-list-activeSelectionBackground);
                        color: var(--vscode-list-activeSelectionForeground);
                    }
                    
                    .tree-node-icon {
                        width: 16px;
                        height: 16px;
                        margin-right: 4px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 10px;
                    }
                    
                    .tree-node-expand {
                        width: 12px;
                        height: 12px;
                        margin-right: 2px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        cursor: pointer;
                        font-size: 8px;
                        transition: transform 0.15s ease;
                    }
                    
                    .tree-node-expand.expanded {
                        transform: rotate(90deg);
                    }
                    
                    .tree-node-name {
                        flex: 1;
                        font-weight: 500;
                    }
                    
                    .tree-node-count {
                        color: var(--vscode-descriptionForeground);
                        font-size: 9px;
                        margin-left: 4px;
                    }
                    
                    .tree-children {
                        margin-left: 16px;
                        border-left: 1px dotted var(--vscode-tree-indentGuidesStroke);
                        padding-left: 4px;
                    }
                    
                    .tree-children.collapsed {
                        display: none;
                    }
                    
                    /* 属性表单样式 */
                    .property-form {
                        display: flex;
                        flex-direction: column;
                        gap: 1px;
                    }
                    
                    .property-group {
                        background-color: var(--vscode-editor-background);
                        border: none;
                        padding: 0;
                    }
                    
                    .property-group-title {
                        font-size: 11px;
                        font-weight: 600;
                        color: var(--vscode-foreground);
                        margin-bottom: 8px;
                        padding: 8px 12px;
                        background-color: var(--vscode-sideBarSectionHeader-background);
                        border-bottom: 1px solid var(--vscode-panel-border);
                    }
                    
                    .form-row {
                        display: flex;
                        align-items: center;
                        padding: 4px 12px;
                        border-bottom: 1px solid var(--vscode-panel-border);
                        min-height: 28px;
                        background-color: var(--vscode-editor-background);
                        position: relative;
                    }
                    
                    .form-row:hover {
                        background-color: var(--vscode-list-hoverBackground);
                    }
                    
                    .form-row.modified {
                        background-color: var(--vscode-diffEditor-insertedTextBackground);
                    }
                    
                    .form-label {
                        font-size: 11px;
                        font-weight: 500;
                        color: var(--vscode-foreground);
                        width: 180px;
                        flex-shrink: 0;
                        margin-right: 12px;
                        cursor: help;
                    }
                    
                    .form-label.required::after {
                        content: " *";
                        color: #f48771;
                    }
                    
                    .form-value {
                        flex: 1;
                        display: flex;
                        align-items: center;
                    }
                    
                    .form-input {
                        font-size: 11px;
                        padding: 2px 6px;
                        border: 1px solid var(--vscode-input-border);
                        border-radius: 2px;
                        background-color: var(--vscode-input-background);
                        color: var(--vscode-input-foreground);
                        font-family: inherit;
                        width: 100%;
                        min-width: 60px;
                    }
                    
                    .form-input:focus {
                        outline: none;
                        border-color: var(--vscode-focusBorder);
                        box-shadow: 0 0 0 1px var(--vscode-focusBorder);
                    }
                    
                    .form-input:disabled {
                        background-color: var(--vscode-input-background);
                        color: var(--vscode-descriptionForeground);
                        opacity: 0.6;
                    }
                    
                    .form-select {
                        font-size: 11px;
                        padding: 2px 6px;
                        border: 1px solid var(--vscode-input-border);
                        border-radius: 2px;
                        background-color: var(--vscode-dropdown-background);
                        color: var(--vscode-dropdown-foreground);
                        font-family: inherit;
                        width: 100%;
                        min-width: 80px;
                    }
                    
                    .form-select:focus {
                        outline: none;
                        border-color: var(--vscode-focusBorder);
                    }
                    
                    .form-checkbox {
                        margin-right: 6px;
                    }
                    
                    /* Tooltip样式 */
                    .tooltip {
                        position: absolute;
                        background-color: var(--vscode-editorHoverWidget-background);
                        border: 1px solid var(--vscode-editorHoverWidget-border);
                        border-radius: 3px;
                        padding: 8px;
                        font-size: 11px;
                        color: var(--vscode-editorHoverWidget-foreground);
                        max-width: 400px;
                        z-index: 1000;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                        display: none;
                        line-height: 1.4;
                        word-wrap: break-word;
                        white-space: normal;
                        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                    }
                    
                    .tooltip.show {
                        display: block;
                    }
                    
                    /* 配置类型徽章样式 */
                    .config-badge {
                        display: inline-block;
                        padding: 1px 6px;
                        margin-left: 6px;
                        font-size: 9px;
                        font-weight: 600;
                        text-align: center;
                        border-radius: 10px;
                        letter-spacing: 0.5px;
                        vertical-align: middle;
                        line-height: 1.2;
                        min-width: 20px;
                        box-shadow: 0 1px 2px rgba(0,0,0,0.1);
                    }
                    
                    /* PB (POST-BUILD) - 蓝色系 */
                    .config-badge.pb {
                        background-color: #0078d4;
                        color: white;
                        border: 1px solid #106ebe;
                    }
                    
                    /* PC (PRE-COMPILE) - 绿色系 */
                    .config-badge.pc {
                        background-color: #107c10;
                        color: white;
                        border: 1px solid #0e6e0e;
                    }
                    
                    /* LK (LINK-TIME/LINK) - 橙色系 */
                    .config-badge.lk {
                        background-color: #ff8c00;
                        color: white;
                        border: 1px solid #e67e00;
                    }
                    
                    /* PI (PUBLISHED-INFORMATION) - 紫色系 */
                    .config-badge.pi {
                        background-color: #8b5cf6;
                        color: white;
                        border: 1px solid #7c3aed;
                    }
                    
                    /* 徽章在悬停时的效果 */
                    .config-badge:hover {
                        transform: translateY(-1px);
                        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                        transition: all 0.2s ease;
                    }
                    
                    /* 在深色主题下的适配 */
                    .vscode-dark .config-badge.pb {
                        background-color: #1f7ce8;
                        border-color: #1a6cc7;
                    }
                    
                    .vscode-dark .config-badge.pc {
                        background-color: #16a016;
                        border-color: #138a13;
                    }
                    
                    .vscode-dark .config-badge.lk {
                        background-color: #ff9500;
                        border-color: #e6851a;
                    }
                    
                    .vscode-dark .config-badge.pi {
                        background-color: #a855f7;
                        border-color: #9333ea;
                    }
                    
                    /* 错误状态样式 */
                    .form-row.error {
                        background-color: var(--vscode-inputValidation-errorBackground);
                        border-left: 3px solid var(--vscode-inputValidation-errorBorder);
                    }
                    
                    .form-row.error .form-input,
                    .form-row.error .form-select {
                        border-color: var(--vscode-inputValidation-errorBorder);
                    }
                    
                    .error-message {
                        position: absolute;
                        right: 12px;
                        top: 50%;
                        transform: translateY(-50%);
                        font-size: 10px;
                        color: var(--vscode-inputValidation-errorForeground);
                        background-color: var(--vscode-inputValidation-errorBackground);
                        padding: 2px 6px;
                        border-radius: 2px;
                        border: 1px solid var(--vscode-inputValidation-errorBorder);
                        z-index: 10;
                    }
                    
                    /* 保存状态提示 */
                    .save-status {
                        position: fixed;
                        top: 20px;
                        right: 20px;
                        padding: 8px 16px;
                        border-radius: 4px;
                        font-size: 12px;
                        font-weight: 500;
                        z-index: 1000;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                        display: none;
                        animation: slideIn 0.3s ease-out;
                    }
                    
                    .save-status.info {
                        background-color: var(--vscode-notificationsInfoIcon-foreground);
                        color: white;
                    }
                    
                    .save-status.success {
                        background-color: var(--vscode-notificationsSuccessIcon-foreground);
                        color: white;
                    }
                    
                    .save-status.error {
                        background-color: var(--vscode-notificationsErrorIcon-foreground);
                        color: white;
                    }
                    
                    @keyframes slideIn {
                        from {
                            transform: translateX(100%);
                            opacity: 0;
                        }
                        to {
                            transform: translateX(0);
                            opacity: 1;
                        }
                    }
                    
                    /* 改进的修改状态样式 */
                    .form-row.modified {
                        background-color: var(--vscode-diffEditor-insertedTextBackground);
                        border-left: 3px solid var(--vscode-gitDecoration-modifiedResourceForeground);
                    }
                    
                    .form-row.modified .form-label::before {
                        content: "● ";
                        color: var(--vscode-gitDecoration-modifiedResourceForeground);
                        font-weight: bold;
                    }
                    
                    /* 改进的输入控件样式 */
                    .form-input:focus,
                    .form-select:focus {
                        outline: none;
                        border-color: var(--vscode-focusBorder);
                        box-shadow: 0 0 0 1px var(--vscode-focusBorder);
                    }
                    
                    .form-input:invalid {
                        border-color: var(--vscode-inputValidation-errorBorder);
                    }
                    
                    /* 空状态改进 */
                    .empty-state {
                        text-align: center;
                        padding: 40px 20px;
                        color: var(--vscode-descriptionForeground);
                        font-style: italic;
                    }
                    
                    .empty-state::before {
                        content: "📝";
                        display: block;
                        font-size: 32px;
                        margin-bottom: 12px;
                    }
                    
                    /* 加载和空状态 */
                    .loading-state {
                        text-align: center;
                        padding: 40px 20px;
                        color: var(--vscode-descriptionForeground);
                    }
                    
                    /* 滚动条 */
                    ::-webkit-scrollbar {
                        width: 8px;
                        height: 8px;
                    }
                    
                    ::-webkit-scrollbar-track {
                        background: var(--vscode-scrollbarSlider-background);
                    }
                    
                    ::-webkit-scrollbar-thumb {
                        background: var(--vscode-scrollbarSlider-activeBackground);
                        border-radius: 4px;
                    }
                    
                    ::-webkit-scrollbar-thumb:hover {
                        background: var(--vscode-scrollbarSlider-hoverBackground);
                    }

                    .custom-tooltip {
                        display: none;
                        position: fixed;
                        z-index: 1000;
                        padding: 8px 12px;
                        background-color: var(--vscode-editorHoverWidget-background);
                        border: 1px solid var(--vscode-editorHoverWidget-border);
                        color: var(--vscode-editorHoverWidget-foreground);
                        border-radius: 4px;
                        font-size: 11px;
                        line-height: 1.4;
                        max-width: 400px;
                        white-space: pre-wrap;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                        pointer-events: none; /* So the tooltip doesn't interfere with mouse events */
                    }
                </style>
            </head>
            <body>
                <div class="custom-tooltip"></div>
                <div class="breadcrumb-bar">
                    <div id="breadcrumb-container" class="breadcrumb">
                        <!-- Breadcrumb items will be populated here -->
                    </div>
                </div>
                
                <!-- 主容器 -->
                <div class="main-container">
                    <!-- 左侧树状视图 -->
                    <div class="tree-panel">
                        <div class="tree-header">
                            <span>📁 Configuration Tree</span>
                        </div>
                        <div class="tree-content" id="tree-content">
                            <div class="loading-state">Loading ARXML file...</div>
                        </div>
                    </div>
                    
                    <!-- 右侧属性编辑器 -->
                    <div class="property-panel">
                        <div class="property-header">
                            <span id="property-title">⚙️ Properties</span>
                        </div>
                        <div class="property-content" id="property-content">
                            <div class="empty-state">Select a container to edit its properties</div>
                        </div>
                    </div>
                </div>
                <script>
                    let currentTreeData = null;
                    let selectedNode = null;
                    let breadcrumbPath = [];
                    
                    // 全局设置对象
                    window.arxmlSettings = {
                        configVariantDisplay: 'VARIANT-POST-BUILD' // 默认值
                    };

                    const tooltip = document.querySelector('.custom-tooltip');

                    document.addEventListener('mouseover', function(e) {
                        const target = e.target.closest('[data-tooltip]');
                        if (target) {
                            const tooltipText = target.getAttribute('data-tooltip');
                            if (tooltipText) {
                                // 使用 innerText 来处理换行符
                                tooltip.innerText = tooltipText;
                                tooltip.style.display = 'block';
                            }
                        }
                    });

                    document.addEventListener('mouseout', function(e) {
                        const target = e.target.closest('[data-tooltip]');
                        if (target) {
                            tooltip.style.display = 'none';
                        }
                    });

                    document.addEventListener('mousemove', function(e) {
                        if (tooltip.style.display === 'block') {
                            const yOffset = 20;
                            const xOffset = 10;
                            
                            const winHeight = window.innerHeight;
                            const tooltipHeight = tooltip.offsetHeight;
                            const tooltipWidth = tooltip.offsetWidth;

                            let newY, newX;
                            
                            // Position below cursor if in top half of screen, otherwise above
                            if (e.clientY < winHeight / 2) {
                                newY = e.clientY + yOffset;
                            } else {
                                newY = e.clientY - tooltipHeight - (yOffset / 2);
                            }
                            
                            newX = e.clientX + xOffset;
                            
                            // Prevent tooltip from going off-screen horizontally
                            if (newX + tooltipWidth > window.innerWidth) {
                                newX = window.innerWidth - tooltipWidth - xOffset;
                            }

                            // Prevent tooltip from going off-screen vertically
                            if (newY < 0) {
                                newY = yOffset;
                            }

                            if (newY + tooltipHeight > window.innerHeight) {
                                newY = window.innerHeight - tooltipHeight;
                            }
                            
                            tooltip.style.left = newX + 'px';
                            tooltip.style.top = newY + 'px';
                        }
                    });

                    // 处理webview消息
                    window.addEventListener('message', event => {
                        const message = event.data;
                        switch (message.type) {
                            case 'update':
                                updateContent(message.data);
                                break;
                            case 'expandAll':
                                expandAllNodes();
                                break;
                            case 'collapseAll':
                                collapseAllNodes();
                                break;
                            case 'refresh':
                                location.reload();
                                break;
                            case 'saveStatus':
                                handleSaveStatus(message.status, message.message);
                                break;
                            case 'settings':
                                // 更新设置
                                if (message.settings) {
                                    const oldSettings = { ...window.arxmlSettings };
                                    window.arxmlSettings = { ...window.arxmlSettings, ...message.settings };
                                    console.log('Settings updated:', window.arxmlSettings);
                                    
                                    // 如果配置变体显示设置发生变化，重新渲染属性面板
                                    if (oldSettings.configVariantDisplay !== window.arxmlSettings.configVariantDisplay && selectedNode) {
                                        console.log('Config variant display changed, refreshing property panel');
                                        updatePropertyPanel(selectedNode);
                                    }
                                }
                                break;
                        }
                    });

                    function updateContent(data) {
                        const treeContent = document.getElementById('tree-content');
                        
                        if (data.error) {
                            treeContent.innerHTML = '<div class="loading-state">❌ Error: ' + data.error + '</div>';
                        } else if (data.tree) {
                            currentTreeData = data.tree;
                            
                            // 提取模块作为根节点
                            const moduleNodes = extractModuleNodes(data.tree);
                            let treeHtml = '';
                            
                            if (moduleNodes.length > 0) {
                                moduleNodes.forEach(module => {
                                    treeHtml += renderTreeNode(module, 0);
                                });
                            } else {
                                treeHtml += renderTreeNode(data.tree, 0);
                            }
                            
                            treeContent.innerHTML = treeHtml;
                            attachTreeEventListeners();
                            
                            // 自动展开并设置默认选择
                            setTimeout(() => {
                                autoExpandTree();
                                setDefaultSelection(moduleNodes.length > 0 ? moduleNodes : [data.tree]);
                            }, 100);
                        } else if (data.fileInfo) {
                            let html = '<div class="loading-state">⚠️ Basic file preview</div>';
                            html += '<div style="padding: 20px; font-size: 11px;">';
                            html += '<p><strong>File:</strong> ' + data.fileInfo.path + '</p>';
                            html += '<p><strong>Size:</strong> ' + data.fileInfo.size + ' bytes</p>';
                            html += '<p><strong>Type:</strong> ' + data.fileInfo.type + '</p>';
                            html += '</div>';
                            treeContent.innerHTML = html;
                        } else {
                            treeContent.innerHTML = '<div class="loading-state">Loading file...</div>';
                        }
                    }

                    function extractModuleNodes(tree) {
                        const modules = [];
                        
                        function findModules(node) {
                            if (!node) return;
                            
                            const moduleName = node.name.toLowerCase();
                            if (['can', 'lin', 'mcu', 'spi', 'port', 'os', 'det', 'ecuc', 'ecum'].includes(moduleName)) {
                                modules.push(node);
                                return;
                            }
                            
                            if (node.children) {
                                node.children.forEach(child => findModules(child));
                            }
                        }
                        
                        findModules(tree);
                        return modules;
                    }

                    function renderTreeNode(node, level = 0) {
                        const hasChildren = node.children && node.children.length > 0;
                        const hasParameters = node.parameters && node.parameters.length > 0;
                        
                        // 过滤掉无意义的中间层级（如CONTAINERS、SUB-CONTAINERS等）
                        const shouldSkipNode = isStructuralNode(node.name);
                        
                        if (shouldSkipNode && hasChildren) {
                            // 跳过当前节点，直接渲染子节点
                            let html = '';
                            node.children.forEach(child => {
                                html += renderTreeNode(child, level);
                            });
                            return html;
                        }
                        
                        const icon = getNodeIcon(node.type);
                        const paramCount = hasParameters ? node.parameters.length : 0;
                        
                        let html = '<div class="tree-node" data-node-id="' + node.id + '" data-level="' + level + '">';
                        
                        // 展开/折叠按钮
                        if (hasChildren) {
                            html += '<div class="tree-node-expand">▶</div>';
                        } else {
                            html += '<div class="tree-node-expand"></div>';
                        }
                        
                        // 节点图标
                        html += '<div class="tree-node-icon">' + icon + '</div>';
                        
                        // 节点名称
                        html += '<div class="tree-node-name">' + escapeHtml(node.name) + '</div>';
                        
                        // 参数计数
                        if (paramCount > 0) {
                            html += '<div class="tree-node-count">(' + paramCount + ')</div>';
                        }
                        
                        html += '</div>';
                        
                        // 子节点
                        if (hasChildren) {
                            html += '<div class="tree-children" data-parent-id="' + node.id + '">';
                            node.children.forEach(child => {
                                html += renderTreeNode(child, level + 1);
                            });
                            html += '</div>';
                        }
                        
                        return html;
                    }

                    function getNodeIcon(type) {
                        switch (type) {
                            case 'root': return '🏠';
                            case 'module': return '📦';
                            case 'container': return '📁';
                            case 'parameter': return '⚙️';
                            default: return '📄';
                        }
                    }

                    function attachTreeEventListeners() {
                        document.querySelectorAll('.tree-node').forEach(node => {
                            node.addEventListener('click', function(e) {
                                e.stopPropagation();
                                
                                const expandBtn = this.querySelector('.tree-node-expand');
                                const isExpandClick = e.target === expandBtn;
                                const hasChildren = this.nextElementSibling && this.nextElementSibling.classList.contains('tree-children');
                                
                                if (isExpandClick && hasChildren) {
                                    // 展开/折叠
                                    const childrenDiv = this.nextElementSibling;
                                    const isExpanded = !childrenDiv.classList.contains('collapsed');
                                    
                                    if (isExpanded) {
                                        childrenDiv.classList.add('collapsed');
                                        expandBtn.classList.remove('expanded');
                                    } else {
                                        childrenDiv.classList.remove('collapsed');
                                        expandBtn.classList.add('expanded');
                                    }
                                } else {
                                    // 选择节点
                                    document.querySelectorAll('.tree-node').forEach(n => n.classList.remove('selected'));
                                    this.classList.add('selected');
                                    
                                    const nodeId = this.getAttribute('data-node-id');
                                    selectNode(nodeId);
                                }
                            });
                        });
                    }

                    function selectNode(nodeId) {
                        const node = findNodeById(currentTreeData, nodeId);
                        if (!node) return;
                        
                        selectedNode = node;
                        updateBreadcrumb(node);
                        updatePropertyPanel(node);
                    }

                    function updateBreadcrumb(node) {
                        const path = getNodePath(node);
                        const breadcrumb = document.getElementById('breadcrumb-container');
                        
                        let html = '<span class="breadcrumb-item">ARXML Configuration</span>';
                        
                        path.forEach((pathNode, index) => {
                            html += '<span class="breadcrumb-separator">▶</span>';
                            html += '<span class="breadcrumb-item" data-node-id="' + pathNode.id + '">' + escapeHtml(pathNode.name) + '</span>';
                        });
                        
                        breadcrumb.innerHTML = html;
                        
                        // 添加面包屑点击事件
                        breadcrumb.querySelectorAll('.breadcrumb-item[data-node-id]').forEach(item => {
                            item.addEventListener('click', function() {
                                const nodeId = this.getAttribute('data-node-id');
                                const nodeElement = document.querySelector('.tree-node[data-node-id="' + nodeId + '"]');
                                if (nodeElement) {
                                    nodeElement.click();
                                    nodeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                }
                            });
                        });
                    }

                    function getNodePath(targetNode) {
                        const path = [];
                        
                        function findPath(node, currentPath) {
                            if (node.id === targetNode.id) {
                                path.push(...currentPath, node);
                                return true;
                            }
                            
                            if (node.children) {
                                for (const child of node.children) {
                                    if (findPath(child, [...currentPath, node])) {
                                        return true;
                                    }
                                }
                            }
                            
                            return false;
                        }
                        
                        findPath(currentTreeData, []);
                        return path.slice(1); // 移除根节点
                    }

                    function updatePropertyPanel(node) {
                        const propertyContent = document.getElementById('property-content');
                        const propertyTitle = document.getElementById('property-title');
                        
                        propertyTitle.textContent = '⚙️ ' + node.name + ' Properties';
                        
                        if (!node.parameters || node.parameters.length === 0) {
                            propertyContent.innerHTML = '<div class="empty-state">No parameters to configure</div>';
                            return;
                        }
                        
                        let html = '<div class="property-form">';
                        html += '<div class="property-group">';
                        html += '<div class="property-group-title">Configuration Parameters</div>';
                        
                        node.parameters.forEach(param => {
                            // 调试日志输出
                            console.log('Rendering parameter:', param.name || param.shortName, {
                                configClasses: param.metadata?.configClasses || [],
                                displayType: getConfigTypeDisplay(param.metadata?.configClasses || [])
                            });
                            
                            html += renderParameterField(param);
                        });
                        
                        html += '</div>';
                        html += '</div>';
                        
                        propertyContent.innerHTML = html;
                        attachFormEventListeners();
                    }

                    function getConfigTypeDisplay(configClasses) {
                        /**
                         * 根据设计文档，显示规则：
                         * - 根据配置项选择显示哪种变体的配置类型
                         * - 支持的变体：VARIANT-POST-BUILD, VARIANT-PRE-COMPILE, VARIANT-LINK-TIME
                         * - 返回徽章HTML，而不是简单的文本
                         * - POST-BUILD → 蓝色徽章 "PB"
                         * - PRE-COMPILE → 绿色徽章 "PC"  
                         * - LINK-TIME → 橙色徽章 "LK"
                         * - LINK → 橙色徽章 "LK"
                         * - PUBLISHED-INFORMATION → 紫色徽章 "PI"
                         * - 找不到对应条目 → 不显示任何标记
                         */
                        if (!configClasses || configClasses.length === 0) {
                            return '';
                        }
                        
                        // 获取配置的变体类型（默认为 VARIANT-POST-BUILD）
                        const configVariant = window.arxmlSettings?.configVariantDisplay || 'VARIANT-POST-BUILD';
                        
                        // 查找指定变体的条目
                        const targetEntry = configClasses.find(entry => 
                            entry.variant === configVariant
                        );
                        
                        if (!targetEntry) {
                            return '';
                        }
                        
                        // 根据 class 值返回对应的徽章HTML
                        switch (targetEntry.class) {
                            case 'POST-BUILD':
                                return '<span class="config-badge pb">PB</span>';
                            case 'PRE-COMPILE':
                                return '<span class="config-badge pc">PC</span>';
                            case 'LINK-TIME':
                                return '<span class="config-badge lk">LK</span>';
                            case 'LINK':
                                return '<span class="config-badge lk">LK</span>';
                            case 'PUBLISHED-INFORMATION':
                                return '<span class="config-badge pi">PI</span>';
                            default:
                                return '';
                        }
                    }
                    
                    function buildTooltipContent(param, description, configClasses) {
                        /**
                         * 构建工具提示内容：
                         * 1. 参数的 description（描述）
                         * 2. 换行后显示 "Config Classes:"
                         * 3. 按照固定变体顺序显示class值，格式为 "POST-BUILD / PRE-COMPILE / LINK-TIME"
                         */
                        let tooltip = description || '';
                        
                        if (configClasses && configClasses.length > 0) {
                            if (tooltip) {
                                tooltip += '\\n\\n';
                            }
                            
                            const orderedVariants = ['VARIANT-POST-BUILD', 'VARIANT-PRE-COMPILE', 'VARIANT-LINK-TIME'];
                            const displayClasses = orderedVariants.map(variant => {
                                const entry = configClasses.find(c => c.variant === variant);
                                return entry ? entry.class : '-';
                            });
                            
                            tooltip += 'Config Classes:\\n';
                            tooltip += displayClasses.join(' / ');
                        }
                        
                        return tooltip;
                    }

                    function renderParameterField(param) {
                        const paramName = param.name || param.shortName || 'Unknown Parameter';
                        const paramValue = getEffectiveParamValue(param);
                        const paramType = param.type || 'string';
                        const description = param.description || param.metadata?.description || '';
                        const isRequired = param.required || false;
                        const configClasses = param.metadata?.configClasses || [];
                        
                        // 获取配置类型显示HTML
                        const configTypeDisplay = getConfigTypeDisplay(configClasses);
                        
                        // 构建工具提示内容
                        const tooltipContent = buildTooltipContent(param, description, configClasses);
                        
                        let html = '<div class="form-row" data-param-name="' + escapeHtml(paramName) + '">';
                        
                        // 参数名标签（现在包含徽章HTML），使用 data-tooltip
                        html += '<div class="form-label' + (isRequired ? ' required' : '') + '" data-tooltip="' + escapeHtml(tooltipContent) + '">';
                        html += escapeHtml(paramName);
                        if (configTypeDisplay) {
                            html += configTypeDisplay; // 直接添加HTML，不需要转义
                        }
                        html += '</div>';
                        
                        // 参数值
                        html += '<div class="form-value">';
                        
                        switch (paramType) {
                            case 'boolean':
                                html += '<label style="display: flex; align-items: center; font-size: 11px; margin: 0;">';
                                html += '<input type="checkbox" class="form-checkbox" ' + (paramValue === 'true' ? 'checked' : '') + '>';
                                html += 'Enabled';
                                html += '</label>';
                                break;
                                
                            case 'enum':
                                html += '<select class="form-select">';
                                html += '<option value="">Select...</option>';
                                const enumOptions = getEnumOptions(param);
                                enumOptions.forEach(option => {
                                    const selected = paramValue === option ? 'selected' : '';
                                    html += '<option value="' + escapeHtml(option) + '" ' + selected + '>' + escapeHtml(option) + '</option>';
                                });
                                html += '</select>';
                                break;
                                
                            case 'number':
                                html += '<input type="number" class="form-input" value="' + escapeHtml(paramValue) + '" placeholder="0">';
                                break;
                                
                            default: // string
                                html += '<input type="text" class="form-input" value="' + escapeHtml(paramValue) + '" placeholder="">';
                                break;
                        }
                        
                        html += '</div>';
                        html += '</div>';
                        
                        return html;
                    }
                    
                    function normalizeToString(value) {
                        if (value === undefined || value === null) return '';
                        return String(value);
                    }
                    
                    function getEffectiveParamValue(param) {
                        const currentValue = normalizeToString(param?.value);
                        if (currentValue !== '') return currentValue;
                        const defaultValue = normalizeToString(param?.default ?? param?.metadata?.defaultValue ?? param?.metadata?.default);
                        return defaultValue;
                    }
                    
                    function getEnumOptions(param) {
                        const options = [];
                        const seen = new Set();
                        
                        const add = (v) => {
                            const s = normalizeToString(v);
                            if (!s || seen.has(s)) return;
                            seen.add(s);
                            options.push(s);
                        };
                        
                        const lists = [
                            param?.metadata?.enumValues,
                            param?.constraints?.enumValues,
                            param?.constraints?.values,
                            param?.constraints?.allowedValues
                        ];
                        
                        lists.forEach(list => {
                            if (!Array.isArray(list)) return;
                            list.forEach(add);
                        });
                        
                        add(param?.value);
                        add(param?.default);
                        add(param?.metadata?.defaultValue);
                        add(param?.metadata?.default);
                        
                        return options;
                    }

                    function attachFormEventListeners() {
                        // 添加表单输入事件监听器
                        document.querySelectorAll('.form-input, .form-select, .form-checkbox').forEach(input => {
                            input.addEventListener('change', function() {
                                const row = this.closest('.form-row');
                                const paramName = row.getAttribute('data-param-name');
                                let value = this.value;
                                
                                if (this.type === 'checkbox') {
                                    value = this.checked ? 'true' : 'false';
                                }
                                
                                // 更新参数值并保存到文档
                                updateParameterValue(paramName, value);
                                
                                // 标记为已修改
                                row.classList.add('modified');
                                
                                // 显示保存状态
                                showSaveStatus('正在保存...');
                            });
                            
                            // 添加实时验证
                            input.addEventListener('input', function() {
                                const row = this.closest('.form-row');
                                validateParameterInput(this, row);
                            });
                        });
                        
                        // 添加tooltip功能
                        document.querySelectorAll('.form-label[title]').forEach(label => {
                            const tooltip = label.getAttribute('title');
                            if (!tooltip || tooltip.trim() === '') return;
                            
                            // 创建tooltip元素
                            const tooltipElement = document.createElement('div');
                            tooltipElement.className = 'tooltip';
                            // 使用innerHTML来支持换行显示
                            tooltipElement.innerHTML = tooltip.replace(/\\n/g, '<br>');
                            label.parentElement.appendChild(tooltipElement);
                            
                            // 移除原始title属性，避免浏览器默认tooltip
                            label.removeAttribute('title');
                            
                            let hoverTimeout;
                            
                            label.addEventListener('mouseenter', function(e) {
                                clearTimeout(hoverTimeout);
                                hoverTimeout = setTimeout(() => {
                                    const rect = label.getBoundingClientRect();
                                    const containerRect = label.closest('.property-content').getBoundingClientRect();
                                    
                                    tooltipElement.style.left = (rect.left - containerRect.left) + 'px';
                                    tooltipElement.style.top = (rect.bottom - containerRect.top + 5) + 'px';
                                    tooltipElement.classList.add('show');
                                }, 500); // 延迟500ms显示
                            });
                            
                            label.addEventListener('mouseleave', function() {
                                clearTimeout(hoverTimeout);
                                tooltipElement.classList.remove('show');
                            });
                            
                            // 点击label时也隐藏tooltip
                            label.addEventListener('click', function() {
                                tooltipElement.classList.remove('show');
                            });
                        });
                    }

                    function updateParameterValue(paramName, newValue) {
                        if (!selectedNode || !selectedNode.parameters) return;
                        
                        // 查找并更新参数
                        const param = selectedNode.parameters.find(p => 
                            (p.name === paramName) || (p.shortName === paramName)
                        );
                        
                        if (param) {
                            const oldValue = param.value;
                            param.value = newValue;
                            
                            // 发送更新到VSCode
                            vscode.postMessage({
                                type: 'parameterChanged',
                                data: {
                                    nodeId: selectedNode.id,
                                    paramName: paramName,
                                    oldValue: oldValue,
                                    newValue: newValue,
                                    nodePath: getNodePath(selectedNode).map(n => n.name).join(' > ')
                                }
                            });
                            
                            // 调试日志输出
                            console.log('Parameter updated:', paramName, ':', oldValue, '->', newValue);
                            console.log('Parameter configClasses:', param.metadata?.configClasses || []);
                            console.log('Selected config type:', getConfigTypeDisplay(param.metadata?.configClasses || []));
                        }
                    }

                    function validateParameterInput(input, row) {
                        const paramName = row.getAttribute('data-param-name');
                        const value = input.value;
                        let isValid = true;
                        let errorMessage = '';
                        
                        // 移除之前的错误状态
                        row.classList.remove('error');
                        const existingError = row.querySelector('.error-message');
                        if (existingError) existingError.remove();
                        
                        // 根据输入类型进行验证
                        if (input.type === 'number') {
                            if (value && isNaN(Number(value))) {
                                isValid = false;
                                errorMessage = '请输入有效的数字';
                            }
                        } else if (input.type === 'text') {
                            // 可以添加更多文本验证规则
                            if (value.length > 255) {
                                isValid = false;
                                errorMessage = '文本长度不能超过255个字符';
                            }
                        }
                        
                        if (!isValid) {
                            row.classList.add('error');
                            const errorDiv = document.createElement('div');
                            errorDiv.className = 'error-message';
                            errorDiv.textContent = errorMessage;
                            row.appendChild(errorDiv);
                        }
                        
                        return isValid;
                    }

                    function showSaveStatus(message, type = 'info') {
                        // 创建或更新状态提示
                        let statusDiv = document.getElementById('save-status');
                        if (!statusDiv) {
                            statusDiv = document.createElement('div');
                            statusDiv.id = 'save-status';
                            statusDiv.className = 'save-status';
                            document.body.appendChild(statusDiv);
                        }
                        
                        statusDiv.textContent = message;
                        statusDiv.className = 'save-status ' + type;
                        statusDiv.style.display = 'block';
                        
                        // 自动隐藏
                        setTimeout(() => {
                            statusDiv.style.display = 'none';
                        }, 3000);
                    }

                    function resetParameterModifications() {
                        // 移除所有修改标记
                        document.querySelectorAll('.form-row.modified').forEach(row => {
                            row.classList.remove('modified');
                        });
                        
                        // 移除所有错误状态
                        document.querySelectorAll('.form-row.error').forEach(row => {
                            row.classList.remove('error');
                            const errorMsg = row.querySelector('.error-message');
                            if (errorMsg) errorMsg.remove();
                        });
                    }

                    function autoExpandTree() {
                        document.querySelectorAll('.tree-node-expand').forEach(expand => {
                            const childrenDiv = expand.parentElement.nextElementSibling;
                            if (childrenDiv && childrenDiv.classList.contains('tree-children')) {
                                childrenDiv.classList.remove('collapsed');
                                expand.classList.add('expanded');
                            }
                        });
                    }

                    function setDefaultSelection(moduleNodes) {
                        if (moduleNodes.length === 0) return;
                        
                        for (const module of moduleNodes) {
                            const firstContainer = findFirstContainer(module);
                            if (firstContainer) {
                                setTimeout(() => {
                                    const nodeElement = document.querySelector('.tree-node[data-node-id="' + firstContainer.id + '"]');
                                    if (nodeElement) {
                                        nodeElement.click();
                                        nodeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                                    }
                                }, 200);
                                return;
                            }
                        }
                    }

                    function findFirstContainer(node) {
                        if (!node) return null;
                        
                        if (node.children && node.children.length > 0) {
                            for (const child of node.children) {
                                if (isContainerType(child.type)) {
                                    return child;
                                }
                                const found = findFirstContainer(child);
                                if (found) return found;
                            }
                        }
                        
                        return null;
                    }

                    function isContainerType(type) {
                        return ['container', 'root', 'package', 'module'].includes(type);
                    }

                    function findNodeById(tree, nodeId) {
                        if (!tree) return null;
                        if (tree.id === nodeId) return tree;
                        
                        if (tree.children) {
                            for (const child of tree.children) {
                                const found = findNodeById(child, nodeId);
                                if (found) return found;
                            }
                        }
                        
                        return null;
                    }

                    function expandAllNodes() {
                        document.querySelectorAll('.tree-children').forEach(children => {
                            children.classList.remove('collapsed');
                        });
                        document.querySelectorAll('.tree-node-expand').forEach(expand => {
                            expand.classList.add('expanded');
                        });
                    }

                    function collapseAllNodes() {
                        document.querySelectorAll('.tree-children').forEach(children => {
                            children.classList.add('collapsed');
                        });
                        document.querySelectorAll('.tree-node-expand').forEach(expand => {
                            expand.classList.remove('expanded');
                        });
                    }

                    function escapeHtml(text) {
                        const div = document.createElement('div');
                        div.textContent = text;
                        return div.innerHTML;
                    }

                    function isStructuralNode(nodeName) {
                        const structuralNames = [
                            'CONTAINERS', 'SUB-CONTAINERS', 'ELEMENTS', 
                            'PARAMETER-VALUES', 'PARAMETERS', 'ECUC-CONTAINER-VALUE'
                        ];
                        return structuralNames.includes(nodeName.toUpperCase());
                    }

                    function handleSaveStatus(status, message) {
                        if (status === 'success') {
                            showSaveStatus(message, 'success');
                        } else if (status === 'error') {
                            showSaveStatus(message, 'error');
                        }
                    }
                </script>
            </body>
            </html>
        `;
    }

    private async updateWebview(webview: vscode.Webview, uri: vscode.Uri) {
        try {
            console.log('Updating webview for:', uri.fsPath);
            
            // 首先尝试使用Python后端解析
            try {
                console.log('尝试使用Python后端解析...');
                vscode.window.showInformationMessage('🐍 正在调用Python后端解析ARXML文件...');
                
            const result = await this.treeDataService.parseFile(uri.fsPath);
                
            if (result.success && result.treeStructure) {
                    console.log('Python后端解析成功');
                    vscode.window.showInformationMessage('✅ Python后端解析成功！');
                
                // 获取配置信息
                const config = vscode.workspace.getConfiguration('arxmlTreePreviewer');
                const configVariantDisplay = config.get<string>('configVariantDisplay', 'VARIANT-POST-BUILD');
                
                // 发送数据更新消息
                webview.postMessage({
                    type: 'update',
                        data: {
                            tree: result.treeStructure,
                            filePath: result.filePath,
                            fileType: result.fileType,
                            metadata: result.metadata
                        }
                });
                
                // 发送配置信息
                webview.postMessage({
                    type: 'settings',
                    settings: {
                        configVariantDisplay: configVariantDisplay
                    }
                });
                
                    return;
            } else {
                    console.log('Python后端解析失败，降级到基本预览:', result.error);
                    vscode.window.showWarningMessage(`❌ Python后端解析失败: ${result.error || '未知错误'}`);
                    // 继续执行降级逻辑
                }
            } catch (backendError) {
                console.log('Python后端调用异常，降级到基本预览:', backendError);
                vscode.window.showWarningMessage(`❌ Python后端调用异常: ${backendError}`);
                // 继续执行降级逻辑
            }
            
            // 降级到基本文件预览
            console.log('使用基本文件预览');
            const fileStats = await fs.promises.stat(uri.fsPath);
            const fileExtension = path.extname(uri.fsPath).toLowerCase();
            
            // 读取文件前1000个字符作为预览
            const fileContent = await fs.promises.readFile(uri.fsPath, 'utf8');
            const preview = fileContent.length > 1000 
                ? fileContent.substring(0, 1000) + '\n\n... (文件内容已截断，显示前1000个字符)'
                : fileContent;
            
                webview.postMessage({
                    type: 'update',
                data: { 
                    fileInfo: {
                        path: uri.fsPath,
                        size: fileStats.size,
                        type: fileExtension === '.arxml' ? 'ARXML' : 
                              fileExtension === '.xdm' ? 'XDM' : 'XML',
                        preview: preview
                    },
                    backendWarning: 'Python后端解析失败，使用基本文件预览。可查看输出面板了解详情。'
                }
                });
            
        } catch (error) {
            console.error('Error updating webview:', error);
            webview.postMessage({
                type: 'update',
                data: { error: `读取文件失败: ${error}` }
            });
        }
    }

    private async handleParameterChanged(document: vscode.TextDocument, data: any): Promise<void> {
        try {
            // 记录参数变更
            console.log('Parameter changed:', data);
            
            // 这里我们需要更新XML文档中的实际参数值
            const edit = new vscode.WorkspaceEdit();
            const currentText = document.getText();
            
            // 简单的参数替换逻辑（实际应用中需要更复杂的XML解析和替换）
            // 这里先实现一个基础版本，后续可以改进
            const updatedText = await this.updateXMLParameter(currentText, data);
            
            if (updatedText !== currentText) {
                const fullRange = new vscode.Range(
                    document.positionAt(0),
                    document.positionAt(currentText.length)
                );
                
                edit.replace(document.uri, fullRange, updatedText);
                
                // 应用编辑
                const success = await vscode.workspace.applyEdit(edit);
                
                if (success) {
                    // 通知webview保存成功
                    this.currentWebview?.postMessage({
                        type: 'saveStatus',
                        status: 'success',
                        message: '参数已保存'
                    });
                    
                    console.log('Parameter saved successfully:', data.paramName);
                } else {
                    throw new Error('Failed to apply edit');
                }
            }
            
        } catch (error) {
            console.error('Error handling parameter change:', error);
            
            // 通知webview保存失败
            this.currentWebview?.postMessage({
                type: 'saveStatus',
                status: 'error',
                message: '参数保存失败: ' + (error as Error).message
            });
            
            vscode.window.showErrorMessage(`参数保存失败: ${(error as Error).message}`);
        }
    }

    private async updateXMLParameter(xmlContent: string, data: any): Promise<string> {
        // 这是一个简化的XML参数更新实现
        // 实际应用中应该使用更专业的XML解析器
        
        const { paramName, newValue, oldValue } = data;
        
        // 尝试找到参数定义并替换值
        // 这里使用正则表达式进行简单替换，实际应用中需要更精确的XML操作
        
        // 匹配 <PARAMETER-NAME>paramName</PARAMETER-NAME> 后面的 <VALUE>oldValue</VALUE>
        const parameterPattern = new RegExp(
            `(<PARAMETER-NAME>${escapeRegExp(paramName)}</PARAMETER-NAME>[\\s\\S]*?<VALUE>)${escapeRegExp(oldValue)}(</VALUE>)`,
            'gi'
        );
        
        if (parameterPattern.test(xmlContent)) {
            return xmlContent.replace(parameterPattern, `$1${newValue}$2`);
        }
        
        // 如果上面的模式不匹配，尝试其他常见的ARXML参数格式
        const alternativePattern = new RegExp(
            `(shortName="${escapeRegExp(paramName)}"[\\s\\S]*?<VALUE>)${escapeRegExp(oldValue)}(</VALUE>)`,
            'gi'
        );
        
        if (alternativePattern.test(xmlContent)) {
            return xmlContent.replace(alternativePattern, `$1${newValue}$2`);
        }
        
        // 如果都不匹配，返回原内容（可能需要更复杂的解析）
        console.warn('Could not find parameter in XML content:', paramName);
        return xmlContent;
    }

    private async saveDocument(document: vscode.TextDocument): Promise<void> {
        try {
            await document.save();
            
            this.currentWebview?.postMessage({
                type: 'saveStatus',
                status: 'success',
                message: '文档已保存'
            });
            
        } catch (error) {
            console.error('Error saving document:', error);
            
            this.currentWebview?.postMessage({
                type: 'saveStatus',
                status: 'error',
                message: '文档保存失败: ' + (error as Error).message
            });
        }
    }
}

// 辅助函数：转义正则表达式特殊字符
function escapeRegExp(string: string): string {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
