import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { spawn } from 'child_process';

export interface TreeNode {
    id: string;
    name: string;
    type: string;
    path: string;
    value?: string;
    children: TreeNode[];
    parameters?: any[];
    metadata?: {
        description?: string;
        tooltip?: string;
        icon?: string;
        isExpandable?: boolean;
        hasChildren?: boolean;
        sourceLocation?: {
            line: number;
            column: number;
        };
    };
    attributes?: { [key: string]: any };
    source_path?: string;
    source_line?: number;
    source_column?: number;
}

export interface ParseResult {
    success: boolean;
    fileType: string;
    filePath: string;
    treeStructure: TreeNode;
    metadata?: {
        totalPackages?: number;
        totalContainers?: number;
        totalParameters?: number;
        parseTime?: number;
    };
    containers?: { [key: string]: any };
    variables?: { [key: string]: any };
    error?: string;
}

export class TreeDataService {
    private outputChannel: vscode.OutputChannel;
    private logFilePath: string;

    constructor() {
        this.outputChannel = vscode.window.createOutputChannel('ARXML Viewer');
        // 延迟初始化日志文件路径，在实际需要时创建
        this.logFilePath = '';
    }

    private initializeLogFile(): void {
        if (this.logFilePath) return; // 已经初始化过了
        
        try {
            // 获取扩展路径
            const extension = vscode.extensions.getExtension('ywfhighlo.arxml-viewer');
            if (!extension) {
                console.warn('无法获取扩展信息，使用工作区目录作为日志路径');
                const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
                if (workspaceRoot) {
                    const logDir = path.join(workspaceRoot, 'arxml-viewer-logs');
                    if (!fs.existsSync(logDir)) {
                        fs.mkdirSync(logDir, { recursive: true });
                    }
                    this.logFilePath = path.join(logDir, `frontend_backend_comm_${this.getTimestamp()}.log`);
                } else {
                    // 如果连工作区都没有，就使用临时目录
                    const os = require('os');
                    const logDir = path.join(os.tmpdir(), 'arxml-viewer-logs');
                    if (!fs.existsSync(logDir)) {
                        fs.mkdirSync(logDir, { recursive: true });
                    }
                    this.logFilePath = path.join(logDir, `frontend_backend_comm_${this.getTimestamp()}.log`);
                }
            } else {
                const extensionPath = extension.extensionPath;
                const logDir = path.join(extensionPath, 'python-backend', 'communication_logs');
                if (!fs.existsSync(logDir)) {
                    fs.mkdirSync(logDir, { recursive: true });
                }
                this.logFilePath = path.join(logDir, `frontend_backend_comm_${this.getTimestamp()}.log`);
            }
            
            // 写入日志头
            this.writeLog('='.repeat(80));
            this.writeLog('ARXML Viewer 前后端通信日志');
            this.writeLog(`日志开始时间: ${new Date().toLocaleString()}`);
            this.writeLog('='.repeat(80));
            
        } catch (error) {
            console.error('初始化日志文件失败:', error);
            // 如果日志初始化失败，设置一个默认路径避免后续错误
            this.logFilePath = path.join(require('os').tmpdir(), `arxml-viewer-${Date.now()}.log`);
        }
    }

    private getTimestamp(): string {
        const now = new Date();
        return now.getFullYear().toString() +
               (now.getMonth() + 1).toString().padStart(2, '0') +
               now.getDate().toString().padStart(2, '0') + '_' +
               now.getHours().toString().padStart(2, '0') +
               now.getMinutes().toString().padStart(2, '0') +
               now.getSeconds().toString().padStart(2, '0');
    }

    private writeLog(message: string) {
        const timestamp = new Date().toISOString();
        const logEntry = `[${timestamp}] ${message}\n`;
        
        // 写入到输出通道
        this.outputChannel.appendLine(message);
        
        // 确保日志文件已初始化
        if (!this.logFilePath) {
            this.initializeLogFile();
        }
        
        // 写入到日志文件
        try {
            if (this.logFilePath) {
                fs.appendFileSync(this.logFilePath, logEntry);
            }
        } catch (error) {
            console.error('写入日志文件失败:', error);
        }
    }

