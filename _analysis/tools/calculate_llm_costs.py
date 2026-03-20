#!/usr/bin/env python3
"""
Calculate rough LLM analysis costs for function groups
"""

import csv


def calculate_llm_costs():
    """Calculate rough LLM analysis costs by function size groups."""
    
    matched_file = "zCoD/matched_issues_with_cids.csv"
    
    print("LLM ANALYSIS COST ESTIMATION")
    print("=" * 35)
    
    # Cost assumptions
    print("ASSUMPTIONS:")
    print("- C++ code: ~12 tokens per line (avg)")
    print("- GPT-4: $0.03/1K input + $0.06/1K output tokens")
    print("- Claude: $0.015/1K input + $0.075/1K output tokens") 
    print("- Analysis output: ~800 tokens per function")
    print("- Input = function code + prompt (~200 tokens)")
    print()
    
    tokens_per_line = 12
    prompt_tokens = 200
    output_tokens = 800
    
    # GPT-4 pricing
    gpt4_input_cost = 0.03 / 1000  # per token
    gpt4_output_cost = 0.06 / 1000
    
    # Claude pricing  
    claude_input_cost = 0.015 / 1000
    claude_output_cost = 0.075 / 1000
    
    # Read matched issues and group by function length
    function_lengths = []
    
    with open(matched_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                length = int(row['function_length'])
                function_lengths.append(length)
            except (ValueError, KeyError):
                continue
    
    total_issues = len(function_lengths)
    
    # Define size groups
    size_groups = [
        ("1-25 lines", 1, 25),
        ("26-50 lines", 26, 50), 
        ("51-100 lines", 51, 100),
        ("101-200 lines", 101, 200),
        ("201+ lines", 201, 9999)
    ]
    
    print(f"COST ANALYSIS FOR {total_issues} VULNERABLE FUNCTIONS")
    print("=" * 60)
    
    total_gpt4_cost = 0
    total_claude_cost = 0
    
    for group_name, min_len, max_len in size_groups:
        # Count functions in this group
        group_functions = [l for l in function_lengths if min_len <= l <= max_len]
        count = len(group_functions)
        
        if count == 0:
            continue
            
        avg_length = sum(group_functions) / len(group_functions)
        
        # Calculate tokens
        input_tokens_per_func = (avg_length * tokens_per_line) + prompt_tokens
        
        # Calculate costs per function
        gpt4_cost_per_func = (input_tokens_per_func * gpt4_input_cost) + (output_tokens * gpt4_output_cost)
        claude_cost_per_func = (input_tokens_per_func * claude_input_cost) + (output_tokens * claude_output_cost)
        
        # Calculate group totals
        group_gpt4_cost = count * gpt4_cost_per_func
        group_claude_cost = count * claude_cost_per_func
        
        total_gpt4_cost += group_gpt4_cost
        total_claude_cost += group_claude_cost
        
        print(f"\\n📊 {group_name}")
        print(f"   Functions: {count}")
        print(f"   Avg length: {avg_length:.0f} lines")
        print(f"   Tokens per function: ~{input_tokens_per_func:.0f} input + {output_tokens} output")
        print(f"   Cost per function:")
        print(f"     GPT-4: ${gpt4_cost_per_func:.3f}")
        print(f"     Claude: ${claude_cost_per_func:.3f}")
        print(f"   Group total:")
        print(f"     GPT-4: ${group_gpt4_cost:.2f}")
        print(f"     Claude: ${group_claude_cost:.2f}")
    
    print("\\n" + "=" * 60)
    print("TOTAL COST TO ANALYZE ALL MATCHED FUNCTIONS")
    print("=" * 60)
    print(f"GPT-4 Total: ${total_gpt4_cost:.2f}")
    print(f"Claude Total: ${total_claude_cost:.2f}")
    
    print("\\n📝 COST PER 100 FUNCTIONS BY SIZE:")
    print("-" * 40)
    
    for group_name, min_len, max_len in size_groups:
        group_functions = [l for l in function_lengths if min_len <= l <= max_len]
        if len(group_functions) == 0:
            continue
            
        avg_length = sum(group_functions) / len(group_functions)
        input_tokens_per_func = (avg_length * tokens_per_line) + prompt_tokens
        
        gpt4_cost_per_func = (input_tokens_per_func * gpt4_input_cost) + (output_tokens * gpt4_output_cost)
        claude_cost_per_func = (input_tokens_per_func * claude_input_cost) + (output_tokens * claude_output_cost)
        
        gpt4_per_100 = gpt4_cost_per_func * 100
        claude_per_100 = claude_cost_per_func * 100
        
        print(f"{group_name:15} | GPT-4: ${gpt4_per_100:5.1f} | Claude: ${claude_per_100:5.1f}")
    
    print("\\n💡 RECOMMENDATIONS:")
    print("- Start with smaller functions (1-50 lines) for proof of concept")
    print("- Claude is more cost-effective for bulk analysis")
    print("- Consider batch processing to reduce per-function overhead")
    print("- Large functions (200+ lines) may need chunking for better results")


if __name__ == "__main__":
    calculate_llm_costs()