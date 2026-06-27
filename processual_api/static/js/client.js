const CLIENT = (() => {
  const BASE = '';

  let _token = null;
  let _onUnauthorized = null;

  function setToken(t) { _token = t; }
  function getToken() { return _token; }
  function clearToken() { _token = null; }
  function onUnauthorized(fn) { _onUnauthorized = fn; }

  async function fetchJSON(method, path, body) {
    const headers = { 'Content-Type': 'application/json' };
    if (_token) headers['Authorization'] = 'Bearer ' + _token;

    const opts = { method, headers };
    if (body !== undefined) opts.body = JSON.stringify(body);

    let res;
    try {
      res = await fetch(BASE + path, opts);
    } catch (err) {
      throw { status: 0, message: 'Network error — is the backend running?', detail: err.message };
    }

    if (!res.ok) {
      if (res.status === 401 && _onUnauthorized) _onUnauthorized();
      let detail = '';
      try { const j = await res.json(); detail = j.detail || j.message || ''; } catch (_) {}
      throw { status: res.status, message: res.statusText, detail };
    }

    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) return res.json();
    if (ct.includes('application/pdf') || ct.includes('application/octet-stream')) return res.blob();
    return res.text();
  }

  return {
    setToken, getToken, clearToken, onUnauthorized,
    get:   (p)      => fetchJSON('GET', p),
    post:  (p, b)   => fetchJSON('POST', p, b),
    put:   (p, b)   => fetchJSON('PUT', p, b),
    del:   (p)      => fetchJSON('DELETE', p),
  };
})();
