from pathlib import Path

files = [
    Path("processual_api/cgt_governor/types.py"),
    Path("processual_api/routers/cgt_governor.py"),
    Path("processual_api/middleware/subscription.py"),
    Path("processual_api/routers/settings.py"),
]

def fix_line(line: str) -> str:
    # Repair mojibake such as: â€” / âœ“ / â†’
    if "â" in line or "Ã" in line:
        try:
            line = line.encode("cp1252").decode("utf-8")
        except UnicodeError:
            line = line.encode("cp1252", errors="ignore").decode("utf-8", errors="ignore")

    # Convert remaining Unicode symbols to ASCII-safe text
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
        line = line.replace(old, new)

    return line

for path in files:
    text = path.read_text(encoding="utf-8")
    fixed = "".join(fix_line(line) for line in text.splitlines(keepends=True))
    path.write_text(fixed, encoding="utf-8")
    print(f"fixed: {path}")