    private logError(message: string, error?: any) {
        this.writeLog(`❌ 错误: ${message}`);
        if (error) {
            this.writeLog(`错误详情: ${JSON.stringify(error, null, 2)}`);
        }
    }

    private logInfo(message: string) {
        this.writeLog(`ℹ️ 信息: ${message}`);
    }

    private logSuccess(message: string) {
        this.writeLog(`✅ 成功: ${message}`);
    }

    async parseFile(filePath: string): Promise<ParseResult> {
        this.writeLog('\n' + '='.repeat(60));
        this.logInfo(`开始解析文件: ${filePath}`);
        
        try {
            // 检查文件是否存在
            if (!fs.existsSync(filePath)) {
                const error = `文件不存在: ${filePath}`;
                this.logError(error);
                return {
                    success: false,
                    fileType: 'unknown',
                    filePath: filePath,
                    treeStructure: { id: 'error', name: 'Error', type: 'error', path: '', children: [] },
                    error: error
                };
            }

            this.logInfo(`文件存在，大小: ${fs.statSync(filePath).size} 字节`);

            // 获取扩展路径
            const extension = vscode.extensions.getExtension('ywfhighlo.arxml-viewer');
            if (!extension) {
                const error = '无法找到扩展';
                this.logError(error);
                return {
                    success: false,
                    fileType: 'unknown',
                    filePath: filePath,
                    treeStructure: { id: 'error', name: 'Error', type: 'error', path: '', children: [] },
                    error: error
                };
            }

            const extensionPath = extension.extensionPath;
            this.logInfo(`扩展路径: ${extensionPath}`);

            // 构建Python后端路径
            const pythonBackendPath = path.join(extensionPath, 'python-backend');
            const cliWrapperPath = path.join(pythonBackendPath, 'cli_wrapper.py');
            
            this.logInfo(`Python后端路径: ${pythonBackendPath}`);
            this.logInfo(`CLI包装器路径: ${cliWrapperPath}`);

            // 检查Python脚本是否存在
            if (!fs.existsSync(cliWrapperPath)) {
                const error = `Python CLI包装器不存在: ${cliWrapperPath}`;
                this.logError(error);
                return {
                    success: false,
                    fileType: 'unknown',
                    filePath: filePath,
                    treeStructure: { id: 'error', name: 'Error', type: 'error', path: '', children: [] },
                    error: error
                };
            }

            this.logInfo('Python CLI包装器存在');

            // 构建命令 - 使用绝对路径确保正确调用
            const isWin = process.platform === 'win32';
            const command = isWin ? 'python' : 'python3';
            const args = [cliWrapperPath, 'parse', '--file', filePath];
            
            // 记录详细的调试信息
            this.logInfo(`当前工作目录: ${process.cwd()}`);
            this.logInfo(`扩展路径: ${extensionPath}`);
            this.logInfo(`Python后端目录是否存在: ${fs.existsSync(pythonBackendPath)}`);
            this.logInfo(`CLI包装器是否存在: ${fs.existsSync(cliWrapperPath)}`);
            this.logInfo(`目标文件是否存在: ${fs.existsSync(filePath)}`);
            this.logInfo(`目标文件路径: ${filePath}`);
            
            this.logInfo(`执行命令: ${command} ${args.join(' ')}`);
            this.logInfo(`工作目录: ${pythonBackendPath}`);

            return new Promise<ParseResult>((resolve) => {
                let stdout = '';
                let stderr = '';
                
                this.logInfo('启动Python子进程...');

                const process = spawn(command, args, {
                    cwd: pythonBackendPath,
                    shell: true
                });

                process.stdout.on('data', (data) => {
                    const chunk = data.toString();
                    stdout += chunk;
                    this.writeLog(`📤 Python输出: ${chunk.trim()}`);
                });

                process.stderr.on('data', (data) => {
                    const chunk = data.toString();
                    stderr += chunk;
                    this.writeLog(`⚠️ Python错误输出: ${chunk.trim()}`);
                });

                process.on('close', (code) => {
                    this.logInfo(`Python进程结束，退出码: ${code}`);
                    this.writeLog(`📊 标准输出长度: ${stdout.length} 字符`);
                    this.writeLog(`📊 错误输出长度: ${stderr.length} 字符`);

                    if (code !== 0) {
                        const error = `Python进程异常退出，退出码: ${code}\n错误输出: ${stderr}`;
                        this.logError(error);
                        resolve({
                            success: false,
                            fileType: 'unknown',
                            filePath: filePath,
                            treeStructure: { id: 'error', name: 'Error', type: 'error', path: '', children: [] },
                            error: error
                        });
                        return;
                    }

                    if (!stdout.trim()) {
                        const error = 'Python后端没有返回任何输出';
                        this.logError(error);
                        resolve({
                            success: false,
                            fileType: 'unknown',
                            filePath: filePath,
                            treeStructure: { id: 'error', name: 'Error', type: 'error', path: '', children: [] },
                            error: error
                        });
                        return;
                    }

                    this.writeLog('\n📋 完整Python输出:');
                    this.writeLog('-'.repeat(40));
                    this.writeLog(stdout);
                    this.writeLog('-'.repeat(40));

                    try {
                        // 尝试解析JSON输出
                        this.logInfo('开始解析JSON输出...');
                        
                        // 查找JSON开始位置（跳过调试信息）
                        const jsonStartIndex = stdout.indexOf('{');
                        if (jsonStartIndex === -1) {
                            const error = '输出中未找到JSON数据';
                            this.logError(error);
                            resolve({
                                success: false,
                                fileType: 'unknown',
                                filePath: filePath,
                                treeStructure: { id: 'error', name: 'Error', type: 'error', path: '', children: [] },
                                error: error
                            });
                            return;
                        }

                        const jsonString = stdout.substring(jsonStartIndex);
                        this.logInfo(`提取的JSON字符串长度: ${jsonString.length}`);
                        this.writeLog('\n🔍 提取的JSON字符串前200字符:');
                        this.writeLog(jsonString.substring(0, 200) + '...');

                        const result: ParseResult = JSON.parse(jsonString);
                        
                        this.logSuccess('JSON解析成功');
                        this.writeLog(`🏗️ 解析结果摘要:`);
                        this.writeLog(`  - 成功: ${result.success}`);
                        this.writeLog(`  - 文件类型: ${result.fileType}`);
                        this.writeLog(`  - 文件路径: ${result.filePath}`);
                        
                        if (result.metadata) {
                            this.writeLog(`  - 总包数: ${result.metadata.totalPackages || 0}`);
                            this.writeLog(`  - 总容器数: ${result.metadata.totalContainers || 0}`);
                            this.writeLog(`  - 总参数数: ${result.metadata.totalParameters || 0}`);
                            this.writeLog(`  - 解析时间: ${result.metadata.parseTime || 0}秒`);
                        }

                        // 保存后端完整解析内容到log目录
                        this.saveBackendContentToLog(filePath, stdout);

                        // 分析树结构
                        if (result.treeStructure) {
                            this.analyzeTreeStructure(result.treeStructure);
                        }

                        resolve(result);

                    } catch (parseError) {
                        const error = `JSON解析失败: ${parseError}`;
                        this.logError(error);
                        this.writeLog('\n🔍 解析失败的原始输出:');
                        this.writeLog(stdout);
                        resolve({
                            success: false,
                            fileType: 'unknown',
                            filePath: filePath,
                            treeStructure: { id: 'error', name: 'Error', type: 'error', path: '', children: [] },
                            error: error
                        });
                    }
                });

                process.on('error', (error) => {
                    const errorMsg = `无法启动Python进程: ${error.message}`;
                    this.logError(errorMsg, error);
                    resolve({
                        success: false,
                        fileType: 'unknown',
                        filePath: filePath,
                        treeStructure: { id: 'error', name: 'Error', type: 'error', path: '', children: [] },
                        error: errorMsg
                    });
                });
            });

        } catch (error) {
            const errorMsg = `解析过程中发生异常: ${error}`;
            this.logError(errorMsg, error);
            return {
                success: false,
                fileType: 'unknown',
                filePath: filePath,
                treeStructure: { id: 'error', name: 'Error', type: 'error', path: '', children: [] },
                error: errorMsg
            };
        }
    }

