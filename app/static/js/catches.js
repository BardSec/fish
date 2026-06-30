(function () {
  function card(c) {
    return `<a class="card tap" style="display:block" href="/trips/${c.trip_id}">
      <div class="row" style="justify-content:space-between">
        <strong>${escapeHtml(c.species)}</strong>
        <span>${c.length ? escapeHtml(c.length) + '"' : ''}</span>
      </div>
      <div class="muted">${[c.time_caught, c.bait, c.water_type].filter(Boolean).map(escapeHtml).join(' · ')}</div>
      ${c.kept ? '<span class="pill">kept</span>' : '<span class="pill accent">released</span>'}
    </a>`;
  }
  let _t;
  async function load() {
    const params = { species: $('#f-species').value.trim(), bait: $('#f-bait').value.trim() };
    let catches = await Data.listCatches(params);
    // Local fallback isn't server-filtered, so filter client-side too.
    const sp = params.species.toLowerCase(), ba = params.bait.toLowerCase();
    catches = catches.filter(c =>
      (!sp || (c.species || '').toLowerCase().includes(sp)) &&
      (!ba || (c.bait || '').toLowerCase().includes(ba)));
    catches.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
    $('#catch-list').innerHTML = catches.length ? catches.map(card).join('')
      : '<div class="empty">No catches yet.</div>';
  }
  const debounced = () => { clearTimeout(_t); _t = setTimeout(load, 250); };
  document.addEventListener('DOMContentLoaded', () => {
    $('#f-species').addEventListener('input', debounced);
    $('#f-bait').addEventListener('input', debounced);
    load();
  });
  Sync.onChange(load);
})();
