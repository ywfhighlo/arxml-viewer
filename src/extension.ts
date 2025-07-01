import * as vscode from 'vscode';
import { handleConvertCommand, handleOpenTemplateSettingsCommand } from './commandHandler';

export function activate(context: vscode.ExtensionContext) {
    console.log('Markdown Docs Converter is now active!');
    
    // Register all conversion commands
    const disposables = [
        vscode.commands.registerCommand('markdown-docs-converter.mdToDocx', 
            (uri: vscode.Uri) => handleConvertCommand(uri, 'md-to-docx', context)),
        
        vscode.commands.registerCommand('markdown-docs-converter.mdToPdf', 
            (uri: vscode.Uri) => handleConvertCommand(uri, 'md-to-pdf', context)),
        
        vscode.commands.registerCommand('markdown-docs-converter.mdToHtml', 
            (uri: vscode.Uri) => handleConvertCommand(uri, 'md-to-html', context)),
        
        vscode.commands.registerCommand('markdown-docs-converter.officeToMd', 
            (uri: vscode.Uri) => handleConvertCommand(uri, 'office-to-md', context)),
        
        vscode.commands.registerCommand('markdown-docs-converter.diagramToPng', 
            (uri: vscode.Uri) => handleConvertCommand(uri, 'diagram-to-png', context)),
        
        vscode.commands.registerCommand('markdown-docs-converter.openTemplateSettings', 
            () => handleOpenTemplateSettingsCommand())
    ];
    
    context.subscriptions.push(...disposables);
}

export function deactivate() {
    console.log('Markdown Docs Converter is now deactivated.');
} 