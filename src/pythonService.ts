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
    context: vscode.ExtensionContext
): Promise<PythonResponse> {
    
    return new Promise((resolve, reject) => {
        // Python 脚本路径
        const scriptPath = path.join(context.extensionPath, 'backend', 'cli.py');
        
        // 获取 Python 路径配置
        const config = vscode.workspace.getConfiguration('office-docs-converter');
        const pythonPath = config.get<string>('pythonPath', 'python3');

        const args = [
            scriptPath,
            '--conversion-type', conversionType,
            '--input-path', sourcePath,
            '--output-dir', outputDir
        ];
        
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
                    // 解析 Python 脚本返回的 JSON 结果
                    const response: PythonResponse = JSON.parse(stdout.trim());
                    resolve(response);
                } catch (e: any) {
                    reject({ 
                        success: false, 
                        error: `无法解析 Python 脚本输出：${e.message}\n输出内容：${stdout}` 
                    });
                }
            } else {
                reject({ 
                    success: false, 
                    error: stderr || `Python 脚本退出，代码：${code}` 
                });
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