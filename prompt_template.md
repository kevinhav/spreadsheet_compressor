# SpreadsheetLLM Table Extraction Instructions

## Your Task

Extract all data tables from the compressed spreadsheet representation and return them as a JSON array.

## Input Format Explanation

The compressed spreadsheet format contains three key components:

### 1. Value Dictionary

Maps cell values to their Excel addresses using a compact notation:

- `"Revenue": "A1"` → Cell A1 contains the text "Revenue"
- `"IntNum": "B2:B10"` → Cells B2 through B10 contain integer-type data
- `"12500.50": "C2,C5:C7"` → The value 12500.50 appears in multiple cells/ranges

**Key points:**
- Single addresses like "A1" indicate one cell
- Ranges like "A1:B10" indicate rectangular regions
- Comma-separated addresses like "C2,C5:C7" indicate multiple locations
- The value "IntNum", "FloatNum", etc. indicates compressed numeric data of that type

### 2. Format Regions

Describes rectangular areas with homogeneous data types:

```json
{
  "region_id": 1,
  "range": "A1:F10",
  "format_type": "Integer",
  "bounds": {
    "top_left": {"row": 0, "col": 0},
    "bottom_right": {"row": 9, "col": 5}
  }
}
```

**Format types:**
- `Integer` - Whole numbers
- `Float` - Decimal numbers
- `Percentage` - Percentage values
- `Currency` - Money amounts
- `Date` - Date values
- `Time` - Time values
- `Scientific Notation` - Numbers in scientific notation
- `Email` - Email addresses
- `Other` - Text or mixed content

### 3. Anchor Points

Key rows and columns preserved during compression (K=4 expansion around data boundaries):

```json
{
  "anchor_points": {
    "rows": [0, 4, 5, 9, 14, 99],
    "columns": [0, 3, 4, 7, 11]
  }
}
```

These indicate where important transitions occur in the data.

## Detection Strategy

Follow these steps to identify and extract tables:

### Step 1: Identify Header Regions
- Look for `format_regions` with type "Other" near the top (row 0-2)
- Headers often contain text while data contains numbers
- Headers may have borders or bold formatting

### Step 2: Find Data Blocks
- Look for contiguous `format_regions` with numeric types (Integer, Float, Currency, etc.)
- Data blocks typically follow header rows
- Multiple consecutive regions of the same type indicate a data column

### Step 3: Determine Table Boundaries
- Use `anchor_points` to identify where tables start and end
- Tables typically span from a header row to the last data row
- Look for transitions in `format_type` to identify column boundaries

### Step 4: Reconstruct Values
- Use the `value_dictionary` to populate cell values
- For compressed values like "IntNum", note that actual values were removed but the type is preserved
- Combine address ranges to understand table structure

### Step 5: Extract Table Data
- Identify column headers from the first row of each table
- Extract data rows following the headers
- Preserve data types as indicated by `format_type`

## Output Schema

Return a JSON object with a `tables` array containing table objects:

```json
{
  "tables": [
    {
      "table_id": 1,
      "range": "A1:F10",
      "description": "Brief description of what this table contains",
      "headers": ["Year", "Q1", "Q2", "Q3", "Q4", "Total"],
      "data": [
        {"Year": 2020, "Q1": 12500.50, "Q2": 13200.00, "Q3": 14100.00, "Q4": 15300.00, "Total": 55100.50},
        {"Year": 2021, "Q1": 14100.00, "Q2": 15300.00, "Q3": 16200.00, "Q4": 17500.00, "Total": 63100.00}
      ],
      "metadata": {
        "num_rows": 2,
        "num_cols": 6,
        "data_types": {
          "Year": "Integer",
          "Q1": "Currency",
          "Q2": "Currency",
          "Q3": "Currency",
          "Q4": "Currency",
          "Total": "Currency"
        }
      }
    }
  ]
}
```

### Required Fields:
- `table_id` - Unique integer identifier (1, 2, 3...)
- `range` - Excel range of the table (e.g., "A1:F10")
- `description` - Brief text describing the table's content
- `headers` - Array of column header names
- `data` - Array of row objects, where each object maps header → value
- `metadata.num_rows` - Number of data rows (excluding header)
- `metadata.num_cols` - Number of columns
- `metadata.data_types` - Map of header → format_type

