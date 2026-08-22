#!/usr/bin/env node
const assert = require('assert').strict;
const { splitSentences, planRevision } = require('../src/chatvoice/web/static/transcript-state.js');

function createHarness(existing = []) {
  return { confirmed: [...existing], rewrite: [], live: '', confirmedCount: 0 };
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function apply(state, text, final = false) {
  const plan = planRevision({
    text,
    confirmedCount: state.confirmedCount,
    previousRewrite: state.rewrite,
    previousLive: state.live,
    final,
  });
  state.confirmed.push(...plan.promote);
  state.confirmedCount += plan.promote.length;
  state.rewrite = plan.rewrite;
  state.live = plan.live;
  return plan;
}

const state = createHarness();
apply(state, '第一句话。');
assert.deepEqual(state, { confirmed: [], rewrite: [], live: '第一句话。', confirmedCount: 0 });

apply(state, '第一句话。第二句话。');
assert.deepEqual(state.confirmed, []);
assert.deepEqual(state.rewrite, ['第一句话。']);
assert.equal(state.live, '第二句话。');

apply(state, '第一句话。第二句话已经纠正。第三句话。');
assert.deepEqual(state.confirmed, ['第一句话。']);
assert.deepEqual(state.rewrite, ['第二句话已经纠正。']);
assert.equal(state.live, '第三句话。');

const beforeRegression = clone(state);
const regression = apply(state, '第一句话。第二句话。');
assert.equal(regression.regressive, true);
assert.deepEqual(state, beforeRegression, 'a shorter ASR revision must not swallow visible text');

const beforePause = clone(state);
assert.deepEqual(state, beforePause, 'pause is a transport state change and must not mutate transcript zones');

apply(state, '第一句话。第二句话最终纠正。第三句话。第四句话。');
assert.deepEqual(state.confirmed, ['第一句话。', '第二句话最终纠正。']);
assert.deepEqual(state.rewrite, ['第三句话。']);
assert.equal(state.live, '第四句话。');

apply(state, '第一句话。第二句话最终纠正。第三句话。第四句话。', true);
assert.deepEqual(state.confirmed, ['第一句话。', '第二句话最终纠正。', '第三句话。', '第四句话。']);
assert.deepEqual(state.rewrite, []);
assert.equal(state.live, '');

state.confirmedCount = 0;
apply(state, '继续记录的第一句。');
assert.deepEqual(state.confirmed.slice(0, 4), ['第一句话。', '第二句话最终纠正。', '第三句话。', '第四句话。']);
assert.equal(state.live, '继续记录的第一句。', 'continuation must preserve the previous meeting transcript');

const emptyFinalState = createHarness();
apply(emptyFinalState, '待确认上文。新的实时内容。');
apply(emptyFinalState, '', true);
assert.deepEqual(emptyFinalState.confirmed, ['待确认上文。', '新的实时内容。'], 'an empty final event must retain the last visible partial');

const correctedTailState = createHarness();
apply(correctedTailState, 'We need a recorder. It should keep context.');
apply(correctedTailState, 'We need a meeting recorder. It should keep context.');
assert.deepEqual(correctedTailState.rewrite, ['We need a meeting recorder.']);
assert.equal(correctedTailState.live, 'It should keep context.');

const repeatedSentenceState = createHarness();
apply(repeatedSentenceState, '可以重复。可以重复。新的内容。');
apply(repeatedSentenceState, '可以重复。可以重复。新的内容。下一句。');
assert.deepEqual(repeatedSentenceState.confirmed, ['可以重复。', '可以重复。'], 'legitimate repeated sentences must not be deduplicated away');

const monotonicState = createHarness();
let previousConfirmedLength = 0;
for (let index = 1; index <= 40; index += 1) {
  const fullText = Array.from({ length: index }, (_, sentenceIndex) => `第${sentenceIndex + 1}句。`).join('');
  apply(monotonicState, fullText);
  assert.ok(monotonicState.confirmed.length >= previousConfirmedLength);
  previousConfirmedLength = monotonicState.confirmed.length;
  if (index % 7 === 0) {
    const shorterText = Array.from({ length: Math.max(1, index - 3) }, (_, sentenceIndex) => `第${sentenceIndex + 1}句。`).join('');
    apply(monotonicState, shorterText);
    assert.ok(monotonicState.confirmed.length >= previousConfirmedLength);
  }
}

assert.ok(splitSentences('这是一个很长的识别片段，没有句号，但是有多个逗号，需要在页面中逐步上移，避免所有文字一直挤在实时区域，最后突然整体跳动').length >= 2);
assert.deepEqual(splitSentences('中文一句。English sentence! 最后一段？'), ['中文一句。', 'English sentence!', '最后一段？']);

console.log(JSON.stringify({
  ok: true,
  cases: [
    'single partial',
    'rewrite above live divider',
    'monotonic confirmation',
    'regressive revision retained',
    'pause retention',
    'final promotion',
    'continue after end',
    'empty final fallback',
    'same-width contextual correction',
    'legitimate duplicate sentences',
    '40-step monotonic stress',
    'long clause splitting',
    'mixed punctuation splitting',
  ],
}, null, 2));
