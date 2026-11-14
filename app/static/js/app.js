/* PaUtos — UI behaviour (presentation only).
   Adapted from PhilReg's app.js: password toggle + strength meter, step wizard,
   dismissible messages. Nothing here changes what the server receives: the register
   form still submits the same fields as one normal POST, and the server remains the
   source of truth for validation. */
(function () {
  'use strict';

  const $  = (id) => document.getElementById(id);
  const qs = (sel, ctx = document) => ctx.querySelector(sel);
  const qsa = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));


  /* ── Light / dark theme (light is the default; choice is remembered) ───── */
  const root = document.documentElement;
  const metaTheme = qs('meta[name="theme-color"]');
  const metaScheme = qs('meta[name="color-scheme"]');
  function applyTheme(t) {
    if (t === 'light') root.setAttribute('data-theme', 'light'); else root.removeAttribute('data-theme');
    if (metaTheme) metaTheme.setAttribute('content', t === 'light' ? '#e1e2e4' : '#1b1a20');
    if (metaScheme) metaScheme.setAttribute('content', t === 'light' ? 'light' : 'dark');
    qsa('.theme-toggle').forEach((b) => {
      b.setAttribute('aria-label', t === 'light' ? 'Switch to dark mode' : 'Switch to light mode');
    });
  }
  applyTheme(root.getAttribute('data-theme') === 'light' ? 'light' : 'dark');
  qsa('.theme-toggle').forEach((b) => b.addEventListener('click', () => {
    const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    applyTheme(next);
    try { localStorage.setItem('pautos-theme', next); } catch (e) { /* private mode: still works for this page */ }
  }));

  /* ── Flash messages: dismiss button + auto-hide for success/info ───────── */
  function dismissFlash(el) {
    el.classList.add('leaving');
    setTimeout(() => el.remove(), 320);
  }
  qsa('.flash').forEach((el) => {
    const btn = qs('.flash-close', el);
    if (btn) btn.addEventListener('click', () => dismissFlash(el));
    if (!el.classList.contains('error')) setTimeout(() => dismissFlash(el), 6000);
  });

  /* ── Password show / hide ──────────────────────────────────────────────── */
  qsa('.pw-toggle').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = qs('input', btn.closest('.pw-wrap'));
      if (!input) return;
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.setAttribute('aria-pressed', String(show));
      btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    });
  });

  /* ── Password strength meter (inputs marked data-strength) ─────────────── */
  qsa('input[data-strength]').forEach((input) => {
    const box = qs('.pw-strength', input.closest('.field'));
    if (!box) return;
    const bars = qsa('.pw-bar', box);
    const label = qs('.pw-label', box);
    input.addEventListener('input', () => {
      const v = input.value;
      const score = v ? [v.length >= 8, /[A-Z]/.test(v), /\d/.test(v), /[^A-Za-z0-9]/.test(v)].filter(Boolean).length : 0;
      const level = score <= 2 ? 'weak' : score === 3 ? 'fair' : 'strong';
      bars.forEach((b, i) => { b.className = 'pw-bar' + (i < score ? ' fill-' + level : ''); });
      label.className = 'pw-label' + (score ? ' ' + level : '');
      label.textContent = score ? level.charAt(0).toUpperCase() + level.slice(1) : '';
    });
  });

  /* ── Clear a field's error once the user edits it ──────────────────────── */
  function clearFieldError(input) {
    const field = input.closest('.field');
    if (!field) return;
    input.classList.remove('is-invalid');
    input.removeAttribute('aria-invalid');
    field.classList.remove('has-error');
    qsa('.field-error', field).forEach((e) => {
      if (e.classList.contains('js-error')) { e.hidden = true; e.textContent = ''; }
      else e.remove();
    });
  }
  qsa('.field input, .field select').forEach((el) => {
    el.addEventListener('input', () => clearFieldError(el));
    el.addEventListener('change', () => clearFieldError(el));
  });

  /* ── Register: rider-only fields (same behaviour as the old inline script) */
  const roleSelect = $('role');
  const riderFields = $('rider-fields');
  function toggleRider() {
    if (roleSelect && riderFields) riderFields.hidden = roleSelect.value !== 'rider';
  }
  if (roleSelect && riderFields) {
    roleSelect.addEventListener('change', toggleRider);
    toggleRider();
  }

  /* ── Register wizard ───────────────────────────────────────────────────── */
  const form = qs('form[data-wizard]');
  if (form) initWizard(form);

  function initWizard(form) {
    const panes = qsa('.form-step', form);
    const stepEls = qsa('#reg-steps .step');
    const back = $('btn-back');
    const next = $('btn-next');
    let current = Math.max(0, panes.findIndex((p) => p.classList.contains('active')));

    // Mirrors the server's rules for instant feedback. The server still validates everything.
    function normalizePhone(raw) {
      const d = (raw || '').replace(/[\s\-()]/g, '');
      if (/^09\d{9}$/.test(d)) return '+63' + d.slice(1);
      if (/^\+639\d{9}$/.test(d)) return d;
      if (/^639\d{9}$/.test(d)) return '+' + d;
      return null;
    }
    const val = (id) => ($(id) ? $(id).value : '');
    const isRider = () => val('role') === 'rider';

    const rules = {
      role: (v) => (v ? '' : 'Choose an account type.'),
      full_name: (v) => (v.trim().length < 2 ? 'Enter your full name (at least 2 characters).' : ''),
      email: (v) => (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim()) ? '' : 'Enter a valid email address.'),
      phone: (v) => (normalizePhone(v) ? '' : 'Enter a valid PH mobile number (e.g. 09171234567).'),
      vehicle_type: (v) => (isRider() && !v ? 'Please select your vehicle type.' : ''),
      plate_number: (v) => (isRider() && ['motorcycle', 'car'].includes(val('vehicle_type')) && !v.trim()
        ? 'Plate number is required for this vehicle.' : ''),
      password: (v) => (v.length < 8 ? 'Use at least 8 characters.'
        : !(/[A-Za-z]/.test(v) && /\d/.test(v)) ? 'Password must contain at least one letter and one number.' : ''),
      confirm_password: (v) => (v !== val('password') || !v ? 'Passwords must match.' : ''),
    };

    function setError(input, msg) {
      const field = input.closest('.field');
      const slot = qs('.js-error', field);
      if (!slot) return !msg;
      if (msg) {
        input.classList.add('is-invalid');
        input.setAttribute('aria-invalid', 'true');
        qsa('.field-error.server', field).forEach((e) => e.remove());
        slot.textContent = msg;
        slot.hidden = false;
      } else {
        input.classList.remove('is-invalid');
        input.removeAttribute('aria-invalid');
        slot.hidden = true;
        slot.textContent = '';
      }
      return !msg;
    }

    // Validate every visible field in one pane; returns the first invalid input (or null).
    function validatePane(index) {
      let firstBad = null;
      qsa('input, select', panes[index]).forEach((input) => {
        if (input.type === 'hidden' || input.closest('[hidden]')) return;
        const rule = rules[input.id];
        if (!rule) return;
        if (!setError(input, rule(input.value)) && !firstBad) firstBad = input;
      });
      return firstBad;
    }

    function render(focus) {
      panes.forEach((p, i) => p.classList.toggle('active', i === current));
      stepEls.forEach((el, i) => {
        el.classList.toggle('active', i === current);
        el.classList.toggle('done', i < current);
        if (i === current) el.setAttribute('aria-current', 'step'); else el.removeAttribute('aria-current');
      });
      form.classList.toggle('on-first', current === 0);
      form.classList.toggle('on-last', current === panes.length - 1);
      if (focus) {
        const f = qs('input:not([type=hidden]), select', panes[current]);
        if (f) f.focus();
      }
    }

    function go(n, focus) {
      current = Math.min(Math.max(n, 0), panes.length - 1);
      render(focus);
    }

    next.addEventListener('click', () => {
      const bad = validatePane(current);
      if (bad) { bad.focus(); return; }
      go(current + 1, true);
    });
    back.addEventListener('click', () => go(current - 1, true));

    // Enter advances the wizard instead of submitting early.
    form.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter' || e.target.tagName === 'BUTTON' || e.target.tagName === 'TEXTAREA') return;
      if (current < panes.length - 1) { e.preventDefault(); next.click(); }
    });

    // Final submit: re-check every step; jump back to the first problem if any.
    form.addEventListener('submit', (e) => {
      for (let i = 0; i < panes.length; i++) {
        const bad = validatePane(i);
        if (bad) {
          e.preventDefault();
          go(i, false);
          bad.focus();
          return;
        }
      }
      const submit = $('btn-submit');
      if (submit) { submit.disabled = true; submit.innerHTML = '<span class="spinner"></span> Creating account…'; }
    });

    render(false);
  }


  /* ── New request: highlight the chosen service + show its fee ──────────── */
  const catSelect = $('category_id');
  const catHints = qsa('.cat-hints li');
  if (catSelect && catHints.length) {
    const budgetField = $('item_budget') ? $('item_budget').closest('.field') : null;
    const budgetLabel = budgetField ? qs('label', budgetField) : null;
    const sync = () => {
      let purchase = false;
      catHints.forEach((li) => {
        const on = li.dataset.id === catSelect.value;
        li.classList.toggle('is-selected', on);
        if (on) purchase = li.dataset.purchase === '1';
      });
      if (budgetLabel) {
        const star = qs('.req', budgetLabel);
        if (purchase && !star) {
          const s = document.createElement('span');
          s.className = 'req'; s.setAttribute('aria-hidden', 'true'); s.textContent = '*';
          budgetLabel.appendChild(s);
        } else if (!purchase && star) star.remove();
      }
    };
    catSelect.addEventListener('change', sync);
    sync();
  }

  /* ── Prevent double-submits on forms marked data-once ──────────────────── */
  qsa('form[data-once]').forEach((f) => {
    f.addEventListener('submit', (e) => {
      if (e.defaultPrevented) return;
      const btn = e.submitter || qs('button[type="submit"]', f);
      if (!btn) return;
      setTimeout(() => {
        qsa('button[type="submit"]', f).forEach((b) => { b.disabled = true; });
        btn.dataset.label = btn.innerHTML;
        btn.innerHTML = '<span class="spinner"></span> Please wait…';
      }, 0);
    });
  });

  // Restore buttons if the page comes back from the back/forward cache mid-submit.
  window.addEventListener('pageshow', (e) => {
    if (!e.persisted) return;
    const submit = $('btn-submit');
    if (submit) { submit.disabled = false; submit.textContent = 'Create account'; }
    qsa('form[data-once] button[type="submit"]').forEach((b) => {
      b.disabled = false;
      if (b.dataset.label) b.innerHTML = b.dataset.label;
    });
  });
})();
