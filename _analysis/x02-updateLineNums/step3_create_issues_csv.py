#!/usr/bin/env python3
"""
Step 3: Create Issues CSV from Perfect Findings

This script reads the Perfect findings Excel file (output from step2_split_findings.py)
and creates an issues.csv file in the format expected by Vulnhalla for LLM processing.

Process:
1. Read Findings_WithCodeLine_WithTriageComment_Perfect.xlsx
2. Map Excel columns to issues.csv format
3. Correct file paths for Vulnhalla compatibility (remove /cod_trunk prefix)
4. Create issues.csv with all required columns in correct order

Column Mapping:
- name → CID
- help → category
- type → Type
- message → coverity_annotation
- file → File (original) or file_path (enhanced)
- start_line → current_line_number (corrected line) or line_number (fallback)
- start_offset → 0 (not available)
- end_line → same as start_line
- end_offset → 0 (not available)
- matched_function → found_function_name
- function_length → found_function_length
- function_start_line → found_function_start
- function_end_line → found_function_end

Usage:
    python step3_create_issues_csv.py                    # Use default Perfect file
    python step3_create_issues_csv.py --input custom.xlsx # Use custom input file
    python step3_create_issues_csv.py --output custom.csv # Use custom output file
"""

import pandas as pd
import csv
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import sys

def correct_file_path_for_vulnhalla(file_path: str) -> str:
    """
    Correct file paths to be compatible with Vulnhalla's LLM analysis.
    
    This function transforms file paths to be relative to the CodeQL database 
    sourceLocationPrefix, ensuring compatibility with the ZIP archive structure.
    
    Args:
        file_path: Original file path from Excel findings
        
    Returns:
        Corrected path relative to sourceLocationPrefix
        
    Examples:
        '/cod_trunk/code/common/libs/AVT/IndirectionTexture.cpp' 
        → '/code/common/libs/AVT/IndirectionTexture.cpp'
    """
    if not file_path or pd.isna(file_path):
        return ''
    
    path_str = str(file_path)
    
    # Remove the /cod_trunk prefix to make path relative to sourceLocationPrefix
    # The CodeQL database has sourceLocationPrefix: D:\mapped_drives\cod\trunk
    # So paths should be relative to that (i.e., start with /code/...)
    if path_str.startswith('/cod_trunk/'):
        path_str = path_str.replace('/cod_trunk/', '/')
        
    return path_str

