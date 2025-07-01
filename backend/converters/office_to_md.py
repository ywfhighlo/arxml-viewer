from typing import List, Optional
import os
from .base_converter import BaseConverter
import re
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

# PDF处理
try:
    import pypdf
    import pytesseract
    from pdf2image import convert_from_path
    pdf_available = True
except ImportError:
    pdf_available = False

# Office文件处理
try:
    import docx2txt
    docx_available = True
except ImportError:
    docx_available = False

try:
    import pandas as pd
    import tabulate
    pandas_available = True
except ImportError:
    pandas_available = False

try:
    from pptx import Presentation
    pptx_available = True
except ImportError:
    pptx_available = False

# HTML转Markdown
try:
    import html2text
    html2text_available = True
except ImportError:
    html2text_available = False

class OfficeToMdConverter(BaseConverter):
    """
    Office 文档到 Markdown 转换器
    
    迁移自 tools/office_to_md.py 的成熟转换逻辑
    支持 PDF/DOCX/XLSX/PPTX/HTML -> Markdown 转换
    """
    
    def __init__(self, output_dir: str, **kwargs):
        super().__init__(output_dir, **kwargs)
        self.poppler_path = kwargs.get('poppler_path')
        self.tesseract_cmd = kwargs.get('tesseract_cmd')
        self._check_dependencies()
        
    def _check_dependencies(self):
        """检查依赖库是否已安装"""
        missing_deps = []
        
        if not pdf_available:
            missing_deps.append("pypdf, pytesseract, pdf2image (用于PDF处理)")
            self.logger.warning("PDF处理库未安装，PDF转换功能将受限")
            
        if not docx_available:
            missing_deps.append("docx2txt (用于Word文档处理)")
            self.logger.warning("docx2txt库未安装，Word转换功能将受限")
            
        if not pandas_available:
            missing_deps.append("pandas, tabulate (用于Excel文件处理)")
            self.logger.warning("pandas/tabulate库未安装，Excel转换功能将受限")
            
        if not pptx_available:
            missing_deps.append("python-pptx (用于PowerPoint文件处理)")
            self.logger.warning("python-pptx库未安装，PowerPoint转换功能将受限")
            
        if not html2text_available:
            self.logger.warning("html2text库未安装，HTML转换功能将受限")
            
        # 检查tesseract是否安装
        try:
            subprocess.run(["tesseract", "--version"], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, 
                          check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            missing_deps.append("tesseract-ocr (用于图像OCR处理)")
            self.logger.warning("tesseract未安装，OCR功能将不可用")
            
        if missing_deps:
            self.logger.warning(f"以下依赖缺失，部分功能可能不可用: {', '.join(missing_deps)}")
    
    def convert(self, input_path: str) -> List[str]:
        """
        转换 Office 文档为 Markdown
        
        Args:
            input_path: 输入的 Office 文件或包含 Office 文件的目录
            
        Returns:
            List[str]: 生成的输出文件路径列表
        """
        # 支持的文件扩展名
        supported_extensions = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.xlsm', 
                              '.pptx', '.ppt', '.html', '.htm']
        
        # 验证输入
        if not self._is_valid_input(input_path, supported_extensions):
            raise ValueError(f"无效的输入文件或目录: {input_path}")
        
        output_files = []
        
        if os.path.isfile(input_path):
            # 单文件转换
            output_file = self._convert_single_file(input_path)
            if output_file:
                output_files.append(output_file)
        else:
            # 批量转换目录下的所有支持文件
            office_files = self._get_files_by_extension(input_path, supported_extensions)
            if not office_files:
                raise ValueError(f"目录中未找到支持的Office文件: {input_path}")
            
            for office_file in office_files:
                output_file = self._convert_single_file(office_file)
                if output_file:
                    output_files.append(output_file)
        
        return output_files
    
    def _convert_single_file(self, file_path: str) -> Optional[str]:
        """
        转换单个 Office 文件
        
        Args:
            file_path: Office 文件路径
            
        Returns:
            str: 输出文件路径，失败时返回 None
        """
        file_path_obj = Path(file_path)
        file_type = self._get_file_type(file_path_obj)
        
        if not file_type:
            self.logger.warning(f"不支持的文件类型: {file_path}")
            return None
        
        try:
            self.logger.info(f"正在处理{file_type}文件: {file_path_obj.name}...")
            
            # 根据文件类型提取文本
            if file_type == 'pdf':
                text = self._extract_text_from_pdf(file_path_obj)
                md_text = self._convert_to_markdown(text) if text else ""
            elif file_type == 'word':
                text = self._extract_text_from_word(file_path_obj)
                md_text = self._convert_to_markdown(text) if text else ""
            elif file_type == 'excel':
                # Excel已经转为markdown表格，不需要再转换
                md_text = self._extract_text_from_excel(file_path_obj)
            elif file_type == 'powerpoint':
                md_text = self._extract_text_from_powerpoint(file_path_obj)
            elif file_type == 'html':
                md_text = self._extract_text_from_html(file_path_obj)
            else:
                self.logger.warning(f"未知文件类型: {file_type}")
                return None
            
            if md_text:
                output_file = self._save_markdown(md_text, file_path_obj)
                return output_file
            else:
                self.logger.warning(f"无法从 {file_path_obj.name} 提取文本")
                return None
                
        except Exception as e:
            self.logger.error(f"处理文件 {file_path} 失败: {str(e)}")
            return None
    
    def _get_file_type(self, file_path: Path) -> Optional[str]:
        """
        检查文件是否为支持的格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件类型，如果不支持则返回None
        """
        suffix = file_path.suffix.lower()
        
        if suffix in ['.pdf']:
            return 'pdf'
        elif suffix in ['.docx', '.doc']:
            return 'word'
        elif suffix in ['.xlsx', '.xls', '.xlsm']:
            return 'excel'
        elif suffix in ['.pptx', '.ppt']:
            return 'powerpoint'
        elif suffix in ['.html', '.htm']:
            return 'html'
        else:
            return None
    
    def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        """
        从PDF文件提取文本
        迁移自 tools/office_to_md.py
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            提取的文本内容
        """
        if not pdf_available:
            self.logger.error("PDF处理库未安装，无法处理PDF文件")
            return "## PDF内容提取失败\n\n需安装PDF处理库: pip install pypdf pytesseract pdf2image"
            
        try:
            # 首先尝试直接提取文本
            reader = pypdf.PdfReader(pdf_path)
            text = ""
            
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text.strip():
                    text += page_text + "\n\n"
                    
            # 如果提取的文本太少,可能是扫描版PDF,使用OCR
            if len(text.strip()) < 100:
                self.logger.info(f"{pdf_path.name} 可能是扫描版PDF,尝试使用OCR...")
                text = self._ocr_pdf(pdf_path)
                
            return text
            
        except Exception as e:
            self.logger.error(f"处理 {pdf_path} 时出错: {str(e)}")
            return ""
    
    def _ocr_pdf(self, pdf_path: Path) -> str:
        """使用OCR处理扫描版PDF"""
        try:
            # 如果用户提供了Tesseract的路径，则配置pytesseract
            if self.tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

            text = ""
            # 将PDF转换为图片，并传入poppler_path
            images = convert_from_path(pdf_path, poppler_path=self.poppler_path)
            
            for i, image in enumerate(images):
                self.logger.info(f"正在OCR第 {i+1}/{len(images)} 页...")
                text += pytesseract.image_to_string(image, lang='chi_sim+eng') + "\n\n"
                
            return text
            
        except Exception as e:
            self.logger.error(f"OCR处理失败: {str(e)}")
            # 返回一个有意义的错误信息，而不是让程序崩溃
            return f"## OCR处理失败\n\n错误信息: {str(e)}\n\n请确认:\n1. Tesseract-OCR已正确安装并配置了路径。\n2. Poppler已正确安装并配置了路径。\n3. 已安装tesseract对应的语言数据包 (如 chi_sim)。"
    
    def _extract_text_from_word(self, docx_path: Path) -> str:
        """
        从Word文档提取文本
        迁移自 tools/office_to_md.py
        
        Args:
            docx_path: Word文档路径
            
        Returns:
            提取的文本内容
        """
        if not docx_available:
            self.logger.error("docx2txt库未安装，无法处理Word文件")
            return "## Word内容提取失败\n\n需安装docx2txt库: pip install docx2txt"
            
        try:
            # 使用docx2txt提取文本
            text = docx2txt.process(docx_path)
            return text
            
        except Exception as e:
            self.logger.error(f"处理Word文档 {docx_path} 时出错: {str(e)}")
            return ""
    
    def _extract_text_from_excel(self, excel_path: Path) -> str:
        """
        从Excel文档提取文本
        迁移自 tools/office_to_md.py
        
        Args:
            excel_path: Excel文档路径
            
        Returns:
            提取的文本内容，以Markdown表格形式
        """
        if not pandas_available:
            self.logger.error("pandas/tabulate库未安装，无法处理Excel文件")
            return "## Excel内容提取失败\n\n需安装相关库: pip install pandas tabulate openpyxl"
            
        try:
            # 读取所有sheet
            xls = pd.ExcelFile(excel_path)
            md_text = ""
            
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(excel_path, sheet_name=sheet_name)
                
                # 添加sheet名称作为标题
                md_text += f"## Sheet: {sheet_name}\n\n"
                
                # 转换为markdown表格
                md_table = df.to_markdown(index=False)
                md_text += md_table + "\n\n"
                
            return md_text
            
        except ImportError as e:
            if "openpyxl" in str(e):
                self.logger.error(f"处理Excel文档 {excel_path} 时出错: 缺少openpyxl依赖")
                return "## Excel内容提取失败\n\n需安装openpyxl库: pip install openpyxl\n\n错误信息: " + str(e)
            elif "tabulate" in str(e):
                self.logger.error(f"处理Excel文档 {excel_path} 时出错: 缺少tabulate依赖")
                return "## Excel内容提取失败\n\n需安装tabulate库: pip install tabulate\n\n错误信息: " + str(e)
            else:
                self.logger.error(f"处理Excel文档 {excel_path} 时出错: {str(e)}")
                return ""
        except Exception as e:
            self.logger.error(f"处理Excel文档 {excel_path} 时出错: {str(e)}")
            return ""
    
    def _extract_text_from_powerpoint(self, pptx_path: Path) -> str:
        """
        从PowerPoint文档提取文本
        迁移自 tools/office_to_md.py
        
        Args:
            pptx_path: PowerPoint文档路径
            
        Returns:
            提取的文本内容
        """
        if not pptx_available:
            self.logger.error("python-pptx库未安装，无法处理PowerPoint文件")
            return "## PowerPoint内容提取失败\n\n需安装python-pptx库: pip install python-pptx"
            
        try:
            prs = Presentation(pptx_path)
            md_text = ""
            
            for i, slide in enumerate(prs.slides):
                md_text += f"## 幻灯片 {i+1}\n\n"
                
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        md_text += f"{shape.text}\n\n"
                        
                # 添加分隔线
                md_text += "---\n\n"
                
            return md_text
            
        except Exception as e:
            self.logger.error(f"处理PowerPoint文档 {pptx_path} 时出错: {str(e)}")
            return ""
    
    def _extract_text_from_html(self, html_path: Path) -> str:
        """
        从HTML文件提取并转换为Markdown文本
        迁移自 tools/office_to_md.py
        
        Args:
            html_path: HTML文件路径
            
        Returns:
            Markdown格式文本
        """
        if not html2text_available:
            self.logger.error("html2text库未安装，无法处理HTML文件")
            return "## HTML内容提取失败\n\n需安装html2text库: pip install html2text"
            
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            h = html2text.HTML2Text()
            h.ignore_links = False
            md_text = h.handle(html_content)
            return md_text
        except Exception as e:
            self.logger.error(f"处理HTML文档 {html_path} 时出错: {str(e)}")
            return ""
    
    def _convert_to_markdown(self, text: str) -> str:
        """
        将提取的文本转换为Markdown格式
        迁移自 tools/office_to_md.py
        
        Args:
            text: 提取的原始文本
            
        Returns:
            markdown格式的文本
        """
        # 基本的Markdown转换规则
        md_text = text
        
        # 1. 处理标题
        # 假设大写字母开头的行是标题
        md_text = re.sub(r'^([A-Z][^.\n]+)$', r'# \1', md_text, flags=re.MULTILINE)
        
        # 2. 处理列表
        # 假设数字开头的行是有序列表
        md_text = re.sub(r'^\s*(\d+)\.\s+', r'\1. ', md_text, flags=re.MULTILINE)
        
        # 3. 处理加粗文本（假设全大写或带有星号的文本是要加粗的）
        md_text = re.sub(r'\*([^*]+)\*', r'**\1**', md_text)
        
        # 4. 处理代码块
        # 假设缩进的行是代码
        md_text = re.sub(r'(?m)^(\s{4,})(.*?)$', r'```\n\2\n```', md_text)
        
        return md_text
    
    def _save_markdown(self, md_text: str, file_path: Path) -> str:
        """
        保存Markdown文件
        迁移自 tools/office_to_md.py
        
        Args:
            md_text: markdown文本
            file_path: 原文件路径
            
        Returns:
            str: 保存的Markdown文件路径
        """
        # 创建输出文件路径
        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 生成输出文件名
        file_name = file_path.stem
        file_type = file_path.suffix.lower()[1:]  # 不包含点的扩展名
        
        output_file = output_path / f"{file_name}.md"
        
        # 添加文件头
        header = f"""---
title: {file_name} Document
source_file: {file_path.name}
file_type: {file_type}
converted_date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
---

"""
        md_text = header + md_text
        
        # 保存文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(md_text)
            
        self.logger.info(f"已保存到 {output_file}")
        return str(output_file) 