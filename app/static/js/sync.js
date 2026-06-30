/* Sync engine: drains the local mutation queue to the server, pulls a fresh
 * snapshot, records conflicts, and keeps the header status badge current. */
const Sync = (() => {
  let _syncing = false;
  const listeners = [];
  const onChange = fn => listeners.push(fn);
  const emit = () => listeners.forEach(fn => { try { fn(); } catch (_) {} });

  // Strip client-only bookkeeping before sending to the server.
  function cleanData(data) {
    if (!data) return data;
    const { _dirty, _server_updated_at, ...rest } = data;
    return rest;
  }

  async function updateBadge() {
    const el = document.getElementById('sync-status');
    if (!el) return;
    const pending = await LocalDB.queuePendingCount();
    el.classList.remove('online', 'offline', 'syncing', 'pending');
    if (!navigator.onLine) {
      el.classList.add('offline');
      el.textContent = pending ? `Offline · ${pending} queued` : 'Offline';
    } else if (_syncing) {
      el.classList.add('syncing');
      el.innerHTML = '<span class="spinner"></span> Syncing';
    } else if (pending) {
      el.classList.add('pending');
      el.textContent = `${pending} to sync`;
    } else {
      el.classList.add('online');
      el.textContent = 'Synced';
    }
  }

  async function processResult(r) {
    switch (r.status) {
      case 'applied':
      case 'created':
      case 'conflict_client_wins':
        if (r.server) await LocalDB.applyServer(r.entity, r.server);
        await LocalDB.dequeue(r.op_id);
        break;
      case 'deleted':
        await LocalDB.dequeue(r.op_id);
        break;
      case 'conflict_server_wins':
        // Server copy won — adopt it locally and flag for the user to review.
        if (r.server) {
          await LocalDB.applyServer(r.entity, r.server);
          await LocalDB.addConflict({
            entity: r.entity, record_id: r.id, server: r.server,
            note: 'Your offline edit was superseded by a newer change on the server.',
            at: LocalDB.now(),
          });
        }
        await LocalDB.dequeue(r.op_id);
        break;
      case 'error':
        await LocalDB.setQueueError(r.op_id, r.message || 'sync error');
        break;
    }
  }

  // Photos go to /api/photos, not the /api/sync batch. Uploaded after the
  // owning trip/catch so the foreign key already exists on the server.
  async function flushPhotos(photoOps) {
    for (const i of photoOps) {
      try {
        await Api.post('/api/photos', i.data);
        await LocalDB.dequeue(i.op_id);
      } catch (e) { await LocalDB.setQueueError(i.op_id, e.message); }
    }
  }

  async function flush() {
    if (_syncing || !navigator.onLine) { updateBadge(); return; }
    const pending = await LocalDB.queuePending();
    if (!pending.length) { await pullSnapshot(); updateBadge(); return; }

    _syncing = true; updateBadge();
    try {
      const photoOps = pending.filter(i => i.entity === 'photo');
      const dataOps = pending.filter(i => i.entity !== 'photo');
      if (dataOps.length) {
        const operations = dataOps.map(i => ({
          op_id: i.op_id, entity: i.entity, op: i.op, id: i.id,
          base_updated_at: i.base_updated_at, data: cleanData(i.data),
        }));
        const data = await Api.post('/api/sync', { operations });
        for (const r of (data.results || [])) await processResult(r);
      }
      if (photoOps.length) await flushPhotos(photoOps);
      await pullSnapshot();
    } catch (e) {
      // Network blipped mid-sync — leave the queue intact and retry later.
      console.warn('sync failed', e);
    } finally {
      _syncing = false; updateBadge(); emit();
    }
  }

  /* Pull the full server dataset into the local mirror. Skipped while local
   * edits are pending so we never clobber an unsynced change. */
  async function pullSnapshot() {
    if (!navigator.onLine) return;
    const pendingCount = await LocalDB.queuePendingCount();
    if (pendingCount) return;
    try {
      const snap = await Api.get('/api/sync/snapshot');
      for (const t of snap.trips) await LocalDB.applyServer('trip', t);
      for (const c of snap.catches) await LocalDB.applyServer('catch', c);
      for (const p of snap.pins) await LocalDB.applyServer('pin', p);
      await LocalDB.kvSet('last_snapshot', snap.server_time);
      emit();
    } catch (e) { /* offline / transient — fine */ }
  }

  function init() {
    updateBadge();
    window.addEventListener('online', () => { updateBadge(); flush(); });
    window.addEventListener('offline', updateBadge);
    // Initial sync shortly after load, then a gentle poll.
    setTimeout(flush, 800);
    setInterval(() => { if (navigator.onLine) flush(); }, 30000);
  }

  return { init, flush, pullSnapshot, updateBadge, onChange };
})();