    private analyzeTreeStructure(node: TreeNode, level: number = 0): void {
        const indent = '  '.repeat(level);
        const childrenCount = node.children ? node.children.length : 0;
        const hasChildren = childrenCount > 0;
        
        this.writeLog(`${indent}🌳 [层级${level}] ${node.name} (${node.type}) - ${childrenCount}个子节点 ${hasChildren ? '✓' : '✗'}`);
        
        if (node.value !== undefined && node.value !== null) {
            this.writeLog(`${indent}    💾 值: ${node.value}`);
        }
        
        if (node.path) {
            this.writeLog(`${indent}    📍 路径: ${node.path}`);
        }

        if (node.children && node.children.length > 0) {
            for (const child of node.children) {
                this.analyzeTreeStructure(child, level + 1);
            }
        }
    }

    logNodeSelection(node: TreeNode) {
        this.writeLog('\n' + '-'.repeat(40));
        this.logInfo(`节点选择: ${node.name}`);
        this.logInfo(`节点类型: ${node.type}`);
        this.logInfo(`节点路径: ${node.path || '未知'}`);
        
        if (node.parameters) {
            this.logInfo(`参数数量: ${node.parameters.length}`);
            if (node.parameters.length > 0) {
                this.writeLog('参数列表:');
                node.parameters.forEach((param, index) => {
                    this.writeLog(`  ${index + 1}. ${param.name || '未命名参数'}: ${param.value || '无值'}`);
                });
            }
        }
        
        if (node.children) {
            this.logInfo(`子节点数量: ${node.children.length}`);
        }
        
        this.writeLog('-'.repeat(40));
    }

