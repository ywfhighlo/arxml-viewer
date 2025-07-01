import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { executePythonScript } from './pythonService';

type ConversionType = 'md-to-docx' | 'md-to-pdf' | 'md-to-html' | 'md-to-pptx' | 'office-to-md' | 'diagram-to-png';

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
            // 获取输出目录配置
            const configOutputDir = config.get<string>('outputDirectory', './converted');
            const outputDir = path.isAbsolute(configOutputDir) 
                ? configOutputDir 
                : path.join(path.dirname(sourcePath), configOutputDir);

            // 确保输出目录存在
            if (!fs.existsSync(outputDir)) {
                fs.mkdirSync(outputDir, { recursive: true });
            }
            
            let conversionOptions: any = null;

            if (['md-to-docx', 'md-to-pdf', 'md-to-pptx'].includes(conversionType)) {
                const sharedOptions = {
                    projectName: config.get<string>('projectName', ''),
                    author: config.get<string>('author', ''),
                    email: config.get<string>('email', ''),
                    mobilephone: config.get<string>('mobilephone', ''),
                    promoteHeadings: config.get<boolean>('promoteHeadings', true)
                };
                conversionOptions = { ...sharedOptions };

                if (conversionType === 'md-to-docx' || conversionType === 'md-to-pdf') {
                    if (config.get<boolean>('useDocxTemplate', true)) {
                        let templatePath = config.get<string>('docxTemplatePath', '');
                        if (!templatePath) {
                            templatePath = path.join(context.extensionPath, 'backend', 'converters', 'templates', 'template.docx');
                        }
                        conversionOptions.templatePath = templatePath;
                    }
                } else if (conversionType === 'md-to-pptx') {
                    if (config.get<boolean>('usePptxTemplate', true)) {
                        let templatePath = config.get<string>('pptxTemplatePath', '');
                        if (!templatePath) {
                            templatePath = path.join(context.extensionPath, 'backend', 'converters', 'templates', 'template.pptx');
                        }
                        conversionOptions.templatePath = templatePath;
                    }
                }
            } else if (conversionType === 'office-to-md') {
                conversionOptions = {
                    popplerPath: config.get<string>('popplerPath', '')
                };
            }
            
            const result = await executePythonScript(
                sourcePath, 
                conversionType, 
                outputDir, 
                context, 
                conversionOptions,
                (message: string, percentage?: number) => {
                    progress.report({ 
                        message,
                        increment: percentage !== undefined 
                            ? percentage - (progress as any).value || 0 
                            : undefined
                    });
                }
            );

            if (result.success) {
                const outputFiles = result.outputFiles || [];
                if (outputFiles.length > 0) {
                    const message = outputFiles.length === 1
                        ? `转换完成：${path.basename(outputFiles[0])}`
                        : `成功转换 ${outputFiles.length} 个文件`;
                    
                    vscode.window.showInformationMessage(message, '打开文件夹').then(selection => {
                        if (selection === '打开文件夹') {
                            vscode.commands.executeCommand('revealFileInOS', vscode.Uri.file(outputDir));
                        }
                    });
                }
            } else {
                // 如果 result.error 本身就是错误详情，直接抛出
                throw new Error(result.error || '转换失败，发生未知错误');
            }
        } catch (error: any) {
            // 确保我们显示的是一个字符串
            const errorMessage = (error.message || error).toString();
            vscode.window.showErrorMessage(`转换失败：${errorMessage}`);
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

 