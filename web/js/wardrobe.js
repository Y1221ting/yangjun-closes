/* 衣柜页：分类挂杆、悬停展开正面、筛选与搜索。 */
(function (App) {
  'use strict';

  const CLOTH_CATEGORIES = ['top', 'outer', 'bottom', 'dress'];
  const ACCESSORY_CATEGORY = 'accessory';
  const ACCESSORY_STYLES = ['hang', 'bag', 'flat', 'drawer'];

  const state = {
    meta: null,
    items: [],
    counts: null,
    category: '',
    color: '',
    season: '',
    scene: '',
    keyword: '',
    loading: false,
  };

  const els = {};
  let drag = null;
  let cabinetDrag = null;

  function cache() {
    els.rack = document.getElementById('wardrobe-rack');
    els.empty = document.getElementById('empty-state');
    els.filterEmpty = document.getElementById('filter-empty');
    els.count = document.getElementById('wardrobe-count');
    els.categories = document.getElementById('category-filters');
    els.color = document.getElementById('filter-color');
    els.season = document.getElementById('filter-season');
    els.scene = document.getElementById('filter-scene');
    els.clear = document.getElementById('btn-clear-filters');
    els.search = document.getElementById('search-input');
    els.filterToggle = document.getElementById('btn-filter-toggle');
    els.filterPop = document.getElementById('filter-pop');
    els.filterDone = document.getElementById('btn-filter-done');
    els.filterCount = document.getElementById('filter-count');
  }

  function labelsOf(key) {
    const map = {};
    (state.meta[key] || []).forEach((opt) => {
      map[opt.value] = opt.label;
    });
    return map;
  }

  function hasFilters() {
    return Boolean(
      state.category || state.color || state.season || state.scene || state.keyword
    );
  }

  // ---------------------------------------------------------------- 筛选栏

  function categoryCount(opt) {
    if (!state.counts) return '';
    if (!opt.value) return state.counts.total;
    return (state.counts.categories || {})[opt.value] || 0;
  }

  function renderCategoryChips() {
    const options = [{ value: '', label: '全部' }].concat(state.meta.categories);
    els.categories.innerHTML = '';

    options.forEach((opt) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'catalog-item' + (state.category === opt.value ? ' is-active' : '');
      btn.innerHTML = `
        <img class="catalog-item__leaf" src="/assets/decor/leaf-small.webp" alt="">
        <span class="catalog-item__name">${escape(opt.label)}</span>
        <span class="catalog-item__count">${categoryCount(opt)}</span>
      `;
      btn.addEventListener('click', () => {
        state.category = opt.value;
        renderCategoryChips();
        updateClearButton();
        load();
      });
      els.categories.appendChild(btn);
    });
  }

  async function loadCounts() {
    try {
      state.counts = await App.api.get('/api/garments/counts');
      renderCategoryChips();
    } catch (err) {
      // 角标失败不影响衣柜使用
      console.warn('读取分类数量失败', err);
    }
  }

  function fillSelect(select, options, placeholder) {
    const current = select.value;
    select.innerHTML = '';

    const empty = document.createElement('option');
    empty.value = '';
    empty.textContent = placeholder;
    select.appendChild(empty);

    options.forEach((opt) => {
      const option = document.createElement('option');
      option.value = opt.value;
      option.textContent = opt.label;
      select.appendChild(option);
    });

    if (current) select.value = current;
  }

  function activeFilterCount() {
    return [state.color, state.season, state.scene].filter(Boolean).length;
  }

  function updateClearButton() {
    const active = hasFilters();
    els.clear.hidden = !active;
    const count = activeFilterCount();
    els.filterCount.hidden = count === 0;
    els.filterCount.textContent = count ? String(count) : '';
    els.filterToggle.classList.toggle('is-active', active);
  }

  function toggleFilters(force) {
    const show = force === undefined ? els.filterPop.hidden : force;
    els.filterPop.hidden = !show;
    els.filterToggle.setAttribute('aria-expanded', show ? 'true' : 'false');
  }

  function clearFilters() {
    state.category = '';
    state.color = '';
    state.season = '';
    state.scene = '';
    state.keyword = '';
    els.color.value = '';
    els.season.value = '';
    els.scene.value = '';
    els.search.value = '';
    renderCategoryChips();
    updateClearButton();
    load();
  }

  // ---------------------------------------------------------------- 挂件

  function imageVersion(item) {
    return item.updated_at ? `?v=${encodeURIComponent(item.updated_at)}` : '';
  }

  function escape(value) {
    return App.ui.escapeHtml(value);
  }

  function openGarment(item) {
    App.nav.toGarment(item.id);
  }

  // ---------------------------------------------------------------- 拖动排序

  function beginDrag(event, el) {
    drag = {
      el,
      rail: el.parentElement,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
    };
    try {
      el.setPointerCapture(event.pointerId);
    } catch (ignore) {
      /* 指针捕获失败时仍可拖动 */
    }
  }

  function onDragMove(event) {
    if (!drag || event.pointerId !== drag.pointerId) return;

    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (!drag.moved) {
      if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
      drag.moved = true;
      drag.el.classList.add('is-dragging');
      document.body.classList.add('is-racking');
    }

    // 拖动靠近左右边缘时自动滚动
    const scroll = drag.rail.closest('.rack-scroll');
    if (scroll) {
      const scrollRect = scroll.getBoundingClientRect();
      const edge = 60;
      if (event.clientX < scrollRect.left + edge) {
        scroll.scrollLeft -= 16;
      } else if (event.clientX > scrollRect.right - edge) {
        scroll.scrollLeft += 16;
      }
    }

    const items = Array.from(drag.rail.querySelectorAll('.rack-item'));
    if (!items.length) return;

    const firstRect = items[0].getBoundingClientRect();
    const lastRect = items[items.length - 1].getBoundingClientRect();

    if (event.clientX < firstRect.left) {
      drag.rail.insertBefore(drag.el, items[0]);
      return;
    }
    if (event.clientX > lastRect.right) {
      drag.rail.appendChild(drag.el);
      return;
    }

    const target = items.find((node) => {
      const rect = node.getBoundingClientRect();
      return event.clientX >= rect.left && event.clientX <= rect.right;
    });
    if (!target || target === drag.el) return;

    const rect = target.getBoundingClientRect();
    const before = event.clientX < rect.left + rect.width / 2;
    drag.rail.insertBefore(drag.el, before ? target : target.nextSibling);
  }

  async function onDragUp(event) {
    if (!drag || event.pointerId !== drag.pointerId) return;

    const { el, rail, moved, pointerId } = drag;
    drag = null;
    try {
      el.releasePointerCapture(pointerId);
    } catch (ignore) {
      /* 已经释放时忽略 */
    }
    el.classList.remove('is-dragging');
    document.body.classList.remove('is-racking');

    if (!moved) return;
    el._dragEndedAt = Date.now();

    const ids = Array.from(rail.querySelectorAll('.rack-item')).map((node) =>
      Number(node.dataset.id)
    );
    try {
      await App.api.put('/api/garments/order', { ids });
      App.ui.toast('顺序已保存');
    } catch (err) {
      App.ui.toast(err.message, 'error');
      load();
    }
  }

  function rackItem(item, index) {
    const el = document.createElement('div');
    el.className = 'rack-item';
    el.dataset.id = item.id;
    el.style.animationDelay = `${Math.min(index, 10) * 30}ms`;
    el.tabIndex = 0;
    el.setAttribute('role', 'button');
    el.setAttribute('aria-label', item.name);

    const suffix = imageVersion(item);
    const images = item.images || {};
    const sidePath = images.side
      ? images.side.path
      : images.front
        ? images.front.path
        : null;
    const frontPath = item.thumb || (images.front ? images.front.path : null);
    const sideSrc = sidePath ? `/data/${escape(sidePath)}${suffix}` : '';
    const frontSrc = frontPath ? `/data/${escape(frontPath)}${suffix}` : '';

    const categoryLabels = labelsOf('categories');
    const colorLabels = labelsOf('colors');
    const metaText = [
      categoryLabels[item.category] || '',
      item.color ? colorLabels[item.color] || '' : '',
    ]
      .filter(Boolean)
      .join(' · ');
    el.setAttribute('aria-label', metaText ? `${item.name} · ${metaText}` : item.name);

    el.innerHTML = `
      <span class="rack-item__hanger" aria-hidden="true">
        <svg viewBox="0 0 64 48">
          <path d="M32 20 V13 a6 6 0 1 1 7 -5"></path>
          <path d="M32 20 L7 42 H57 Z"></path>
        </svg>
      </span>
      <span class="rack-item__garment">
        ${sideSrc ? `<img class="rack-item__side" src="${sideSrc}" alt="" loading="lazy">` : ''}
        ${frontSrc ? `<img class="rack-item__front" src="${frontSrc}" alt="" loading="lazy">` : ''}
      </span>
      <span class="rack-item__name">${escape(item.name)}</span>
      <span class="rack-item__meta">${escape(metaText)}</span>
      <button class="rack-item__delete" type="button" title="删除">✕</button>
    `;

    el.addEventListener('pointerdown', (event) => {
      if (event.button !== undefined && event.button !== 0) return;
      if (event.target.closest('.rack-item__delete')) return;
      beginDrag(event, el);
    });
    el.addEventListener('click', (event) => {
      if (event.target.closest('.rack-item__delete')) return;
      if (el._dragEndedAt && Date.now() - el._dragEndedAt < 300) return;
      openGarment(item);
    });
    el.addEventListener('keydown', (event) => {
      if (event.target !== el) return;
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openGarment(item);
      }
    });
    el.querySelector('.rack-item__delete').addEventListener('click', (event) => {
      handleDelete(event, item);
    });

    return el;
  }

  function railSection(label, items, category) {
    const section = document.createElement('section');
    section.className = 'rack-section';
    section.dataset.category = category;
    section.innerHTML = `
      <div class="rack-section__head">
        <span class="rack-section__label">${escape(label)}</span>
        <span class="rack-section__count">${items.length}</span>
      </div>
      <div class="rack-section__body">
        <button class="rack-nav" type="button" data-dir="-1" aria-label="向左滚动">‹</button>
        <div class="rack-scroll">
          <div class="rack-track">
            <div class="rack-bar"></div>
            <div class="rack-items"></div>
          </div>
        </div>
        <button class="rack-nav" type="button" data-dir="1" aria-label="向右滚动">›</button>
      </div>
    `;

    const trackItems = section.querySelector('.rack-items');
    items.forEach((item, index) => trackItems.appendChild(rackItem(item, index)));

    const scroll = section.querySelector('.rack-scroll');
    section.querySelectorAll('.rack-nav').forEach((button) => {
      button.addEventListener('click', () => {
        const distance = Math.max(320, scroll.clientWidth * 0.8);
        scroll.scrollBy({
          left: Number(button.dataset.dir) * distance,
          behavior: 'smooth',
        });
      });
    });

    return section;
  }

  // ---------------------------------------------------------------- 配饰收纳

  function accessoryStyle(item) {
    return ACCESSORY_STYLES.includes(item.display_style) ? item.display_style : 'hang';
  }

  function accessoryTag(item) {
    const categoryLabels = labelsOf('categories');
    const colorLabels = labelsOf('colors');
    const metaText = [
      categoryLabels[item.category] || '',
      item.color ? colorLabels[item.color] || '' : '',
    ]
      .filter(Boolean)
      .join(' · ');

    return `
      <span class="accessory-tag">
        <span class="accessory-tag__name">${escape(item.name)}</span>
        <span class="accessory-tag__meta">${escape(metaText)}</span>
      </span>
    `;
  }

  function accessoryItem(item) {
    const style = accessoryStyle(item);
    const el = document.createElement('div');
    el.className = `accessory-item accessory-item--${style}`;
    el.dataset.id = item.id;
    el.tabIndex = 0;
    el.setAttribute('role', 'button');

    const categoryLabels = labelsOf('categories');
    const colorLabels = labelsOf('colors');
    const metaText = [
      categoryLabels[item.category] || '',
      item.color ? colorLabels[item.color] || '' : '',
    ]
      .filter(Boolean)
      .join(' · ');
    el.setAttribute('aria-label', metaText ? `${item.name} · ${metaText}` : item.name);

    const suffix = imageVersion(item);
    const src = item.thumb ? `/data/${escape(item.thumb)}${suffix}` : '';
    const image = src
      ? `<img class="accessory-img" src="${src}" alt="" loading="lazy">`
      : '<span class="accessory-missing">无图</span>';

    let visual;
    if (style === 'bag') {
      visual = `
        <span class="accessory-bag">
          ${image}
          <span class="accessory-bag__front" aria-hidden="true"></span>
        </span>
      `;
    } else if (style === 'flat') {
      visual = `<span class="accessory-flat">${image}</span>`;
    } else {
      visual = `
        <span class="accessory-clip" aria-hidden="true"></span>
        ${image}
      `;
    }

    el.innerHTML = `
      ${visual}
      ${accessoryTag(item)}
      <button class="accessory-item__delete" type="button" title="删除">✕</button>
    `;

    el.addEventListener('click', (event) => {
      if (event.target.closest('.accessory-item__delete')) return;
      openGarment(item);
    });
    el.addEventListener('keydown', (event) => {
      if (event.target !== el) return;
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openGarment(item);
      }
    });
    el.querySelector('.accessory-item__delete').addEventListener('click', (event) => {
      handleDelete(event, item);
    });

    return el;
  }

  function accessorySection(items) {
    const visible = items.filter((item) => accessoryStyle(item) !== 'drawer');
    if (!visible.length) return null;

    const section = document.createElement('section');
    section.className = 'accessory-section';

    const hangItems = visible.filter((item) => accessoryStyle(item) === 'hang');
    const shelfItems = visible.filter((item) => accessoryStyle(item) !== 'hang');

    section.innerHTML = `
      <div class="rack-section__head">
        <span class="rack-section__label">配饰</span>
        <span class="rack-section__count">${visible.length}</span>
      </div>
      <div class="accessory-zone">
        <div class="accessory-row accessory-row--hang" ${hangItems.length ? '' : 'hidden'}>
          <div class="accessory-track accessory-track--hang">
            <div class="accessory-rod" aria-hidden="true"></div>
            <div class="accessory-items"></div>
          </div>
        </div>
        <div class="accessory-row accessory-row--shelf" ${shelfItems.length ? '' : 'hidden'}>
          <div class="accessory-track accessory-track--shelf">
            <div class="accessory-shelf-line" aria-hidden="true"></div>
            <div class="accessory-items"></div>
          </div>
        </div>
      </div>
    `;

    const hangBox = section.querySelector('.accessory-row--hang .accessory-items');
    hangItems.forEach((item) => hangBox.appendChild(accessoryItem(item)));
    const shelfBox = section.querySelector('.accessory-row--shelf .accessory-items');
    shelfItems.forEach((item) => shelfBox.appendChild(accessoryItem(item)));

    return section;
  }

  // ---------------------------------------------------------------- 衣帽柜

  function zoneOfItem(item) {
    if (['shoes', 'bag', 'hat'].includes(item.category)) return item.category;
    if (item.category === 'accessory' && item.display_style === 'drawer') {
      return 'drawer';
    }
    return null;
  }

  function cabinetSlotOf(item) {
    const slot = Number(item.cabinet_slot);
    return Number.isInteger(slot) && slot >= 0 ? slot : null;
  }

  function slotsOf(items) {
    const map = new Map();
    items.forEach((item) => {
      const slot = cabinetSlotOf(item);
      if (slot !== null) map.set(slot, item);
    });
    return map;
  }

  function maxCabinetSlot(items) {
    let max = -1;
    items.forEach((item) => {
      const slot = cabinetSlotOf(item);
      if (slot !== null && slot > max) max = slot;
    });
    return max;
  }

  function cabinetLabel(item) {
    const categoryLabels = labelsOf('categories');
    const colorLabels = labelsOf('colors');
    const metaText = [
      categoryLabels[item.category] || '',
      item.color ? colorLabels[item.color] || '' : '',
    ]
      .filter(Boolean)
      .join(' · ');
    return metaText ? `${item.name} · ${metaText}` : item.name;
  }

  function cabinetItem(item, zone, slot) {
    const el = document.createElement('div');
    el.className = `closet-item closet-item--${zone}`;
    el.dataset.id = item.id;
    el.tabIndex = 0;
    el.setAttribute('role', 'button');
    const label = cabinetLabel(item);
    el.setAttribute('aria-label', label);

    const suffix = imageVersion(item);
    const src = item.thumb ? `/data/${escape(item.thumb)}${suffix}` : '';
    el.innerHTML = `
      ${src ? `<img class="closet-item__img" src="${src}" alt="" loading="lazy">` : '<span class="closet-item__missing">无图</span>'}
      <span class="closet-item__tag">${escape(label)}</span>
      <button class="closet-item__delete" type="button" title="删除">✕</button>
    `;

    el.addEventListener('click', (event) => {
      if (event.target.closest('.closet-item__delete')) return;
      if (el._dragEndedAt && Date.now() - el._dragEndedAt < 300) return;
      openGarment(item);
    });
    el.addEventListener('keydown', (event) => {
      if (event.target !== el) return;
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openGarment(item);
      }
    });
    el.querySelector('.closet-item__delete').addEventListener('click', (event) => {
      handleDelete(event, item);
    });
    el.addEventListener('pointerdown', (event) => {
      beginCabinetDrag(event, el, item, zone, slot);
    });

    return el;
  }

  function cabinetCell(zone, slot, item) {
    const cell = document.createElement('div');
    cell.className = 'closet-cell';
    cell.dataset.zone = zone;
    cell.dataset.slot = slot;
    if (!item) {
      cell.classList.add('is-empty');
      return cell;
    }
    cell.appendChild(cabinetItem(item, zone, slot));
    return cell;
  }

  function fillCabinetGrid(container, zone, total, map) {
    container.innerHTML = '';
    for (let slot = 0; slot < total; slot += 1) {
      container.appendChild(cabinetCell(zone, slot, map.get(slot)));
    }
  }

  function drawerElement(index, map) {
    const drawer = document.createElement('div');
    drawer.className = 'closet-drawer';
    drawer.dataset.index = index;

    const count = [0, 1, 2].filter((offset) => map.has(index * 3 + offset)).length;
    drawer.innerHTML = `
      <div class="closet-drawer__tray">
        <div class="closet-drawer__cells"></div>
      </div>
      <button class="closet-drawer__front" type="button" data-panel="drawer-${index}"
              aria-label="打开第 ${index + 1} 个抽屉">
        <span class="closet-drawer__label">小配饰 ${index * 3 + 1}–${index * 3 + 3}</span>
        <span class="closet-drawer__handle"></span>
        ${count ? `<span class="closet-drawer__count">${count} 件</span>` : ''}
      </button>
    `;

    const cells = drawer.querySelector('.closet-drawer__cells');
    for (let offset = 0; offset < 3; offset += 1) {
      const slot = index * 3 + offset;
      const cell = cabinetCell('drawer', slot, map.get(slot));
      const number = document.createElement('span');
      number.className = 'closet-drawer__cell-index';
      number.textContent = String(offset + 1);
      cell.appendChild(number);
      cells.appendChild(cell);
    }
    return drawer;
  }

  function cabinetSection({ shoes, hats, bags, drawers }) {
    const shoeRows = Math.max(4, Math.ceil((maxCabinetSlot(shoes) + 1) / 2));
    const hatRows = Math.max(1, Math.ceil((maxCabinetSlot(hats) + 1) / 3));
    const bagRows = Math.max(2, Math.ceil((maxCabinetSlot(bags) + 1) / 3));
    const drawerRows = Math.max(1, Math.ceil((maxCabinetSlot(drawers) + 1) / 9));
    const drawerCount = drawerRows * 3;

    const gap = 6;
    const shoeH = shoeRows * 150 + (shoeRows - 1) * gap;
    const hatH = hatRows * 120 + (hatRows - 1) * gap;
    const bagH = bagRows * 240 + (bagRows - 1) * gap;
    const rightH = hatH + gap + bagH;
    const middleH = Math.max(shoeH, rightH);
    const leftFill = middleH - shoeH;
    const rightFill = middleH - rightH;
    const total = shoes.length + hats.length + bags.length + drawers.length;

    const section = document.createElement('section');
    section.className = 'closet-section';
    section.innerHTML = `
      <div class="rack-section__head">
        <span class="rack-section__label">衣帽柜</span>
        <span class="rack-section__count">${total ? `${total} 件` : '空柜'}</span>
      </div>
      <div class="closet" data-open-panel="">
        <div class="closet__top">
          ${[0, 1, 2].map((index) => `
            <div class="closet-top">
              <div class="closet-top__inner">
                <span class="closet-box" aria-hidden="true"></span>
              </div>
              <button class="closet-door" type="button" data-panel="door-${index}"
                      data-hinge="${index === 2 ? 'right' : 'left'}"
                      aria-label="打开顶柜第 ${index + 1} 扇门">
                <span class="closet-door__panel">
                  <span class="closet-door__label">收纳盒 ${index + 1}</span>
                  <span class="closet-door__handle"></span>
                </span>
              </button>
            </div>
          `).join('')}
        </div>
        <div class="closet-zone-head">
          <span>鞋 · 8 格</span>
          <span>帽子（上） / 包（下）</span>
        </div>
        <div class="closet__middle">
          <div class="closet-side closet-side--left">
            <div class="closet-grid closet-shoes" style="--rows:${shoeRows}"></div>
            ${leftFill > 0 ? `<div class="closet-fill" style="height:${leftFill}px"></div>` : ''}
          </div>
          <div class="closet-side closet-side--right">
            <div class="closet-grid closet-hats" style="--rows:${hatRows}"></div>
            <div class="closet-grid closet-bags" style="--rows:${bagRows}"></div>
            ${rightFill > 0 ? `<div class="closet-fill" style="height:${rightFill}px"></div>` : ''}
          </div>
        </div>
        <div class="closet-zone-head closet-zone-head--drawers">
          <span>小配饰抽屉 · 9 格</span>
        </div>
        <div class="closet__drawers"></div>
      </div>
    `;

    fillCabinetGrid(section.querySelector('.closet-shoes'), 'shoes', shoeRows * 2, slotsOf(shoes));
    fillCabinetGrid(section.querySelector('.closet-hats'), 'hat', hatRows * 3, slotsOf(hats));
    fillCabinetGrid(section.querySelector('.closet-bags'), 'bag', bagRows * 3, slotsOf(bags));

    const drawerBox = section.querySelector('.closet__drawers');
    const drawerMap = slotsOf(drawers);
    for (let index = 0; index < drawerCount; index += 1) {
      drawerBox.appendChild(drawerElement(index, drawerMap));
    }

    section.querySelectorAll('[data-panel]').forEach((button) => {
      button.addEventListener('click', (event) => {
        event.stopPropagation();
        toggleCabinetPanel(section, button.dataset.panel);
      });
    });

    return section;
  }

  function toggleCabinetPanel(section, name) {
    const closet = section.querySelector('.closet');
    const current = closet.dataset.openPanel || '';
    const next = current === name ? '' : name;
    closet.dataset.openPanel = next;
    section.querySelectorAll('[data-panel]').forEach((button) => {
      button.classList.toggle('is-open', button.dataset.panel === next);
    });
    section.querySelectorAll('.closet-drawer').forEach((drawer) => {
      drawer.classList.toggle(
        'is-open',
        `drawer-${drawer.dataset.index}` === next
      );
    });
    section.classList.toggle('has-open-drawer', next.startsWith('drawer-'));
  }

  function closeCabinetPanels() {
    document.querySelectorAll('.closet-section').forEach((section) => {
      const closet = section.querySelector('.closet');
      if (!closet || !closet.dataset.openPanel) return;
      toggleCabinetPanel(section, closet.dataset.openPanel);
    });
  }

  function findClosetDrop(event, zone) {
    const cells = document.querySelectorAll('.closet-cell');
    for (const cell of cells) {
      if (cell.dataset.zone !== zone) continue;
      const drawer = cell.closest('.closet-drawer');
      if (drawer && !drawer.classList.contains('is-open')) continue;
      const rect = cell.getBoundingClientRect();
      if (
        event.clientX >= rect.left && event.clientX <= rect.right &&
        event.clientY >= rect.top && event.clientY <= rect.bottom
      ) {
        return { type: 'cell', slot: Number(cell.dataset.slot), cell };
      }
    }
    if (zone === 'drawer') {
      const fronts = document.querySelectorAll('.closet-drawer__front');
      for (const front of fronts) {
        const rect = front.getBoundingClientRect();
        if (
          event.clientX >= rect.left && event.clientX <= rect.right &&
          event.clientY >= rect.top && event.clientY <= rect.bottom
        ) {
          const drawer = front.closest('.closet-drawer');
          return { type: 'drawer', index: Number(drawer.dataset.index), front };
        }
      }
    }
    return null;
  }

  function beginCabinetDrag(event, el, item, zone, slot) {
    if (event.button !== undefined && event.button !== 0) return;
    if (event.target.closest('.closet-item__delete')) return;
    cabinetDrag = {
      el,
      item,
      zone,
      slot,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
    };
    try {
      el.setPointerCapture(event.pointerId);
    } catch (ignore) {
      /* 指针捕获失败时仍可拖动 */
    }
  }

  function onCabinetDragMove(event) {
    if (!cabinetDrag || event.pointerId !== cabinetDrag.pointerId) return;
    const dx = event.clientX - cabinetDrag.startX;
    const dy = event.clientY - cabinetDrag.startY;
    if (!cabinetDrag.moved) {
      if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
      cabinetDrag.moved = true;
      cabinetDrag.el.classList.add('is-dragging');
      document.body.classList.add('is-cabinet-dragging');
    }

    document
      .querySelectorAll('.closet-cell.is-drop-target, .closet-drawer__front.is-drop-target')
      .forEach((node) => node.classList.remove('is-drop-target'));
    const drop = findClosetDrop(event, cabinetDrag.zone);
    if (drop) {
      (drop.cell || drop.front).classList.add('is-drop-target');
    }
  }

  async function onCabinetDragUp(event) {
    if (!cabinetDrag || event.pointerId !== cabinetDrag.pointerId) return;
    const { el, item, zone, slot, pointerId, moved } = cabinetDrag;
    cabinetDrag = null;
    try {
      el.releasePointerCapture(pointerId);
    } catch (ignore) {
      /* 已经释放时忽略 */
    }
    el.classList.remove('is-dragging');
    document.body.classList.remove('is-cabinet-dragging');
    document
      .querySelectorAll('.closet-cell.is-drop-target, .closet-drawer__front.is-drop-target')
      .forEach((node) => node.classList.remove('is-drop-target'));

    if (!moved) return;
    el._dragEndedAt = Date.now();

    const drop = findClosetDrop(event, zone);
    if (!drop) return;

    let targetSlot = drop.slot;
    let targetDrawer = null;
    if (drop.type === 'drawer') {
      targetDrawer = drop.index;
      const used = new Set(
        state.items
          .filter((candidate) => zoneOfItem(candidate) === 'drawer')
          .map((candidate) => cabinetSlotOf(candidate))
      );
      targetSlot = [0, 1, 2]
        .map((offset) => targetDrawer * 3 + offset)
        .find((candidate) => !used.has(candidate));
      if (targetSlot === undefined) {
        App.ui.toast('这个抽屉已经满了', 'error');
        return;
      }
    }

    if (targetSlot === slot) return;

    const occupant = state.items.find(
      (candidate) =>
        candidate.id !== item.id &&
        zoneOfItem(candidate) === zone &&
        cabinetSlotOf(candidate) === targetSlot
    );

    const before = [
      { item, slot: cabinetSlotOf(item) },
      ...(occupant ? [{ item: occupant, slot: cabinetSlotOf(occupant) }] : []),
    ];
    const payload = [{ id: item.id, slot: targetSlot }];
    if (occupant) payload.push({ id: occupant.id, slot });

    item.cabinet_slot = targetSlot;
    if (occupant) occupant.cabinet_slot = slot;

    try {
      await App.api.put('/api/garments/cabinet-slots', { items: payload });
      App.ui.toast('位置已保存');
      render();
      if (zone === 'drawer') {
        const nextSection = els.rack.querySelector('.closet-section');
        const openIndex = Math.floor(targetSlot / 3);
        if (nextSection) {
          toggleCabinetPanel(nextSection, `drawer-${openIndex}`);
        }
      }
    } catch (err) {
      before.forEach((entry) => {
        entry.item.cabinet_slot = entry.slot;
      });
      App.ui.toast(err.message, 'error');
      render();
    }
  }

  // ---------------------------------------------------------------- 渲染

  function render() {
    const items = state.items;
    const filtered = hasFilters();

    els.rack.innerHTML = '';
    els.rack.hidden = items.length === 0;

    if (items.length) {
      els.count.textContent = filtered
        ? `筛选出 ${items.length} 件`
        : `${items.length} 件衣服`;
    } else {
      els.count.textContent = filtered ? '没有符合条件的衣服' : '还没有衣服';
    }

    els.empty.hidden = items.length > 0 || filtered || state.loading;
    els.filterEmpty.hidden = items.length > 0 || !filtered || state.loading;

    const grouped = {};
    items.forEach((item) => {
      if (!grouped[item.category]) grouped[item.category] = [];
      grouped[item.category].push(item);
    });

    (state.meta.categories || []).forEach((cat) => {
      if (!CLOTH_CATEGORIES.includes(cat.value)) return;
      const list = grouped[cat.value];
      if (!list || !list.length) return;
      els.rack.appendChild(railSection(cat.label, list, cat.value));
    });

    const accessories = grouped[ACCESSORY_CATEGORY] || [];
    const accessorySectionEl = accessorySection(accessories);
    if (accessorySectionEl) {
      els.rack.appendChild(accessorySectionEl);
    }

    const closetGroups = {
      shoes: grouped.shoes || [],
      hats: grouped.hat || [],
      bags: grouped.bag || [],
      drawers: accessories.filter((item) => accessoryStyle(item) === 'drawer'),
    };
    const closetCount =
      closetGroups.shoes.length +
      closetGroups.hats.length +
      closetGroups.bags.length +
      closetGroups.drawers.length;
    // 没筛选时始终显示完整柜体（空格也保留）；筛选时只在有柜内物品时显示
    if (!filtered || closetCount) {
      els.rack.appendChild(cabinetSection(closetGroups));
    }
  }

  async function handleDelete(event, item) {
    event.stopPropagation();

    const confirmed = await App.ui.confirm({
      title: `删除「${item.name}」？`,
      message: '这件衣服会移入回收站，图片不会立刻删除，可以随时恢复。',
      confirmText: '移入回收站',
    });
    if (!confirmed) return;

    try {
      await App.api.del(`/api/garments/${item.id}`);
      App.ui.toast('已删除');
      load();
    } catch (err) {
      App.ui.toast(err.message, 'error');
    }
  }

  // ---------------------------------------------------------------- 数据

  async function load() {
    state.loading = true;
    try {
      const params = new URLSearchParams();
      if (state.category) params.set('category', state.category);
      if (state.color) params.set('color', state.color);
      if (state.season) params.set('season', state.season);
      if (state.scene) params.set('scene', state.scene);
      if (state.keyword) params.set('q', state.keyword);

      const query = params.toString();
      state.items = await App.api.get('/api/garments' + (query ? `?${query}` : ''));
      render();
      loadCounts();
    } catch (err) {
      App.ui.toast(err.message, 'error');
    } finally {
      state.loading = false;
    }
  }

  // ---------------------------------------------------------------- 初始化

  function init(meta) {
    state.meta = meta;
    cache();

    renderCategoryChips();
    fillSelect(els.color, meta.colors, '颜色');
    fillSelect(els.season, meta.seasons, '季节');
    fillSelect(
      els.scene,
      meta.scenes.map((name) => ({ value: name, label: name })),
      '场合'
    );

    els.color.addEventListener('change', () => {
      state.color = els.color.value;
      updateClearButton();
      load();
    });
    els.season.addEventListener('change', () => {
      state.season = els.season.value;
      updateClearButton();
      load();
    });
    els.scene.addEventListener('change', () => {
      state.scene = els.scene.value;
      updateClearButton();
      load();
    });
    els.clear.addEventListener('click', clearFilters);
    document.getElementById('btn-clear-empty').addEventListener('click', clearFilters);

    els.filterToggle.addEventListener('click', (event) => {
      event.stopPropagation();
      toggleFilters();
    });
    els.filterPop.addEventListener('click', (event) => event.stopPropagation());
    els.filterDone.addEventListener('click', () => toggleFilters(false));
    document.addEventListener('click', () => toggleFilters(false));
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') toggleFilters(false);
    });
    window.addEventListener('hashchange', () => toggleFilters(false));

    let timer = null;
    els.search.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        state.keyword = els.search.value.trim();
        updateClearButton();
        load();
      }, 220);
    });

    window.addEventListener('pointermove', onDragMove);
    window.addEventListener('pointerup', onDragUp);
    window.addEventListener('pointercancel', onDragUp);
    window.addEventListener('pointermove', onCabinetDragMove);
    window.addEventListener('pointerup', onCabinetDragUp);
    window.addEventListener('pointercancel', onCabinetDragUp);
    document.addEventListener('pointerdown', (event) => {
      if (!event.target.closest('.closet')) {
        closeCabinetPanels();
      }
    });

    updateClearButton();
    loadCounts();
    load();
  }

  App.wardrobe = { init, load, loadCounts };
})(window.App = window.App || {});
