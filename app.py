"""
Local SEO Audit Tool
A comprehensive tool to audit websites for local SEO performance.
"""

from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import re
import json
import time
import urllib.parse
from urllib.robotparser import RobotFileParser
import socket
import ssl
import threading
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ─────────────────────────────────────────────
#  Helper utilities
# ─────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

LOCAL_SCHEMA_TYPES = [
    "LocalBusiness", "Store", "Restaurant", "Hotel", "MedicalBusiness",
    "HealthAndBeautyBusiness", "LegalService", "FinancialService",
    "HomeAndConstructionBusiness", "AutoDealer", "RealEstateAgent",
    "ProfessionalService", "SportsActivityLocation", "EntertainmentBusiness",
    "FoodEstablishment", "Organization",
]

NAP_PATTERNS = {
    "phone": [
        r'\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}',
        r'\+?1?\s?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}',
        r'\+\d{1,3}\s?\d{6,14}',
    ],
    "address": [
        r'\d{1,5}\s[\w\s]{2,40},\s[A-Z]{2}\s\d{5}',
        r'\d{1,5}\s[\w\s]{2,40},\s[\w\s]+,\s[A-Z]{2}\s\d{5}',
    ],
}


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urllib.parse.urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def safe_get(url: str, timeout: int = 10) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
        return resp
    except Exception:
        return None


def score_to_grade(score: float) -> dict:
    if score >= 90:
        return {"grade": "A", "color": "#22c55e"}
    elif score >= 75:
        return {"grade": "B", "color": "#84cc16"}
    elif score >= 60:
        return {"grade": "C", "color": "#eab308"}
    elif score >= 40:
        return {"grade": "D", "color": "#f97316"}
    else:
        return {"grade": "F", "color": "#ef4444"}


# ─────────────────────────────────────────────
#  Audit modules
# ─────────────────────────────────────────────

def check_ssl(base_url: str) -> dict:
    result = {"name": "SSL / HTTPS", "items": []}
    parsed = urllib.parse.urlparse(base_url)
    hostname = parsed.netloc.split(":")[0]

    # Check if HTTPS
    https_resp = safe_get(f"https://{hostname}")
    if https_resp and https_resp.status_code < 400:
        result["items"].append({"label": "HTTPS available", "status": "pass", "detail": "Site is accessible over HTTPS"})
    else:
        result["items"].append({"label": "HTTPS available", "status": "fail", "detail": "Site is NOT accessible over HTTPS — critical for trust & rankings"})
        return result

    # Check HTTP → HTTPS redirect
    http_resp = safe_get(f"http://{hostname}")
    if http_resp:
        final = http_resp.url
        if final.startswith("https://"):
            result["items"].append({"label": "HTTP→HTTPS redirect", "status": "pass", "detail": f"Redirects to {final}"})
        else:
            result["items"].append({"label": "HTTP→HTTPS redirect", "status": "warn", "detail": "HTTP version does not redirect to HTTPS"})

    # Check SSL expiry
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(5)
            s.connect((hostname, 443))
            cert = s.getpeercert()
            expiry_str = cert["notAfter"]
            expiry = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
            days_left = (expiry - datetime.utcnow()).days
            if days_left > 30:
                result["items"].append({"label": "SSL certificate expiry", "status": "pass", "detail": f"Expires in {days_left} days ({expiry.strftime('%Y-%m-%d')})"})
            elif days_left > 0:
                result["items"].append({"label": "SSL certificate expiry", "status": "warn", "detail": f"Expires SOON in {days_left} days — renew immediately"})
            else:
                result["items"].append({"label": "SSL certificate expiry", "status": "fail", "detail": "SSL certificate has EXPIRED"})
    except Exception as e:
        result["items"].append({"label": "SSL certificate expiry", "status": "warn", "detail": f"Could not verify certificate: {e}"})

    return result


