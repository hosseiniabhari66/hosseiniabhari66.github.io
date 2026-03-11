import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from bs4 import BeautifulSoup


def normalize_scholar_user_id(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        return ""
    if "scholar.google.com" not in value:
        return value
    parsed = urlparse(value)
    user_values = parse_qs(parsed.query).get("user", [])
    return user_values[0].strip() if user_values else ""


def resolve_scholar_user_id() -> str:
    env_value = normalize_scholar_user_id(os.getenv("SCHOLAR_USER_ID", ""))
    if env_value:
        return env_value

    fallback_file = Path("data") / "publications.json"
    if fallback_file.exists():
        try:
            payload = json.loads(fallback_file.read_text(encoding="utf-8"))
            file_value = normalize_scholar_user_id(str(payload.get("scholar_user_id", "")))
            if file_value:
                return file_value
        except json.JSONDecodeError:
            pass

    raise RuntimeError(
        "Missing Google Scholar user id. Set repository variable SCHOLAR_USER_ID "
        "(preferred), secret SCHOLAR_USER_ID, or data/publications.json -> scholar_user_id."
    )


def parse_int(value: str) -> int:
    text = (value or "").strip().replace(",", "")
    if text.isdigit():
        return int(text)
    return 0


def fetch_publications(scholar_user_id: str, max_pubs: int, request_timeout: int):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
    }
    publications = []
    page_size = 100
    cstart = 0

    while len(publications) < max_pubs:
        params = {
            "view_op": "list_works",
            "hl": "en",
            "user": scholar_user_id,
            "cstart": str(cstart),
            "pagesize": str(page_size),
        }
        url = "https://scholar.google.com/citations?" + urlencode(params)
        print(f"Fetching page offset {cstart}...", flush=True)
        response = requests.get(url, headers=headers, timeout=request_timeout)
        response.raise_for_status()
        html = response.text
        html_lower = html.lower()
        if "unusual traffic" in html_lower or "not a robot" in html_lower:
            raise RuntimeError(
                "Google Scholar blocked this request (captcha/anti-bot). "
                "Try rerunning later; GitHub-hosted runners are sometimes blocked."
            )

        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("tr.gsc_a_tr")
        if not rows:
            break

        for row in rows:
            title_node = row.select_one("a.gsc_a_at")
            if not title_node:
                continue
            title = title_node.get_text(strip=True)
            href = title_node.get("href", "").strip()
            link = f"https://scholar.google.com{href}" if href else ""

            gray_nodes = row.select("div.gs_gray")
            authors = gray_nodes[0].get_text(strip=True) if len(gray_nodes) > 0 else ""
            venue = gray_nodes[1].get_text(strip=True) if len(gray_nodes) > 1 else ""

            citation_node = row.select_one("a.gsc_a_ac")
            citations = parse_int(citation_node.get_text(strip=True) if citation_node else "")

            year_node = row.select_one("td.gsc_a_y span")
            year = (year_node.get_text(strip=True) if year_node else "").strip()

            publications.append(
                {
                    "title": title,
                    "authors": authors,
                    "venue": venue,
                    "year": year,
                    "citations": citations,
                    "url": link,
                }
            )
            if len(publications) >= max_pubs:
                break

        cstart += page_size

    return publications


def fetch_publications_via_serpapi(
    scholar_user_id: str, max_pubs: int, request_timeout: int, serpapi_api_key: str
):
    publications = []
    start = 0
    batch = 100
    profile_url = f"https://scholar.google.com/citations?user={scholar_user_id}"

    while len(publications) < max_pubs:
        params = {
            "engine": "google_scholar_author",
            "author_id": scholar_user_id,
            "hl": "en",
            "start": str(start),
            "num": str(batch),
            "api_key": serpapi_api_key,
        }
        print(f"Fetching via SerpAPI offset {start}...", flush=True)
        response = requests.get("https://serpapi.com/search.json", params=params, timeout=request_timeout)
        response.raise_for_status()
        payload = response.json()

        author_data = payload.get("author", {}) if isinstance(payload, dict) else {}
        profile_url = author_data.get("link", profile_url)

        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        if not articles:
            break

        for article in articles:
            if not isinstance(article, dict):
                continue
            cited_raw = article.get("cited_by", {})
            if isinstance(cited_raw, dict):
                cited_val = cited_raw.get("value", 0)
            else:
                cited_val = cited_raw
            citations = parse_int(str(cited_val))

            publications.append(
                {
                    "title": (article.get("title") or article.get("article_title") or "").strip(),
                    "authors": (article.get("authors") or "").strip(),
                    "venue": (article.get("publication") or article.get("source") or "").strip(),
                    "year": str(article.get("year", "")).strip(),
                    "citations": citations,
                    "url": (article.get("link") or "").strip(),
                }
            )
            if len(publications) >= max_pubs:
                break

        start += len(articles)

    return publications, profile_url


def main() -> None:
    scholar_user_id = resolve_scholar_user_id()
    max_pubs_raw = os.getenv("SCHOLAR_MAX_PUBLICATIONS", "10").strip()
    max_pubs = int(max_pubs_raw) if max_pubs_raw.isdigit() else 10
    timeout_raw = os.getenv("SCHOLAR_TIMEOUT_SECONDS", "120").strip()
    timeout_seconds = int(timeout_raw) if timeout_raw.isdigit() else 90
    serpapi_api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    scholar_profile_url = f"https://scholar.google.com/citations?user={scholar_user_id}"

    print(f"Fetching Google Scholar author: {scholar_user_id}", flush=True)
    try:
        publication_rows = fetch_publications(scholar_user_id, max_pubs, timeout_seconds)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status == 403 and serpapi_api_key:
            print("Direct Scholar blocked (403). Falling back to SerpAPI...", flush=True)
            publication_rows, scholar_profile_url = fetch_publications_via_serpapi(
                scholar_user_id, max_pubs, timeout_seconds, serpapi_api_key
            )
        elif status == 403:
            raise RuntimeError(
                "Google Scholar returned 403 on GitHub runner. "
                "Set SERPAPI_API_KEY (secret) for fallback or use a self-hosted runner."
            ) from exc
        else:
            raise

    publication_rows.sort(
        key=lambda x: (x.get("year", ""), x.get("citations", 0)),
        reverse=True,
    )

    payload = {
        "scholar_user_id": scholar_user_id,
        "scholar_profile_url": scholar_profile_url,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "publications": publication_rows,
    }

    output_file = Path("data") / "publications.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(publication_rows)} publications to {output_file}", flush=True)


if __name__ == "__main__":
    main()
