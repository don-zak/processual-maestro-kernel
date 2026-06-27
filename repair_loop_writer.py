from pathlib import Path

code = r'''
import json
import requests

OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
MAESTRO_GOVERN_URL = "http://127.0.0.1:8000/cgt/govern"
MAESTRO_API_KEY = "local_test_key_123456789"
MODEL = "qwen3-coder:30b"

HEADERS = {
    "X-API-Key": MAESTRO_API_KEY,
    "Content-Type": "application/json"
}

def call_ollama(prompt, label):
    print(f"=== Calling Ollama: {label} ===")
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=180)
    print("OLLAMA STATUS:", response.status_code)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def govern(answer, prompt, stage):
    print(f"=== Sending to Maestro: {stage} ===")
    payload = {
        "answer": answer,
        "context": {
            "task": "evaluate_local_agent_answer",
            "agent": MODEL,
            "prompt": prompt,
            "stage": stage
        }
    }

    response = requests.post(
        MAESTRO_GOVERN_URL,
        headers=HEADERS,
        json=payload,
        timeout=60
    )
    print("MAESTRO STATUS:", response.status_code)
    response.raise_for_status()
    return response.json()

original_prompt = "Write a practical plan to improve customer service in a telecom company. Keep it concise but useful."

original_answer = call_ollama(original_prompt, "original answer")

print("\n=== Original Agent Answer ===")
print(original_answer)

first_judgment = govern(original_answer, original_prompt, "first_judgment")

print("\n=== First Maestro Judgment ===")
print(json.dumps(first_judgment, indent=2, ensure_ascii=False))

repair_prompt = first_judgment.get("repair_prompt")
if not repair_prompt:
    raise RuntimeError("No repair_prompt returned by Maestro.")

repaired_answer = call_ollama(repair_prompt, "repair answer")

print("\n=== Repaired Agent Answer ===")
print(repaired_answer)

second_judgment = govern(repaired_answer, repair_prompt, "second_judgment_after_repair")

print("\n=== Second Maestro Judgment ===")
print(json.dumps(second_judgment, indent=2, ensure_ascii=False))

print("\n=== Comparison Summary ===")
print("FIRST  rank:", first_judgment.get("rank"))
print("FIRST  reward:", first_judgment.get("reward"))
print("FIRST  policy:", first_judgment.get("policy"))
print("SECOND rank:", second_judgment.get("rank"))
print("SECOND reward:", second_judgment.get("reward"))
print("SECOND policy:", second_judgment.get("policy"))
'''

Path("run_ollama_maestro_repair_loop.py").write_text(code, encoding="utf-8")
print("WROTE run_ollama_maestro_repair_loop.py")