def check_meta_tags(soup: BeautifulSoup, url: str) -> dict:
    result = {"name": "Meta Tags & Title", "items": []}

    # Title
    title_tag = soup.find("title")
    if title_tag and title_tag.text.strip():
        title = title_tag.text.strip()
        tlen = len(title)
        if 30 <= tlen <= 60:
            result["items"].append({"label": "Title tag", "status": "pass", "detail": f'"{title}" ({tlen} chars)'})
        elif tlen < 30:
            result["items"].append({"label": "Title tag", "status": "warn", "detail": f'"{title}" — too short ({tlen} chars, aim for 30–60)'})
        else:
            result["items"].append({"label": "Title tag", "status": "warn", "detail": f'"{title}" — too long ({tlen} chars, aim for 30–60)'})
    else:
        result["items"].append({"label": "Title tag", "status": "fail", "detail": "Missing title tag — critical SEO element"})

    # Meta description
    meta_desc = soup.find("meta", attrs={"name": re.compile("description", re.I)})
    if meta_desc and meta_desc.get("content", "").strip():
        desc = meta_desc["content"].strip()
        dlen = len(desc)
        if 120 <= dlen <= 160:
            result["items"].append({"label": "Meta description", "status": "pass", "detail": f'"{desc[:80]}…" ({dlen} chars)'})
        else:
            result["items"].append({"label": "Meta description", "status": "warn", "detail": f"Length {dlen} chars — aim for 120–160"})
    else:
        result["items"].append({"label": "Meta description", "status": "fail", "detail": "Missing meta description"})

    # Viewport
    viewport = soup.find("meta", attrs={"name": re.compile("viewport", re.I)})
    if viewport:
        result["items"].append({"label": "Viewport meta tag", "status": "pass", "detail": viewport.get("content", "")})
    else:
        result["items"].append({"label": "Viewport meta tag", "status": "fail", "detail": "Missing — site may not be mobile-friendly"})

    # Canonical
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href"):
        result["items"].append({"label": "Canonical tag", "status": "pass", "detail": canonical["href"]})
    else:
        result["items"].append({"label": "Canonical tag", "status": "warn", "detail": "No canonical tag found — may cause duplicate content issues"})

    # Robots meta
    robots_meta = soup.find("meta", attrs={"name": re.compile("robots", re.I)})
    if robots_meta:
        content = robots_meta.get("content", "").lower()
        if "noindex" in content:
            result["items"].append({"label": "Robots meta", "status": "fail", "detail": f"Page set to NOINDEX: {content}"})
        else:
            result["items"].append({"label": "Robots meta", "status": "pass", "detail": content or "index, follow (default)"})
    else:
        result["items"].append({"label": "Robots meta", "status": "pass", "detail": "No robots meta — defaults to index, follow"})

    # Open Graph
    og_title = soup.find("meta", property="og:title")
    og_desc = soup.find("meta", property="og:description")
    og_image = soup.find("meta", property="og:image")
    og_count = sum(1 for t in [og_title, og_desc, og_image] if t)
    if og_count == 3:
        result["items"].append({"label": "Open Graph tags", "status": "pass", "detail": "og:title, og:description, og:image all present"})
    elif og_count > 0:
        result["items"].append({"label": "Open Graph tags", "status": "warn", "detail": f"Only {og_count}/3 core OG tags found"})
    else:
        result["items"].append({"label": "Open Graph tags", "status": "warn", "detail": "No Open Graph tags — affects social sharing appearance"})

    return result


