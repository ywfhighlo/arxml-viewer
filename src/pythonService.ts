import * as vscode from 'vscode';
import * as path from 'path';
import { spawn } from 'child_process';

type ConversionType = 'md-to-docx' | 'md-to-pdf' | 'md-to-html' | 'office-to-md' | 'diagram-to-png';

interface PythonResponse {
    success: boolean;
    outputFiles?: string[];
    error?: string;
}

/**
 * 执行 Python 后端脚本进行文件转换
 */
export function executePythonScript(
    sourcePath: string,
    conversionType: ConversionType,
    outputDir: string,
    context: vscode.ExtensionContext,
    conversionOptions?: any
): Promise<PythonResponse> {
    
    return new Promise((resolve, reject) => {
        // Python 脚本路径
        const scriptPath = path.join(context.extensionPath, 'backend', 'cli.py');
        
        // 获取 Python 路径配置，并根据操作系统智能选择默认值
        const config = vscode.workspace.getConfiguration('markdown-docs-converter');
        const isWindows = process.platform === 'win32';
        const defaultPythonCommand = isWindows ? 'python' : 'python3';
        const pythonPath = config.get<string>('pythonPath', defaultPythonCommand);

        const args = [
            scriptPath,
            '--conversion-type', conversionType,
            '--input-path', sourcePath,
            '--output-dir', outputDir
        ];
        
        // 添加转换选项参数（对DOCX和PDF转换有效）
        if (conversionOptions && (conversionType === 'md-to-docx' || conversionType === 'md-to-pdf')) {
            if (conversionOptions.useTemplate === false) {
                // 如果不使用模板，明确传递空模板路径
                args.push('--template-path', '');
            } else if (conversionOptions.templatePath) {
                // 如果指定了自定义模板路径
                args.push('--template-path', conversionOptions.templatePath);
            }
            // 如果 useTemplate 为 true 但 templatePath 为空，则不传递 --template-path，由后端决定使用默认模板

            // 添加项目信息参数
            if (conversionOptions.projectName) {
                args.push('--project-name', conversionOptions.projectName);
            }
            if (conversionOptions.author) {
                args.push('--author', conversionOptions.author);
            }
            if (conversionOptions.email) {
                args.push('--email', conversionOptions.email);
            }
            if (conversionOptions.mobilephone) {
                args.push('--mobilephone', conversionOptions.mobilephone);
            }
            
            // 添加标题提升参数
            if (conversionOptions.promoteHeadings) {
                args.push('--promote-headings');
            }
        }
        
        console.log(`执行命令: ${pythonPath} ${args.join(' ')}`);

        const pyProcess = spawn(pythonPath, args);

        let stdout = '';
        let stderr = '';

        pyProcess.stdout.on('data', (data) => {
            stdout += data.toString();
        });

        pyProcess.stderr.on('data', (data) => {
            stderr += data.toString();
        });

        pyProcess.on('close', (code) => {
            if (code === 0) {
                try {
                    // 解析 Python 脚本返回的 JSON 成功结果
                    const response: PythonResponse = JSON.parse(stdout.trim());
                    resolve(response);
                } catch (e: any) {
                    reject({ 
                        success: false, 
                        error: `无法解析 Python 脚本成功输出：${e.message}\n输出内容：${stdout}` 
                    });
                }
            } else {
                // 当脚本以非零代码退出时，记录所有输出以供诊断
                console.error(`Python script exited with code: ${code}`);
                console.error("--- STDOUT ---");
                console.error(stdout);
                console.error("--- STDERR ---");
                console.error(stderr);
                
                // 优先尝试解析 stdout，因为它可能包含详细的 JSON 错误报告
                try {
                    const errorResponse: PythonResponse = JSON.parse(stdout.trim());
                    reject(errorResponse); // 即使成功解析，也将其视为一个错误并拒绝
                } catch (e) {
                    // 如果解析 stdout 失败，则回退到使用 stderr 或退出代码
                    reject({ 
                        success: false, 
                        error: stderr || `Python 脚本退出，代码：${code}` 
                    });
                }
            }
        });

        pyProcess.on('error', (err) => {
            reject({ 
                success: false, 
                error: `无法启动 Python 脚本：${err.message}` 
            });
        });
    });
}

 