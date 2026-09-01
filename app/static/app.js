const PAGE_SIZE = 30;

const SECTIONS = [
  { id: "new", el: "section-new" },
  { id: "relevant", el: "section-relevant" },
  { id: "fading", el: "section-fading" },
];

async function loadSection(section, offset = 0) {
  const container = document.getElementById(section.el);
  if (offset === 0) {
    container.innerHTML = `<p class="empty-state">Loading…</p>`;
  }

  try {
    const res = await fetch(`/api/topics?section=${section.id}&limit=${PAGE_SIZE}&offset=${offset}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (offset === 0 && data.topics.length === 0) {
      container.innerHTML = `<p class="empty-state">Nothing here yet.</p>`;
      return;
    }

    const cardsHtml = data.topics.map(renderCard).join("");
    if (offset === 0) {
      container.innerHTML = cardsHtml;
    } else {
      container.querySelector(".show-more-wrap")?.remove();
      container.insertAdjacentHTML("beforeend", cardsHtml);
    }

    if (data.has_more) {
      container.insertAdjacentHTML(
        "beforeend",
        `<div class="show-more-wrap"><button type="button" class="show-more">Show more</button></div>`
      );
      container.querySelector(".show-more").addEventListener("click", () => {
        loadSection(section, offset + PAGE_SIZE);
      });
    }
  } catch (err) {
    container.innerHTML = `<p class="empty-state">Couldn't load this section (${err.message}).</p>`;
  }
}

function renderCard(topic) {
  return `
    <div class="card">
      <p class="card-title">
        <a class="card-title-link" href="/topic.html?id=${topic.topic_id}">${escapeHtml(topic.label)}</a>
      </p>
      <p class="card-meta">
        <span class="badge ${topic.trend_label}">${topic.trend_label}</span>
        &nbsp;${topic.current_count} mention${topic.current_count === 1 ? "" : "s"} this week
      </p>
      ${declineNote(topic)}
      <div class="sparkline">${renderSparkline(topic.sparkline)}</div>
      <ul class="recent-items">${renderRecentItems(topic.recent_items)}</ul>
    </div>`;
}

loadLastUpdated("last-updated");
SECTIONS.forEach((section) => loadSection(section));