def check_local_schema(soup: BeautifulSoup) -> dict:
    result = {"name": "Structured Data (Schema.org)", "items": []}
    found_schemas = []

    # JSON-LD
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict) and "@graph" in data:
                items = data["@graph"]
            else:
                items = [data]

            for item in items:
                stype = item.get("@type", "")
                if isinstance(stype, list):
                    stype = stype[0]
                found_schemas.append(stype)

                if any(t.lower() in stype.lower() for t in LOCAL_SCHEMA_TYPES):
                    # Check NAP in schema
                    has_name = bool(item.get("name"))
                    has_address = bool(item.get("address"))
                    has_phone = bool(item.get("telephone"))
                    has_geo = bool(item.get("geo"))
                    has_hours = bool(item.get("openingHours") or item.get("openingHoursSpecification"))

                    result["items"].append({"label": f"Local schema: {stype}", "status": "pass", "detail": "Local business schema found"})
                    result["items"].append({"label": "Schema: name", "status": "pass" if has_name else "warn", "detail": item.get("name", "Missing")})
                    result["items"].append({"label": "Schema: address", "status": "pass" if has_address else "fail", "detail": str(item.get("address", "Missing"))[:100]})
                    result["items"].append({"label": "Schema: telephone", "status": "pass" if has_phone else "warn", "detail": item.get("telephone", "Missing")})
                    result["items"].append({"label": "Schema: geo coordinates", "status": "pass" if has_geo else "warn", "detail": str(item.get("geo", "Missing"))})
                    result["items"].append({"label": "Schema: opening hours", "status": "pass" if has_hours else "warn", "detail": "Present" if has_hours else "Missing — add opening hours"})
        except Exception:
            pass

    if not any("Local schema" in i["label"] for i in result["items"]):
        if found_schemas:
            result["items"].append({"label": "Local business schema", "status": "fail", "detail": f"Found schema types: {', '.join(set(found_schemas))} — none are local business types"})
        else:
            result["items"].append({"label": "Local business schema", "status": "fail", "detail": "No JSON-LD structured data found — add LocalBusiness schema"})

    # Check microdata as fallback
    microdata = soup.find(attrs={"itemtype": re.compile("schema.org", re.I)})
    if microdata:
        itype = microdata.get("itemtype", "")
        result["items"].append({"label": "Microdata schema", "status": "pass", "detail": f"Found: {itype}"})

    return result


def check_nap(soup: BeautifulSoup) -> dict:
    result = {"name": "NAP Consistency (Name, Address, Phone)", "items": []}
    text = soup.get_text(" ", strip=True)

    # Phone
    phones_found = []
    for pat in NAP_PATTERNS["phone"]:
        matches = re.findall(pat, text)
        phones_found.extend(matches)
    phones_found = list(set(phones_found))

    if phones_found:
        result["items"].append({"label": "Phone number", "status": "pass", "detail": f"Found: {', '.join(phones_found[:3])}"})
        if len(phones_found) > 2:
            result["items"].append({"label": "Multiple phones", "status": "warn", "detail": f"{len(phones_found)} phone numbers found — ensure consistency across directories"})
    else:
        result["items"].append({"label": "Phone number", "status": "fail", "detail": "No phone number detected on page — critical for local SEO"})

    # Address
    addrs_found = []
    for pat in NAP_PATTERNS["address"]:
        matches = re.findall(pat, text)
        addrs_found.extend(matches)
    addrs_found = list(set(addrs_found))

    if addrs_found:
        result["items"].append({"label": "Address", "status": "pass", "detail": f"Found: {addrs_found[0]}"})
    else:
        result["items"].append({"label": "Address", "status": "warn", "detail": "No US-format address detected — ensure full address is on page"})

    # Footer NAP (best practice)
    footer = soup.find("footer")
    if footer:
        footer_text = footer.get_text(" ", strip=True)
        footer_phones = []
        for pat in NAP_PATTERNS["phone"]:
            footer_phones.extend(re.findall(pat, footer_text))
        if footer_phones:
            result["items"].append({"label": "NAP in footer", "status": "pass", "detail": "Phone number found in footer"})
        else:
            result["items"].append({"label": "NAP in footer", "status": "warn", "detail": "No phone number in footer — add NAP to footer for consistency"})
    else:
        result["items"].append({"label": "Footer element", "status": "warn", "detail": "No <footer> element found"})

    # Contact page link
    contact_links = soup.find_all("a", href=re.compile(r"contact|about|location", re.I))
    if contact_links:
        result["items"].append({"label": "Contact/Location page", "status": "pass", "detail": f"Found link: {contact_links[0].get('href', '')}"})
    else:
        result["items"].append({"label": "Contact/Location page", "status": "warn", "detail": "No contact/location page link found"})

    return result


