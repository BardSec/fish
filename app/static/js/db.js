/* Local-first data store backed by IndexedDB.
 *
 * Everything the user creates is written here FIRST (so it works with no
 * connectivity) and a mutation is appended to the `queue` store. The sync
 * engine (sync.js) drains that queue to the server when online.
 *
 * Stores:
 *   trips, catches, pins   -> local mirror of records (keyed by id)
 *   queue                  -> pending mutations awaiting sync
 *   conflicts              -> server-wins conflicts for the user to review
 *   kv                     -> misc cache (e.g. last dashboard snapshot)
 */
const LocalDB = (() => {
  const DB_NAME = 'fishing-atlas';
  const DB_VERSION = 1;
  let _db = null;

  function open() {
    if (_db) return Promise.resolve(_db);
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        for (const s of ['trips', 'catches', 'pins', 'conflicts']) {
          if (!db.objectStoreNames.contains(s)) db.createObjectStore(s, { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains('queue'))
          db.createObjectStore('queue', { keyPath: 'op_id' });
        if (!db.objectStoreNames.contains('kv'))
          db.createObjectStore('kv', { keyPath: 'key' });
      };
      req.onsuccess = () => { _db = req.result; resolve(_db); };
      req.onerror = () => reject(req.error);
    });
  }

  function tx(store, mode, fn) {
    return open().then(db => new Promise((resolve, reject) => {
      const t = db.transaction(store, mode);
      const os = t.objectStore(store);
      let result;
      Promise.resolve(fn(os)).then(r => { result = r; });
      t.oncomplete = () => resolve(result);
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    }));
  }

  const reqP = r => new Promise((res, rej) => { r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });

  const uuid = () => (crypto.randomUUID ? crypto.randomUUID()
    : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
        const r = Math.random() * 16 | 0; return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
      }));
  const now = () => new Date().toISOString();

  // --- generic ---------------------------------------------------------------
  const put = (store, val) => tx(store, 'readwrite', os => reqP(os.put(val)));
  const get = (store, id) => tx(store, 'readonly', os => reqP(os.get(id)));
  const getAll = store => tx(store, 'readonly', os => reqP(os.getAll()));
  const del = (store, id) => tx(store, 'readwrite', os => reqP(os.delete(id)));
  const clear = store => tx(store, 'readwrite', os => reqP(os.clear()));

  // --- key/value cache -------------------------------------------------------
  const kvGet = key => get('kv', key).then(r => (r ? r.value : null));
  const kvSet = (key, value) => put('kv', { key, value });

  // --- local-first mutations -------------------------------------------------
  const ENTITY_STORE = { trip: 'trips', catch: 'catches', pin: 'pins' };

  /** Create/update a record locally and enqueue an upsert for sync. */
  async function save(entity, data) {
    const store = ENTITY_STORE[entity];
    const existing = data.id ? await get(store, data.id) : null;
    const record = Object.assign({}, existing, data);
    record.id = record.id || uuid();
    record.updated_at = now();
    record._dirty = true; // not yet confirmed by server
    await put(store, record);
    await enqueue({
      op_id: uuid(),
      entity,
      op: 'upsert',
      id: record.id,
      base_updated_at: existing ? (existing._server_updated_at || existing.updated_at) : null,
      data: record,
      tries: 0,
      status: 'pending',
    });
    return record;
  }

  /** Delete a record locally and enqueue a delete for sync. */
  async function remove(entity, id) {
    const store = ENTITY_STORE[entity];
    await del(store, id);
    await enqueue({ op_id: uuid(), entity, op: 'delete', id, tries: 0, status: 'pending' });
  }

  /** Apply an authoritative server record into the local mirror. */
  async function applyServer(entity, record) {
    const store = ENTITY_STORE[entity];
    record._dirty = false;
    record._server_updated_at = record.updated_at;
    await put(store, record);
  }

  // --- sync queue ------------------------------------------------------------
  const enqueue = item => put('queue', item);
  const queueAll = () => getAll('queue');
  const queuePending = () => getAll('queue').then(items => items.filter(i => i.status !== 'error'));
  const queuePendingCount = () => queuePending().then(items => items.length);
  const dequeue = opId => del('queue', opId);
  async function setQueueError(opId, message) {
    const item = await get('queue', opId);
    if (item) { item.status = 'error'; item.error = message; item.tries = (item.tries || 0) + 1; await put('queue', item); }
  }
  const clearQueue = () => clear('queue');

  // --- conflicts -------------------------------------------------------------
  const addConflict = c => put('conflicts', Object.assign({ id: uuid() }, c));
  const conflicts = () => getAll('conflicts');
  const resolveConflict = id => del('conflicts', id);

  return {
    open, uuid, now,
    put, get, getAll, del, clear,
    kvGet, kvSet,
    save, remove, applyServer,
    enqueue, queueAll, queuePending, queuePendingCount, dequeue, setQueueError, clearQueue,
    addConflict, conflicts, resolveConflict,
  };
})();
