import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scholarly import scholarly


def resolve_scholar_user_id() -> str:
    env_value = os.getenv("SCHOLAR_USER_ID", "").strip()
    if env_value:
        return env_value

    fallback_file = Path("data") / "publications.json"
    if fallback_file.exists():
        try:
            payload = json.loads(fallback_file.read_text(encoding="utf-8"))
            file_value = str(payload.get("scholar_user_id", "")).strip()
            if file_value:
                return file_value
        except json.JSONDecodeError:
            pass

    raise RuntimeError(
        "Missing Google Scholar user id. Set repository variable SCHOLAR_USER_ID "
        "(preferred), secret SCHOLAR_USER_ID, or data/publications.json -> scholar_user_id."
    )


def main() -> None:
    scholar_user_id = resolve_scholar_user_id()
    max_pubs_raw = os.getenv("SCHOLAR_MAX_PUBLICATIONS", "30").strip()
    max_pubs = int(max_pubs_raw) if max_pubs_raw.isdigit() else 30

    author = scholarly.search_author_id(scholar_user_id)
    author = scholarly.fill(author, sections=["publications"])

    publication_rows = []
    for pub in author.get("publications", [])[:max_pubs]:
        filled = scholarly.fill(pub)
        bib = filled.get("bib", {})
        pub_url = filled.get("pub_url", "")
        citations = filled.get("num_citations", 0)

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
    print(f"Wrote {len(publication_rows)} publications to {output_file}")


if __name__ == "__main__":
    main()
