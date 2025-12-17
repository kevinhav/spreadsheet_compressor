"""Excel Reader Factory - Abstract multi-format Excel reading."""

from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any, Optional, Union
import pandas as pd
import xlrd
import openpyxl
from openpyxl.styles import Border, Fill, Font


class BaseExcelReader(ABC):
    """Abstract base class for Excel readers."""

    @abstractmethod
    def read_workbook(self, filepath: str) -> Any:
        """Read workbook from file.

        Args:
            filepath: Path to Excel file

        Returns:
            Workbook object (format-specific)
        """
        pass

    @abstractmethod
    def get_dataframe(self, wb: Any, sheet_name: Optional[Union[str, int]] = None) -> pd.DataFrame:
        """Convert workbook to pandas DataFrame.

        Args:
            wb: Workbook object

        Returns:
            pandas DataFrame
        """
        pass

    @abstractmethod
    def get_format_info(self, wb: Any, row: int, col: int) -> Dict[str, Any]:
        """Extract formatting information for a cell.

        Args:
            wb: Workbook object
            row: Row index (0-based)
            col: Column index (0-based)

        Returns:
            Dict with formatting info (borders, fill, font, etc.)
        """
        pass


class XLSReader(BaseExcelReader):
    """Reader for .xls files using xlrd."""

    def read_workbook(self, filepath: str) -> xlrd.book.Book:
        """Read .xls workbook using xlrd.

        Args:
            filepath: Path to .xls file

        Returns:
            xlrd Book object
        """
        return xlrd.open_workbook(filepath, formatting_info=True)

    def get_dataframe(self, wb: xlrd.book.Book, sheet_name: Optional[Union[str, int]] = None) -> pd.DataFrame:
        """Convert xlrd workbook to DataFrame.

        Args:
            wb: xlrd Book object

        Returns:
            pandas DataFrame from first sheet
        """
        # Read first sheet
        # If a sheet_name was provided, pass it through to pandas; otherwise default to sheet 0
        if sheet_name is None:
            sn = 0
        else:
            sn = sheet_name
        return pd.read_excel(wb, engine='xlrd', sheet_name=sn)

    def get_format_info(self, wb: xlrd.book.Book, row: int, col: int) -> Dict[str, Any]:
        """Extract format info from xlrd cell.

        Args:
            wb: xlrd Book object
            row: Row index
            col: Column index

        Returns:
            Dict with formatting information
        """
        sheet = wb.sheet_by_index(0)

        # We no longer extract stylistic formatting (borders/colors/fonts).
        # Return an empty dict for backward compatibility.
        return {}


class XLSXReader(BaseExcelReader):
    """Reader for .xlsx files using openpyxl."""

    def read_workbook(self, filepath: str) -> openpyxl.Workbook:
        """Read .xlsx workbook using openpyxl.

        Args:
            filepath: Path to .xlsx file

        Returns:
            openpyxl Workbook object
        """
        return openpyxl.load_workbook(filepath, data_only=True)

    def get_dataframe(self, wb: openpyxl.Workbook, sheet_name: Optional[Union[str, int]] = None) -> pd.DataFrame:
        """Convert openpyxl workbook to DataFrame.

        Args:
            wb: openpyxl Workbook object

        Returns:
            pandas DataFrame from active sheet
        """
        # Get active sheet as DataFrame, robustly handling a possible
        # single-row merged title above the true header row.
        def _get_sheet_rows(target_sheet):
            return list(target_sheet.values)

        # Determine which sheet to use (default to active)
        if sheet_name is None:
            sheet = wb.active
        else:
            # Allow either string name or integer index
            try:
                if isinstance(sheet_name, int):
                    sheet = wb.worksheets[sheet_name]
                else:
                    sheet = wb[sheet_name]
            except Exception:
                # fallback to active sheet
                sheet = wb.active

        rows = _get_sheet_rows(sheet)

        # Find header row: prefer the first row that has more than one non-None
        # cell. If the top row is a single merged title cell, skip it.
        header_idx = None
        for idx, row in enumerate(rows):
            non_null = [c for c in row if c is not None]
            if len(non_null) == 0:
                # empty row - skip
                continue
            # If row contains more than one non-empty cell, treat as header
            if len(non_null) > 1:
                header_idx = idx
                break
            # If single non-empty cell but it's clearly a header-like string
            # and next row exists with multiple entries, skip it as title
            if len(non_null) == 1 and idx + 1 < len(rows):
                next_non_null = [c for c in rows[idx + 1] if c is not None]
                if len(next_non_null) > 1:
                    # current row is probably a title, so continue to next
                    continue
                else:
                    header_idx = idx
                    break

        if header_idx is None:
            # fallback: use first row as header
            header_idx = 0

        cols = rows[header_idx]
        data = rows[header_idx + 1:]
        return pd.DataFrame(data, columns=cols)

    def get_format_info(self, wb: openpyxl.Workbook, row: int, col: int) -> Dict[str, Any]:
        """Extract format info from openpyxl cell.

        Args:
            wb: openpyxl Workbook object
            row: Row index (0-based)
            col: Column index (0-based)

        Returns:
            Dict with formatting information
        """
        # We no longer extract stylistic formatting (borders/colors/fonts).
        # Return an empty dict for backward compatibility.
        return {}


def create_reader(filepath: str) -> BaseExcelReader:
    """Factory function to create appropriate Excel reader based on file extension.

    Args:
        filepath: Path to Excel file

    Returns:
        BaseExcelReader instance (XLSReader or XLSXReader)

    Raises:
        ValueError: If file format is not supported
    """
    ext = filepath.lower().split('.')[-1]

    if ext == 'xls':
        return XLSReader()
    elif ext == 'xlsx':
        return XLSXReader()
    else:
        raise ValueError(f"Unsupported file format: .{ext}. Only .xls and .xlsx are supported.")