## Examples

### Example 1: Simple Single Table

**Input (compressed):**
```json
{
  "compression_data": {
    "value_dictionary": {
      "Year": "A1",
      "Revenue": "B1",
      "2020": "A2",
      "2021": "A3",
      "FloatNum": "B2:B3"
    },
    "format_regions": [
      {"region_id": 1, "range": "A1:B1", "format_type": "Other"},
      {"region_id": 2, "range": "A2:A3", "format_type": "Integer"},
      {"region_id": 3, "range": "B2:B3", "format_type": "Float"}
    ]
  }
}
```

**Output:**
```json
{
  "tables": [
    {
      "table_id": 1,
      "range": "A1:B3",
      "description": "Yearly revenue data",
      "headers": ["Year", "Revenue"],
      "data": [
        {"Year": 2020, "Revenue": "[numeric]"},
        {"Year": 2021, "Revenue": "[numeric]"}
      ],
      "metadata": {
        "num_rows": 2,
        "num_cols": 2,
        "data_types": {
          "Year": "Integer",
          "Revenue": "Float"
        }
      }
    }
  ]
}
```

### Example 2: Multiple Tables

When multiple distinct tables are found, return multiple objects in the `tables` array:

```json
{
  "tables": [
    {
      "table_id": 1,
      "range": "A1:C5",
      "description": "First table - sales data"
      // ... rest of fields
    },
    {
      "table_id": 2,
      "range": "A10:D15",
      "description": "Second table - expense data"
      // ... rest of fields
    }
  ]
}
```

## Edge Cases

### 1. Multiple Tables in One Sheet
- Look for gaps in `anchor_points.rows` indicating separation
- Each distinct table should be a separate object in the `tables` array

### 2. Merged or Sparse Cells
- Use range notation in data if cells are merged
- Include null for empty cells within table boundaries

### 3. Compressed Numeric Values
- When you see "IntNum", "FloatNum", etc. in the value_dictionary, the actual values have been compressed
- Note the data type but indicate values are "[numeric]" in extracted data
- The type information is preserved in `format_regions`

### 4. Ambiguous Table Boundaries
- When uncertain, prefer larger table boundaries over splitting
- Use description field to note any ambiguity

### 5. No Clear Tables
- If no structured tables are detected, return an empty array: `{"tables": []}`

### 6. Headers Spanning Multiple Rows
- Combine multi-row headers into single header names
- Example: Row 1 has "Sales", Row 2 has "Q1" → Header: "Sales Q1"

## Quality Checks

Before returning your JSON output, verify:

1. **Header-Data Alignment**: Each data row has values for all headers
2. **Type Consistency**: Data types match the `format_type` from format_regions
3. **Row/Column Counts**: `num_rows` and `num_cols` match actual data
4. **Valid JSON**: Output is properly formatted JSON
5. **Complete Tables**: All identifiable tables are extracted
6. **No Duplicates**: Each cell appears in only one table

## Common Patterns

### Pattern 1: Header Row + Data Rows
Most common: First row contains text headers, subsequent rows contain data.

### Pattern 2: Summary Rows
Look for Total/Sum rows at the bottom of data regions (often in bold or with borders).

### Pattern 3: Multi-Level Headers
Headers may span multiple rows for sub-categories. Flatten into single header names.

### Pattern 4: Lookup Tables
Small tables mapping keys to values (e.g., product codes → names).

## Tips for LLM Processing

- Start by visualizing the table structure from the value_dictionary
- Use format_regions to understand data types and table layout
- Anchor points help identify important row/column transitions
- When in doubt, describe what you observe in the description field
- It's better to extract tables conservatively than to force incorrect structure

## Final Notes

- This compression format reduces spreadsheet size by ~25x while preserving structure
- Some specific cell values may be replaced with type markers (IntNum, FloatNum)
- The goal is to extract the table **structure** and **schema**, with values where available
- Focus on identifying table boundaries, headers, and data types accurately
