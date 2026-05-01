const state = {
  data: null,
  search: "",
};

const els = {
  search: document.querySelector("#searchInput"),
  jump: document.querySelector("#jumpSelect"),
  list: document.querySelector("#scheduleList"),
  title: document.querySelector("#resultsTitle"),
};

function formatCategory(category) {
  const labels = {
    core: "Core",
    stride: "Stride",
    trifecta: "TS60 Trifecta",
  };
  return labels[category] || category;
}

function formatPeriod(period) {
  const [year, month] = period.split("-").map(Number);
  return new Date(year, month - 1, 1).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });
}

function scheduleAnchorId(schedule) {
  return `schedule-${schedule.id}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function matchesSearch(schedule, entry, needle) {
  if (!needle) return true;
  const haystack = [
    schedule.title,
    schedule.period,
    entry.groupTitle,
    entry.week ? `week ${entry.week}` : "",
    entry.dayLabel,
    entry.workout,
    entry.workoutType,
    entry.classDateDisplay,
    entry.instructor,
    entry.startTime,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(needle);
}

function sortSchedulesForDisplay(schedules) {
  const categoryOrder = { trifecta: 0, core: 1, stride: 2 };
  return [...schedules].sort((a, b) => {
    const categoryDelta = (categoryOrder[a.category] ?? 99) - (categoryOrder[b.category] ?? 99);
    if (categoryDelta) return categoryDelta;
    return a.period.localeCompare(b.period) || a.title.localeCompare(b.title);
  });
}

function filteredSchedules() {
  const needle = state.search.trim().toLowerCase();
  return sortSchedulesForDisplay(state.data.schedules)
    .map((schedule) => ({
      ...schedule,
      groups: schedule.groups
        .map((group) => ({
          ...group,
          entries: group.entries.filter((entry) => matchesSearch(schedule, entry, needle)),
        }))
        .filter((group) => group.entries.length),
    }))
    .filter((schedule) => schedule.groups.length);
}

function jumpLabel(schedule) {
  if (schedule.category === "trifecta") return formatPeriod(schedule.period);
  return schedule.title;
}

function renderJumpSelect() {
  const categories = ["trifecta", "core", "stride"];
  els.jump.innerHTML = [
    '<option value="">Choose section...</option>',
    ...categories.map((category) => {
      const schedules = sortSchedulesForDisplay(state.data.schedules).filter((schedule) => schedule.category === category);
      if (!schedules.length) return "";
      return `
        <optgroup label="${escapeHtml(formatCategory(category))}">
          ${schedules
            .map(
              (schedule) =>
                `<option value="${escapeHtml(schedule.id)}">${escapeHtml(jumpLabel(schedule))}</option>`,
            )
            .join("")}
        </optgroup>
      `;
    }),
  ].join("");
}

function groupEntriesByWeek(entries) {
  return entries.reduce((weeks, entry) => {
    let key = entry.week ? `Week ${entry.week}` : "Daily";
    if (!entry.week && entry.startTime && entry.scheduledDate) {
      const date = new Date(`${entry.scheduledDate}T12:00:00`);
      key = date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    }
    if (!weeks.has(key)) weeks.set(key, []);
    weeks.get(key).push(entry);
    return weeks;
  }, new Map());
}

function entryDayLabel(entry) {
  if (entry.startTime) return entry.startTime;
  if (entry.scheduledDate) {
    const date = new Date(`${entry.scheduledDate}T12:00:00`);
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }
  if (entry.dayLabel) return entry.dayLabel;
  if (entry.day) return `Day ${entry.day}`;
  return "";
}

function renderEntry(entry) {
  const link = entry.url
    ? `<a class="workout-link" href="${escapeHtml(entry.url)}" target="_blank" rel="noopener">Open</a>`
    : `<span class="missing-link">${entry.linkStatus === "tbd" ? "TBD" : "No link"}</span>`;
  const dayLabel = entryDayLabel(entry);
  const dayTag = dayLabel ? `<span class="day-tag">${escapeHtml(dayLabel)}</span>` : "";

  return `
    <div class="workout-row${dayLabel ? " has-day-tag" : ""}">
      ${dayTag}
      <div>
        <div class="workout-title">${escapeHtml(entry.workout)}</div>
      </div>
      ${link}
    </div>
  `;
}

function renderGroup(group, schedule) {
  const weeks = groupEntriesByWeek(group.entries);
  const weekHtml = [...weeks.entries()]
    .map(
      ([week, entries]) => `
        <div class="week-block">
          <span class="week-label">${escapeHtml(week)}</span>
          ${entries.map(renderEntry).join("")}
        </div>
      `,
    )
    .join("");

  const showGroupTitle = !(schedule.groups.length === 1 && group.title === "Main Schedule");

  return `
    <section class="group">
      ${showGroupTitle ? `<div class="group-title">${escapeHtml(group.title)}</div>` : ""}
      ${weekHtml}
    </section>
  `;
}

function renderSchedule(schedule) {
  const entries = schedule.groups.flatMap((group) => group.entries);
  const linked = entries.filter((entry) => entry.url).length;
  const categoryClass = schedule.category === "core" ? "gold" : schedule.category === "stride" ? "" : "red";
  return `
    <article class="schedule-card" id="${scheduleAnchorId(schedule)}">
      <header class="schedule-head">
        <div>
          <h3>${escapeHtml(schedule.title)}</h3>
          <div class="schedule-meta">
            <span class="pill ${categoryClass}">${formatCategory(schedule.category)}</span>
            <span class="pill">${formatPeriod(schedule.period)}</span>
            <span class="pill">${entries.length} workouts</span>
            <span class="pill">${linked} links</span>
          </div>
        </div>
      </header>
      ${schedule.groups.map((group) => renderGroup(group, schedule)).join("")}
    </article>
  `;
}

function renderResults() {
  const schedules = filteredSchedules();
  const entryCount = schedules.reduce(
    (total, schedule) => total + schedule.groups.reduce((sum, group) => sum + group.entries.length, 0),
    0,
  );
  els.title.textContent = `${schedules.length} schedules, ${entryCount} workouts`;
  els.list.innerHTML = schedules.length
    ? schedules.map(renderSchedule).join("")
    : '<div class="empty-state">No workouts match the current filters.</div>';
}

function renderAll() {
  renderResults();
}

function attachEvents() {
  els.search.addEventListener("input", (event) => {
    state.search = event.target.value;
    renderResults();
  });

  els.jump.addEventListener("change", (event) => {
    const scheduleId = event.target.value;
    if (!scheduleId) return;
    state.search = "";
    els.search.value = "";
    renderAll();
    els.jump.value = scheduleId;
    document.getElementById(scheduleAnchorId({ id: scheduleId }))?.scrollIntoView({
      block: "start",
      behavior: "smooth",
    });
  });
}

async function init() {
  try {
    const response = await fetch("data/schedules.json");
    if (!response.ok) throw new Error(`Failed to load schedule data: ${response.status}`);
    state.data = await response.json();
    renderJumpSelect();
    renderAll();
    attachEvents();
  } catch (error) {
    els.list.innerHTML = `<div class="empty-state">${escapeHtml(error.message)}</div>`;
  }
}

init();
