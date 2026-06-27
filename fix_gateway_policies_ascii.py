from pathlib import Path

path = Path("processual_api/cgt_governor/gateway/policies.py")

text = path.read_text(encoding="utf-8")

if "â" in text or "Ã" in text:
    try:
        text = text.encode("cp1252").decode("utf-8")
    except UnicodeError:
        text = text.encode("cp1252", errors="ignore").decode("utf-8", errors="ignore")

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
    "⚠": "[WARN]",
    "↧": "[DOWN]",
    "─": "-",
}

for old, new in replacements.items():
    text = text.replace(old, new)

path.write_text(text, encoding="utf-8")
print(f"fixed: {path}")
