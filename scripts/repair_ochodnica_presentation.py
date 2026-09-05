from pathlib import Path
from bs4 import BeautifulSoup
import sys

OUT = Path("idsk-full-v4")
BASE = "/ochodnica"

NAV = [
    ("Domov", f"{BASE}/"),
    ("Obec", f"{BASE}/sk/o-obci/"),
    ("Samospráva", f"{BASE}/sk/samosprava/"),
    ("Aktuality", f"{BASE}/sk/kategoria/novinky-z-obce/"),
    ("Úradné oznamy", f"{BASE}/sk/kategoria/uradne-oznamy/"),
    ("Občan a podnikateľ", f"{BASE}/sk/obcan-a-podnikatel/"),
    ("Kontakt", f"{BASE}/sk/kontakt.html"),
]

def norm(text):
    return " ".join((text or "").split()).strip().casefold()

def localize(value):
    if not value or not isinstance(value, str):
        return value
    if value.startswith(BASE + "/") or value == BASE:
        return value
    if value == "/":
        return BASE + "/"
    if value.startswith("//"):
        return value
    if value.startswith("/"):
        return BASE + value
    return value

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

if not OUT.exists():
    raise SystemExit(f"Missing generated output: {OUT}")

pages = duplicate_h1 = breadcrumbs = forms = 0

for path in OUT.rglob("*.html"):
    soup = BeautifulSoup(path.read_text("utf-8", errors="ignore"), "html.parser")
    changed = False

    # Fixed primary navigation: never derive it from article pagination.
    primary = soup.select_one("body > nav.nav .wrap")
    if primary is not None:
        primary.clear()
        for label, href in NAV:
            a = soup.new_tag("a", href=href)
            a.string = label
            primary.append(a)
        changed = True

    content = soup.select_one(".source-content")
    shell_h1 = soup.select_one("#main > .wrap > h1")
    if content is not None:
        # Avoid nested <main>, which is invalid and caused inconsistent layout.
        for nested in list(content.find_all("main")):
            nested.unwrap()
            changed = True

        # Remove copied source breadcrumb only when it contains the original #home SVG.
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

        # Keep one H1: shell heading wins; distinct inner section headings remain.
        if shell_h1 is not None:
            wanted = norm(shell_h1.get_text(" ", strip=True))
            for h1 in list(content.find_all("h1")):
                if norm(h1.get_text(" ", strip=True)) == wanted:
                    h1.decompose()
                    duplicate_h1 += 1
                    changed = True

        # The original server-side contact POST cannot work on GitHub Pages.
        if path.relative_to(OUT).as_posix() == "sk/kontakt.html":
            for form in list(content.find_all("form")):
                form.replace_with(contact_card(soup))
                forms += 1
                changed = True

    # Repair root-relative links missed by the crawler.
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

