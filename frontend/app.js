const API = ""; // same origin (the FastAPI server also serves this frontend)
const STATUSES = ["applied", "interviewing", "offered", "rejected"];
const LABELS = { applied: "Applied", interviewing: "Interviewing", offered: "Offered", rejected: "Rejected" };

const $ = (sel, root = document) => root.querySelector(sel);
let token = localStorage.getItem("jat_token");
let user = JSON.parse(localStorage.getItem("jat_user") || "null");
let applications = [];
let editingId = null;
let uploadTargetId = null;
let pendingEmail = null;

/* ---------- helpers ---------- */
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

let toastTimer;
function toast(message, isError = false) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 3500);
}

async function api(path, { method = "GET", body, form, raw = false } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(API + path, { method, headers, body: payload });
  if (res.status === 401 && token) {
    logout();
    throw new Error("Session expired. Please log in again.");
  }
  if (!res.ok) {
    let detail = "Something went wrong.";
    try {
      const data = await res.json();
      detail = Array.isArray(data.detail) ? data.detail.map((e) => e.msg).join(", ") : data.detail || detail;
    } catch (_) { /* non-JSON error */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return raw ? res : res.json();
}

function guard(fn) {
  return async (...args) => {
    try { await fn(...args); } catch (err) { toast(err.message, true); }
  };
}

/* ---------- views ---------- */
function showAuth() {
  $("#app-view").hidden = true;
  $("#auth-view").hidden = false;
  showTab("login");
}

function showApp() {
  $("#auth-view").hidden = true;
  $("#app-view").hidden = false;
  $("#user-name").textContent = user ? user.name : "";
  refresh();
}

function logout() {
  token = null; user = null;
  localStorage.removeItem("jat_token");
  localStorage.removeItem("jat_user");
  showAuth();
}

/* ---------- auth ---------- */
function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $("#login-form").hidden = name !== "login";
  $("#signup-form").hidden = name !== "signup";
  $("#otp-form").hidden = name !== "otp";
  $(".tabs").hidden = name === "otp";
}

async function sendOtp(email) {
  const res = await api("/auth/send-otp", { method: "POST", body: { email } });
  pendingEmail = email;
  $("#otp-msg").textContent = res.dev_otp
    ? `Dev mode (no SMTP configured): your code is ${res.dev_otp}`
    : `We sent a 6-digit code to ${email}.`;
  showTab("otp");
}

document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => showTab(t.dataset.tab)));

$("#signup-form").addEventListener("submit", guard(async (e) => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  await api("/auth/signup", { method: "POST", body: f });
  await sendOtp(f.email);
}));

$("#otp-form").addEventListener("submit", guard(async (e) => {
  e.preventDefault();
  const otp = new FormData(e.target).get("otp");
  await api("/auth/verify-otp", { method: "POST", body: { email: pendingEmail, otp } });
  toast("Email verified - you can log in now.");
  e.target.reset();
  showTab("login");
  $("#login-form [name=email]").value = pendingEmail;
}));

$("#resend-otp").addEventListener("click", guard(() => sendOtp(pendingEmail)));

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = Object.fromEntries(new FormData(e.target));
  try {
    const res = await api("/auth/login", { method: "POST", body: f });
    token = res.access_token; user = res.user;
    localStorage.setItem("jat_token", token);
    localStorage.setItem("jat_user", JSON.stringify(user));
    e.target.reset();
    showApp();
  } catch (err) {
    if (err.status === 403) {          // account exists but email not verified yet
      try { await sendOtp(f.email); } catch (e2) { toast(e2.message, true); }
    } else toast(err.message, true);
  }
});

$("#logout").addEventListener("click", logout);

/* ---------- dashboard ---------- */
async function refresh() {
  const params = new URLSearchParams({ limit: "100" });
  const search = $("#search").value.trim();
  const status = $("#status-filter").value;
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  const [stats, list] = await Promise.all([api("/applications/stats"), api(`/applications?${params}`)]);
  applications = list.items;
  renderStats(stats);
  renderBoard();
}

function renderStats(s) {
  const items = [
    ["Total applications", s.total],
    ["Active (applied + interviewing)", s.active],
    ["Offers", s.by_status.offered],
    ["Offer rate", `${s.offer_rate}%`],
  ];
  $("#stats").innerHTML = items.map(([label, value]) =>
    `<div class="stat"><b>${esc(value)}</b><span class="muted">${esc(label)}</span></div>`).join("");
}

function formatSalary(range) {
  if (!range || (range.min == null && range.max == null)) return "";
  const fmt = (n) => (n == null ? "?" : Number(n).toLocaleString("en-IN"));
  return `${fmt(range.min)} – ${fmt(range.max)}`;
}