    showOutput() {
        this.outputChannel.show();
    }

    /**
     * 将后端解析内容保存到log目录
     */
    private saveBackendContentToLog(filePath: string, backendContent: string): void {
        // 禁用日志文件生成
        return;
        
        try {
            // 获取工作区根目录
            const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
            if (!workspaceRoot) {
                this.logError('无法获取工作区根目录，跳过保存后端内容到log目录');
                return;
            }

            // 创建log目录（如果不存在）
            const logDir = path.join(workspaceRoot!, 'log');
            if (!fs.existsSync(logDir)) {
                fs.mkdirSync(logDir, { recursive: true });
                this.logInfo(`创建log目录: ${logDir}`);
            }

            // 生成日志文件名：与arxml文件名相同，但后缀为.log
            const originalFileName = path.basename(filePath);
            const logFileName = path.basename(originalFileName, path.extname(originalFileName)) + '.log';
            const logFilePath = path.join(logDir, logFileName);

            // 准备要保存的内容
            const timestamp = new Date().toLocaleString();
            const logContent = `# ARXML文件解析日志
# 原始文件: ${filePath}
# 生成时间: ${timestamp}
# 后端解析内容:
${'-'.repeat(80)}

${backendContent}

${'-'.repeat(80)}
# 日志结束
`;

            // 保存到文件
            fs.writeFileSync(logFilePath, logContent, 'utf8');
            this.logSuccess(`后端解析内容已保存到: ${logFilePath}`);
            
            // 显示通知
            vscode.window.showInformationMessage(`📝 后端解析内容已保存到: ${logFileName}`);

        } catch (error) {
            this.logError(`保存后端内容到log目录失败: ${error}`, error);
        }
    }
}