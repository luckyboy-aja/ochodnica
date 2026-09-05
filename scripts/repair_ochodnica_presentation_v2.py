from pathlib import Path
from bs4 import BeautifulSoup
from html import escape
from urllib.parse import unquote, urljoin, urlsplit
import re
import sys

OUT = Path("idsk-full-v4")
BASE = "/ochodnica"
SOURCE = "https://www.ochodnica.sk"
ASSETS = OUT / "assets" / "migrated"

NAV = [
    ("Domov", f"{BASE}/"),
    ("Obec", f"{BASE}/sk/o-obci/"),
    ("Samospráva", f"{BASE}/sk/samosprava/"),
    ("Aktuality", f"{BASE}/sk/kategoria/novinky-z-obce/"),
    ("Úradné oznamy", f"{BASE}/sk/kategoria/uradne-oznamy/"),
    ("Občan a podnikateľ", f"{BASE}/sk/obcan-a-podnikatel/"),
    ("Kontakt", f"{BASE}/sk/kontakt.html"),
]

SECTION_INDEXES = [
    ("sk/o-obci", "Obec", "Informácie o obci"),
    ("sk/samosprava", "Samospráva", "Informácie o samospráve"),
    ("sk/obcan-a-podnikatel", "Občan a podnikateľ", "Informácie pre občanov a podnikateľov"),
]


def page_files():
    files = []
    for p in OUT.rglob("*.html"):
        rel = p.relative_to(OUT).as_posix()
        # Captured HTML responses under assets/migrated are binary/source artifacts,
        # not generated IDSK pages. Never rewrite or validate their internal markup.
        if rel.startswith("assets/migrated/"):
            continue
        files.append(p)
    return files


def norm(text):
    return " ".join((text or "").split()).strip().casefold()


def sanitize_name(name):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:150] or "file"


def asset_index():
    by_suffix = {}
    if not ASSETS.exists():
        return by_suffix
    for p in ASSETS.rglob("*"):
        if not p.is_file():
            continue
        name = p.name
        # Stored crawler files are <12-char-sha>_<sanitized-original-name>.
        suffix = name[13:] if len(name) > 13 and name[12] == "_" else name
        by_suffix.setdefault(suffix, []).append(p)
    return by_suffix


ASSET_BY_SUFFIX = asset_index()
source_fallbacks = 0
reused_assets = 0
post_forms_repaired = 0


def localize(value):
    global source_fallbacks, reused_assets
    if not value or not isinstance(value, str):
        return value
    if value.startswith(("mailto:", "tel:", "javascript:", "data:", "blob:", "#")):
        return value
    if value.startswith(BASE + "/") or value == BASE:
        return value
    if value == "/":
        return BASE + "/"
    if value.startswith("//"):
        return value
    if not value.startswith("/"):
        return value

    parts = urlsplit(value)
    raw_path = unquote(parts.path)
    rel = raw_path.lstrip("/")
    target = OUT / rel

    # Existing generated page or original-path local file.
    if target.exists():
        return BASE + value
    if rel and not Path(rel).suffix and (target / "index.html").exists():
        return BASE + value

    # Reuse an already downloaded hashed migration asset by its original filename.
    original_name = Path(raw_path).name
    if original_name:
        sanitized = sanitize_name(original_name)
        matches = ASSET_BY_SUFFIX.get(sanitized, [])
        if len(matches) == 1:
            reused_assets += 1
            return BASE + "/" + matches[0].relative_to(OUT).as_posix()
        # Some source URLs had no extension while Content-Type added one on storage.
        loose = []
        for suffix, paths in ASSET_BY_SUFFIX.items():
            if suffix == sanitized or suffix.startswith(sanitized + "."):
                loose.extend(paths)
        if len(loose) == 1:
            reused_assets += 1
            return BASE + "/" + loose[0].relative_to(OUT).as_posix()

    # Do not invent a dead GitHub Pages path. Preserve the exact original public URL.
    source_fallbacks += 1
    return SOURCE + value


