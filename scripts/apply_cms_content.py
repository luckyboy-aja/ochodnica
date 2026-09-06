from __future__ import annotations

from pathlib import Path, PurePosixPath
from datetime import date, datetime
from bs4 import BeautifulSoup
from html import escape
import markdown
import os
import re
import shutil
import sys
import unicodedata
import yaml

BASE = "/ochodnica"
REPO = Path(".")
SITE = Path(os.environ.get("SITE_ROOT", "."))
CONTENT = REPO / "cms-content"
ADMIN = REPO / "admin"
CMS_MEDIA = REPO / "assets" / "cms"

NAV = [
    ("Domov", f"{BASE}/"),
    ("Obec", f"{BASE}/sk/o-obci/"),
    ("Samospráva", f"{BASE}/sk/samosprava/"),
    ("Aktuality", f"{BASE}/sk/kategoria/novinky-z-obce/"),
    ("Úradné oznamy", f"{BASE}/sk/kategoria/uradne-oznamy/"),
    ("Občan a podnikateľ", f"{BASE}/sk/obcan-a-podnikatel/"),
    ("Kontakt", f"{BASE}/sk/kontakt.html"),
]

ERRORS: list[str] = []
GENERATED: list[Path] = []
OVERRIDDEN: list[Path] = []


def err(message: str) -> None:
    ERRORS.append(message)


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:120] or "clanok"


def as_bool(value, default=True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() not in {"0", "false", "no", "nie", "off"}


def parse_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return date.today()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Neplatný dátum: {text}")


def read_frontmatter(path: Path) -> dict:
    text = path.read_text("utf-8", errors="strict").replace("\r\n", "\n")
    data = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end < 0:
            raise ValueError("chýba ukončenie YAML front matter")
        raw = text[4:end]
        data = yaml.safe_load(raw) or {}
        body = text[end + 4 :].lstrip("\n")
    if not isinstance(data, dict):
        raise ValueError("front matter musí byť objekt")
    data["_body"] = body
    data["_file"] = path
    return data


def clean_html(raw: str) -> str:
    html = markdown.markdown(raw or "", extensions=["extra", "sane_lists"], output_format="html5")
    soup = BeautifulSoup(html, "html.parser")
    for bad in soup.find_all(["script", "object", "embed"]):
        bad.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.casefold().startswith("on"):
                del tag.attrs[attr]
        for attr in ("href", "src"):
            value = tag.get(attr)
            if isinstance(value, str) and value.strip().casefold().startswith("javascript:"):
                del tag.attrs[attr]
    return str(soup)


def public_media(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "mailto:", "tel:")):
        return value
    if value.startswith(BASE + "/"):
        return value
    value = value.lstrip("/")
    if value.startswith("assets/cms/"):
        return f"{BASE}/{value}"
    return value


def attachments_html(items) -> str:
    if not items:
        return ""
    links = []
    for item in items:
        if isinstance(item, str):
            label, file_value = Path(item).name, item
        elif isinstance(item, dict):
            file_value = item.get("file") or ""
            label = item.get("label") or Path(str(file_value)).name
        else:
            continue
        href = public_media(str(file_value))
        if href:
            links.append(f'<li><a href="{escape(href, quote=True)}">{escape(str(label))}</a></li>')
    if not links:
        return ""
    return '<section class="cms-attachments"><h2>Prílohy</h2><ul>' + "".join(links) + "</ul></section>"


