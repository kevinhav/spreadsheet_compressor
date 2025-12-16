"""Compression Output Formatter - Generate unified LLM-optimized JSON output."""

import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from .IndexColumnConverter import IndexColumnConverter


class CompressionOutputFormatter:
    """Format compression artifacts into LLM-optimized JSON structure."""

    def __init__(self):
        self.format_version = "1.0"
        self.converter = IndexColumnConverter()

    def format_unified_output(self,
                             filename: str,
                             file_format: str,
                             original_dims: Tuple[int, int],
                             compressed_dims: Tuple[int, int],
                             areas: List,
                             compress_dict: Dict,
                             compression_metadata: Dict) -> Dict:
        """Transform areas + dict into unified LLM-optimized JSON.

        Args:
            filename: Source file name
            file_format: File extension (xls or xlsx)
            original_dims: (rows, cols) of original sheet
            compressed_dims: (rows, cols) of compressed sheet
            areas: List of area tuples from identical_cell_aggregation
            compress_dict: Value dictionary from inverted_index
            compression_metadata: Metadata from get_compression_metadata

        Returns:
            Dictionary with complete compression data
        """

        # Convert areas list to format_regions structure
        format_regions = []
        for idx, area in enumerate(areas):
            format_regions.append({
                'region_id': idx + 1,
                'range': self._bounds_to_range(area[0], area[1]),
                'format_type': area[2],
                'bounds': {
                    'top_left': {'row': area[0][0], 'col': area[0][1]},
                    'bottom_right': {'row': area[1][0], 'col': area[1][1]}
                }
            })

        # Build complete structure
        unified_output = {
            'metadata': {
                'source_file': filename,
                'file_format': file_format,
                'original_dimensions': {
                    'rows': original_dims[0],
                    'cols': original_dims[1]
                },
                'compressed_dimensions': {
                    'rows': compressed_dims[0],
                    'cols': compressed_dims[1]
                },
                'compression_ratio': compression_metadata.get('compression_ratio', 0),
                'k_parameter': compression_metadata.get('k_parameter', 4),
                'compression_timestamp': datetime.now().isoformat(),
                'format_version': self.format_version
            },
            'compression_data': {
                'value_dictionary': compress_dict,
                'format_regions': format_regions,
                'anchor_points': {
                    'rows': compression_metadata.get('anchor_rows', []),
                    'columns': compression_metadata.get('anchor_columns', [])
                }
            },
            'extraction_instructions': self._get_extraction_instructions(),
            'tables': []
        }

        return unified_output

    def _bounds_to_range(self, top_left: Tuple[int, int], bottom_right: Tuple[int, int]) -> str:
        """Convert numeric bounds to Excel range (e.g., A1:F10).

        Args:
            top_left: (row, col) tuple
            bottom_right: (row, col) tuple

        Returns:
            Excel-style range string
        """
        tl_addr = self.converter.parse_colindex(top_left[1] + 1) + str(top_left[0] + 1)
        br_addr = self.converter.parse_colindex(bottom_right[1] + 1) + str(bottom_right[0] + 1)

        if tl_addr == br_addr:
            return tl_addr
        return f"{tl_addr}:{br_addr}"

    def _get_extraction_instructions(self) -> Dict:
        """Embed minimal extraction guidance in output.

        Returns:
            Dict with extraction task information
        """
        return {
            'task': 'extract_all_tables',
            'output_format': 'json_array',
            'note': 'See prompt_template.md for detailed extraction instructions'
        }

    def write_to_file(self, output_dict: Dict, output_path: str):
        """Write JSON with pretty formatting.

        Args:
            output_dict: Dictionary to write
            output_path: Path to output file
        """
        # Convert numpy types to native Python types for JSON serialization
        output_dict = self._convert_numpy_types(output_dict)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_dict, f, indent=2, ensure_ascii=False)

    def _convert_numpy_types(self, obj):
        """Recursively convert numpy types to native Python types.

        Args:
            obj: Object to convert

        Returns:
            Converted object
        """
        import numpy as np

        if isinstance(obj, dict):
            return {self._convert_key(k): self._convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj

    def _convert_key(self, key):
        """Convert dict keys to strings if they're numpy types.

        Args:
            key: Dictionary key

        Returns:
            Converted key (string if was numpy type)
        """
        import numpy as np

        if isinstance(key, (np.integer, np.floating)):
            return str(key)
        return key

    def write_legacy_format(self, areas: List, compress_dict: Dict, areas_path: str, dict_path: str):
        """Maintain backward compatibility with original _areas.txt and _dict.txt format.

        Args:
            areas: List of area tuples
            compress_dict: Value dictionary
            areas_path: Path for areas output
            dict_path: Path for dict output
        """
        # Write areas
        with open(areas_path, 'w', encoding='utf-8') as f:
            for area in areas:
                range_str = self._bounds_to_range(area[0], area[1])
                f.write(f"{range_str}\t{area[2]}\n")

        # Write dictionary
        with open(dict_path, 'w', encoding='utf-8') as f:
            f.write(str(compress_dict))
