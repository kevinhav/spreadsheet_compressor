"""Main public API for spreadsheet compression."""

import os
from typing import Optional, Dict
import pandas as pd

from .ExcelReaderFactory import create_reader
from .SheetCompressor import SheetCompressor
from .CompressionOutputFormatter import CompressionOutputFormatter


def compress_excel(
    input_path: str,
    k_parameter: int = 4,
    output_file: Optional[str] = None,
    sheet_name: Optional[str] = None
) -> Dict:
    """Compress Excel file into LLM-optimized JSON format.

    This is the main entry point for the spreadsheet compression library.
    It reads an Excel file (.xls or .xlsx), applies the SpreadsheetLLM
    compression algorithm, and returns a structured JSON representation
    optimized for LLM consumption.

    Args:
        input_path: Path to .xls or .xlsx file
        k_parameter: Anchor expansion distance (default: 4)
            Higher values preserve more context around data boundaries
            but result in less compression
        output_file: Optional path to save JSON output
            If provided, writes the output to this file

    Returns:
        Dictionary with complete compression data:
            - metadata: File info, dimensions, compression ratio
            - compression_data: Value dictionary, format regions, anchor points
            - extraction_instructions: Guidance for LLM processing
            - tables: Empty array (to be populated by LLM)

    Raises:
        FileNotFoundError: If input_path doesn't exist
        ValueError: If file format is not .xls or .xlsx
        Exception: For other errors during processing

    Example:
        >>> result = compress_excel("sales_report.xlsx")
        >>> print(result['metadata']['compression_ratio'])
        25.6

        >>> # Save to file
        >>> result = compress_excel("data.xls", k_parameter=6, output_file="compressed.json")

        >>> # Batch processing
        >>> import glob
        >>> for file in glob.glob("*.xlsx"):
        ...     compress_excel(file, output_file=file.replace(".xlsx", "_compressed.json"))
    """

    # Validate input file exists
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Get file info
    filename = os.path.basename(input_path)
    file_ext = input_path.lower().split('.')[-1]

    try:
        # Step 1: Read Excel file with appropriate reader
        reader = create_reader(input_path)
        wb = reader.read_workbook(input_path)
        # Allow callers to request a specific sheet by name or index; pass through
        sheet = reader.get_dataframe(wb, sheet_name=sheet_name)

        # Store original dimensions
        original_dims = (len(sheet), len(sheet.columns))

        # Step 2: Initialize compressor with K parameter
        compressor = SheetCompressor(k=k_parameter)

        # Step 3: Apply anchoring algorithm
        compressed_sheet = compressor.anchor(sheet)
        compressed_dims = (len(compressed_sheet), len(compressed_sheet.columns))

        # Step 5: Encode to markdown format (only data-type information retained)
        markdown = compressor.encode(compressed_sheet)

        # Step 6: Create value dictionary (inverted index)
        compress_dict = compressor.inverted_index(markdown)

        # Step 7: Add category information to markdown
        markdown['Category'] = markdown['Value'].apply(compressor.get_category)

        # Step 8: Create category dictionary
        category_dict = compressor.inverted_category(markdown)

        # Step 9: Perform identical cell aggregation to find regions
        areas = compressor.identical_cell_aggregation(compressed_sheet, category_dict)

        # Step 10: Get compression metadata
        original_size = original_dims[0] * original_dims[1]
        compressed_size = compressed_dims[0] * compressed_dims[1]
        compression_metadata = compressor.get_compression_metadata(original_size, compressed_size)

        # Step 11: Format as separate compressed and encoded JSON outputs
        formatter = CompressionOutputFormatter()
        compressed_output = formatter.format_unified_output(
            filename=filename,
            file_format=file_ext,
            original_dims=original_dims,
            compressed_dims=compressed_dims,
            areas=areas,
            compress_dict=compress_dict,
            compression_metadata=compression_metadata
        )

        encoded_output = formatter.format_encoded_output(
            markdown=markdown,
            filename=filename,
            file_format=file_ext
        )

        result = {
            'compressed': compressed_output,
            'encoded': encoded_output
        }

        # Step 12: Optionally write to file
        if output_file:
            formatter.write_to_file(result, output_file)

        return result

    except ValueError as e:
        # Re-raise format errors
        raise e
    except Exception as e:
        # Wrap other errors with context
        raise Exception(f"Error processing {filename}: {str(e)}") from e


def compress_excel_legacy(
    input_path: str,
    k_parameter: int = 4,
    areas_output: Optional[str] = None,
    dict_output: Optional[str] = None
) -> Dict:
    """Compress Excel file using legacy _areas.txt and _dict.txt format.

    This function provides backward compatibility with the original
    spreadsheet-llm-unofficial output format.

    Args:
        input_path: Path to .xls or .xlsx file
        k_parameter: Anchor expansion distance (default: 4)
        areas_output: Optional path for _areas.txt file
        dict_output: Optional path for _dict.txt file

    Returns:
        Dictionary with 'areas' and 'dict' keys

    Example:
        >>> result = compress_excel_legacy(
        ...     "data.xlsx",
        ...     areas_output="output_areas.txt",
        ...     dict_output="output_dict.txt"
        ... )
    """

    # Get unified output
    result = compress_excel(input_path, k_parameter=k_parameter)

    # Extract areas and dict
    areas_list = []
    for region in result['compression_data']['format_regions']:
        top_left = (region['bounds']['top_left']['row'], region['bounds']['top_left']['col'])
        bottom_right = (region['bounds']['bottom_right']['row'], region['bounds']['bottom_right']['col'])
        areas_list.append([top_left, bottom_right, region['format_type']])

    compress_dict = result['compression_data']['value_dictionary']

    # Write legacy format if paths provided
    if areas_output or dict_output:
        formatter = CompressionOutputFormatter()
        if areas_output and dict_output:
            formatter.write_legacy_format(areas_list, compress_dict, areas_output, dict_output)

    return {
        'areas': areas_list,
        'dict': compress_dict
    }
