(function () {
  async function renderSync() {
    const pending = await LocalDB.queuePending();
    const all = await LocalDB.queueAll();
    const errors = all.filter(i => i.status === 'error');
    const last = await LocalDB.kvGet('last_snapshot');
    $('#sync-info').innerHTML = `
      Status: <strong>${navigator.onLine ? 'Online' : 'Offline'}</strong><br>
      Pending changes: <strong>${pending.length}</strong><br>
      Last server sync: <strong>${last ? new Date(last).toLocaleString() : 'never'}</strong>`;

    $('#queue-errors').innerHTML = errors.length
      ? `<div class="banner warn">${errors.length} change(s) failed to sync:
          <ul>${errors.map(e => `<li>${escapeHtml(e.entity)} — ${escapeHtml(e.error || 'error')}
            <button class="btn small secondary" data-retry="${e.op_id}">Retry</button></li>`).join('')}</ul></div>`
      : '';
    $$('[data-retry]').forEach(b => b.addEventListener('click', async () => {
      const item = await LocalDB.get('queue', b.dataset.retry);
      if (item) { item.status = 'pending'; await LocalDB.put('queue', item); }
      Sync.flush();
    }));
  }

  async function renderConflicts() {
    const list = await LocalDB.conflicts();
    $('#conflicts').innerHTML = list.length
      ? list.map(c => `<div class="card" style="margin:0 0 10px">
          <div>${escapeHtml(c.note)}</div>
          <div class="muted">${escapeHtml(c.entity)} · ${new Date(c.at).toLocaleString()}</div>
          <div class="btn-row">
            <button class="btn small secondary" data-keep-server="${c.id}">Keep server version</button>
            <button class="btn small primary" data-keep-mine="${c.id}" data-entity="${c.entity}" data-rid="${c.record_id}">Re-apply my edit</button>
          </div></div>`).join('')
      : '<p class="muted">None.</p>';

    $$('[data-keep-server]').forEach(b => b.addEventListener('click', async () => {
      await LocalDB.resolveConflict(b.dataset.keepServer); renderConflicts();
      toast('Kept server version');
    }));
    $$('[data-keep-mine]').forEach(b => b.addEventListener('click', async () => {
      // Re-queue the current local record as a fresh edit (becomes newest write).
      const store = { trip: 'trips', catch: 'catches', pin: 'pins' }[b.dataset.entity];
      const rec = await LocalDB.get(store, b.dataset.rid);
      if (rec) await LocalDB.save(b.dataset.entity, rec);
      await LocalDB.resolveConflict(b.dataset.keepMine);
      Sync.flush(); renderConflicts(); toast('Re-applying your edit');
    }));
  }

  async function exportJson() {
    let payload;
    try { payload = await Api.get('/api/sync/snapshot'); }
    catch (e) {
      payload = { trips: await LocalDB.getAll('trips'), catches: await LocalDB.getAll('catches'), pins: await LocalDB.getAll('pins') };
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'fishing-atlas-backup.json';
    a.click(); URL.revokeObjectURL(a.href);
  }

  document.addEventListener('DOMContentLoaded', () => {
    const sel = $('#theme-select');
    sel.value = localStorage.getItem('theme') || 'dark';
    sel.addEventListener('change', () => applyTheme(sel.value));

    $('#sync-now').addEventListener('click', () => { Sync.flush(); setTimeout(renderSync, 600); });
    $('#refresh-snapshot').addEventListener('click', async () => { await Sync.pullSnapshot(); renderSync(); toast('Reloaded from server'); });
    $('#export').addEventListener('click', exportJson);
    $('#clear-local').addEventListener('click', async () => {
      if (!confirm('Clear local cache on this device? Unsynced changes will be lost.')) return;
      for (const s of ['trips', 'catches', 'pins', 'queue', 'conflicts']) await LocalDB.clear(s);
      await Sync.pullSnapshot(); renderSync(); renderConflicts(); toast('Local cache cleared');
    });

    renderSync(); renderConflicts();
  });
  Sync.onChange(() => { renderSync(); renderConflicts(); });
})();