def source_page_url(path: Path) -> str:
    rel = path.relative_to(OUT).as_posix()
    if rel == "index.html":
        return SOURCE + "/"
    if rel.endswith("/index.html"):
        return SOURCE + "/" + rel[:-10]
    return SOURCE + "/" + rel


def repair_post_form(form, path: Path):
    """Keep source-side POST forms usable from static GitHub Pages.

    Relative/local POST actions would otherwise post to GitHub Pages and fail.
    Point them back to the equivalent endpoint on the original municipality site.
    """
    global post_forms_repaired
    method = (form.get("method") or "get").strip().lower()
    if method != "post":
        return False

    action = (form.get("action") or "").strip()
    if not action:
        form["action"] = source_page_url(path)
        post_forms_repaired += 1
        return True

    parts = urlsplit(action)
    if parts.scheme in ("http", "https") or action.startswith("//"):
        return False

    if action.startswith("/"):
        form["action"] = SOURCE + action
    else:
        form["action"] = urljoin(source_page_url(path), action)
    post_forms_repaired += 1
    return True


def contact_card(soup):
    card = soup.new_tag("div")
    card["class"] = ["static-contact"]
    strong = soup.new_tag("strong")
    strong.string = "Kontaktujte obec priamo"
    card.append(strong)
    p = soup.new_tag("p")
    p.string = "Kontaktný formulár z pôvodného webu nie je na statickej verzii aktívny."
    card.append(p)
    actions = soup.new_tag("p")
    mail = soup.new_tag("a", href="mailto:obec@ochodnica.sk")
    mail["class"] = ["btn", "btn-primary"]
    mail.string = "Napísať e-mail"
    actions.append(mail)
    actions.append(soup.new_string(" "))
    phone = soup.new_tag("a", href="tel:+421414233121")
    phone["class"] = ["btn"]
    phone.string = "041 / 423 31 21"
    actions.append(phone)
    card.append(actions)
    return card


def page_title(path):
    try:
        soup = BeautifulSoup(path.read_text("utf-8", errors="ignore"), "html.parser")
        h1 = soup.select_one("#main > .wrap > h1") or soup.find("h1")
        if h1 and h1.get_text(" ", strip=True):
            return h1.get_text(" ", strip=True)
        if soup.title and soup.title.string:
            return soup.title.string.split(" – ")[0].strip()
    except Exception:
        pass
    return path.stem.replace("-", " ").strip().capitalize()


def section_index_html(section_dir, title, intro):
    directory = OUT / section_dir
    links = []
    for child in sorted(directory.glob("*.html"), key=lambda p: page_title(p).casefold()):
        if child.name == "index.html":
            continue
        label = page_title(child)
        href = f"{BASE}/{child.relative_to(OUT).as_posix()}"
        links.append(f'<li><a href="{escape(href, quote=True)}">{escape(label)}</a></li>')

    nav_html = "".join(
        f'<a href="{escape(href, quote=True)}">{escape(label)}</a>'
        for label, href in NAV
    )
    items = "".join(links) or "<li>V tejto sekcii zatiaľ nie sú ďalšie položky.</li>"
    return f'''<!DOCTYPE html>
<html lang="sk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} – Obec Ochodnica</title><link rel="stylesheet" href="{BASE}/idsk.css"></head>
<body><a class="skip" href="#main">Preskočiť na obsah</a><div class="top"><div class="wrap">Verejná správa Slovenskej republiky</div></div>
<header class="head"><div class="wrap"><a class="brand" href="{BASE}/"><img alt="Erb obce Ochodnica" src="{BASE}/assets/migrated/images/1c5ac9f7c63c_logo.png"><span><strong>Obec Ochodnica</strong><small>webové sídlo obce</small></span></a></div></header>
<nav class="nav" aria-label="Hlavná navigácia"><div class="wrap">{nav_html}</div></nav>
<main id="main"><div class="wrap"><div class="crumb"><a href="{BASE}/">Domov</a> › {escape(title)}</div><span class="kicker">Obec Ochodnica</span><h1>{escape(title)}</h1><div class="content source-content"><div class="section-index"><p>{escape(intro)}. Vyberte si požadovanú položku:</p><ul class="section-links">{items}</ul></div></div></div></main>
<footer class="footer"><div class="wrap"><div class="footgrid"><div><strong>Obec Ochodnica</strong><span>Ochodnica 121, 023 35 Ochodnica</span><a href="mailto:obec@ochodnica.sk">obec@ochodnica.sk</a></div><div><strong>Technické riešenie a realizácia</strong><span>NESS Žilina</span></div></div><div class="footbottom">Obsah migrovaný z pôvodného verejného webového sídla obce Ochodnica.</div></div></footer></body></html>'''


