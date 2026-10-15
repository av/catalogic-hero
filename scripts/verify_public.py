"""Capture the public deliverables on a fresh GitHub-hosted browser outside Tailscale."""
import asyncio
import hashlib
import ipaddress
import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / 'proof'
BASE = 'https://av.github.io/catalogic-hero/'
HOST = 'av.github.io'
EXPECTED = {
    'hero': '37626c74cbb7a80fa78d4b0838334c5ddd4a8ed01efaf34a78a64e44c74e8737',
    'comparison': 'd87f75466d8a2cb0bc8a0c675865d359a1459390aaf4d33424a35fec78851938',
}


def network_evidence():
    assert os.environ.get('GITHUB_ACTIONS') == 'true', 'Run external proof on GitHub Actions'
    assert os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted', 'Require a standard GitHub-hosted runner'
    interfaces = json.loads(subprocess.check_output(['ip', '-j', 'addr'], text=True))
    routes = json.loads(subprocess.check_output(['ip', '-j', 'route', 'show', 'table', 'all'], text=True))
    names = [item['ifname'] for item in interfaces]
    assert not any(name.startswith(('tailscale', 'tun', 'wg')) for name in names), names
    assert not any('100.64.' in route.get('dst', '') for route in routes), 'Tailnet route found'
    addresses = sorted({item[4][0] for item in socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)})
    assert addresses and all(ipaddress.ip_address(address).is_global for address in addresses), addresses
    return {
        'observed': {
            'runner_environment': os.environ['RUNNER_ENVIRONMENT'],
            'runner_os': os.environ.get('RUNNER_OS'),
            'interfaces': names,
            'tailnet_interfaces': [],
            'tailnet_routes': [],
            'public_dns_addresses': addresses,
            'workflow_url': f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}",
        },
        'inferred': 'This standard GitHub-hosted runner is outside Ivan\'s tailnet: no Tailscale setup, interface, route or browser credentials are present.',
    }


async def image_check(page):
    await page.wait_for_function('''() => [...document.images].every(i=>i.complete && i.naturalWidth>0 && i.naturalHeight>0)''')
    return await page.locator('img').evaluate_all('''images=>images.map(i=>({alt:i.alt,width:i.naturalWidth,height:i.naturalHeight,inline:i.currentSrc.startsWith('data:')}))''')


async def main():
    PROOF.mkdir(exist_ok=True)
    report = {'started_utc': datetime.now(timezone.utc).isoformat(), 'network': network_evidence(), 'cases': []}
    (PROOF / 'public-verification.json').write_text(json.dumps(report, indent=2))
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        report['browser'] = browser.version
        for kind, path in [('hero', ''), ('comparison', 'catalogic-hero-compare.html')]:
            for device, width, height in [('desktop', 1440, 900), ('mobile', 390, 844)]:
                context = await browser.new_context(
                    viewport={'width': width, 'height': height},
                    device_scale_factor=1,
                    is_mobile=device == 'mobile', has_touch=device == 'mobile',
                    storage_state={'cookies': [], 'origins': []},
                    service_workers='block',
                )
                assert await context.cookies() == []
                requests, errors, failures, denied = [], [], [], []

                async def guard(route):
                    request = route.request
                    url = urlsplit(request.url)
                    headers = await request.all_headers()
                    item = {'url': request.url, 'method': request.method,
                            'authorization_present': 'authorization' in headers,
                            'cookie_present': 'cookie' in headers}
                    requests.append(item)
                    if url.scheme != 'https' or url.hostname != HOST or item['authorization_present'] or item['cookie_present']:
                        denied.append(item)
                        await route.abort()
                    else:
                        await route.continue_()

                await context.route('**/*', guard)
                page = await context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('requestfailed', lambda request: failures.append({'url': request.url, 'failure': request.failure}))
                response = await page.goto(BASE + path, wait_until='load', timeout=60000)
                assert response and response.status == 200
                assert hashlib.sha256(await response.body()).hexdigest() == EXPECTED[kind], 'Served file changed'
                server = await response.server_addr()
                assert server and ipaddress.ip_address(server['ipAddress']).is_global, server
                await page.evaluate('document.fonts.ready')
                await page.wait_for_timeout(2200)
                images = await image_check(page)
                fonts = await page.evaluate('''()=>[...document.fonts].map(f=>({family:f.family,status:f.status}))''')
                assert fonts and all(font['status'] == 'loaded' for font in fonts), fonts
                assert all(image['inline'] for image in images)
                dimensions = await page.evaluate('''()=>({viewportWidth:innerWidth,viewportHeight:innerHeight,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight})''')
                assert dimensions['viewportWidth'] == dimensions['scrollWidth'], dimensions
                if kind == 'hero':
                    assert ' '.join((await page.locator('h1').inner_text()).split()) == 'Recover before the restore finishes.'
                    assert await page.locator('.capabilities').evaluate('(e)=>e.getBoundingClientRect().bottom') <= height
                screenshot = f'{kind}-{device}.png'
                await page.screenshot(path=str(PROOF / screenshot))
                image_modes = []
                if kind == 'comparison':
                    for target, target_width, target_height in [('desktop', 1440, 900), ('mobile', 390, 844)]:
                        await page.locator(f'button[data-device="{target}"]').click()
                        for cookie in [False, True]:
                            await page.locator('#cookie').set_checked(cookie)
                            loaded = await image_check(page)
                            assert len(loaded) == 2 and all(image['width'] == target_width and image['height'] == target_height for image in loaded)
                            image_modes.append({'device': target, 'first_visit': cookie, 'images': loaded})
                    await page.locator('#cookie').uncheck()
                    assert await page.locator('#facts tbody tr').count() == 13
                assert not denied and not errors and not failures, {'denied': denied, 'errors': errors, 'failures': failures}
                assert requests == [{'url': BASE + path, 'method': 'GET', 'authorization_present': False, 'cookie_present': False}], requests
                assert await context.cookies() == []
                report['cases'].append({
                    'page': kind, 'device': device, 'url': BASE + path,
                    'status': response.status, 'observed': {
                        'fresh_logged_out_context': True, 'cookies_before_and_after': 0,
                        'server': server, 'dimensions': dimensions, 'fonts': fonts,
                        'images': images, 'all_comparison_image_modes': image_modes,
                        'requests': requests, 'private_host_requests': [],
                        'javascript_errors': errors, 'failed_requests': failures,
                        'screenshot': screenshot, 'original_file_hash_matches': True,
                    },
                })
                (PROOF / 'public-verification.json').write_text(json.dumps(report, indent=2))
                await context.close()
        # The comparison's primary link must resolve on this public host.
        context = await browser.new_context(storage_state={'cookies': [], 'origins': []})
        page = await context.new_page()
        await page.goto(BASE + 'catalogic-hero-compare.html')
        await page.get_by_role('link', name='Open the new hero', exact=False).click()
        await page.wait_for_url(BASE + 'catalogic-hero.html')
        await expect(page.locator('h1')).to_be_visible()
        report['comparison_link_observed'] = page.url
        await context.close()
        await browser.close()
    report['completed_utc'] = datetime.now(timezone.utc).isoformat()
    report['result'] = 'PASS'
    (PROOF / 'public-verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
