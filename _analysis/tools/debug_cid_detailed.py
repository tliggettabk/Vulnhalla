#!/usr/bin/env python3
"""
Debug CID Fields - Check actual data
"""

import csv


def debug_cid_fields():
    reportable_file = r"C:\Users\tliggett\Downloads\Reportable.csv"
    
    print("DEBUGGING CID FIELDS IN REPORTABLE.CSV")
    print("=" * 45)
    
    with open(reportable_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        print("CSV Headers:", reader.fieldnames)
        print()
        
        # Look at first 20 rows
        print("First 20 rows:")
        print("-" * 60)
        
        for i, row in enumerate(reader):
            if i < 20:
                cid = row.get('CID', '')
                date = row.get('First Detected', '')
                issue_type = row.get('Type', '')
                print(f"Row {i+1:2d}: CID=\"{cid}\" Date=\"{date}\" Type=\"{issue_type}\"")
            if i >= 19:
                break
    
    # Now let's check what happens when I filter by date
    print("\n" + "=" * 60)
    print("CHECKING DATE FILTERING")
    print("=" * 60)
    
    from datetime import datetime
    
    def parse_date(date_str):
        try:
            if '/' in date_str:
                month, day, year = date_str.split('/')
                if len(year) == 2:
                    year = '20' + year
                return datetime(int(year), int(month), int(day))
        except:
            return None
        return None

    def should_include_issue(first_detected):
        cutoff_date = datetime(2025, 10, 1)
        issue_date = parse_date(first_detected)
        if issue_date is None:
            return True
        return issue_date < cutoff_date
    
    with open(reportable_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        filtered_count = 0
        cid_count = 0
        
        print("First 10 issues that PASS the date filter:")
        print("-" * 50)
        
        for row in reader:
            if should_include_issue(row.get('First Detected', '')):
                filtered_count += 1
                cid = row.get('CID', '')
                
                if cid.strip():  # Check if CID is not empty
                    cid_count += 1
                
                if filtered_count <= 10:
                    print(f"CID: \"{cid}\" | Date: {row.get('First Detected', '')} | Type: {row.get('Type', '')}")
        
        print(f"\nFILTERED RESULTS SUMMARY:")
        print(f"Total passing filter: {filtered_count}")
        print(f"With non-empty CIDs: {cid_count}")
        print(f"With empty CIDs: {filtered_count - cid_count}")


if __name__ == "__main__":
    debug_cid_fields()