import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests


ORCID_ID_PATTERN = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")


def normalize_orcid_id(raw_value: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""
    if "orcid.org/" in value:
        value = value.rsplit("/", 1)[-1]
    match = ORCID_ID_PATTERN.search(value)
    return match.group(0) if match else value


def resolve_orcid_id() -> str:
    env_value = normalize_orcid_id(os.getenv("ORCID_ID", ""))
    if env_value:
        return env_value

    fallback_file = Path("data") / "publications.json"
    if fallback_file.exists():
        try:
            payload = json.loads(fallback_file.read_text(encoding="utf-8"))
            file_value = normalize_orcid_id(str(payload.get("orcid_id", "")))
            if file_value:
                return file_value
        except json.JSONDecodeError:
            pass

    raise RuntimeError(
        "Missing ORCID id. Set repository variable ORCID_ID (preferred) "
        "or data/publications.json -> orcid_id."
    )


def get_nested_value(data: dict, path: list) -> str:
    node = data
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return ""
        node = node[key]
    return str(node).strip() if node is not None else ""


def pick_external_id_url(summary: dict) -> str:
    external_ids = summary.get("external-ids", {}).get("external-id", [])
    if not isinstance(external_ids, list):
        return ""
    for item in external_ids:
        if not isinstance(item, dict):
            continue
        id_type = str(item.get("external-id-type", "")).lower()
        id_value = str(item.get("external-id-value", "")).strip()
        if id_type == "doi" and id_value:
            return f"https://doi.org/{id_value}"
        url_value = get_nested_value(item, ["external-id-url", "value"])
        if url_value:
            return url_value
    return ""


def fetch_orcid_works(orcid_id: str, request_timeout: int, max_pubs: int):
    url = f"https://pub.orcid.org/v3.0/{orcid_id}/works"
    headers = {
        "Accept": "application/json",
        "User-Agent": "pyLB-publications-updater/1.0",
    }
    print(f"Fetching ORCID works for {orcid_id}", flush=True)
    response = requests.get(url, headers=headers, timeout=request_timeout)
    response.raise_for_status()
    payload = response.json()

    groups = payload.get("group", []) if isinstance(payload, dict) else []
    publications = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        summaries = group.get("work-summary", [])
        if not isinstance(summaries, list) or not summaries:
            continue
        summary = summaries[0]
        if not isinstance(summary, dict):
            continue

        title = get_nested_value(summary, ["title", "title", "value"])
        if not title:
            continue
        authors = ""
        venue = get_nested_value(summary, ["journal-title", "value"])
        year = get_nested_value(summary, ["publication-date", "year", "value"])
        url = pick_external_id_url(summary) or get_nested_value(summary, ["url", "value"])

        publications.append(
            {
                "title": title,
                "authors": authors,
                "venue": venue,
                "year": year,
                "citations": 0,
                "url": url,
            }
        )
        if len(publications) >= max_pubs:
            break

    publications.sort(key=lambda x: x.get("year", ""), reverse=True)
    return publications


def main() -> None:
    orcid_id = resolve_orcid_id()
    max_pubs_raw = os.getenv("ORCID_MAX_PUBLICATIONS", "50").strip()
    max_pubs = int(max_pubs_raw) if max_pubs_raw.isdigit() else 50
    timeout_raw = os.getenv("ORCID_TIMEOUT_SECONDS", "45").strip()
    timeout_seconds = int(timeout_raw) if timeout_raw.isdigit() else 45

    publication_rows = fetch_orcid_works(orcid_id, timeout_seconds, max_pubs)

    payload = {
        "source": "orcid",
        "orcid_id": orcid_id,
        "profile_url": f"https://orcid.org/{orcid_id}",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "publications": publication_rows,
    }

    output_file = Path("data") / "publications.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Wrote {len(publication_rows)} publications to {output_file}", flush=True)


if __name__ == "__main__":
    main()
