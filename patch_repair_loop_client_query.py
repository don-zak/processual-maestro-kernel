from pathlib import Path

p = Path("run_ollama_maestro_repair_loop.py")
s = p.read_text(encoding="utf-8")

old = '''payload = {
        "answer": answer,
        "context": {'''

new = '''payload = {
        "client_query": prompt,
        "answer": answer,
        "context": {'''

if old not in s:
    raise SystemExit("TARGET BLOCK NOT FOUND")

s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

print("UPDATED client_query in repair loop")
