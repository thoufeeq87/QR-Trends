function escapeHtml(str) {
  return str.replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function escapeAttr(str) {
  return escapeHtml(str);
}

function renderSparkline(points, width = 240, height = 36) {
  if (!points || points.length === 0) return "";
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

function renderRecentItems(items) {
  return items
    .map((item) => {
      // Prefer the AI-generated ~10-word summary; items tagged before this feature
      // shipped (or a rare empty summary) fall back to the raw title.
      const label = item.short_summary || item.title;
      return `
        <li>
          <a href="${escapeAttr(item.url)}" target="_blank" rel="noopener">${escapeHtml(label)}</a>
          <span class="source">— ${escapeHtml(item.source_name)}</span>
        </li>`;
    })
    .join("");
}

function declineNote(topic) {
  if (topic.trend_label !== "declining" || !topic.prior_count) return "";
  const priorWeeklyRate = Math.round((topic.prior_count * 7) / 23);
  return `<p class="decline-note">was ~${priorWeeklyRate}/week, now ${topic.current_count}</p>`;
}

function formatRelativeTime(isoString) {
  if (!isoString) return "never";
  const diffMs = Date.now() - new Date(isoString).getTime();
  const minutes = Math.round(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

async function loadLastUpdated(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  try {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const status = await res.json();
    el.textContent = `Last updated: ${formatRelativeTime(status.last_ingested_at)}`;
  } catch (err) {
    el.textContent = "";
  }
}
