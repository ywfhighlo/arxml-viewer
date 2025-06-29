import * as vscode from 'vscode';
import * as path from 'path';
import * as child_process from 'child_process';
import * as fs from 'fs';
import { ParseResult, NodeDetails, ValidationResult } from '../models/parseResult';

export class PythonBackendService {
    private pythonProcess: child_process.ChildProcess | null = null;
    private initialized: boolean = false;
    private initPromise: Promise<void> | null = null;

    constructor(private readonly extensionPath: string) {}

    async initialize(): Promise<void> {
        if (this.initPromise) {
            return this.initPromise;
        }

        this.initPromise = this._doInitialize();
        return this.initPromise;
    }

    private async _doInitialize(): Promise<void> {
        if (this.initialized) {
            return;
        }

        try {
            const scriptPath = path.join(this.extensionPath, 'python-backend', 'cli_wrapper.py');
            
            // 检查脚本文件是否存在
            if (!fs.existsSync(scriptPath)) {
                throw new Error(`Python脚本不存在: ${scriptPath}`);
    }

            // 检查虚拟环境
            const venvPath = path.join(this.extensionPath, 'python-backend', 'venv');
            let pythonPath: string;

            if (fs.existsSync(venvPath)) {
                // 使用虚拟环境
                pythonPath = process.platform === 'win32' 
                    ? path.join(venvPath, 'Scripts', 'python.exe')
                    : path.join(venvPath, 'bin', 'python');
            } else {
                // 使用系统Python
                pythonPath = this.getPythonPath();
            }

            console.log(`使用Python路径: ${pythonPath}`);
            console.log(`脚本路径: ${scriptPath}`);

            this.initialized = true;
            console.log('✅ Python后端初始化成功');
        } catch (error) {
            console.error('❌ Python后端初始化失败:', error);
            throw new Error(`初始化Python后端失败: ${error}`);
        }
    }

    async parseFile(filePath: string): Promise<ParseResult> {
        await this.initialize();

        return new Promise((resolve, reject) => {
            try {
                const scriptPath = path.join(this.extensionPath, 'python-backend', 'cli_wrapper.py');
                
                // 检查虚拟环境
                const venvPath = path.join(this.extensionPath, 'python-backend', 'venv');
                let pythonPath: string;

                if (fs.existsSync(venvPath)) {
                    pythonPath = process.platform === 'win32' 
                        ? path.join(venvPath, 'Scripts', 'python.exe')
                        : path.join(venvPath, 'bin', 'python');
            } else {
                    pythonPath = this.getPythonPath();
            }
            
                console.log(`解析文件: ${filePath}`);
                console.log(`使用Python: ${pythonPath}`);

                const childProcess = child_process.spawn(pythonPath, [scriptPath, 'parse', '--file', filePath], {
                    cwd: path.join(this.extensionPath, 'python-backend'),
                    stdio: ['pipe', 'pipe', 'pipe']
            });

            let stdout = '';
            let stderr = '';

                childProcess.stdout?.on('data', (data) => {
                    stdout += data.toString();
            });

                childProcess.stderr?.on('data', (data) => {
                    stderr += data.toString();
                });

                childProcess.on('close', (code) => {
                if (code === 0) {
                        try {
                            const result = JSON.parse(stdout);
                            resolve(result);
                        } catch (parseError) {
                            console.error('解析Python输出失败:', stdout);
                            reject(new Error(`解析Python输出失败: ${parseError}`));
                        }
                } else {
                        console.error('Python进程错误:', stderr);
                        reject(new Error(`Python进程退出代码: ${code}, 错误: ${stderr}`));
                }
            });

                childProcess.on('error', (error) => {
                    console.error('启动Python进程失败:', error);
                    reject(new Error(`启动Python进程失败: ${error.message}`));
        });

            } catch (error) {
                reject(new Error(`执行解析失败: ${error}`));
            }
        });
    }

    async validateFile(filePath: string): Promise<ValidationResult> {
        await this.initialize();

        return new Promise((resolve, reject) => {
            try {
                const scriptPath = path.join(this.extensionPath, 'python-backend', 'cli_wrapper.py');

        // 检查虚拟环境
                const venvPath = path.join(this.extensionPath, 'python-backend', 'venv');
                let pythonPath: string;

                if (fs.existsSync(venvPath)) {
                    pythonPath = process.platform === 'win32' 
                        ? path.join(venvPath, 'Scripts', 'python.exe')
                        : path.join(venvPath, 'bin', 'python');
                } else {
                    pythonPath = this.getPythonPath();
                }

                const childProcess = child_process.spawn(pythonPath, [scriptPath, 'validate', '--file', filePath], {
                    cwd: path.join(this.extensionPath, 'python-backend'),
                    stdio: ['pipe', 'pipe', 'pipe']
                });

                let stdout = '';
                let stderr = '';

                childProcess.stdout?.on('data', (data) => {
                    stdout += data.toString();
                });

                childProcess.stderr?.on('data', (data) => {
                    stderr += data.toString();
                });

                childProcess.on('close', (code) => {
                    if (code === 0) {
                        resolve({
                            success: true,
                            isValid: true,
                            errors: []
                        });
                    } else {
                        resolve({
                            success: true,
                            isValid: false,
                            errors: [stderr || '验证失败']
                        });
                    }
                });

                childProcess.on('error', (error) => {
                    reject(new Error(`启动验证进程失败: ${error.message}`));
                });

            } catch (error) {
                reject(new Error(`执行验证失败: ${error}`));
            }
        });
    }

    async testBackend(): Promise<boolean> {
        try {
            await this.initialize();
            return true;
        } catch (error) {
            console.error('测试后端失败:', error);
            return false;
        }
    }

    private getPythonPath(): string {
        const config = vscode.workspace.getConfiguration('arxmlTreePreviewer');
        const configPath = config.get<string>('pythonPath', '');
        
        if (configPath) {
            return configPath;
        }

        // 尝试常见的Python路径
        if (process.platform === 'win32') {
            return 'python';
        } else {
            return 'python3';
        }
    }

    dispose(): void {
        if (this.pythonProcess) {
            this.pythonProcess.kill();
            this.pythonProcess = null;
        }
        this.initialized = false;
        this.initPromise = null;
    }

    getBackendInfo(): { type: string; script: string; useVirtualEnv: boolean } {
        return {
            type: 'command',
            script: path.join(this.extensionPath, 'python-backend', 'cli_wrapper.py'),
            useVirtualEnv: fs.existsSync(path.join(this.extensionPath, 'python-backend', 'venv'))
        };
    }

    getSupportedExtensions(): string[] {
        return ['.arxml', '.xdm', '.xml'];
    }
} 