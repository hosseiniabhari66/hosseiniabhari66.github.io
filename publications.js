async function renderPublications() {
  const list = document.getElementById("publication-list");
  const status = document.getElementById("publication-status");
  const scholarLink = document.getElementById("scholar-profile-link");

  if (!list || !status) {
    return;
  }

  try {
    const response = await fetch("data/publications.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Failed to load publications data.");
    }

    const payload = await response.json();
    const publications = Array.isArray(payload.publications) ? payload.publications : [];

    if (payload.scholar_profile_url && scholarLink) {
      scholarLink.href = payload.scholar_profile_url;
    }

    if (publications.length === 0) {
      status.textContent = "No publications found yet. Run the updater workflow in GitHub Actions.";
      return;
    }

    list.innerHTML = "";
    publications.forEach((item) => {
      const li = document.createElement("li");
      const title = item.title || "Untitled publication";
      const authors = item.authors || "Unknown authors";
      const venue = item.venue || "Unknown venue";
      const year = item.year || "N/A";
      const citations = item.citations ?? 0;
      const link = item.url || "#";

      li.innerHTML =
        `<strong>${title}</strong><br>` +
        `<span>${authors}</span><br>` +
        `<em>${venue}</em> (${year}) | Citations: ${citations} ` +
        (item.url ? `| <a href="${link}" target="_blank" rel="noopener noreferrer">Link</a>` : "");
      list.appendChild(li);
    });

    const updatedAt = payload.updated_at || "unknown time";
    status.textContent = `Last updated: ${updatedAt}`;
  } catch (error) {
    status.textContent = "Could not load publication data. Check workflow logs in GitHub Actions.";
  }
}

renderPublications();
