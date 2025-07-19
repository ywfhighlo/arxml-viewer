import * as vscode from 'vscode';
import { ArxmlCustomEditorProvider } from './customEditor';
import * as path from 'path';

export async function activate(context: vscode.ExtensionContext) {
    console.log('🚀 ARXML Viewer extension is starting...');
    console.log('📁 Extension path:', context.extensionPath);
    
    // 立即显示激活消息以确保能看到
    // vscode.window.showInformationMessage('🎉 ARXML Viewer 插件正在激活...');

    try {
        // 注册自定义编辑器提供者
        const customEditorProvider = new ArxmlCustomEditorProvider(context);
        const customEditorDisposable = vscode.window.registerCustomEditorProvider(
            'arxmlTreePreview',
            customEditorProvider,
            {
                webviewOptions: {
                    retainContextWhenHidden: true,
                },
                supportsMultipleEditorsPerDocument: false,
            }
        );
        console.log('✅ Custom editor provider registered successfully');

        // 注册文件打开监听器，实现双击文件时自动双标签页打开
        const fileOpenListener = vscode.workspace.onDidOpenTextDocument(async (document) => {
            const fileExtension = path.extname(document.fileName).toLowerCase();
            const config = vscode.workspace.getConfiguration('arxmlTreePreviewer');
            const enableDualTabs = config.get<boolean>('enableDualTabs', true);
            
            if (enableDualTabs && ['.arxml', '.xdm', '.xml', '.bmd'].includes(fileExtension)) {
                // 检查是否已经有相同文件打开，避免重复打开
                const existingTabs = vscode.window.tabGroups.all.flatMap(group => group.tabs);
                const hasPreviewTab = existingTabs.some(tab => 
                    tab.input instanceof vscode.TabInputCustom && 
                    tab.input.uri.fsPath === document.uri.fsPath &&
                    tab.input.viewType === 'arxmlTreePreview'
                );
                const hasTextTab = existingTabs.some(tab => 
                    tab.input instanceof vscode.TabInputText && 
                    tab.input.uri.fsPath === document.uri.fsPath
                );
                
                // 如果两个视图都不存在，才执行双标签页打开
                if (!hasPreviewTab || !hasTextTab) {
                    setTimeout(async () => {
                        try {
                            await openDualTabs(document.uri);
                        } catch (error) {
                            console.log('双标签页打开失败，降级到单标签页:', error);
                        }
                    }, 100);
                }
            }
        });

        // 注册命令处理器，用于打开文件时创建双标签页
        const openWithDualTabsCommand = vscode.commands.registerCommand('arxml.openWithDualTabs', async (uri?: vscode.Uri) => {
            if (!uri && vscode.window.activeTextEditor) {
                uri = vscode.window.activeTextEditor.document.uri;
            }

            if (uri) {
                try {
                    await openDualTabs(uri);
                } catch (error) {
                    console.error('❌ Error opening with dual tabs:', error);
                    vscode.window.showErrorMessage(`双标签页打开失败: ${error}`);
                }
            }
        });

        // 注册命令
        const openToSideCommand = vscode.commands.registerCommand('arxml.openToSide', async (uri?: vscode.Uri) => {
            console.log('🚀 arxml.openToSide command executed!', uri?.fsPath);
            
            if (!uri && vscode.window.activeTextEditor) {
                uri = vscode.window.activeTextEditor.document.uri;
            }

            if (uri) {
                try {
                    console.log('📂 File extension:', path.extname(uri.fsPath));
                    console.log('📂 File path:', uri.fsPath);
                    
                    // 直接打开自定义编辑器
                    console.log('🔧 Opening with custom editor...');
                    await vscode.commands.executeCommand('vscode.openWith', uri, 'arxmlTreePreview', vscode.ViewColumn.Beside);
                    
                    // vscode.window.showInformationMessage(`✅ 已在侧边打开ARXML树形预览: ${uri.fsPath}`);
                } catch (error) {
                    console.error('❌ Error opening to side:', error);
                    vscode.window.showErrorMessage(`在侧边打开文件失败: ${error}`);
                }
            } else {
                vscode.window.showErrorMessage('❌ 没有可打开的文件');
            }
        });

        const openTreePreviewCommand = vscode.commands.registerCommand('arxml.openTreePreview', async (uri?: vscode.Uri) => {
            if (!uri && vscode.window.activeTextEditor) {
                uri = vscode.window.activeTextEditor.document.uri;
            }

            if (uri) {
                try {
                    await vscode.commands.executeCommand('vscode.openWith', uri, 'arxmlTreePreview');
                    // vscode.window.showInformationMessage(`✅ 已打开ARXML树形预览: ${uri.fsPath}`);
                } catch (error) {
                    console.error('❌ Error opening tree preview:', error);
                    vscode.window.showErrorMessage(`打开树形预览失败: ${error}`);
                }
            } else {
                vscode.window.showErrorMessage('❌ 没有可打开的文件');
            }
        });

        const testCustomEditorCommand = vscode.commands.registerCommand('arxml.testCustomEditor', async () => {
            const activeEditor = vscode.window.activeTextEditor;
            if (!activeEditor) {
                vscode.window.showErrorMessage('❌ 请先打开一个ARXML文件');
                return;
            }
            
            const uri = activeEditor.document.uri;
            console.log('🧪 Testing custom editor with file:', uri.fsPath);
            
            try {
                await vscode.commands.executeCommand('vscode.openWith', uri, 'arxmlTreePreview', vscode.ViewColumn.Beside);
                // vscode.window.showInformationMessage(`✅ 自定义编辑器测试成功: ${uri.fsPath}`);
            } catch (error) {
                console.error('❌ Custom editor test failed:', error);
                vscode.window.showErrorMessage(`自定义编辑器测试失败: ${error}`);
            }
        });

        // 添加展开/折叠命令
        const expandAllCommand = vscode.commands.registerCommand('arxml.expandAll', () => {
            // 通过消息传递给当前活动的自定义编辑器
            const activeEditor = vscode.window.activeTextEditor;
            if (activeEditor && activeEditor.document.uri.toString().includes('arxmlTreePreview')) {
                // 如果当前是自定义编辑器，发送展开消息
                customEditorProvider.expandAll();
                // vscode.window.showInformationMessage('📂 正在展开所有节点...');
            } else {
                vscode.window.showWarningMessage('⚠️ 请先打开ARXML树形预览');
            }
        });

        const collapseAllCommand = vscode.commands.registerCommand('arxml.collapseAll', () => {
            // 通过消息传递给当前活动的自定义编辑器
            const activeEditor = vscode.window.activeTextEditor;
            if (activeEditor && activeEditor.document.uri.toString().includes('arxmlTreePreview')) {
                // 如果当前是自定义编辑器，发送折叠消息
                customEditorProvider.collapseAll();
                // vscode.window.showInformationMessage('📁 正在折叠所有节点...');
            } else {
                vscode.window.showWarningMessage('⚠️ 请先打开ARXML树形预览');
            }
        });

        const refreshPreviewCommand = vscode.commands.registerCommand('arxml.refreshPreview', () => {
            // 刷新当前自定义编辑器
            const activeEditor = vscode.window.activeTextEditor;
            if (activeEditor && activeEditor.document.uri.toString().includes('arxmlTreePreview')) {
                customEditorProvider.refresh();
                // vscode.window.showInformationMessage('🔄 预览已刷新');
            } else {
                vscode.window.showWarningMessage('⚠️ 请先打开ARXML树形预览');
            }
        });

        // 监听配置变化
        const configChangeListener = vscode.workspace.onDidChangeConfiguration(event => {
            if (event.affectsConfiguration('arxmlTreePreviewer.configVariantDisplay')) {
                console.log('Configuration changed: configVariantDisplay');
                // 通知自定义编辑器更新配置
                customEditorProvider.updateSettings();
            }
        });

        // 添加所有订阅
        context.subscriptions.push(
            customEditorDisposable,
            fileOpenListener,
            openWithDualTabsCommand,
            openToSideCommand,
            openTreePreviewCommand,
            testCustomEditorCommand,
            expandAllCommand,
            collapseAllCommand,
            refreshPreviewCommand,
            configChangeListener
        );
    
        console.log('✅ All providers and commands registered successfully');
        // vscode.window.showInformationMessage('🎉 ARXML Viewer 插件已激活！右键ARXML文件选择"在侧边打开ARXML预览"');
        
    } catch (error) {
        console.error('❌ Error during activation:', error);
        vscode.window.showErrorMessage(`插件激活失败: ${error}`);
    }
}

async function openDualTabs(uri: vscode.Uri): Promise<void> {
    try {
        console.log('🔄 正在打开双标签页:', uri.fsPath);
        
        const column = vscode.window.activeTextEditor ? vscode.window.activeTextEditor.viewColumn : vscode.ViewColumn.One;

        // 步骤1: 在当前标签页组中打开原始文本文件。
        // 我们不希望这个标签页成为焦点，所以我们稍后会打开预览。
        await vscode.window.showTextDocument(uri, {
            preview: false,
            viewColumn: column
        });

        // 步骤2: 在同一个标签页组中打开自定义预览视图。
        // 这将会成为活动标签页。
        await vscode.commands.executeCommand('vscode.openWith', uri, 'arxmlTreePreview', column);
        
        console.log('✅ 双标签页打开成功 - 预览和原始文件在同一个标签组中。');
        
    } catch (error) {
        console.error('❌ 双标签页打开失败:', error);
        throw error;
    }
}

export function deactivate() {
    console.log('👋 ARXML Viewer extension deactivated');
}
