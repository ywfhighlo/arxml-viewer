import * as vscode from 'vscode';
import * as path from 'path';
import { PythonBackendService } from './pythonBackendService';
import { ParseResult } from '../models/parseResult';

export class FileService {
    private backendService: PythonBackendService;
    private parseCache: Map<string, any> = new Map();

    constructor(backendService: PythonBackendService) {
        this.backendService = backendService;
    }

    async loadFile(filePath: string): Promise<any> {
        // 检查缓存
        const cached = this.parseCache.get(filePath);
        if (cached) {
            return cached;
        }

        try {
            const result = await this.backendService.parseFile(filePath);
            this.parseCache.set(filePath, result);
            return result;
        } catch (error) {
            throw new Error(`加载文件失败: ${error}`);
        }
    }

    clearCache(): void {
        this.parseCache.clear();
    }

    getSupportedExtensions(): string[] {
        return ['.arxml', '.xdm', '.xml'];
    }

    isSupported(uri: vscode.Uri): boolean {
        const extension = uri.fsPath.toLowerCase().split('.').pop();
        return ['arxml', 'xdm', 'xml'].includes(extension || '');
    }

    async openFileAtLocation(location: { file: string; line: number; column: number }): Promise<void> {
        try {
            const document = await vscode.workspace.openTextDocument(location.file);
            const editor = await vscode.window.showTextDocument(document);
            
            const position = new vscode.Position(location.line - 1, location.column - 1);
            const range = new vscode.Range(position, position);
            
            editor.selection = new vscode.Selection(range.start, range.end);
            editor.revealRange(range, vscode.TextEditorRevealType.InCenter);
        } catch (error) {
            vscode.window.showErrorMessage(`无法打开文件位置: ${error}`);
        }
    }
} 