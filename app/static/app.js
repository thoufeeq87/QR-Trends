const PAGE_SIZE = 30;
const DOMAIN_STORAGE_KEY = "qa-pulse-domain";

const SECTIONS = [
  { id: "new", el: "section-new" },
  { id: "relevant", el: "section-relevant" },
  { id: "fading", el: "section-fading" },
];

const DOMAIN_META = {
  qa: {
    title: "QA Pulse",
    subtitle: "What's trending, stable, or fading in software QA/testing.",
  },
  agents: {
    title: "AI Agent Pulse",
    subtitle: "What's trending, stable, or fading in AI agents / agentic AI.",
  },
};

function getStoredDomain() {
  try {
    const stored = localStorage.getItem(DOMAIN_STORAGE_KEY);
    return stored && DOMAIN_META[stored] ? stored : "qa";
  } catch (err) {
    return "qa";
  }
}

function setStoredDomain(domain) {
  try {
    localStorage.setItem(DOMAIN_STORAGE_KEY, domain);
  } catch (err) {
    // Private browsing / storage blocked — the dropdown still works for this load,
    // it just won't remember the choice next visit.
  }
}

function applyDomainHeader(domain) {
  const meta = DOMAIN_META[domain];
  document.title = meta.title;
  document.getElementById("page-title").textContent = meta.title;
  document.getElementById("page-subtitle").textContent = meta.subtitle;
}

async function loadSection(section, domain, offset = 0) {
  const container = document.getElementById(section.el);
  if (offset === 0) {
    container.innerHTML = `<p class="empty-state">Loading…</p>`;
  }

  try {
    const res = await fetch(
      `/api/topics?section=${section.id}&domain=${domain}&limit=${PAGE_SIZE}&offset=${offset}`
    );
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
        loadSection(section, domain, offset + PAGE_SIZE);
      });
    }
  } catch (err) {
    container.innerHTML = `<p class="empty-state">Couldn't load this section (${err.message}).</p>`;
  }
}

function loadDomain(domain) {
  applyDomainHeader(domain);
  loadLastUpdated("last-updated", domain);
  SECTIONS.forEach((section) => loadSection(section, domain));
}

function renderCard(topic) {
  return `
    <div class="card card--${topic.trend_label}">
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

const initialDomain = getStoredDomain();
const domainSelect = document.getElementById("domain-select");
domainSelect.value = initialDomain;
domainSelect.addEventListener("change", () => {
  const domain = domainSelect.value;
  setStoredDomain(domain);
  loadDomain(domain);
});

loadDomain(initialDomain);
