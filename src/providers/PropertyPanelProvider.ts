import * as vscode from 'vscode';
import { TreeNode } from '../services/TreeDataService';

export interface ParameterItem {
    id: string;
    name: string;
    type: string;
    value: string;
    description?: string;
    constraints?: any;
    metadata?: any;
}

export class PropertyPanelProvider implements vscode.TreeDataProvider<ParameterItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<ParameterItem | undefined | null | void> = new vscode.EventEmitter<ParameterItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<ParameterItem | undefined | null | void> = this._onDidChangeTreeData.event;

    private currentParameters: ParameterItem[] = [];
    private currentContainer: TreeNode | null = null;

    constructor() {
        // 注册PropertyPanelProvider特有的命令
        vscode.commands.registerCommand('arxml.editParameter', (item: ParameterItem) => this.editParameter(item));
    }

    getTreeItem(element: ParameterItem): vscode.TreeItem {
        const item = new vscode.TreeItem(element.name, vscode.TreeItemCollapsibleState.None);
        
        // 特殊处理info类型（空状态提示）
        if (element.type === 'info') {
            item.iconPath = new vscode.ThemeIcon('info');
            item.description = element.description;
            item.tooltip = element.description;
            item.contextValue = 'info';
            return item;
        }
        
        // 设置图标
        switch (element.type) {
            case 'enumeration':
                item.iconPath = new vscode.ThemeIcon('symbol-enum');
                break;
            case 'numerical':
            case 'integer':
            case 'float':
                item.iconPath = new vscode.ThemeIcon('symbol-numeric');
                break;
            case 'textual':
            case 'string':
                item.iconPath = new vscode.ThemeIcon('symbol-string');
                break;
            case 'boolean':
                item.iconPath = new vscode.ThemeIcon('symbol-boolean');
                break;
            default:
                item.iconPath = new vscode.ThemeIcon('symbol-variable');
        }
        
        // 设置描述（显示值）
        if (element.value !== undefined && element.value !== null && element.value !== '') {
            item.description = `= ${element.value}`;
        } else {
            item.description = '(未设置)';
        }
        
        // 设置工具提示
        let tooltip = `参数: ${element.name}\n类型: ${element.type}`;
        if (element.value !== undefined && element.value !== null && element.value !== '') {
            tooltip += `\n值: ${element.value}`;
        }
        if (element.description) {
            tooltip += `\n描述: ${element.description}`;
        }
        if (element.constraints) {
            if (element.constraints.lowerMultiplicity || element.constraints.upperMultiplicity) {
                tooltip += `\n约束: ${element.constraints.lowerMultiplicity || 0}..${element.constraints.upperMultiplicity || '*'}`;
            }
            if (element.constraints.min !== undefined || element.constraints.max !== undefined) {
                tooltip += `\n范围: ${element.constraints.min || '-∞'}..${element.constraints.max || '+∞'}`;
            }
        }
        item.tooltip = tooltip;
        
        // 设置上下文值（用于右键菜单）
        item.contextValue = 'parameter';
        
        // 设置命令（双击编辑）
        item.command = {
            command: 'arxml.editParameter',
            title: '编辑参数',
            arguments: [element]
        };
        
        return item;
    }

    getChildren(element?: ParameterItem): Thenable<ParameterItem[]> {
        if (!element) {
            if (this.currentParameters.length === 0) {
                // 如果没有参数，返回一个提示项
                const emptyItem: ParameterItem = {
                    id: 'empty_state',
                    name: this.currentContainer ? '此容器没有参数' : '请在左侧树中选择一个容器',
                    type: 'info',
                    value: '',
                    description: this.currentContainer ? '选择其他容器查看参数' : '点击容器节点查看其参数配置'
                };
                return Promise.resolve([emptyItem]);
            }
            return Promise.resolve(this.currentParameters);
        } else {
            return Promise.resolve([]);
        }
    }

    updateParameters(container: TreeNode | null): void {
        this.currentContainer = container;
        
        if (!container || !container.parameters) {
            this.currentParameters = [];
        } else {
            // 转换参数格式
            this.currentParameters = container.parameters.map((param: any) => ({
                id: param.id || `param_${Math.random()}`,
                name: param.name || param.shortName || 'Unknown Parameter',
                type: param.type || 'unknown',
                value: param.value || '',
                description: param.description,
                constraints: param.constraints,
                metadata: param.metadata
            }));
        }
        
        this._onDidChangeTreeData.fire();
    }

    clearParameters(): void {
        this.currentContainer = null;
        this.currentParameters = [];
        this._onDidChangeTreeData.fire();
    }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    editParameter(parameter: ParameterItem): void {
        const options: vscode.InputBoxOptions = {
            prompt: `编辑参数: ${parameter.name}`,
            value: parameter.value,
            placeHolder: `输入 ${parameter.type} 类型的值...`
        };

        if (parameter.type === 'boolean') {
            // 布尔类型使用快速选择
            vscode.window.showQuickPick(['true', 'false'], {
                placeHolder: `选择 ${parameter.name} 的值`
            }).then(value => {
                if (value !== undefined) {
                    this.updateParameterValue(parameter, value);
                }
            });
        } else if (parameter.type === 'enumeration') {
            // 枚举类型显示可选值（如果有的话）
            vscode.window.showInputBox(options).then(value => {
                if (value !== undefined) {
                    this.updateParameterValue(parameter, value);
                }
            });
        } else {
            // 其他类型使用输入框
            vscode.window.showInputBox(options).then(value => {
                if (value !== undefined) {
                    this.updateParameterValue(parameter, value);
                }
            });
        }
    }

    private updateParameterValue(parameter: ParameterItem, newValue: string): void {
        // 更新参数值
        parameter.value = newValue;
        
        // 更新原始数据
        if (this.currentContainer && this.currentContainer.parameters) {
            const originalParam = this.currentContainer.parameters.find((p: any) => p.id === parameter.id);
            if (originalParam) {
                originalParam.value = newValue;
            }
        }
        
        // 刷新显示
        this._onDidChangeTreeData.fire();
        
        vscode.window.showInformationMessage(`参数 "${parameter.name}" 已更新为: ${newValue}`);
    }

    getSelectedContainer(): TreeNode | null {
        return this.currentContainer;
    }
} 