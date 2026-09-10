const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.join(__dirname, '../src/chatvoice/web/static');
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');

function harness(mutation) {
  const elements = [];
  const timers = new Map();
  const stores = new Map();
  const requests = [];
  const downloads = [];
  const tracks = [];
  const graphs = [];
  const sockets = [];
  const revoked = [];
  let serial = 0;
  let clipboard = '';
  const matches = (element, selector) => {
    if (selector.startsWith('#')) return element.id === selector.slice(1);
    if (selector.startsWith('.')) return element.classList.contains(selector.slice(1));
    const attribute = selector.match(/^\[([^=\]]+)(?:="([^"]+)")?\]$/);
    return attribute ? element.hasAttribute(attribute[1]) && (attribute[2] === undefined || element.getAttribute(attribute[1]) === attribute[2]) : element.tagName === selector.toUpperCase();
  };
  class Element {
    constructor(tag = 'div', attributes = {}) {
      this.tagName = tag.toUpperCase(); this.attributes = {}; this.dataset = {}; this.children = []; this.listeners = {};
      this.value = ''; this.textContent = ''; this.innerHTML = ''; this.hidden = false; this.disabled = false; this.checked = false;
      this.style = { setProperty(name, value) { this[name] = value; } };
      this.className = ''; this.clientWidth = 300; this.clientHeight = 60;
      this.classList = {
        contains: name => this.className.split(/\s+/).includes(name),
        add: (...names) => { this.className = [...new Set([...this.className.split(/\s+/), ...names])].join(' '); },
        remove: (...names) => { this.className = this.className.split(/\s+/).filter(name => !names.includes(name)).join(' '); },
        toggle: (name, force) => { const active = force === undefined ? !this.classList.contains(name) : force; this.classList[active ? 'add' : 'remove'](name); return active; },
      };
      Object.entries(attributes).forEach(([name, value]) => this.setAttribute(name, value));
      elements.push(this);
    }
    setAttribute(name, value) {
      this.attributes[name] = String(value);
      if (name.startsWith('data-')) this.dataset[name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = value;
      else if (name === 'class') this.className = value;
      else if (['hidden', 'disabled', 'checked'].includes(name)) this[name] = true;
      else this[name] = value;
    }
    getAttribute(name) { return this.attributes[name]; }
    hasAttribute(name) { return name in this.attributes; }
    removeAttribute(name) { delete this.attributes[name]; }
    append(...children) { children.forEach(child => { child.parentNode = this; this.children.push(child); }); }
    appendChild(child) { this.append(child); return child; }
    insertBefore(child, before) { child.parentNode = this; this.children.splice(Math.max(0, this.children.indexOf(before)), 0, child); }
    remove() { if (this.parentNode) this.parentNode.children = this.parentNode.children.filter(child => child !== this); elements.splice(elements.indexOf(this), 1); }
    contains(child) { return child === this || this.children.some(item => item.contains(child)); }
    closest(selector) { return matches(this, selector) ? this : this.parentNode?.closest(selector); }
    querySelectorAll(selector) { return elements.filter(element => element !== this && this.contains(element) && matches(element, selector)); }
    querySelector(selector) { return this.querySelectorAll(selector)[0] || this.children[0] || this.appendChild(new Element('span')); }
    addEventListener(type, callback) { (this.listeners[type] ||= []).push(callback); }
    async dispatch(type, extra = {}) { for (const callback of this.listeners[type] || []) await callback({ target: this, preventDefault() {}, stopPropagation() {}, ...extra }); }
    click() { if (this.tagName === 'A') downloads.push({ href: this.href, download: this.download }); return this.dispatch('click'); }
    focus() {} scrollIntoView() {} select() {}
    get options() { return this.children.filter(child => child.tagName === 'OPTION'); }
    get selectedIndex() { return Math.max(0, this.options.findIndex(option => option.value === this.value)); }
    reset() { this.children.forEach(child => { if (child.tagName === 'INPUT') child.value = ''; }); }
    showModal() { this.open = true; } close() { this.open = false; return this.dispatch('close'); }
    getContext() { return { setTransform() {}, clearRect() {}, beginPath() {}, roundRect() {}, fill() {} }; }
  }
  const body = new Element('body');
  const stack = [body];
  for (const token of html.matchAll(/<\/?([a-z][\w-]*)\b([^>]*)>/gi)) {
    if (token[0].startsWith('</')) { if (stack.at(-1).tagName === token[1].toUpperCase()) stack.pop(); continue; }
    const attributes = {};
    for (const attr of token[2].matchAll(/([\w-]+)(?:="([^"]*)")?/g)) attributes[attr[1]] = attr[2] || '';
    const element = new Element(token[1], attributes);
    stack.at(-1).append(element);
    if (!['input', 'img', 'meta', 'link', 'br', 'hr', 'source'].includes(token[1])) stack.push(element);
  }
  const document = { body, title: '', getElementById: id => elements.find(element => element.id === id), querySelectorAll: selector => elements.filter(element => matches(element, selector)), createElement: tag => new Element(tag), addEventListener: (...args) => body.addEventListener(...args) };
  const later = callback => { const id = ++serial; timers.set(id, callback); return id; };
  const transactions = [];
  const transactionControl = { holdWrites: false };
  const database = {
    objectStoreNames: { contains: name => stores.has(name) },
    createObjectStore(name) { stores.set(name, new Map()); return { createIndex() {} }; },
    transaction(name, mode = 'readonly') {
      const store = stores.get(name); assert.ok(store, `unknown store ${name}`);
      const staged = new Map([...store].map(([key, value]) => [key, structuredClone(value)]));
      const tx = { mode, name, pending: 0, requestSucceeded: false, completed: false, aborted: false,
        commit() {
          if (this.completed || this.aborted || this.pending) return;
          if (mode === 'readwrite') { store.clear(); for (const [key, value] of staged) store.set(key, value); }
          this.completed = true; this.oncomplete?.();
        },
        abort() {
          if (this.completed || this.aborted) return;
          this.aborted = true; this.error = new Error('浏览器事务中止'); this.onabort?.();
        },
      };
      transactions.push(tx);
      const request = value => {
        const result = {}; tx.pending++;
        queueMicrotask(() => {
          if (tx.aborted) return;
          result.result = structuredClone(value); result.onsuccess?.();
          tx.requestSucceeded = true; tx.pending--;
          queueMicrotask(() => { if (!(mode === 'readwrite' && transactionControl.holdWrites)) tx.commit(); });
        });
        return result;
      };
      tx.objectStore = () => ({
        getAll: () => request([...staged.values()]), get: id => request(staged.get(id)),
        put: value => { assert.equal(mode, 'readwrite'); staged.set(value.id, structuredClone(value)); return request(value.id); },
        delete: id => { assert.equal(mode, 'readwrite'); staged.delete(id); return request(undefined); },
      });
      return tx;
    },
  };
  class Socket {
    static OPEN = 1; static CONNECTING = 0;
    constructor(url) { this.url = url; this.readyState = 0; this.sent = []; sockets.push(this); }
    send(text) { this.sent.push(JSON.parse(text)); }
    async open() { this.readyState = 1; await this.onopen?.(); }
    message(payload) { this.onmessage?.({ data: JSON.stringify(payload) }); }
    close() { this.readyState = 3; this.closed = true; this.onclose?.(); }
  }
  class AudioGraph {
    constructor() { this.sampleRate = 48000; this.currentTime = 0; this.destination = {}; this.nodes = []; graphs.push(this); }
    node() { const node = { connect() { this.connected = true; }, disconnect() { this.disconnected = true; }, getByteTimeDomainData(buffer) { buffer.fill(128); }, start() {}, stop() { this.stopped = true; } }; this.nodes.push(node); return node; }
    createMediaStreamSource() { return this.node(); } createScriptProcessor() { return this.node(); } createAnalyser() { return this.node(); }
    createBufferSource() { return this.node(); } createBuffer(channels, length) { return { duration: length / 24000, getChannelData: () => new Float32Array(length) }; }
    async resume() {} async close() { this.closed = true; }
  }
  class Recorder {
    constructor(stream) { this.stream = stream; this.state = 'inactive'; this.mimeType = 'audio/webm'; }
    start() { this.state = 'recording'; }
    stop() { this.state = 'inactive'; this.ondataavailable?.({ data: new Blob(['reference'], { type: this.mimeType }) }); this.onstop?.(); }
  }
  const context = vm.createContext({ console, Blob, FormData, TextDecoder, TextEncoder, AbortController, Uint8Array, Float32Array, Int16Array, ArrayBuffer, Date, Intl, crypto: require('node:crypto').webcrypto,
    document, URLSearchParams, location: { protocol: 'https:', host: 'app.example.test', search: '' }, confirm: () => true,
    navigator: { clipboard: { async writeText(text) { clipboard = text; } }, mediaDevices: { async getUserMedia() { const track = { stop() { this.stopped = true; } }; tracks.push(track); return { getTracks: () => [track] }; } } },
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    indexedDB: { open() { const pending = {}; queueMicrotask(() => { pending.result = database; pending.onupgradeneeded?.(); pending.onsuccess?.(); }); return pending; } },
    WebSocket: Socket, AudioContext: AudioGraph, MediaRecorder: Recorder,
    URL: { createObjectURL: () => `blob:offline-${++serial}`, revokeObjectURL: value => revoked.push(value) },
    btoa: value => Buffer.from(value, 'binary').toString('base64'), atob: value => Buffer.from(value, 'base64').toString('binary'),
    setTimeout: later, setInterval: later, clearTimeout: id => timers.delete(id), clearInterval: id => timers.delete(id), requestAnimationFrame: later, cancelAnimationFrame: id => timers.delete(id),
    fetch: async (url, options = {}) => { requests.push({ url, ...options }); return await api.respond(url, options); },
    addEventListener() {}, matchMedia: () => ({ matches: false }), innerWidth: 1200,
  });
  context.window = context; context.globalThis = context;
  const api = { context, document, timers, stores, requests, downloads, tracks, graphs, sockets, revoked, transactions, transactionControl,
    get clipboard() { return clipboard; },
    respond: async url => { throw new Error(`Unexpected offline request: ${url}`); },
    run: code => vm.runInContext(code, context),
    element: id => { const element = document.getElementById(id); assert.ok(element, id); return element; },
    async settle(predicate) { for (let turn = 0; turn < 100; turn++) { if (predicate()) return; await new Promise(resolve => setImmediate(resolve)); } assert.fail('async barrier not reached'); },
  };
  vm.runInContext(fs.readFileSync(path.join(root, 'transcript-state.js'), 'utf8'), context);
  let script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
  const bootstrap = script.lastIndexOf('\n    updateTtsCount();');
  assert.ok(bootstrap > 0);
  script = script.slice(0, bootstrap);
  if (mutation) { assert.ok(script.includes(mutation[0]), 'mutation target missing'); script = script.replace(mutation[0], mutation[1]); }
  vm.runInContext(script, context, { filename: 'production-index.js' });
  return api;
}

function json(value, status = 200) { return { ok: status < 400, status, json: async () => value, text: async () => JSON.stringify(value), headers: { get: () => null } }; }
function audio(value = 'synthetic-audio', type = 'audio/mpeg') { return { ...json({}), blob: async () => new Blob([value], { type }) }; }
function sse(events) { let index = 0; return { ...json({}), body: { getReader: () => ({ cancel: async () => {}, read: async () => index < events.length ? { value: new TextEncoder().encode(events[index++]), done: false } : { done: true } }) } }; }
function deferred() { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; }
module.exports = { harness, json, audio, sse, deferred, assert };
