import datetime
import numpy as np
import pandas as pd
import re
from pandas.tseries.api import guess_datetime_format

from .IndexColumnConverter import IndexColumnConverter

CATEGORIES = ['Integer', 'Float', 'Percentage', 'Scientific Notation', 'Date',
              'Time', 'Currency', 'Email', 'Other']


class SheetCompressor:
    def __init__(self, k=4):
        """Initialize SheetCompressor with configurable K parameter.

        Args:
            k: Anchor expansion distance (default: 4)
        """
        self.k = k
        self.row_candidates = []
        self.column_candidates = []
        self.row_lengths = {}
        self.column_lengths = {}

    def get_format(self, value):
        """Return data-format related information (e.g., Numeric, String).

        Args:
            value: cell value

        Returns:
            List with a single string describing the data format
        """
        category = self.get_category(value)
        return [category]

    def encode(self, sheet):
        """Encode spreadsheet into markdown format.

        Args:
            sheet: pandas DataFrame

        Returns:
            DataFrame with Address, Value, Format columns
        """
        converter = IndexColumnConverter()
        markdown = pd.DataFrame(columns=['Address', 'Value', 'Format'])
        for rowindex, i in sheet.iterrows():
            for colindex, j in enumerate(sheet.columns.tolist()):
                val = i[j]
                new_row = pd.DataFrame([converter.parse_colindex(colindex + 1) + str(rowindex + 1), val,
                                        self.get_format(val)]).T
                new_row.columns = markdown.columns
                markdown = pd.concat([markdown, new_row])
        return markdown

    #Checks for identical dtypes across row/column
    def get_dtype_row(self, sheet):
        current_type = []
        for i, j in sheet.iterrows():
            if current_type != (temp := j.apply(type).to_list()):
                current_type = temp
                self.row_candidates.append(i)

    def get_dtype_column(self, sheet):
        current_type = []
        for i, j in enumerate(sheet.columns):
            if current_type != (temp := sheet[j].apply(type).to_list()):
                current_type = temp
                self.column_candidates.append(i)

    #Checks for length of text across row/column, looks for outliers, marks as candidates
    def get_length_row(self, sheet):
        def _safe_len(x):
            try:
                na = pd.isna(x)
            except Exception:
                na = False

            if isinstance(na, (bool, np.bool_)) and na:
                return 0
            # If na is array-like (Series/ndarray), treat as non-scalar: try to get length
            if not isinstance(na, (bool, np.bool_)) and hasattr(x, '__len__'):
                try:
                    return len(x)
                except Exception:
                    return 0

            if isinstance(x, (float, int, datetime.datetime, np.number)):
                return 0
            if isinstance(x, str):
                return len(x)
            try:
                return len(x)
            except Exception:
                return 0

        for i, j in sheet.iterrows():
            self.row_lengths[i] = sum(j.apply(lambda x: _safe_len(x)))
        mean = np.mean(list(self.row_lengths.values()))
        std = np.std(list(self.row_lengths.values()))
        min = np.max([mean - 2 * std, 0])
        max = mean + 2 * std
        self.row_lengths = dict((k, v) for k, v in self.row_lengths.items() if v < min or v > max)

    def get_length_column(self, sheet):
        def _safe_len(x):
            try:
                na = pd.isna(x)
            except Exception:
                na = False

            if isinstance(na, (bool, np.bool_)) and na:
                return 0
            if not isinstance(na, (bool, np.bool_)) and hasattr(x, '__len__'):
                try:
                    return len(x)
                except Exception:
                    return 0

            if isinstance(x, (float, int, datetime.datetime, np.number)):
                return 0
            if isinstance(x, str):
                return len(x)
            try:
                return len(x)
            except Exception:
                return 0

        for i, j in enumerate(sheet.columns):
            self.column_lengths[i] = sum(sheet[j].apply(lambda x: _safe_len(x)))
        mean = np.mean(list(self.column_lengths.values()))
        std = np.std(list(self.column_lengths.values()))
        min = np.max([mean - 2 * std, 0])
        max = mean + 2 * std
        self.column_lengths = dict((k, v) for k, v in self.column_lengths.items() if v < min or v > max)

    def anchor(self, sheet):
        """Apply anchoring algorithm with K parameter.

        Args:
            sheet: pandas DataFrame

        Returns:
            Compressed DataFrame with anchor points
        """

        #Given num, obtain all integers from num - k to num + k inclusive
        def surrounding_k(num, k):
            return list(range(num - k, num + k + 1))

        self.get_dtype_row(sheet)
        self.get_dtype_column(sheet)
        self.get_length_row(sheet)
        self.get_length_column(sheet)

        #Keep candidates found in both dtype/length method
        self.row_candidates = np.intersect1d(list(self.row_lengths.keys()), self.row_candidates)
        self.column_candidates = np.intersect1d(list(self.column_lengths.keys()), self.column_candidates)

        #Beginning/End are candidates
        self.row_candidates = np.append(self.row_candidates, [0, len(sheet) - 1]).astype('int32')
        self.column_candidates = np.append(self.column_candidates, [0, len(sheet.columns) - 1]).astype('int32')

        #Get K closest rows/columns to each candidate (use self.k instead of global K)
        self.row_candidates = np.unique(list(np.concatenate([surrounding_k(i, self.k) for i in self.row_candidates]).flat))
        self.column_candidates = np.unique(list(np.concatenate([surrounding_k(i, self.k) for i in self.column_candidates]).flat))

        #Truncate negative/out of bounds
        self.row_candidates = self.row_candidates[(self.row_candidates >= 0) & (self.row_candidates < len(sheet))]
        self.column_candidates = self.column_candidates[(self.column_candidates >= 0) & (self.column_candidates < len(sheet.columns))]

        sheet = sheet.iloc[self.row_candidates, self.column_candidates]

        #Remap coordinates
        sheet = sheet.reset_index().drop(columns='index')
        sheet.columns = list(range(len(sheet.columns)))

        return sheet

    #Converts markdown to value-key pair
    def inverted_index(self, markdown):

        #Takes array of Excel cells and combines adjacent cells
        def combine_cells(array):

            if len(array) == 1:
                return array[0]
            return array[0] + ':' + array[-1]

        #Convert unhashable types to string representation
        def make_hashable(value):
            if pd.isna(value):
                return value
            # Handle unhashable types (ArrayFormula, etc.) by converting to string
            try:
                hash(value)
                return value
            except TypeError:
                return str(value)

        dictionary = {}
        for _, i in markdown.iterrows():
            key = make_hashable(i['Value'])
            if key in dictionary:
                dictionary[key].append(i['Address'])
            else:
                dictionary[key] = [i['Address']]
        dictionary = {k: v for k, v in dictionary.items() if not pd.isna(k)}
        dictionary = {k: combine_cells(v) for k, v in dictionary.items()}
        return dictionary

    #Key-Value to Value-Key for categories
    def inverted_category(self, markdown):
        #Convert unhashable types to string representation
        def make_hashable(value):
            if pd.isna(value):
                return value
            # Handle unhashable types (ArrayFormula, etc.) by converting to string
            try:
                hash(value)
                return value
            except TypeError:
                return str(value)

        dictionary = {}
        for _, i in markdown.iterrows():
                key = make_hashable(i['Value'])
                dictionary[key] = i['Category']
        return dictionary

    #Regex to NFS
    def get_category(self, string):
        if pd.isna(string):
            return 'Other'
        if isinstance(string, float):
            return 'Float'
        if isinstance(string, int):
            return 'Integer'
        if isinstance(string, datetime.datetime):
            return 'yyyy/mm/dd'
        if re.match(r'^-?\d+$', str(string)):
            return 'Integer'
        if re.match(r'^-?\d+\.\d+$', str(string)):
            return 'Float'
        if re.match(r'^[-+]?\d*\.?\d*%$', str(string)) or re.match(r'^\d{1,3}(,\d{3})*(\.\d+)?%$', str(string)):
            return 'Percentage'
        if re.match(r'^[-+]?[$]\d*\.?\d{2}$', str(string)) or re.match(r'^[-+]?[$]\d{1,3}(,\d{3})*(\.\d{2})?$', str(string)):
            return 'Currency'
        if re.match(r'\b-?[1-9](?:\.\d+)?[Ee][-+]?\d+\b', str(string)):
            return 'Scientific Notation'
        if re.match(r"^((([!#$%&'*+\-/=?^_`{|}~\w])|([!#$%&'*+\-/=?^_`{|}~\w][!#$%&'*+\-/=?^_`{|}~\.\w]{0,}[!#$%&'*+\-/=?^_`{|}~\w]))[@]\w+([-.]\w+)*\.\w+([-.]\w+)*)$", str(string)):
            return 'Email'
        if datetime_format := guess_datetime_format(str(string)):
            return datetime_format
        return 'Other'

    def identical_cell_aggregation(self, sheet, dictionary):
        """Aggregate identical cells into regions using DFS.

        Args:
            sheet: pandas DataFrame
            dictionary: Category dictionary

        Returns:
            List of areas with bounds and category
        """

        #Handles nan edge cases
        def replace_nan(sheet_value):
            if pd.isna(sheet_value):
                return 'Other'
            else:
                return dictionary[sheet_value]

        #DFS for checking bounds (iterative implementation to avoid recursion limit)
        def dfs(r, c, val_type):
            stack = [(r, c)]
            bounds = [r, c, r, c]  # [min_row, min_col, max_row, max_col]

            while stack:
                curr_r, curr_c = stack.pop()

                # Skip if already visited
                if visited[curr_r][curr_c]:
                    continue

                # Skip if type doesn't match
                match = replace_nan(sheet.iloc[curr_r, curr_c])
                if val_type != match:
                    continue

                # Mark as visited
                visited[curr_r][curr_c] = True

                # Update bounds
                bounds[0] = min(bounds[0], curr_r)
                bounds[1] = min(bounds[1], curr_c)
                bounds[2] = max(bounds[2], curr_r)
                bounds[3] = max(bounds[3], curr_c)

                # Add valid neighbors to stack
                for next_r, next_c in [[curr_r - 1, curr_c], [curr_r, curr_c - 1],
                                       [curr_r + 1, curr_c], [curr_r, curr_c + 1]]:
                    if (0 <= next_r < len(sheet) and
                        0 <= next_c < len(sheet.columns) and
                        not visited[next_r][next_c]):
                        neighbor_match = replace_nan(sheet.iloc[next_r, next_c])
                        if val_type == neighbor_match:
                            stack.append((next_r, next_c))

            return bounds

        m = len(sheet)
        n = len(sheet.columns)

        visited = [[False] * n for _ in range(m)]
        areas = []

        for r in range(m):
            for c in range(n):
                if not visited[r][c]:
                    val_type = replace_nan(sheet.iloc[r, c])
                    bounds = dfs(r, c, val_type)
                    areas.append([(bounds[0], bounds[1]), (bounds[2], bounds[3]), val_type])
        return areas

    def get_compression_metadata(self, original_size, compressed_size):
        """Return metadata about the compression process.

        Args:
            original_size: Original number of cells
            compressed_size: Compressed number of cells

        Returns:
            Dict with compression metadata
        """
        return {
            'k_parameter': self.k,
            'compression_ratio': original_size / compressed_size if compressed_size > 0 else 0,
            'anchor_rows': self.row_candidates.tolist() if hasattr(self.row_candidates, 'tolist') else list(self.row_candidates),
            'anchor_columns': self.column_candidates.tolist() if hasattr(self.column_candidates, 'tolist') else list(self.column_candidates)
        }
