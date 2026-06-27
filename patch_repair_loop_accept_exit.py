from pathlib import Path

p = Path("run_ollama_maestro_repair_loop.py")
s = p.read_text(encoding="utf-8")

old = '''repair_prompt = first_judgment.get("repair_prompt")
if not repair_prompt:
    raise RuntimeError("No repair_prompt returned by Maestro.")'''

new = '''repair_prompt = first_judgment.get("repair_prompt")
if not repair_prompt:
    print("\\n=== No Repair Needed ===")
    print("Maestro accepted the original answer.")
    print("FIRST rank:", first_judgment.get("rank"))
    print("FIRST reward:", first_judgment.get("reward"))
    print("FIRST policy:", first_judgment.get("policy"))
    raise SystemExit(0)'''

if old not in s:
    raise SystemExit("TARGET BLOCK NOT FOUND")

s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")

print("UPDATED no-repair accept handling")