if not OUT.exists():
    raise SystemExit(f"Missing generated output: {OUT}")

pages = duplicate_h1 = breadcrumbs = forms = 0

for path in page_files():
    soup = BeautifulSoup(path.read_text("utf-8", errors="ignore"), "html.parser")
    changed = False

    primary = soup.select_one("body > nav.nav .wrap")
    if primary is not None:
        primary.clear()
        for label, href in NAV:
            a = soup.new_tag("a", href=href)
            a.string = label
            primary.append(a)
        if primary.parent is not None:
            primary.parent["aria-label"] = "Hlavná navigácia"
        changed = True

    content = soup.select_one(".source-content")
    shell_h1 = soup.select_one("#main > .wrap > h1")
    if content is not None:
        for nested in list(content.find_all("main")):
            nested.unwrap()
            changed = True

        for ul in list(content.find_all("ul")):
            home = any(
                (use.get("xlink:href") or use.get("href")) == "#home"
                for use in ul.find_all("use")
            )
            classes = set(ul.get("class") or [])
            if home and ({"border-bottom", "d-none", "align-items-center"} & classes):
                ul.decompose()
                breadcrumbs += 1
                changed = True

        if shell_h1 is not None:
            wanted = norm(shell_h1.get_text(" ", strip=True))
            for h1 in list(content.find_all("h1")):
                if norm(h1.get_text(" ", strip=True)) == wanted:
                    h1.decompose()
                    duplicate_h1 += 1
                    changed = True

        rel_path = path.relative_to(OUT).as_posix()
        if rel_path == "sk/kontakt.html":
            for form in list(content.find_all("form")):
                form.replace_with(contact_card(soup))
                forms += 1
                changed = True
        else:
            for form in content.find_all("form"):
                if repair_post_form(form, path):
                    changed = True

    # Resolve only generated-page references. Never rewrite captured HTML assets.
    for tag in soup.find_all(True):
        for attr in ("href", "src", "action", "poster"):
            old = tag.get(attr)
            if old:
                new = localize(old)
                if new != old:
                    tag[attr] = new
                    changed = True
        srcset = tag.get("srcset")
        if srcset:
            rendered = []
            srcset_changed = False
            for part in srcset.split(","):
                bits = part.strip().split()
                if not bits:
                    continue
                new = localize(bits[0])
                srcset_changed |= new != bits[0]
                bits[0] = new
                rendered.append(" ".join(bits))
            if srcset_changed:
                tag["srcset"] = ", ".join(rendered)
                changed = True

    if changed:
        path.write_text(str(soup), encoding="utf-8")
        pages += 1

section_pages = 0
for section_dir, title, intro in SECTION_INDEXES:
    directory = OUT / section_dir
    if not directory.exists():
        continue
    (directory / "index.html").write_text(
        section_index_html(section_dir, title, intro), encoding="utf-8"
    )
    section_pages += 1