def check_google_signals(soup: BeautifulSoup, html: str) -> dict:
    result = {"name": "Google Business & Maps Signals", "items": []}

    # Google Maps embed
    maps_embed = bool(re.search(r'maps\.google\.com|google\.com/maps|maps\.googleapis\.com', html, re.I))
    if maps_embed:
        result["items"].append({"label": "Google Maps embed", "status": "pass", "detail": "Google Maps iframe/embed detected"})
    else:
        result["items"].append({"label": "Google Maps embed", "status": "warn", "detail": "No Google Maps embed found — embed a map to boost local relevance"})

    # Google Analytics
    ga = bool(re.search(r'google-analytics\.com|gtag\(|GA_MEASUREMENT_ID|UA-\d+|G-[A-Z0-9]+', html))
    if ga:
        result["items"].append({"label": "Google Analytics", "status": "pass", "detail": "Google Analytics tracking detected"})
    else:
        result["items"].append({"label": "Google Analytics", "status": "warn", "detail": "No Google Analytics detected — install for performance tracking"})

    # Google Search Console verification
    gsc = soup.find("meta", attrs={"name": "google-site-verification"})
    if gsc:
        result["items"].append({"label": "Google Search Console", "status": "pass", "detail": f"Verification tag found: {gsc.get('content', '')[:40]}"})
    else:
        result["items"].append({"label": "Google Search Console", "status": "warn", "detail": "No GSC verification tag — verify ownership in Search Console"})

    # Google Business Profile review link
    gbp_link = bool(re.search(r'g\.page|maps\.app\.goo\.gl|google\.com/maps/place', html, re.I))
    if gbp_link:
        result["items"].append({"label": "Google Business Profile link", "status": "pass", "detail": "Link to Google Business Profile found"})
    else:
        result["items"].append({"label": "Google Business Profile link", "status": "warn", "detail": "No Google Business Profile link — add a link for reviews"})

    return result


def check_page_speed_signals(resp: requests.Response, soup: BeautifulSoup) -> dict:
    result = {"name": "Page Speed Signals", "items": []}

    # Response time
    elapsed = resp.elapsed.total_seconds() if resp else 99
    if elapsed < 1.0:
        result["items"].append({"label": "Server response time", "status": "pass", "detail": f"{elapsed:.2f}s — excellent"})
    elif elapsed < 2.5:
        result["items"].append({"label": "Server response time", "status": "warn", "detail": f"{elapsed:.2f}s — acceptable but could be faster"})
    else:
        result["items"].append({"label": "Server response time", "status": "fail", "detail": f"{elapsed:.2f}s — too slow, aim for <1s"})

    # Content size
    content_size = len(resp.content) / 1024 if resp else 0
    if content_size < 200:
        result["items"].append({"label": "HTML page size", "status": "pass", "detail": f"{content_size:.1f} KB"})
    elif content_size < 500:
        result["items"].append({"label": "HTML page size", "status": "warn", "detail": f"{content_size:.1f} KB — consider reducing"})
    else:
        result["items"].append({"label": "HTML page size", "status": "fail", "detail": f"{content_size:.1f} KB — too large"})

    # Compression (gzip/br)
    encoding = resp.headers.get("Content-Encoding", "") if resp else ""
    if encoding in ("gzip", "br", "deflate"):
        result["items"].append({"label": "Compression", "status": "pass", "detail": f"Content-Encoding: {encoding}"})
    else:
        result["items"].append({"label": "Compression", "status": "warn", "detail": "No compression detected — enable gzip/Brotli"})

    # Cache headers
    cache = resp.headers.get("Cache-Control", "") if resp else ""
    if cache:
        result["items"].append({"label": "Cache-Control header", "status": "pass", "detail": cache})
    else:
        result["items"].append({"label": "Cache-Control header", "status": "warn", "detail": "No Cache-Control header set"})

    # Images without lazy loading
    imgs = soup.find_all("img")
    lazy_missing = [i for i in imgs if not i.get("loading") and not i.get("data-src")]
    if not imgs:
        result["items"].append({"label": "Image optimization", "status": "warn", "detail": "No images found on page"})
    elif len(lazy_missing) == 0:
        result["items"].append({"label": "Image lazy loading", "status": "pass", "detail": f"All {len(imgs)} images have lazy loading or are deferred"})
    else:
        result["items"].append({"label": "Image lazy loading", "status": "warn", "detail": f"{len(lazy_missing)}/{len(imgs)} images missing loading='lazy'"})

    # Images missing alt text
    no_alt = [i for i in imgs if not i.get("alt", "").strip()]
    if no_alt:
        result["items"].append({"label": "Image alt text", "status": "fail" if len(no_alt) > 3 else "warn", "detail": f"{len(no_alt)} images missing alt text — hurts accessibility & SEO"})
    else:
        result["items"].append({"label": "Image alt text", "status": "pass", "detail": f"All {len(imgs)} images have alt text"})

    return result


