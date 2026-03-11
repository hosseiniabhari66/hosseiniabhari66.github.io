import json
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scholarly import scholarly


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


def run_with_timeout(callable_obj, timeout_seconds: int):
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(callable_obj)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError as exc:
            raise RuntimeError(
                f"Google Scholar request timed out after {timeout_seconds}s. "
                "Try again later or reduce SCHOLAR_MAX_PUBLICATIONS."
            ) from exc


def main() -> None:
    scholar_user_id = resolve_scholar_user_id()
    max_pubs_raw = os.getenv("SCHOLAR_MAX_PUBLICATIONS", "15").strip()
    max_pubs = int(max_pubs_raw) if max_pubs_raw.isdigit() else 15
    timeout_raw = os.getenv("SCHOLAR_TIMEOUT_SECONDS", "120").strip()
    timeout_seconds = int(timeout_raw) if timeout_raw.isdigit() else 120

    print(f"Fetching Google Scholar author: {scholar_user_id}", flush=True)
    author = run_with_timeout(lambda: scholarly.search_author_id(scholar_user_id), timeout_seconds)
    author = run_with_timeout(lambda: scholarly.fill(author, sections=["publications"]), timeout_seconds)

    publication_rows = []
    for pub in author.get("publications", [])[:max_pubs]:
        # Avoid per-publication network calls to keep workflow fast and reliable.
        bib = pub.get("bib", {})
        pub_url = pub.get("pub_url", "")
        citations = pub.get("num_citations", 0)

        publication_rows.append(
            {
                "title": bib.get("title", "").strip(),
                "authors": bib.get("author", "").strip(),
                "venue": (bib.get("journal") or bib.get("venue") or "").strip(),
                "year": str(bib.get("pub_year", "")).strip(),
                "citations": int(citations) if str(citations).isdigit() else 0,
                "url": pub_url.strip(),
            }
        )

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
