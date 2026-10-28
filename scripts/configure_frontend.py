"""Inject non-secret deployment metadata. API keys never belong in this file."""
import json
import os
from pathlib import Path

source = os.environ['SOURCE_URL']
if not source.startswith('https://github.com/'):
    raise SystemExit('Expected a public GitHub source URL.')
Path('web/config.js').write_text('window.INDEXLENS_CONFIG = ' + json.dumps({
    'apiBase': '', 'sourceUrl': source,
}) + ';\n')

