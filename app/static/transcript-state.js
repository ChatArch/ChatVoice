(function attachTranscriptState(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.TranscriptState = api;
}(typeof globalThis !== 'undefined' ? globalThis : this, function createTranscriptStateApi() {
  function normalizeText(value) {
    return String(value || '').replace(/\s+/g, ' ').trim();
  }

  function hasContent(value) {
    try {
      return /[\p{L}\p{N}]/u.test(value);
    } catch (_) {
      return /[A-Za-z0-9\u3400-\u9fff]/.test(value);
    }
  }

  function splitLongClause(value, maxChars = 46) {
    if (value.length <= maxChars) return [value];
    const clauses = value.match(/[^，,：:]+[，,：:]?/g) || [value];
    const output = [];
    let buffer = '';
    for (const clause of clauses) {
      if (buffer && buffer.length + clause.length > maxChars) {
        output.push(buffer);
        buffer = clause;
      } else {
        buffer += clause;
      }
    }
    if (buffer) output.push(buffer);
    return output;
  }

  function splitSentences(text) {
    const normalized = normalizeText(text);
    if (!normalized) return [];
    const sentences = normalized.match(/[^。！？!?；;.]+[。！？!?；;.]?/g) || [];
    return sentences
      .flatMap((sentence) => splitLongClause(sentence.trim()))
      .map((sentence) => sentence.trim())
      .filter(hasContent);
  }

  function planRevision(options) {
    const sentences = splitSentences(options.text);
    const confirmedCount = Math.max(0, Number(options.confirmedCount || 0));
    const previousRewrite = Array.isArray(options.previousRewrite) ? options.previousRewrite.filter(Boolean) : [];
    const previousLive = normalizeText(options.previousLive);
    const previousPending = [...previousRewrite, ...(previousLive ? [previousLive] : [])];
    const final = Boolean(options.final);

    if (!sentences.length) {
      return {
        promote: final ? previousPending : [],
        rewrite: final ? [] : previousRewrite,
        live: final ? '' : previousLive,
        sentenceCount: 0,
        regressive: false,
      };
    }

    const remaining = sentences.slice(Math.min(confirmedCount, sentences.length));
    if (final) {
      const promote = remaining.length >= previousPending.length ? remaining : previousPending;
      return { promote, rewrite: [], live: '', sentenceCount: sentences.length, regressive: false };
    }

    if (remaining.length < previousPending.length) {
      return {
        promote: [],
        rewrite: previousRewrite,
        live: previousLive,
        sentenceCount: sentences.length,
        regressive: true,
      };
    }

    const targetConfirmedCount = Math.max(confirmedCount, sentences.length - 2);
    const promote = sentences.slice(confirmedCount, targetConfirmedCount);
    return {
      promote,
      rewrite: sentences.slice(targetConfirmedCount, -1),
      live: sentences[sentences.length - 1] || '',
      sentenceCount: sentences.length,
      regressive: false,
    };
  }

  return { normalizeText, splitSentences, planRevision };
}));
