/* Shared app bootstrap + helpers, loaded on every page. */

// --- Service worker registration --------------------------------------------
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(err =>
      console.warn('SW registration failed', err));
  });
}

// --- Tiny DOM/util helpers ---------------------------------------------------
const $ = sel => document.querySelector(sel);
const $$ = sel => Array.from(document.querySelectorAll(sel));

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function toast(msg, ms = 2400) {
  let t = $('#toast');
  if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('show');
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove('show'), ms);
}

function fmtDate(d) {
  if (!d) return '';
  const dt = new Date(d + 'T00:00:00');
  return isNaN(dt) ? d : dt.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });
}

function stars(n) {
  n = Math.max(0, Math.min(5, parseInt(n || 0, 10)));
  return '★'.repeat(n) + '☆'.repeat(5 - n);
}

function qs(obj) {
  return Object.entries(obj).filter(([, v]) => v !== '' && v != null)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
}

// --- Theme -------------------------------------------------------------------
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
}
applyTheme(localStorage.getItem('theme') || 'dark');

// --- Data facade: remote when online, local mirror when offline --------------
const Data = (() => {
  async function remoteElseLocal(url, store) {
    try { return await Api.get(url); }
    catch (e) { return (await LocalDB.getAll(store)) || []; }
  }
  return {
    listTrips: (params = {}) => remoteElseLocal('/api/trips?' + qs(params), 'trips'),
    listCatches: (params = {}) => remoteElseLocal('/api/catches?' + qs(params), 'catches'),
    listPins: (params = {}) => remoteElseLocal('/api/pins?' + qs(params), 'pins'),

    async getTrip(id) {
      try { return await Api.get('/api/trips/' + id); }
      catch (e) {
        const trip = await LocalDB.get('trips', id);
        if (!trip) throw e;
        const all = await LocalDB.getAll('catches');
        trip.catches = all.filter(c => c.trip_id === id);
        trip.photos = trip.photos || [];
        return trip;
      }
    },

    async dashboard() {
      try {
        const d = await Api.get('/api/dashboard');
        await LocalDB.kvSet('dashboard_cache', d);
        return { data: d, stale: false };
      } catch (e) {
        const cached = await LocalDB.kvGet('dashboard_cache');
        return { data: cached, stale: true };
      }
    },

    async meta() {
      try {
        const m = await Api.get('/api/meta');
        await LocalDB.kvSet('meta_cache', m);
        return m;
      } catch (e) { return (await LocalDB.kvGet('meta_cache')) || { choices: {}, species: [], baits: [], water_bodies: [] }; }
    },
  };
})();

// --- Boot --------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
  await LocalDB.open();
  Sync.init();
});