function cardHtml(a) {
  const salary = formatSalary(a.salary_range);
  const date = a.applied_date ? new Date(a.applied_date).toLocaleDateString() : "";
  const meta = [a.location, salary, date].filter(Boolean).map(esc).join(" · ");
  const options = STATUSES.map((s) =>
    `<option value="${s}" ${s === a.status ? "selected" : ""}>${LABELS[s]}</option>`).join("");
  const link = a.job_url && /^https?:\/\//i.test(a.job_url)
    ? `<a href="${esc(a.job_url)}" target="_blank" rel="noopener noreferrer">View job posting</a>` : "";
  const resume = a.has_resume
    ? `<button class="btn small" data-action="download" data-id="${a.id}">Resume ↓</button>
       <button class="btn small" data-action="upload" data-id="${a.id}">Replace</button>`
    : `<button class="btn small" data-action="upload" data-id="${a.id}">Upload resume</button>`;
  return `<div class="card">
    <h4>${esc(a.position)}</h4>
    <div>${esc(a.company)}</div>
    <div class="meta">${meta}</div>
    ${link}
    ${a.notes ? `<div class="notes">${esc(a.notes)}</div>` : ""}
    <div class="actions">
      <select data-action="status" data-id="${a.id}" aria-label="Change status">${options}</select>
      ${resume}
      <button class="btn small" data-action="edit" data-id="${a.id}">Edit</button>
      <button class="btn small danger" data-action="delete" data-id="${a.id}">Delete</button>
    </div>
  </div>`;
}

function renderBoard() {
  $("#board").innerHTML = STATUSES.map((s) => {
    const items = applications.filter((a) => a.status === s);
    return `<div class="column">
      <h3><span><span class="dot" style="background:var(--${s})"></span>${LABELS[s]}</span><span>${items.length}</span></h3>
      ${items.map(cardHtml).join("") || '<div class="empty">Nothing here yet</div>'}
    </div>`;
  }).join("");
}

/* board actions (event delegation) */
$("#board").addEventListener("click", guard(async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  const { action, id } = btn.dataset;
  if (action === "edit") openDialog(applications.find((a) => a.id === id));
  else if (action === "upload") { uploadTargetId = id; $("#resume-input").click(); }
  else if (action === "download") await downloadResume(id);
  else if (action === "delete") {
    if (!confirm("Delete this application and its resume?")) return;
    await api(`/applications/${id}`, { method: "DELETE" });
    toast("Application deleted.");
    await refresh();
  }
}));

$("#board").addEventListener("change", guard(async (e) => {
  const sel = e.target.closest("select[data-action=status]");
  if (!sel) return;
  await api(`/applications/${sel.dataset.id}/status`, { method: "PATCH", body: { status: sel.value } });
  await refresh();
}));

$("#resume-input").addEventListener("change", guard(async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file || !uploadTargetId) return;
  const form = new FormData();
  form.append("file", file);
  await api(`/applications/${uploadTargetId}/resume`, { method: "POST", form });
  toast("Resume uploaded.");
  await refresh();
}));

async function downloadResume(id) {
  const res = await api(`/applications/${id}/resume`, { raw: true });
  const blob = await res.blob();
  const a = applications.find((x) => x.id === id);
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = (a && a.resume_filename) || "resume.pdf";
  link.click();
  URL.revokeObjectURL(link.href);
}

/* search + filter */
let searchTimer;
$("#search").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(guard(refresh), 300);
});
$("#status-filter").addEventListener("change", guard(refresh));

/* ---------- add / edit dialog ---------- */
function openDialog(app = null) {
  editingId = app ? app.id : null;
  const form = $("#app-form");
  form.reset();
  $("#dialog-title").textContent = app ? "Edit application" : "Add application";
  if (app) {
    form.company.value = app.company;
    form.position.value = app.position;
    form.location.value = app.location || "";
    form.status.value = app.status;
    form.salary_min.value = app.salary_range?.min ?? "";
    form.salary_max.value = app.salary_range?.max ?? "";
    form.applied_date.value = app.applied_date ? app.applied_date.slice(0, 10) : "";
    form.job_url.value = app.job_url || "";
    form.notes.value = app.notes || "";
  } else {
    form.applied_date.value = new Date().toISOString().slice(0, 10);
  }
  $("#app-dialog").showModal();
}

$("#add-btn").addEventListener("click", () => openDialog());
$("#cancel-dialog").addEventListener("click", () => $("#app-dialog").close());

$("#app-form").addEventListener("submit", guard(async (e) => {
  e.preventDefault();
  const f = e.target;
  const num = (v) => (v === "" ? null : Number(v));
  const min = num(f.salary_min.value), max = num(f.salary_max.value);
  if (min != null && max != null && min > max) throw new Error("Salary min cannot exceed max.");
  const body = {
    company: f.company.value.trim(),
    position: f.position.value.trim(),
    location: f.location.value.trim(),
    status: f.status.value,
    salary_range: min == null && max == null ? null : { min, max },
    applied_date: f.applied_date.value ? `${f.applied_date.value}T00:00:00Z` : null,
    job_url: f.job_url.value.trim() || null,
    notes: f.notes.value.trim() || null,
  };
  if (editingId) await api(`/applications/${editingId}`, { method: "PUT", body });
  else await api("/applications", { method: "POST", body });
  $("#app-dialog").close();
  toast(editingId ? "Application updated." : "Application added.");
  await refresh();
}));

/* ---------- boot ---------- */
if (token) showApp(); else showAuth();
