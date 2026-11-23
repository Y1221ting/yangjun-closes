/* 搭配页顶部：基准模特的五角度旋转展示。 */
(function (App) {
  'use strict';

  const state = {
    loading: false,
  };

  const els = {};
  let view = null;

  function cache() {
    els.hero = document.getElementById('model-hero');
    els.view = document.getElementById('model-view');
    els.empty = document.getElementById('model-empty');
  }

  function init() {
    cache();
    view = App.createRotateView({
      view: 'model-view',
      frame: 'model-frame',
      dots: 'model-dots',
      hint: 'model-hint',
    });
    view.init();
    els.hero.hidden = false;
  }

  async function load() {
    if (state.loading) return;
    state.loading = true;
    try {
      const data = await App.api.get('/api/model');
      const images = data.images || {};
      if (Object.keys(images).length) {
        els.empty.hidden = true;
        els.view.hidden = false;
        view.mount(images, data.updated_at);
      } else {
        view.destroy();
        els.view.hidden = true;
        els.empty.hidden = false;
      }
    } catch (err) {
      App.ui.toast(err.message, 'error');
    } finally {
      state.loading = false;
    }
  }

  App.modelStage = { init, load };
})(window.App = window.App || {});
