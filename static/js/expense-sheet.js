/* Add / edit expense sheet (templates/_expense_sheet.html). Real API:
   POST /api/payments/add · PUT /api/payments/<id> · POST /delete_payment/<id>?api=1 · GET /api/categories */
(function () {
  'use strict';
  var cats = null, amt = '', cat = null, editId = null, onSaved = null, origDate = '', cycle = null;
  var $ = function (id) { return document.getElementById(id); };
  var LAST = 'lastExpenseCat';

  async function loadCats() {
    if (cats) return cats;
    var r = await Pop.api('GET', '/api/categories');
    cats = (r.ok && Array.isArray(r.data)) ? r.data : [];
    /* the family's most-used categories first would need usage data; defaults stay alphabetical, as in the API */
    return cats;
  }
  async function loadCycle() {   // the current cycle's first day: the earliest date an expense can be moved to
    if (cycle) return cycle;
    var r = await Pop.api('GET', '/api/family/cycle');
    cycle = (r.ok && r.data) ? r.data : {};
    return cycle;
  }
  function paintAmt() { $('expAmt').textContent = amt ? amt : '0'; }
  function paintCats() {
    $('expCats').innerHTML = cats.map(function (c) {
      return '<button type="button" class="chip-btn' + (c.name === cat ? ' on' : '') + '" role="radio" aria-checked="' + (c.name === cat) + '" data-cat="' + Pop.esc(c.name) + '">' +
        '<i class="dot" style="background:' + Pop.esc(c.color) + '"></i>' + Pop.esc(c.name) + '</button>';
    }).join('');
    var on = $('expCats').querySelector('.on'); if (on) on.scrollIntoView({ inline: 'center', block: 'nearest' });
  }

  async function open(opts) {
    opts = opts || {}; onSaved = opts.onSaved || null;
    await loadCats();
    var p = opts.payment || null; editId = p ? p.id : null;
    if (p) await loadCycle();
    var last = null; try { last = localStorage.getItem(LAST); } catch (e) {}
    cat = p ? p.category : (opts.category || (cats.some(function (c) { return c.name === last; }) ? last : (cats[0] && cats[0].name)));
    amt = p ? String(+p.amount) : (opts.amount ? String(opts.amount) : '');
    $('expDesc').value = p ? p.description : (opts.description || '');
    $('expTitle').textContent = p ? '✏️ עריכת תשלום' : '💸 הוצאה חדשה';
    $('expSave').firstElementChild.textContent = p ? '💾' : '💸';
    $('expSaveT').textContent = p ? 'שמירה' : 'הוספת ההוצאה';
    $('expDelete').classList.toggle('hidden', !p);
    $('expWho').classList.toggle('hidden', !!p);
    // date: editable when editing, limited to the current cycle and today
    origDate = p && p.date ? String(p.date).slice(0, 10) : '';
    $('expDateWrap').classList.toggle('hidden', !p);
    $('expDate').value = origDate;
    $('expDate').max = Pop.iso(new Date());
    if (cycle && cycle.start_date) $('expDate').min = cycle.start_date; else $('expDate').removeAttribute('min');
    paintAmt(); paintCats();
    Pop.openSheet('expSheet');
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!$('expSheet')) return;
    $('expKeys').addEventListener('click', function (e) {
      var k = e.target.closest('.key'); if (!k) return;
      var v = k.getAttribute('data-k') || k.textContent.trim();
      if (v === 'del') amt = amt.slice(0, -1);
      else if (v === '.') { if (amt.indexOf('.') < 0) amt = (amt || '0') + '.'; }
      else {
        var parts = amt.split('.');
        if (parts.length > 1 && parts[1].length >= 2) return;
        if (parts[0].length >= 7 && parts.length === 1) return;
        amt = (amt === '0' ? '' : amt) + v;
      }
      Pop.squish(k); paintAmt();
    });
    $('expCats').addEventListener('click', function (e) {
      var b = e.target.closest('[data-cat]'); if (!b) return;
      cat = b.getAttribute('data-cat'); paintCats();
    });
    $('expSave').addEventListener('click', async function () {
      var a = parseFloat(amt);
      if (!a || a <= 0) { Pop.toast('הקלידו סכום בעזרת המקלדת', 'error'); Pop.squish($('expAmt').parentNode); return; }
      var desc = $('expDesc').value.trim() || cat;
      var body = { description: desc, amount: a, category: cat };
      if (editId) {
        var d = $('expDate').value;
        if (!d) { Pop.toast('בחרו תאריך', 'error'); $('expDate').focus(); return; }
        if (d > $('expDate').max) { Pop.toast('אי אפשר לבחור תאריך עתידי', 'error'); $('expDate').focus(); return; }
        if ($('expDate').min && d < $('expDate').min) { Pop.toast('אפשר לבחור תאריך רק מתוך המחזור הנוכחי', 'error'); $('expDate').focus(); return; }
        if (d !== origDate) body.date = d;
      }
      var btn = this; btn.disabled = true;
      var r = editId ? await Pop.api('PUT', '/api/payments/' + editId, body)
                     : await Pop.api('POST', '/api/payments/add', body);
      btn.disabled = false;
      if (!r.ok) { Pop.toast((r.data && r.data.error) || 'השמירה נכשלה', 'error'); return; }
      try { localStorage.setItem(LAST, cat); } catch (e) {}
      Pop.confetti(btn, 50);
      Pop.toast(editId ? 'התשלום עודכן ✓' : Pop.money(a) + ' נרשם ✓', 'success');
      Pop.closeSheet('expSheet');
      if (onSaved) onSaved({ id: editId, amount: a, category: cat, description: desc });
    });
    $('expDelete').addEventListener('click', async function () {
      if (!editId) return;
      var ok = await Pop.confirm({ title: 'למחוק את התשלום?', text: 'אי אפשר לבטל מחיקה.', ok: 'כן, למחוק', danger: true });
      if (!ok) return;
      var r = await Pop.api('POST', '/delete_payment/' + editId + '?api=1');
      if (!r.ok) { Pop.toast('המחיקה נכשלה', 'error'); return; }
      Pop.toast('התשלום נמחק', 'success'); Pop.closeSheet('expSheet');
      if (onSaved) onSaved({ id: editId, deleted: true });
    });
  });

  window.ExpenseSheet = { open: open };
})();
