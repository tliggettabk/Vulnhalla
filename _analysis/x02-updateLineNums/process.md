# Line Number Update Process

This folder contains the tools and process for updating and validating line numbers in vulnerability findings using CodeQL function mapping.

## Overview

The process consists of multiple steps to progressively enhance and validate vulnerability findings data:

1. **Function Mapping & Code Verification** - Map findings to containing functions and verify code accuracy
2. **Triage by Status** - Split findings into actionable categories for targeted processing
3. **Line Number Updates** - Update line numbers for findings where code has moved
4. **Final Validation** - Re-verify updated findings

## Process Steps

### Step 1: Function Mapping & Code Verification

**Script:** `step1_function_mapping.py`

**Purpose:** Enhance findings with function mapping data and code verification

**Process:**
- Maps each finding to its containing function using FunctionTree.csv
- Verifies code accuracy by comparing expected vs actual source code
- Adds 30+ analysis columns including function details, code verification, and status classification

**Input:** 
- `../x01-cov-setup/Findings_WithCodeLine_WithTriageComment.xlsx` (883 findings)
- `C:/code/codeQL_CoD/codeql/FunctionTree.csv` (299,839 functions)
- `C:/code/codeQL_CoD/codeql/src.zip` (source code archive)

**Output:**
- `../x01-cov-setup/Findings_WithCodeLine_WithTriageComment_Enhanced.xlsx`
- Enhanced file with 146 total columns (original + 32 analysis columns)

**Key Analysis Columns:**
- `analysis_status`: 'perfect', 'found', or 'problem'
- `found_function_name`: Containing function identified by location
- `code_at_cited_line`: Expected code at the cited line
- `cited_line_matches`: Whether expected code matches actual
- `cited_line_found_at`: Line where expected code was actually found

**Usage:**
```bash
# Test mode (first 10 findings)
python step1_function_mapping.py --test

# Full processing with quiet output
python step1_function_mapping.py --quiet

# Custom paths
python step1_function_mapping.py --excel custom_input.xlsx --output custom_output.xlsx
```

**Results Summary:**
- **55.7% location mapping success** (492/883 findings mapped to functions)  
- **73.4% FunctionTree availability** (648/883 files have function data)
- **19.9% perfect matches** (176 findings with exact code location)
- **28.4% correctable matches** (251 findings with code moved but findable)
- **51.6% problematic cases** (456 findings needing manual review)

**Success Rate for Files with Function Data:**
- **75.9% function mapping success** (492/648)
- **65.9% perfect + correctable** (427/648) 

### Step 2: Triage by Analysis Status

**Script:** `step2_split_findings.py`

**Purpose:** Split enhanced findings into three actionable categories for targeted processing

**Process:**
- Reads enhanced Excel file from Step 1
- Filters by `analysis_status` column
- Creates separate files for different handling workflows
- Sorts findings by file path and line number for easier review

**Input:**
- `../x01-cov-setup/Findings_WithCodeLine_WithTriageComment_Enhanced.xlsx`

**Output Files:**
1. **Perfect Matches** (`*_Perfect.xlsx`): 176 findings (19.9%)
   - Code exactly where expected
   - Ready for immediate processing
   - High confidence in line number accuracy

2. **Correctable** (`*_Correctable.xlsx`): 251 findings (28.4%) 
   - Code moved but findable with corrections
   - Candidates for automated line number updates
   - Use `cited_line_found_at` column for new line numbers

3. **Problems** (`*_Problems.xlsx`): 456 findings (51.6%)
   - Needs manual review
   - Code not found, function mapping failed, or other issues
   - May require research or different approaches

**Usage:**
```bash
# Default: use enhanced file from step 1
python step2_split_findings.py

# Dry run to see what would be created
python step2_split_findings.py --dry-run

# Custom input file
python step2_split_findings.py --input custom_enhanced.xlsx

# Custom output directory
python step2_split_findings.py --output-dir /path/to/output
```

### Step 3: Line Number Updates (TODO)

**Script:** `step3_create_issues_csv.py` ✅

**Purpose:** Convert Perfect findings to issues.csv format for Vulnhalla LLM processing

**Process:**
- Reads Perfect findings Excel file from Step 2
- Maps Excel columns to issues.csv format required by Vulnhalla
- Uses corrected line numbers (current_line_number) for accuracy
- Creates standard CSV with proper comma/quote handling

