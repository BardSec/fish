(async function () {
  function rankCard(title, items, unit) {
    if (!items || !items.length) return '';
    const lis = items.map(i =>
      `<li><span>${escapeHtml(i.label)}</span><span class="count">${i.count}${unit ? ' ' + unit : ''}</span></li>`).join('');
    return `<div class="card"><h3>${title}</h3><ul class="ranklist">${lis}</ul></div>`;
  }

  async function render() {
    const { data, stale } = await Data.dashboard();
    const banner = $('#stale-banner');
    if (!data) {
      banner.innerHTML = '<div class="banner warn">No data available offline yet. Connect once to load your atlas.</div>';
      return;
    }
    banner.innerHTML = stale
      ? '<div class="banner warn">⚠ Offline — showing the last synced snapshot.</div>' : '';

    $('#stat-trips').textContent = data.total_trips;
    $('#stat-fish').textContent = data.total_fish;
    $('#stat-pins').textContent = data.total_pins;
    $('#stat-catches').textContent = data.total_catches;

    $('#rank-cards').innerHTML = [
      rankCard('Top species', data.top_species),
      rankCard('Best water bodies', data.best_water_bodies, 'fish'),
      rankCard('Best flies / lures', data.best_baits),
      rankCard('Best months', data.best_months, 'fish'),
      rankCard('Best seasons', data.best_seasons, 'fish'),
      rankCard('Best time of day', data.best_time_of_day),
    ].join('');

    $('#recent-trips').innerHTML = (data.recent_trips || []).length
      ? data.recent_trips.map(t => `
        <a class="card tap" href="/trips/${t.id}" style="display:block">
          <strong>${escapeHtml(t.water_body || 'Trip')}</strong>
          <div class="muted">${[fmtDate(t.date), (t.fishing_type || '').split(',').map(s => s.trim()).filter(Boolean).join(', '), `${t.fish_count || 0} fish`].filter(Boolean).map(escapeHtml).join(' · ')}</div>
        </a>`).join('')
      : '<p class="muted">No trips yet. Log your first one!</p>';

    $('#productive-pins').innerHTML = (data.most_productive_pins || []).filter(p => p.catch_count > 0).length
      ? data.most_productive_pins.filter(p => p.catch_count > 0).map(p => `
        <div class="card" style="margin:0 0 10px">
          <strong>${escapeHtml(p.name)}</strong> <span class="stars">${stars(p.confidence)}</span>
          <div class="muted">${escapeHtml(p.water_body || '')} · ${escapeHtml(p.spot_type || '')} · ${p.catch_count} catches</div>
        </div>`).join('')
      : '<p class="muted">No catches tied to pins yet.</p>';
  }

  document.addEventListener('DOMContentLoaded', render);
  Sync.onChange(render);
})();
