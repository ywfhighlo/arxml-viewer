#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARXML/XDM GUI 测试脚本 - 调用统一后端服务
基于 Vector Eparm 风格的界面设计

作者: 余文锋
日期: 2025年6月20日
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import os
from pathlib import Path
import sys
import subprocess
import time

# ProcessorAdapter, ElementInfo, PackageInfo, ParseResult and direct processor imports are removed
# as the GUI now consumes the JSON output from the cli_wrapper.py.

class ARXMLGUIApp:
    """ARXML/XDM GUI应用程序 - 通过后端CLI获取数据"""
    
    def __init__(self, root, default_file=None):
        self.root = root
        self.root.title("ARXML/XDM Viewer - Unified Backend")
        self.root.geometry("1400x800")
        self.root.minsize(1000, 600)
        
        # 数据存储
        self.parse_result = None
        self.current_file = None
        self.tree_data = {}
        
        self.create_menu()
        self.create_toolbar()
        self.create_main_layout()
        self.create_status_bar()
        
        self.tree.bind('<<TreeviewSelect>>', self.on_tree_select)
        self.tree.bind('<Button-3>', self.show_context_menu)
        
        self.create_context_menu()
        
        if default_file and os.path.exists(default_file):
            self.root.after(100, lambda: self.load_file(default_file))
            
    def load_file(self, file_path):
        """加载文件，通过调用cli_wrapper.py获取JSON数据"""
        try:
            self.status_label.config(text=f"正在调用后端解析: {os.path.basename(file_path)}")
            self.progress.start()
            self.root.update()

            # 构建命令
            cli_script_path = Path(__file__).parent.parent / 'python-backend' / 'cli_wrapper.py'
            command = [
                sys.executable,  # 使用当前python解释器
                str(cli_script_path),
                'parse',
                '--file',
                file_path
            ]

            # 执行命令
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                check=True
            )

            # 解析JSON输出
            self.parse_result = json.loads(process.stdout)

            if not self.parse_result.get("success"):
                error_msg = self.parse_result.get("error", "未知后端错误")
                messagebox.showerror("后端解析错误", f"无法解析文件:\n{error_msg}")
                return
                
            self.current_file = file_path
            self.populate_tree()
            self.expand_all()
            
            # 设置默认焦点到第一个有效容器
            first_focusable_node = self.find_first_focusable_node()
            if first_focusable_node:
                self.tree.selection_set(first_focusable_node)
                self.tree.focus(first_focusable_node)
                self.tree.see(first_focusable_node)
                # 手动触发选择事件以更新参数面板
                self.on_tree_select(None)
            
            self.status_label.config(text=f"文件已加载: {os.path.basename(file_path)}")
            
        except subprocess.CalledProcessError as e:
            messagebox.showerror("后端调用错误", f"调用后端脚本失败:\n{e.stderr}")
        except json.JSONDecodeError:
            messagebox.showerror("JSON错误", "无法解析后端返回的JSON数据。")
        except Exception as e:
            messagebox.showerror("错误", f"加载文件时出错:\n{str(e)}")
        finally:
            self.progress.stop()
            self.status_label.config(text="就绪")
            
    def populate_tree(self):
        """使用从后端获取的JSON数据填充树形视图"""
        # 清空现有内容
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.tree_data.clear()

        if not self.parse_result or 'treeStructure' not in self.parse_result:
            return

        root_node_data = self.parse_result['treeStructure']
        self.add_container_node_to_tree('', root_node_data)
        
    def add_container_node_to_tree(self, parent, node_data):
        """递归地将容器节点添加到树视图"""
        # 计算子节点的总数（包括子容器和参数）
        children_count = len(node_data.get('children', [])) + len(node_data.get('parameters', []))
        
        node_id = self.tree.insert(
            parent, 'end',
            text=node_data.get('name', 'Unnamed'),
            values=(node_data.get('type', 'container'), children_count),
            tags=(node_data.get('type'),)
        )
        
        self.tree_data[node_id] = node_data # 存储整个节点字典
        
        # 为子容器递归调用 (不再需要检查类型，因为children里只有容器)
        for child_data in node_data.get('children', []):
            self.add_container_node_to_tree(node_id, child_data)
                
    def on_tree_select(self, event):
        """树形视图选择事件"""
        selection = self.tree.selection()
        if not selection:
            return
            
        item_id = selection[0]
        data = self.tree_data.get(item_id)
        
        if data:
            self.update_parameters(data)

    def update_parameters(self, node_data):
        """更新右侧参数面板"""
        for item in self.params_tree.get_children():
            self.params_tree.delete(item)
            
        if not isinstance(node_data, dict):
            return
        
        # 参数现在直接从'parameters'键获取
        params = node_data.get('parameters', [])
        
        if params:
            for param_data in params:
                param_name = param_data.get('name', 'Unnamed')
                param_value = param_data.get('value', '')
                self.params_tree.insert('', 'end', text=param_name, values=(str(param_value),))
        else:
            self.params_tree.insert('', 'end', text='无参数', values=('此容器不包含参数',))

    def export_element_json(self):
        """导出选中元素的数据为JSON"""
        selection = self.tree.selection()
        if selection:
            item_id = selection[0]
            if item_id in self.tree_data:
                element_data_dict = self.tree_data[item_id] # 这已经是一个字典了
                
                filename = filedialog.asksaveasfilename(
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                    title="导出元素数据"
                )
                
                if filename:
                    try:
                        with open(filename, 'w', encoding='utf-8') as f:
                            json.dump(element_data_dict, f, indent=2, ensure_ascii=False)
                        self.status_label.config(text=f"已导出到: {filename}")
                    except Exception as e:
                        messagebox.showerror("错误", f"导出失败: {str(e)}")

    def create_menu(self):
        """创建菜单栏"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="打开文件...", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="视图", menu=view_menu)
        view_menu.add_command(label="展开所有", command=self.expand_all)
        view_menu.add_command(label="折叠所有", command=self.collapse_all)
        view_menu.add_separator()
        view_menu.add_command(label="刷新", command=self.refresh_view)
        
        self.file_menu = file_menu
    
    def create_toolbar(self):
        """创建工具栏"""
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)
        
        # 打开文件按钮
        ttk.Button(toolbar, text="打开文件", command=self.open_file).pack(side=tk.LEFT, padx=2)
        
        # 分隔符
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # 展开/折叠按钮
        ttk.Button(toolbar, text="展开所有", command=self.expand_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="折叠所有", command=self.collapse_all).pack(side=tk.LEFT, padx=2)
        
        # 分隔符
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # 搜索框
        ttk.Label(toolbar, text="搜索:").pack(side=tk.LEFT, padx=2)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=20)
        self.search_entry.pack(side=tk.LEFT, padx=2)
        self.search_entry.bind('<Return>', self.on_search_enter)
        ttk.Button(toolbar, text="搜索", command=self.search_elements).pack(side=tk.LEFT, padx=2)
        
        # 绑定搜索事件
        self.search_var.trace_add('write', self.on_search_changed)
        
    def create_main_layout(self):
        """创建主布局 - DaVinci风格：左侧容器树 + 右侧参数区域"""
        # 创建主面板，实现1:2.5的比例
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧面板 - 容器树形视图 (权重=10)
        left_frame = ttk.LabelFrame(main_paned, text="容器结构", padding=5)
        main_paned.add(left_frame, weight=10)
        
        # 创建树形视图
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # 树形视图 - 只显示容器结构，不显示参数
        self.tree = ttk.Treeview(tree_frame, columns=('type', 'children'), show='tree headings')
        self.tree.heading('#0', text='容器名称')
        self.tree.heading('type', text='类型')
        self.tree.heading('children', text='子元素')
        
        self.tree.column('#0', width=250, minwidth=200)
        self.tree.column('type', width=150, minwidth=100)
        self.tree.column('children', width=80, minwidth=60)
        
        # 滚动条
        tree_scrolly = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scrollx = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scrolly.set, xscrollcommand=tree_scrollx.set)
        
        # 布局
        self.tree.grid(row=0, column=0, sticky='nsew')
        tree_scrolly.grid(row=0, column=1, sticky='ns')
        tree_scrollx.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # 右侧面板 - 参数区域 (权重=25，实现1:2.5比例)
        right_frame = ttk.LabelFrame(main_paned, text="参数", padding=5)
        main_paned.add(right_frame, weight=25)
        
        # 参数表格 - 显示参数名和参数值
        params_frame = ttk.Frame(right_frame)
        params_frame.pack(fill=tk.BOTH, expand=True)
        
        self.params_tree = ttk.Treeview(params_frame, columns=('value',), show='tree headings')
        self.params_tree.heading('#0', text='参数名')
        self.params_tree.heading('value', text='参数值')
        self.params_tree.column('#0', width=300, minwidth=200)
        self.params_tree.column('value', width=400, minwidth=200)
        
        # 参数区域滚动条
        params_scrolly = ttk.Scrollbar(params_frame, orient=tk.VERTICAL, command=self.params_tree.yview)
        params_scrollx = ttk.Scrollbar(params_frame, orient=tk.HORIZONTAL, command=self.params_tree.xview)
        self.params_tree.configure(yscrollcommand=params_scrolly.set, xscrollcommand=params_scrollx.set)
        
        # 参数区域布局
        self.params_tree.grid(row=0, column=0, sticky='nsew')
        params_scrolly.grid(row=0, column=1, sticky='ns')
        params_scrollx.grid(row=1, column=0, sticky='ew')
        
        params_frame.grid_rowconfigure(0, weight=1)
        params_frame.grid_columnconfigure(0, weight=1)
        
    def create_status_bar(self):
        """创建状态栏"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_label = ttk.Label(self.status_bar, text="就绪")
        self.status_label.pack(side=tk.LEFT, padx=5, pady=2)
        
        # 进度条
        self.progress = ttk.Progressbar(self.status_bar, mode='indeterminate')
        self.progress.pack(side=tk.RIGHT, padx=5, pady=2)
    
    def create_context_menu(self):
        """创建右键上下文菜单"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="展开所有子项", command=self.expand_all_children)
        self.context_menu.add_command(label="折叠所有子项", command=self.collapse_all_children)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="复制名称", command=self.copy_element_name)
        self.context_menu.add_command(label="复制路径", command=self.copy_element_path)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="导出为JSON", command=self.export_element_json)
    
    def show_context_menu(self, event):
        """显示右键菜单"""
        # 选择右键点击的项目
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def on_search_changed(self, *args):
        """搜索内容变化时的处理"""
        search_text = self.search_var.get().lower()
        if len(search_text) >= 2:  # 至少2个字符才开始搜索
            self.highlight_search_results(search_text)
        else:
            self.clear_search_highlights()
    
    def on_search_enter(self, event):
        """按回车键时跳转到下一个搜索结果"""
        search_text = self.search_var.get().lower()
        if search_text:
            self.find_next_match(search_text)
    
    def highlight_search_results(self, search_text):
        """高亮搜索结果"""
        # 清除之前的高亮
        self.clear_search_highlights()
        
        # 搜索并高亮匹配项
        self._search_in_tree('', search_text)
    
    def _search_in_tree(self, parent, search_text):
        """递归搜索树形视图"""
        for item in self.tree.get_children(parent):
            item_text = self.tree.item(item, 'text').lower()
            if search_text in item_text:
                # 高亮匹配项
                self.tree.item(item, tags=('search_match',))
                
                # 展开父节点以显示匹配项
                parent_item = self.tree.parent(item)
                while parent_item:
                    self.tree.item(parent_item, open=True)
                    parent_item = self.tree.parent(parent_item)
            
            # 递归搜索子项
            self._search_in_tree(item, search_text)
    
    def clear_search_highlights(self):
        """清除搜索高亮"""
        for item in self.tree.get_children():
            self._clear_highlights_recursive(item)
    
    def _clear_highlights_recursive(self, item):
        """递归清除高亮"""
        self.tree.item(item, tags=())
        for child in self.tree.get_children(item):
            self._clear_highlights_recursive(child)
    
    def find_next_match(self, search_text):
        """查找下一个匹配项"""
        current_selection = self.tree.selection()
        if current_selection:
            next_item = self._find_next_match_from(current_selection[0], search_text)
        else:
            next_item = self._find_first_match(search_text)
        
        if next_item:
            self.tree.selection_set(next_item)
            self.tree.focus(next_item)
            self.tree.see(next_item)
    
    def _find_next_match_from(self, start_item, search_text):
        """从指定项开始查找下一个匹配项"""
        all_items = self._get_all_items()
        start_index = all_items.index(start_item) if start_item in all_items else -1
        
        for i in range(start_index + 1, len(all_items)):
            item = all_items[i]
            if search_text in self.tree.item(item, 'text').lower():
                return item
        
        # 如果没找到，从头开始找
        for i in range(0, start_index):
            item = all_items[i]
            if search_text in self.tree.item(item, 'text').lower():
                return item
        
        return None
    
    def _find_first_match(self, search_text):
        """查找第一个匹配项"""
        all_items = self._get_all_items()
        for item in all_items:
            if search_text in self.tree.item(item, 'text').lower():
                return item
        return None
    
    def _get_all_items(self):
        """获取所有树项"""
        items = []
        
        def collect_items(parent):
            for item in self.tree.get_children(parent):
                items.append(item)
                collect_items(item)
        
        collect_items('')
        return items
    
    def expand_all_children(self):
        """展开所有子项"""
        selection = self.tree.selection()
        if selection:
            self._expand_recursive(selection[0])
    
    def collapse_all_children(self):
        """折叠所有子项"""
        selection = self.tree.selection()
        if selection:
            self._collapse_recursive(selection[0])
    
    def _expand_recursive(self, item):
        """递归展开"""
        self.tree.item(item, open=True)
        for child in self.tree.get_children(item):
            self._expand_recursive(child)
    
    def _collapse_recursive(self, item):
        """递归折叠"""
        for child in self.tree.get_children(item):
            self._collapse_recursive(child)
        self.tree.item(item, open=False)
    
    def copy_element_name(self):
        """复制元素名称"""
        selection = self.tree.selection()
        if selection:
            name = self.tree.item(selection[0], 'text')
            self.root.clipboard_clear()
            self.root.clipboard_append(name)
            self.status_label.config(text=f"已复制名称: {name}")
    
    def copy_element_path(self):
        """复制元素路径"""
        selection = self.tree.selection()
        if selection:
            item = selection[0]
            path_parts = []
            
            while item:
                path_parts.append(self.tree.item(item, 'text'))
                item = self.tree.parent(item)
            
            path = '/'.join(reversed(path_parts))
            self.root.clipboard_clear()
            self.root.clipboard_append(path)
            self.status_label.config(text=f"已复制路径: {path}")
        
    def open_file(self):
        """打开支持的配置文件"""
        file_path = filedialog.askopenfilename(
            title="选择配置文件",
            filetypes=[
                ("支持的格式", "*.arxml *.bmd *.xdm *.xml"),
                ("ARXML文件", "*.arxml"), 
                ("BMD文件", "*.bmd"),
                ("XDM文件", "*.xdm"),
                ("XML文件", "*.xml"), 
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            self.load_file(file_path)
    
    def expand_all(self):
        """展开所有节点"""
        def expand_item(item):
            self.tree.item(item, open=True)
            for child in self.tree.get_children(item):
                expand_item(child)
                
        for item in self.tree.get_children():
            expand_item(item)
            
    def collapse_all(self):
        """折叠所有节点"""
        def collapse_item(item):
            self.tree.item(item, open=False)
            for child in self.tree.get_children(item):
                collapse_item(child)
                
        for item in self.tree.get_children():
            collapse_item(item)
            
    def refresh_view(self):
        """刷新视图"""
        if self.current_file:
            self.load_file(self.current_file)
            
    def search_elements(self, event=None):
        """搜索元素"""
        search_text = self.search_var.get().strip().lower()
        if not search_text:
            return
            
        # 清除之前的搜索高亮
        for item in self.tree.get_children():
            self.clear_search_highlight(item)
            
        # 搜索并高亮
        found_items = []
        for item in self.tree.get_children():
            self.search_in_item(item, search_text, found_items)
            
        if found_items:
            # 选择第一个找到的项目
            self.tree.selection_set(found_items[0])
            self.tree.focus(found_items[0])
            self.tree.see(found_items[0])
            
            self.status_label.config(text=f"找到 {len(found_items)} 个匹配项")
        else:
            self.status_label.config(text="未找到匹配项")
            
    def search_in_item(self, item, search_text, found_items):
        """在项目中搜索"""
        item_text = self.tree.item(item, 'text').lower()
        if search_text in item_text:
            found_items.append(item)
            self.tree.set(item, 'tags', 'search_result')
            
        for child in self.tree.get_children(item):
            self.search_in_item(child, search_text, found_items)
            
    def clear_search_highlight(self, item):
        """清除搜索高亮"""
        current_tags = self.tree.item(item, 'tags')
        if 'search_result' in current_tags:
            new_tags = [tag for tag in current_tags if tag != 'search_result']
            self.tree.set(item, 'tags', new_tags)
            
        for child in self.tree.get_children(item):
            self.clear_search_highlight(child)

    def find_first_focusable_node(self):
        """查找默认应聚焦的节点：模块下的第一个有效子容器。"""
        root_items = self.tree.get_children()
        if not root_items:
            return None

        # 根节点 -> 模块
        module_items = self.tree.get_children(root_items[0])
        if not module_items:
            return root_items[0]

        # 模块 -> 第一个子容器
        container_items = self.tree.get_children(module_items[0])
        if not container_items:
            return module_items[0]
        
        return container_items[0]

def main():
    """主函数"""
    print("正在启动ARXML/XDM GUI (通过后端CLI)...")
    
    try:
        root = tk.Tk()
        print("Tkinter根窗口创建成功")
        
        default_file = None
        
        app = ARXMLGUIApp(root, default_file)
        print("GUI应用创建成功")
        
        root.bind('<Control-o>', lambda e: app.open_file())
        
        style = ttk.Style()
        style.configure("Treeview", rowheight=20)
        style.configure("Treeview.Heading", font=('Arial', 10, 'bold'))
        style.configure('search_result.Treeview', background='yellow')
        app.tree.tag_configure('search_match', background='yellow', foreground='black')
        
        print("GUI初始化完成，开始主循环...")
        root.mainloop()
        print("GUI已关闭")
        
    except Exception as e:
        print(f"GUI启动失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()