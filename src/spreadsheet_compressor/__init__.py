"""Spreadsheet Compressor - Compress Excel files for LLM consumption."""

__version__ = "0.1.0"

from .spreadsheet_compressor import compress_excel, compress_excel_legacy

__all__ = ['compress_excel', 'compress_excel_legacy']