def check_mobile_friendliness(soup: BeautifulSoup, html: str) -> dict:
    result = {"name": "Mobile Friendliness", "items": []}

    # Viewport
    viewport = soup.find("meta", attrs={"name": re.compile("viewport", re.I)})
    if viewport and "width=device-width" in viewport.get("content", ""):
        result["items"].append({"label": "Responsive viewport", "status": "pass", "detail": viewport["content"]})
    else:
        result["items"].append({"label": "Responsive viewport", "status": "fail", "detail": "Missing or incorrect viewport meta tag"})

    # Touch icons
    apple_icon = soup.find("link", rel=re.compile("apple-touch-icon", re.I))
    if apple_icon:
        result["items"].append({"label": "Apple touch icon", "status": "pass", "detail": apple_icon.get("href", "")})
    else:
        result["items"].append({"label": "Apple touch icon", "status": "warn", "detail": "No apple-touch-icon found"})

    # Favicon
    favicon = soup.find("link", rel=re.compile("icon|shortcut icon", re.I))
    if favicon:
        result["items"].append({"label": "Favicon", "status": "pass", "detail": favicon.get("href", "")})
    else:
        result["items"].append({"label": "Favicon", "status": "warn", "detail": "No favicon link tag found"})

    # Click-to-call links
    tel_links = soup.find_all("a", href=re.compile(r"^tel:", re.I))
    if tel_links:
        result["items"].append({"label": "Click-to-call links", "status": "pass", "detail": f"{len(tel_links)} tel: link(s) found — great for mobile users"})
    else:
        result["items"].append({"label": "Click-to-call links", "status": "warn", "detail": "No tel: links — add click-to-call for mobile visitors"})

    # Font size (heuristic: check if there's a stylesheet link)
    stylesheets = soup.find_all("link", rel="stylesheet")
    if stylesheets:
        result["items"].append({"label": "External stylesheets", "status": "pass", "detail": f"{len(stylesheets)} stylesheet(s) linked"})
    else:
        result["items"].append({"label": "External stylesheets", "status": "warn", "detail": "No external stylesheets — inline CSS may be hard to maintain"})

    return result


def check_content_signals(soup: BeautifulSoup) -> dict:
    result = {"name": "Content & On-Page Signals", "items": []}

    # H1 tag
    h1s = soup.find_all("h1")
    if len(h1s) == 1:
        result["items"].append({"label": "H1 tag", "status": "pass", "detail": f'"{h1s[0].text.strip()[:80]}"'})
    elif len(h1s) == 0:
        result["items"].append({"label": "H1 tag", "status": "fail", "detail": "No H1 tag found"})
    else:
        result["items"].append({"label": "H1 tag", "status": "warn", "detail": f"{len(h1s)} H1 tags found — use only one per page"})

    # Heading hierarchy
    h2s = soup.find_all("h2")
    h3s = soup.find_all("h3")
    result["items"].append({"label": "Heading hierarchy", "status": "pass" if h2s else "warn",
                             "detail": f"H2: {len(h2s)}, H3: {len(h3s)} — {'good structure' if h2s else 'add H2 subheadings'}"})

    # Word count
    body = soup.find("body")
    if body:
        text = body.get_text(" ", strip=True)
        wc = len(text.split())
        if wc >= 300:
            result["items"].append({"label": "Word count", "status": "pass", "detail": f"~{wc} words"})
        else:
            result["items"].append({"label": "Word count", "status": "warn", "detail": f"~{wc} words — aim for 300+ words on key pages"})

    # Internal links
    internal_links = [a for a in soup.find_all("a", href=True)
                      if not a["href"].startswith(("http", "//", "mailto:", "tel:", "#"))]
    result["items"].append({"label": "Internal links", "status": "pass" if internal_links else "warn",
                             "detail": f"{len(internal_links)} internal link(s) found"})

    # External links
    external_links = [a for a in soup.find_all("a", href=True)
                      if a["href"].startswith(("http://", "https://"))]
    result["items"].append({"label": "External links", "status": "pass" if external_links else "warn",
                             "detail": f"{len(external_links)} external link(s)"})

    # Nofollow check on all links
    nofollow_links = [a for a in soup.find_all("a", rel=True) if "nofollow" in a.get("rel", [])]
    if nofollow_links:
        result["items"].append({"label": "Nofollow links", "status": "warn", "detail": f"{len(nofollow_links)} nofollow link(s) — review if intentional"})

    return result


