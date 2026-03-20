# Vulnhalla Data Processing Documentation

## Project Overview
This document tracks the steps for processing Coverity findings data to create a filtered dataset containing only unique CID entries.

## Steps

### Step 1: Get CSV of Open Findings from Coverity ✅
- **Status**: Completed
- **Output**: `0.+all.csv`
- **Description**: Retrieved current open findings data from Coverity in CSV format

### Step 2: Filter Backup Data for Unique CIDs and Production Code ✅
- **Status**: Completed
- **Input**: `Findings Data All Time_backup_20251103141207.xlsx` (from `C:\tmp\cntnr_test\findings-metadata\`)
- **Output**: `Findings Data All Time_backup_20251103141207_UniqueCID_Production_Only.xlsx`
- **Goal**: Create a copy with only rows where uniqueCID=true AND ABK_Code_Type='Production'
- **Rationale**: Using this backup file as it's closest to the October snapshot and filtering for production code only

#### Results:
- **Original rows**: 4,134 findings
- **Filtered rows**: 1,631 findings (uniqueCID=True AND Production code)
- **Rows removed**: 2,503 findings (duplicates + non-production code)
- **Worksheet used**: 'data' sheet from the Excel file
- **Filter conditions**: `uniqueCID == True` AND `'1. ABK_Code_Type' == 'Production'`

#### Breakdown of filtering:
- uniqueCID=True only: 1,945 findings (from original 4,134)
- Production code only: 3,719 findings (from original 4,134)  
- **Both conditions**: 1,631 findings (final result)

#### Sub-steps for Step 2:
- [x] Create Python script to process Excel file
- [x] Load the Excel file and examine its structure
- [x] Identify correct worksheet ('data') and column name ('uniqueCID')
- [x] Filter rows where uniqueCID=true AND ABK_Code_Type='Production'
- [x] Save filtered data to new Excel file
- [x] Validate the output

### Step 2.6: Split WithCodeLine by Triage Comment Content ✅
- **Status**: Completed
- **Input**: `Findings_UniqueCID_Production_WithCodeLine.xlsx` (1,627 rows)
- **Outputs**: 
  - `Findings_WithCodeLine_BlankTriageComment.xlsx` (744 rows)
  - `Findings_WithCodeLine_WithTriageComment.xlsx` (883 rows)
- **Goal**: Split findings with code context based on whether they have triage comments
- **Rationale**: Separate already-triaged findings from untriaged ones for focused analysis

#### Results:
- **Input rows**: 1,627 findings (with code context)
- **Blank/No triage comments**: 744 findings (45.7% - untriaged)
- **With triage comments**: 883 findings (54.3% - triaged)
- **Split criteria**: Presence of alphabetic characters in `Last Triage Comment` field

#### Sub-steps for Step 2.6:
- [x] Create script to analyze Last Triage Comment column
- [x] Implement logic to detect alphabetic content vs blank/empty
- [x] Split WithCodeLine data into two separate Excel files
- [x] Validate split results and create summary

### Step 2.5: Split Findings by Code Line Content ✅
- **Status**: Completed
- **Input**: `Findings Data All Time_backup_20251103141207_UniqueCID_Production_Only.xlsx` 
- **Outputs**: 
  - `Findings_UniqueCID_Production_BlankCodeLine.xlsx` (4 rows)
  - `Findings_UniqueCID_Production_WithCodeLine.xlsx` (1,627 rows)
- **Goal**: Split filtered data based on whether `code_at_cited_line` contains alphabetic content
- **Rationale**: Separate findings with actual code context from those without

#### Results:
- **Input rows**: 1,631 findings (unique Production code)
- **Blank/No alpha content**: 4 findings (no meaningful code context)
- **With alpha content**: 1,627 findings (has actual code information)
- **Split criteria**: Presence of alphabetic characters in `code_at_cited_line` field

#### Sub-steps for Step 2.5:
- [x] Create script to analyze code_at_cited_line column
- [x] Implement logic to detect alphabetic content vs blank/empty
- [x] Split data into two separate Excel files
- [x] Validate split results and create summary

## Files Created/Modified
- `process_documentation.md` - This documentation file
- `filter_unique_cid.py` - Script to process the Excel file ✅
- `split_by_code_line.py` - Script to split by code line content ✅
- `split_by_triage_comment.py` - Script to split by triage comment content ✅
- `Findings Data All Time_backup_20251103141207_UniqueCID_Production_Only.xlsx` - Filtered output file ✅
- `Findings_UniqueCID_Production_BlankCodeLine.xlsx` - Split file (blank code lines) ✅
- `Findings_UniqueCID_Production_WithCodeLine.xlsx` - Split file (with code lines) ✅
- `Findings_WithCodeLine_BlankTriageComment.xlsx` - Split file (no triage comments) ✅
- `Findings_WithCodeLine_WithTriageComment.xlsx` - Split file (with triage comments) ✅
- `filtering_summary.txt` - Summary of filtering operation ✅
- `split_summary.txt` - Summary of code line split operation ✅
- `triage_split_summary.txt` - Summary of triage comment split operation ✅

## Notes
- Starting date: March 17, 2026
- Working with backup from November 3, 2025 (closest available to October snapshot)
- Original data contains 4,134 findings across 114 columns
- After filtering for unique CIDs + Production code: 1,631 findings remain (60.5% reduction)
- After splitting by code line content: 4 blank + 1,627 with code = 1,631 total
- After splitting by triage comment: 744 untriaged + 883 triaged = 1,627 total
- Column name was 'uniqueCID' (lowercase 'u'), not 'UniqueCID'
- ABK_Code_Type value was 'Production' (capitalized), not 'production'
- Data was located in the 'data' worksheet of the Excel file
- Most findings (99.7%) have meaningful code context in code_at_cited_line field
- Of findings with code context: 45.7% are untriaged, 54.3% have triage comments