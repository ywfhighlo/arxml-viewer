from typing import List, Optional
import os
import subprocess
import tempfile
import re
import shutil
from pathlib import Path

# 图形处理库
try:
    from PIL import Image
    pil_available = True
except ImportError:
    pil_available = False

try:
    import cairosvg
    cairosvg_available = True
except ImportError:
    cairosvg_available = False

try:
    from svglib.svglib import renderSVG
    from reportlab.graphics import renderPM
    svglib_available = True
except ImportError:
    svglib_available = False

from .base_converter import BaseConverter

class DiagramToPngConverter(BaseConverter):
    """
    图表到 PNG 转换器
    
    迁移自 tools/convert_figures.py 的成熟转换逻辑
    支持 SVG/Mermaid -> PNG 转换
    """
    
    # SVG图像DPI常量
    DEFAULT_DPI = 300
    
    def __init__(self, output_dir: str, **kwargs):
        super().__init__(output_dir, **kwargs)
        self.dpi = kwargs.get('dpi', self.DEFAULT_DPI)
        self._check_dependencies()
        
    def _check_dependencies(self):
        """检查依赖库和外部工具是否已安装"""
        missing_deps = []
        
        if not pil_available:
            missing_deps.append("Pillow (用于图像处理)")
            self.logger.warning("Pillow库未安装，图像处理功能将受限")
            
        if not cairosvg_available:
            missing_deps.append("cairosvg (用于SVG转换)")
            self.logger.warning("cairosvg库未安装，SVG转换功能将受限")
            
        if not svglib_available:
            missing_deps.append("svglib, reportlab (用于SVG转换)")
            self.logger.warning("svglib/reportlab库未安装，SVG转换功能将受限")
            
        # 检查外部工具
        tools_status = {}
        external_tools = ['inkscape', 'rsvg-convert', 'mmdc']
        
        for tool in external_tools:
            if self._check_tool_availability(tool):
                tools_status[tool] = True
                self.logger.info(f"检测到外部工具: {tool}")
            else:
                tools_status[tool] = False
                
        self.tools_status = tools_status
        
        if missing_deps:
            self.logger.warning(f"以下依赖缺失，部分功能可能不可用: {', '.join(missing_deps)}")
    
    def _check_tool_availability(self, tool_name: str) -> bool:
        """检查外部工具是否可用"""
        return shutil.which(tool_name) is not None
    
    def convert(self, input_path: str) -> List[str]:
        """
        转换图表文件为 PNG
        
        Args:
            input_path: 输入的图表文件或包含图表文件的目录
            
        Returns:
            List[str]: 生成的输出文件路径列表
        """
        # 支持的文件扩展名
        supported_extensions = ['.svg', '.drawio', '.mmd']
        
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
            diagram_files = self._get_files_by_extension(input_path, supported_extensions)
            if not diagram_files:
                raise ValueError(f"目录中未找到支持的图表文件: {input_path}")
            
            for diagram_file in diagram_files:
                output_file = self._convert_single_file(diagram_file)
                if output_file:
                    output_files.append(output_file)
        
        return output_files
    
    def _convert_single_file(self, file_path: str) -> Optional[str]:
        """
        转换单个图表文件
        
        Args:
            file_path: 图表文件路径
            
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
            
            # 创建输出文件路径
            output_path = Path(self.output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            output_file = output_path / f"{file_path_obj.stem}.png"
            
            # 根据文件类型选择转换方法
            if file_type == 'svg':
                success = self._convert_svg_to_png(file_path_obj, output_file)
            elif file_type == 'mermaid':
                success = self._convert_mermaid_to_png(file_path_obj, output_file)
            elif file_type == 'drawio':
                success = self._convert_drawio_to_png(file_path_obj, output_file)
            else:
                self.logger.warning(f"未知文件类型: {file_type}")
                return None
            
            if success:
                self.logger.info(f"成功转换: {file_path} -> {output_file}")
                return str(output_file)
            else:
                self.logger.error(f"转换失败: {file_path}")
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
        
        if suffix in ['.svg']:
            return 'svg'
        elif suffix in ['.drawio']:
            return 'drawio'
        elif suffix in ['.mmd']:
            return 'mermaid'
        else:
            return None
    
    def _convert_svg_to_png(self, svg_file: Path, output_file: Path) -> bool:
        """
        SVG转PNG转换
        迁移自 tools/convert_figures.py 的 convert_svg_to_png 函数
        
        优先使用的转换方法顺序：
        1. Inkscape (命令行工具)
        2. rsvg-convert (命令行工具) 
        3. svglib/reportlab (Python库)
        4. cairosvg (Python库)
        """
        methods = [
            ("Inkscape", self._convert_with_inkscape),
            ("rsvg-convert", self._convert_with_rsvg),
            ("svglib", self._convert_with_svglib),
            ("cairosvg", self._convert_with_cairosvg)
        ]
        
        for method_name, method_func in methods:
            try:
                if method_func(svg_file, output_file, self.dpi):
                    self.logger.info(f"使用 {method_name} 成功转换 {svg_file.name}")
                    return True
            except Exception as e:
                self.logger.debug(f"{method_name} 转换失败: {str(e)}")
                continue
        
        self.logger.error(f"所有转换方法都失败了: {svg_file}")
        return False
    
    def _convert_with_inkscape(self, svg_file: Path, output_file: Path, dpi: int) -> bool:
        """使用Inkscape转换SVG"""
        if not self.tools_status.get('inkscape', False):
            return False
            
        try:
            cmd = [
                "inkscape",
                str(svg_file),
                "--export-type=png",
                f"--export-filename={output_file}",
                f"--export-dpi={dpi}"
            ]
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.returncode == 0
            
        except Exception:
            return False
    
    def _convert_with_rsvg(self, svg_file: Path, output_file: Path, dpi: int) -> bool:
        """使用rsvg-convert转换SVG"""
        if not self.tools_status.get('rsvg-convert', False):
            return False
            
        try:
            cmd = [
                "rsvg-convert",
                "-o", str(output_file),
                "-d", str(dpi),
                "-p", str(dpi),
                str(svg_file)
            ]
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return result.returncode == 0
            
        except Exception:
            return False
    
    def _convert_with_svglib(self, svg_file: Path, output_file: Path, dpi: int) -> bool:
        """使用svglib/reportlab转换SVG"""
        if not svglib_available:
            return False
            
        try:
            drawing = renderSVG.renderSVG(str(svg_file))
            renderPM.drawToFile(drawing, str(output_file), fmt="PNG", dpi=dpi)
            return True
            
        except Exception:
            return False
    
    def _convert_with_cairosvg(self, svg_file: Path, output_file: Path, dpi: int) -> bool:
        """使用cairosvg转换SVG"""
        if not cairosvg_available:
            return False
            
        try:
            with open(svg_file, 'rb') as f:
                svg_data = f.read()
            
            cairosvg.svg2png(
                bytestring=svg_data,
                write_to=str(output_file),
                dpi=dpi
            )
            return True
            
        except Exception:
            return False
    
    def _convert_mermaid_to_png(self, mermaid_file: Path, output_file: Path) -> bool:
        """
        转换Mermaid文件到PNG
        迁移自 tools/convert_figures.py 的 convert_mermaid_to_png 函数
        """
        if not self.tools_status.get('mmdc', False):
            self.logger.error("mermaid-cli (mmdc) 未安装，无法转换Mermaid图表")
            self.logger.info("请安装: npm install -g @mermaid-js/mermaid-cli")
            return False
        
        try:
            # 读取mermaid代码
            with open(mermaid_file, 'r', encoding='utf-8') as f:
                mermaid_code = f.read().strip()
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', encoding='utf-8', delete=False) as f:
                f.write(mermaid_code)
                temp_file = f.name
            
            try:
                # 使用mmdc转换
                cmd = [
                    "mmdc",
                    "-i", temp_file,
                    "-o", str(output_file),
                    "-t", "base",
                    "-b", "white"
                ]
                
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                return result.returncode == 0
                
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_file)
                except:
                    pass
                    
        except Exception as e:
            self.logger.error(f"转换Mermaid文件失败: {str(e)}")
            return False
    
    def _convert_drawio_to_png(self, drawio_file: Path, output_file: Path) -> bool:
        """
        转换Draw.io文件到PNG
        需要安装draw.io命令行工具
        """
        # Draw.io转换需要特殊的工具，这里提供一个基本实现
        self.logger.warning("Draw.io转换功能需要额外的工具支持")
        self.logger.info("请考虑手动导出为SVG格式，然后使用SVG转换功能")
        return False 