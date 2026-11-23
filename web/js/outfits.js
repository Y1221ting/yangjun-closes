/* 搭配库：真实封面预览、场景筛选、搜索、新建与删除。 */
(function (App) {
  'use strict';

  const BASE_WIDTH = {
    outer: 42,
    top: 38,
    dress: 42,
    bottom: 34,
    shoes: 20,
    bag: 16,
    accessory: 12,
  };

  const state = {
    items: [],
    meta: null,
    scene: '',
    keyword: '',
  };

  const els = {};

  function cache() {
    els.grid = document.getElementById('outfit-grid');
    els.empty = document.getElementById('outfit-empty');
    els.filterEmpty = document.getElementById('outfit-filter-empty');
    els.count = document.getElementById('outfit-count');
    els.sceneFilters = document.getElementById('outfit-scene-filters');
    els.search = document.getElementById('outfit-search');
    els.clear = document.getElementById('btn-outfit-clear');
  }

  function hasFilters() {
    return Boolean(state.scene || state.keyword);
  }

  function sceneText(outfit) {
    return outfit.scenes && outfit.scenes.length ? outfit.scenes.join(' / ') : '未分类';
  }

  // ---------------------------------------------------------------- 筛选

  function renderSceneFilters() {
    const options = [{ value: '', label: '全部' }].concat(
      (state.meta.scenes || []).map((name) => ({ value: name, label: name }))
    );

    els.sceneFilters.innerHTML = '';
    options.forEach((opt) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chip' + (state.scene === opt.value ? ' is-active' : '');
      btn.textContent = opt.label;
      btn.addEventListener('click', () => {
        state.scene = opt.value;
        renderSceneFilters();
        updateClear();
        load();
      });
      els.sceneFilters.appendChild(btn);
    });
  }

  function updateClear() {
    els.clear.hidden = !hasFilters();
  }

  function clearFilters() {
    state.scene = '';
    state.keyword = '';
    els.search.value = '';
    renderSceneFilters();
    updateClear();
    load();
  }

  // ---------------------------------------------------------------- 封面

  function miniPreview(outfit) {
    if (!outfit.items || !outfit.items.length) {
      return '<span class="card__placeholder">空搭配</span>';
    }

    const items = outfit.items
      .slice()
      .sort((a, b) => a.z_index - b.z_index)
      .map((item) => {
        const width = ((BASE_WIDTH[item.category] || 30) * item.scale).toFixed(2);
        const clipTop = typeof item.clip_top === 'number' ? item.clip_top : 0;
        const clipBottom =
          typeof item.clip_bottom === 'number' ? item.clip_bottom : 1;
        const clip = `inset(${(clipTop * 100).toFixed(2)}% 0 ${((1 - clipBottom) * 100).toFixed(2)}% 0)`;
        return (
          `<img class="outfit-mini__item" src="/data/${App.ui.escapeHtml(item.image)}" alt="" ` +
          `style="left:${(item.x * 100).toFixed(2)}%;top:${(item.y * 100).toFixed(2)}%;` +
          `width:${width}%;z-index:${item.z_index};` +
          `clip-path:${clip};` +
          `transform:translate(-50%,-50%) rotate(${item.rotation}deg)">`
        );
      })
      .join('');

    return `<div class="outfit-mini">${items}</div>`;
  }

  // ---------------------------------------------------------------- 渲染

  function card(outfit) {
    const el = document.createElement('article');
    el.className = 'card outfit-card';
    el.dataset.id = outfit.id;

    const suffix = outfit.updated_at
      ? `?v=${encodeURIComponent(outfit.updated_at)}`
      : '';
    const cover = outfit.worn_cover
      ? `<img class="outfit-worn-cover" src="/data/${App.ui.escapeHtml(outfit.worn_cover)}${suffix}" alt="${App.ui.escapeHtml(outfit.name)}" loading="lazy">`
      : miniPreview(outfit);

    el.innerHTML = `
      <button class="card__delete" type="button" title="删除">✕</button>
      <div class="card__media outfit-card__cover">
        ${cover}
        ${outfit.worn_cover ? '<span class="outfit-badge">上身</span>' : ''}
      </div>
      <div class="card__body">
        <p class="card__name">${App.ui.escapeHtml(outfit.name)}</p>
        <p class="card__meta">${outfit.item_count} 件 · ${App.ui.escapeHtml(sceneText(outfit))}</p>
      </div>
    `;

    el.addEventListener('click', () => App.nav.toOutfit(outfit.id));
    el.querySelector('.card__delete').addEventListener('click', (event) => {
      handleDelete(event, outfit);
    });
    return el;
  }

  function render() {
    const items = state.items;
    const filtered = hasFilters();

    els.grid.innerHTML = '';
    els.grid.hidden = items.length === 0;

    if (items.length) {
      els.count.textContent = filtered
        ? `筛选出 ${items.length} 套`
        : `${items.length} 套搭配`;
    } else {
      els.count.textContent = filtered ? '没有符合条件的搭配' : '还没有搭配';
    }

    els.empty.hidden = items.length > 0 || filtered;
    els.filterEmpty.hidden = items.length > 0 || !filtered;

    items.forEach((outfit, index) => {
      const el = card(outfit);
      el.style.animationDelay = `${Math.min(index, 12) * 24}ms`;
      els.grid.appendChild(el);
    });
  }

  async function handleDelete(event, outfit) {
    event.stopPropagation();

    const confirmed = await App.ui.confirm({
      title: `删除搭配「${outfit.name}」？`,
      message: '这套搭配会移入回收站，布局和上身图都会保留，可以随时恢复。',
      confirmText: '移入回收站',
    });
    if (!confirmed) return;

    try {
      await App.api.del(`/api/outfits/${outfit.id}`);
      App.ui.toast('已删除搭配');
      load();
    } catch (err) {
      App.ui.toast(err.message, 'error');
    }
  }

  // ---------------------------------------------------------------- 数据

  async function load() {
    try {
      const params = new URLSearchParams();
      if (state.scene) params.set('scene', state.scene);
      if (state.keyword) params.set('q', state.keyword);
      const query = params.toString();
      state.items = await App.api.get('/api/outfits' + (query ? `?${query}` : ''));
      render();
    } catch (err) {
      App.ui.toast(err.message, 'error');
    }
  }

  async function create() {
    try {
      const outfit = await App.api.post('/api/outfits', {
        name: '未命名搭配',
        scenes: [],
      });
      App.nav.toOutfit(outfit.id);
    } catch (err) {
      App.ui.toast(err.message, 'error');
    }
  }

  // ---------------------------------------------------------------- 初始化

  function init(meta) {
    state.meta = meta;
    cache();

    renderSceneFilters();
    updateClear();

    let timer = 0;
    els.search.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        state.keyword = els.search.value.trim();
        updateClear();
        load();
      }, 220);
    });

    els.clear.addEventListener('click', clearFilters);
    document.getElementById('btn-outfit-clear-empty').addEventListener('click', clearFilters);
    document.getElementById('btn-new-outfit').addEventListener('click', create);
    document.getElementById('btn-new-outfit-empty').addEventListener('click', create);

    load();
  }

  App.outfits = { init, load };
})(window.App = window.App || {});