def create_issues_csv(excel_path: str, output_csv: str = None) -> Dict:
    """
    Convert Perfect findings Excel file to issues.csv format.
    
    Args:
        excel_path: Path to Perfect findings Excel file
        output_csv: Path for output CSV file (default: issues.csv)
    
    Returns:
        Dict with processing results and statistics
    """
    
    print("=" * 60)
    print("STEP 3: CREATING ISSUES.CSV FROM PERFECT FINDINGS")
    print("=" * 60)
    
    # Load Perfect findings
    print(f"\n1. Loading Perfect findings Excel file: {excel_path}")
    try:
        df = pd.read_excel(excel_path)
        print(f"   Loaded {len(df):,} Perfect findings with {len(df.columns):,} columns")
    except Exception as e:
        print(f"ERROR loading Excel file: {e}")
        return {"error": str(e)}
    
    if len(df) == 0:
        print("WARNING: No Perfect findings found in input file")
        return {"error": "No data to process"}
    
    # Check required columns exist
    required_mappings = {
        'name': ['CID', 'cid'],
        'help': ['category', 'Category'],
        'type': ['Type', 'type'], 
        'message': ['coverity_annotation', 'Coverity Annotation'],
        'file': ['file_path', 'File'],
        'start_line': ['current_line_number', 'line_number', 'current_line_number', 'Line Number']
    }
    
    column_map = {}
    missing_columns = []
    
    print(f"\n2. Mapping Excel columns to issues.csv format:")
    
    for csv_col, possible_excel_cols in required_mappings.items():
        found = False
        for excel_col in possible_excel_cols:
            if excel_col in df.columns:
                column_map[csv_col] = excel_col
                print(f"   {csv_col:<12} ← {excel_col}")
                found = True
                break
        
        if not found:
            missing_columns.append(csv_col)
            print(f"   {csv_col:<12} ← [MISSING - tried: {', '.join(possible_excel_cols)}]")
    
    if missing_columns:
        print(f"\nERROR: Missing required columns: {missing_columns}")
        print(f"Available columns: {', '.join(sorted(df.columns))}")
        return {"error": f"Missing columns: {missing_columns}"}
    
    # Set default output path
    if output_csv is None:
        output_csv = Path(excel_path).parent / "issues.csv"
    else:
        output_csv = Path(output_csv)
    
    print(f"\n3. Creating issues.csv with {len(df):,} findings...")
    print(f"   Output file: {output_csv}")
    
    # Build issues.csv data
    issues_data = []
    
    for idx, row in df.iterrows():
        # Correct file path for Vulnhalla compatibility
        raw_file_path = str(row[column_map['file']]) if pd.notna(row[column_map['file']]) else ''
        corrected_file_path = correct_file_path_for_vulnhalla(raw_file_path)
        
        # Core required columns in exact order
        issue_record = {
            'name': str(row[column_map['name']]) if pd.notna(row[column_map['name']]) else '',
            'help': str(row[column_map['help']]) if pd.notna(row[column_map['help']]) else '',
            'type': str(row[column_map['type']]) if pd.notna(row[column_map['type']]) else '',
            'message': str(row[column_map['message']]) if pd.notna(row[column_map['message']]) else '',
            'file': corrected_file_path,
            'start_line': int(row[column_map['start_line']]) if pd.notna(row[column_map['start_line']]) else 0,
            'start_offset': 0,  # Not available
            'end_line': int(row[column_map['start_line']]) if pd.notna(row[column_map['start_line']]) else 0,  # Same as start_line
            'end_offset': 0,  # Not available
        }
        
        issues_data.append(issue_record)
    
    # Write CSV file with exact column order - core columns only
    csv_columns = [
        'name', 'help', 'type', 'message',
        'file', 'start_line', 'start_offset', 'end_line', 'end_offset'
    ]
    
    try:
        with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
            writer.writeheader()
            writer.writerows(issues_data)
        
        print(f"✅ Successfully created issues.csv: {output_csv}")
        print(f"   {len(issues_data):,} findings converted")
        print(f"   Columns: {', '.join(csv_columns)}")
        print(f"   File paths corrected for Vulnhalla compatibility")
        
        # Show sample data
        if issues_data:
            print(f"\n4. Sample data (first row):")
            sample = issues_data[0]
            for col, value in sample.items():
                if col == 'file':
                    print(f"   {col:<18}: {value} (path corrected)")
                else:
                    print(f"   {col:<18}: {value}")
        
        return {
            'success': True,
            'output_file': str(output_csv),
            'findings_count': len(issues_data),
            'column_mapping': {k: v for k, v in column_map.items() if v is not None}
        }
        
    except Exception as e:
        print(f"ERROR writing CSV file: {e}")
        return {"error": f"CSV write failed: {e}"}

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Create issues.csv from Perfect findings')
    parser.add_argument('--input', '-i', 
                       default='Findings_WithCodeLine_WithTriageComment_Perfect.xlsx', 
                       help='Path to Perfect findings Excel file')
    parser.add_argument('--output', '-o', 
                       help='Output CSV file path (default: issues.csv in same directory as input)')
    
    args = parser.parse_args()
    
    # Resolve input path
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = Path.cwd() / input_path
    
    # Verify input file exists
    if not input_path.exists():
        print(f"ERROR: Input file not found at {input_path}")
        return 1
    
    # Process
    results = create_issues_csv(str(input_path), args.output)
    
    if 'error' in results:
        print(f"ERROR: {results['error']}")
        return 1
    
    print(f"\n✓ Step 3 complete. Issues.csv ready for Vulnhalla LLM processing.")
    
    return 0

if __name__ == '__main__':
    exit(main())