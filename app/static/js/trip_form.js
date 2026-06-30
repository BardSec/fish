(function () {
  const form = () => $('#trip-form');
  const tripId = () => form().dataset.tripId || null;

  function readFile(file) {
    return new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.onerror = rej;
      r.readAsDataURL(file);
    });
  }

  function collect() {
    const fd = new FormData(form());
    const data = {};
    fd.forEach((v, k) => { data[k] = typeof v === 'string' ? v.trim() : v; });
    if (tripId()) data.id = tripId();
    return data;
  }

  async function prefill(id) {
    let trip;
    try { trip = await Data.getTrip(id); } catch (e) { return; }
    const f = form();
    Object.entries(trip).forEach(([k, v]) => {
      if (f.elements[k] && v != null) f.elements[k].value = v;
    });
  }

  async function onSubmit(e) {
    e.preventDefault();
    const btn = e.submitter; if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }
    const data = collect();
    if (!data.date) { toast('Date is required'); if (btn) { btn.disabled = false; btn.textContent = 'Save trip'; } return; }

    const trip = await LocalDB.save('trip', data);

    // Queue any selected photos (uploaded after the trip syncs).
    const files = $('#trip-photos').files;
    for (const file of files) {
      const dataUrl = await readFile(file);
      await LocalDB.enqueue({
        op_id: LocalDB.uuid(), entity: 'photo', op: 'upload', status: 'pending', tries: 0,
        data: { id: LocalDB.uuid(), trip_id: trip.id, data_url: dataUrl, caption: '' },
      });
    }

    await Sync.updateBadge();
    Sync.flush();
    toast(navigator.onLine ? 'Trip saved' : 'Saved offline — will sync later');
    location.href = '/trips/' + trip.id;
  }

  document.addEventListener('DOMContentLoaded', () => {
    const id = tripId();
    if (id) prefill(id);
    else { // default date to today for fast entry
      form().elements['date'].value = new Date().toISOString().slice(0, 10);
    }
    form().addEventListener('submit', onSubmit);
  });
})();
