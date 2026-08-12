"""报告产出层：资料提取、模板注册与 Word 排版。"""
from .docx_writer import DOCX_AVAILABLE, render
from .materials import SUPPORTED_SUFFIXES, extract_text
from .templates import DEFAULT_TEMPLATE, ReportTemplate, get_template, list_templates

__all__ = ['render', 'DOCX_AVAILABLE', 'extract_text', 'SUPPORTED_SUFFIXES',
           'get_template', 'list_templates', 'DEFAULT_TEMPLATE', 'ReportTemplate']
