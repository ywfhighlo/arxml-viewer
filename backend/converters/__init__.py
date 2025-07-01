from .md_to_office import MdToOfficeConverter
from .office_to_md import OfficeToMdConverter
from .diagram_to_png import DiagramToPngConverter
from .md_to_ppt import MdToPptConverter

CONVERTER_REGISTRY = {
    'md-to-docx': MdToOfficeConverter,
    'md-to-pdf': MdToOfficeConverter,
    'md-to-html': MdToOfficeConverter,
    'md-to-pptx': MdToPptConverter,
    'office-to-md': OfficeToMdConverter,
    'diagram-to-png': DiagramToPngConverter,
} 