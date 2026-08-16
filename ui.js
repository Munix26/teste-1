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
})();
