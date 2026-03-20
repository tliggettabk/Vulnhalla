#!/usr/bin/env python3
"""
Step 2: Split Function Mapping Results

This script reads the enhanced findings Excel file (output from step1_function_mapping.py)
and splits it into three separate files based on analysis status for targeted processing.

Process:
1. Read Findings_WithCodeLine_WithTriageComment_Enhanced.xlsx
2. Filter by analysis_status column:
   - 'perfect': Code exactly where expected
   - 'found': Code moved but findable with corrections
   - 'problem': Needs manual review
3. Create three separate Excel files for different handling workflows

Usage:
    python step2_split_findings.py                          # Use default enhanced file
    python step2_split_findings.py --input custom_file.xlsx # Use custom input file
    python step2_split_findings.py --dry-run                # Show counts without creating files
"""

import pandas as pd
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sys

def split_findings_by_status(excel_path: str, output_dir: str = None, dry_run: bool = False) -> Dict:
    """
    Split findings Excel file by analysis status.
    
    Args:
        excel_path: Path to enhanced Excel file
        output_dir: Directory for output files (default: same as input)
        dry_run: If True, only show counts without creating files
    
    Returns:
        Dict with processing results and statistics
    """
    
    print("=" * 60)
    print("STEP 2: SPLITTING FINDINGS BY ANALYSIS STATUS")
    print("=" * 60)
    
    # Load enhanced data
    print(f"\n1. Loading enhanced Excel file: {excel_path}")
    try:
        df = pd.read_excel(excel_path)
        print(f"   Loaded {len(df):,} findings with {len(df.columns):,} columns")
    except Exception as e:
        print(f"ERROR loading Excel file: {e}")
        return {"error": str(e)}
    
    # Check for analysis_status column
    if 'analysis_status' not in df.columns:
        print("ERROR: 'analysis_status' column not found. Input file must be enhanced with function mapping results.")
        return {"error": "Missing analysis_status column"}
    
    # Count by status
    status_counts = df['analysis_status'].value_counts()
    total_findings = len(df)
    
    print(f"\n2. Analysis status breakdown:")
    print(f"   Total findings: {total_findings:,}")
    for status in ['perfect', 'found', 'problem']:
        count = status_counts.get(status, 0)
        percentage = count / total_findings * 100 if total_findings > 0 else 0
        print(f"   {status.capitalize():<8}: {count:,} ({percentage:.1f}%)")
    
    # Check for unexpected statuses
    expected_statuses = {'perfect', 'found', 'problem'}
    actual_statuses = set(status_counts.index)
    unexpected = actual_statuses - expected_statuses
    if unexpected:
        print(f"   WARNING: Unexpected statuses found: {unexpected}")
    
    # Determine output directory - default to current working directory, not input file directory
    if output_dir is None:
        output_dir = Path.cwd()  # Use current working directory instead of input file directory
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(exist_ok=True)
    
    # Base filename for outputs
    base_name = Path(excel_path).stem
    if base_name.endswith('_Enhanced'):
        base_name = base_name[:-9]  # Remove '_Enhanced' suffix
    
    results = {}
    
    print(f"\n3. Creating split files in: {output_dir}")
    
    # Split and save each category
    for status in ['perfect', 'found', 'problem']:
        # Filter data
        filtered_df = df[df['analysis_status'] == status].copy()
        count = len(filtered_df)
        
        if count == 0:
            print(f"   {status.capitalize():<8}: 0 findings - skipping file creation")
            results[status] = {'count': 0, 'file': None}
            continue
        
        # Create output filename
        status_suffix = {
            'perfect': 'Perfect',
            'found': 'Correctable', 
            'problem': 'Problems'
        }
        
        output_file = output_dir / f"{base_name}_{status_suffix[status]}.xlsx"
        
        if dry_run:
            print(f"   {status.capitalize():<8}: {count:,} findings -> [DRY-RUN] {output_file.name}")
            results[status] = {'count': count, 'file': str(output_file)}
        else:
            try:
                # Sort by file path and line number for easier review
                if not filtered_df.empty:
                    sort_columns = []
                    if 'file_path' in filtered_df.columns:
                        sort_columns.append('file_path')
                    if 'line_number' in filtered_df.columns:
                        sort_columns.append('line_number')
                    
                    if sort_columns:
                        filtered_df = filtered_df.sort_values(sort_columns)
                
                filtered_df.to_excel(output_file, index=False)
                print(f"   {status.capitalize():<8}: {count:,} findings -> {output_file.name}")
                results[status] = {'count': count, 'file': str(output_file)}
                
            except Exception as e:
                print(f"   ERROR saving {status} file: {e}")
                results[status] = {'count': count, 'file': None, 'error': str(e)}
    
    # Summary
    print(f"\n" + "=" * 60)
    print("SPLIT RESULTS SUMMARY")  
    print("=" * 60)
    
    if dry_run:
        print("DRY-RUN MODE - No files created")
    else:
        print("Files created successfully:")
    
    total_processed = 0
    for status in ['perfect', 'found', 'problem']:
        result = results.get(status, {'count': 0})
        count = result['count']
        total_processed += count
        
        if count > 0:
            file_info = result.get('file', 'None')
            if 'error' in result:
                print(f"   {status.capitalize():<12}: {count:,} findings [ERROR: {result['error']}]")
            else:
                file_name = Path(file_info).name if file_info else 'None'
                print(f"   {status.capitalize():<12}: {count:,} findings -> {file_name}")
        else:
            print(f"   {status.capitalize():<12}: {count:,} findings [No file created]")
    
    print(f"\nTotal processed: {total_processed:,} / {total_findings:,}")
    
    if not dry_run:
        print(f"\n✓ Split complete. Files saved to: {output_dir}")
        print(f"\nNext steps:")
        print(f"   - Review Perfect findings for immediate processing")
        print(f"   - Process Correctable findings with line number updates") 
        print(f"   - Manually review Problem findings")
    
    return {
        'status_counts': status_counts.to_dict(),
        'results': results,
        'total_findings': total_findings,
        'output_dir': str(output_dir)
    }

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Split enhanced findings by analysis status')
    parser.add_argument('--input', '-i', 
                       default='../x01-cov-setup/Findings_WithCodeLine_WithTriageComment_Enhanced.xlsx', 
                       help='Path to enhanced Excel file from step 1')
    parser.add_argument('--output-dir', '-o', 
                       help='Output directory for split files (default: same as input)')
    parser.add_argument('--dry-run', '-d', action='store_true', 
                       help='Show what would be created without actually creating files')
    
    args = parser.parse_args()
    
    # Resolve input path
    script_dir = Path(__file__).parent
    if not Path(args.input).is_absolute():
        input_path = script_dir / args.input
    else:
        input_path = Path(args.input)
    
    # Verify input file exists
    if not input_path.exists():
        print(f"ERROR: Input file not found at {input_path}")
        return 1
    
    # Process
    results = split_findings_by_status(str(input_path), args.output_dir, args.dry_run)
    
    if 'error' in results:
        print(f"ERROR: {results['error']}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())