/**
 * 解析结果接口定义
 */

export interface TreeNodeData {
    id: string;
    name: string;
    type: 'root' | 'package' | 'container' | 'variable' | 'instance' | 'element';
    path: string;
    attributes?: Record<string, any>;
    children: TreeNodeData[];
    metadata: {
        description?: string;
        tooltip?: string;
        icon?: string;
        isExpandable: boolean;
        hasChildren: boolean;
        sourceLocation?: {
            line: number;
            column: number;
            length: number;
        };
    };
    // ARXML/XDM特定字段
    shortName?: string;
    definition?: string;
    value?: any;
    instances?: number;
}

export interface ParseResult {
    success: boolean;
    error?: string;
    fileType: 'arxml' | 'xdm' | 'xml';
    filePath: string;
    treeStructure: TreeNodeData;
    metadata: {
        totalPackages?: number;
        totalContainers?: number;
        totalParameters?: number;
        totalVariables?: number;
        totalInstances?: number;
        parseTime?: number;
        rootTag?: string;
        totalElements?: number;
    };
    containers?: Record<string, any>;
    variables?: Record<string, any>;
}

export interface NodeDetails {
    success: boolean;
    nodeType: string;
    path: string;
    details: any;
}

export interface ValidationResult {
    success: boolean;
    isValid: boolean;
    errors: string[];
    warnings?: string[];
    fileType?: string;
    fileSize?: number;
} 