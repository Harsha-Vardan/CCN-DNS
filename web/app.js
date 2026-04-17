/* ═══════════════════════════════════════════════════════════════════════════
   DNS Resolution Service — Frontend Logic  (app.js)
   Talks to flask API on http://127.0.0.1:5000
   ═══════════════════════════════════════════════════════════════════════════ */

'use strict';

const API = 'http://127.0.0.1:5000';

// ─────────────────────────────────────────────────────────────────────────────
//  Tab switching
// ─────────────────────────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  document.getElementById('nav-' + name).classList.add('active');

  // Auto-load data for certain tabs
  if (name === 'cache')   loadCache();
  if (name === 'metrics') loadMetrics();
}

// ─────────────────────────────────────────────────────────────────────────────
//  Health check  (sidebar status indicator)
// ─────────────────────────────────────────────────────────────────────────────
async function checkHealth() {
  const dot  = document.querySelector('.dot');
  const text = document.getElementById('status-text');
  try {
    const r = await fetch(API + '/health', { signal: AbortSignal.timeout(3000) });
    const d = await r.json();
    if (d.binary_ok) {
      dot.className  = 'dot online';
      text.textContent = 'Online';
    } else {
      dot.className  = 'dot pulse';
      dot.style.background = 'var(--orange)';
      text.textContent = 'No binary';
    }
  } catch {
    dot.className  = 'dot offline';
    text.textContent = 'API offline';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  DNS Lookup
// ─────────────────────────────────────────────────────────────────────────────
async function resolveDNS() {
  const domain = document.getElementById('domain-input').value.trim();
  const qtype  = document.getElementById('type-select').value;
  const btn    = document.getElementById('resolve-btn');
  const label  = document.getElementById('resolve-btn-label');
  const out    = document.getElementById('lookup-result');

  if (!domain) { showError(out, 'Please enter a domain name.'); return; }

  btn.disabled   = true;
  label.innerHTML = '<span class="spinner"></span>';
  out.innerHTML   = '<div class="placeholder"><span class="placeholder-icon">⏳</span><p>Resolving…</p></div>';

  try {
    const resp = await fetch(`${API}/resolve?domain=${encodeURIComponent(domain)}&type=${qtype}`);
    const data = await resp.json();

    if (!resp.ok || data.error) {
      showError(out, data.error || 'Resolution failed.');
      return;
    }

    renderLookupResult(out, data);
  } catch (e) {
    showError(out, `Cannot reach API: ${e.message}. Is the Flask server running?`);
  } finally {
    btn.disabled    = false;
    label.textContent = 'Resolve';
  }
}

function quickResolve(domain) {
  document.getElementById('domain-input').value = domain;
  resolveDNS();
}

function renderLookupResult(container, data) {
  const cachedBadge = data.cached
    ? `<span class="result-badge badge-cached">⚡ Cached</span>`
    : `<span class="result-badge badge-network">🌐 Network</span>`;
  const tcpBadge = data.used_tcp
    ? `<span class="result-badge badge-tcp">🔗 TCP Fallback</span>` : '';
  const typeBadge = `<span class="result-badge badge-type">${esc(data.record_type)}</span>`;

  const answers = (data.answers || []).map(a => {
    let dataHtml = esc(String(a.data));
    if (a.type === 'A' || a.type === 'AAAA' || a.type === 'CNAME') {
      const targetUrl = (a.type === 'CNAME') ? esc(String(a.data)) : esc(a.name);
      dataHtml = `<a href="https://${targetUrl}" target="_blank" style="color: inherit; text-decoration: none; border-bottom: 1px dotted var(--accent); transition: color 0.15s;" onmouseover="this.style.color='var(--accent)'" onmouseout="this.style.color='inherit'" title="Open ${targetUrl}">${esc(String(a.data))}</a>`;
    }
    return `
    <div class="answer-card">
      <span class="answer-name" title="${esc(a.name)}">${esc(a.name)}</span>
      <span class="answer-type-badge">${esc(typeStr(a.type))}</span>
      <span class="answer-data">${dataHtml}</span>
      <span class="answer-ttl">TTL ${a.ttl ?? '—'}s</span>
    </div>`;
  }).join('');

  container.innerHTML = `
    <div class="result-meta">
      ${cachedBadge}${tcpBadge}${typeBadge}
      <span class="latency-display">⏱ <b>${data.latency_ms} ms</b></span>
    </div>
    <div class="answer-list">
      ${answers || '<div class="placeholder"><p>No answer records</p></div>'}
    </div>
    <details class="raw-json">
      <summary>Raw JSON response</summary>
      <pre>${esc(JSON.stringify(data, null, 2))}</pre>
    </details>`;
}

// ─────────────────────────────────────────────────────────────────────────────
//  Resolution Path Visualiser
// ─────────────────────────────────────────────────────────────────────────────
async function renderPath() {
  const domain = document.getElementById('path-domain').value.trim();
  const qtype  = document.getElementById('path-type').value;
  const out    = document.getElementById('path-output');

  if (!domain) { out.innerHTML = errorBox('Please enter a domain name.'); return; }
  out.innerHTML = '<div class="placeholder"><span class="spinner"></span><p>Resolving trace…</p></div>';

  try {
    const resp = await fetch(`${API}/resolve?domain=${encodeURIComponent(domain)}&type=${qtype}`);
    const data = await resp.json();

    if (!resp.ok || data.error) {
      out.innerHTML = errorBox(data.error || 'Resolution failed.'); return;
    }

    const path = data.resolution_path || [];
    const hops = path.map((ip, i) => {
      const role = i === 0 ? 'Root Server'
                 : i === path.length - 1 ? 'Authoritative NS'
                 : 'TLD / Intermediate NS';
      return `
        <div class="hop-item">
          <span class="hop-num">${i + 1}</span>
          <span class="hop-ip">${esc(ip)}</span>
          <span class="hop-role">${role}</span>
        </div>`;
    }).join('');

    const answer = (data.answers || [])[0];
    const resultLine = answer
      ? `<div class="hop-item" style="border-color:rgba(74,222,128,0.3);">
           <span class="hop-num" style="border-color:var(--green);color:var(--green);background:rgba(74,222,128,0.12);">✓</span>
           <span class="hop-ip" style="color:var(--green);">${esc(String(answer.data))}</span>
           <span class="hop-role">Answer — ${esc(typeStr(answer.type))} record</span>
         </div>` : '';

    out.innerHTML = `
      <div class="card-title">
        ${esc(domain)} &nbsp;→&nbsp; ${esc(data.record_type)}
        &nbsp;·&nbsp; ${path.length} hop${path.length !== 1 ? 's' : ''}
        &nbsp;·&nbsp; ${data.latency_ms} ms
        ${data.used_tcp ? '&nbsp;·&nbsp; <span style="color:var(--orange)">TCP fallback</span>' : ''}
      </div>

      <div class="path-flow">
        <div class="path-node">
          <div class="path-node-icon client">💻</div>
          <div class="path-node-info"><h4>Your Request</h4><p>${esc(domain)}</p></div>
        </div>
        <div class="path-arrow"></div>
        <div class="path-node">
          <div class="path-node-icon root">🌍</div>
          <div class="path-node-info"><h4>Root Server</h4><p>${path[0] || '—'}</p></div>
        </div>
        <div class="path-arrow"></div>
        <div class="path-node">
          <div class="path-node-icon tld">🔀</div>
          <div class="path-node-info"><h4>TLD / Delegation hops</h4><p>${path.length} nameservers queried</p></div>
        </div>
        <div class="path-arrow"></div>
        <div class="path-node">
          <div class="path-node-icon auth">🏛</div>
          <div class="path-node-info"><h4>Authoritative NS</h4><p>${path[path.length-1] || '—'}</p></div>
        </div>
      </div>

      <div class="card-title" style="margin-top:20px;">Server Hops</div>
      <div class="hop-list">${hops}${resultLine}</div>`;
  } catch (e) {
    out.innerHTML = errorBox(`Cannot reach API: ${e.message}`);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Cache
// ─────────────────────────────────────────────────────────────────────────────
async function loadCache() {
  const body    = document.getElementById('cache-body');
  try {
    const resp = await fetch(API + '/cache');
    const data = await resp.json();
    const s    = data.stats || {};

    document.getElementById('cs-size').textContent    = s.size   ?? '—';
    document.getElementById('cs-hits').textContent    = s.hits   ?? '—';
    document.getElementById('cs-misses').textContent  = s.misses ?? '—';
    document.getElementById('cs-hitrate').textContent = (s.hit_rate ?? '—') + '%';

    const entries = data.entries || [];
    if (entries.length === 0) {
      body.innerHTML = '<tr><td colspan="5" class="empty-row">Cache is empty</td></tr>';
      return;
    }

    body.innerHTML = entries.map(e => `
      <tr>
        <td class="mono">${esc(e.domain)}</td>
        <td><span class="answer-type-badge">${esc(e.type)}</span></td>
        <td class="mono">${esc(e.ip) || '—'}</td>
        <td class="mono">${e.remaining_ttl}s</td>
        <td class="${e.status === 'valid' ? 'tag-valid' : 'tag-expired'}">${e.status}</td>
      </tr>`).join('');
  } catch {
    body.innerHTML = '<tr><td colspan="5" class="empty-row" style="color:var(--red)">Could not load cache</td></tr>';
  }
}

async function clearCache() {
  if (!confirm('Clear all cached DNS records?')) return;
  await fetch(API + '/cache', { method: 'DELETE' });
  loadCache();
}

// ─────────────────────────────────────────────────────────────────────────────
//  Metrics
// ─────────────────────────────────────────────────────────────────────────────
async function loadMetrics() {
  try {
    const resp = await fetch(API + '/metrics');
    const m    = await resp.json();

    if (!m.total) {
      document.getElementById('m-total').textContent   = '0';
      document.getElementById('m-hitrate').textContent = '0 %';
      document.getElementById('m-avg').textContent     = '— ms';
      document.getElementById('m-minmax').textContent  = '— / —';
      document.getElementById('m-success').textContent = '— %';
      document.getElementById('m-tcp').textContent     = '—';
      document.getElementById('recent-body').innerHTML =
        '<tr><td colspan="5" class="empty-row">No queries yet</td></tr>';
      return;
    }

    document.getElementById('m-total').textContent   = m.total;
    document.getElementById('m-hitrate').textContent = m.cache_hit_rate + ' %';
    document.getElementById('m-avg').textContent     = m.avg_latency_ms + ' ms';
    document.getElementById('m-minmax').textContent  = m.min_latency_ms + ' / ' + m.max_latency_ms;
    const successPct = m.total > 0 ? Math.round(m.success / m.total * 100) : 0;
    document.getElementById('m-success').textContent = successPct + ' %';
    document.getElementById('m-tcp').textContent     = m.tcp_fallbacks;

    const rows = (m.recent_queries || []).slice().reverse().map(q => `
      <tr>
        <td class="mono">${esc(q.domain)}</td>
        <td><span class="answer-type-badge">${esc(q.qtype)}</span></td>
        <td class="mono">${Number(q.latency_ms).toFixed(2)} ms</td>
        <td>${q.cached ? '<span class="tag-valid">Hit</span>' : '<span style="color:var(--text-dim)">Miss</span>'}</td>
        <td>${q.success ? '<span class="tag-valid">✓</span>' : '<span class="tag-expired">✗</span>'}</td>
      </tr>`).join('');

    document.getElementById('recent-body').innerHTML = rows ||
      '<tr><td colspan="5" class="empty-row">No queries yet</td></tr>';
  } catch {
    document.getElementById('m-total').textContent = 'Error';
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Benchmark
// ─────────────────────────────────────────────────────────────────────────────
async function runBenchmark() {
  const input   = document.getElementById('bench-domains').value;
  const qtype   = document.getElementById('bench-type').value;
  const btn     = document.getElementById('bench-btn');
  const out     = document.getElementById('bench-result');

  const domains = input.split(',').map(d => d.trim()).filter(Boolean);
  if (domains.length === 0) { out.innerHTML = errorBox('Enter at least one domain.'); return; }

  btn.disabled  = true;
  out.innerHTML = '<div class="placeholder"><span class="spinner"></span><p>Running benchmark…</p></div>';

  try {
    const resp = await fetch(API + '/benchmark', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domains, type: qtype })
    });
    const data = await resp.json();
    if (data.error) { out.innerHTML = errorBox(data.error); return; }

    renderBenchmark(out, data.results || []);
  } catch (e) {
    out.innerHTML = errorBox(`Cannot reach API: ${e.message}`);
  } finally {
    btn.disabled = false;
  }
}

function renderBenchmark(container, results) {
  if (!results.length) {
    container.innerHTML = errorBox('No results returned.');
    return;
  }

  // Find max latency for bar scaling
  const allTimes = results.flatMap(r => [r.local_cold_ms, r.google_ms, r.cloudflare_ms].filter(v => v > 0));
  const maxTime  = allTimes.length ? Math.max(...allTimes) : 1;

  const bar = (ms) => {
    if (!ms || ms < 0) return '<span class="bench-timeout">Timeout</span>';
    const pct = Math.min(100, (ms / maxTime) * 100).toFixed(1);
    return `<div class="mini-bar-wrap">
      <div class="mini-bar" style="width:${pct}%"></div>
      <span>${ms.toFixed(2)} ms</span>
    </div>`;
  };

  const rows = results.map(r => {
    const times = [
      { name: 'local', ms: r.local_cold_ms },
      { name: 'google', ms: r.google_ms },
      { name: 'cloudflare', ms: r.cloudflare_ms }
    ].filter(t => t.ms > 0).sort((a, b) => a.ms - b.ms);
    const winner = times[0]?.name;

    const warmCell = r.local_warm_ms != null
      ? `<td class="mono" style="color:var(--green)">${r.local_warm_ms.toFixed(3)} ms ⚡</td>`
      : '<td class="mono" style="color:var(--text-dim)">—</td>';

    return `<tr>
      <td class="mono">${esc(r.domain)}</td>
      <td class="${winner==='local'?'bench-winner mono':'mono'}">${bar(r.local_cold_ms)}</td>
      ${warmCell}
      <td class="${winner==='google'?'bench-winner mono':'mono'}">${bar(r.google_ms)}</td>
      <td class="${winner==='cloudflare'?'bench-winner mono':'mono'}">${bar(r.cloudflare_ms)}</td>
    </tr>`;
  }).join('');

  container.innerHTML = `
    <div class="card-title">Results — ${results.length} domain(s)</div>
    <div class="table-wrap bench-table-wrap">
      <table>
        <thead>
          <tr>
            <th>Domain</th>
            <th>Local Cold (ms)</th>
            <th>Local Warm ⚡</th>
            <th>Google 8.8.8.8</th>
            <th>Cloudflare 1.1.1.1</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <p style="margin-top:12px;font-size:0.75rem;color:var(--text-dim);">
      ⚡ Local Warm = cached hit latency &nbsp;|&nbsp; ✓ Winner highlighted in green
    </p>`;
}

// ─────────────────────────────────────────────────────────────────────────────
//  Packet Inspector
// ─────────────────────────────────────────────────────────────────────────────
function inspectPacket() {
  const domain  = document.getElementById('pkt-domain').value.trim() || 'example.com';
  const qtype   = document.getElementById('pkt-type').value;
  const out     = document.getElementById('pkt-output');
  const ann     = document.getElementById('pkt-annotation');

  // Build the DNS query packet in JavaScript (mirrors the C++ build_query logic)
  const id    = 0xABCD;
  const flags = 0x0100;   // RD=1

  // Encode QNAME
  const labels = domain.replace(/\.$/, '').split('.');
  let qname = [];
  for (const lbl of labels) {
    qname.push(lbl.length);
    for (const c of lbl) qname.push(c.charCodeAt(0));
  }
  qname.push(0x00);

  const typeMap = { A: 1, AAAA: 28, NS: 2, MX: 15 };
  const qtypeId = typeMap[qtype] || 1;

  const pkt = [
    (id >> 8) & 0xFF, id & 0xFF,           // Transaction ID
    (flags >> 8) & 0xFF, flags & 0xFF,      // Flags
    0x00, 0x01,                              // QDCOUNT = 1
    0x00, 0x00,                              // ANCOUNT = 0
    0x00, 0x00,                              // NSCOUNT = 0
    0x00, 0x00,                              // ARCOUNT = 0
    ...qname,                                // QNAME
    (qtypeId >> 8) & 0xFF, qtypeId & 0xFF,  // QTYPE
    0x00, 0x01                               // QCLASS = IN
  ];

  // Render hex dump in groups of 16
  const hex = pkt.map(b => b.toString(16).padStart(2, '0'));
  let hexOut = '';
  for (let i = 0; i < hex.length; i++) {
    if (i % 16 === 0 && i > 0) hexOut += '\n';
    else if (i % 8 === 0 && i > 0) hexOut += '  ';
    else if (i > 0) hexOut += ' ';
    hexOut += hex[i];
  }
  out.textContent = hexOut;

  // Annotation table
  const qnameLen = qname.length;
  const hdLen    = 12;
  ann.innerHTML = `
    <div class="card-title">Field Breakdown</div>
    ${annRow(hex.slice(0, 2).join(' '),     'Transaction ID', `0x${id.toString(16).toUpperCase()} (${id})`)}
    ${annRow(hex.slice(2, 4).join(' '),     'Flags',          `0x${flags.toString(16).toUpperCase()} — RD=1 (recursion desired)`)}
    ${annRow(hex.slice(4, 6).join(' '),     'QDCOUNT',        '1 question')}
    ${annRow(hex.slice(6, 8).join(' '),     'ANCOUNT',        '0 answers (query)')}
    ${annRow(hex.slice(8, 10).join(' '),    'NSCOUNT',        '0 authority records')}
    ${annRow(hex.slice(10, 12).join(' '),   'ARCOUNT',        '0 additional records')}
    ${annRow(hex.slice(12, 12+qnameLen).join(' '), 'QNAME',  `"${domain}" in wire format (length-prefixed labels)`)}
    ${annRow(hex.slice(12+qnameLen, 14+qnameLen).join(' '), 'QTYPE', `${qtypeId} = ${qtype}`)}
    ${annRow(hex.slice(14+qnameLen, 16+qnameLen).join(' '), 'QCLASS', '1 = IN (Internet)')}
    <p style="margin-top:10px;font-size:0.75rem;color:var(--text-dim);">
      Total: ${pkt.length} bytes &nbsp;|&nbsp; DNS header: 12 bytes &nbsp;|&nbsp; Question: ${pkt.length - 12} bytes
    </p>`;
}

function annRow(bytes, field, desc) {
  return `<div class="ann-row">
    <span class="ann-bytes">${esc(bytes)}</span>
    <span class="ann-field">${esc(field)}</span>
    <span class="ann-desc">${esc(desc)}</span>
  </div>`;
}

// ─────────────────────────────────────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function showError(container, msg) {
  container.innerHTML = `<div class="error-box">⚠ ${esc(msg)}</div>`;
}

function errorBox(msg) {
  return `<div class="error-box">⚠ ${esc(msg)}</div>`;
}

function typeStr(typeId) {
  const m = { 1:'A', 28:'AAAA', 2:'NS', 5:'CNAME', 6:'SOA', 12:'PTR', 15:'MX', 16:'TXT' };
  return m[typeId] || String(typeId);
}

// ─────────────────────────────────────────────────────────────────────────────
//  Boot
// ─────────────────────────────────────────────────────────────────────────────
checkHealth();
setInterval(checkHealth, 10_000);   // re-check every 10 s

// Render the first packet view on load
window.addEventListener('DOMContentLoaded', () => {
  switchTab('lookup');
  inspectPacket();
});
