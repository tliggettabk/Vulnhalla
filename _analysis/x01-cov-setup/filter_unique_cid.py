#!/usr/bin/env python3
"""
Script to filter Excel file for rows where UniqueCID=True

This script processes the Findings Data All Time backup file and creates a new copy
containing only rows where the UniqueCID column is set to True.
"""

import pandas as pd
import sys
import os
from pathlib import Path

def main():
    # File paths
    input_file = r"C:\tmp\cntnr_test\findings-metadata\Findings Data All Time_backup_20251103141207.xlsx"
    output_file = "Findings Data All Time_backup_20251103141207_UniqueCID_Production_Only.xlsx"
    
    # Check if shortcut exists, we'll need to find the actual file
    shortcut_path = "Findings Data All Time_backup_20251103141207.xlsx - Shortcut.lnk"
    
    print("Step 2: Filtering Excel file for uniqueCID=True AND ABK_Code_Type='Production' rows")
    print("=" * 50)
    
    try:
        # Check if the file exists
        if not os.path.exists(input_file):
            print(f"Error: Could not find {input_file}")
            print("Please verify the file path is correct.")
            return
        
        print(f"Loading Excel file: {input_file}")
        
        # Load the Excel file - use the 'data' worksheet specifically
        excel_file = pd.ExcelFile(input_file)
        print(f"Available sheets: {excel_file.sheet_names}")
        
        print(f"\nLoading 'data' worksheet...")
        df = pd.read_excel(input_file, sheet_name='data')
        
        print(f"Data shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        
        # Check if uniqueCID column exists
        if 'uniqueCID' not in df.columns:
            print("Available columns:")
            for i, col in enumerate(df.columns):
                print(f"  {i}: {col}")
            print("\nuniqueCID column not found. Please check column names.")
            return
        
        # Show some sample data
        print(f"\nSample of uniqueCID column values:")
        print(df['uniqueCID'].value_counts())
        print(f"\nFirst few rows of uniqueCID:")
        print(df['uniqueCID'].head(10))
        
        # Check ABK_Code_Type column
        print(f"\nSample of '1. ABK_Code_Type' column values:")
        print(df['1. ABK_Code_Type'].value_counts())
        
        # Filter for rows where uniqueCID is True AND ABK_Code_Type is 'Production'
        print(f"\nApplying filters:")
        print(f"- uniqueCID == True")
        print(f"- '1. ABK_Code_Type' == 'Production'")
        
        filtered_df = df[(df['uniqueCID'] == True) & (df['1. ABK_Code_Type'] == 'Production')]
        
        print(f"Filtered file shape: {filtered_df.shape}")
        print(f"Rows removed: {len(df) - len(filtered_df)}")
        print(f"Rows remaining: {len(filtered_df)}")
        
        # Save the filtered data
        print(f"Saving filtered data to: {output_file}")
        filtered_df.to_excel(output_file, index=False)
        
        print("✅ Successfully created filtered Excel file!")
        print(f"Output file: {output_file}")
        
        # Create a summary
        summary = f"""
Filtering Summary:
- Input file: {input_file}
- Output file: {output_file}
- Original rows: {len(df):,}
- Filtered rows: {len(filtered_df):,}
- Rows removed: {len(df) - len(filtered_df):,}
- Filter conditions: uniqueCID == True AND '1. ABK_Code_Type' == 'Production'
"""
        print(summary)
        
        # Save summary to file
        with open("filtering_summary.txt", "w") as f:
            f.write(summary)
        
    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
        print("Make sure the Excel file is in the current directory")
    except Exception as e:
        print(f"Error processing file: {e}")
        print(f"Error type: {type(e).__name__}")

if __name__ == "__main__":
    main()