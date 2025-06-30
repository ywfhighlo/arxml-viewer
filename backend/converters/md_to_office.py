from typing import List, Optional
import os
from .base_converter import BaseConverter
import json
import subprocess
import platform
import re
import shutil
from datetime import datetime
from pathlib import Path

# 平台检测和条件导入（迁移自tools/md_to_docx.py）
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    try:
        from win32com.client import Dispatch
        from docx.enum.section import WD_SECTION_START
        from docxcompose.composer import Composer
        from docx import Document
        from docxtpl import DocxTemplate
        WIN32COM_AVAILABLE = True
    except ImportError:
        WIN32COM_AVAILABLE = False
else:
    WIN32COM_AVAILABLE = False
    WD_SECTION_START = None

class MdToOfficeConverter(BaseConverter):
    """
    Markdown 到 Office 文档转换器
    
    迁移自 tools/md_to_docx.py 的成熟转换逻辑
    支持 Markdown -> DOCX/PDF/HTML 转换
    """
    
    def __init__(self, output_dir: str, **kwargs):
        super().__init__(output_dir, **kwargs)
        self.output_format = kwargs.get('output_format', 'docx')
        self.template_path = kwargs.get('template_path')
        
        # 验证输出格式
        if self.output_format not in ['docx', 'pdf', 'html']:
            raise ValueError(f"不支持的输出格式: {self.output_format}")
    
    def convert(self, input_path: str) -> List[str]:
        """
        将 Markdown 文件转换为指定的 Office 格式
        
        Args:
            input_path: 输入的 .md 文件或包含 .md 文件的目录
            
        Returns:
            List[str]: 生成的输出文件路径列表
        """
        # 验证输入
        if not self._is_valid_input(input_path, ['.md']):
            raise ValueError(f"无效的输入文件或目录: {input_path}")
        
        output_files = []
        
        if os.path.isfile(input_path):
            # 单文件转换
            output_file = self._convert_single_file(input_path)
            if output_file:
                output_files.append(output_file)
        else:
            # 批量转换目录下的所有 .md 文件
            md_files = self._get_files_by_extension(input_path, ['.md'])
            if not md_files:
                raise ValueError(f"目录中未找到 .md 文件: {input_path}")
            
            for md_file in md_files:
                output_file = self._convert_single_file(md_file)
                if output_file:
                    output_files.append(output_file)
        
        return output_files
    
    def _convert_single_file(self, md_file: str) -> Optional[str]:
        """
        转换单个 Markdown 文件
        基于 tools/md_to_docx.py 的 convert_to_docx 函数逻辑
        
        Args:
            md_file: Markdown 文件路径
            
        Returns:
            str: 输出文件路径，失败时返回 None
        """
        try:
            if self.output_format == 'docx':
                return self._convert_to_docx(md_file)
            elif self.output_format == 'pdf':
                return self._convert_to_pdf(md_file)
            elif self.output_format == 'html':
                return self._convert_to_html(md_file)
        except Exception as e:
            self.logger.error(f"转换文件 {md_file} 失败: {str(e)}")
            return None
    
    def _convert_to_docx(self, md_file: str) -> Optional[str]:
        """
        转换为 DOCX 格式
        迁移自 tools/md_to_docx.py 的 convert_to_docx 函数
        """
        input_path = Path(md_file)
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 创建输出文件名
        if self.template_path and WIN32COM_AVAILABLE:
            output_file = str(output_path / f"{input_path.stem}.template.docx")
        else:
            output_file = str(output_path / f"{input_path.stem}.docx")
        
        # 检查输入文件是否存在
        if not input_path.exists():
            self.logger.error(f"找不到输入文件: {md_file}")
            return None
        
        try:
            # 处理标题前的序号, 图片标题, 和列表前的空行
            processed_file = self._remove_title_numbers(md_file)
            
            # 设置资源路径列表，包括Markdown文件所在目录
            resource_paths = [
                str(input_path.parent),
                str(input_path.parent.parent)  # 上级目录(支持../路径)
            ]
            resource_path_arg = '--resource-path=' + os.pathsep.join(resource_paths)
            
            # 检查pandoc是否可用
            if not self._check_tool_availability("pandoc"):
                self.logger.error(f"找不到pandoc命令，无法转换文件: {md_file}")
                return None
            
            # 如果使用模板且在Windows上
            if self.template_path and os.path.exists(self.template_path) and WIN32COM_AVAILABLE:
                return self._convert_with_template(processed_file, input_path, output_path, resource_path_arg, md_file)
            else:
                # 使用简单pandoc转换
                return self._convert_simple_docx(processed_file, output_file, resource_path_arg, md_file)
                
        except Exception as e:
            self.logger.error(f"处理文件 {md_file} 时出错: {str(e)}")
            return None
    
    def _convert_with_template(self, processed_file: str, input_path: Path, 
                             output_path: Path, resource_path_arg: str, original_file: str) -> Optional[str]:
        """使用模板转换DOCX"""
        temp_docx = str(output_path / f"{input_path.stem}_temp.docx")
        
        # 构建pandoc命令
        cmd = [
            'pandoc',
            processed_file,
            '-o', temp_docx,
            resource_path_arg,
            '--quiet'
        ]
        
        # 执行pandoc命令
        try:
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                self.logger.error(f"Pandoc转换失败: {stderr}")
                return None
        except FileNotFoundError:
            self.logger.error("无法执行pandoc命令，请确保pandoc已正确安装")
            return None
        
        # 获取文档标题
        title = self._get_title_from_md(processed_file)
        
        # 复制模板并追加内容
        try:
            final_output = self._copy_template_and_append_content(self.template_path, temp_docx, title)
            
            # 清理临时文件
            self._cleanup_temp_files([temp_docx], processed_file, original_file)
            
            self.logger.info(f"成功转换: {original_file} -> {final_output}")
            return final_output
            
        except Exception as e:
            self.logger.error(f"模板处理失败: {e}")
            self._cleanup_temp_files([temp_docx], processed_file, original_file)
            return None
    
    def _convert_simple_docx(self, processed_file: str, output_file: str, 
                           resource_path_arg: str, original_file: str) -> Optional[str]:
        """简单pandoc转换，适用于所有系统"""
        cmd = [
            'pandoc',
            processed_file,
            '-o', output_file,
            resource_path_arg,
            '--quiet'
        ]
        
        try:
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            stdout, stderr = process.communicate()
            
            # 清理临时文件
            if processed_file != original_file:
                try:
                    os.remove(processed_file)
                except Exception as e:
                    self.logger.warning(f"无法删除临时文件 {processed_file}: {e}")
            
            if process.returncode != 0:
                self.logger.error(f"转换失败: {original_file} -> {output_file}")
                self.logger.error(f"错误: {stderr}")
                return None
                
        except FileNotFoundError:
            self.logger.error("无法执行pandoc命令，请确保pandoc已正确安装")
            if processed_file != original_file:
                try:
                    os.remove(processed_file)
                except:
                    pass
            return None
        
        self.logger.info(f"成功转换: {original_file} -> {output_file}")
        return output_file
    
    def _convert_to_pdf(self, md_file: str) -> Optional[str]:
        """
        转换为 PDF 格式
        先转换为DOCX，然后转为PDF
        """
        # 先转为DOCX
        docx_file = self._convert_to_docx(md_file)
        if not docx_file:
            return None
        
        # 转换DOCX为PDF
        pdf_file = self._convert_docx_to_pdf(docx_file)
        return pdf_file
    
    def _convert_to_html(self, md_file: str) -> Optional[str]:
        """
        转换为 HTML 格式
        迁移自 tools/md_to_docx.py 的 convert_md_to_html 函数
        """
        input_path = Path(md_file)
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        output_file = str(output_path / f"{input_path.stem}.html")
        
        if not input_path.exists():
            self.logger.error(f"找不到输入文件: {md_file}")
            return None
        
        try:
            # 处理标题前的序号等
            processed_file = self._remove_title_numbers(md_file)
            
            # 设置资源路径列表
            resource_paths = [
                str(input_path.parent),
                str(input_path.parent.parent)
            ]
            resource_path_arg = '--resource-path=' + os.pathsep.join(resource_paths)
            
            # 构建pandoc命令
            cmd = [
                'pandoc',
                processed_file,
                '-o', output_file,
                '--standalone',
                '--metadata', f'title={self._get_title_from_md(processed_file)}',
                resource_path_arg,
                '--quiet'
            ]
            
            # 检查pandoc是否可用
            if not self._check_tool_availability("pandoc"):
                self.logger.error(f"找不到pandoc命令，无法转换HTML文件: {md_file}")
                return None
            
            # 执行pandoc命令
            try:
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    self.logger.error(f"Pandoc HTML转换失败: {stderr}")
                    return None
            except FileNotFoundError:
                self.logger.error("无法执行pandoc命令，请确保pandoc已正确安装")
                return None
            
            # 后处理HTML文件，添加样式和目录
            self._post_process_html(output_file, processed_file)
            
            # 清理临时文件
            if processed_file != md_file:
                try:
                    os.remove(processed_file)
                except Exception as e:
                    self.logger.warning(f"无法删除临时文件 {processed_file}: {e}")
            
            self.logger.info(f"成功生成HTML: {md_file} -> {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"处理HTML文件 {md_file} 时出错: {str(e)}")
            return None
    
    # 以下是从 tools/md_to_docx.py 迁移的辅助函数
    
    def _check_tool_availability(self, tool_name: str) -> bool:
        """检查外部工具是否可用"""
        return shutil.which(tool_name) is not None
    
    def _get_title_from_md(self, md_file: str) -> str:
        """从markdown文件中提取标题"""
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line.startswith('# '):
                    return first_line[2:].strip()
        except Exception:
            pass
        return os.path.splitext(os.path.basename(md_file))[0]
    
    def _remove_title_numbers(self, input_file: str) -> str:
        """
        处理Markdown文件，去掉标题前面的序号（如1.1、2.3.4等格式），
        并删除图片标题，同时确保列表前有空行以便Pandoc正确识别。
        """
        try:
            # 读取原始文件内容
            with open(input_file, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # 1. 正则表达式匹配标题前的序号
            pattern_title_numbers = r'^(#+)\s+(\d+(\.\d+)*)\s+(.+)$'
            processed_content = re.sub(pattern_title_numbers, r'\1 \4', original_content, flags=re.MULTILINE)
            
            # 2. 删除图片标题
            processed_content = self._remove_image_captions(processed_content)

            # 3. 确保列表前有空行以便Pandoc正确识别
            lines = processed_content.splitlines()
            new_processed_lines = []
            list_markers = ("- ", "* ", "+ ")
            
            for i, current_line_text in enumerate(lines):
                stripped_line = current_line_text.lstrip()
                is_list_item = any(stripped_line.startswith(marker) for marker in list_markers)

                if is_list_item:
                    if i > 0:
                        previous_line_text = lines[i-1]
                        stripped_previous_line = previous_line_text.lstrip()
                        is_previous_list_item = any(stripped_previous_line.startswith(marker) for marker in list_markers)
                        
                        if previous_line_text.strip() and not is_previous_list_item:
                            new_processed_lines.append("")
                
                new_processed_lines.append(current_line_text)
            
            processed_content = "\n".join(new_processed_lines)
            
            # 确保处理后的内容以换行符结尾
            if original_content.endswith('\n') and not processed_content.endswith('\n'):
                processed_content += '\n'
            elif new_processed_lines and any(new_processed_lines[-1].lstrip().startswith(marker) for marker in list_markers) and not processed_content.endswith('\n'):
                processed_content += '\n'

            # 如果内容没有变化，直接返回原文件路径
            if processed_content == original_content:
                return input_file
            
            # 创建临时文件保存处理后的内容
            temp_file = input_file + '.temp.md'
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(processed_content)
            
            return temp_file
        except Exception as e:
            self.logger.error(f"处理Markdown预处理时出错 (file: {input_file}): {str(e)}")
            return input_file
    
    def _remove_image_captions(self, content: str) -> str:
        """删除图片标题（占位符实现）"""
        # 这里可以添加具体的图片标题删除逻辑
        return content
    
    def _convert_docx_to_pdf(self, docx_path: str) -> Optional[str]:
        """
        将docx转换为PDF
        迁移自 tools/md_to_docx.py 的 convert_docx_to_pdf 函数
        """
        pdf_path = str(Path(docx_path).with_suffix('.pdf'))
        
        # Windows系统使用Word COM对象
        if WIN32COM_AVAILABLE:
            word = Dispatch('Word.Application')
            word.Visible = False
            
            try:
                doc = word.Documents.Open(str(Path(docx_path).resolve()))
                pdf_format = 17
                doc.SaveAs(str(Path(pdf_path).resolve()), FileFormat=pdf_format)
                doc.Close()
                
                self.logger.info(f"成功生成PDF: {pdf_path}")
                return pdf_path
            except Exception as e:
                self.logger.error(f"转换PDF失败: {docx_path} -> {pdf_path}")
                self.logger.error(f"错误: {str(e)}")
                return None
            finally:
                word.Quit()
        
        # 非Windows系统尝试使用其他工具
        else:
            # 尝试使用LibreOffice
            if self._check_tool_availability("soffice"):
                try:
                    cmd = [
                        "soffice",
                        "--headless",
                        "--convert-to", "pdf",
                        "--outdir", str(Path(pdf_path).parent),
                        str(docx_path)
                    ]
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                    
                    if result.returncode == 0:
                        self.logger.info(f"成功使用LibreOffice生成PDF: {pdf_path}")
                        return pdf_path
                    else:
                        self.logger.error(f"LibreOffice转换失败: {result.stderr}")
                except Exception as e:
                    self.logger.error(f"LibreOffice转换错误: {str(e)}")
            
            self.logger.warning("无法转换为PDF，跳过PDF生成")
            return None
    
    def _copy_template_and_append_content(self, template_path: str, content_path: str, title: str) -> str:
        """
        使用docxcompose合并模板和内容文档
        迁移自 tools/md_to_docx.py
        """
        if not WIN32COM_AVAILABLE:
            self.logger.warning("在非Windows系统上无法使用模板功能，将使用简单转换")
            return content_path
            
        output_path = str(Path(content_path).parent / f"{Path(content_path).stem.replace('_temp', '')}.template.docx")
        
        try:
            # 获取模板上下文数据（简化版）
            context = {
                'project_name': 'Markdown Docs Converter',
                'title': title,
                'document_no': "P" + datetime.now().strftime("%Y%m%d%H%M%S"),
                'date': datetime.now().strftime("%Y-%m-%d"),
                'author': '余文锋',
                'mobilephone': '',
                'email': ''
            }
            
            # 使用DocxTemplate渲染模板
            doc = DocxTemplate(template_path)
            doc.render(context)
            doc.save(output_path)

            # 加载渲染后的模板文档
            master = Document(output_path)
            composer = Composer(master)
            
            # 加载内容文档
            doc2 = Document(content_path)
            
            # 在模板文档末尾添加连续分节符
            section = master.add_section()
            section.start_type = WD_SECTION_START.CONTINUOUS
            
            # 合并文档，保留样式
            composer.append(doc2)
            
            # 更新文档属性
            master.core_properties.title = title
            
            # 保存文档
            composer.save(output_path)
            
            return output_path
        except Exception as e:
            self.logger.error(f"模板处理失败: {e}")
            return content_path
    
    def _post_process_html(self, html_file: str, processed_md_file: str):
        """后处理HTML文件，添加样式和目录"""
        try:
            # 读取生成的HTML文件
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # 获取GitHub主题CSS
            theme_css = self._get_github_theme_css()
            
            # 添加锚点ID到标题
            import re
            def add_anchor_to_heading(match):
                level = len(match.group(1))
                title = match.group(2)
                anchor_id = re.sub(r'[^\w\s-]', '', title).strip()
                anchor_id = re.sub(r'[\s_-]+', '-', anchor_id).lower()
                return f'<h{level} id="{anchor_id}">{title}</h{level}>'
            
            html_content = re.sub(r'<h([1-6])>(.*?)</h[1-6]>', add_anchor_to_heading, html_content)
            
            # 插入CSS样式
            css_insert = f'<style>\n{theme_css}\n</style>'
            if '</head>' in html_content:
                html_content = html_content.replace('</head>', f'{css_insert}\n</head>')
            else:
                html_content = f'<head>\n{css_insert}\n</head>\n{html_content}'
            
            # 写回HTML文件
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
        except Exception as e:
            self.logger.warning(f"HTML后处理失败: {e}")
    
    def _get_github_theme_css(self) -> str:
        """获取GitHub主题的CSS样式"""
        return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #24292e;
            max-width: 980px;
            margin: 0 auto;
            padding: 45px;
            background-color: #ffffff;
        }
        h1, h2, h3, h4, h5, h6 {
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
            line-height: 1.25;
        }
        h1 { font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 10px; }
        h2 { font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 8px; }
        h3 { font-size: 1.25em; }
        h4 { font-size: 1em; }
        h5 { font-size: 0.875em; }
        h6 { font-size: 0.85em; color: #6a737d; }
        p { margin-top: 0; margin-bottom: 16px; }
        blockquote {
            padding: 0 1em;
            color: #6a737d;
            border-left: 0.25em solid #dfe2e5;
            margin: 0 0 16px 0;
        }
        ul, ol { padding-left: 2em; margin-top: 0; margin-bottom: 16px; }
        li { word-wrap: break-all; }
        code {
            padding: 0.2em 0.4em;
            margin: 0;
            font-size: 85%;
            background-color: rgba(27,31,35,0.05);
            border-radius: 3px;
        }
        pre {
            padding: 16px;
            overflow: auto;
            font-size: 85%;
            line-height: 1.45;
            background-color: #f6f8fa;
            border-radius: 3px;
        }
        """
    
    def _cleanup_temp_files(self, temp_files: List[str], processed_file: str, original_file: str):
        """清理临时文件"""
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                self.logger.warning(f"无法删除临时文件 {temp_file}: {e}")
        
        if processed_file != original_file:
            try:
                if os.path.exists(processed_file):
                    os.remove(processed_file)
            except Exception as e:
                self.logger.warning(f"无法删除临时文件 {processed_file}: {e}") 