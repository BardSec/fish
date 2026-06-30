(function () {
  const cfg = window.MAP_CONFIG || {};
  let map, markerLayer, placing = false, draftMarker = null;

  // Point Leaflet at the vendored marker images (so it works offline).
  const icon = L.icon({
    iconUrl: '/static/vendor/leaflet/images/marker-icon.png',
    iconRetinaUrl: '/static/vendor/leaflet/images/marker-icon-2x.png',
    shadowUrl: '/static/vendor/leaflet/images/marker-shadow.png',
    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
  });

  function filters() {
    return {
      species: $('#f-species').value.trim(),
      water_body: $('#f-water').value.trim(),
      spot_type: $('#f-spot').value,
      min_confidence: $('#f-conf').value,
    };
  }

  function popupHtml(p) {
    return `<strong>${escapeHtml(p.name)}</strong><br>
      <span class="stars">${stars(p.confidence)}</span><br>
      ${escapeHtml(p.water_body || '')} ${p.spot_type ? '· ' + escapeHtml(p.spot_type) : ''}<br>
      ${p.primary_species ? escapeHtml(p.primary_species) + '<br>' : ''}
      ${p.notes ? escapeHtml(p.notes) + '<br>' : ''}
      ${p.is_public ? '<em>public</em>' : '<em>private</em>'} · ${p.catch_count || 0} catches<br>
      <a href="#" data-edit-pin="${p.id}">Edit</a> · <a href="#" data-del-pin="${p.id}">Delete</a>`;
  }

  function clientFilter(pins, f) {
    const sp = f.species.toLowerCase(), wb = f.water_body.toLowerCase();
    return pins.filter(p =>
      (!sp || (p.primary_species || '').toLowerCase().includes(sp)) &&
      (!wb || (p.water_body || '').toLowerCase().includes(wb)) &&
      (!f.spot_type || p.spot_type === f.spot_type) &&
      (!f.min_confidence || (p.confidence || 0) >= +f.min_confidence));
  }

  async function loadPins() {
    const f = filters();
    let pins = await Data.listPins(f);
    pins = clientFilter(pins, f); // also covers offline (unfiltered) source
    markerLayer.clearLayers();
    pins.forEach(p => {
      if (p.latitude == null || p.longitude == null) return;
      const m = L.marker([p.latitude, p.longitude], { icon }).addTo(markerLayer);
      m.bindPopup(popupHtml(p));
      m.on('popupopen', e => {
        const el = e.popup.getElement();
        el.querySelector('[data-del-pin]')?.addEventListener('click', async ev => {
          ev.preventDefault();
          if (!confirm('Delete this pin?')) return;
          await LocalDB.remove('pin', p.id); Sync.flush(); loadPins();
        });
        el.querySelector('[data-edit-pin]')?.addEventListener('click', ev => {
          ev.preventDefault(); openPanel(p);
        });
      });
    });
  }

  // --- pin form panel --------------------------------------------------------
  function openPanel(pin) {
    const panel = $('#pin-panel'), form = $('#pin-form');
    form.reset();
    $('#pin-panel-title').textContent = pin && pin.id ? 'Edit pin' : 'New pin';
    if (pin) {
      ['id', 'name', 'water_body', 'access_point', 'spot_type', 'primary_species', 'notes', 'latitude', 'longitude', 'confidence']
        .forEach(k => { if (form.elements[k] && pin[k] != null) form.elements[k].value = pin[k]; });
      $('#pin-public').checked = !!pin.is_public;
    }
    panel.style.display = 'block';
    panel.scrollIntoView({ behavior: 'smooth' });
  }
  function closePanel() { $('#pin-panel').style.display = 'none'; if (draftMarker) { map.removeLayer(draftMarker); draftMarker = null; } }

  function enterPlacement() {
    placing = true; toast('Tap the map to drop your pin');
    $('#add-pin-btn').textContent = 'Tap map to place…';
  }
  function exitPlacement() { placing = false; $('#add-pin-btn').textContent = '📍 Add pin (tap map)'; }

  function onMapClick(e) {
    if (!placing) return;
    const { lat, lng } = e.latlng;
    if (draftMarker) map.removeLayer(draftMarker);
    draftMarker = L.marker([lat, lng], { icon }).addTo(map);
    openPanel({ latitude: lat.toFixed(6), longitude: lng.toFixed(6) });
    exitPlacement();
  }

  async function onSavePin(e) {
    e.preventDefault();
    const form = e.target, fd = new FormData(form), data = {};
    fd.forEach((v, k) => { data[k] = typeof v === 'string' ? v.trim() : v; });
    data.is_public = $('#pin-public').checked;
    if (!data.id) delete data.id;
    if (!data.name || !data.latitude || !data.longitude) { toast('Name and coordinates are required'); return; }
    await LocalDB.save('pin', data);
    closePanel(); await Sync.updateBadge(); Sync.flush();
    toast(navigator.onLine ? 'Pin saved' : 'Saved offline');
    loadPins();
  }

  let _t;
  const debounced = () => { clearTimeout(_t); _t = setTimeout(loadPins, 250); };

  document.addEventListener('DOMContentLoaded', () => {
    map = L.map('map').setView([cfg.lat || 35.67, cfg.lng || -83.75], cfg.zoom || 11);
    L.tileLayer(cfg.tileUrl, { attribution: cfg.attribution, maxZoom: 19 }).addTo(map);
    markerLayer = L.layerGroup().addTo(map);
    map.on('click', onMapClick);

    $('#add-pin-btn').addEventListener('click', () => placing ? exitPlacement() : enterPlacement());
    $('#pin-cancel').addEventListener('click', closePanel);
    $('#pin-form').addEventListener('submit', onSavePin);
    $('#locate-btn').addEventListener('click', () => {
      if (!navigator.geolocation) return toast('Geolocation unavailable');
      navigator.geolocation.getCurrentPosition(pos => {
        const { latitude, longitude } = pos.coords;
        map.setView([latitude, longitude], 15);
        if (draftMarker) map.removeLayer(draftMarker);
        draftMarker = L.marker([latitude, longitude], { icon }).addTo(map);
        openPanel({ latitude: latitude.toFixed(6), longitude: longitude.toFixed(6) });
      }, () => toast('Could not get your location'));
    });
    ['f-species', 'f-water'].forEach(id => $('#' + id).addEventListener('input', debounced));
    ['f-spot', 'f-conf'].forEach(id => $('#' + id).addEventListener('change', loadPins));

    loadPins();
    setTimeout(() => map.invalidateSize(), 200);
  });
  Sync.onChange(loadPins);
})();
