from pathlib import Path
from bs4 import BeautifulSoup
from collections import Counter
import csv
import re
import sys

OUT = Path("idsk-full-v4")
BASE = "/ochodnica"

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
aliases_checked = 0
counts = Counter()
repairs = Counter()


def fail(rel, code, detail=""):
    errors.append((rel, code, detail))


def rel_path(path: Path) -> str:
    return path.relative_to(OUT).as_posix()


def is_migrated_asset_html(path: Path) -> bool:
    return rel_path(path).startswith("assets/migrated/")


def alias_target(soup):
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


def normalize_static_content(soup, content):
    """Repair only markup that cannot work on static GitHub Pages or renders nothing.
    Keep all visible source text and fields intact.
    """
    changed = False

    # Preserve legacy form fields/text, but make POST forms inert on a static site.
    for form in content.find_all("form"):
        method = (form.get("method") or "get").lower()
        action = (form.get("action") or "").strip()
        if method == "post":
            if action:
                form["data-original-action"] = action
            form["data-original-method"] = method
            form.attrs.pop("action", None)
            form.attrs.pop("method", None)
            form["onsubmit"] = "return false"
            for button in form.find_all(["button", "input"]):
                kind = (button.get("type") or "").lower()
                if button.name == "button" or kind in ("submit", "image"):
                    button["disabled"] = "disabled"
            notice = soup.new_tag("p")
            notice["class"] = ["static-form-notice"]
            notice.string = "Formulár je v tejto statickej verzii iba informatívny a údaje neodosiela."
            form.insert_before(notice)
            repairs["post_forms_inert"] += 1
            changed = True

    # Source occasionally contains <a> only as formatting, without href.
    # Turn actual e-mail labels into mailto links; unwrap other empty anchors.
    for a in list(content.find_all("a")):
        href = (a.get("href") or "").strip()
        if href:
            continue
        label = " ".join(a.get_text(" ", strip=True).split())
        if not label:
            a.unwrap()
            repairs["empty_anchors_unwrapped"] += 1
            changed = True
            continue
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", label):
            a["href"] = "mailto:" + label
            repairs["email_links_repaired"] += 1
        else:
            a.unwrap()
            repairs["text_anchors_unwrapped"] += 1
        changed = True

    # An img without src and without alt text renders nothing. Remove only these
    # empty placeholders; a missing src with meaningful alt still remains a QC error.
    for img in list(content.find_all("img")):
        src = (img.get("src") or "").strip()
        alt = (img.get("alt") or "").strip()
        if not src and not alt:
            img.decompose()
            repairs["empty_images_removed"] += 1
            changed = True

    return changed


def inspect_page(path: Path, representative=False):
    global checked, aliases_checked
    checked += 1
    rel = rel_path(path)
    soup = BeautifulSoup(path.read_text("utf-8", errors="ignore"), "html.parser")

    redirect = alias_target(soup)
    if redirect:
        aliases_checked += 1
        if representative:
            fail(rel, "representative-page-is-redirect", redirect)
        if not local_target_exists(redirect):
            fail(rel, "redirect-target-missing", redirect)
        body_link = soup.find("a", href=True)
        if body_link is None or body_link.get("href") != redirect:
            fail(rel, "redirect-fallback-link-mismatch", redirect)
        return

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

    if normalize_static_content(soup, content):
        path.write_text(str(soup), encoding="utf-8")

    text = " ".join(content.get_text(" ", strip=True).split())
    meaningful = content.find(["p", "li", "article", "table", "img", "h2", "h3", "a"])

    if representative:
        if len(text) < 20 and content.find("img") is None:
            fail(rel, "representative-content-too-short", f"chars={len(text)}")
        if meaningful is None:
            fail(rel, "representative-content-empty")

    # Detect genuine error pages, but do not flag legitimate titles such as V404.
    low_title = title.casefold()
    standalone_404 = re.search(r"(?<![\w])404(?![\w])", low_title) is not None
    if standalone_404 or "stránka sa nenašla" in low_title or "page not found" in low_title:
        fail(rel, "source-error-page-migrated", title)

    for img in content.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src:
            fail(rel, "image-without-src", (img.get("alt") or "")[:120])
        elif src.startswith(BASE + "/") and not local_target_exists(src):
            fail(rel, "broken-local-image", src)

    for a in content.find_all("a"):
        href = (a.get("href") or "").strip()
        label = " ".join(a.get_text(" ", strip=True).split())
        if not href and label:
            fail(rel, "link-without-href", label[:120])
        if href.lower().startswith("javascript:"):
            fail(rel, "javascript-link-left", href[:160])
        if href.startswith(BASE + "/") and not local_target_exists(href):
            fail(rel, "broken-local-link", href)

    for form in content.find_all("form"):
        method = (form.get("method") or "get").lower()
        action = (form.get("action") or "").strip()
        if method == "post" or (action and action.startswith("/")):
            fail(rel, "server-form-left", f"method={method}; action={action}")


# Public HTML pages only. Downloaded HTML artefacts under assets/migrated are
# content files, not IDSK page shells, and are already covered by migration link validation.
html_pages = [p for p in OUT.rglob("*.html") if not is_migrated_asset_html(p)]
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

home = OUT / "index.html"
if home.exists():
    soup = BeautifulSoup(home.read_text("utf-8", errors="ignore"), "html.parser")
    hrefs = [a.get("href") or "" for a in soup.find_all("a")]
    if not any("/sk/novinky-z-obce/" in href for href in hrefs):
        fail("index.html", "homepage-missing-news-links")
    if not any("/sk/uradne-oznamy/" in href for href in hrefs):
        fail("index.html", "homepage-missing-official-notice-links")

with (OUT / "DEEP-QC-ERRORS.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["page", "code", "detail"])
    w.writerows(errors)

summary = [
    "Ochodnica – deep subpage QC",
    f"Public HTML pages inspected: {len(html_pages)}",
    f"Redirect aliases validated: {aliases_checked}",
    f"Representative pages re-inspected: {len(REPRESENTATIVE_PAGES)}",
    f"QC errors: {len(errors)}",
    f"Static POST forms made inert: {repairs['post_forms_inert']}",
    f"Email links repaired: {repairs['email_links_repaired']}",
    f"Formatting anchors unwrapped: {repairs['text_anchors_unwrapped'] + repairs['empty_anchors_unwrapped']}",
    f"Empty image placeholders removed: {repairs['empty_images_removed']}",
]
for name in SECTION_FLOORS:
    summary.append(f"Coverage {name}: {counts[name]}")
(OUT / "DEEP-QC-SUMMARY.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")

print("\n".join(summary))
for row in errors[:150]:
    print("DEEP_QC_ERROR", *row)

if errors:
    sys.exit(4)
