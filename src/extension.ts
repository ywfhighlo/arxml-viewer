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

export function deactivate() {
    console.log('👋 ARXML Viewer extension deactivated');
}
