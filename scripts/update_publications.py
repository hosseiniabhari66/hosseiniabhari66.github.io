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


def main() -> None:
    scholar_user_id = resolve_scholar_user_id()
    max_pubs_raw = os.getenv("SCHOLAR_MAX_PUBLICATIONS", "10").strip()
    max_pubs = int(max_pubs_raw) if max_pubs_raw.isdigit() else 10
    timeout_raw = os.getenv("SCHOLAR_TIMEOUT_SECONDS", "120").strip()
    timeout_seconds = int(timeout_raw) if timeout_raw.isdigit() else 90

    print(f"Fetching Google Scholar author: {scholar_user_id}", flush=True)
    publication_rows = fetch_publications(scholar_user_id, max_pubs, timeout_seconds)

    publication_rows.sort(
        key=lambda x: (x.get("year", ""), x.get("citations", 0)),
        reverse=True,
    )

    payload = {
        "scholar_user_id": scholar_user_id,
        "scholar_profile_url": f"https://scholar.google.com/citations?user={scholar_user_id}",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "publications": publication_rows,
    }

    output_file = Path("data") / "publications.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(publication_rows)} publications to {output_file}", flush=True)


if __name__ == "__main__":
    main()
