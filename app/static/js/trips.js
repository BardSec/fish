(function () {
  const fields = ['q', 'species', 'water', 'bait', 'weather', 'from', 'to'];

  function params() {
    const v = id => $('#f-' + id).value.trim();
    return {
      q: v('q'), species: v('species'), water_body: v('water'),
      bait: v('bait'), weather: v('weather'), from: v('from'), to: v('to'),
    };
  }

  function card(t) {
    const caught = t.species_caught ? ` · ${escapeHtml(t.species_caught)}` : '';
    return `<a class="card tap" style="display:block" href="/trips/${t.id}">
      <div class="row" style="justify-content:space-between">
        <strong>${escapeHtml(t.water_body || 'Untitled trip')}</strong>
        <span class="muted">${fmtDate(t.date)}</span>
      </div>
      <div class="muted">${escapeHtml(t.general_location || '')}</div>
      <div style="margin-top:6px">
        ${t.fishing_type ? `<span class="pill accent">${escapeHtml(t.fishing_type)}</span>` : ''}
        <span class="pill">${t.fish_count || 0} fish</span>
        ${t.weather ? `<span class="pill">${escapeHtml(t.weather)}</span>` : ''}
      </div>
      <div class="muted" style="margin-top:4px">${escapeHtml(t.target_species || '')}${caught}</div>
    </a>`;
  }

  let _t;
  async function load() {
    const list = $('#trip-list');
    const trips = await Data.listTrips(params());
    trips.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
    list.innerHTML = trips.length ? trips.map(card).join('')
      : '<div class="empty">No trips match. <a href="/trips/new">Log a trip →</a></div>';
  }
  const debounced = () => { clearTimeout(_t); _t = setTimeout(load, 250); };

  document.addEventListener('DOMContentLoaded', () => {
    fields.forEach(f => $('#f-' + f).addEventListener('input', debounced));
    $('#f-clear').addEventListener('click', () => { fields.forEach(f => $('#f-' + f).value = ''); load(); });
    load();
  });
  Sync.onChange(load);
})();