**Input:**
- `Findings_WithCodeLine_WithTriageComment_Perfect.xlsx` (176 findings)

**Output:**
- `issues.csv` - Standard format with 9 core columns
- 176 findings with corrected line numbers ready for LLM analysis

**Column Mapping:**
- `name` ← `CID` (finding identifier)
- `help` ← `Category` (vulnerability category)
- `type` ← `Type` (specific vulnerability type)
- `message` ← `coverity_annotation` (detailed description)
- `file` ← `file_path` (enhanced file path)
- `start_line` ← `current_line_number` (corrected line number)
- `start_offset` = 0, `end_offset` = 0 (not available)
- `end_line` = same as start_line

**Usage:**
```bash
# Use default Perfect findings file
python step3_create_issues_csv.py

# Custom input/output
python step3_create_issues_csv.py --input custom_perfect.xlsx --output custom_issues.csv
```

### Step 4: Create Test Subset

**Script:** `step4_create_test_subset.py`

**Purpose:** Create smaller subset of issues.csv for Vulnhalla testing

**Process:**
- Reads full issues.csv (176 findings)
- Creates manageable test subset for initial LLM testing
- Multiple selection methods: first N, random N, by type, specific CIDs
- Outputs issues_test.csv for Vulnhalla processing

**Input:**
- `issues.csv` (176 Perfect findings)

**Output:**
- `issues_test.csv` - Smaller subset for testing

**Selection Methods:**
- **First N:** `--count 10` (default: first 10 findings)
- **Random N:** `--count 5 --random` (random 5 findings)
- **By Type:** `--type "Uninitialized" --count 5` (5 of specific vulnerability type)
- **Specific CIDs:** `--cids 24428,19309,15673` (exact findings by CID)

**Usage:**
```bash
# Default: first 10 findings
python step4_create_test_subset.py

# Random 5 findings
python step4_create_test_subset.py --count 5 --random

# 3 uninitialized variable findings
python step4_create_test_subset.py --type "Uninitialized" --count 3

# Specific findings by CID
python step4_create_test_subset.py --cids 24428,19309,15673
```

### Step 5: Line Number Updates (TODO)

**Script:** `step3_update_line_numbers.py` *(planned)*

**Purpose:** Update line numbers for correctable findings

**Process:**
- Process the Correctable file from Step 2
- Update line numbers using `cited_line_found_at` column
- Validate updates by re-verifying code location
- Generate updated findings file

### Step 4: Final Validation (TODO)

**Script:** `step4_validate_updates.py` *(planned)*

**Purpose:** Re-verify all updated findings

**Process:** 
- Validate line number updates from Step 3
- Cross-check with original perfect matches
- Generate final validated findings file
- Produce accuracy and confidence metrics

## File Dependencies

```
Input Files:
├── ../x01-cov-setup/Findings_WithCodeLine_WithTriageComment.xlsx
├── C:/code/codeQL_CoD/codeql/FunctionTree.csv
└── C:/code/codeQL_CoD/codeql/src.zip

Generated Files:
├── ../x01-cov-setup/Findings_WithCodeLine_WithTriageComment_Enhanced.xlsx
├── ../x01-cov-setup/Findings_WithCodeLine_WithTriageComment_Perfect.xlsx
├── ../x01-cov-setup/Findings_WithCodeLine_WithTriageComment_Correctable.xlsx
└── ../x01-cov-setup/Findings_WithCodeLine_WithTriageComment_Problems.xlsx
```

## Key Metrics & Success Rates

**Overall Results (883 findings):**
- Function mapping success: 55.7% (492/883)
- Perfect matches: 19.9% (176/883)
- Correctable: 28.4% (251/883) 
- Problematic: 51.6% (456/883)

**For Files with Function Data (648 findings):**
- Function mapping: 75.9% (492/648)
- Perfect + Correctable: 65.9% (427/648)

**File Coverage:**
- Files in FunctionTree.csv: 73.4% (648/883)
- Files available in src.zip: 96.8% (855/883)

## Next Steps

1. ✅ **Step 1 Complete** - Function mapping and code verification
2. ✅ **Step 2 Complete** - Triage by analysis status  
3. 🔄 **Step 3 Planned** - Automated line number updates for correctable findings
4. 🔄 **Step 4 Planned** - Final validation and accuracy metrics

The current process successfully identifies and categorizes findings, with nearly 66% of findings that have function data being either perfect or correctable through automated methods.