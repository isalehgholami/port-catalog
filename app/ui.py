"""The single-page web UI (vanilla JS, no CDN: works on air-gapped hosts)."""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Port catalog</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='3' fill='%230d1117'/%3E%3Cpath d='M3 4v8M6 4v8M9 4v8M12 4v8' stroke='%2358a6ff' stroke-width='1.6'/%3E%3Cpath d='M9 4v8' stroke='%233fb950' stroke-width='1.6'/%3E%3C/svg%3E">
<style>
:root{
  --bg:#0d1117; --card:#161b22; --line:#30363d; --fg:#c9d1d9; --muted:#8b949e;
  --accent:#58a6ff; --ok:#3fb950; --warn:#d29922; --bad:#f85149;
  --raised:#1c2128;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,"SF Mono","Cascadia Mono",Menlo,Consolas,"Liberation Mono",monospace;
}
*{box-sizing:border-box}
html{color-scheme:dark}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 var(--sans);-webkit-font-smoothing:antialiased}
a{color:var(--accent)}
button{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
.wrap{max-width:1280px;margin:0 auto;padding:20px 16px 64px}
.mono{font-family:var(--mono)}

header{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 16px;margin-bottom:16px}
h1{font-size:20px;font-weight:650;margin:0;letter-spacing:-.01em}
.meta{color:var(--muted);font-size:13px}
.meta b{color:var(--fg);font-weight:500}
.live{margin-left:auto;display:flex;align-items:center;gap:8px;color:var(--muted);font-size:13px}
.live i{width:7px;height:7px;border-radius:50%;background:var(--ok);display:inline-block}
.live.stale i{background:var(--bad)}
.live button{background:none;border:1px solid var(--line);border-radius:6px;padding:2px 10px;cursor:pointer;color:var(--muted)}
.live button:hover{color:var(--fg);border-color:var(--muted)}

/* chips */
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}
.chip{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border:1px solid var(--line);background:var(--card);border-radius:999px;font-size:13px}
.chip.bad{color:var(--bad);border-color:#f8514955;background:#f8514912}
.chip.good{color:var(--ok);border-color:#3fb95055;background:#3fb95012}
.chip.err{color:var(--bad);border-color:#f8514955;background:#f8514912}
.chip button{font-family:var(--mono);background:var(--raised);border:1px solid var(--line);border-radius:5px;padding:0 6px;cursor:pointer;color:var(--ok)}
.chip button:hover{border-color:var(--ok)}

/* the port strip */
.strip{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px 10px;margin-bottom:20px}
.strip-head{display:flex;flex-wrap:wrap;gap:4px 16px;align-items:baseline;margin-bottom:8px}
.strip-head h2{font-size:14px;margin:0;font-weight:600}
.legend{display:flex;gap:12px;color:var(--muted);font-size:12px;margin-left:auto}
.legend span{display:inline-flex;align-items:center;gap:5px}
.legend s{width:10px;height:10px;border-radius:2px;display:inline-block;text-decoration:none}
.cells{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:2px;height:34px}
.cell{border:0;padding:0;border-radius:2px;background:#21262d;cursor:pointer;min-width:0}
.cell.used{background:var(--accent)}
.cell.exposed{background:var(--bad)}
.cell.next{background:var(--ok)}
.cell:hover{filter:brightness(1.35);outline:1px solid var(--fg)}
.scale{display:flex;justify-content:space-between;color:var(--muted);font:11px var(--mono);margin-top:5px}
.tip{min-height:20px;margin-top:6px;color:var(--muted);font-size:12.5px}
.tip b{color:var(--fg);font-family:var(--mono);font-weight:500}

/* toolbar */
.toolbar{display:flex;gap:10px;align-items:center;margin-bottom:12px}
.search{flex:1;display:flex;align-items:center;gap:8px;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:0 12px}
.search:focus-within{border-color:var(--accent)}
.search input{flex:1;background:none;border:0;color:var(--fg);font:inherit;padding:9px 0;outline:0;min-width:0}
.search kbd{font:11px var(--mono);color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 5px}
.count{color:var(--muted);font-size:13px;white-space:nowrap}

/* tables */
section.group{margin-bottom:22px}
.ghead{display:flex;align-items:baseline;gap:10px;margin:0 0 6px;padding:0 2px}
.ghead h3{margin:0;font-size:15px;font-weight:600}
.ghead span{color:var(--muted);font-size:12.5px}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:8px;background:var(--card)}
table{width:100%;border-collapse:collapse;min-width:860px}
th{text-align:left;font-weight:500;color:var(--muted);font-size:12.5px;padding:7px 12px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:9px 12px;border-bottom:1px solid #21262d;vertical-align:top}
tr:last-child td{border-bottom:0}
th:nth-child(4),td:nth-child(4){min-width:190px}
th:nth-child(8),td:nth-child(8){min-width:300px}
td .mono{overflow-wrap:anywhere}
tbody tr:hover{background:#1a2029}
td.port button{font:600 15px var(--mono);background:none;border:0;padding:0;color:var(--accent);cursor:pointer}
td.port button:hover{text-decoration:underline}
td.arrow{color:var(--muted);padding-left:0;padding-right:0;width:1%}
.sub{color:var(--muted);font-size:12.5px}
.tag{display:inline-block;font:12px var(--mono);padding:0 7px;border-radius:5px;border:1px solid var(--line);margin:0 4px 2px 0;white-space:nowrap}
.tag.warn{color:var(--warn);border-color:#d2992266;background:#d2992214}
.tag.ok{color:var(--ok);border-color:#3fb95066;background:#3fb95014}
.tag.info{color:var(--muted)}
.tag.bad{color:var(--bad);border-color:#f8514966}
.dash{color:#484f58}
ul.notes{list-style:none;margin:0;padding:0}
ul.notes li{display:flex;gap:8px;font-size:13px;margin-bottom:3px}
ul.notes li:before{content:"";flex:none;width:7px;height:7px;border-radius:50%;margin-top:7px;background:var(--muted)}
ul.notes li.ok:before{background:var(--ok)}
ul.notes li.warn:before{background:var(--warn)}
ul.notes li.warn{color:#e3b341}
.ann{display:flex;gap:8px;align-items:baseline;margin-top:4px}
.ann q{quotes:none;color:var(--fg);background:var(--raised);border-left:2px solid var(--accent);padding:0 8px;border-radius:0 4px 4px 0}
.link{background:none;border:0;padding:0;color:var(--accent);cursor:pointer;font-size:12.5px}
.link:hover{text-decoration:underline}
details.extra{margin-top:8px}
details.extra summary{cursor:pointer;color:var(--muted);padding:4px 2px}
details.extra summary:hover{color:var(--fg)}
.empty{border:1px dashed var(--line);border-radius:8px;padding:28px;text-align:center;color:var(--muted)}
.empty b{display:block;color:var(--fg);margin-bottom:4px}

#toast{position:fixed;left:50%;bottom:24px;transform:translate(-50%,16px);background:var(--raised);border:1px solid var(--line);padding:7px 14px;border-radius:8px;opacity:0;pointer-events:none;transition:opacity .15s,transform .15s;font-size:13px}
#toast.on{opacity:1;transform:translate(-50%,0)}
@media (prefers-reduced-motion:reduce){#toast{transition:none}}
@media (max-width:640px){.live{margin-left:0}.legend{margin-left:0}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Port catalog</h1>
    <div class="meta" id="meta"></div>
    <div class="live" id="live"><i></i><span id="livetxt">loading…</span><button id="refresh" type="button">Refresh</button></div>
  </header>
  <div class="chips" id="chips"></div>
  <div class="strip" id="stripbox" hidden>
    <div class="strip-head">
      <h2>Port range <span class="mono" id="rangetxt"></span></h2>
      <div class="legend">
        <span><s style="background:#21262d"></s>free</span>
        <span><s style="background:var(--accent)"></s>in use</span>
        <span><s style="background:var(--bad)"></s>exposed publicly</span>
        <span><s style="background:var(--ok)"></s>suggested</span>
      </div>
    </div>
    <div class="cells" id="cells"></div>
    <div class="scale" id="scale"></div>
    <div class="tip" id="tip">Hover the map to inspect a block. Click to copy its first free port.</div>
  </div>
  <div class="toolbar">
    <label class="search"><span class="sub" aria-hidden="true">Filter</span>
      <input id="q" type="search" placeholder="Project, port, image, domain, note…" autocomplete="off" aria-label="Filter ports">
      <kbd>/</kbd></label>
    <div class="count" id="count"></div>
  </div>
  <main id="main"></main>
</div>
<div id="toast" role="status" aria-live="polite"></div>
<script>
"use strict";
const EXT = new Set(["", "0.0.0.0", "::", "*"]);
let DATA = null, TOKEN = "";
try { TOKEN = sessionStorage.getItem("pc-token") || ""; } catch (e) {}
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const isExt = ip => EXT.has(ip == null ? "" : ip);
const dash = '<span class="dash">—</span>';

let toastT;
function toast(msg) {
  const t = $("toast"); t.textContent = msg; t.classList.add("on");
  clearTimeout(toastT); toastT = setTimeout(() => t.classList.remove("on"), 1600);
}
async function copy(text) {
  try { await navigator.clipboard.writeText(String(text)); }
  catch (e) {
    const a = document.createElement("textarea"); a.value = text; document.body.appendChild(a);
    a.select(); try { document.execCommand("copy"); } catch (e2) {} a.remove();
  }
  toast("Copied " + text);
}

async function api(path, opts) {
  opts = opts || {}; opts.headers = Object.assign({}, opts.headers);
  if (TOKEN) opts.headers.Authorization = "Bearer " + TOKEN;
  let r = await fetch(path, opts);
  if (r.status === 401) {
    const t = prompt("This catalog needs an access token:");
    if (!t) throw new Error("Access token required");
    TOKEN = t; try { sessionStorage.setItem("pc-token", t); } catch (e) {}
    opts.headers.Authorization = "Bearer " + TOKEN;
    r = await fetch(path, opts);
  }
  if (!r.ok) throw new Error("Request failed (" + r.status + ")");
  return r.json();
}

async function load() {
  try {
    DATA = await api("/api/catalog");
    $("live").classList.remove("stale");
    render();
  } catch (e) {
    $("live").classList.add("stale");
    $("livetxt").textContent = e.message + " — retrying every 30s";
  }
}

function renderChips(d) {
  const exposed = d.port_rows.filter(r => r.origin === "docker" && isExt(r.bind_ip));
  let h = '<span class="chip"><b>' + d.port_rows.length + '</b> ports</span>';
  h += exposed.length
    ? '<span class="chip bad" title="Docker bypasses UFW for published ports"><b>' + exposed.length + '</b> exposed publicly</span>'
    : '<span class="chip good">Nothing exposed publicly</span>';
  if (d.next_free_ports.length) {
    h += '<span class="chip">Next free ' + d.next_free_ports.slice(0, 5).map(p =>
      '<button type="button" data-copy="' + p + '" title="Copy ' + p + '">' + p + '</button>').join("") + '</span>';
  }
  Object.entries(d.errors).forEach(([k, v]) => { if (v) h += '<span class="chip err">' + esc(k) + ': ' + esc(v) + '</span>'; });
  $("chips").innerHTML = h;
}

function renderStrip(d) {
  const [a, b] = d.port_range, span = b - a + 1;
  if (span < 1) { $("stripbox").hidden = true; return; }
  $("stripbox").hidden = false;
  $("rangetxt").textContent = a + "–" + b;
  const n = Math.min(100, span), size = Math.ceil(span / n), cells = Math.ceil(span / size);
  const owner = {}, exposed = new Set();
  d.port_rows.forEach(r => {
    owner[r.host_port] = r;
    if (r.origin === "docker" && isExt(r.bind_ip)) exposed.add(r.host_port);
  });
  const used = new Set(d.used_ports), next = new Set(d.next_free_ports);
  let h = "";
  for (let i = 0; i < cells; i++) {
    const lo = a + i * size, hi = Math.min(b, lo + size - 1);
    let u = 0, ex = 0, nx = 0, firstFree = null;
    for (let p = lo; p <= hi; p++) {
      if (used.has(p)) u++; else if (firstFree === null) firstFree = p;
      if (exposed.has(p)) ex++;
      if (next.has(p)) nx++;
    }
    const cls = ex ? "exposed" : u ? "used" : nx ? "next" : "";
    h += '<button type="button" class="cell ' + cls + '" data-lo="' + lo + '" data-hi="' + hi +
      '" data-u="' + u + '" data-ex="' + ex + '" data-ff="' + (firstFree == null ? "" : firstFree) +
      '" aria-label="Ports ' + lo + ' to ' + hi + ': ' + u + ' in use"></button>';
  }
  $("cells").innerHTML = h;
  $("cells").style.gridTemplateColumns = "repeat(" + cells + ",1fr)";
  const marks = [a, a + Math.round(span / 4), a + Math.round(span / 2), a + Math.round(span * 3 / 4), b];
  $("scale").innerHTML = marks.map(m => "<span>" + m + "</span>").join("");
}

function groupKey(r) {
  if (r.origin !== "docker") return "host services (non-docker)";
  return r.project || "docker, no compose project";
}

function rowText(r) {
  return JSON.stringify(r).toLowerCase();
}

function rowHtml(r) {
  const ext = isExt(r.bind_ip), docker = r.origin === "docker";
  const bind = r.bind_ip || (docker ? "0.0.0.0" : "—");
  const cont = r.container
    ? '<div class="mono">' + esc(r.container) + (r.host_network ? ' <span class="tag info">host network</span>' : "") + '</div>' +
      '<div class="sub">' + esc([r.service, r.image].filter(Boolean).join(" · ")) + '</div>'
    : dash;
  const bindTag = '<span class="tag ' + (ext ? "warn" : "ok") + '">' + esc(bind) + '</span>';
  const ufw = r.ufw.length ? '<span class="tag ok" title="' + esc(r.ufw.map(u => u.action + " " + u.proto + " from " + u.src).join("; ")) + '">yes</span>' : dash;
  const ngx = r.nginx.length ? r.nginx.map(n => '<span class="tag ok" title="' + esc(n.upstream) + '">' + esc(n.server) + '</span>').join("") : dash;
  const notes = '<ul class="notes">' + r.notes.map(n => '<li class="' + esc(n.level) + '">' + esc(n.text) + '</li>').join("") + '</ul>';
  const ann = '<div class="ann">' + (r.annotation ? '<q>' + esc(r.annotation) + '</q>' : "") +
    '<button class="link" type="button" data-annotate="' + r.host_port + '">' + (r.annotation ? "Edit note" : "Add note") + '</button></div>';
  return '<tr><td class="port"><button type="button" data-copy="' + r.host_port + '" title="Copy port">' + r.host_port + '</button></td>' +
    '<td class="arrow">→</td><td class="mono">' + (r.container_port ? esc(r.container_port) : dash) + '</td>' +
    '<td>' + cont + '</td><td>' + bindTag + '</td><td>' + ufw + '</td><td>' + ngx + '</td><td>' + notes + ann + '</td></tr>';
}

function render() {
  const d = DATA, q = $("q").value.trim().toLowerCase();
  $("meta").innerHTML = '<b>' + esc(d.host) + '</b> · ' + esc(d.generated_at.replace("T", " "));
  $("livetxt").textContent = "Auto-refresh 30s";
  renderChips(d); renderStrip(d);

  const rows = d.port_rows.filter(r => !q || rowText(r).includes(q));
  $("count").textContent = rows.length + (q ? " of " + d.port_rows.length : "") + " ports";
  const groups = new Map();
  rows.forEach(r => { const k = groupKey(r); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(r); });
  const order = [...groups.keys()].sort((x, y) => {
    const w = k => k === "host services (non-docker)" ? 2 : k === "docker, no compose project" ? 1 : 0;
    return w(x) - w(y) || x.localeCompare(y);
  });

  let h = "";
  if (!rows.length) {
    h = q ? '<div class="empty"><b>No ports match “' + esc(q) + '”</b>Try a port number, project or domain.</div>'
          : '<div class="empty"><b>No ports found</b>Start a container with a published port, or check the error chips above.</div>';
  }
  order.forEach(k => {
    const list = groups.get(k), dir = (list.find(r => r.compose_dir) || {}).compose_dir;
    h += '<section class="group"><div class="ghead"><h3>' + esc(k) + '</h3><span>' + list.length + (list.length === 1 ? " port" : " ports") +
      (dir ? ' · <span class="mono">' + esc(dir) + '</span>' : "") + '</span></div><div class="tw"><table><thead><tr>' +
      '<th>Host port</th><th></th><th>Container port</th><th>Container</th><th>Bind IP</th><th>UFW</th><th>Nginx</th><th>Notes</th></tr></thead><tbody>' +
      list.map(rowHtml).join("") + '</tbody></table></div></section>';
  });

  const quiet = d.containers.filter(c => !c.ports.some(p => p.host_port) && (!q || JSON.stringify(c).toLowerCase().includes(q)));
  if (quiet.length) {
    h += '<details class="extra"' + (q ? " open" : "") + '><summary>' + quiet.length + ' container' + (quiet.length === 1 ? "" : "s") + ' without published ports</summary>' +
      '<div class="tw"><table><thead><tr><th>Container</th><th>State</th><th>Exposed ports</th><th>Networks</th></tr></thead><tbody>' +
      quiet.map(c => '<tr><td><div class="mono">' + esc(c.name) + (c.host_network ? ' <span class="tag info">host network</span>' : "") + '</div><div class="sub">' +
        esc([c.compose_project, c.compose_service, c.image].filter(Boolean).join(" · ")) + '</div></td><td>' + esc(c.state) + '</td><td>' +
        (c.ports.length ? c.ports.map(p => '<span class="tag">' + esc(p.container_port) + '</span>').join("") : dash) + '</td><td>' +
        (Object.keys(c.networks).length ? Object.entries(c.networks).map(([n, ip]) => '<span class="tag" title="' + esc(ip) + '">' + esc(n) + '</span>').join("") : dash) +
        '</td></tr>').join("") + '</tbody></table></div></details>';
  }
  $("main").innerHTML = h;
}

document.addEventListener("click", async e => {
  const t = e.target.closest("[data-copy],[data-annotate],.cell");
  if (!t) return;
  if (t.dataset.copy) return copy(t.dataset.copy);
  if (t.classList.contains("cell")) {
    return t.dataset.ff ? copy(t.dataset.ff) : toast("No free port in " + t.dataset.lo + "–" + t.dataset.hi);
  }
  const port = t.dataset.annotate, row = DATA.port_rows.find(r => String(r.host_port) === port);
  const text = prompt("Note for port " + port + " (leave empty to remove):", (row && row.annotation) || "");
  if (text === null) return;
  try {
    await api("/api/annotations", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({port, text})});
    toast(text.trim() ? "Saved note for " + port : "Removed note for " + port);
    load();
  } catch (err) { toast(err.message); }
});

$("cells").addEventListener("mouseover", e => {
  const c = e.target.closest(".cell"); if (!c) return;
  const u = +c.dataset.u, ex = +c.dataset.ex;
  $("tip").innerHTML = '<b>' + c.dataset.lo + '–' + c.dataset.hi + '</b> · ' + u + ' in use' +
    (ex ? ', <span style="color:var(--bad)">' + ex + ' exposed</span>' : "") +
    (c.dataset.ff ? ' · first free <b>' + c.dataset.ff + '</b>' : " · full");
});
$("q").addEventListener("input", () => DATA && render());
$("refresh").addEventListener("click", load);
document.addEventListener("keydown", e => {
  if (e.key === "/" && !/input|textarea/i.test(document.activeElement.tagName)) { e.preventDefault(); $("q").focus(); }
  if (e.key === "Escape" && document.activeElement === $("q")) { $("q").value = ""; $("q").blur(); DATA && render(); }
});
load(); setInterval(load, 30000);
</script>
</body>
</html>
"""
