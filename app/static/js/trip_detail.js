(function () {
  const root = () => $('#trip-detail');
  const tripId = () => root().dataset.tripId;

  function readFile(file) {
    return new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(file); });
  }

  function field(label, value) {
    if (!value && value !== 0) return '';
    return `<div><span class="muted">${label}:</span> ${escapeHtml(value)}</div>`;
  }

  function catchCard(c) {
    return `<div class="card" style="margin:0 0 10px">
      <div class="row" style="justify-content:space-between">
        <strong>${escapeHtml(c.species)}</strong>
        <span>${c.length ? escapeHtml(c.length) + '"' : ''} ${c.kept ? '<span class="pill">kept</span>' : '<span class="pill accent">released</span>'}</span>
      </div>
      <div class="muted">${[c.time_caught, c.bait, c.water_type].filter(Boolean).map(escapeHtml).join(' · ')}</div>
      ${c.presentation ? `<div class="muted">${escapeHtml(c.presentation)}</div>` : ''}
      ${c.notes ? `<div>${escapeHtml(c.notes)}</div>` : ''}
      ${(c.photos || []).map(p => `<img class="thumb" src="${escapeHtml(p.url)}" alt="catch photo">`).join('')}
      <button class="btn small danger" data-del-catch="${c.id}" style="margin-top:8px">Delete catch</button>
    </div>`;
  }

  async function render() {
    let trip;
    try { trip = await Data.getTrip(tripId()); }
    catch (e) { root().innerHTML = '<div class="empty">Trip not found.</div>'; return; }

    const conditions = [
      field('Air', trip.air_temp && trip.air_temp + '°F'), field('Water', trip.water_temp && trip.water_temp + '°F'),
      field('Weather', trip.weather), field('Clouds', trip.cloud_cover), field('Wind', trip.wind),
      field('Clarity', trip.water_clarity), field('Level', trip.water_level), field('Flow', trip.flow),
      field('Recent rain', trip.recent_rain), field('Moon', trip.moon_phase), field('Hatch', trip.hatch),
    ].filter(Boolean).join('');

    root().innerHTML = `
      <h1 class="page-title">${escapeHtml(trip.water_body || 'Trip')}</h1>
      <div class="card">
        <div class="muted">${fmtDate(trip.date)} · ${[trip.start_time, trip.end_time].filter(Boolean).join('–')}</div>
        <div style="margin:6px 0">
          ${(trip.fishing_type || '').split(',').map(s => s.trim()).filter(Boolean).map(ft => `<span class="pill accent">${escapeHtml(ft)}</span>`).join('')}
          <span class="pill">${trip.fish_count || (trip.catches || []).length} fish</span>
        </div>
        ${field('Access', trip.access_point)}${field('Location', trip.general_location)}
        ${field('Target', trip.target_species)}${field('Caught', trip.species_caught)}
        ${field('Largest', trip.largest_fish)}
        ${trip.notes ? `<p>${escapeHtml(trip.notes)}</p>` : ''}
        ${(trip.photos || []).length ? `<div class="thumbs">${trip.photos.map(p => `<img class="thumb" src="${escapeHtml(p.url)}">`).join('')}</div>` : ''}
        <div class="btn-row">
          <a class="btn small secondary" href="/trips/${trip.id}/edit">Edit trip</a>
          <button class="btn small danger" id="del-trip">Delete trip</button>
        </div>
      </div>
      ${conditions ? `<div class="card"><h3>Conditions</h3>${conditions}</div>` : ''}
      <div class="card"><h3>Catches (${(trip.catches || []).length})</h3>
        <div id="catch-list">${(trip.catches || []).map(catchCard).join('') || '<p class="muted">No catches logged yet.</p>'}</div>
      </div>`;

    $('#del-trip').addEventListener('click', async () => {
      if (!confirm('Delete this trip and its catches?')) return;
      await LocalDB.remove('trip', trip.id); Sync.flush();
      toast('Trip deleted'); location.href = '/trips';
    });
    $$('[data-del-catch]').forEach(b => b.addEventListener('click', async () => {
      await LocalDB.remove('catch', b.dataset.delCatch); Sync.flush(); render();
    }));
  }

  async function loadPins() {
    const sel = $('#catch-pin');
    try {
      const pins = await Data.listPins();
      pins.forEach(p => { const o = document.createElement('option'); o.value = p.id; o.textContent = p.name; sel.appendChild(o); });
    } catch (e) { /* offline, skip */ }
  }

  async function onAddCatch(e) {
    e.preventDefault();
    const f = e.target;
    const fd = new FormData(f); const data = {};
    fd.forEach((v, k) => { data[k] = typeof v === 'string' ? v.trim() : v; });
    if (!data.species) { toast('Species is required'); return; }
    data.trip_id = tripId();
    if (!data.map_pin_id) delete data.map_pin_id;
    const c = await LocalDB.save('catch', data);

    const photo = $('#catch-photo').files[0];
    if (photo) {
      const dataUrl = await readFile(photo);
      await LocalDB.enqueue({ op_id: LocalDB.uuid(), entity: 'photo', op: 'upload', status: 'pending', tries: 0,
        data: { id: LocalDB.uuid(), catch_id: c.id, data_url: dataUrl, caption: '' } });
    }
    f.reset();
    await Sync.updateBadge(); Sync.flush();
    toast(navigator.onLine ? 'Catch added' : 'Saved offline');
    render();
  }

  document.addEventListener('DOMContentLoaded', () => {
    render(); loadPins();
    $('#catch-form').addEventListener('submit', onAddCatch);
  });
  Sync.onChange(render);
})();
