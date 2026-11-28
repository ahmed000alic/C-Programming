const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const inr = n => '₹' + Math.round(n).toLocaleString('en-IN');
const inr2 = n => '₹' + Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (n, d = 0) => Number(n).toLocaleString('en-IN', { maximumFractionDigits: d });
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const mlabel = (m, long) => { const [y, mo] = m.split('-'); return long ? `${MON[mo - 1]} ${y}` : `${MON[mo - 1]} ${y.slice(2)}`; };
const TEAL = '#0B7A75', TEAL_L = '#9FD3CE', AMBER = '#F2B233', INK = '#14202E';
const charts = {};

async function api(path, opts = {}) {
  const r = await fetch('/api' + path, { headers: { 'Content-Type': 'application/json' }, ...opts, body: opts.body && JSON.stringify(opts.body) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || 'Something went wrong. Try again.');
  return d;
}
let tt;
function toast(msg, bad) {
  const t = $('#toast'); t.textContent = msg; t.className = 'show' + (bad ? ' bad' : '');
  clearTimeout(tt); tt = setTimeout(() => t.className = '', 3200);
}
const guard = fn => async (...a) => { try { await fn(...a); } catch (e) { toast(e.message, true); } };
function chart(id, cfg) {
  charts[id]?.destroy();
  Chart.defaults.font.family = "'IBM Plex Sans', system-ui, sans-serif"; Chart.defaults.color = '#5D6B78';
  cfg.options = { responsive: true, maintainAspectRatio: false, ...cfg.options };
  charts[id] = new Chart($('#' + id), cfg);
}

/* Odometer: digits roll into place, the one moment of motion on the page */
function odometer(el, text) {
  el.setAttribute('aria-label', text);
  el.innerHTML = [...text].map(ch => /\d/.test(ch)
    ? `<span class="od-d" aria-hidden="true"><span class="od-s" data-d="${ch}">${[...'0123456789'].map(n => `<i>${n}</i>`).join('')}</span></span>`
    : `<span class="od-c" aria-hidden="true">${ch}</span>`).join('');
  requestAnimationFrame(() => requestAnimationFrame(() => $$('.od-s', el).forEach((s, i) => {
    s.style.transitionDelay = i * 80 + 'ms'; s.style.transform = `translateY(-${s.dataset.d}em)`;
  })));
}

/* ---------- Overview ---------- */
async function loadOverview() {
  const s = await api('/summary');
  $('#today-label').textContent = new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  $('#overview-empty').hidden = !s.empty; $('#overview-body').hidden = s.empty;
  if (s.empty) return;
  const { kpi, history, forecast: fc, daily } = s, next = fc.points[0];
  if (next) {
    $('#hero-label').textContent = `Predicted bill for ${mlabel(next.month, true)}`;
    odometer($('#odo'), inr(next.bill));
    $('#hero-sub').textContent = `About ${num(next.kwh)} units. Likely range ${inr(billAt(next.low, next))} to ${inr(billAt(next.high, next))}.`
      + (fc.accuracy ? ` Model accuracy ${fc.accuracy}%.` : '');
  } else {
    $('#hero-label').textContent = 'Predicted bill'; odometer($('#odo'), '—');
    $('#hero-sub').textContent = fc.reason;
  }
  if (kpi.so_far !== undefined) {
    $('#mtd-label').textContent = 'This month so far';
    $('#mtd-kwh').textContent = num(kpi.so_far, 1);
    $('#mtd-bar').style.width = Math.min(100, kpi.days_logged / kpi.days_in_month * 100) + '%';
    $('#mtd-sub').textContent = `${kpi.days_logged} of ${kpi.days_in_month} days logged. Projected ${num(kpi.projected_kwh)} units, ${inr(kpi.projected_bill)}.`;
  } else {
    $('#mtd-kwh').textContent = '0'; $('#mtd-bar').style.width = '0';
    $('#mtd-sub').textContent = 'No readings logged for this month yet.';
  }
  const st = [['Average per day', num(kpi.avg_daily, 1) + ' units', 'last 30 days'],
    ['This month, projected', kpi.projected_kwh ? num(kpi.projected_kwh) + ' units' : '–', kpi.projected_bill ? inr(kpi.projected_bill) : ''],
    ['Last month', kpi.last_kwh ? num(kpi.last_kwh) + ' units' : '–', kpi.last_bill ? inr(kpi.last_bill) : ''],
    ['Days recorded', num(kpi.logged_days), 'in total']];
  $('#stats').innerHTML = st.map(([a, b, c]) => `<div><dt>${a}</dt><dd>${b}</dd><small>${c}</small></div>`).join('');
  $('#insights').innerHTML = s.insights.map(i => `<li class="${i.tone}">${esc(i.text)}</li>`).join('');

  const labels = [...history.map(h => mlabel(h.month)), ...fc.points.map(p => mlabel(p.month))], n = history.length;
  chart('c-monthly', { type: 'bar', data: { labels, datasets: [
    { label: 'Actual units', data: [...history.map(h => h.kwh), ...fc.points.map(() => null)], backgroundColor: history.map(h => h.current ? TEAL_L : TEAL).concat(fc.points.map(() => TEAL)), borderRadius: 4 },
    { label: 'Forecast units', data: [...history.map(() => null), ...fc.points.map(p => p.kwh)], backgroundColor: AMBER, borderRadius: 4 }] },
    options: { plugins: { tooltip: { callbacks: { afterLabel: c => 'Bill ' + inr((c.datasetIndex ? fc.points[c.dataIndex - n] : history[c.dataIndex]).bill) } } },
      scales: { y: { beginAtZero: true, grid: { color: '#E6EBEA' } }, x: { grid: { display: false } } } } });
  chart('c-daily', { type: 'line', data: { labels: daily.map(d => d.date.slice(8) + ' ' + MON[+d.date.slice(5, 7) - 1]), datasets: [
    { label: 'Units', data: daily.map(d => d.kwh), borderColor: TEAL, backgroundColor: 'rgba(11,122,117,.12)', fill: true, tension: .3, pointRadius: 2 },
    { label: 'Average', data: daily.map(() => s.avg30), borderColor: INK, borderDash: [5, 5], pointRadius: 0, borderWidth: 1.5 }] },
    options: { scales: { y: { beginAtZero: true, grid: { color: '#E6EBEA' } }, x: { grid: { display: false }, ticks: { maxTicksLimit: 8 } } } } });
}
// approximate the bill at a different unit count using the forecast's own bill-per-unit
const billAt = (kwh, p) => p.kwh ? p.bill * (kwh / p.kwh) : 0;

/* ---------- Forecast ---------- */
async function loadForecast() {
  const h = $('#f-horizon').value, r = $('#f-reduce').value;
  $('#f-reduce-out').textContent = r + '%';
  const f = await api(`/forecast?horizon=${h}&reduce=${r}`);
  $('#f-msg').textContent = f.ok ? '' : f.reason;
  $('#f-table').innerHTML = f.ok ? `<tr><th>Month</th><th class="n">Units</th><th class="n">Bill</th>${+r ? '<th class="n">Bill with cut</th>' : ''}</tr>`
    + f.points.map(p => `<tr><td>${mlabel(p.month, true)}</td><td class="n">${num(p.kwh)}</td><td class="n">${inr(p.bill)}</td>${+r ? `<td class="n">${inr(p.bill_reduced)}</td>` : ''}</tr>`).join('') : '';
  $('#f-model').innerHTML = f.ok ? `<p><span class="badge">${f.model}</span></p><p>Trained on ${f.trained_on} complete months of your readings.</p>`
    + (f.mae !== null ? `<p>Tested by leaving each month out and predicting it: the average miss is ${num(f.mae, 1)} units, about ${f.accuracy}% accuracy.</p>`
      : '<p>Log at least 6 months to get an accuracy score.</p>')
    + (f.model === 'Linear trend' ? '<p class="muted">Seasonal patterns, such as summer peaks, are picked up once you have 12 months of data.</p>' : '')
    + '<p class="muted">The shaded band is the likely range (80% confidence).</p>' : '<p class="muted">No model yet.</p>';
  const save = f.ok ? f.points.reduce((a, p) => a + p.bill - p.bill_reduced, 0) : 0;
  $('#f-save').hidden = !(+r && f.ok);
  $('#f-save').innerHTML = `Cutting usage by ${r}% would save about <strong>${inr(save)}</strong> over the next ${h} months.`;
  if (!f.ok) return charts['c-forecast']?.destroy();
  const L = f.points.map(p => mlabel(p.month));
  const ds = [{ label: 'High', data: f.points.map(p => p.high), borderWidth: 0, pointRadius: 0, fill: false },
    { label: 'Likely range', data: f.points.map(p => p.low), borderWidth: 0, pointRadius: 0, fill: '-1', backgroundColor: 'rgba(242,178,51,.25)' },
    { label: 'Forecast units', data: f.points.map(p => p.kwh), borderColor: '#C98A00', backgroundColor: AMBER, tension: .3, pointRadius: 4 }];
  if (+r) ds.push({ label: `With ${r}% less`, data: f.points.map(p => Math.round(p.kwh * (1 - r / 100))), borderColor: TEAL, borderDash: [6, 4], tension: .3, pointRadius: 3 });
  chart('c-forecast', { type: 'line', data: { labels: L, datasets: ds }, options: { plugins: { legend: { labels: { filter: i => i.text !== 'High' } } },
    scales: { y: { beginAtZero: true, title: { display: true, text: 'Units (kWh)' }, grid: { color: '#E6EBEA' } }, x: { grid: { display: false } } } } });
}

/* ---------- Readings ---------- */
async function loadReadings() {
  const rows = await api('/readings');
  $('#r-table').innerHTML = rows.length ? '<tr><th>Date</th><th class="n">Units (kWh)</th><th></th></tr>' + rows.map(r =>
    `<tr><td>${new Date(r.date + 'T00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</td><td class="n">${num(r.kwh, 2)}</td>
     <td class="n"><button class="x" data-del="${r.date}" aria-label="Delete reading for ${r.date}">×</button></td></tr>`).join('')
    : '<tr><td class="muted">No readings yet. Add one above or load the sample data.</td></tr>';
}

/* ---------- Appliances ---------- */
async function loadAppliances() {
  const d = await api('/appliances');
  $('#a-table').innerHTML = d.items.length ? '<tr><th>Appliance</th><th class="n">Watts</th><th class="n">Qty</th><th class="n">Hours/day</th><th class="n">Units/month</th><th class="n">Share</th><th class="n">Est. cost</th><th></th></tr>'
    + d.items.map(a => `<tr><td>${esc(a.name)}</td><td class="n">${num(a.watts)}</td><td class="n">${a.qty}</td><td class="n">${a.hours}</td><td class="n">${num(a.kwh_month, 1)}</td><td class="n">${a.share}%</td><td class="n">${inr(a.cost)}</td>
      <td class="n"><button class="x" data-delapp="${a.id}" aria-label="Remove ${esc(a.name)}">×</button></td></tr>`).join('')
    + `<tr><th>Total</th><th></th><th></th><th></th><th class="n">${num(d.total_kwh, 1)}</th><th></th><th class="n">${inr(d.total_bill)}</th><th></th></tr>`
    : '<tr><td class="muted">No appliances yet. Add the big ones first: AC, fridge, fans, geyser.</td></tr>';
  if (!d.items.length) return charts['c-apps']?.destroy();
  const pal = [TEAL, AMBER, '#10243B', '#5BB5AC', '#C98A00', '#6F8CA8', '#B83A3A', '#9FD3CE'];
  chart('c-apps', { type: 'doughnut', data: { labels: d.items.map(a => a.name), datasets: [{ data: d.items.map(a => a.kwh_month), backgroundColor: d.items.map((_, i) => pal[i % pal.length]), borderWidth: 2 }] },
    options: { cutout: '58%', plugins: { legend: { position: 'right' } } } });
}

/* ---------- Tariff ---------- */
function slabRow(s, last) {
  return `<div class="slab${last ? ' last' : ''}"><label>${last ? 'Above' : 'Up to (units)'}<input type="number" min="0" step="any" class="s-upto" ${last ? 'disabled value=""' : `value="${s.upto ?? ''}" required`}></label>
    <label>Rate (₹ per unit)<input type="number" min="0" step="any" class="s-rate" value="${s.rate}" required></label>
    ${last ? '<span></span>' : '<button type="button" class="x" data-rmslab aria-label="Remove slab">×</button>'}</div>`;
}
function drawSlabs(slabs) {
  $('#slabs').innerHTML = slabs.map((s, i) => slabRow(s, i === slabs.length - 1)).join('');
  const last = $$('.slab.last .s-upto')[0]; if (last) last.placeholder = 'all higher usage';
}
const readSlabs = () => $$('.slab').map(r => ({ upto: $('.s-upto', r).value === '' ? null : +$('.s-upto', r).value, rate: +$('.s-rate', r).value }));
async function loadTariff() {
  const t = await api('/tariff'); drawSlabs(t.slabs);
  $('#tariff-form [name=fixed]').value = t.fixed_charge; $('#tariff-form [name=tax]').value = t.tax_pct;
}

/* ---------- Router ---------- */
const loaders = { overview: loadOverview, forecast: loadForecast, readings: loadReadings, appliances: loadAppliances, tariff: loadTariff };
async function route() {
  const p = loaders[location.hash.slice(1)] ? location.hash.slice(1) : 'overview';
  $$('[data-page]').forEach(s => s.hidden = s.dataset.page !== p);
  $$('[data-nav]').forEach(a => a.dataset.nav === p ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current'));
  try { await loaders[p](); } catch (e) { toast(e.message, true); }
}
window.addEventListener('hashchange', route);

/* ---------- Events ---------- */
document.addEventListener('click', guard(async e => {
  const t = e.target;
  if (t.matches('[data-demo]')) { const d = await api('/demo', { method: 'POST' }); toast(`Loaded ${d.imported} days of sample data`); route(); }
  if (t.dataset.del) { await api('/readings/' + t.dataset.del, { method: 'DELETE' }); toast('Reading deleted'); loadReadings(); }
  if (t.dataset.delapp) { await api('/appliances/' + t.dataset.delapp, { method: 'DELETE' }); toast('Appliance removed'); loadAppliances(); }
  if (t.id === 'clear-all' && confirm('Delete all readings and appliances? This cannot be undone.')) { await api('/data', { method: 'DELETE' }); toast('All data deleted'); loadReadings(); }
  if (t.id === 'add-slab') { const s = readSlabs(), last = s.pop(); s.push({ upto: '', rate: last.rate }, last); drawSlabs(s); }
  if (t.dataset.rmslab !== undefined) { t.closest('.slab').remove(); drawSlabs(readSlabs()); }
}));
const onSubmit = (id, fn) => $(id).addEventListener('submit', guard(async e => { e.preventDefault(); await fn(Object.fromEntries(new FormData(e.target)), e.target); }));
onSubmit('#reading-form', async (v, f) => { await api('/readings', { method: 'POST', body: v }); toast('Reading saved'); f.kwh.value = ''; loadReadings(); });
onSubmit('#import-form', async (v, f) => { const d = await api('/readings/import', { method: 'POST', body: { csv: v.csv } }); toast(`Imported ${d.imported} rows` + (d.skipped ? `, skipped ${d.skipped}` : '')); f.reset(); loadReadings(); });
onSubmit('#app-form', async (v, f) => { await api('/appliances', { method: 'POST', body: v }); toast('Appliance added'); f.reset(); f.qty.value = 1; loadAppliances(); });
onSubmit('#tariff-form', async (v) => { await api('/tariff', { method: 'PUT', body: { slabs: readSlabs(), fixed_charge: +v.fixed, tax_pct: +v.tax } }); toast('Tariff saved'); loadTariff(); });
onSubmit('#calc-form', async (v) => {
  const b = await api('/bill', { method: 'POST', body: { units: v.units } });
  $('#calc-out').innerHTML = '<table>' + b.lines.map(l => `<tr><td>${num(l.units, 1)} units at ₹${l.rate}</td><td class="n">${inr2(l.amount)}</td></tr>`).join('')
    + `<tr><td>Fixed charge</td><td class="n">${inr2(b.fixed)}</td></tr><tr><td>Tax and duty</td><td class="n">${inr2(b.tax)}</td></tr></table>`
    + `<div class="calc-total"><span>Total</span><span>${inr2(b.total)}</span></div>`;
});
$('#csv-file').addEventListener('change', e => { const f = e.target.files[0]; if (f) f.text().then(t => $('#import-form textarea').value = t); });
$('#reading-form [name=date]').value = $('#reading-form [name=date]').max = new Date().toLocaleDateString('en-CA');
$('#f-horizon').addEventListener('change', guard(loadForecast)); $('#f-reduce').addEventListener('input', guard(loadForecast));
route();
