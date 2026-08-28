// Helpers compartilhados pelas três páginas. Carregar depois do *-data.js e
// antes do script inline da página.
(function () {
  'use strict';

  // GIF oficial do TibiaWiki: Special:FilePath resolve File:<Nome>.gif sem
  // precisar conhecer o hash do CDN. Se o arquivo não existir (nomes de
  // imagem fora do padrão, ~5% dos casos), o onerror esconde a imagem e a
  // caixa mantém o lugar — nada quebra offline.
  const IMG = (name) =>
    'https://tibia.fandom.com/wiki/Special:FilePath/' +
    encodeURIComponent(String(name).trim().replace(/ /g, '_')) + '.gif';

  window.spr = (name, big) =>
    `<span class="spr${big ? ' spr-big' : ''}"><img loading="lazy" alt="" ` +
    `src="${IMG(name)}" onerror="this.parentElement.classList.add('noimg')"></span>`;

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
