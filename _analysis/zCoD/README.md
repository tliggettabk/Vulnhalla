# Call of Duty External Security Issues Analysis

## Overview
This folder contains the analysis results for external security issues converted from Reportable.csv format and integrated into the Vulnhalla framework for comprehensive security assessment.

## Files in this Directory

### Data Files
- **external_issues.csv** - 250 security issues converted from external Reportable.csv to Vulnhalla format
- **cid_mapping.csv** - Traceability mapping between original CID identifiers and converted data

### Subset Files
- **matched_issues.csv** - 113 issues (45.2%) successfully mapped to functions (includes function name and length)
- **no_line_number_issues.csv** - 70 issues (28.0%) with "Various" line numbers that couldn't be mapped
- **unmatched_issues.csv** - 67 issues (26.8%) with specific line numbers but no matching functions found

### Source Data
- **Original source:** `C:\Users\tliggett\Downloads\Reportable.csv` (294 total issues)
- **Date filter applied:** Issues detected after 10/1/2025 were excluded (44 issues filtered out)
- **Conversion rate:** 85.0% success rate (250/294 issues)

## Analysis Results Summary

### Issue Mapping to Functions
- **Total external issues processed:** 250
- **Successfully mapped to functions:** 113 issues (45.2%)
- **Unable to map:** 137 issues (54.8%)

### Function Impact Assessment
- **Vulnerable functions identified:** 103 unique functions
- **Total functions in Call of Duty codebase:** 299,832
- **Vulnerability rate:** 0.034%

### Vulnerable Function Characteristics
- **Average function length:** 68.2 lines
- **Median function length:** 36.0 lines
- **Function length range:** 1 - 631 lines

### Top Issue Types
1. **Out-of-bounds access:** 111 issues (44.4%)
2. **Out-of-bounds read:** 69 issues (27.6%)
3. **Out-of-bounds write:** 41 issues (16.4%)
4. **Buffer not null terminated:** 6 issues (2.4%)
5. **Illegal address computation:** 6 issues (2.4%)
6. **Copy into fixed size buffer:** 5 issues (2.0%)

### Most Vulnerable Files
- db_zones.cpp: 6 issues
- bg_vehicle_physics_manager.inl: 6 issues  
- online_archive_replay_playback.cpp: 5 issues
- dwEnvironment.cpp: 4 issues
- db_binarypatch_load.cpp: 4 issues

### Functions with Multiple Issues
- **Functions with 2+ issues:** 9 functions
- **Most vulnerable function:** `operator()` with 3 issues

### Mapping Issues
**Why some issues couldn't be mapped:**
- **"Various line number":** 70 issues (external data used generic "Various" instead of specific line numbers)
- **"No matching function":** 67 issues (file/line combinations not found in function database)

## How to Run the Analysis Tools

### Prerequisites
- Python virtual environment activated: `.venv\Scripts\Activate.ps1`
- Call of Duty CodeQL database available at: `C:\code\codeQL_CoD\codeql`
- FunctionTree.csv generated from CodeQL analysis

### Tool Locations
All analysis tools are located in the `tools` folder:

### 1. Convert External Data
**Tool:** `tools\convert_reportable.py`

**Purpose:** Convert external Reportable.csv to Vulnhalla-compatible format

**Usage:**
```powershell
python tools\convert_reportable.py
```

**What it does:**
- Reads `C:\Users\tliggett\Downloads\Reportable.csv`
- Applies date filtering (excludes issues after 10/1/2025)
- Converts to Vulnhalla format with proper column mapping
- Outputs `tools\issues.csv` and `tools\cid_mapping.csv`

### 2. Map Issues to Functions  
**Tool:** `tools\external_issue_mapper.py`

**Purpose:** Map converted external issues to specific functions in the codebase

**Usage:**
```powershell
python tools\external_issue_mapper.py
```

**What it does:**
- Reads `tools\issues.csv` (converted external issues)
- Reads `C:\code\codeQL_CoD\codeql\FunctionTree.csv` (function definitions)
- Maps issues to containing functions based on file:line locations
- Provides comprehensive analysis statistics

**Dependencies:**
- Requires FunctionTree.csv to be generated first from CodeQL analysis
- See `readme-tsl.md` for instructions on generating FunctionTree.csv

### 3. Create Issue Subsets
**Tool:** `tools\create_issue_subsets.py`

**Purpose:** Split external issues into matched, no line number, and unmatched categories

**Usage:**
```powershell
python tools\create_issue_subsets.py
```

**What it does:**
- Reads `zCoD\external_issues.csv` (converted external issues)  
- Reads `C:\code\codeQL_CoD\codeql\FunctionTree.csv` (function definitions)
- Creates three subset files based on mapping results:
  - `zCoD\matched_issues.csv` - Issues mapped to functions (with additional function info)
  - `zCoD\no_line_number_issues.csv` - Issues with "Various" line numbers
  - `zCoD\unmatched_issues.csv` - Issues that couldn't be mapped to functions

### 4. Generate Function Data
**Prerequisite step - run CodeQL analysis:**
```powershell
# Generate FunctionTree.csv using optimized query
& "C:\tmp\CQL\codeql-win64\codeql\codeql.cmd" query run "data\queries\cpp\tools\FunctionTreeFixed.ql" --database="C:\code\codeQL_CoD\codeql" --output="C:\code\codeQL_CoD\codeql\FunctionTreeFixed.bqrs" --threads=2 --timeout=1800

# Convert to CSV format
& "C:\tmp\CQL\codeql-win64\codeql\codeql.cmd" bqrs decode "C:\code\codeQL_CoD\codeql\FunctionTreeFixed.bqrs" --format=csv --output="C:\code\codeQL_CoD\codeql\FunctionTree.csv"
```

## Integration with Vulnhalla Pipeline

The converted external issues can now be used with the rest of the Vulnhalla security analysis pipeline:

1. **LLM Analysis:** External issues can be processed through Vulnhalla's LLM analysis for severity assessment
2. **Comparative Analysis:** Compare external findings with CodeQL-discovered issues  
3. **Function-level Assessment:** Analyze vulnerable functions using existing tools
4. **Security Report Generation:** Include external issues in comprehensive security reports

## Technical Notes

### Column Mapping (External to Vulnhalla)
```
External Field -> Vulnhalla Field
source -> file
source_line -> start_line  
sink -> description
Type -> message
CID + ABK_Classification -> help
```

### Data Quality Notes
- External data used "Various" for many line numbers, limiting precise function mapping
- Some file paths in external data may not exactly match CodeQL database paths
- 45.2% mapping rate is reasonable given data quality constraints

### Performance Characteristics
- External issue processing: Fast (250 issues)
- Function mapping: ~30 seconds for full analysis
- Memory usage: Moderate (loads 299K+ functions into memory)

## Future Enhancements

1. **Improved Path Matching:** Enhance file path normalization for better mapping rates
2. **Line Number Inference:** For "Various" entries, attempt to infer likely line numbers
3. **Cross-Reference Analysis:** Compare external issues with CodeQL findings for validation
4. **Automated Reporting:** Generate comparative reports between external and internal findings

## Command Summary

**Complete workflow to recreate analysis:**
```powershell
# 1. Activate environment
& .venv\Scripts\Activate.ps1

# 2. Convert external data (if needed)
python tools\convert_reportable.py

# 3. Map to functions 
python tools\external_issue_mapper.py
```

**Output:** Comprehensive analysis showing which Call of Duty functions contain externally identified security vulnerabilities.