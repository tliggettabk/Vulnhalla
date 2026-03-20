#!/usr/bin/env python3
"""
Debug CID Issue - Check what's in the filtered data
"""

import csv
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


def debug_cid_issue():
    reportable_file = r"C:\Users\tliggett\Downloads\Reportable.csv"
    
    print("DEBUGGING CID ISSUE")
    print("=" * 20)
    
    with open(reportable_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        total_count = 0
        filtered_count = 0
        cids_found = 0
        
        print("\\nFirst 10 issues that pass the filter:")
        print("-" * 40)
        
        for row in reader:
            total_count += 1
            
            if should_include_issue(row.get('First Detected', '')):
                filtered_count += 1
                
                cid = row.get('CID', '')
                first_detected = row.get('First Detected', '')
                issue_type = row.get('Type', '')
                
                if cid:
                    cids_found += 1
                
                if filtered_count <= 10:
                    print(f"CID: '{cid}' | Date: {first_detected} | Type: {issue_type}")
    
    print(f"\\nSUMMARY:")
    print(f"Total issues: {total_count}")
    print(f"Issues passing filter: {filtered_count}")
    print(f"Issues with CIDs: {cids_found}")
    print(f"Issues without CIDs: {filtered_count - cids_found}")


if __name__ == "__main__":
    debug_cid_issue()