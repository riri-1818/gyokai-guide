// 業界研究ガイド：メニューの開け閉め、グラフ描画、3社比較シートの保存
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';

  // ---- スマホのメニュー ----
  var btn = document.getElementById('menu-btn');
  var side = document.getElementById('side');
  if (btn && side) {
    var setOpen = function (on) {
      side.classList.toggle('open', on);
      btn.setAttribute('aria-expanded', on ? 'true' : 'false');
      btn.textContent = on ? '閉じる' : '業界一覧';
    };
    btn.addEventListener('click', function () { setOpen(!side.classList.contains('open')); });
    side.addEventListener('click', function (e) { if (e.target.closest('a')) setOpen(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') setOpen(false); });
    document.addEventListener('click', function (e) {
      if (side.classList.contains('open') && !side.contains(e.target) && e.target !== btn) setOpen(false);
    });
  }

  // ---- 小道具 ----
  function el(name, attrs, parent) {
    var n = document.createElementNS(NS, name);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }
  function txt(parent, x, y, s, extra) {
    var t = el('text', Object.assign({ x: x, y: y, 'font-size': 12 }, extra || {}), parent);
    t.textContent = s;
    return t;
  }
  function fmt(v) { return v.toLocaleString('ja-JP'); }
  function niceStep(range) {
    var raw = range / 4, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var steps = [1, 2, 2.5, 5, 10].map(function (m) { return m * mag; });
    for (var i = 0; i < steps.length; i++) if (steps[i] >= raw) return steps[i];
    return steps[steps.length - 1];
  }
  var COLORS = ['var(--c1)', 'var(--c2)', 'var(--c3)', 'var(--c4)', 'var(--c5)', 'var(--c6)'];

  // ---- 折れ線（純利益の5期分） ----
  function drawLine(box, spec) {
    box.innerHTML = '';
    var W = Math.max(280, box.clientWidth), narrow = W < 520;
    var H = narrow ? 240 : 300, L = narrow ? 50 : 60, R = 14, T = 14, B = 30;
    var names = Object.keys(spec.series);
    var order = [spec.hl].concat(names.filter(function (n) { return n !== spec.hl; }));
    var color = {}; order.forEach(function (n, i) { color[n] = COLORS[i % COLORS.length]; });
    var all = [];
    names.forEach(function (n) { spec.series[n].forEach(function (v) { if (v !== null) all.push(v); }); });
    var lo = Math.min(0, Math.min.apply(null, all)), hi = Math.max(0, Math.max.apply(null, all));
    var step = niceStep(hi - lo);
    lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
    var n = spec.x.length;
    var X = function (i) { return L + i * (W - L - R) / (n - 1); };
    var Y = function (v) { return T + (hi - v) / (hi - lo) * (H - T - B); };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img', 'aria-label': spec.title }, box);
    for (var t = lo; t <= hi + 1e-9; t += step) {
      el('line', { x1: L, x2: W - R, y1: Y(t), y2: Y(t), style: 'stroke:var(--line)' + (t === 0 ? ';stroke:var(--muted);stroke-opacity:.6' : '') }, svg);
      txt(svg, L - 8, Y(t) + 4, fmt(t), { 'text-anchor': 'end', 'font-size': narrow ? 11 : 12 });
    }
    spec.x.forEach(function (f, i) {
      txt(svg, X(i), H - 8, narrow ? f.replace('年度', '') : f, { 'text-anchor': 'middle', 'font-size': narrow ? 11 : 12 });
    });
    if (narrow) txt(svg, W - R, H - 8, '年度', { 'text-anchor': 'end', 'font-size': 10, opacity: .7 }).setAttribute('dy', 0);
    order.slice().reverse().forEach(function (name) {
      var vals = spec.series[name], on = name === spec.hl, d = '', pen = false;
      vals.forEach(function (v, i) {
        if (v === null) { pen = false; return; }
        d += (pen ? 'L' : 'M') + X(i) + ' ' + Y(v) + ' ';
        pen = true;
      });
      el('path', { d: d, fill: 'none', style: 'stroke:' + color[name] + ';stroke-width:' + (on ? 3 : 2) + ';stroke-linejoin:round' }, svg);
      vals.forEach(function (v, i) {
        if (v === null) return;
        var c = el('circle', { cx: X(i), cy: Y(v), r: on ? 4.5 : 3.2, style: 'fill:' + color[name] + ';stroke:var(--surface);stroke-width:1.5' }, svg);
        el('title', {}, c).textContent = name + ' ' + spec.x[i] + '：' + fmt(v) + spec.unit;
      });
    });
    // なぞると、その年度の全社の数字が出る
    var guide = el('line', { y1: T, y2: H - B, style: 'stroke:var(--muted);stroke-dasharray:3 3;opacity:0' }, svg);
    var tip = document.createElement('div'); tip.className = 'ctip'; box.appendChild(tip);
    var hit = el('rect', { x: L, y: T, width: W - L - R, height: H - T - B, fill: 'transparent' }, svg);
    function show(clientX) {
      var r = svg.getBoundingClientRect(), x = (clientX - r.left) * (W / r.width);
      var i = Math.max(0, Math.min(n - 1, Math.round((x - L) / ((W - L - R) / (n - 1)))));
      guide.setAttribute('x1', X(i)); guide.setAttribute('x2', X(i)); guide.style.opacity = 1;
      var rows = order.filter(function (nm) { return spec.series[nm][i] !== null; })
        .sort(function (a, b) { return spec.series[b][i] - spec.series[a][i]; })
        .map(function (nm) { return nm + '　' + fmt(spec.series[nm][i]) + spec.unit; });
      tip.innerHTML = '<b>' + spec.x[i] + '</b>' + rows.join('<br>');
      tip.classList.add('on');
      var px = X(i) * (r.width / W), tw = tip.offsetWidth;
      tip.style.left = Math.max(0, Math.min(r.width - tw, px + 12 > r.width - tw ? px - tw - 12 : px + 12)) + 'px';
      tip.style.top = '8px';
    }
    function hide() { guide.style.opacity = 0; tip.classList.remove('on'); }
    hit.addEventListener('pointermove', function (e) { show(e.clientX); });
    hit.addEventListener('pointerdown', function (e) { show(e.clientX); });
    hit.addEventListener('pointerleave', hide);
    // 凡例（最新期の数字つき）
    var lg = document.createElement('div'); lg.className = 'legend-list';
    order.forEach(function (name) {
      var vals = spec.series[name], last = vals[vals.length - 1];
      var s = document.createElement('span'); if (name === spec.hl) s.className = 'hl';
      s.innerHTML = '<i style="background:' + color[name] + '"></i>' + name + ' <b>' + fmt(last) + spec.unit + '</b>';
      lg.appendChild(s);
    });
    var note = document.createElement('span'); note.style.color = 'var(--muted)'; note.textContent = '（数字は' + spec.x[n - 1] + '）';
    lg.appendChild(note);
    box.appendChild(lg);
  }

  // ---- 階段グラフ（日銀の政策金利） ----
  function drawStep(box, spec) {
    box.innerHTML = '';
    var W = Math.max(280, box.clientWidth), narrow = W < 520;
    var H = narrow ? 250 : 300, L = 44, R = 14, T = 20, B = 30;
    var t0 = Date.parse('2015-07-01'), t1 = Date.parse('2026-12-31'), lo = -0.25, hi = 1.5;
    var X = function (d) { return L + (Date.parse(d) - t0) / (t1 - t0) * (W - L - R); };
    var Y = function (v) { return T + (hi - v) / (hi - lo) * (H - T - B); };
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, width: W, height: H, role: 'img', 'aria-label': spec.title }, box);
    [0, 0.5, 1].forEach(function (v) {
      el('line', { x1: L, x2: W - R, y1: Y(v), y2: Y(v), style: v === 0 ? 'stroke:var(--muted);stroke-opacity:.6' : 'stroke:var(--line)' }, svg);
      txt(svg, L - 8, Y(v) + 4, v + '%', { 'text-anchor': 'end' });
    });
    for (var y = 2016; y <= 2026; y += narrow ? 4 : 2) txt(svg, X(y + '-01-01'), H - 8, y + '年', { 'text-anchor': 'middle', 'font-size': narrow ? 11 : 12 });
    var rows = spec.rows, d = '';
    rows.forEach(function (r, i) { d += i === 0 ? 'M' + X(r[0]) + ' ' + Y(r[1]) : ' H' + X(r[0]) + ' V' + Y(r[1]); });
    d += ' H' + X('2026-10-21');
    el('path', { d: d, fill: 'none', style: 'stroke:var(--c1);stroke-width:3' }, svg);
    rows.forEach(function (r, i) {
      var c = el('circle', { cx: X(r[0]), cy: Y(r[1]), r: 4, style: 'fill:var(--c1)' }, svg);
      el('title', {}, c).textContent = r[0] + '：' + r[2];
      var last = i === rows.length - 1;
      if (i === 0) txt(svg, (X(rows[0][0]) + X(rows[1][0])) / 2, Y(r[1]) + 20, r[2], { 'text-anchor': 'middle', 'font-size': narrow ? 11 : 12 });
      else if (!narrow || last || i % 2 === 0) {
        var lab = narrow && !last ? r[2].replace(/（.*）/, '') : r[2];
        txt(svg, X(r[0]) - 7, Y(r[1]) - 7, lab, { 'text-anchor': 'end', 'font-size': narrow ? 11 : 12, 'font-weight': last ? 700 : 400, style: last ? 'fill:var(--ink)' : '' });
      }
    });
  }

  // ---- ROE（業界ごとの点） ----
  function drawRoe(box, spec) {
    var MIN = -15, MAX = 40, GOAL = 8;
    var pct = function (v) { return (v - MIN) / (MAX - MIN) * 100; };
    var align = function (p) { return p > 80 ? 'translateX(-100%)' : p < 14 ? 'translateX(-4px)' : 'translateX(-50%)'; };
    var cls = function (v) { return v < 0 ? 'neg' : v >= GOAL ? 'hi' : 'mid'; };
    var f = function (v) { return (v < 0 ? '−' + Math.abs(v).toFixed(1) : v.toFixed(1)) + '%'; };
    var refs = '<div class="ref" style="left:' + pct(0) + '%"></div><div class="ref rgoal" style="left:' + pct(GOAL) + '%"></div>';
    var h = '<div class="roe-row axis"><div></div><div class="track">' +
      [-10, 0, 10, 20, 30, 40].map(function (t) { return '<span class="tick" style="left:' + pct(t) + '%">' + (t < 0 ? '−' + Math.abs(t) : t) + '%</span>'; }).join('') +
      '<span class="tick tgoal" style="left:' + pct(GOAL) + '%">目安8%</span></div></div>';
    spec.rows.forEach(function (row) {
      var sorted = row[1].slice().sort(function (a, b) { return a[1] - b[1]; });
      var lanes = [0, -9, 9], last = [-99, -99, -99];
      var dots = sorted.map(function (c) {
        var li = lanes.findIndex(function (_, i) { return c[1] - last[i] > 2.4; }); if (li < 0) li = 0;
        last[li] = c[1];
        return '<button type="button" class="dot ' + cls(c[1]) + (pct(c[1]) > 80 ? ' r' : pct(c[1]) < 14 ? ' l' : '') + '" style="left:' + pct(c[1]) + '%;top:calc(50% + ' + lanes[li] + 'px)" aria-label="' + c[0] + ' ROE ' + f(c[1]) + '"><span class="tipbox">' + c[0] + ' ' + f(c[1]) + '</span></button>';
      }).join('');
      var hiC = sorted[sorted.length - 1], loC = sorted[0];
      var lab = function (c, pos) { var p = pct(c[1]); return '<span class="lab ' + pos + (c[1] < 0 ? ' neg' : '') + '" style="left:' + p + '%;transform:' + align(p) + '">' + c[0] + ' ' + f(c[1]) + '</span>'; };
      h += '<div class="roe-row"><div class="roe-name">' + row[0] + '</div><div class="track">' + refs + dots + lab(hiC, 'top') + (sorted.length > 1 ? lab(loC, 'bot') : '') + '</div></div>';
    });
    h += '<div class="roe-legend"><span><i style="background:var(--indigo)"></i>8%以上</span><span><i style="background:var(--muted)"></i>0〜8%</span><span><i style="background:var(--down)"></i>マイナス（赤字）</span><span>名前つきは各業界の最高と最低</span></div>';
    box.innerHTML = h;
    box.addEventListener('click', function (e) {
      var d = e.target.closest('.dot');
      box.querySelectorAll('.dot.on').forEach(function (x) { if (x !== d) x.classList.remove('on'); });
      if (d) d.classList.toggle('on');
    });
  }

  var charts = [].slice.call(document.querySelectorAll('[data-chart]')).map(function (box) {
    return { box: box, spec: JSON.parse(box.getAttribute('data-chart')), w: 0 };
  });
  function drawAll() {
    charts.forEach(function (c) {
      var w = c.box.clientWidth;
      if (w === c.w) return;
      c.w = w;
      try {
        if (c.spec.type === 'line') drawLine(c.box, c.spec);
        else if (c.spec.type === 'step') drawStep(c.box, c.spec);
        else if (c.spec.type === 'roe') { if (!c.box.firstChild) drawRoe(c.box, c.spec); }
      } catch (err) { c.box.textContent = 'グラフを表示できませんでした。下の「数字を表で見る」をご覧ください。'; }
    });
  }
  drawAll();
  var timer;
  window.addEventListener('resize', function () { clearTimeout(timer); timer = setTimeout(drawAll, 150); });

  // ---- 3社比較シート（このブラウザに保存） ----
  var KEY = 'gyokai.sheet';
  var cells = document.querySelectorAll('.sheet .cell');
  if (cells.length) {
    var saved = {};
    try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { saved = {}; }
    cells.forEach(function (c) {
      if (saved[c.dataset.key]) c.textContent = saved[c.dataset.key];
      c.addEventListener('input', function () {
        saved[c.dataset.key] = c.textContent;
        try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) { /* 保存できない環境では何もしない */ }
      });
    });
    var clr = document.getElementById('sheet-clear');
    if (clr) clr.addEventListener('click', function () {
      if (!window.confirm('シートに書いた内容をすべて消しますか？')) return;
      saved = {};
      cells.forEach(function (c) { c.textContent = ''; });
      try { localStorage.removeItem(KEY); } catch (e) { /* 何もしない */ }
    });
  }

  // ---- キャラの印鑑：画面に入ったら押す ----
  var seals = document.querySelectorAll('.seal');
  if ('IntersectionObserver' in window && seals.length) {
    document.documentElement.classList.add('js');
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { rootMargin: '0px 0px -8% 0px' });
    seals.forEach(function (s) { io.observe(s); });
  }

  // ---- お問い合わせの送信後 ----
  var sent = document.getElementById('sent-msg');
  if (sent && /[?&]sent=1/.test(location.search)) sent.hidden = false;

  // ---- 用語の説明カード（点線の言葉を押すと出る） ----
  var glEl = document.getElementById('gl-data');
  if (glEl) {
    var GL = {};
    try { GL = JSON.parse(glEl.textContent); } catch (e) { GL = {}; }
    var pop = document.createElement('div');
    pop.className = 'gl-pop';
    pop.setAttribute('role', 'dialog');
    pop.setAttribute('aria-modal', 'false');
    pop.hidden = true;
    document.body.appendChild(pop);
    var opener = null;

    var row = function (label, text, cls) {
      var d = document.createElement('div');
      d.className = 'gp-row' + (cls ? ' ' + cls : '');
      var l = document.createElement('span'); l.className = 'gp-lbl'; l.textContent = label;
      var p = document.createElement('p'); p.textContent = text;
      d.appendChild(l); d.appendChild(p);
      return d;
    };
    var close = function () {
      if (pop.hidden) return;
      pop.hidden = true;
      if (opener) { opener.setAttribute('aria-expanded', 'false'); opener.focus(); }
      opener = null;
    };
    var place = function (btn) {
      if (window.innerWidth <= 700) { pop.classList.add('sheet'); pop.style.left = ''; pop.style.top = ''; return; }
      pop.classList.remove('sheet');
      var r = btn.getBoundingClientRect();
      var w = pop.offsetWidth, hgt = pop.offsetHeight;
      var left = Math.min(Math.max(12, r.left + r.width / 2 - w / 2), window.innerWidth - w - 12);
      var top = r.bottom + 10;
      if (top + hgt > window.innerHeight - 12 && r.top - hgt - 10 > 12) top = r.top - hgt - 10;
      pop.style.left = left + 'px';
      pop.style.top = Math.max(12, top) + 'px';
    };
    var open = function (btn) {
      var g = GL[btn.getAttribute('data-g')];
      if (!g) return;
      if (opener && opener !== btn) opener.setAttribute('aria-expanded', 'false');
      opener = btn;
      btn.setAttribute('aria-expanded', 'true');
      pop.innerHTML = '';
      var head = document.createElement('div'); head.className = 'gp-head';
      var h = document.createElement('p'); h.className = 'gp-title'; h.id = 'gp-title'; h.tabIndex = -1; h.textContent = g.t;
      if (g.yomi) { var y = document.createElement('small'); y.textContent = g.yomi; h.appendChild(y); }
      var x = document.createElement('button'); x.type = 'button'; x.className = 'gp-x'; x.setAttribute('aria-label', '閉じる'); x.textContent = '×';
      x.addEventListener('click', close);
      head.appendChild(h); head.appendChild(x);
      pop.appendChild(head);
      pop.setAttribute('aria-labelledby', 'gp-title');
      pop.appendChild(row('ひとことで', g.short, 'gp-main'));
      if (g.iikae) pop.appendChild(row('友達に説明するなら', g.iikae));
      if (g.tatoe) pop.appendChild(row('たとえると', g.tatoe));
      if (g.kankaku) pop.appendChild(row('数字の感覚', g.kankaku, 'gp-num'));
      if (g.up || g.down) {
        var two = document.createElement('div'); two.className = 'gp-two';
        if (g.up) two.appendChild(row(g.up[0], g.up[1], 'gp-up'));
        if (g.down) two.appendChild(row(g.down[0], g.down[1], 'gp-down'));
        pop.appendChild(two);
      }
      var foot = document.createElement('div'); foot.className = 'gp-foot';
      if (g.link) { var a1 = document.createElement('a'); a1.href = g.link[1]; a1.textContent = g.link[0]; foot.appendChild(a1); }
      var a2 = document.createElement('a'); a2.href = 'yougo.html#g-' + g.k; a2.textContent = '用語集で見る'; foot.appendChild(a2);
      pop.appendChild(foot);
      pop.hidden = false;
      place(btn);
      h.focus({ preventScroll: true });
    };
    document.addEventListener('click', function (e) {
      var b = e.target.closest('.gw');
      if (b) { e.preventDefault(); if (opener === b && !pop.hidden) close(); else open(b); return; }
      if (!pop.hidden && !pop.contains(e.target)) close();
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
    window.addEventListener('resize', function () { if (opener && !pop.hidden) place(opener); });
    window.addEventListener('scroll', function () { if (opener && !pop.hidden && !pop.classList.contains('sheet')) close(); }, { passive: true });
  }

  // ---- 用語集ページの絞り込み ----
  var gfind = document.getElementById('gfind');
  if (gfind) {
    var cards = document.querySelectorAll('.gcard');
    var none = document.getElementById('gfind-none');
    gfind.addEventListener('input', function () {
      var q = gfind.value.trim().toLowerCase();
      var hit = 0;
      cards.forEach(function (c) {
        var ok = !q || c.getAttribute('data-words').toLowerCase().indexOf(q) !== -1 || c.textContent.toLowerCase().indexOf(q) !== -1;
        c.hidden = !ok; if (ok) hit++;
      });
      document.querySelectorAll('.gcards').forEach(function (g) {
        var sec = g.closest('.sec');
        if (sec) sec.hidden = !Array.prototype.some.call(g.children, function (c) { return !c.hidden; });
      });
      if (none) none.hidden = hit > 0;
    });
  }
})();
