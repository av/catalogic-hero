"""Ensure the public pages remain the exact original, self-contained deliverables."""
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    'catalogic-hero.html': '37626c74cbb7a80fa78d4b0838334c5ddd4a8ed01efaf34a78a64e44c74e8737',
    'catalogic-hero-compare.html': 'd87f75466d8a2cb0bc8a0c675865d359a1459390aaf4d33424a35fec78851938',
}
PRIVATE = re.compile(r'(?i)(fedora|tailscale|\.ts\.net|localhost|127\.0\.0\.1|100\.64\.|192\.168\.|https?://10\.)')
SECRETS = re.compile(r'(gh[pousr]_[A-Za-z0-9_]{15,}|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')

class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for name in ('src', 'srcset', 'poster'):
            if name in attrs:
                self.assets.append((tag, name, attrs[name]))
        if tag == 'link' and 'href' in attrs:
            self.assets.append((tag, 'href', attrs['href']))

results = []
for name, expected in EXPECTED.items():
    data = (ROOT / 'docs' / name).read_bytes()
    text = data.decode('utf-8')
    digest = hashlib.sha256(data).hexdigest()
    assert digest == expected, f'{name}: changed from original'
    assert not PRIVATE.search(text), f'{name}: private host marker'
    assert not SECRETS.search(text), f'{name}: credential-like value'
    assert not re.search(r'\b(?:fetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon\s*\(|@import\s)', text), f'{name}: external loading API'
    parsed = Assets()
    parsed.feed(text)
    assert all(value.startswith('data:') for _, _, value in parsed.assets), f'{name}: non-inline asset'
    css_urls = re.findall(r'url\(\s*[\'"]?([^\s)\'"]+)', text)
    assert all(url.startswith(('data:', '#')) for url in css_urls), f'{name}: remote CSS/SVG asset'
    results.append({'file': name, 'bytes': len(data), 'sha256': digest,
                    'unchanged': True, 'private_host_markers': 0,
                    'credential_markers': 0, 'external_asset_references': 0})
assert (ROOT / 'docs/index.html').read_bytes() == (ROOT / 'docs/catalogic-hero.html').read_bytes()
print(json.dumps({'pages': results, 'index_is_unchanged_hero_alias': True}, indent=2))
