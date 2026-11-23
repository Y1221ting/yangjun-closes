/* 阶段 3 单元测试：旋转角度计算。
   用法：node tests/test_rotate_math.js */

'use strict';

const math = require('../web/js/rotate-math.js');

let passed = 0;
let failed = 0;

function check(condition, label, detail) {
  if (condition) {
    passed += 1;
    console.log(`[PASS] ${label}`);
  } else {
    failed += 1;
    console.log(`[FAIL] ${label} ${detail || ''}`);
  }
}

function near(a, b, epsilon = 1e-6) {
  return Math.abs(a - b) < epsilon;
}

function ideals(frames) {
  return frames.map((frame) => frame.ideal);
}

// ---------------------------------------------------------------- 帧序列

const three = math.buildFrames(['front', 'side', 'back']);
check(JSON.stringify(ideals(three)) === '[0,90,180]', '三张图理想角度为 0/90/180');

const two = math.buildFrames(['front', 'back']);
check(JSON.stringify(ideals(two)) === '[0,180]', '缺侧面时为 0/180');

const sideBack = math.buildFrames(['side', 'back']);
check(JSON.stringify(ideals(sideBack)) === '[0,90]', '只有侧/背时归零为 0/90');

const single = math.buildFrames(['front']);
check(JSON.stringify(ideals(single)) === '[0]', '单张图只有一个角度');

const five = math.buildFrames(['front', 'front45', 'side', 'back135', 'back']);
check(
  JSON.stringify(ideals(five)) === '[0,45,90,135,180]',
  '五张图为 0/45/90/135/180'
);

const partial = math.buildFrames(['front', 'front45', 'side']);
check(JSON.stringify(ideals(partial)) === '[0,45,90]', '缺少后段角度时保留 45° 间隔');

// ---------------------------------------------------------------- 采样

const at0 = math.sample(three, 0);
check(near(at0[0].opacity, 1) && near(at0[1].opacity, 0), '0° 只显示正面');
check(near(at0[0].scaleX, 1), '0° 正面宽度完整');

const at45 = math.sample(three, 45);
check(near(at45[0].opacity, 0.5) && near(at45[1].opacity, 0.5), '45° 正面与侧面各半');
check(near(at45[0].scaleX, Math.cos(Math.PI / 4), 1e-3), '45° 正面按余弦压缩');
check(near(at45[1].scaleX, Math.sin(Math.PI / 4), 1e-3), '45° 侧面按正弦展开');
check(at45[0].rotateY < 0 && at45[1].rotateY > 0, '45° 两张图反向倾斜');

const at90 = math.sample(three, 90);
check(near(at90[1].opacity, 1), '90° 完全显示侧面');
check(near(at90[0].opacity, 0), '90° 正面完全隐藏');

const at135 = math.sample(three, 135);
check(near(at135[1].opacity, 0.5) && near(at135[2].opacity, 0.5), '135° 侧面与背面各半');

const at180 = math.sample(three, 180);
check(near(at180[2].opacity, 1), '180° 完全显示背面');
check(near(at180[0].opacity, 0), '180° 正面完全隐藏');

const atNeg = math.sample(three, -50);
check(near(atNeg[0].opacity, 1), '超出下限时钳制到正面');

const atOver = math.sample(three, 300);
check(near(atOver[2].opacity, 1), '超出上限时钳制到背面');

const twoAt90 = math.sample(two, 90);
check(near(twoAt90[0].opacity, 0.5) && near(twoAt90[1].opacity, 0.5), '缺侧面时 90° 前后各半');

const singleAt60 = math.sample(single, 60);
check(near(singleAt60[0].opacity, 1), '单张图任何角度都完整显示');

const fiveAt22 = math.sample(five, 22.5);
check(
  near(fiveAt22[0].opacity, 0.5) && near(fiveAt22[1].opacity, 0.5),
  '五张图 22.5° 正面与左前 45° 各半'
);

const fiveAt112 = math.sample(five, 112.5);
check(
  near(fiveAt112[2].opacity, 0.5) && near(fiveAt112[3].opacity, 0.5),
  '五张图 112.5° 侧面与左后 135° 各半'
);

// ---------------------------------------------------------------- 边界

let minScale = 1;
for (let angle = 0; angle <= 180; angle += 1) {
  const styles = math.sample(three, angle);
  styles.forEach((style) => {
    if (style.opacity > 0.001) {
      minScale = Math.min(minScale, style.scaleX);
    }
  });
}
check(minScale >= 0.18, '任何角度的压缩比都不小于 0.18', `实际 ${minScale}`);

let totalOpacity = 0;
for (let angle = 0; angle <= 180; angle += 1) {
  const styles = math.sample(three, angle);
  totalOpacity = Math.max(totalOpacity, styles.reduce((sum, s) => sum + s.opacity, 0));
}
check(totalOpacity <= 1.0001, '同时可见的图透明度总和不大于 1', `实际 ${totalOpacity}`);

for (let angle = 0; angle <= 180; angle += 1) {
  const styles = math.sample(three, angle);
  const sorted = styles.map((s) => s.scaleX).sort((a, b) => b - a);
  if (sorted[0] < 0.7) {
    check(false, `角度 ${angle}° 至少有一张图保持可见`, `最大 ${sorted[0]}`);
    break;
  }
}
check(true, '所有角度下都至少有一张图保持可见');

console.log(`\n结果：${passed} 项通过，${failed} 项失败`);
process.exit(failed === 0 ? 0 : 1);
