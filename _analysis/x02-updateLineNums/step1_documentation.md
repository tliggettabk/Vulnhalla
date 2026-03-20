# Step 1: Function Mapping and Code Verification Process Documentation

## Overview
This step processes the findings data from the Excel file, maps each finding to its containing function using CodeQL's FunctionTree analysis, and performs code verification for exact matches.

## Input Files
- **Source:** `../x01-cov-setup/Findings_WithCodeLine_WithTriageComment.xlsx`
- **Function Data:** `C:/code/codeQL_CoD/codeql/FunctionTree.csv` (CodeQL generated function boundaries)
- **Source Code:** `C:/code/codeQL_CoD/codeql/src.zip` (CodeQL source archive for verification)

## Process Description

### 1. Data Loading
- Read findings from Excel file with columns: File, Line Number, Function (existing), code_at_cited_line
- Load CodeQL function tree with function boundaries (name, file, start_line, end_line)

### 2. Function Location Mapping
For each finding:
1. Use **File** and **Line Number** to find the containing function from FunctionTree.csv
2. Add columns for found function:
   - `found_function_name` 
   - `found_function_start`
   - `found_function_end` 
   - `found_function_length`

### 3. Function Name Comparison
1. Compare found function name with existing **Function** column
2. Add `functions_match` boolean column indicating if they match
3. If they don't match, lookup the existing Function name in FunctionTree.csv and add:
   - `existing_function_start`
   - `existing_function_end`
   - `existing_function_length`

### 4. Code Verification (NEW - for matching functions only)
For findings where found_function_name matches existing Function:
1. Extract the actual file content from `src.zip`
2. Extract the function code using start/end line boundaries
3. Verify the content at the cited Line Number
4. If `code_at_cited_line` is provided, check if it matches the actual line content
5. If no match, search within the function to see if the code moved to a different line

### 5. Results Analysis
Track statistics on:
- Location mapping success rate
- Function name match/mismatch rates  
- Code verification success rates
- Line number accuracy
- Missing or invalid data

## Script Usage

### Test Mode (Recommended First)
```bash
python step1_function_mapping.py --test
```
- Processes only first 10 findings
- Shows detailed results including code verification
- Does not write output file

### Full Processing
```bash
python step1_function_mapping.py
```
- Processes all findings
- Writes enhanced Excel file with new columns

### Options
- `--excel` - Specify different Excel input file
- `--functions` - Specify different FunctionTree.csv path
- `--srczip` - Specify different src.zip path

## Expected Output Columns

Original columns plus:

**Function Mapping:**
- `found_function_name` - Function containing the File:Line location
- `found_function_start` - Start line of found function
- `found_function_end` - End line of found function  
- `found_function_length` - Length in lines of found function
- `functions_match` - Boolean: found function == existing Function column
- `existing_function_start` - Start line of existing Function name (if found)
- `existing_function_end` - End line of existing Function name (if found)
- `existing_function_length` - Length of existing Function name (if found)
- `status` - Text description of mapping result

**Code Verification (NEW):**
- `line_number_matches` - Boolean: content at line number matches expectation
- `line_number_actual_content` - Actual code content at the cited line number
- `line_number_found_at` - Line number where expected content was found (if moved)
- `cited_line_matches` - Boolean: cited line code matches actual file content
- `cited_line_actual_content` - Actual content at cited line location
- `cited_line_found_at` - Line where cited code was actually found (if moved)
- `function_code_extracted` - Boolean: successfully extracted function from src.zip
- `verification_performed` - Boolean: code verification was attempted

## Key Metrics to Track

### Success Rates
- **Location Mapping Success:** % of findings successfully mapped to containing function
- **Function Name Match Rate:** % where found function matches existing Function column
- **Code Verification Success:** % where function code was successfully extracted from src.zip
- **Line Number Accuracy:** % where cited line numbers contain expected content
- **Code Movement Detection:** % where cited code was found at different line numbers
- **Data Quality:** % with valid file paths and line numbers

### Expected Results
- **High location mapping success (>95%):** Most findings should map to functions
- **Variable name match rates:** May vary depending on data source accuracy
- **High code extraction success (>90%):** Most files should be available in src.zip
- **Moderate line accuracy (60-80%):** Some line drift expected over time
- **Mismatches reveal:** Data quality issues or different function identification methods

## Quality Checks

### Data Validation
- File paths must be non-empty and valid
- Line numbers must be positive integers
- Function boundaries must be logical (start ≤ end)
- src.zip must contain referenced source files

### Code Verification Quality
- **Function Extraction:** Verify function boundaries are reasonable (not too large/small)
- **Line Content Validation:** Actual line content matches expectations
- **Code Movement Detection:** Track when legitimate code has moved within functions
- **File Availability:** Monitor src.zip coverage of referenced files

### Path Normalization
- Handles different path formats (`/cod_trunk/code/`, `D:/mapped_drives/cod/trunk/code/`)  
- Normalizes separators (`\` to `/`)
- Removes quotes and extra characters

### Function Matching
- Exact path matching preferred
- Falls back to partial matching for path variations
- Binary search within files for efficiency
- Fuzzy matching for code content (75%+ similarity)

## Common Issues to Monitor

### Low Location Mapping Success
**Causes:** 
- Path format mismatches between Excel and CodeQL
- Line numbers outside function boundaries
- Missing files in CodeQL analysis

**Solutions:**
- Review path normalization logic
- Check for global scope code (outside functions)
- Verify CodeQL covered all source files

### High Function Name Mismatch Rate  
**Causes:**
- Different function identification methods
- Overloaded functions with same base name
- Namespace/class prefixes in Function column

**Solutions:**
- Analyze mismatch patterns
- Consider fuzzy matching strategies
- Review existing Function column data source

### Missing Function Definitions
**Causes:**
- Function names not in CodeQL analysis
- Typos or formatting differences
- Generated/template functions

**Solutions:**
- Case-insensitive matching
- Partial name matching
- Cross-reference with Classes.csv for methods

## Next Steps

After successful Step 1 completion:
1. Review test results and statistics
2. Adjust for any systematic issues found
3. Run full processing 
4. Analyze results for data quality insights
5. Prepare for Step 2: Line number updates/corrections

## File Outputs

### Test Mode
- Console output with detailed analysis
- No files written

### Full Mode  
- Enhanced Excel file with new function mapping columns
- Processing log with statistics
- Error report for failed mappings

---

*This documentation tracks the function mapping process as part of the findings data enhancement pipeline.*