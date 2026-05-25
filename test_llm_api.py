#!/usr/bin/env python3
"""Test LLM on server. Drop via base64 then run."""
import os
os.chdir('/opt/gitpup/src')

from dotenv import load_dotenv
load_dotenv('/opt/gitpup/.env')
print("DOTENV OK")

from openai import OpenAI
client = OpenAI(
    api_key=os.getenv('OPENROUTER_API_KEY'),
    base_url='https://openrouter.ai/api/v1',
)
model = os.getenv('OPENROUTER_MODEL', 'qwen/qwen3.6-flash')
print(f"MODEL: {model}")

resp = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Say woof! TomKet"}],
    max_tokens=30,
)
print("WOOF:", resp.choices[0].message.content.strip())
