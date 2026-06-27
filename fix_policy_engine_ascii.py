from pathlib import Path

path = Path("processual_api/cgt_governor/policy/engine.py")

text = path.read_text(encoding="utf-8")

# Repair mojibake first if present
if "â" in text or "Ã" in text:
    try:
        text = text.encode("cp1252").decode("utf-8")
    except UnicodeError:
        text = text.encode("cp1252", errors="ignore").decode("utf-8", errors="ignore")

# ASCII-safe replacements
replacements = {
    "—": "-",
    "–": "-",
    "→": "->",
    "✓": "[OK]",
    "✅": "[OK]",
    "✕": "[X]",
    "✗": "[X]",
    "✦": "*",
    "⟳": "[REPAIR]",
    "△": "[WARN]",
    "↧": "[DOWN]",
    "─": "-",
}

for old, new in replacements.items():
    text = text.replace(old, new)

path.write_text(text, encoding="utf-8")
print(f"fixed: {path}")
