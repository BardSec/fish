(function () {
  function card(p) {
    return `<div class="card">
      <div class="row" style="justify-content:space-between">
        <strong>${escapeHtml(p.name)}</strong>
        <span class="stars">${stars(p.confidence)}</span>
      </div>
      <div class="muted">${[p.water_body, p.spot_type, p.access_point].filter(Boolean).map(escapeHtml).join(' · ')}</div>
      ${p.primary_species ? `<div>${escapeHtml(p.primary_species)}</div>` : ''}
      ${p.notes ? `<div class="muted">${escapeHtml(p.notes)}</div>` : ''}
      <div style="margin-top:6px">
        <span class="pill">${p.is_public ? 'public' : 'private'}</span>
        <span class="pill">${p.catch_count || 0} catches</span>
        <span class="pill">${(+p.latitude).toFixed(4)}, ${(+p.longitude).toFixed(4)}</span>
      </div>
      <div class="btn-row">
        <a class="btn small secondary" href="/map">View on map</a>
        <button class="btn small danger" data-del="${p.id}">Delete</button>
      </div>
    </div>`;
  }

  function clientFilter(pins) {
    const sp = $('#f-species').value.trim().toLowerCase();
    const wb = $('#f-water').value.trim().toLowerCase();
    const st = $('#f-spot').value, cf = $('#f-conf').value;
    return pins.filter(p =>
      (!sp || (p.primary_species || '').toLowerCase().includes(sp)) &&
      (!wb || (p.water_body || '').toLowerCase().includes(wb)) &&
      (!st || p.spot_type === st) &&
      (!cf || (p.confidence || 0) >= +cf));
  }

  let _t;
  async function load() {
    let pins = await Data.listPins();
    pins = clientFilter(pins).sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
    $('#pin-list').innerHTML = pins.length ? pins.map(card).join('')
      : '<div class="empty">No pins yet. <a href="/map">Add one on the map →</a></div>';
    $$('[data-del]').forEach(b => b.addEventListener('click', async () => {
      if (!confirm('Delete this pin?')) return;
      await LocalDB.remove('pin', b.dataset.del); Sync.flush(); load();
    }));
  }
  const debounced = () => { clearTimeout(_t); _t = setTimeout(load, 250); };
  document.addEventListener('DOMContentLoaded', () => {
    ['f-species', 'f-water'].forEach(id => $('#' + id).addEventListener('input', debounced));
    ['f-spot', 'f-conf'].forEach(id => $('#' + id).addEventListener('change', load));
    load();
  });
  Sync.onChange(load);
})();