def shell(title: str, category: str, d: date, body_html: str, perex: str = "") -> str:
    nav = "".join(f'<a href="{escape(href, quote=True)}">{escape(label)}</a>' for label, href in NAV)
    lead = f'<p class="cms-perex"><strong>{escape(perex)}</strong></p>' if perex else ""
    return f'''<!doctype html>
<html lang="sk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} – Obec Ochodnica</title><link rel="stylesheet" href="{BASE}/idsk.css"></head>
<body><a class="skip" href="#main">Preskočiť na obsah</a><div class="top"><div class="wrap">Verejná správa Slovenskej republiky</div></div>
<header class="head"><div class="wrap"><a class="brand" href="{BASE}/"><img src="{BASE}/assets/migrated/images/1c5ac9f7c63c_logo.png" alt="Erb obce Ochodnica"><span><strong>Obec Ochodnica</strong><small>webové sídlo obce</small></span></a></div></header>
<nav class="nav" aria-label="Hlavná navigácia"><div class="wrap">{nav}</div></nav>
<main id="main"><div class="wrap"><div class="crumb"><a href="{BASE}/">Domov</a> › {escape(category)} › {escape(title)}</div><span class="kicker">{escape(category)}</span><h1>{escape(title)}</h1><div class="content source-content"><p class="cms-date"><time datetime="{d.isoformat()}">{d.strftime('%d. %m. %Y')}</time></p>{lead}{body_html}</div></div></main>
<footer class="footer"><div class="wrap"><div class="footgrid"><div><strong>Obec Ochodnica</strong><span>Ochodnica 121, 023 35 Ochodnica</span><a href="mailto:obec@ochodnica.sk">obec@ochodnica.sk</a><span>041 / 423 31 21</span></div><div><strong>Technické riešenie a realizácia</strong><span>NESS Žilina</span></div></div><div class="footbottom">Obsah migrovaný z pôvodného verejného webového sídla obce Ochodnica a následne spravovaný cez CMS.</div></div></footer></body></html>'''


def load_entries(folder: Path) -> list[dict]:
    entries = []
    if not folder.exists():
        return entries
    for path in sorted(folder.glob("*.md")):
        try:
            entry = read_frontmatter(path)
            if as_bool(entry.get("published"), True):
                entry["_date"] = parse_date(entry.get("date"))
                entry["_slug"] = slugify(entry.get("slug") or path.stem or entry.get("title"))
                entries.append(entry)
        except Exception as exc:
            err(f"{path}: {exc}")
    return entries


def render_posts(folder_name: str, url_prefix: str, category: str) -> list[dict]:
    entries = load_entries(CONTENT / folder_name)
    seen = set()
    rendered = []
    for entry in entries:
        title = str(entry.get("title") or "").strip()
        if not title:
            err(f"{entry['_file']}: chýba title")
            continue
        d = entry["_date"]
        slug = entry["_slug"]
        key = (d.year, slug)
        if key in seen:
            err(f"{entry['_file']}: duplicitný slug {slug} pre rok {d.year}")
            continue
        seen.add(key)
        target = SITE / url_prefix / str(d.year) / f"{slug}.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        body = clean_html(entry.get("_body") or "") + attachments_html(entry.get("attachments"))
        target.write_text(shell(title, category, d, body, str(entry.get("perex") or "").strip()), encoding="utf-8")
        GENERATED.append(target)
        rendered.append({"title": title, "date": d, "url": f"{BASE}/{target.relative_to(SITE).as_posix()}", "perex": str(entry.get("perex") or "").strip()})
    return sorted(rendered, key=lambda x: (x["date"], x["title"]), reverse=True)


def safe_target(value: str) -> Path | None:
    raw = str(value or "").strip().replace("\\", "/")
    if raw.startswith(BASE + "/"):
        raw = raw[len(BASE) + 1 :]
    raw = raw.lstrip("/")
    p = PurePosixPath(raw)
    if not raw or any(part in {"", ".", ".."} for part in p.parts):
        return None
    if p.parts[0] in {".github", "admin", "scripts", "cms-content", "assets"}:
        return None
    target = SITE.joinpath(*p.parts)
    if raw.endswith("/"):
        target = target / "index.html"
    elif not target.suffix:
        candidate = target / "index.html"
        if candidate.exists():
            target = candidate
    return target


