import * as vscode from 'vscode';
import * as path from 'path';
import { spawn } from 'child_process';

type ConversionType = 'md-to-docx' | 'md-to-pdf' | 'md-to-html' | 'md-to-pptx' | 'office-to-md' | 'diagram-to-png';

interface PythonResponse {
    success: boolean;
    outputFiles?: string[];
    error?: string;
}

interface ProgressInfo {
    type: 'progress';
    stage: string;
    percentage?: number;
}

interface ResultInfo {
    type: 'result';
    success: boolean;
    outputFiles?: string[];
    error?: string;
}

type PythonOutput = ProgressInfo | ResultInfo;

/**
 * 执行 Python 后端脚本进行文件转换
 */
export function executePythonScript(
    sourcePath: string,
    conversionType: ConversionType,
    outputDir: string,
    context: vscode.ExtensionContext,
    conversionOptions?: any,
    progressCallback?: (message: string, percentage?: number) => void
): Promise<PythonResponse> {
    
    return new Promise((resolve, reject) => {
        // Python 脚本路径
        const scriptPath = path.join(context.extensionPath, 'backend', 'cli.py');
        
        // 获取 Python 路径配置，并根据操作系统智能选择默认值
        const config = vscode.workspace.getConfiguration('markdown-hub');
        const isWindows = process.platform === 'win32';
        const defaultPythonCommand = isWindows ? 'python' : 'python3';
        const pythonPath = config.get<string>('pythonPath', defaultPythonCommand);

        const args = [
            scriptPath,
            '--conversion-type', conversionType,
            '--input-path', sourcePath,
            '--output-dir', outputDir
        ];
        
        // 添加转换选项参数（对DOCX, PDF, PPTX转换有效）
        if (conversionOptions && ['md-to-docx', 'md-to-pdf', 'md-to-pptx'].includes(conversionType)) {
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

        let stdoutBuffer = '';

        pyProcess.stdout.on('data', (data) => {
            stdoutBuffer += data.toString();
            
            // 尝试处理缓冲区中的每一行
            let lines = stdoutBuffer.split('\n');
            // 保留最后一个不完整的行（如果有）
            stdoutBuffer = lines[lines.length - 1];
            // 处理完整的行
            lines.slice(0, -1).forEach(line => {
                try {
                    const output = JSON.parse(line) as PythonOutput;
                    if (output.type === 'progress' && progressCallback) {
                        progressCallback(output.stage, output.percentage);
                    } else if (output.type === 'result') {
                        if (output.success) {
                            resolve({
                                success: true,
                                outputFiles: output.outputFiles
                            });
                        } else {
                            reject(new Error(output.error || 'Python 脚本报告了一个未知错误'));
                        }
                    }
                } catch (e) {
                    console.log('非JSON输出:', line);
                }
            });
        });

        pyProcess.stderr.on('data', (data) => {
            console.error(`Python错误输出: ${data}`);
        });

        pyProcess.on('close', (code) => {
            if (code !== 0 && stdoutBuffer.trim()) {
                // 如果进程异常退出且还有未处理的输出，尝试解析
                try {
                    const finalOutput = JSON.parse(stdoutBuffer.trim()) as PythonOutput;
                    if (finalOutput.type === 'result' && !finalOutput.success) {
                        const errorMessage = finalOutput.error || `Python 脚本异常退出，代码：${code}`;
                        reject(new Error(errorMessage));
                        return;
                    }
                } catch (e) {
                    // 解析失败，使用通用错误信息
                    reject(new Error(`Python 脚本异常退出，代码：${code}。输出：${stdoutBuffer.trim()}`));
                }
            } else if (code !== 0) {
                 reject(new Error(`Python 脚本异常退出，代码：${code}`));
            }
        });

        pyProcess.on('error', (err) => {
            reject(new Error(`无法启动 Python 脚本：${err.message}`));
        });
    });
}

 