#!/usr/bin/env python3
"""
Step 4: Create Test Subset from Issues CSV

This script takes the full issues.csv file (output from step3_create_issues_csv.py)
and creates a smaller subset for testing in Vulnhalla.

Process:
1. Read the full issues.csv file (176 findings)
2. Create a smaller subset for testing
3. Save as issues_test.csv

Options:
- First N findings
- Random N findings
- By vulnerability type
- By CID range

Usage:
    python step4_create_test_subset.py --count 10        # First 10 findings
    python step4_create_test_subset.py --count 5 --random # Random 5 findings
    python step4_create_test_subset.py --type "Uninitialized" --count 5  # 5 of specific type
    python step4_create_test_subset.py --cids 24428,19309,15673  # Specific CIDs
"""

import pandas as pd
import csv
import argparse
import random
from pathlib import Path
from typing import Dict, List, Optional
import sys

def create_test_subset(csv_path: str, subset_options: Dict) -> Dict:
    """
    Create a test subset from the full issues.csv file.
    
    Args:
        csv_path: Path to the full issues.csv file
        subset_options: Options for creating the subset
    
    Returns:
        Dict with processing results
    """
    
    print("=" * 60)
    print("STEP 4: CREATING TEST SUBSET FOR VULNHALLA")
    print("=" * 60)
    
    # Load full issues CSV
    print(f"\n1. Loading full issues CSV: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
        print(f"   Loaded {len(df):,} findings")
    except Exception as e:
        print(f"ERROR loading CSV file: {e}")
        return {"error": str(e)}
    
    if len(df) == 0:
        print("ERROR: No data found in CSV file")
        return {"error": "No data to process"}
    
    print(f"\n2. Creating subset with options: {subset_options}")
    
    # Show available data for filtering
    print(f"   Available vulnerability types:")
    type_counts = df['type'].value_counts()
    for vul_type, count in type_counts.head(10).items():
        print(f"     - {vul_type}: {count}")
    if len(type_counts) > 10:
        print(f"     ... and {len(type_counts) - 10} more types")
    
    # Apply filtering/subset logic
    subset_df = df.copy()
    selection_method = "first"
    
    # Filter by specific CIDs
    if subset_options.get('cids'):
        cid_list = [str(cid).strip() for cid in subset_options['cids']]
        subset_df = subset_df[subset_df['name'].astype(str).isin(cid_list)]
        selection_method = f"specific CIDs: {', '.join(cid_list)}"
        print(f"   Filtered to {len(subset_df)} findings with specific CIDs")
    
    # Filter by vulnerability type
    elif subset_options.get('type'):
        vul_type = subset_options['type']
        subset_df = subset_df[subset_df['type'].str.contains(vul_type, case=False, na=False)]
        selection_method = f"type containing '{vul_type}'"
        print(f"   Filtered to {len(subset_df)} findings of type '{vul_type}'")
    
    # Random selection
    if subset_options.get('random', False) and subset_options.get('count'):
        count = min(subset_options['count'], len(subset_df))
        subset_df = subset_df.sample(n=count, random_state=42)
        selection_method = f"random {count}"
        print(f"   Selected {count} random findings")
    
    # First N selection
    elif subset_options.get('count'):
        count = min(subset_options['count'], len(subset_df))
        subset_df = subset_df.head(count)
        if 'specific' not in selection_method and 'type' not in selection_method:
            selection_method = f"first {count}"
        print(f"   Selected first {count} findings")
    
    if len(subset_df) == 0:
        print("ERROR: No findings match the selection criteria")
        return {"error": "No findings selected"}
    
    # Create output filename
    output_file = Path(csv_path).parent / "issues_test.csv"
    
    print(f"\n3. Saving test subset:")
    print(f"   Selection method: {selection_method}")
    print(f"   Selected findings: {len(subset_df)}")
    print(f"   Output file: {output_file}")
    
    try:
        subset_df.to_csv(output_file, index=False)
        
        print(f"✅ Successfully created test subset: {output_file}")
        print(f"   {len(subset_df):,} findings ready for Vulnhalla testing")
        
        # Show sample of selected findings
        print(f"\n4. Selected findings preview:")
        for idx, row in subset_df.head(5).iterrows():
            print(f"   - CID {row['name']}: {row['type']} at {Path(row['file']).name}:{row['start_line']}")
        
        if len(subset_df) > 5:
            print(f"   ... and {len(subset_df) - 5} more findings")
        
        return {
            'success': True,
            'output_file': str(output_file),
            'selected_count': len(subset_df),
            'total_count': len(df),
            'selection_method': selection_method
        }
        
    except Exception as e:
        print(f"ERROR saving test subset: {e}")
        return {"error": f"Save failed: {e}"}

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Create test subset from issues.csv')
    parser.add_argument('--input', '-i', 
                       default='issues.csv', 
                       help='Path to full issues CSV file')
    parser.add_argument('--count', '-c', type=int, default=10,
                       help='Number of findings to include in test set (default: 10)')
    parser.add_argument('--random', '-r', action='store_true',
                       help='Select random findings instead of first N')
    parser.add_argument('--type', '-t', 
                       help='Filter by vulnerability type (partial match)')
    parser.add_argument('--cids', 
                       help='Specific CIDs to include (comma-separated)')
    
    args = parser.parse_args()
    
    # Resolve input path
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = Path.cwd() / input_path
    
    # Verify input file exists
    if not input_path.exists():
        print(f"ERROR: Input file not found at {input_path}")
        print(f"Make sure you've run step 3 to create issues.csv first.")
        return 1
    
    # Prepare subset options
    subset_options = {
        'count': args.count,
        'random': args.random,
        'type': args.type
    }
    
    if args.cids:
        subset_options['cids'] = args.cids.split(',')
    
    # Process
    results = create_test_subset(str(input_path), subset_options)
    
    if 'error' in results:
        print(f"ERROR: {results['error']}")
        return 1
    
    print(f"\n✓ Step 4 complete. Test subset ready for Vulnhalla testing.")
    print(f"  Use 'issues_test.csv' as input for Vulnhalla LLM analysis.")
    
    return 0

if __name__ == '__main__':
    exit(main())