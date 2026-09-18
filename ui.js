// Helpers compartilhados pelas três páginas. Carregar depois do *-data.js e
// antes do script inline da página.
(function () {
  'use strict';

  // ── sprite do TibiaWiki ───────────────────────────────────────────────
  // Vai direto ao CDN (static.wikia.nocookie.net) em vez de passar pelo
  // Special:FilePath: o domínio tibia.fandom.com está atrás do Cloudflare e
  // responde o desafio "Just a moment..." (403) a requisição de <img>, então
  // TODA sprite falhava e só sobrava o "·" do .noimg. O CDN serve a imagem
  // sem desafio nenhum (e ainda economiza o redirect por sprite).
  //
  // O caminho é o do MediaWiki: images/<h0>/<h0h1>/<Arquivo>, com h = md5 do
  // nome do arquivo (espaço → underscore). O sufixo /revision/latest é
  // obrigatório no Fandom; ?path-prefix=en escolhe o wiki inglês.
  // `md5` abaixo existe só para montar esse caminho — nada de segurança.
  function md5(str) {
    const b = [];
    for (let i = 0; i < str.length; i++) {
      let c = str.charCodeAt(i);
      if (c < 0x80) b.push(c);
      else if (c < 0x800) b.push(0xc0 | (c >> 6), 0x80 | (c & 63));
      else if (c < 0xd800 || c >= 0xe000)
        b.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
      else {
        c = 0x10000 + (((c & 0x3ff) << 10) | (str.charCodeAt(++i) & 0x3ff));
        b.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63),
               0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
      }
    }
    const bits = b.length * 8;
    b.push(0x80);
    while (b.length % 64 !== 56) b.push(0);
    const x = [];
    for (let i = 0; i < b.length; i += 4)
      x.push(b[i] | (b[i + 1] << 8) | (b[i + 2] << 16) | (b[i + 3] << 24));
    x.push(bits & 0xffffffff, Math.floor(bits / 4294967296));

    const add = (a, c) => {
      const l = (a & 0xffff) + (c & 0xffff);
      return ((((a >> 16) + (c >> 16) + (l >> 16)) << 16) | (l & 0xffff)) >>> 0;
    };
    const rol = (n, c) => (n << c) | (n >>> (32 - c));
    const cmn = (q, a, c, v, s, t) => add(rol(add(add(a, q), add(v, t)), s), c);
    const ff = (a, c, d, e, v, s, t) => cmn((c & d) | (~c & e), a, c, v, s, t);
    const gg = (a, c, d, e, v, s, t) => cmn((c & e) | (d & ~e), a, c, v, s, t);
    const hh = (a, c, d, e, v, s, t) => cmn(c ^ d ^ e, a, c, v, s, t);
    const ii = (a, c, d, e, v, s, t) => cmn(d ^ (c | ~e), a, c, v, s, t);

    let a = 1732584193, d = -271733879, c = -1732584194, e = 271733878;
    for (let i = 0; i < x.length; i += 16) {
      const oa = a, od = d, oc = c, oe = e;
      a=ff(a,d,c,e,x[i],7,-680876936);    e=ff(e,a,d,c,x[i+1],12,-389564586);
      c=ff(c,e,a,d,x[i+2],17,606105819);  d=ff(d,c,e,a,x[i+3],22,-1044525330);
      a=ff(a,d,c,e,x[i+4],7,-176418897);  e=ff(e,a,d,c,x[i+5],12,1200080426);
      c=ff(c,e,a,d,x[i+6],17,-1473231341);d=ff(d,c,e,a,x[i+7],22,-45705983);
      a=ff(a,d,c,e,x[i+8],7,1770035416);  e=ff(e,a,d,c,x[i+9],12,-1958414417);
      c=ff(c,e,a,d,x[i+10],17,-42063);    d=ff(d,c,e,a,x[i+11],22,-1990404162);
      a=ff(a,d,c,e,x[i+12],7,1804603682); e=ff(e,a,d,c,x[i+13],12,-40341101);
      c=ff(c,e,a,d,x[i+14],17,-1502002290);d=ff(d,c,e,a,x[i+15],22,1236535329);

      a=gg(a,d,c,e,x[i+1],5,-165796510);  e=gg(e,a,d,c,x[i+6],9,-1069501632);
      c=gg(c,e,a,d,x[i+11],14,643717713); d=gg(d,c,e,a,x[i],20,-373897302);
      a=gg(a,d,c,e,x[i+5],5,-701558691);  e=gg(e,a,d,c,x[i+10],9,38016083);
      c=gg(c,e,a,d,x[i+15],14,-660478335);d=gg(d,c,e,a,x[i+4],20,-405537848);
      a=gg(a,d,c,e,x[i+9],5,568446438);   e=gg(e,a,d,c,x[i+14],9,-1019803690);
      c=gg(c,e,a,d,x[i+3],14,-187363961); d=gg(d,c,e,a,x[i+8],20,1163531501);
      a=gg(a,d,c,e,x[i+13],5,-1444681467);e=gg(e,a,d,c,x[i+2],9,-51403784);
      c=gg(c,e,a,d,x[i+7],14,1735328473); d=gg(d,c,e,a,x[i+12],20,-1926607734);

      a=hh(a,d,c,e,x[i+5],4,-378558);     e=hh(e,a,d,c,x[i+8],11,-2022574463);
      c=hh(c,e,a,d,x[i+11],16,1839030562);d=hh(d,c,e,a,x[i+14],23,-35309556);
      a=hh(a,d,c,e,x[i+1],4,-1530992060); e=hh(e,a,d,c,x[i+4],11,1272893353);
      c=hh(c,e,a,d,x[i+7],16,-155497632); d=hh(d,c,e,a,x[i+10],23,-1094730640);
      a=hh(a,d,c,e,x[i+13],4,681279174);  e=hh(e,a,d,c,x[i],11,-358537222);
      c=hh(c,e,a,d,x[i+3],16,-722521979); d=hh(d,c,e,a,x[i+6],23,76029189);
      a=hh(a,d,c,e,x[i+9],4,-640364487);  e=hh(e,a,d,c,x[i+12],11,-421815835);
      c=hh(c,e,a,d,x[i+15],16,530742520); d=hh(d,c,e,a,x[i+2],23,-995338651);

      a=ii(a,d,c,e,x[i],6,-198630844);    e=ii(e,a,d,c,x[i+7],10,1126891415);
      c=ii(c,e,a,d,x[i+14],15,-1416354905);d=ii(d,c,e,a,x[i+5],21,-57434055);
      a=ii(a,d,c,e,x[i+12],6,1700485571); e=ii(e,a,d,c,x[i+3],10,-1894986606);
      c=ii(c,e,a,d,x[i+10],15,-1051523);  d=ii(d,c,e,a,x[i+1],21,-2054922799);
      a=ii(a,d,c,e,x[i+8],6,1873313359);  e=ii(e,a,d,c,x[i+15],10,-30611744);
      c=ii(c,e,a,d,x[i+6],15,-1560198380);d=ii(d,c,e,a,x[i+13],21,1309151649);
      a=ii(a,d,c,e,x[i+4],6,-145523070);  e=ii(e,a,d,c,x[i+11],10,-1120210379);
      c=ii(c,e,a,d,x[i+2],15,718787259);  d=ii(d,c,e,a,x[i+9],21,-343485551);

      a = add(a, oa); d = add(d, od); c = add(c, oc); e = add(e, oe);
    }
    let out = '';
    [a, d, c, e].forEach((w) => {
      for (let i = 0; i < 4; i++)
        out += ((w >> (i * 8 + 4)) & 15).toString(16) + ((w >> (i * 8)) & 15).toString(16);
    });
    return out;
  }

  // Se o arquivo não existir (nomes fora do padrão + páginas de lista do
  // wiki, ~4% dos itens), o onerror esconde a imagem e a caixa mantém o
  // lugar — nada quebra offline.
  const IMG = (name) => {
    const file = String(name).trim().replace(/ /g, '_') + '.gif';
    const h = md5(file);
    return 'https://static.wikia.nocookie.net/tibia/images/' +
      h[0] + '/' + h.slice(0, 2) + '/' + encodeURIComponent(file) +
      '/revision/latest?path-prefix=en';
  };

  // referrerpolicy="no-referrer" é obrigatório: o CDN do Fandom tem proteção
  // contra hotlink e, quando vê Referer de outro site, responde 404 com um
  // JPEG "imagem indisponível" de 300×171 — que o navegador desenha como se
  // fosse a sprite (o onerror nem dispara). Sem Referer ele serve o arquivo
  // de verdade. De quebra, não vaza a URL do site.
  // O mesmo JPEG de 300×171 volta (com 404) quando o arquivo não existe no
  // wiki — ~4% dos itens, que são páginas de lista ("Alicorn Set") sem sprite
  // nenhuma. Como o navegador desenha esse 404, o onerror não serve: quem
  // manda a imagem para o .noimg é a medida no onload. Sprite de Tibia é
  // múltipla de 32; 300×171 só existe no placeholder.
  window.spr = (name, big) =>
    `<span class="spr${big ? ' spr-big' : ''}"><img loading="lazy" alt="" ` +
    `referrerpolicy="no-referrer" src="${IMG(name)}" ` +
    `onload="if(this.naturalWidth===300&&this.naturalHeight===171)` +
    `this.parentElement.classList.add('noimg')" ` +
    `onerror="this.parentElement.classList.add('noimg')"></span>`;

  // ── busca com OR ──────────────────────────────────────────────────────
  // "werelion|cobra" acha qualquer um dos termos (é o que os presets usam)
  window.matchQuery = (hay, q) =>
    q.split('|').map((t) => t.trim()).filter(Boolean).some((t) => hay.includes(t));

  // ── estado dos filtros ────────────────────────────────────────────────
  // Persistidos por página no localStorage: fechar e reabrir o site volta
  // exatamente na consulta em que se estava. Parâmetros de URL (?q=, ?open=)
  // têm prioridade — são os deep-links entre as páginas.
  window.urlParam = (k) => new URLSearchParams(location.search).get(k);

  window.filterState = function (ids, pageKey) {
    const KEY = 'tibia-ai:' + pageKey;
    const el = (id) => document.getElementById(id);

    const save = () => {
      const out = {};
      ids.forEach((id) => {
        const e = el(id);
        if (e) out[id] = e.type === 'checkbox' ? e.checked : e.value;
      });
      try { localStorage.setItem(KEY, JSON.stringify(out)); } catch (_) {}
    };

    const restore = () => {
      try {
        const saved = JSON.parse(localStorage.getItem(KEY) || '{}');
        ids.forEach((id) => {
          const e = el(id);
          if (!e || !(id in saved)) return;
          if (e.type === 'checkbox') e.checked = !!saved[id];
          else e.value = saved[id];
        });
      } catch (_) {}
    };

    const clear = () => {
      ids.forEach((id) => {
        const e = el(id);
        if (!e) return;
        if (e.type === 'checkbox') e.checked = false;
        else e.value = '';
      });
      try { localStorage.removeItem(KEY); } catch (_) {}
    };

    // preset = objeto {idDoFiltro: valor}; limpa tudo antes para o chip ser
    // sempre a mesma consulta, independente do que estava selecionado
    const apply = (preset) => {
      clear();
      Object.entries(preset).forEach(([id, v]) => {
        const e = el(id);
        if (!e) return;
        if (e.type === 'checkbox') e.checked = !!v;
        else e.value = v;
      });
      save();
    };

    ids.forEach((id) => el(id) && el(id).addEventListener('input', save));
    return { save, restore, clear, apply };
  };

  // ── atalhos de teclado ────────────────────────────────────────────────
  // "/" foca a busca em qualquer página (Esc já fecha o painel nas páginas)
  document.addEventListener('keydown', (e) => {
    if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
    const a = document.activeElement;
    if (a && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName)) return;
    const q = document.getElementById('q');
    if (q) { e.preventDefault(); q.focus(); q.select(); }
  });

  // ══════════════════════════════════════════════════════════════════════
  // CAMADA MOBILE (iPhone 15 Pro Max = 430×932 em retrato)
  //
  // Tudo daqui pra baixo é progressive enhancement: monta os controles que
  // o CSS de celular espera e não toca em nada que as páginas usem por id.
  // Nenhuma página precisou mudar o próprio script.
  // ══════════════════════════════════════════════════════════════════════
  const PHONE = window.matchMedia('(max-width: 640px)');
  const onPhone = () => PHONE.matches;
  const on = (mq, fn) => (mq.addEventListener ? mq.addEventListener('change', fn)
                                              : mq.addListener(fn));

  // ── campos de busca: o iOS capitaliza e corrige nome de item ──────────
  // "falcon bow" virava "Falcon Bow" com sugestão de correção; e Enter tem
  // que fechar o teclado, senão ele cobre metade do resultado.
  function tuneSearch() {
    document.querySelectorAll('input[type="search"], input[list]').forEach((el) => {
      el.setAttribute('autocapitalize', 'none');
      el.setAttribute('autocorrect', 'off');
      el.setAttribute('spellcheck', 'false');
      el.setAttribute('enterkeyhint', 'search');
      el.addEventListener('keydown', (e) => { if (e.key === 'Enter') el.blur(); });
    });
  }

  // ── nav: deixa a página atual visível na trilha rolável ───────────────
  // e publica a altura real da barra em --navh: a barra de filtros gruda
  // logo abaixo dela, e com o notch do iPhone essa altura muda.
  function tuneNav() {
    const bar = document.querySelector('.wrap > .topbar');
    const cur = document.querySelector('.topbar nav a.on');
    if (cur && cur.parentElement.scrollWidth > cur.parentElement.clientWidth) {
      cur.parentElement.scrollLeft = cur.offsetLeft - 12;
    }
    if (!bar) return;
    const measure = () => {
      if (!onPhone()) return;
      const h = Math.round(bar.getBoundingClientRect().height);
      if (h) document.documentElement.style.setProperty('--navh', h + 'px');
    };
    measure();
    window.addEventListener('resize', measure);
    window.addEventListener('orientationchange', () => setTimeout(measure, 150));
  }

  // ── filtros: no celular, tudo menos a busca entra num painel dobrável ─
  // No desktop o painel é `display: contents` — os filhos continuam sendo
  // filhos diretos do flex de .controls e o layout fica idêntico ao antigo.
  function tuneFilters() {
    const c = document.querySelector('.controls');
    if (!c) return;
    const count = c.querySelector('.count');
    // busca, seletor de mundo (market) e contagem ficam sempre à vista
    const keep = (el) =>
      el.id === 'q' || el.classList.contains('count') || el.classList.contains('wctl');
    const movable = [...c.children].filter((el) => !keep(el));
    if (!movable.length) return;

    const body = document.createElement('div');
    body.className = 'filters-body';
    movable.forEach((el) => body.appendChild(el));

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'filters-toggle';
    btn.setAttribute('aria-expanded', 'false');
    btn.innerHTML = '⚙ Filtros <span class="fbadge" hidden></span>';

    c.insertBefore(btn, count || null);
    c.insertBefore(body, count || null);

    const setOpen = (v) => {
      body.hidden = !v;
      btn.classList.toggle('on', v);
      btn.setAttribute('aria-expanded', String(v));
    };
    setOpen(!onPhone());
    btn.onclick = () => setOpen(body.hidden);
    on(PHONE, () => setOpen(!onPhone()));

    // contador de filtros ativos: fechado, o painel não pode esconder que
    // existe um filtro ligado (era o jeito mais fácil de "sumir" com dado)
    const badge = btn.querySelector('.fbadge');
    const refresh = () => {
      const n = [...body.querySelectorAll('input, select')]
        .filter((e) => (e.type === 'checkbox' ? e.checked : String(e.value || '') !== ''))
        .length;
      badge.textContent = n;
      badge.hidden = !n;
    };
    ['input', 'change'].forEach((ev) => c.addEventListener(ev, refresh));
    setTimeout(refresh, 0);   // a página restaura o estado depois deste script
    window.addEventListener('tibia:rendered', refresh);
  }

  // ── tabelas viram cartões: rótulo de cada célula sai do <thead> ───────
  function tuneTables() {
    document.querySelectorAll('.scroll > table').forEach((tbl) => {
      const apply = () => { labelCells(tbl); syncSort(tbl); };
      new MutationObserver(() => {
        apply();
        window.dispatchEvent(new CustomEvent('tibia:rendered'));
      }).observe(tbl, { childList: true });
      apply();
    });
  }

  function labelCells(tbl) {
    const heads = [...tbl.querySelectorAll('thead th')].map((th) => th.textContent.trim());
    if (!heads.length) return;
    tbl.querySelectorAll('tbody tr').forEach((tr) => {
      // o título do cartão é o nome; em guia.html a 1ª célula é a caixa de
      // marcar, por isso .name tem prioridade sobre a primeira coluna
      const title = tr.querySelector('td.name') || tr.cells[0];
      [...tr.cells].forEach((td, i) => {
        if (td === title) { td.setAttribute('data-t', ''); return; }
        if (td.querySelector('input, select, button')) { td.classList.add('has-ctl'); return; }
        const txt = td.textContent.trim();
        if (!txt || txt === '—' || txt === '-') td.classList.add('is-empty');
        else if (heads[i]) td.setAttribute('data-l', heads[i]);
      });
      if (tr.onclick) tr.classList.add('tappable');
    });
  }

  // Sem <thead> visível não há onde clicar para ordenar: a barra reproduz
  // os mesmos <th data-k> em um <select>, e o clique real continua sendo no
  // <th> — assim cada página mantém a própria regra de sentido padrão.
  function syncSort(tbl) {
    const ths = [...tbl.querySelectorAll('thead th[data-k]')];
    let bar = tbl.msortBar;
    if (!ths.length) { if (bar) bar.hidden = true; return; }

    if (!bar) {
      const box = tbl.closest('.scroll');
      if (!box || !box.parentNode) return;
      bar = document.createElement('div');
      bar.className = 'msort';
      bar.innerHTML = '<label for="msort-' + (tbl.id || 'tbl') + '">Ordenar</label>' +
        '<select id="msort-' + (tbl.id || 'tbl') + '"></select>' +
        '<button type="button" title="Inverter a ordem">⇅</button>';
      box.parentNode.insertBefore(bar, box);
      tbl.msortBar = bar;

      const sel = bar.querySelector('select');
      // o <th> é re-criado a cada render: procurar na hora do clique
      sel.onchange = () => {
        const th = tbl.querySelector('thead th[data-k="' + sel.value + '"]');
        if (th) th.click();
      };
      bar.querySelector('button').onclick = () => {
        const th = tbl.querySelector('thead th.sorted') ||
                   tbl.querySelector('thead th[data-k]');
        if (th) th.click();
      };
    }

    bar.hidden = false;
    const sel = bar.querySelector('select');
    const opts = ths.map((th) =>
      `<option value="${th.dataset.k}">${th.textContent.trim()}</option>`).join('');
    if (sel.innerHTML !== opts) sel.innerHTML = opts;
    const cur = tbl.querySelector('thead th.sorted');
    if (cur) sel.value = cur.dataset.k;
  }

  // ── folha de detalhe: o gesto de voltar do iOS fecha o painel ─────────
  function tuneSheet() {
    const ov = document.getElementById('overlay');
    if (!ov) return;
    let pushed = false;

    new MutationObserver(() => {
      const open = ov.classList.contains('open');
      if (open && !pushed && onPhone()) {
        pushed = true;
        history.pushState({ tibiaSheet: 1 }, '');
      } else if (!open && pushed) {
        pushed = false;
        if (history.state && history.state.tibiaSheet) history.back();
      }
    }).observe(ov, { attributes: true, attributeFilter: ['class'] });

    window.addEventListener('popstate', () => {
      if (!ov.classList.contains('open')) return;
      pushed = false;
      if (typeof window.closeDetail === 'function') window.closeDetail();
      else ov.classList.remove('open');
    });
  }

  // ── voltar ao topo (a lista de cartões é longa) ───────────────────────
  function tuneFab() {
    const fab = document.createElement('button');
    fab.type = 'button';
    fab.className = 'fab-top';
    fab.setAttribute('aria-label', 'Voltar ao topo');
    fab.textContent = '↑';
    fab.onclick = () => window.scrollTo({ top: 0, behavior: 'smooth' });
    document.body.appendChild(fab);
    const upd = () => fab.classList.toggle('on', window.scrollY > 600);
    window.addEventListener('scroll', upd, { passive: true });
    upd();
  }

  tuneSearch();
  tuneNav();
  tuneFilters();
  tuneTables();
  tuneSheet();
  tuneFab();
})();
