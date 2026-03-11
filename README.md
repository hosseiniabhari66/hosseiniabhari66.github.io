# Professional Academic Website (GitHub Pages)

This folder contains a complete starter website for a professional academic/engineering profile.

## Files Included

- `index.html` - Home page with about, research areas, and contact.
- `projects.html` - Project portfolio page.
- `publications.html` - Publications page.
- `style.css` - Shared styling.
- `script.js` - Small helper for dynamic footer year.

## Quick Deploy Steps

1. Create (or use) the repository named `yourusername.github.io`.
2. Copy all files from this folder into the repository root.
3. Commit and push to the `main` branch.
4. In GitHub, open **Settings -> Pages**.
5. Under **Build and deployment**, set:
   - **Source**: Deploy from a branch
   - **Branch**: `main` / root
6. Wait 1-2 minutes, then open `https://yourusername.github.io`.

## Personalization Checklist

- Replace all `Hossein` placeholders with your preferred full name.
- Update email and social/profile links.
- Add your real project repositories and descriptions.
- Replace publication placeholders with your actual citations.
- Add `cv.pdf` to this folder for the CV button on the home page.
- Optional: add a profile photo as `profile.jpg` and include it in `index.html`.

## Optional Enhancements

- Add `favicon.ico`.
- Connect a custom domain via a `CNAME` file.
- Add analytics (Plausible or Google Analytics).
- Add a blog section (`blog.html`) and RSS feed.

## Automatic Publications from ORCID

This repository includes an automated pipeline that updates `data/publications.json`
from your ORCID record and renders it on `publications.html`.

### Included Files

- `scripts/update_publications.py` - Fetches publications from ORCID public API.
- `.github/workflows/update-publications.yml` - Runs on schedule and manual trigger.
- `data/publications.json` - Generated data consumed by `publications.js`.
- `publications.js` - Renders publication list in browser.

### One-Time Setup

1. Copy your ORCID id, for example: `0000-0002-1825-0097`.
2. In your GitHub repository, go to **Settings -> Secrets and variables -> Actions**.
3. Create repository variable (preferred):
   - Name: `ORCID_ID`
   - Value: your ORCID id (id only or full URL like `https://orcid.org/0000-0002-1825-0097`).
4. Optional: create repository variable:
   - Name: `ORCID_MAX_PUBLICATIONS`
   - Value: max number of items, e.g., `50`
5. Optional: create repository variable:
   - Name: `ORCID_TIMEOUT_SECONDS`
   - Value: request timeout in seconds, e.g., `45`
6. Run the workflow once manually:
   - **Actions -> Update Publications -> Run workflow**

Alternative fallback if you do not want settings:
- Put your id directly in `data/publications.json` under `orcid_id`.

### Notes

- ORCID public API is official and stable for this use case.
- ORCID works metadata may not always include full author lists in the public works endpoint.
- If a run fails, rerun the workflow later from the Actions tab.
