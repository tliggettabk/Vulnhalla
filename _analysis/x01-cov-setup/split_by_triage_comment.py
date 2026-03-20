#!/usr/bin/env python3
"""
Script to split the WithCodeLine file into two files based on Last Triage Comment content

This script takes the WithCodeLine file and splits it into:
1. Entries where Last Triage Comment is blank or has no alphabetic characters
2. Entries where Last Triage Comment has information (contains alphabetic characters)
"""

import pandas as pd
import sys
import os
import re
from pathlib import Path

def has_alpha_content(text):
    """Check if text contains alphabetic characters"""
    if pd.isna(text) or text == '' or str(text).strip() == '':
        return False
    # Check if the string contains any alphabetic characters
    return bool(re.search(r'[a-zA-Z]', str(text)))

def main():
    # File paths
    input_file = "Findings_UniqueCID_Production_WithCodeLine.xlsx"
    output_file_blank = "Findings_WithCodeLine_BlankTriageComment.xlsx"
    output_file_with_info = "Findings_WithCodeLine_WithTriageComment.xlsx"
    
    print("Step 2.6: Splitting WithCodeLine file based on Last Triage Comment content")
    print("=" * 70)
    
    try:
        # Check if the input file exists
        if not os.path.exists(input_file):
            print(f"Error: Could not find {input_file}")
            print("Make sure you've run the previous split script first.")
            return
        
        print(f"Loading WithCodeLine Excel file: {input_file}")
        df = pd.read_excel(input_file)
        
        print(f"Input file shape: {df.shape}")
        print(f"Columns available: {len(df.columns)}")
        
        # Check if Last Triage Comment column exists
        if 'Last Triage Comment' not in df.columns:
            print("Available columns containing 'triage' or 'comment':")
            for i, col in enumerate(df.columns):
                if 'triage' in col.lower() or 'comment' in col.lower():
                    print(f"  {i}: {col}")
            print("\n'Last Triage Comment' column not found. Please check column names.")
            return
        
        # Analyze the Last Triage Comment column
        print(f"\nAnalyzing 'Last Triage Comment' column...")
        total_rows = len(df)
        
        # Check for null/empty values
        null_count = df['Last Triage Comment'].isna().sum()
        empty_count = (df['Last Triage Comment'] == '').sum()
        
        print(f"Total rows: {total_rows}")
        print(f"Null values: {null_count}")
        print(f"Empty strings: {empty_count}")
        
        # Show some sample values
        print(f"\nSample values from 'Last Triage Comment':")
        sample_values = df['Last Triage Comment'].dropna().head(10)
        for i, val in enumerate(sample_values):
            truncated_val = str(val)[:100] + "..." if len(str(val)) > 100 else str(val)
            print(f"  {i+1}: '{truncated_val}' (has_alpha: {has_alpha_content(val)})")
        
        # Apply the splitting logic
        print(f"\nApplying split logic...")
        df['has_alpha_content'] = df['Last Triage Comment'].apply(has_alpha_content)
        
        # Split the data
        df_blank = df[~df['has_alpha_content']].drop('has_alpha_content', axis=1)
        df_with_info = df[df['has_alpha_content']].drop('has_alpha_content', axis=1)
        
        print(f"\nSplit results:")
        print(f"Blank/No alpha content: {len(df_blank):,} rows")
        print(f"With alpha content: {len(df_with_info):,} rows")
        print(f"Total: {len(df_blank) + len(df_with_info):,} rows")
        
        # Save the split files
        print(f"\nSaving split files...")
        
        if len(df_blank) > 0:
            df_blank.to_excel(output_file_blank, index=False)
            print(f"✅ Saved blank/no alpha file: {output_file_blank}")
        else:
            print(f"⚠️ No rows with blank/no alpha content found")
        
        if len(df_with_info) > 0:
            df_with_info.to_excel(output_file_with_info, index=False)
            print(f"✅ Saved with-info file: {output_file_with_info}")
        else:
            print(f"⚠️ No rows with alpha content found")
        
        # Create a summary
        summary = f"""
Triage Comment Split Summary:
- Input file: {input_file}
- Output file (blank/no alpha): {output_file_blank}
- Output file (with alpha): {output_file_with_info}
- Original rows: {total_rows:,}
- Blank/No alpha rows: {len(df_blank):,}
- With alpha rows: {len(df_with_info):,}
- Split criteria: presence of alphabetic characters in Last Triage Comment
"""
        print(summary)
        
        # Save summary to file
        with open("triage_split_summary.txt", "w") as f:
            f.write(summary)
        
        print("✅ Successfully split the WithCodeLine file based on Last Triage Comment content!")
        
    except Exception as e:
        print(f"Error processing file: {e}")
        print(f"Error type: {type(e).__name__}")

if __name__ == "__main__":
    main()