def check_technical(soup: BeautifulSoup, base_url: str, html: str) -> dict:
    result = {"name": "Technical SEO", "items": []}

    # Robots.txt
    robots_url = base_url.rstrip("/") + "/robots.txt"
    robots_resp = safe_get(robots_url)
    if robots_resp and robots_resp.status_code == 200:
        content = robots_resp.text
        if "Disallow: /" in content and len(content) < 30:
            result["items"].append({"label": "robots.txt", "status": "fail", "detail": "robots.txt blocks ALL crawlers — site won't be indexed"})
        else:
            result["items"].append({"label": "robots.txt", "status": "pass", "detail": f"Found at {robots_url}"})
    else:
        result["items"].append({"label": "robots.txt", "status": "warn", "detail": "No robots.txt found"})

    # Sitemap
    sitemap_url = base_url.rstrip("/") + "/sitemap.xml"
    sitemap_resp = safe_get(sitemap_url)
    if sitemap_resp and sitemap_resp.status_code == 200:
        result["items"].append({"label": "sitemap.xml", "status": "pass", "detail": f"Found at {sitemap_url}"})
    else:
        # Check robots.txt for sitemap reference
        sitemap_in_robots = False
        if robots_resp and robots_resp.status_code == 200:
            sitemap_in_robots = "Sitemap:" in robots_resp.text
        if sitemap_in_robots:
            result["items"].append({"label": "sitemap.xml", "status": "warn", "detail": "Sitemap referenced in robots.txt but /sitemap.xml not found"})
        else:
            result["items"].append({"label": "sitemap.xml", "status": "fail", "detail": "No sitemap.xml found — submit one to Google Search Console"})

    # 404 page
    fake_url = base_url.rstrip("/") + "/this-page-definitely-does-not-exist-xyz123"
    fake_resp = safe_get(fake_url)
    if fake_resp and fake_resp.status_code == 404:
        result["items"].append({"label": "Custom 404 page", "status": "pass", "detail": "Server returns proper 404 status for missing pages"})
    elif fake_resp and fake_resp.status_code == 200:
        result["items"].append({"label": "Custom 404 page", "status": "warn", "detail": "Server returns 200 for missing pages (soft 404) — fix this"})

    # WWW redirect
    parsed = urllib.parse.urlparse(base_url)
    hostname = parsed.netloc
    alt = f"https://www.{hostname}" if not hostname.startswith("www.") else f"https://{hostname[4:]}"
    alt_resp = safe_get(alt)
    if alt_resp and alt_resp.url.rstrip("/") == base_url.rstrip("/"):
        result["items"].append({"label": "WWW/non-WWW redirect", "status": "pass", "detail": f"{alt} redirects correctly"})
    else:
        result["items"].append({"label": "WWW/non-WWW redirect", "status": "warn", "detail": "Check that www and non-www redirect to a single canonical version"})

    # Inline scripts (performance)
    inline_scripts = soup.find_all("script", src=False)
    non_empty = [s for s in inline_scripts if s.string and len(s.string.strip()) > 50]
    if len(non_empty) > 5:
        result["items"].append({"label": "Inline scripts", "status": "warn", "detail": f"{len(non_empty)} inline scripts — consider externalizing for better caching"})
    else:
        result["items"].append({"label": "Inline scripts", "status": "pass", "detail": f"{len(non_empty)} inline scripts"})

    return result


