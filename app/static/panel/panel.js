(() => {
  'use strict';

  // ---------- Configuración ----------
  const API = '/api/v1';
  const CURRENCY = 'EUR'; // cámbiala aquí si el catálogo usa otra moneda (USD, MXN…)
  const TOKEN_KEY = 'ac_panel_token';
  const RATINGS = ['A+++', 'A++', 'A+', 'A', 'B', 'C', 'D'];
  const TYPES = { split: 'Split', mini_split: 'Mini split', window: 'Ventana', portable: 'Portátil', central: 'Central' };
  const SORTS = {
    'created_at:desc': 'Más recientes',
    'price:asc': 'Precio, de menor a mayor',
    'price:desc': 'Precio, de mayor a menor',
    'brand:asc': 'Marca, de la A a la Z',
    'btu_capacity:desc': 'Capacidad, de mayor a menor',
    'btu_capacity:asc': 'Capacidad, de menor a mayor',
    'power_consumption:asc': 'Consumo, de menor a mayor',
  };

  // useGrouping 'always': en es-ES los números de 4 cifras (9000) no llevan punto por defecto
  const nfInt = new Intl.NumberFormat('es-ES', { useGrouping: 'always' });
  const nfDec = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 });
  const nfMoney = new Intl.NumberFormat('es-ES', { style: 'currency', currency: CURRENCY, useGrouping: 'always' });
  const currencySymbol = (() => {
    const part = new Intl.NumberFormat('es-ES', { style: 'currency', currency: CURRENCY })
      .formatToParts(0).find((p) => p.type === 'currency');
    return part ? part.value : CURRENCY;
  })();

  // ---------- Utilidades ----------
  const $ = (sel, root = document) => root.querySelector(sel);

  function h(tag, props, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (v === true) el.setAttribute(k, '');
      else el.setAttribute(k, v);
    }
    for (const kid of kids.flat()) {
      if (kid == null || kid === false) continue;
      el.append(kid); // los strings se insertan como texto, nunca como HTML
    }
    return el;
  }

  const store = {
    get(k) { try { return sessionStorage.getItem(k) || ''; } catch { return ''; } },
    set(k, v) { try { sessionStorage.setItem(k, v); } catch { /* sin almacenamiento: la sesión dura lo que la pestaña */ } },
    del(k) { try { sessionStorage.removeItem(k); } catch { /* nada */ } },
  };

  const debounce = (fn, ms) => {
    let t;
    return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  };

  // ---------- Estado ----------
  const defaultFilters = () => ({
    brand: '', ac_type: '', energy_rating: '', min_btu: '', max_btu: '',
    min_price: '', max_price: '', available: '',
    has_inverter: false, has_heating: false, has_wifi: false,
  });

  const state = {
    token: store.get(TOKEN_KEY),
    me: null,
    items: [],
    total: 0,
    page: 0,
    size: 25,
    sort: 'created_at:desc',
    filters: defaultFilters(),
    reqId: 0,
    editing: null, // equipo en edición (null = alta)
    deleting: null,
  };

  const isAdmin = () => !!(state.me && state.me.is_superuser);

  // ---------- API ----------
  class ApiError extends Error {
    constructor(status, detail, retryAfter) {
      super(typeof detail === 'string' ? detail : 'Error');
      this.status = status;
      this.detail = detail;
      this.retryAfter = retryAfter;
    }
  }

  async function api(path, opts = {}) {
    const { method = 'GET', json, form, auth = true, query } = opts;
    const headers = {};
    let body;
    if (json !== undefined) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(json);
    } else if (form) {
      body = new URLSearchParams(form);
    }
    if (auth && state.token) headers.Authorization = 'Bearer ' + state.token;

    let url = API + path;
    if (query) {
      const qs = new URLSearchParams();
      for (const [k, v] of Object.entries(query)) if (v !== '' && v != null) qs.set(k, v);
      const s = qs.toString();
      if (s) url += '?' + s;
    }

    let res;
    try {
      res = await fetch(url, { method, headers, body });
    } catch {
      throw new ApiError(0, 'No se pudo conectar con la API. Comprueba que el servidor está en marcha.');
    }
    if (res.status === 204) return null;

    let data = null;
    if ((res.headers.get('content-type') || '').includes('application/json')) {
      try { data = await res.json(); } catch { /* cuerpo vacío o inválido */ }
    }
    if (!res.ok) {
      if (res.status === 401 && auth) expireSession();
      const detail = data && data.detail !== undefined ? data.detail : res.statusText;
      throw new ApiError(res.status, detail, res.headers.get('Retry-After'));
    }
    return data;
  }

  const FIELD_LABELS = {
    brand: 'Marca', model: 'Modelo', ac_type: 'Tipo', btu_capacity: 'Capacidad (BTU)',
    power_consumption: 'Consumo', energy_rating: 'Clasificación energética',
    recommended_area_m2: 'Superficie recomendada', price: 'Precio', stock_quantity: 'Stock',
    warranty_months: 'Garantía', noise_level_db: 'Nivel de ruido', email: 'Email', password: 'Contraseña',
  };
  const RULE_TEXT = {
    missing: 'es obligatorio',
    greater_than: 'debe ser mayor que 0',
    greater_than_equal: 'debe ser 0 o más',
    string_too_short: 'es demasiado corto',
    string_too_long: 'es demasiado largo',
    enum: 'tiene un valor no permitido',
    int_parsing: 'debe ser un número entero',
    int_from_float: 'debe ser un número entero',
    float_parsing: 'debe ser un número',
  };

  function waitText(retryAfter) {
    const s = parseInt(retryAfter, 10);
    if (!Number.isFinite(s) || s <= 0) return 'más tarde';
    if (s < 60) return `en ${s} segundos`;
    const m = Math.ceil(s / 60);
    return `en ${m} ${m === 1 ? 'minuto' : 'minutos'}`;
  }

  // Convierte un error de la API en un mensaje que dice qué pasó y qué hacer
  function explain(err) {
    if (!(err instanceof ApiError)) return 'Ha ocurrido un error inesperado. Recarga la página e inténtalo de nuevo.';
    if (err.status === 0) return err.detail;
    if (err.status === 429) return `Demasiados intentos fallidos. Vuelve a intentarlo ${waitText(err.retryAfter)}.`;
    if (err.status === 403) return 'Tu cuenta no tiene permisos para hacer esto. Pide acceso de administrador.';
    if (err.status === 422 && Array.isArray(err.detail)) {
      const msgs = err.detail.map((d) => {
        const field = d.loc && d.loc[d.loc.length - 1];
        if (field === 'password') return 'La contraseña debe tener entre 8 y 72 caracteres.';
        if (field === 'email') return 'Escribe un email válido.';
        const label = FIELD_LABELS[field] || field || 'Un campo';
        return `${label} ${RULE_TEXT[d.type] || 'no es válido'}.`;
      });
      return [...new Set(msgs)].join(' ');
    }
    if (err.status >= 500) return 'La API ha fallado al procesar la petición. Inténtalo de nuevo; si sigue igual, revisa el registro del servidor.';
    return typeof err.detail === 'string' ? err.detail : 'No se pudo completar la acción.';
  }

  // ---------- Vistas ----------
  function show(view) {
    $('#view-login').hidden = view !== 'login';
    $('#view-catalog').hidden = view !== 'catalog';
    document.title = view === 'login' ? 'Acceso - Catálogo de climatización' : 'Catálogo de climatización';
  }

  function showLogin(message) {
    show('login');
    setLoginMessage(message || '', 'info');
  }

  function setLoginMessage(text, kind) {
    const el = $('#login-message');
    el.hidden = !text;
    el.textContent = text;
    el.classList.toggle('notice-error', kind === 'error');
  }

  function expireSession() {
    if (!state.token) return;
    state.token = '';
    state.me = null;
    store.del(TOKEN_KEY);
    closeDialogs();
    showLogin('Tu sesión ha caducado. Inicia sesión de nuevo.');
  }

  function logout() {
    state.token = '';
    state.me = null;
    store.del(TOKEN_KEY);
    state.filters = defaultFilters();
    state.page = 0;
    closeDialogs();
    showLogin('');
    $('#login-password').value = '';
    $('#login-email').focus();
  }

  function closeDialogs() {
    for (const d of document.querySelectorAll('dialog[open]')) d.close();
  }

  let toastTimer;
  function toast(text) {
    const el = $('#toast');
    el.textContent = text;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
  }

  // ---------- Acceso ----------
  function selectTab(which) {
    const login = which === 'login';
    $('#tab-login').setAttribute('aria-selected', String(login));
    $('#tab-register').setAttribute('aria-selected', String(!login));
    $('#tab-login').tabIndex = login ? 0 : -1;
    $('#tab-register').tabIndex = login ? -1 : 0;
    $('#form-login').hidden = !login;
    $('#form-register').hidden = login;
    setLoginMessage('', 'info');
  }

  async function doLogin(email, password) {
    const data = await api('/login/access-token', { method: 'POST', form: { username: email, password }, auth: false });
    state.token = data.access_token;
    store.set(TOKEN_KEY, state.token);
    state.me = await api('/users/me');
    enterCatalog();
  }

  async function submitLogin(ev) {
    ev.preventDefault();
    const form = ev.currentTarget;
    const email = form.email.value.trim();
    const password = form.password.value;
    if (!email || !password) {
      setLoginMessage('Escribe tu email y tu contraseña.', 'error');
      return;
    }
    const btn = $('button[type="submit"]', form);
    btn.disabled = true;
    setLoginMessage('', 'info');
    try {
      await doLogin(email, password);
      form.password.value = '';
    } catch (e) {
      setLoginMessage(e.status === 401 ? 'Email o contraseña incorrectos. Revísalos e inténtalo de nuevo.' : explain(e), 'error');
    } finally {
      btn.disabled = false;
    }
  }

  async function submitRegister(ev) {
    ev.preventDefault();
    const form = ev.currentTarget;
    const email = form.email.value.trim();
    const password = form.password.value;
    const fullName = form.full_name.value.trim();
    if (!email) { setLoginMessage('Escribe tu email.', 'error'); return; }
    if (password.length < 8 || password.length > 72) {
      setLoginMessage('La contraseña debe tener entre 8 y 72 caracteres.', 'error');
      return;
    }
    const btn = $('button[type="submit"]', form);
    btn.disabled = true;
    setLoginMessage('', 'info');
    try {
      await api('/users/', { method: 'POST', json: { email, password, full_name: fullName || null }, auth: false });
      await doLogin(email, password);
      form.reset();
    } catch (e) {
      setLoginMessage(explain(e), 'error');
    } finally {
      btn.disabled = false;
    }
  }

  // ---------- Catálogo: filtros ----------
  function buildQuery() {
    const f = state.filters;
    const [sortBy, order] = state.sort.split(':');
    return {
      skip: state.page * state.size,
      limit: state.size,
      sort_by: sortBy,
      order,
      brand: f.brand.trim(),
      ac_type: f.ac_type,
      energy_rating: f.energy_rating,
      min_btu: f.min_btu,
      max_btu: f.max_btu,
      min_price: f.min_price,
      max_price: f.max_price,
      available: f.available,
      has_inverter: f.has_inverter ? 'true' : '',
      has_heating: f.has_heating ? 'true' : '',
      has_wifi: f.has_wifi ? 'true' : '',
    };
  }

  function activeFilterCount() {
    const f = state.filters;
    return ['brand', 'ac_type', 'energy_rating', 'min_btu', 'max_btu', 'min_price', 'max_price', 'available']
      .filter((k) => String(f[k]).trim() !== '').length
      + ['has_inverter', 'has_heating', 'has_wifi'].filter((k) => f[k]).length;
  }

  function readFiltersFromUI() {
    const f = state.filters;
    f.brand = $('#f-brand').value;
    f.ac_type = $('#f-type').value;
    f.min_btu = $('#f-btu-min').value;
    f.max_btu = $('#f-btu-max').value;
    f.min_price = $('#f-price-min').value;
    f.max_price = $('#f-price-max').value;
    f.available = $('#f-available').value;
    f.has_inverter = $('#f-inverter').checked;
    f.has_heating = $('#f-heating').checked;
    f.has_wifi = $('#f-wifi').checked;
  }

  function syncFiltersToUI() {
    const f = state.filters;
    $('#f-brand').value = f.brand;
    $('#f-type').value = f.ac_type;
    $('#f-btu-min').value = f.min_btu;
    $('#f-btu-max').value = f.max_btu;
    $('#f-price-min').value = f.min_price;
    $('#f-price-max').value = f.max_price;
    $('#f-available').value = f.available;
    $('#f-inverter').checked = f.has_inverter;
    $('#f-heating').checked = f.has_heating;
    $('#f-wifi').checked = f.has_wifi;
    for (const b of document.querySelectorAll('#scale button')) {
      b.setAttribute('aria-pressed', String(b.dataset.rating === f.energy_rating));
    }
    updateFilterToggle();
  }

  function updateFilterToggle() {
    const n = activeFilterCount();
    $('#btn-filters').textContent = n ? `Filtros (${n})` : 'Filtros';
  }

  function rangeError() {
    const f = state.filters;
    const num = (v) => (String(v).trim() === '' ? null : Number(v));
    const [b1, b2, p1, p2] = [num(f.min_btu), num(f.max_btu), num(f.min_price), num(f.max_price)];
    if (b1 !== null && b2 !== null && b1 > b2) return 'La capacidad mínima no puede ser mayor que la máxima.';
    if (p1 !== null && p2 !== null && p1 > p2) return 'El precio mínimo no puede ser mayor que el máximo.';
    return '';
  }

  function applyFilters() {
    readFiltersFromUI();
    updateFilterToggle();
    state.page = 0;
    const err = rangeError();
    if (err) { showBanner(err); return; }
    loadList();
  }

  const applyFiltersSoon = debounce(applyFilters, 350);

  // ---------- Catálogo: carga y pintado ----------
  function showBanner(text) {
    const el = $('#banner');
    el.textContent = text;
    el.hidden = !text;
  }

  function setLoading(on) {
    $('#table-wrap').setAttribute('aria-busy', String(on));
  }

  async function loadList() {
    const id = ++state.reqId;
    setLoading(true);
    showBanner('');
    try {
      const data = await api('/air-conditioners/', { query: buildQuery() });
      if (id !== state.reqId) return; // llegó una respuesta más reciente
      if (data.items.length === 0 && data.total > 0 && state.page > 0) {
        state.page = Math.max(0, Math.ceil(data.total / state.size) - 1);
        return loadList();
      }
      state.items = data.items;
      state.total = data.total;
      render();
    } catch (e) {
      if (id !== state.reqId) return;
      showBanner(explain(e));
    } finally {
      if (id === state.reqId) setLoading(false);
    }
  }

  const kw = (btu) => nfDec.format((btu * 0.29307107) / 1000);

  function statusBadge(it) {
    if (!it.is_available) return h('span', { class: 'badge badge-off' }, 'No disponible');
    if (it.stock_quantity > 0) return h('span', { class: 'badge badge-ok' }, `En stock (${nfInt.format(it.stock_quantity)})`);
    return h('span', { class: 'badge badge-warn' }, 'Sin stock');
  }

  function extras(it) {
    const list = [];
    if (it.has_inverter) list.push('Inverter');
    if (it.has_heating) list.push('calefacción');
    if (it.has_wifi) list.push('WiFi');
    if (!list.length) return null;
    const text = list.join(', ');
    return h('span', { class: 'unit-extras' }, text.charAt(0).toUpperCase() + text.slice(1));
  }

  function rowFor(it) {
    const name = `${it.brand} ${it.model}`;
    return h('tr', null,
      h('td', { class: 'cell-unit' },
        h('span', { class: 'unit-brand' }, it.brand), ' ', h('span', { class: 'unit-model' }, it.model), extras(it)),
      h('td', { class: 'nowrap', 'data-label': 'Tipo' }, TYPES[it.ac_type] || it.ac_type),
      h('td', { class: 'num', 'data-label': 'Capacidad' },
        h('span', null, h('span', { class: 'cap-main' }, nfInt.format(it.btu_capacity)), ' BTU', h('span', { class: 'cap-sub' }, `${kw(it.btu_capacity)} kW`))),
      h('td', { class: 'num', 'data-label': 'Consumo' }, `${nfInt.format(it.power_consumption)} W`),
      h('td', { class: 'num', 'data-label': 'Superficie' }, `${nfDec.format(it.recommended_area_m2)} m²`),
      h('td', { 'data-label': 'Eficiencia' },
        h('span', { class: 'rating', 'data-rating': it.energy_rating, role: 'img', 'aria-label': `Clasificación energética ${it.energy_rating}` }, it.energy_rating)),
      h('td', { class: 'num', 'data-label': 'Precio' }, h('span', { class: 'price' }, nfMoney.format(it.price))),
      h('td', { 'data-label': 'Estado' }, statusBadge(it)),
      h('td', { class: 'col-actions' }, isAdmin() ? h('span', { class: 'row-actions' },
        h('button', { type: 'button', class: 'btn btn-quiet btn-sm', 'aria-label': `Editar ${name}`, onclick: () => openForm(it) }, 'Editar'),
        h('button', { type: 'button', class: 'btn btn-quiet btn-sm', 'aria-label': `Eliminar ${name}`, onclick: () => openDelete(it) }, 'Eliminar'),
      ) : null),
    );
  }

  function render() {
    const total = state.total;
    $('#result-count').textContent = total === 1 ? '1 equipo' : `${nfInt.format(total)} equipos`;

    const tbody = $('#rows');
    tbody.replaceChildren(...state.items.map(rowFor));

    const empty = $('#empty');
    const tableEl = $('table.grid');
    tableEl.hidden = total === 0;
    empty.hidden = total !== 0;
    if (total === 0) {
      const filtered = activeFilterCount() > 0;
      empty.replaceChildren(
        h('h2', null, filtered ? 'Ningún equipo coincide' : 'El catálogo está vacío'),
        h('p', null, filtered
          ? 'Prueba a quitar algún filtro o a ampliar los rangos.'
          : (isAdmin() ? 'Añade el primer equipo para empezar.' : 'Todavía no hay equipos. Vuelve más tarde.')),
        filtered
          ? h('button', { type: 'button', class: 'btn btn-secondary', onclick: resetFilters }, 'Quitar filtros')
          : (isAdmin() ? h('button', { type: 'button', class: 'btn btn-primary', onclick: () => openForm(null) }, 'Añadir equipo') : null),
      );
    }

    const pages = Math.max(1, Math.ceil(total / state.size));
    $('#pager').hidden = total === 0;
    if (total) {
      const from = state.page * state.size + 1;
      const to = Math.min(total, from + state.items.length - 1);
      $('#pager-info').textContent = `Mostrando ${nfInt.format(from)} a ${nfInt.format(to)} de ${nfInt.format(total)}`;
      $('#pager-page').textContent = `Página ${state.page + 1} de ${pages}`;
      $('#btn-prev').disabled = state.page === 0;
      $('#btn-next').disabled = state.page >= pages - 1;
    }
  }

  function resetFilters() {
    state.filters = defaultFilters();
    state.page = 0;
    syncFiltersToUI();
    loadList();
  }

  function buildStaticControls() {
    const type = $('#f-type');
    type.replaceChildren(h('option', { value: '' }, 'Todos los tipos'),
      ...Object.entries(TYPES).map(([v, l]) => h('option', { value: v }, l)));

    $('#f-sort').replaceChildren(...Object.entries(SORTS).map(([v, l]) => h('option', { value: v }, l)));
    $('#legend-price').textContent = `Precio (${currencySymbol})`;

    $('#scale').replaceChildren(...RATINGS.map((r) => h('button', {
      type: 'button', 'data-rating': r, 'aria-pressed': 'false',
      'aria-label': `Clasificación ${r}`,
      onclick: () => {
        state.filters.energy_rating = state.filters.energy_rating === r ? '' : r;
        syncFiltersToUI();
        state.page = 0;
        if (!rangeError()) loadList();
      },
    }, h('span', null, r), h('span', { class: 'tick', 'aria-hidden': 'true' }, '✓'))));
  }

  // ---------- Alta y edición ----------
  const FIELDS = [
    { name: 'brand', label: 'Marca', kind: 'text', required: true, max: 100 },
    { name: 'model', label: 'Modelo', kind: 'text', required: true, max: 100 },
    { name: 'ac_type', label: 'Tipo de equipo', kind: 'select', required: true, options: TYPES },
    { name: 'energy_rating', label: 'Clasificación energética', kind: 'select', required: true, options: Object.fromEntries(RATINGS.map((r) => [r, r])) },
    { name: 'btu_capacity', label: 'Capacidad (BTU)', kind: 'int', required: true, min: 1 },
    { name: 'power_consumption', label: 'Consumo (W)', kind: 'float', required: true, min: 0.01 },
    { name: 'recommended_area_m2', label: 'Superficie recomendada (m²)', kind: 'float', required: true, min: 0.01 },
    { name: 'price', label: `Precio (${currencySymbol})`, kind: 'float', required: true, min: 0.01, step: '0.01' },
    { name: 'stock_quantity', label: 'Unidades en stock', kind: 'int', min: 0, fallback: 0 },
    { name: 'warranty_months', label: 'Garantía (meses)', kind: 'int', min: 0, fallback: 12 },
    { name: 'noise_level_db', label: 'Nivel de ruido (dB)', kind: 'float', min: 0, nullable: true, hint: 'Opcional' },
  ];
  const CHECKS = [
    { name: 'has_inverter', label: 'Inverter', fallback: false },
    { name: 'has_heating', label: 'Calefacción', fallback: false },
    { name: 'has_wifi', label: 'WiFi', fallback: false },
    { name: 'is_available', label: 'Disponible para la venta', fallback: true },
  ];

  function buildFormFields() {
    const box = $('#form-fields');
    const nodes = FIELDS.map((f) => {
      const id = 'ff-' + f.name;
      let control;
      if (f.kind === 'select') {
        control = h('select', { id, name: f.name, required: f.required },
          ...Object.entries(f.options).map(([v, l]) => h('option', { value: v }, l)));
      } else if (f.kind === 'text') {
        control = h('input', { id, name: f.name, type: 'text', required: f.required, maxlength: f.max, autocomplete: 'off' });
      } else {
        control = h('input', {
          id, name: f.name, type: 'number', required: f.required, min: f.min,
          step: f.kind === 'int' ? '1' : (f.step || 'any'), inputmode: f.kind === 'int' ? 'numeric' : 'decimal',
        });
      }
      return h('div', { class: 'field' }, h('label', { for: id }, f.label, f.hint ? h('span', { class: 'opt' }, ` (${f.hint.toLowerCase()})`) : null), control);
    });
    const checks = h('div', { class: 'form-checks' }, ...CHECKS.map((c) =>
      h('label', { class: 'form-check' }, h('input', { type: 'checkbox', name: c.name }), c.label)));
    box.replaceChildren(...nodes, checks);
  }

  function fillForm(it) {
    const form = $('#form-ac');
    for (const f of FIELDS) {
      const el = form.elements[f.name];
      const v = it ? it[f.name] : (f.kind === 'select' ? Object.keys(f.options)[0] : (f.fallback ?? ''));
      el.value = v == null ? '' : String(v);
    }
    for (const c of CHECKS) form.elements[c.name].checked = it ? !!it[c.name] : c.fallback;
    // Nuevo equipo: que el tipo y la clasificación no queden preseleccionados sin querer
    if (!it) { form.elements.ac_type.value = 'split'; form.elements.energy_rating.value = 'A++'; }
  }

  function readForm() {
    const form = $('#form-ac');
    const out = {};
    for (const f of FIELDS) {
      const raw = form.elements[f.name].value.trim();
      if (f.kind === 'text' || f.kind === 'select') out[f.name] = raw;
      else if (raw === '') out[f.name] = f.nullable ? null : (f.fallback ?? null);
      else out[f.name] = f.kind === 'int' ? parseInt(raw, 10) : parseFloat(raw);
    }
    for (const c of CHECKS) out[c.name] = form.elements[c.name].checked;
    return out;
  }

  function openForm(item) {
    state.editing = item;
    $('#dlg-form-title').textContent = item ? `Editar ${item.brand} ${item.model}` : 'Añadir equipo';
    $('#btn-save').textContent = item ? 'Guardar cambios' : 'Guardar equipo';
    $('#form-error').hidden = true;
    fillForm(item);
    $('#dlg-form').showModal();
    $('#ff-brand').focus();
  }

  async function submitForm(ev) {
    ev.preventDefault();
    const form = ev.currentTarget;
    if (!form.checkValidity()) { form.reportValidity(); return; }

    const payload = readForm();
    let body = payload;
    if (state.editing) {
      body = {};
      for (const [k, v] of Object.entries(payload)) {
        if (v !== state.editing[k]) body[k] = v; // PATCH: solo lo que cambió
      }
      if (!Object.keys(body).length) { $('#dlg-form').close(); toast('No había cambios que guardar'); return; }
    }

    const btn = $('#btn-save');
    btn.disabled = true;
    $('#form-error').hidden = true;
    try {
      if (state.editing) await api(`/air-conditioners/${state.editing.id}`, { method: 'PATCH', json: body });
      else await api('/air-conditioners/', { method: 'POST', json: body });
      const wasEdit = !!state.editing;
      $('#dlg-form').close();
      toast(wasEdit ? 'Cambios guardados' : 'Equipo añadido');
      await loadList();
    } catch (e) {
      const el = $('#form-error');
      el.textContent = explain(e);
      el.hidden = false;
    } finally {
      btn.disabled = false;
    }
  }

  // ---------- Eliminación ----------
  function openDelete(item) {
    state.deleting = item;
    $('#delete-text').textContent = `Se eliminará ${item.brand} ${item.model} del catálogo. Esta acción no se puede deshacer.`;
    $('#delete-error').hidden = true;
    $('#dlg-delete').showModal();
    $('#dlg-delete [data-close]').focus();
  }

  async function submitDelete(ev) {
    ev.preventDefault();
    const item = state.deleting;
    if (!item) return;
    const btn = $('#btn-confirm-delete');
    btn.disabled = true;
    try {
      await api(`/air-conditioners/${item.id}`, { method: 'DELETE' });
      $('#dlg-delete').close();
      toast('Equipo eliminado');
      await loadList();
    } catch (e) {
      const el = $('#delete-error');
      el.textContent = explain(e);
      el.hidden = false;
    } finally {
      btn.disabled = false;
    }
  }

  // ---------- Entrada al catálogo ----------
  function enterCatalog() {
    $('#me-email').textContent = state.me.email;
    $('#me-role').textContent = isAdmin() ? 'Administrador' : 'Solo lectura';
    $('#btn-new').hidden = !isAdmin();
    show('catalog');
    syncFiltersToUI();
    loadList();
  }

  // ---------- Arranque ----------
  function bind() {
    // Acceso
    $('#tab-login').addEventListener('click', () => selectTab('login'));
    $('#tab-register').addEventListener('click', () => selectTab('register'));
    $('.tabs').addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        const next = $('#tab-login').getAttribute('aria-selected') === 'true' ? 'register' : 'login';
        selectTab(next);
        $('#tab-' + next).focus();
      }
    });
    $('#form-login').addEventListener('submit', submitLogin);
    $('#form-register').addEventListener('submit', submitRegister);
    $('#btn-logout').addEventListener('click', logout);

    // Filtros
    const ff = $('#form-filters');
    ff.addEventListener('submit', (e) => { e.preventDefault(); applyFilters(); });
    ff.addEventListener('input', (e) => {
      const t = e.target;
      if (t.matches('input[type="search"], input[type="number"]')) applyFiltersSoon();
    });
    ff.addEventListener('change', (e) => {
      const t = e.target;
      if (t.matches('select, input[type="checkbox"]')) applyFilters();
    });
    $('#btn-reset').addEventListener('click', resetFilters);
    $('#btn-filters').addEventListener('click', () => {
      const open = $('#filters').classList.toggle('is-open');
      $('#btn-filters').setAttribute('aria-expanded', String(open));
    });

    // Orden, tamaño de página y paginación
    $('#f-sort').addEventListener('change', (e) => { state.sort = e.target.value; state.page = 0; loadList(); });
    $('#f-size').addEventListener('change', (e) => { state.size = parseInt(e.target.value, 10); state.page = 0; loadList(); });
    $('#btn-prev').addEventListener('click', () => { if (state.page > 0) { state.page -= 1; loadList(); $('#results').scrollIntoView({ block: 'start' }); } });
    $('#btn-next').addEventListener('click', () => { state.page += 1; loadList(); $('#results').scrollIntoView({ block: 'start' }); });

    // Diálogos
    $('#btn-new').addEventListener('click', () => openForm(null));
    $('#form-ac').addEventListener('submit', submitForm);
    $('#form-delete').addEventListener('submit', submitDelete);
    for (const d of document.querySelectorAll('dialog')) {
      d.addEventListener('click', (e) => {
        if (e.target === d || e.target.closest('[data-close]')) d.close();
      });
    }
  }

  async function init() {
    buildStaticControls();
    buildFormFields();
    bind();
    $('#f-sort').value = state.sort;
    $('#f-size').value = String(state.size);

    if (!state.token) { showLogin(''); return; }
    try {
      state.me = await api('/users/me');
      enterCatalog();
    } catch (e) {
      if (state.token) { // no fue un 401 (ese caso ya mostró el acceso)
        state.token = '';
        store.del(TOKEN_KEY);
        showLogin(explain(e));
      }
    }
  }

  init();
})();