CSS = r"""
/* Ochodnica v6 presentation repair */
.source-content{min-width:0}
.source-content .container{width:100%;max-width:none;margin:0;padding:0}
.source-content .row{display:flex;flex-wrap:wrap;margin:-12px}
.source-content [class*="col-"]{min-width:0;width:100%;padding:12px}
.source-content article,.source-content aside{min-width:0}
.source-content h2{font-size:30px;line-height:1.2;margin:32px 0 16px}
.source-content h3{font-size:22px;line-height:1.3;margin:24px 0 12px}
.source-content p{margin:0 0 16px}
.source-content ul,.source-content ol{padding-left:24px}
.source-content img,.source-content iframe{max-width:100%;height:auto}
.source-content figure{max-width:100%;margin:20px 0}
.source-content .img-fluid,.source-content .img-responsive{display:block;max-width:100%;height:auto}
.source-content .rounded{border-radius:8px}
.source-content .bg-white{background:#fff}
.source-content .bg-tertiary{background:#004d99}
.source-content .bg-secondary{background:#245b79}
.source-content .text-white{color:#fff!important}
.source-content .text-gray{color:#d8e1e8!important}
.source-content .text-uppercase{text-transform:uppercase}
.source-content .font-weight-bold{font-weight:700}
.source-content .font-weight-normal{font-weight:400}
.source-content .font-size-bigger{font-size:1.08em}
.source-content .d-block{display:block}
.source-content .d-inline-block{display:inline-block}
.source-content .d-flex{display:flex}
.source-content .align-items-center{align-items:center}
.source-content .m-auto{margin:auto}
.source-content .mb{margin-bottom:16px}
.source-content .mb-2{margin-bottom:8px}.source-content .mb-3{margin-bottom:16px}.source-content .mb-4{margin-bottom:24px}
.source-content .mt-3{margin-top:16px}.source-content .mt-4{margin-top:24px}.source-content .mt-5{margin-top:32px}
.source-content .mr-2{margin-right:8px}.source-content .mr-3{margin-right:16px}.source-content .ml-2{margin-left:8px}
.source-content .p-2{padding:12px}.source-content .p-3{padding:16px}.source-content .p-5{padding:32px}
.source-content .pl-3{padding-left:16px}.source-content .pr-3{padding-right:16px}
.source-content .pt-2{padding-top:12px}.source-content .pb-2{padding-bottom:12px}
.source-content .pt-5{padding-top:32px}.source-content .pb-5{padding-bottom:32px}
.source-content .border-bottom{border-bottom:1px solid #d8dde3}
.source-content .shadow{box-shadow:0 2px 12px rgba(0,0,0,.12)}
.source-content .btn{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:10px 16px;border:2px solid #005ea8;border-radius:3px;background:#fff;color:#005ea8;text-decoration:none;font-weight:700;line-height:1.2}
.source-content .btn:hover{background:#eef6fb}.source-content .btn-primary{background:#005ea8;color:#fff}.source-content .btn-primary:hover{background:#00477f}
.source-content .btn-block{display:flex;width:100%}
.source-content input,.source-content textarea,.source-content select{width:100%;max-width:100%;padding:10px 12px;border:2px solid #707b86;border-radius:2px;font:inherit}
.source-content label{display:block;margin:0 0 6px;font-weight:700}.source-content .form-group{margin-bottom:18px}
.source-content table{width:100%;max-width:100%;border-collapse:collapse}.source-content th{background:#f3f5f7;text-align:left}
.source-content .article-list-item{padding-bottom:12px;border-bottom:1px solid rgba(255,255,255,.28)}
.source-content .article-list-title{margin-top:0}.source-content .bg-tertiary a,.source-content .bg-secondary a{color:#fff}
.source-content .static-contact{margin:24px 0;padding:24px;border-left:5px solid #005ea8;background:#f3f5f7}
.source-content .static-contact strong{display:block;font-size:22px;margin-bottom:8px}
@media(min-width:768px){
.source-content .col-md-3{flex:0 0 25%;max-width:25%}.source-content .col-md-4{flex:0 0 33.333%;max-width:33.333%}
.source-content .col-md-6{flex:0 0 50%;max-width:50%}.source-content .col-md-8{flex:0 0 66.667%;max-width:66.667%}
.source-content .col-md-9{flex:0 0 75%;max-width:75%}.source-content .col-md-12{flex:0 0 100%;max-width:100%}
.source-content .p-md-5{padding:32px}.source-content .pl-md-5{padding-left:32px}.source-content .pr-md-5{padding-right:32px}
.source-content .pt-md-3{padding-top:16px}.source-content .pb-md-3{padding-bottom:16px}.source-content .d-none.d-md-flex{display:flex}}
@media(min-width:1100px){
.source-content .col-xl-4{flex:0 0 33.333%;max-width:33.333%}.source-content .col-xl-8{flex:0 0 66.667%;max-width:66.667%}
.source-content .mt-xl-0{margin-top:0}.source-content .p-lg-2{padding:12px}.source-content .p-lg-5{padding:32px}}
@media(max-width:767px){.source-content .d-none{display:none}.source-content .row{margin:-8px}.source-content [class*="col-"]{padding:8px}main{padding-top:28px}}
"""
css = OUT / "idsk.css"
current = css.read_text("utf-8", errors="ignore")
if "/* Ochodnica v6 presentation repair */" not in current:
    css.write_text(current.rstrip() + "\n" + CSS.strip() + "\n", encoding="utf-8")

# Hard local-reference validation after the presentation rewrite.
broken = []
for path in OUT.rglob("*.html"):
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

print(f"Presentation repaired: pages={pages}, duplicate_h1={duplicate_h1}, breadcrumbs={breadcrumbs}, contact_forms={forms}")
print(f"Broken local references after presentation repair: {len(broken)}")
for row in broken[:50]:
    print("BROKEN", row[0], row[1])

if broken:
    sys.exit(2)