def check_social_signals(soup: BeautifulSoup, html: str) -> dict:
    result = {"name": "Social & Review Signals", "items": []}

    social_patterns = {
        "Facebook": r"facebook\.com",
        "Instagram": r"instagram\.com",
        "Twitter/X": r"twitter\.com|x\.com",
        "LinkedIn": r"linkedin\.com",
        "YouTube": r"youtube\.com",
        "Yelp": r"yelp\.com",
        "TripAdvisor": r"tripadvisor\.com",
    }

    found = []
    missing = []
    for platform, pattern in social_patterns.items():
        if re.search(pattern, html, re.I):
            found.append(platform)
        else:
            missing.append(platform)

    if found:
        result["items"].append({"label": "Social media links", "status": "pass", "detail": f"Found: {', '.join(found)}"})
    else:
        result["items"].append({"label": "Social media links", "status": "warn", "detail": "No social media links found"})

    if "Yelp" in found:
        result["items"].append({"label": "Yelp listing link", "status": "pass", "detail": "Yelp link found on page"})
    else:
        result["items"].append({"label": "Yelp listing link", "status": "warn", "detail": "No Yelp link — important for local trust signals"})

    # Review schema
    review_schema = bool(re.search(r'"Review"|"AggregateRating"|"ratingValue"', html))
    if review_schema:
        result["items"].append({"label": "Review schema", "status": "pass", "detail": "Review/rating structured data found"})
    else:
        result["items"].append({"label": "Review schema", "status": "warn", "detail": "No review schema — add AggregateRating to show stars in search results"})

    # Review count in content
    review_text = bool(re.search(r'\d+\s*(reviews?|ratings?|stars?)', html, re.I))
    if review_text:
        result["items"].append({"label": "Review count visible", "status": "pass", "detail": "Review count/stars visible in page content"})
    else:
        result["items"].append({"label": "Review count visible", "status": "warn", "detail": "No visible review count — display review count to build trust"})

    return result


# ─────────────────────────────────────────────
#  Score calculation
# ─────────────────────────────────────────────

def calculate_score(sections: list) -> dict:
    weights = {
        "SSL / HTTPS": 15,
        "Meta Tags & Title": 15,
        "Structured Data (Schema.org)": 15,
        "NAP Consistency (Name, Address, Phone)": 12,
        "Google Business & Maps Signals": 10,
        "Page Speed Signals": 10,
        "Mobile Friendliness": 10,
        "Content & On-Page Signals": 8,
        "Technical SEO": 8,
        "Social & Review Signals": 7,
    }

    total_weight = sum(weights.values())
    weighted_score = 0

    for section in sections:
        name = section["name"]
        items = section["items"]
        if not items:
            continue
        pass_count = sum(1 for i in items if i["status"] == "pass")
        warn_count = sum(1 for i in items if i["status"] == "warn")
        fail_count = sum(1 for i in items if i["status"] == "fail")
        total = len(items)
        section_score = (pass_count * 1.0 + warn_count * 0.4) / total * 100
        section["score"] = round(section_score)
        w = weights.get(name, 5)
        weighted_score += section_score * w

    overall = weighted_score / total_weight
    return {"overall": round(overall), **score_to_grade(overall)}


# ─────────────────────────────────────────────
#  Flask routes
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/audit", methods=["POST"])
def audit():
    data = request.get_json()
    url = data.get("url", "").strip()

    if not url:
        return jsonify({"error": "Please enter a URL"}), 400

    base_url = normalize_url(url)

    resp = safe_get(base_url)
    if not resp:
        return jsonify({"error": f"Could not reach {base_url} — check the URL and try again"}), 400

    if resp.status_code >= 400:
        return jsonify({"error": f"Server returned HTTP {resp.status_code}"}), 400

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    sections = []
    sections.append(check_ssl(base_url))
    sections.append(check_meta_tags(soup, base_url))
    sections.append(check_local_schema(soup))
    sections.append(check_nap(soup))
    sections.append(check_google_signals(soup, html))
    sections.append(check_page_speed_signals(resp, soup))
    sections.append(check_mobile_friendliness(soup, html))
    sections.append(check_content_signals(soup))
    sections.append(check_technical(soup, base_url, html))
    sections.append(check_social_signals(soup, html))

    score_info = calculate_score(sections)

    # Build summary counts
    all_items = [i for s in sections for i in s["items"]]
    summary = {
        "pass": sum(1 for i in all_items if i["status"] == "pass"),
        "warn": sum(1 for i in all_items if i["status"] == "warn"),
        "fail": sum(1 for i in all_items if i["status"] == "fail"),
        "total": len(all_items),
    }

    return jsonify({
        "url": base_url,
        "audited_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "score": score_info,
        "summary": summary,
        "sections": sections,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