def apply_page_overrides() -> None:
    folder = CONTENT / "stranky"
    if not folder.exists():
        return
    used = set()
    for path in sorted(folder.glob("*.md")):
        try:
            entry = read_frontmatter(path)
            if not as_bool(entry.get("published"), True):
                continue
            target = safe_target(entry.get("target_path"))
            if target is None:
                err(f"{path}: neplatná target_path")
                continue
            if target in used:
                err(f"{path}: duplicitná target_path {target.relative_to(SITE)}")
                continue
            used.add(target)
            if not target.exists():
                err(f"{path}: cieľová stránka neexistuje: {target.relative_to(SITE)}")
                continue
            soup = BeautifulSoup(target.read_text("utf-8", errors="ignore"), "html.parser")
            content = soup.select_one(".source-content")
            shell_h1 = soup.select_one("#main > .wrap > h1")
            if content is None or shell_h1 is None:
                err(f"{path}: cieľ nemá IDSK content shell: {target.relative_to(SITE)}")
                continue
            title = str(entry.get("title") or shell_h1.get_text(" ", strip=True)).strip()
            shell_h1.string = title
            if soup.title:
                soup.title.string = f"{title} – Obec Ochodnica"
            body_html = clean_html(entry.get("_body") or "")
            content.clear()
            fragment = BeautifulSoup(body_html, "html.parser")
            for node in list(fragment.contents):
                content.append(node)
            target.write_text(str(soup), encoding="utf-8")
            OVERRIDDEN.append(target)
        except Exception as exc:
            err(f"{path}: {exc}")


def insert_listing(index_rel: str, heading: str, items: list[dict], css_class: str) -> None:
    if not items:
        return
    path = SITE / index_rel
    if not path.exists():
        err(f"chýba index pre CMS listing: {index_rel}")
        return
    soup = BeautifulSoup(path.read_text("utf-8", errors="ignore"), "html.parser")
    content = soup.select_one(".source-content")
    if content is None:
        err(f"{index_rel}: chýba .source-content")
        return
    for old in content.select(f"section.{css_class}"):
        old.decompose()
    section = soup.new_tag("section")
    section["class"] = [css_class]
    h2 = soup.new_tag("h2")
    h2.string = heading
    section.append(h2)
    for item in items[:20]:
        article = soup.new_tag("article")
        article["class"] = ["cms-list-item"]
        h3 = soup.new_tag("h3")
        a = soup.new_tag("a", href=item["url"])
        a.string = item["title"]
        h3.append(a)
        article.append(h3)
        time = soup.new_tag("time", datetime=item["date"].isoformat())
        time.string = item["date"].strftime("%d. %m. %Y")
        article.append(time)
        if item.get("perex"):
            p = soup.new_tag("p")
            p.string = item["perex"]
            article.append(p)
        section.append(article)
    content.insert(0, section)
    path.write_text(str(soup), encoding="utf-8")


def update_home(news: list[dict], notices: list[dict]) -> None:
    items = sorted(news + notices, key=lambda x: (x["date"], x["title"]), reverse=True)[:8]
    if not items:
        return
    insert_listing("index.html", "Najnovšie informácie", items, "cms-home-updates")


def load_settings() -> dict:
    path = CONTENT / "settings.yml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text("utf-8")) or {}
    return data if isinstance(data, dict) else {}


def update_contacts(settings: dict) -> None:
    if not settings:
        return
    municipality = str(settings.get("municipality") or "Obec Ochodnica")
    address = str(settings.get("address") or "Ochodnica 121, 023 35 Ochodnica")
    email = str(settings.get("email") or "obec@ochodnica.sk")
    phone = str(settings.get("phone") or "041 / 423 31 21")
    mobile = str(settings.get("mobile") or "").strip()
    for path in SITE.rglob("*.html"):
        rel = path.relative_to(SITE).as_posix()
        if rel.startswith(("assets/migrated/", "admin/")):
            continue
        soup = BeautifulSoup(path.read_text("utf-8", errors="ignore"), "html.parser")
        contact = soup.select_one("footer.footer .footgrid > div")
        brand = soup.select_one("header.head .brand strong")
        changed = False
        if brand and brand.get_text(" ", strip=True) != municipality:
            brand.string = municipality
            changed = True
        if contact:
            contact.clear()
            strong = soup.new_tag("strong")
            strong.string = municipality
            contact.append(strong)
            span = soup.new_tag("span")
            span.string = address
            contact.append(span)
            mail = soup.new_tag("a", href=f"mailto:{email}")
            mail.string = email
            contact.append(mail)
            span = soup.new_tag("span")
            span.string = phone
            contact.append(span)
            if mobile:
                span = soup.new_tag("span")
                span.string = mobile
                contact.append(span)
            changed = True
        if changed:
            path.write_text(str(soup), encoding="utf-8")


