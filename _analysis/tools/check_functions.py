import csv

print('FUNCTION LENGTH ANALYSIS')
print('=' * 30)

with open(r'C:\code\codeQL_CoD\codeql\FunctionTree.csv', 'r') as f:
    reader = csv.DictReader(f)
    
    lengths = []
    count = 0
    
    for row in reader:
        try:
            start = int(row['start_line'])
            end = int(row['end_line'])
            length = end - start + 1
            
            if count < 15:  # Show first 15 examples
                print(f"{row['function_name'][:20]:20} {start:>5} to {end:>5} = {length:>3} lines")
            
            if length > 0:  # Only count valid lengths
                lengths.append(length)
            
            count += 1
            
        except Exception as e:
            continue
    
    print(f"\nTotal functions processed: {count}")
    print(f"Valid functions: {len(lengths)}")
    
    if lengths:
        import statistics
        print(f"\nFUNCTION LENGTH STATISTICS:")
        print(f"Smallest: {min(lengths)} lines")
        print(f"Largest: {max(lengths)} lines") 
        print(f"Average: {statistics.mean(lengths):.1f} lines")
        print(f"Median: {statistics.median(lengths):.1f} lines")
        
        # Show distribution
        ranges = [(1, 5), (6, 10), (11, 25), (26, 50), (51, 100), (101, 500), (501, float('inf'))]
        labels = ['Very Small (1-5)', 'Small (6-10)', 'Medium (11-25)', 'Large (26-50)', 'Very Large (51-100)', 'Huge (101-500)', 'Massive (500+)']
        
        print(f"\nSIZE DISTRIBUTION:")
        for (min_size, max_size), label in zip(ranges, labels):
            count = len([l for l in lengths if min_size <= l < max_size])
            percent = count / len(lengths) * 100
            print(f"{label:20} {count:>6} ({percent:>5.1f}%)")