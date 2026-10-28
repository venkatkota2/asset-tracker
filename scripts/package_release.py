"""Package source and an offline demo without credentials, caches or raw data."""
from pathlib import Path
import json
import zipfile

root = Path(__file__).resolve().parents[1]
output = root.parent / 'indexlens.zip'
web = root / 'web'
report = json.loads((web / 'data/report.json').read_text())
if report['dataset']['kind'] != 'synthetic':
    raise SystemExit('Offline release packaging expects the explicit synthetic demonstration.')
html = (web / 'index.html').read_text()
html = html.replace('<link rel="stylesheet" href="./styles.css">',
                    '<style>' + (web / 'styles.css').read_text() + '</style>')
html = html.replace('<script defer src="./config.js"></script><script defer src="./app.js"></script>', '')
app = (web / 'app.js').read_text()
app = app.replace("const response=await fetch(base?`${base}/api/report`:'./data/report.json',{signal:AbortSignal.timeout(20000)});",
                  'const response={ok:true,json:async()=>window.INDEXLENS_DEMO};')
payload = json.dumps(report, separators=(',', ':'), allow_nan=False).replace('<','\\u003c')
scripts = '<script>' + (web/'config.js').read_text() + '\nwindow.INDEXLENS_DEMO=' + payload + ';\n' + app + '</script>'
html = html.replace('</body>', scripts + '</body>')
skip = {'.git', '.cache', '.pytest_cache', '__pycache__', '.venv', 'build', 'dist', '.openai'}
with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(p in skip or p.endswith('.egg-info') for p in rel.parts):
            continue
        if path.name.startswith('.env') and path.name != '.env.example':
            continue
        if 'data/raw' in rel.as_posix() or path.suffix in {'.pyc', '.tmp'}:
            continue
        archive.write(path, f'indexlens/{rel.as_posix()}')
    archive.writestr('indexlens/preview.html', html)
print(f'{output} ({output.stat().st_size:,} bytes)')

