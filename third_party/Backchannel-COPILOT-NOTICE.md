Backchannel adapted code notice
===============================

Upstream: https://github.com/talberthoule/backchannel
Immutable SHA: 16028a55dbbf886b68eaddc06dfd7c38b72de596
License: MIT

Adapted files:
- backend/app/services/live_chat_context.py
- backend/app/services/file_parsing.py (text/Markdown/DOCX helpers; upstream has no PDF parser)

Speakr changes:
- Pure-Python bounded context assembly, retaining the tail of recent transcription.
- Deterministic lexical retrieval with Chinese/unicode token handling.
- Host-specific PDF parsing and upload/ZIP expansion limits, explicit over-limit rejection.
- No Backchannel database, ORM, audio, PII or agent-stack dependencies.
- Chinese-first prompt framing; retrieved context is not a verified external citation.

This is host integration code for Speakr, not an iframe wrapper or a full Backchannel app import.

Full upstream LICENSE (retained verbatim):

MIT License

Copyright (c) 2026 Talbert Houle

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
