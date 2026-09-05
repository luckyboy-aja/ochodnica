from pathlib import Path
from bs4 import BeautifulSoup
import re
import sys

OUT = Path("idsk-full-v4")
BASE = "/ochodnica"
EXPECTED_NAV = [
    ("Domov", f"{BASE}/"),
    ("Obec", f"{BASE}/sk/o-obci/"),
    ("Samospráva", f"{BASE}/sk/samosprava/"),
    ("Aktuality", f"{BASE}/sk/kategoria/novinky-z-obce/"),
    ("Úradné oznamy", f"{BASE}/sk/kategoria/uradne-oznamy/"),
    ("Občan a podnikateľ", f"{BASE}/sk/obcan-a-podnikatel/"),
    ("Kontakt", f"{BASE}/sk/kontakt.html"),
]

if not OUT.exists():
    raise SystemExit(f"Missing generated output: {OUT}")


def rel_path(path: Path) -> str:
    return path.relative_to(OUT).as_posix()


def is_migrated_asset_html(path: Path) -> bool:
    rel = rel_path(path)
    return rel.startswith("assets/migrated/")


def alias_target(soup):
    """Return the target of a crawler-generated redirect alias, otherwise None."""
    refresh = soup.find("meta", attrs={"http-equiv": lambda v: v and str(v).casefold() == "refresh"})
    canonical = soup.find("link", rel=lambda v: v and "canonical" in ([v] if isinstance(v, str) else v))
    refresh_target = None
    if refresh:
        content = refresh.get("content") or ""
        m = re.search(r"url\s*=\s*(.+)$", content, flags=re.I)
        if m:
            refresh_target = m.group(1).strip().strip("'\"")
    canonical_target = (canonical.get("href") or "").strip() if canonical else None
    if refresh_target and canonical_target and refresh_target == canonical_target:
        return refresh_target
    return None


def local_target_exists(value: str) -> bool:
    if not value.startswith(BASE + "/") and value != BASE:
        return True
    clean = value.split("#", 1)[0].split("?", 1)[0]
    rel_target = clean[len(BASE):].lstrip("/")
    target = OUT / rel_target
    if not rel_target:
        target = OUT / "index.html"
    elif clean.endswith("/") or not Path(rel_target).suffix:
        target = target / "index.html"
    return target.exists()


changed_pages = 0
converted_h1 = 0
removed_dead_icons = 0

# Only presentation pages are modified. HTML files under assets/migrated are
# downloaded source artefacts, not public IDSK page shells.
for path in OUT.rglob("*.html"):
    if is_migrated_asset_html(path):
        continue
    soup = BeautifulSoup(path.read_text("utf-8", errors="ignore"), "html.parser")
    if alias_target(soup):
        continue
    changed = False

    top = soup.select_one("body > .top .wrap")
    if top is not None and top.get_text(" ", strip=True) != "Verejná správa Slovenskej republiky":
        top.clear()
        top.append("Verejná správa Slovenskej republiky")
        changed = True

    content = soup.select_one(".source-content")
    if content is not None:
        for h1 in list(content.find_all("h1")):
            h1.name = "h2"
            converted_h1 += 1
            changed = True

        available_ids = {tag.get("id") for tag in soup.find_all(id=True)}
        for svg in list(content.find_all("svg")):
            use = svg.find("use")
            if use is None:
                continue
            ref = use.get("href") or use.get("xlink:href")
            if ref and ref.startswith("#") and ref[1:] not in available_ids:
                svg.decompose()
                removed_dead_icons += 1
                changed = True

    if changed:
        path.write_text(str(soup), encoding="utf-8")
        changed_pages += 1

