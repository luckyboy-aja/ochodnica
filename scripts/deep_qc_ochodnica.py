from pathlib import Path
from bs4 import BeautifulSoup
from collections import Counter
import csv
import sys

OUT = Path("idsk-full-v4")
BASE = "/ochodnica"

# Explicit representative pages from every important area. These are checked in
# addition to the all-page structural QC performed by visual_qc_ochodnica.py.
REPRESENTATIVE_PAGES = [
    "index.html",
    "sk/o-obci/index.html",
    "sk/o-obci/historia.html",
    "sk/o-obci/poloha.html",
    "sk/o-obci/pre-turistov.html",
    "sk/o-obci/symboly-obce.html",
    "sk/samosprava/index.html",
    "sk/samosprava/obecne-zastupitelstvo.html",
    "sk/samosprava/obecny-urad.html",
    "sk/samosprava/stavebny-urad.html",
    "sk/samosprava/verejne-obstaravanie.html",
    "sk/obcan-a-podnikatel/index.html",
    "sk/obcan-a-podnikatel/cintorin.html",
    "sk/obcan-a-podnikatel/materska-skola.html",
    "sk/obcan-a-podnikatel/kulturny-dom.html",
    "sk/obcan-a-podnikatel/farnost.html",
    "sk/kategoria/novinky-z-obce/index.html",
    "sk/kategoria/uradne-oznamy/index.html",
    "sk/novinky-z-obce/2026/zmeny-v-overovani-podpisov-a-listin-platne-od-01-09-2026.html",
    "sk/novinky-z-obce/2026/odstavka-vody-dna-27-08-2026.html",
    "sk/uradne-oznamy/2026/oznamenie-o-akcii-29-30-08-2026.html",
]

# Coverage floors. They make the build fail if a whole content area silently
# disappears even when individual links happen to stay syntactically valid.
SECTION_FLOORS = {
    "o-obci": ("sk/o-obci/*.html", 10),
    "samosprava": ("sk/samosprava/*.html", 10),
    "obcan-a-podnikatel": ("sk/obcan-a-podnikatel/*.html", 10),
    "novinky-z-obce": ("sk/novinky-z-obce/**/*.html", 20),
    "uradne-oznamy": ("sk/uradne-oznamy/**/*.html", 20),
    "kategorie": ("sk/kategoria/**/index.html", 2),
}

if not OUT.exists():
    raise SystemExit(f"Missing generated output: {OUT}")

errors = []
checked = 0
counts = Counter()


def fail(rel, code, detail=""):
    errors.append((rel, code, detail))


def inspect_page(path: Path, representative=False):
    global checked
    checked += 1
    rel = path.relative_to(OUT).as_posix()
    soup = BeautifulSoup(path.read_text("utf-8", errors="ignore"), "html.parser")

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    h1 = soup.find("h1")
    h1_text = h1.get_text(" ", strip=True) if h1 else ""
    content = soup.select_one(".source-content")

    if not title:
        fail(rel, "missing-title")
    if not h1_text:
        fail(rel, "missing-or-empty-h1")
    if content is None:
        fail(rel, "missing-source-content")
        return

    text = " ".join(content.get_text(" ", strip=True).split())
    meaningful = content.find(["p", "li", "article", "table", "img", "h2", "h3", "a"])

    # Representative pages must contain a meaningful body, not just the shell.
    if representative:
        if len(text) < 20 and content.find("img") is None:
            fail(rel, "representative-content-too-short", f"chars={len(text)}")
        if meaningful is None:
            fail(rel, "representative-content-empty")

    # Catch source error pages accidentally migrated as content.
    low_title = title.casefold()
    if "404" in low_title or "stránka sa nenašla" in low_title or "page not found" in low_title:
        fail(rel, "source-error-page-migrated", title)

    # Links/images that are visibly empty or unusable.
    for img in content.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src:
            fail(rel, "image-without-src")

    for a in content.find_all("a"):
        href = (a.get("href") or "").strip()
        label = " ".join(a.get_text(" ", strip=True).split())
        if not href and label:
            fail(rel, "link-without-href", label[:120])
        if href.lower().startswith("javascript:"):
            fail(rel, "javascript-link-left", href[:160])

    # No old server-side form may survive anywhere on the static site.
    for form in content.find_all("form"):
        method = (form.get("method") or "get").lower()
        action = (form.get("action") or "").strip()
        if method == "post" or (action and action.startswith("/")):
            fail(rel, "server-form-left", f"method={method}; action={action}")


html_pages = list(OUT.rglob("*.html"))
for page in html_pages:
    inspect_page(page, representative=False)

for rel in REPRESENTATIVE_PAGES:
    page = OUT / rel
    if not page.exists():
        fail(rel, "representative-page-missing")
        continue
    inspect_page(page, representative=True)

for name, (pattern, minimum) in SECTION_FLOORS.items():
    matches = list(OUT.glob(pattern))
    counts[name] = len(matches)
    if len(matches) < minimum:
        fail(pattern, "section-coverage-below-floor", f"found={len(matches)} minimum={minimum}")

# Check that the homepage exposes both news and official-notice content, because
# these are the two most visible dynamic sections after migration.
home = OUT / "index.html"
if home.exists():
    soup = BeautifulSoup(home.read_text("utf-8", errors="ignore"), "html.parser")
    hrefs = [a.get("href") or "" for a in soup.find_all("a")]
    if not any("/sk/novinky-z-obce/" in href for href in hrefs):
        fail("index.html", "homepage-missing-news-links")
    if not any("/sk/uradne-oznamy/" in href for href in hrefs):
        fail("index.html", "homepage-missing-official-notice-links")

# Persist diagnostics so we can inspect exactly which page failed without
# relying only on a truncated Actions console log.
with (OUT / "DEEP-QC-ERRORS.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["page", "code", "detail"])
    w.writerows(errors)

summary = [
    "Ochodnica – deep subpage QC",
    f"All HTML pages inspected: {len(html_pages)}",
    f"Representative pages re-inspected: {len(REPRESENTATIVE_PAGES)}",
    f"QC errors: {len(errors)}",
]
for name in SECTION_FLOORS:
    summary.append(f"Coverage {name}: {counts[name]}")
(OUT / "DEEP-QC-SUMMARY.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")

print("\n".join(summary))
for row in errors[:150]:
    print("DEEP_QC_ERROR", *row)

if errors:
    sys.exit(4)
