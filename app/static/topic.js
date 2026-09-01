async function loadTopic() {
  const id = new URLSearchParams(window.location.search).get("id");
  const titleEl = document.getElementById("topic-title");
  const metaEl = document.getElementById("topic-meta");
  const detailEl = document.getElementById("topic-detail");

  if (!id) {
    titleEl.textContent = "Topic not found";
    detailEl.innerHTML = `<p class="empty-state">No topic ID given.</p>`;
    return;
  }

  try {
    const res = await fetch(`/api/topics/${encodeURIComponent(id)}`);
    if (res.status === 404) {
      titleEl.textContent = "Topic not found";
      detailEl.innerHTML = `<p class="empty-state">This topic doesn't exist.</p>`;
      return;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const topic = await res.json();

    document.title = `QA Pulse — ${topic.label}`;
    titleEl.textContent = topic.label;
    metaEl.innerHTML = `
      <span class="badge ${topic.trend_label}">${topic.trend_label}</span>
      &nbsp;${topic.current_count} mention${topic.current_count === 1 ? "" : "s"} this week
      (was ${topic.prior_count} in the prior ~3 weeks)`;

    detailEl.innerHTML = `
      ${declineNote(topic)}
      <div class="sparkline">${renderSparkline(topic.sparkline, 480, 60)}</div>
      <h2>Recent items</h2>
      <ul class="recent-items">${renderRecentItems(topic.recent_items)}</ul>`;
  } catch (err) {
    titleEl.textContent = "Couldn't load topic";
    detailEl.innerHTML = `<p class="empty-state">${err.message}</p>`;
  }
}

loadTopic();
