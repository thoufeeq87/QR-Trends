const SECTIONS = [
  { id: "new", el: "section-new" },
  { id: "relevant", el: "section-relevant" },
  { id: "fading", el: "section-fading" },
];

async function loadSection(section) {
  const container = document.getElementById(section.el);
  try {
    const res = await fetch(`/api/topics?section=${section.id}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const topics = await res.json();
    if (topics.length === 0) {
      container.innerHTML = `<p class="empty-state">Nothing here yet.</p>`;
      return;
    }
    container.innerHTML = topics.map(renderCard).join("");
  } catch (err) {
    container.innerHTML = `<p class="empty-state">Couldn't load this section (${err.message}).</p>`;
  }
}

function renderCard(topic) {
  const recentItems = topic.recent_items
    .map(
      (item) => `
        <li>
          <a href="${escapeAttr(item.url)}" target="_blank" rel="noopener">${escapeHtml(item.title)}</a>
          <span class="source">— ${escapeHtml(item.source_name)}</span>
        </li>`
    )
    .join("");

  return `
    <div class="card">
      <p class="card-title">${escapeHtml(topic.label)}</p>
      <p class="card-meta">
        <span class="badge ${topic.trend_label}">${topic.trend_label}</span>
        &nbsp;${topic.current_count} mention${topic.current_count === 1 ? "" : "s"} this week
      </p>
      <div class="sparkline">${renderSparkline(topic.sparkline)}</div>
      <ul class="recent-items">${recentItems}</ul>
    </div>`;
}

function renderSparkline(points) {
  if (!points || points.length === 0) return "";
  const width = 240;
  const height = 36;
  const max = Math.max(1, ...points.map((p) => p.count));
  const step = points.length > 1 ? width / (points.length - 1) : 0;

  const coords = points.map((p, i) => {
    const x = i * step;
    const y = height - (p.count / max) * (height - 4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return `
    <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="mentions per week">
      <polyline fill="none" stroke="currentColor" stroke-width="2" points="${coords.join(" ")}" />
    </svg>`;
}

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function escapeAttr(str) {
  return escapeHtml(str);
}

SECTIONS.forEach(loadSection);
