import * as vscode from 'vscode';
import { handleConvertCommand, handleOpenTemplateSettingsCommand } from './commandHandler';

export function activate(context: vscode.ExtensionContext) {
    console.log('Markdown Hub is now active!');
    
    // Register all conversion commands
    const disposables = [
        vscode.commands.registerCommand('markdown-hub.mdToDocx', 
            (uri: vscode.Uri) => handleConvertCommand(uri, 'md-to-docx', context)),
        
        vscode.commands.registerCommand('markdown-hub.mdToPdf', 
            (uri: vscode.Uri) => handleConvertCommand(uri, 'md-to-pdf', context)),
        
        vscode.commands.registerCommand('markdown-hub.mdToHtml', 
            (uri: vscode.Uri) => handleConvertCommand(uri, 'md-to-html', context)),
        
        vscode.commands.registerCommand('markdown-hub.officeToMd', 
            (uri: vscode.Uri) => handleConvertCommand(uri, 'office-to-md', context)),
        
        vscode.commands.registerCommand('markdown-hub.diagramToPng', 
            (uri: vscode.Uri) => handleConvertCommand(uri, 'diagram-to-png', context)),
        
        vscode.commands.registerCommand('markdown-hub.openTemplateSettings', 
            () => handleOpenTemplateSettingsCommand())
    ];
    
    context.subscriptions.push(...disposables);
}

export function deactivate() {
    console.log('Markdown Hub is now deactivated.');
} 