CSS = r'''
/* Ochodnica v6 presentation repair v2 */
.source-content{min-width:0}.source-content .container{width:100%;max-width:none;margin:0;padding:0}
.source-content .row{display:flex;flex-wrap:wrap;margin:-12px}.source-content [class*="col-"]{min-width:0;width:100%;padding:12px}
.source-content article,.source-content aside{min-width:0}.source-content h2{font-size:30px;line-height:1.2;margin:32px 0 16px}.source-content h3{font-size:22px;line-height:1.3;margin:24px 0 12px}
.source-content p{margin:0 0 16px}.source-content ul,.source-content ol{padding-left:24px}.source-content img,.source-content iframe{max-width:100%;height:auto}.source-content figure{max-width:100%;margin:20px 0}
.source-content .img-fluid,.source-content .img-responsive{display:block;max-width:100%;height:auto}.source-content .d-block{display:block}.source-content .d-inline-block{display:inline-block}.source-content .d-flex{display:flex}.source-content .align-items-center{align-items:center}
.source-content .btn{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:10px 16px;border:2px solid #005ea8;border-radius:3px;background:#fff;color:#005ea8;text-decoration:none;font-weight:700;line-height:1.2}.source-content .btn-primary{background:#005ea8;color:#fff}.source-content .btn-block{display:flex;width:100%}
.source-content table{width:100%;max-width:100%;border-collapse:collapse}.source-content th{background:#f3f5f7;text-align:left}.source-content .static-contact{margin:24px 0;padding:24px;border-left:5px solid #005ea8;background:#f3f5f7}.source-content .static-contact strong{display:block;font-size:22px;margin-bottom:8px}
.section-links{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;list-style:none;padding:0!important;margin:24px 0}.section-links li{margin:0}.section-links a{display:block;height:100%;padding:15px 17px;border:1px solid #d8dde3;border-left:4px solid #005ea8;background:#fff;text-decoration:none;font-weight:700}
@media(min-width:768px){.source-content .col-md-1{flex:0 0 8.333%;max-width:8.333%}.source-content .col-md-2{flex:0 0 16.667%;max-width:16.667%}.source-content .col-md-3{flex:0 0 25%;max-width:25%}.source-content .col-md-4{flex:0 0 33.333%;max-width:33.333%}.source-content .col-md-5{flex:0 0 41.667%;max-width:41.667%}.source-content .col-md-6{flex:0 0 50%;max-width:50%}.source-content .col-md-7{flex:0 0 58.333%;max-width:58.333%}.source-content .col-md-8{flex:0 0 66.667%;max-width:66.667%}.source-content .col-md-9{flex:0 0 75%;max-width:75%}.source-content .col-md-10{flex:0 0 83.333%;max-width:83.333%}.source-content .col-md-11{flex:0 0 91.667%;max-width:91.667%}.source-content .col-md-12{flex:0 0 100%;max-width:100%}.source-content .d-none.d-md-block{display:block}.source-content .d-none.d-md-flex{display:flex}}
@media(max-width:767px){.source-content .d-none{display:none}.source-content .row{margin:-8px}.source-content [class*="col-"]{padding:8px}.section-links{grid-template-columns:1fr}main{padding-top:28px}}
'''
css = OUT / "idsk.css"
current = css.read_text("utf-8", errors="ignore")
if "/* Ochodnica v6 presentation repair v2 */" not in current:
    css.write_text(current.rstrip() + "\n" + CSS.strip() + "\n", encoding="utf-8")

broken = []
for path in page_files():
    soup = BeautifulSoup(path.read_text("utf-8", errors="ignore"), "html.parser")
    for tag in soup.find_all(["a", "img", "source", "video", "audio", "link"]):
        value = tag.get("href") or tag.get("src")
        if not value or not value.startswith(BASE + "/"):
            continue
        rel = value[len(BASE) + 1:].split("#", 1)[0].split("?", 1)[0]
        target = OUT / rel
        if not rel:
            target = OUT / "index.html"
        elif value.split("?", 1)[0].endswith("/") or not Path(rel).suffix:
            target = target / "index.html"
        if not target.exists():
            broken.append((path.relative_to(OUT).as_posix(), value))

print(f"Presentation v2 repaired: pages={pages}, duplicate_h1={duplicate_h1}, breadcrumbs={breadcrumbs}, contact_forms={forms}, post_forms_repaired={post_forms_repaired}, section_indexes={section_pages}")
print(f"Reused migrated assets for old root-relative refs: {reused_assets}")
print(f"Preserved original source URL fallbacks: {source_fallbacks}")
print(f"Broken local references after presentation v2: {len(broken)}")
for row in broken[:100]:
    print("BROKEN", row[0], row[1])

if broken:
    sys.exit(2)