CSS_PATCH = r"""
/* Ochodnica visual QC patch */
.footgrid strong,.footgrid span,.footgrid a{display:block}.footgrid strong{margin-bottom:6px}.footgrid a{margin-top:4px}
.source-content .text-center{text-align:center}.source-content .position-relative{position:relative}.source-content .position-static{position:static}
.source-content .pt-1{padding-top:6px}.source-content .pb-3{padding-bottom:16px}.source-content .mb-0{margin-bottom:0}.source-content .mb-5{margin-bottom:32px}
.source-content .no-gutters{margin:0}.source-content .no-gutters>[class*="col-"]{padding-left:0;padding-right:0}
.source-content .fa{display:none}.source-content .stretched-link{position:relative;z-index:1}
@media(min-width:768px){
.source-content .col-md-1{flex:0 0 8.333%;max-width:8.333%}.source-content .col-md-2{flex:0 0 16.667%;max-width:16.667%}.source-content .col-md-3{flex:0 0 25%;max-width:25%}.source-content .col-md-4{flex:0 0 33.333%;max-width:33.333%}.source-content .col-md-5{flex:0 0 41.667%;max-width:41.667%}.source-content .col-md-6{flex:0 0 50%;max-width:50%}.source-content .col-md-7{flex:0 0 58.333%;max-width:58.333%}.source-content .col-md-8{flex:0 0 66.667%;max-width:66.667%}.source-content .col-md-9{flex:0 0 75%;max-width:75%}.source-content .col-md-10{flex:0 0 83.333%;max-width:83.333%}.source-content .col-md-11{flex:0 0 91.667%;max-width:91.667%}.source-content .col-md-12{flex:0 0 100%;max-width:100%}
.source-content .d-none.d-md-block{display:block}.source-content .d-none.d-md-flex{display:flex}.source-content .text-md-right{text-align:right}.source-content .align-items-md-center{align-items:center}.source-content .mb-md-0{margin-bottom:0}.source-content .mb-md-2{margin-bottom:8px}.source-content .mb-md-3{margin-bottom:16px}
}
@media(min-width:992px){
.source-content .col-lg-1{flex:0 0 8.333%;max-width:8.333%}.source-content .col-lg-2{flex:0 0 16.667%;max-width:16.667%}.source-content .col-lg-3{flex:0 0 25%;max-width:25%}.source-content .col-lg-4{flex:0 0 33.333%;max-width:33.333%}.source-content .col-lg-5{flex:0 0 41.667%;max-width:41.667%}.source-content .col-lg-6{flex:0 0 50%;max-width:50%}.source-content .col-lg-7{flex:0 0 58.333%;max-width:58.333%}.source-content .col-lg-8{flex:0 0 66.667%;max-width:66.667%}.source-content .col-lg-9{flex:0 0 75%;max-width:75%}.source-content .col-lg-10{flex:0 0 83.333%;max-width:83.333%}.source-content .col-lg-11{flex:0 0 91.667%;max-width:91.667%}.source-content .col-lg-12{flex:0 0 100%;max-width:100%}
}
@media(min-width:1200px){
.source-content .col-xl-1{flex:0 0 8.333%;max-width:8.333%}.source-content .col-xl-2{flex:0 0 16.667%;max-width:16.667%}.source-content .col-xl-3{flex:0 0 25%;max-width:25%}.source-content .col-xl-4{flex:0 0 33.333%;max-width:33.333%}.source-content .col-xl-5{flex:0 0 41.667%;max-width:41.667%}.source-content .col-xl-6{flex:0 0 50%;max-width:50%}.source-content .col-xl-7{flex:0 0 58.333%;max-width:58.333%}.source-content .col-xl-8{flex:0 0 66.667%;max-width:66.667%}.source-content .col-xl-9{flex:0 0 75%;max-width:75%}.source-content .col-xl-10{flex:0 0 83.333%;max-width:83.333%}.source-content .col-xl-11{flex:0 0 91.667%;max-width:91.667%}.source-content .col-xl-12{flex:0 0 100%;max-width:100%}
}
"""
css = OUT / "idsk.css"
current = css.read_text("utf-8", errors="ignore")
if "/* Ochodnica visual QC patch */" not in current:
    css.write_text(current.rstrip() + "\n" + CSS_PATCH.strip() + "\n", encoding="utf-8")

errors = []
html_pages = [p for p in OUT.rglob("*.html") if not is_migrated_asset_html(p)]
aliases_checked = 0
shell_pages_checked = 0

for path in html_pages:
    soup = BeautifulSoup(path.read_text("utf-8", errors="ignore"), "html.parser")
    rel = rel_path(path)
    redirect = alias_target(soup)

    # Redirect aliases are intentionally tiny HTML documents, so shell checks do
    # not apply. They are accepted only if both refresh and canonical agree and
    # the local destination really exists.
    if redirect:
        aliases_checked += 1
        if not local_target_exists(redirect):
            errors.append((rel, f"redirect-target-missing={redirect}"))
        body_link = soup.find("a", href=True)
        if body_link is None or body_link.get("href") != redirect:
            errors.append((rel, "redirect-fallback-link-mismatch"))
        continue

    shell_pages_checked += 1
    mains = soup.find_all("main")
    if len(mains) != 1:
        errors.append((rel, f"main-count={len(mains)}"))
    h1s = soup.find_all("h1")
    if len(h1s) != 1:
        errors.append((rel, f"h1-count={len(h1s)}"))

    nav = soup.select_one("body > nav.nav .wrap")
    if nav is None:
        errors.append((rel, "missing-primary-nav"))
    else:
        actual = [(a.get_text(" ", strip=True), a.get("href")) for a in nav.find_all("a", recursive=False)]
        if actual != EXPECTED_NAV:
            errors.append((rel, f"bad-primary-nav={actual!r}"))
        if any(label.isdigit() for label, _ in actual):
            errors.append((rel, "pagination-leaked-into-primary-nav"))

    top = soup.select_one("body > .top .wrap")
    if top is None or top.get_text(" ", strip=True) != "Verejná správa Slovenskej republiky":
        errors.append((rel, "bad-top-strip"))

    if "NESS Žilina" not in soup.get_text(" ", strip=True):
        errors.append((rel, "missing-NESS-footer-branding"))

    if rel == "sk/kontakt.html" and soup.select_one(".source-content form") is not None:
        errors.append((rel, "server-form-left-on-static-site"))

    for tag in soup.find_all(["a", "img", "source", "video", "audio", "link"]):
        value = tag.get("href") or tag.get("src")
        if not value or not value.startswith(BASE + "/"):
            continue
        if not local_target_exists(value):
            errors.append((rel, f"broken-local={value}"))

for required in [
    OUT / "index.html",
    OUT / "sk/o-obci/index.html",
    OUT / "sk/samosprava/index.html",
    OUT / "sk/obcan-a-podnikatel/index.html",
    OUT / "sk/kategoria/uradne-oznamy/index.html",
    OUT / "sk/kontakt.html",
    OUT / "sk/uradne-oznamy/2026/oznamenie-o-akcii-29-30-08-2026.html",
]:
    if not required.exists():
        errors.append((str(required), "required-page-missing"))

print(f"Visual QC: user_html={len(html_pages)}, shell_pages={shell_pages_checked}, redirect_aliases={aliases_checked}, changed={changed_pages}, converted_inner_h1={converted_h1}, removed_dead_icons={removed_dead_icons}")
print(f"Visual/structural QC errors: {len(errors)}")
for row in errors[:100]:
    print("QC_ERROR", row[0], row[1])

if errors:
    sys.exit(3)
