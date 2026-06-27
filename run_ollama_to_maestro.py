import json
import time

import requests

OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
MAESTRO_GOVERN_URL = "http://127.0.0.1:8000/cgt/govern"
MAESTRO_API_KEY = "local_test_key_123456789"
MODEL = "qwen3-coder:30b"
RUN_ID = f"ollama_test_{int(time.time())}"

prompt = "Write a practical plan to improve customer service in a telecom company. Keep it concise but useful."

ollama_payload = {
    "model": MODEL,
    "messages": [
        {
            "role": "user",
            "content": prompt
        }
    ],
    "temperature": 0.2
}

print("=== Calling Ollama / qwen3-coder ===")
ollama_response = requests.post(OLLAMA_URL, json=ollama_payload, timeout=180)
print("OLLAMA STATUS:", ollama_response.status_code)
ollama_response.raise_for_status()

ollama_json = ollama_response.json()
agent_answer = ollama_json["choices"][0]["message"]["content"]

print("\n=== Agent Answer ===")
print(agent_answer)

maestro_payload = {
    "answer": agent_answer,
    "client_query": prompt,
    "context": {
        "run_id": RUN_ID,
        "agent_id": "qwen3-coder-local",
        "model": MODEL,
        "provider": "ollama",
        "scenario_id": "customer_service",
        "tags": ["local", "ollama", "governance"],
        "environment": "local",
        "policy_version": "cgt_v1",
    }
}

headers = {
    "X-API-Key": MAESTRO_API_KEY,
    "Content-Type": "application/json"
}

print("\n=== Sending Answer to Maestro /cgt/govern ===")
maestro_response = requests.post(
    MAESTRO_GOVERN_URL,
    headers=headers,
    json=maestro_payload,
    timeout=60
)

print("MAESTRO STATUS:", maestro_response.status_code)
maestro_response.raise_for_status()

judgment = maestro_response.json()

print("\n=== Maestro Judgment ===")
print(json.dumps(judgment, indent=2, ensure_ascii=False))
