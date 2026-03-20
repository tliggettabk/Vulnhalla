#!/usr/bin/env python3
"""
Check exact file path from unmatched issues
"""

import csv


def check_gscr_path():
    """Check the exact file path for g_scr_main_mp from unmatched issues."""
    
    issues_file = "zCoD/unmatched_issues_with_cids.csv"
    
    print("CHECKING G_SCR_MAIN_MP FILE PATH")
    print("=" * 35)
    
    with open(issues_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        found_count = 0
        for row in reader:
            file_path = row.get('file', '')
            if 'g_scr_main_mp' in file_path:
                found_count += 1
                print(f"File: {file_path}")
                print(f"Line: {row.get('start_line', '')}")
                print(f"Issue: {row.get('name', '')}")
                print()
        
        if found_count == 0:
            print("No g_scr_main_mp files found in unmatched issues")
    
    # Also check other issue files
    for filename in ["matched_issues_with_cids.csv", "no_line_number_issues_with_cids.csv"]:
        filepath = f"zCoD/{filename}"
        print(f"\\nChecking {filename}:")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                found_count = 0
                
                for row in reader:
                    file_path = row.get('file', '')
                    if 'g_scr_main_mp' in file_path:
                        found_count += 1
                        print(f"  Found: {file_path}")
                        
                        if found_count == 1:  # Show details for first match
                            print(f"  Line: {row.get('start_line', '')}")
                            print(f"  Issue: {row.get('name', '')}")
                
                if found_count == 0:
                    print(f"  No g_scr_main_mp files found")
                else:
                    print(f"  Total found: {found_count}")
                    
        except FileNotFoundError:
            print(f"  File not found: {filepath}")


if __name__ == "__main__":
    check_gscr_path()