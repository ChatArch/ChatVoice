"""Limit audio request bodies before multipart parsing, including chunked bodies."""
from __future__ import annotations

import re
from collections.abc import Callable

from fastapi import HTTPException
from fastapi.responses import JSONResponse


class AudioUploadLimits:
    def __init__(self, app, *, limit_for_path: Callable[[str], int]):
        self.app = app
        self.limit_for_path = limit_for_path

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        if scope['type'] != 'http' or scope.get('method') != 'POST' or not (
            path == '/api/asr' or re.fullmatch(r'/api/meetings/[^/]+/(?:audio|import)', path)
        ):
            await self.app(scope, receive, send)
            return
        limit = self.limit_for_path(path)
        raw_length = dict(scope.get('headers', [])).get(b'content-length')
        if raw_length is not None:
            try:
                length = int(raw_length)
                if length < 0:
                    raise ValueError
            except ValueError:
                await JSONResponse({'detail': '无效的上传长度'}, status_code=400)(scope, receive, send)
                return
            if length > limit:
                await JSONResponse({'detail': '音频上传超过应用大小限制'}, status_code=413)(scope, receive, send)
                return
        received = 0
        async def bounded_receive():
            nonlocal received
            message = await receive()
            if message['type'] == 'http.request':
                received += len(message.get('body', b''))
                if received > limit:
                    raise HTTPException(status_code=413, detail='音频上传超过应用大小限制')
            return message
        await self.app(scope, bounded_receive, send)
