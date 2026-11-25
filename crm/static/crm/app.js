// Enlaces con data-modal: se abren en una ventana emergente; sin JS siguen siendo páginas normales.
(() => {
  const el = document.getElementById('app-modal');
  if (!el || !window.bootstrap) return;
  const content = document.getElementById('app-modal-content');
  const modal = bootstrap.Modal.getOrCreateInstance(el);
  const headers = { 'X-Requested-With': 'XMLHttpRequest' };
  let url, trigger;

  const render = (html) => {
    content.innerHTML = html;
    const f = content.querySelector('.errorlist input, .errorlist select, .errorlist textarea')
      || content.querySelector('input:not([type=hidden]), select, textarea')
      || content.querySelector('[data-bs-dismiss="modal"].btn');
    if (f) el.classList.contains('show') ? f.focus() : el.addEventListener('shown.bs.modal', () => f.focus(), { once: true });
  };

  document.addEventListener('click', async (e) => {
    const a = e.target.closest('a[data-modal]');
    if (!a || e.button || e.metaKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault();
    url = a.href; trigger = a;
    try {
      const r = await fetch(url, { headers, credentials: 'same-origin' });
      if (!r.ok || r.redirected) throw new Error(r.status);
      render(await r.text());
      modal.show();
    } catch { location.href = url; }
  });

  content.addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = e.target;
    f.querySelectorAll('[type=submit]').forEach((b) => { b.disabled = true; });
    try {
      const r = await fetch(url, { method: 'POST', body: new FormData(f), headers, credentials: 'same-origin', redirect: 'manual' });
      if (r.type === 'opaqueredirect') { // éxito: recarga para ver datos y mensajes de Django
        modal.hide();
        location.reload();
      } else if (r.ok) render(await r.text());
      else throw new Error(r.status);
    } catch { location.href = url; }
  });

  el.addEventListener('hidden.bs.modal', () => { content.innerHTML = ''; if (trigger) trigger.focus(); });
})();

