"""Check relative Markdown file links without external dependencies."""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
errors = []
files = list(root.rglob("*.md"))
for path in files:
    if any(p in {".git", "node_modules", ".venv"} for p in path.relative_to(root).parts):
        continue
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
        if "://" in target or target.startswith(("#", "mailto:")):
            continue
        target = target.split("#", 1)[0]
        if target and not (path.parent / target).exists():
            errors.append(f"{path.relative_to(root)}: {target}")
if errors:
    print("\n".join(errors))
    sys.exit(1)
print("Relative Markdown links: OK")
