/* ═══════════════════════════════════════════════════════════════════════════
   OurHome IL — "Pop" helpers. Extends design-concepts/concept-a/concept.js:
   same tiny, dependency-free approach (globals $, $$, countUp, toast, confetti,
   openSheet, closeSheet) plus what the real app needs: API calls, confirm
   dialog, formatting, share/copy, the labelled radial FAB and nav blob.
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  window.$ = $; window.$$ = $$;
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var HE_DAYS = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת'];
  var HE_DAYS_SHORT = ['א׳', 'ב׳', 'ג׳', 'ד׳', 'ה׳', 'ו׳', 'ש׳'];
  var HE_MONTHS = ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני', 'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר'];

  /* ── text & numbers ── */
  function esc(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function num(n, d) { return (Number(n) || 0).toLocaleString('he-IL', { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 }); }
  /* ₪ with cents only when they exist */
  function money(n) { var v = Number(n) || 0; return '₪' + num(v, Math.abs(v - Math.round(v)) >= 0.005 ? 2 : 0); }
  function money0(n) { return '₪' + num(Math.round(Number(n) || 0)); }
  function pad2(n) { return String(n).padStart(2, '0'); }
  function iso(d) { return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()); }
  function longDate(d) { d = d || new Date(); return 'יום ' + HE_DAYS[d.getDay()] + ' · ' + d.getDate() + ' ב' + HE_MONTHS[d.getMonth()]; }
  function dayLabel(s) {
    var d = String(s || '').split(' ')[0].split('T')[0];
    var t = new Date(), y = new Date(); y.setDate(t.getDate() - 1);
    if (d === iso(t)) return 'היום';
    if (d === iso(y)) return 'אתמול';
    var dt = new Date(d + 'T12:00:00'); if (isNaN(dt)) return d;
    return 'יום ' + HE_DAYS[dt.getDay()] + ' ' + dt.getDate() + '.' + (dt.getMonth() + 1);
  }
  function minutesToWords(m) {
    m = Math.round(m); if (m < 1) return 'פחות מדקה'; if (m < 60) return m + ' דקות';
    var h = Math.floor(m / 60), r = m % 60, hw = h === 1 ? 'שעה' : h === 2 ? 'שעתיים' : h + ' שעות';
    return r ? hw + ' ו-' + r + ' דק׳' : hw;
  }
  function hm(mins) { mins = Math.round(mins || 0); return Math.floor(mins / 60) + ':' + pad2(mins % 60); }
  function hms(secs) { secs = Math.max(0, Math.floor(secs)); return pad2(Math.floor(secs / 3600)) + ':' + pad2(Math.floor(secs % 3600 / 60)) + ':' + pad2(secs % 60); }
  var AV = ['sun', 'coral', 'mint', 'grape', 'peach', ''];
  function avatarClass(name) { var h = 0; String(name || '?').split('').forEach(function (c) { h = (h * 31 + c.charCodeAt(0)) >>> 0; }); return AV[h % AV.length]; }
  function initial(name) { return (String(name || '?').trim()[0] || '?'); }

  /* ── keyword guessing ──
     Shared by the shopping list (departments) and the expense sheet (expense categories): same matching,
     different vocabulary, because the two taxonomies are unrelated. Rules are [value, pattern] pairs in
     priority order, first match wins.
     Hebrew final letters (ך ם ן ף ץ) turn regular inside a longer word — מלפפון becomes מלפפונים — so both
     the pattern and the text are folded before matching. */
  function foldHe(t) { return String(t).replace(/[ךםןףץ]/g, function (c) { return { 'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ' }[c]; }); }
  function guessRules(rules) { return rules.map(function (g) { return [g[0], new RegExp(foldHe(g[1]))]; }); }
  function guessFrom(rules, text) {
    var n = foldHe(text || '').trim();
    if (!n) return '';
    for (var i = 0; i < rules.length; i++) if (rules[i][1].test(n)) return rules[i][0];
    return '';
  }

  /* ── network ──
     Everything the app writes goes through here, so this is where a save is allowed to be called a save.
     Rules, after expenses were reported "נוסף ✓" for six weeks without ever reaching the server:
     - a 200 whose body is not JSON (a login page, a proxy error page) is a FAILURE, not a save
     - 401/403 is its own reason, so the screen can say "log in again" instead of a vague error
     - GET is retried automatically (safe to repeat). POST/PUT/DELETE is never retried on its own:
       /api/payments/add is not idempotent and a blind retry can record the expense twice.
       Callers show the user a retry button instead.
     Returns { ok, status, data } as before, plus `reason` and `retriable` for callers that want them. */
  var NET_MSG = {
    offline: 'אין חיבור לשרת',
    auth: 'פג תוקף ההתחברות — התחברו מחדש',
    server: 'השרת לא הגיב כמו שצריך',
    html: 'השרת החזיר תשובה לא צפויה'
  };
  function sleep(ms) { return new Promise(function (res) { setTimeout(res, ms); }); }

  async function apiOnce(method, url, body) {
    var opts = { method: method, headers: { 'Accept': 'application/json' }, credentials: 'same-origin', cache: 'no-store' };
    if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    var r;
    try { r = await fetch(url, opts); }
    catch (e) { return { ok: false, status: 0, data: { error: NET_MSG.offline }, reason: 'offline', retriable: true }; }
    var text = '', data = null;
    try { text = await r.text(); } catch (e) { text = ''; }
    if (text) { try { data = JSON.parse(text); } catch (e) { data = null; } }
    if (data === null && text && text.trim().charAt(0) === '<') {   /* never reached the API */
      return { ok: false, status: r.status, data: { error: NET_MSG.html }, reason: 'html', retriable: true };
    }
    if (r.status === 401 || r.status === 403) {
      return { ok: false, status: r.status, data: data || { error: NET_MSG.auth }, reason: 'auth', retriable: false };
    }
    if (!r.ok) {
      return { ok: false, status: r.status, data: data || { error: NET_MSG.server },
               reason: r.status >= 500 ? 'server' : 'rejected', retriable: r.status >= 500 };
    }
    return { ok: true, status: r.status, data: data, reason: null, retriable: false };
  }

  /* the sentence to show the user for a failed call, in their words */
  function netMsg(r, fallback) {
    if (!r) return fallback || NET_MSG.server;
    if (r.reason === 'auth') return NET_MSG.auth;
    if (r.reason === 'offline') return NET_MSG.offline;
    if (r.data && r.data.error) return r.data.error;
    return fallback || NET_MSG.server;
  }

  async function api(method, url, body) {
    var r = await apiOnce(method, url, body);
    if (String(method).toUpperCase() === 'GET') {
      for (var i = 0; i < 2 && !r.ok && r.retriable; i++) { await sleep(400 * (i + 1)); r = await apiOnce(method, url, body); }
    }
    return r;
  }

  /* ── count-up (from concept.js, with a guaranteed settle) ── */
  function countUp(el, to, o) {
    if (!el) return; o = o || {};
    var prefix = o.prefix || '', suffix = o.suffix || '', dur = o.dur || 1000, dec = o.decimals || 0;
    var from = parseFloat(el.dataset.v || '0'); if (!isFinite(from)) from = 0; el.dataset.v = to;
    var fmt = function (v) { return prefix + num(v, dec) + suffix; };
    if (reduceMotion || from === to) { el.textContent = fmt(to); return; }
    var t0 = performance.now();
    (function tick(now) { var p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 4); el.textContent = fmt(from + (to - from) * e); if (p < 1) requestAnimationFrame(tick); })(t0);
    setTimeout(function () { el.textContent = fmt(to); }, dur + 80);
  }

  /* ── toast ── */
  function toast(msg, type) {
    if (type === 'danger') type = 'error';
    var w = $('#toastWrap'); if (!w) { w = document.createElement('div'); w.id = 'toastWrap'; w.className = 'toast-wrap'; w.setAttribute('aria-live', 'polite'); document.body.appendChild(w); }
    var t = document.createElement('div'); t.className = 'toast ' + (type || ''); t.setAttribute('role', 'status'); t.textContent = msg;
    w.appendChild(t);
    setTimeout(function () { t.classList.add('out'); setTimeout(function () { t.remove(); }, 320); }, 2600);
  }

  /* ── confetti (from concept.js) ── */
  function confetti(x, y, n) {
    if (reduceMotion) return;
    if (x && x.getBoundingClientRect) { var r = x.getBoundingClientRect(); n = y; x = r.left + r.width / 2; y = r.top + r.height / 2; }
    n = n || 40;
    var c = $('#confetti'); if (!c) { c = document.createElement('canvas'); c.id = 'confetti'; document.body.appendChild(c); }
    var dpr = window.devicePixelRatio || 1; c.width = innerWidth * dpr; c.height = innerHeight * dpr; c.style.width = innerWidth + 'px'; c.style.height = innerHeight + 'px';
    var ctx = c.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    var cols = ['#FF5C6C', '#FFC531', '#2FD59A', '#3E9BFF', '#8F6BFF', '#FF9E64'];
    var ps = Array.from({ length: n }, function () { return { x: x, y: y, vx: (Math.random() - .5) * 11, vy: -Math.random() * 9 - 4, r: Math.random() * 5 + 3, c: cols[Math.random() * cols.length | 0], rot: Math.random() * 6, vr: (Math.random() - .5) * .4, life: 1 }; });
    var t0 = performance.now();
    (function frame(now) {
      var dt = Math.min(32, now - t0) / 16; t0 = now; ctx.clearRect(0, 0, innerWidth, innerHeight); var alive = false;
      ps.forEach(function (p) { p.vy += .35 * dt; p.x += p.vx * dt; p.y += p.vy * dt; p.rot += p.vr; p.life -= .012 * dt; if (p.life <= 0) return; alive = true;
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot); ctx.globalAlpha = Math.max(0, p.life); ctx.fillStyle = p.c; ctx.fillRect(-p.r, -p.r * .6, p.r * 2, p.r * 1.2); ctx.restore(); });
      if (alive) requestAnimationFrame(frame); else ctx.clearRect(0, 0, innerWidth, innerHeight);
    })(t0);
  }
  function squish(el) { if (!el) return; el.classList.remove('squish'); void el.offsetWidth; el.classList.add('squish'); }

  /* ── sheets (bottom) ── */
  var openCount = 0;
  function lock(on) { openCount = Math.max(0, openCount + (on ? 1 : -1)); document.body.style.overflow = openCount ? 'hidden' : ''; }
  function openSheet(id) {
    var el = typeof id === 'string' ? document.getElementById(id) : id; if (!el || el.classList.contains('open')) return;
    el.classList.add('open'); lock(true);
    var s = $('.sheet', el); if (s) s.scrollTop = 0;
  }
  function closeSheet(id) {
    var el = typeof id === 'string' ? document.getElementById(id) : id; if (!el || !el.classList.contains('open')) return;
    el.classList.remove('open'); lock(false);
  }
  document.addEventListener('click', function (e) {
    var ov = e.target.closest && e.target.closest('.sheet-ov');
    if (ov && e.target === ov) closeSheet(ov);
    var c = e.target.closest && e.target.closest('[data-close]');
    if (c) closeSheet(c.getAttribute('data-close'));
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var d = $$('.dialog-ov'); if (d.length) { var cancel = $('[data-cancel]', d[d.length - 1]); if (cancel) cancel.click(); return; }
    var o = $$('.sheet-ov.open'); if (o.length) closeSheet(o[o.length - 1]);
  });

  /* ── confirm dialog (Promise) ── */
  function confirmPop(o) {
    o = o || {};
    return new Promise(function (resolve) {
      var w = document.createElement('div'); w.className = 'dialog-ov';
      w.innerHTML = '<div class="dialog" role="dialog" aria-modal="true"><h3>' + esc(o.title || 'לאשר?') + '</h3>' + (o.text ? '<p>' + esc(o.text) + '</p>' : '') +
        '<div class="sheet-actions"><button type="button" class="btn block ' + (o.danger ? 'danger' : 'mint') + '" data-ok>' + esc(o.ok || 'אישור') + '</button>' +
        '<button type="button" class="text-btn" data-cancel>' + esc(o.cancel || 'ביטול') + '</button></div></div>';
      document.body.appendChild(w); lock(true);
      var done = function (v) { w.remove(); lock(false); resolve(v); };
      $('[data-ok]', w).addEventListener('click', function () { done(true); });
      $('[data-cancel]', w).addEventListener('click', function () { done(false); });
      w.addEventListener('click', function (e) { if (e.target === w) done(false); });
      setTimeout(function () { $('[data-ok]', w).focus(); }, 30);
    });
  }

  /* ── clipboard / share (WebView-safe) ── */
  function copyText(text) {
    var fb = function () { return new Promise(function (res) { var ta = document.createElement('textarea'); ta.value = text; ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0'; document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); } catch (e) {} ta.remove(); res(); }); };
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text).catch(fb);
    return fb();
  }
  function share(title, text) {
    var copy = function () { return copyText(text).then(function () { toast('הטקסט הועתק — אפשר להדביק בוואטסאפ', 'success'); }); };
    var cancelled = function (e) { return e && (e.name === 'AbortError' || /cancel/i.test(e.message || '')); };
    if (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Share) { return window.Capacitor.Plugins.Share.share({ title: title, text: text }).catch(function (e) { if (!cancelled(e)) return copy(); }); }
    if (navigator.share) { return navigator.share({ title: title, text: text }).catch(function (e) { if (!cancelled(e)) return copy(); }); }
    return copy();
  }
  function onVisible(fn) { document.addEventListener('visibilitychange', function () { if (!document.hidden) fn(); }); }

  /* ── page chrome: nav blob, FAB, password toggles ── */
  document.addEventListener('DOMContentLoaded', function () {
    var nav = $('.nav-pill');
    if (nav) {
      var blob = $('.nav-blob', nav), cur = parseInt(nav.style.getPropertyValue('--i'), 10) || 0, prev = null;
      try { prev = sessionStorage.getItem('navIdx'); sessionStorage.setItem('navIdx', cur); } catch (e) {}
      if (prev !== null && +prev !== cur && !reduceMotion) {
        blob.classList.add('still'); nav.style.setProperty('--i', prev);
        requestAnimationFrame(function () { requestAnimationFrame(function () { blob.classList.remove('still'); nav.style.setProperty('--i', cur); }); });
      }
    }
    var fw = $('.fab-wrap');
    if (fw) {
      var scrim = $('.fab-scrim'), fab = $('.fab', fw), label = $('.lbl', fab);
      var items = $$('.fab-item', fw), R = 104;
      var place = function (open) {
        items.forEach(function (b, i) {
          /* first item on the reading-start side: right in RTL */
          var a = Math.PI * (items.length === 1 ? .5 : (i / (items.length - 1))), dir = document.documentElement.dir === 'rtl' ? 1 : -1;
          var x = dir * Math.cos(a) * R, y = -Math.sin(a) * R * .95 - 18;
          b.style.transform = open ? 'translate(' + x.toFixed(0) + 'px,' + y.toFixed(0) + 'px) scale(1)' : 'translate(0,0) scale(.3)';
        });
      };
      /* each page names its own FAB — "הוספה" where the menu only creates things, "פעולות" where it
         also opens a view — so keep that word instead of hardcoding one here */
      var closedLabel = (label && label.textContent.trim()) || 'הוספה';
      var toggle = function (force) {
        var open = typeof force === 'boolean' ? force : !fw.classList.contains('open');
        fw.classList.toggle('open', open); if (scrim) scrim.classList.toggle('show', open);
        fab.setAttribute('aria-expanded', String(open)); if (label) label.textContent = open ? 'סגירה' : closedLabel;
        items.forEach(function (b) { b.tabIndex = open ? 0 : -1; b.setAttribute('aria-hidden', String(!open)); });
        place(open);
      };
      toggle(false);
      /* slide away only while scrolling down (so content passing under it is readable);
         it comes back as soon as scrolling stops, on scroll up, or at the end of the page */
      var lastY = window.scrollY, idle = null;
      window.addEventListener('scroll', function () {
        var y = window.scrollY, down = y > lastY + 6, up = y < lastY - 6;
        var atEnd = y + innerHeight >= document.documentElement.scrollHeight - 150;
        if (!fw.classList.contains('open')) {
          if (down && y > 120 && !atEnd) fw.classList.add('away'); else if (up || y < 60 || atEnd) fw.classList.remove('away');
        }
        if (down || up) lastY = y;
        clearTimeout(idle); idle = setTimeout(function () { fw.classList.remove('away'); }, 700);
      }, { passive: true });
      fab.addEventListener('click', function () { toggle(); });
      if (scrim) scrim.addEventListener('click', function () { toggle(false); });
      items.forEach(function (b) { b.addEventListener('click', function () { toggle(false); }); });
    }
    $$('[data-toggle-pw]').forEach(function (b) {
      b.addEventListener('click', function () {
        var i = document.getElementById(b.getAttribute('data-toggle-pw')); if (!i) return;
        var show = i.type === 'password'; i.type = show ? 'text' : 'password';
        var s = $('span', b); if (s) s.textContent = show ? 'הסתר' : 'הצג';
      });
    });
  });

  window.Pop = {
    esc: esc, num: num, money: money, money0: money0, iso: iso, pad2: pad2, longDate: longDate, dayLabel: dayLabel,
    minutesToWords: minutesToWords, hm: hm, hms: hms, avatarClass: avatarClass, initial: initial,
    api: api, netMsg: netMsg, foldHe: foldHe, guessRules: guessRules, guessFrom: guessFrom,
    countUp: countUp, toast: toast, confetti: confetti, squish: squish,
    openSheet: openSheet, closeSheet: closeSheet, confirm: confirmPop, copyText: copyText, share: share, onVisible: onVisible,
    HE_DAYS: HE_DAYS, HE_DAYS_SHORT: HE_DAYS_SHORT, HE_MONTHS: HE_MONTHS, reduceMotion: reduceMotion
  };
  /* concept.js-compatible globals */
  window.countUp = countUp; window.toast = toast; window.confetti = confetti; window.openSheet = openSheet; window.closeSheet = closeSheet;
  window.showToast = toast;   /* legacy name used by flashed messages */
})();