// Avisos tipo ficha, borrado con deshacer, buscador en vivo y alta rápida de interacciones.
(() => {
  const headers = { 'X-Requested-With': 'XMLHttpRequest' };
  const toasts = document.getElementById('toasts');
  const csrf = () => document.querySelector('[name=csrfmiddlewaretoken]')?.value;
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
  const X = '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M3 3l8 8M11 3l-8 8"/></svg>';

  function toast(text, { undo, error, ms = 8000, onEnd } = {}) {
    const el = document.createElement('div');
    el.className = 'toast-ficha' + (error ? ' is-error' : '');
    if (error) el.setAttribute('role', 'alert');
    el.innerHTML = '<span class="toast-tab" aria-hidden="true"></span><p class="toast-text"></p>'
      + (undo ? '<button type="button" class="toast-btn" data-act="undo">Deshacer</button>' : '')
      + `<button type="button" class="toast-x" data-act="x" aria-label="Cerrar aviso">${X}</button><span class="toast-bar"></span>`;
    el.querySelector('.toast-text').textContent = text;
    el.querySelector('.toast-bar').style.animationDuration = ms + 'ms';
    let done = false;
    const end = (why) => {
      if (done) return;
      done = true; clearTimeout(timer);
      el.classList.add('is-leaving');
      setTimeout(() => el.remove(), 200);
      if (onEnd) onEnd(why);
    };
    const timer = setTimeout(() => end('timeout'), ms);
    el.addEventListener('click', (e) => { const b = e.target.closest('[data-act]'); if (b) end(b.dataset.act); });
    toasts.append(el);
    return { end };
  }

  // --- Eliminar con deshacer: el POST real se envía al agotarse el aviso, al cerrarlo o al salir de la página
  const pending = new Set();
  let sentOnHide = false;
  const send = (url, keepalive) => fetch(url, {
    method: 'POST', credentials: 'same-origin', redirect: 'manual', keepalive,
    headers: { ...headers, 'X-Silent': '1', 'X-CSRFToken': csrf() },
  });
  const hide = (row) => { row.classList.add('is-gone'); row._t = setTimeout(() => { row.hidden = true; }, 200); };
  const show = (row) => { clearTimeout(row._t); row.hidden = false; void row.offsetWidth; row.classList.remove('is-gone'); };

  // tras reemplazar el HTML, vuelve a ocultar las filas pendientes de borrar
  const reocultar = (contenedor) => pending.forEach((i) => {
    const a = contenedor.querySelector(`a[data-undo][href="${i.path}"]`);
    if (a && a.closest('[data-undo-row]')) { i.row = a.closest('[data-undo-row]'); hide(i.row); }
  });

  async function commit(item) {
    try {
      const r = await send(item.url);
      if (r.status !== 204) throw new Error(r.status); // 302 a login (sesión caducada) u otro error: no es éxito
      if (item.next) location.href = item.next;
    } catch {
      show(item.row);
      toast('No se pudo eliminar. Inténtalo de nuevo.', { error: true, ms: 6000 });
    }
  }

  if (toasts) {
    document.addEventListener('click', (e) => {
      const a = e.target.closest('a[data-undo]');
      if (!a || e.button || e.metaKey || e.ctrlKey || e.shiftKey) return;
      const row = a.closest('[data-undo-row]');
      if (!row || !csrf()) return; // sin fila o sin token: página de confirmación normal
      e.preventDefault();
      const item = { url: a.href, path: a.getAttribute('href'), row, next: a.dataset.undoNext };
      pending.add(item);
      hide(row);
      toast(a.dataset.undo + (a.dataset.undoNote ? '. ' + a.dataset.undoNote : ''), {
        undo: true,
        onEnd: (why) => {
          if (item.sent) return;
          pending.delete(item);
          why === 'undo' ? show(item.row) : commit(item);
        },
      });
    });
    window.addEventListener('pagehide', () => {
      pending.forEach((i) => { i.sent = true; sentOnHide = true; send(i.url, true).catch(() => {}); });
      pending.clear();
    });
    window.addEventListener('pageshow', (e) => { if (e.persisted && sentOnHide) location.reload(); });
  }

  // --- Buscador en vivo
  const form = document.getElementById('filtros');
  const lista = document.getElementById('lista');
  const buscar = document.getElementById('buscar');
  if (form && lista && buscar) {
    let timer, ctrl;

    const marcar = () => {
      const term = buscar.value.trim();
      if (!term) return;
      const re = new RegExp(term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
      lista.querySelectorAll('[data-hl]').forEach((cell) => {
        const w = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (w.nextNode()) nodes.push(w.currentNode);
        nodes.forEach((n) => {
          re.lastIndex = 0;
          if (!re.test(n.data)) return;
          const frag = document.createDocumentFragment();
          let last = 0;
          n.data.replace(re, (m, i) => {
            frag.append(n.data.slice(last, i));
            const mk = document.createElement('mark');
            mk.className = 'hl'; mk.textContent = m;
            frag.append(mk);
            last = i + m.length;
            return m;
          });
          frag.append(n.data.slice(last));
          n.replaceWith(frag);
        });
      });
    };

    const refresh = async () => {
      const params = new URLSearchParams(new FormData(form));
      [...params.keys()].forEach((k) => { if (!params.get(k)) params.delete(k); });
      const qs = params.toString();
      const url = location.pathname + (qs ? '?' + qs : '');
      if (ctrl) ctrl.abort();
      const mine = ctrl = new AbortController();
      lista.classList.add('is-loading');
      try {
        const r = await fetch(url, { signal: mine.signal, credentials: 'same-origin' });
        if (!r.ok || r.redirected) throw new Error(r.status);
        const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
        const nuevo = doc.getElementById('lista');
        if (!nuevo) throw new Error('sin lista');
        lista.innerHTML = nuevo.innerHTML;
        reocultar(lista);
        history.replaceState(null, '', url);
        const n = +nuevo.dataset.total;
        document.getElementById('contador').textContent = buscar.value.trim() ? plural(n, 'resultado') : plural(n, 'cliente');
        const hc = document.getElementById('count-badge');
        if (hc) hc.textContent = n;
        const exp = document.querySelector('a[data-export]');
        if (exp) exp.href = exp.pathname + (qs ? '?' + qs : '');
        marcar();
      } catch (err) {
        if (err.name === 'AbortError') return;
        location.href = url;
      } finally {
        if (ctrl === mine) lista.classList.remove('is-loading');
      }
    };

    buscar.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(refresh, 250); });
    form.addEventListener('submit', (e) => { e.preventDefault(); clearTimeout(timer); refresh(); });
    form.querySelectorAll('select[data-auto]').forEach((s) => s.addEventListener('change', () => form.submit()));
    buscar.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      e.preventDefault();
      if (buscar.value) { buscar.value = ''; clearTimeout(timer); refresh(); } else buscar.blur();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey || document.body.classList.contains('modal-open')) return;
      if (e.target.closest('input, textarea, select, [contenteditable]')) return;
      e.preventDefault();
      buscar.focus(); buscar.select();
    });
    marcar();
  }

  // --- Alta rápida de interacción en la ficha del cliente
  const qf = document.getElementById('quick-form');
  if (qf && toasts) {
    const det = qf.querySelector('details');
    const t0 = Date.now(), f0 = qf.elements.fecha.value;
    // hora "ahora" en la zona del servidor: la del render más el tiempo transcurrido
    const ahora = () => new Date(Date.parse(f0 + ':00Z') + Date.now() - t0).toISOString().slice(0, 16);
    const errores = () => qf.querySelectorAll('[data-error]').forEach((p) => { p.textContent = ''; p.hidden = true; });

    qf.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = qf.querySelector('[type=submit]');
      const fd = new FormData(qf);
      if (!det.open) fd.set('fecha', ahora());
      errores();
      btn.disabled = true;
      let r;
      try {
        r = await fetch(qf.action, { method: 'POST', body: fd, headers, credentials: 'same-origin', redirect: 'manual' });
      } catch { qf.submit(); return; }
      try {
        if (r.type === 'opaqueredirect') {
          const g = await fetch(location.href, { credentials: 'same-origin' });
          const doc = new DOMParser().parseFromString(await g.text(), 'text/html');
          const nuevo = doc.getElementById('timeline');
          if (!g.ok || !nuevo) throw new Error('timeline');
          const tl = document.getElementById('timeline');
          const viejos = new Set([...tl.querySelectorAll('[data-id]')].map((x) => x.dataset.id));
          tl.innerHTML = nuevo.innerHTML;
          tl.querySelectorAll('[data-id]').forEach((x) => { if (!viejos.has(x.dataset.id)) x.classList.add('tl-new'); });
          reocultar(tl); // borrados aún por confirmar siguen ocultos
          qf.reset(); det.open = false;
          qf.elements.notas.focus();
          toast('Interacción guardada.', { ms: 4000 });
        } else if (r.ok) {
          const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
          let n = 0;
          doc.querySelectorAll('.errorlist').forEach((ul) => {
            const f = ul.parentElement.querySelector('[name]');
            const p = f && qf.querySelector(`[data-error="${f.name}"]`);
            if (!p) return;
            p.textContent = ul.textContent.trim(); p.hidden = false; n++;
            if (f.name === 'fecha') det.open = true;
          });
          if (!n) throw new Error('errores');
          const campo = qf.querySelector('[data-error]:not([hidden])').parentElement.querySelector('textarea, input:not([type=radio])');
          (campo || qf.elements.notas).focus();
        } else throw new Error(r.status);
      } catch { location.reload(); } // el POST pudo haberse guardado: recarga en vez de reenviar
      btn.disabled = false;
    });
  }
})();