def copy_cms_runtime() -> None:
    if SITE.resolve() == REPO.resolve():
        return
    if ADMIN.exists():
        dst = SITE / "admin"
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(ADMIN, dst)
    if CMS_MEDIA.exists():
        dst = SITE / "assets" / "cms"
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(CMS_MEDIA, dst)


def local_target_exists(url: str) -> bool:
    clean = url.split("#", 1)[0].split("?", 1)[0]
    if not clean.startswith(BASE + "/"):
        return True
    rel = clean[len(BASE) + 1 :]
    target = SITE / rel
    if not rel:
        target = SITE / "index.html"
    elif clean.endswith("/") or not Path(rel).suffix:
        target = target / "index.html"
    return target.exists()


def validate() -> None:
    for path in GENERATED + OVERRIDDEN:
        soup = BeautifulSoup(path.read_text("utf-8", errors="ignore"), "html.parser")
        if len(soup.find_all("h1")) != 1:
            err(f"{path.relative_to(SITE)}: CMS stránka nemá presne jedno H1")
        if soup.select_one(".source-content") is None:
            err(f"{path.relative_to(SITE)}: CMS stránka nemá .source-content")
        if "NESS Žilina" not in soup.get_text(" ", strip=True):
            err(f"{path.relative_to(SITE)}: chýba NESS Žilina branding")
        for tag in soup.find_all(["a", "img", "source", "video", "audio", "link"]):
            value = tag.get("href") or tag.get("src") or ""
            if value.startswith(BASE + "/") and not local_target_exists(value):
                err(f"{path.relative_to(SITE)}: neexistujúci lokálny odkaz {value}")
        for form in soup.find_all("form"):
            if (form.get("method") or "get").casefold() == "post":
                err(f"{path.relative_to(SITE)}: POST formulár nie je povolený na statickom webe")


def main() -> int:
    if not SITE.exists():
        print(f"CMS: site root neexistuje: {SITE}", file=sys.stderr)
        return 2
    copy_cms_runtime()
    news = render_posts("novinky", "sk/novinky-z-obce", "Aktuality")
    notices = render_posts("uradne-oznamy", "sk/uradne-oznamy", "Úradné oznamy")
    apply_page_overrides()
    insert_listing("sk/kategoria/novinky-z-obce/index.html", "Aktuality spravované cez CMS", news, "cms-managed-news")
    insert_listing("sk/kategoria/uradne-oznamy/index.html", "Úradné oznamy spravované cez CMS", notices, "cms-managed-notices")
    update_home(news, notices)
    update_contacts(load_settings())
    validate()

    summary = [
        "Ochodnica CMS render",
        f"Site root: {SITE}",
        f"CMS aktuality: {len(news)}",
        f"CMS úradné oznamy: {len(notices)}",
        f"CMS nové stránky: {len(GENERATED)}",
        f"CMS prepísané existujúce stránky: {len(OVERRIDDEN)}",
        f"CMS QC errors: {len(ERRORS)}",
    ]
    (SITE / "CMS-QC-SUMMARY.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    for message in ERRORS[:100]:
        print("CMS_QC_ERROR", message)
    return 5 if ERRORS else 0


if __name__ == "__main__":
    raise SystemExit(main())
