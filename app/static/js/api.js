/* Thin fetch wrappers around the JSON API. Reject on network/HTTP errors so
 * callers can fall back to local data when offline. */
const Api = (() => {
  async function request(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    let json = null;
    try { json = await res.json(); } catch (_) { /* ignore */ }
    if (!res.ok || (json && json.ok === false)) {
      const msg = (json && json.error) || `HTTP ${res.status}`;
      const e = new Error(msg); e.status = res.status; e.body = json; throw e;
    }
    return json ? json.data : null;
  }

  return {
    get: url => request('GET', url),
    post: (url, body) => request('POST', url, body),
    put: (url, body) => request('PUT', url, body),
    del: url => request('DELETE', url),
    // multipart upload (photos)
    async upload(url, formData) {
      const res = await fetch(url, { method: 'POST', body: formData });
      const json = await res.json();
      if (!res.ok || json.ok === false) throw new Error(json.error || `HTTP ${res.status}`);
      return json.data;
    },
  };
})();
