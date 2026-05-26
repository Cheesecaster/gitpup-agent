#!/usr/bin/env python3
"""GitPup Agent Core — LLM interaction with OpenRouter"""
import os, json, urllib.request

LLM_URL = os.environ.get("LLM_URL", "https://openrouter.ai/api/v1/chat/completions")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3.6-flash")

def ask(messages, system="", max_tokens=2000, temperature=0.7, model=None):
    """Call LLM with a list of messages. Returns the assistant reply text."""
    full_messages = []
    if system:
        full_messages.append({"role": "system", "content": system})
    full_messages.extend(messages)
    
    data = json.dumps({
        "model": model or LLM_MODEL,
        "messages": full_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()
    
    req = urllib.request.Request(LLM_URL, data=data)
    req.add_header("Content-Type", "application/json")
    if LLM_API_KEY:
        req.add_header("Authorization", "Bearer " + LLM_API_KEY)
    
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            resp = json.loads(r.read())
            return resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return f"[LLM Error: {str(e)[:100]}]"
