from pathlib import Path
import subprocess
import sys

WORKFLOW = Path('.github/workflows/build-full-idsk-site-v4.yml')

src = WORKFLOW.read_text(encoding='utf-8')
lines = src.splitlines()
start = next(i for i, line in enumerate(lines) if "cat > /tmp/build_v4.py <<'PY'" in line)
body = []
for line in lines[start + 1:]:
    if line.strip() == 'PY':
        break
    body.append(line[10:] if line.startswith('          ') else line)
script = '\n'.join(body) + '\n'

marker = "\ncritical=OUT/'sk/uradne-oznamy/2026/oznamenie-o-akcii-29-30-08-2026.html'"
if marker not in script:
    raise SystemExit('Could not locate v4 validation marker')

repair = r'''
# v6 repair pass for the tiny set of links left unclassified after exhaustive crawl.
if broken:
    print('V6 first-pass broken references:', flush=True)
    for row in broken:
        print('  ', row, flush=True)

    reverse = {page_href(u): u for u in processed}
    first_pass_values = {row[1] for row in broken}

    # Re-fetch the source behind each broken local target when it can be mapped back.
    for _, v in list(broken):
        u = reverse.get(v)
        if not u and v.startswith('/ochodnica/') and 'page--q-' not in v:
            rel = v[len('/ochodnica/'):]
            u = canonical(ROOT + rel)
        if not u:
            continue
        k = asset_key(u)
        if k not in asset_map and u not in html_urls and u not in aliases:
            print(f'V6 repairing target from source: {u}', flush=True)
            process(u)

    # Classify links introduced by any repair-generated HTML page.
    for p in OUT.rglob('*.html'):
        soup = BeautifulSoup(p.read_text('utf-8', errors='ignore'), 'html.parser')
        changed = False
        for a in soup.select('a[data-original-internal]'):
            u = a.get('data-original-internal')
            k = asset_key(u)
            if k in asset_map:
                a['href'] = asset_map[k]
            elif u in html_urls or u in aliases:
                a['href'] = page_href(u)
            else:
                a['href'] = u
            del a['data-original-internal']
            changed = True
        if changed:
            p.write_text(str(soup), encoding='utf-8')

    # Resolve the originally broken targets to a local page/asset whenever possible.
    # If the original source itself is unavailable, preserve that original URL instead of a dead local URL.
    reverse = {page_href(u): u for u in processed}
    for p in OUT.rglob('*.html'):
        soup = BeautifulSoup(p.read_text('utf-8', errors='ignore'), 'html.parser')
        changed = False
        for tag in soup.find_all(['a', 'img', 'source', 'video', 'audio', 'link']):
            attr = 'href' if tag.get('href') is not None else 'src'
            v = tag.get(attr)
            if v not in first_pass_values:
                continue
            u = reverse.get(v)
            if not u and v.startswith('/ochodnica/') and 'page--q-' not in v:
                u = canonical(ROOT + v[len('/ochodnica/'):])
            replacement = None
            if u:
                k = asset_key(u)
                if k in asset_map:
                    replacement = asset_map[k]
                elif u in html_urls or u in aliases:
                    replacement = page_href(u)
                else:
                    replacement = u
            if replacement and replacement != v:
                tag[attr] = replacement
                changed = True
        if changed:
            p.write_text(str(soup), encoding='utf-8')

    # Re-run hard local-reference validation.
    broken = []
    for p in OUT.rglob('*.html'):
        soup = BeautifulSoup(p.read_text('utf-8', errors='ignore'), 'html.parser')
        for tag in soup.find_all(['a', 'img', 'source', 'video', 'audio', 'link']):
            v = tag.get('href') or tag.get('src')
            if not v or not v.startswith('/ochodnica/'):
                continue
            rel = v[len('/ochodnica/'):].split('#', 1)[0].split('?', 1)[0]
            target = OUT / rel
            if not rel:
                target = OUT / 'index.html'
            elif v.split('?', 1)[0].endswith('/') or not Path(rel).suffix:
                target = target / 'index.html'
            if not target.exists():
                broken.append([str(p.relative_to(OUT)), v])

    print(f'V6 broken references after repair: {len(broken)}', flush=True)
    for row in broken:
        print('  ', row, flush=True)
'''

script = script.replace(marker, '\n' + repair + marker, 1)
runner = Path('/tmp/build_v6.py')
runner.write_text(script, encoding='utf-8')

result = subprocess.run([sys.executable, str(runner)])
raise SystemExit(result.returncode)
