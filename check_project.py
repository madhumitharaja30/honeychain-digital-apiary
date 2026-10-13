"""Quick local syntax/configuration checker for HoneyChain."""
from pathlib import Path
import ast

root = Path(__file__).resolve().parent
required = [root/'app.py', root/'requirements.txt', root/'templates/base.html', root/'static/style.css', root/'static/app.js']
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit('Missing required files:\n' + '\n'.join(missing))
ast.parse((root/'app.py').read_text(encoding='utf-8'))
for p in root.glob('templates/*.html'):
    text = p.read_text(encoding='utf-8')
    if text.count('{{') != text.count('}}'):
        raise SystemExit(f'Unbalanced template braces: {p.name}')
print('HoneyChain project structure and Python syntax: OK')
print('Run run.bat on Windows, or: python -m venv venv && pip install -r requirements.txt && python app.py')
