#!/usr/bin/env python3
"""
Quick script to test different Azure model deployments
"""

import os
from dotenv import load_dotenv
from src.utils.llm_config import load_llm_config
import litellm

load_dotenv()

# Common deployment names to try
test_models = [
    "gpt-4o",
    "gpt-4-turbo", 
    "gpt4o",
    "gpt4-turbo",
    "gpt-4",
    "gpt4"
]

print("Testing available Azure model deployments...")
print("=" * 50)

for model_name in test_models:
    try:
        # Temporarily set the model
        os.environ["MODEL"] = model_name
        config = load_llm_config()
        
        # Try a simple request
        response = litellm.completion(
            model=config["model"],
            api_key=config["api_key"],
            api_base=config.get("endpoint"),
            api_version=config.get("api_version"),
            messages=[{"role": "user", "content": "Say 'Hello' if you can read this."}],
            temperature=0.1,
            max_tokens=10
        )
        
        print(f"✅ {model_name}: WORKING")
        print(f"   Response: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"❌ {model_name}: {str(e)[:100]}...")

print("\n" + "=" * 50)
print("Use any working deployment name as your MODEL in .env")