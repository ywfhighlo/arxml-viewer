import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { executePythonScript } from './pythonService';

type ConversionType = 'md-to-docx' | 'md-to-pdf' | 'md-to-html' | 'office-to-md' | 'diagram-to-png';

/**
 * 处理所有转换命令的核心逻辑
 */
export async function handleConvertCommand(
    resourceUri: vscode.Uri, 
    conversionType: ConversionType, 
    context: vscode.ExtensionContext
) {
    if (!resourceUri) {
        vscode.window.showErrorMessage('无法执行转换：未选择文件或文件夹。');
        return;
    }

    const sourcePath = resourceUri.fsPath;
    const config = vscode.workspace.getConfiguration('markdown-hub');
    
    vscode.window.withProgress({
        location: vscode.ProgressLocation.Notification,
        title: `正在转换 ${path.basename(sourcePath)}`,
        cancellable: false
    }, async (progress) => {
        try {
            progress.report({ message: '开始转换...' });

            // 获取输出目录配置
            const configOutputDir = config.get<string>('outputDirectory', './converted');
            const outputDir = path.isAbsolute(configOutputDir) 
                ? configOutputDir 
                : path.join(path.dirname(sourcePath), configOutputDir);

            // 确保输出目录存在
            if (!fs.existsSync(outputDir)) {
                fs.mkdirSync(outputDir, { recursive: true });
            }

            progress.report({ message: '调用转换引擎...' });
            
            // 获取模板配置（仅对DOCX和PDF转换有效）
            let conversionOptions = null;
            if (conversionType === 'md-to-docx' || conversionType === 'md-to-pdf') {
                const useTemplate = config.get<boolean>('useTemplate', true);
                const templatePath = config.get<string>('templatePath', '');
                const projectName = config.get<string>('projectName', '');
                const author = config.get<string>('author', '');
                const email = config.get<string>('email', '');
                const mobilephone = config.get<string>('mobilephone', '');
                const promoteHeadings = config.get<boolean>('promoteHeadings', true);
                
                conversionOptions = {
                    useTemplate,
                    templatePath,
                    projectName,
                    author,
                    email,
                    mobilephone,
                    promoteHeadings
                };
            }
            
            const result = await executePythonScript(sourcePath, conversionType, outputDir, context, conversionOptions);

            if (result.success) {
                const message = result.outputFiles && result.outputFiles.length > 0
                    ? `转换成功！生成了 ${result.outputFiles.length} 个文件。`
                    : '转换成功！';
                
                const actions = ['打开文件夹', '查看详情'];
                const selection = await vscode.window.showInformationMessage(message, ...actions);
                
                if (selection === '打开文件夹') {
                    vscode.env.openExternal(vscode.Uri.file(outputDir));
                } else if (selection === '查看详情' && result.outputFiles) {
                    const fileList = result.outputFiles.map(f => `• ${path.basename(f)}`).join('\n');
                    vscode.window.showInformationMessage(`生成的文件：\n${fileList}`);
                }
            } else {
                vscode.window.showErrorMessage(`转换失败：${result.error}`);
            }
        } catch (error: any) {
            const errorMessage = error.error || error.message || '未知错误，请查看输出面板获取更多信息';
            vscode.window.showErrorMessage(`发生意外错误：${errorMessage}`);
        }
    });
}

/**
 * 打开模板设置页面
 */
export async function handleOpenTemplateSettingsCommand() {
    // 打开VS Code设置页面，并定位到模板相关设置
    await vscode.commands.executeCommand('workbench.action.openSettings', '@ext:ywfhighlo.markdown-hub template');
}

 