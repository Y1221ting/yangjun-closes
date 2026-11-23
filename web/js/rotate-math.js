/* 旋转视图的纯计算部分：角度 → 每张图的 transform 和透明度。
   浏览器里挂在 App.rotateMath，Node 里可以直接 require 做单元测试。 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) {
    module.exports = api;
  } else {
    root.App = root.App || {};
    root.App.rotateMath = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // 每个角度的理想位置（0 = 正面，180 = 背面）
  const RAW_IDEAL = { front: 0, front45: 45, side: 90, back135: 135, back: 180 };

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function smoothstep(edge0, edge1, x) {
    const t = clamp((x - edge0) / (edge1 - edge0), 0, 1);
    return t * t * (3 - 2 * t);
  }

  /**
   * 把角度列表转成帧序列，并把第一帧归零。
   * ['front','side','back'] → ideal [0, 90, 180]
   * ['side','back']         → ideal [0, 90]
   */
  function buildFrames(angles) {
    const frames = angles.map((angle, index) => ({
      angle,
      raw: Object.prototype.hasOwnProperty.call(RAW_IDEAL, angle)
        ? RAW_IDEAL[angle]
        : index * 90,
    }));
    const base = frames.length ? frames[0].raw : 0;
    return frames.map((frame) => ({
      angle: frame.angle,
      ideal: frame.raw - base,
    }));
  }

  /**
   * 采样当前角度，返回每帧的 {scaleX, rotateY, opacity}。
   * 相邻两帧在 30%~70% 之间交叉淡化，并轻微反向旋转，形成翻卡效果。
   */
  function sample(frames, angle) {
    const styles = frames.map(() => ({ scaleX: 0, rotateY: 0, opacity: 0 }));
    if (!frames.length) {
      return styles;
    }
    if (frames.length === 1) {
      styles[0] = { scaleX: 1, rotateY: 0, opacity: 1 };
      return styles;
    }

    const min = frames[0].ideal;
    const max = frames[frames.length - 1].ideal;
    const current = clamp(angle, min, max);

    let index = 0;
    while (index < frames.length - 2 && current > frames[index + 1].ideal) {
      index += 1;
    }

    const from = frames[index];
    const to = frames[index + 1];
    const span = to.ideal - from.ideal || 1;
    const progress = clamp((current - from.ideal) / span, 0, 1);

    const outScale = Math.max(0.18, Math.cos((progress * Math.PI) / 2));
    const inScale = Math.max(0.18, Math.sin((progress * Math.PI) / 2));
    const outOpacity = 1 - smoothstep(0.3, 0.7, progress);
    const inOpacity = smoothstep(0.3, 0.7, progress);

    styles[index] = {
      scaleX: outScale,
      rotateY: -progress * 30,
      opacity: outOpacity,
    };
    styles[index + 1] = {
      scaleX: inScale,
      rotateY: (1 - progress) * 30,
      opacity: inOpacity,
    };
    return styles;
  }

  return { buildFrames, sample };
});
