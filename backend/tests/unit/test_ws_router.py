from unittest.mock import AsyncMock, MagicMock

from fastapi import WebSocket

from router.ws import ws_applications


def make_ws():
    """Возвращает мок WebSocket с async close/accept"""
    ws = MagicMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.receive_text = AsyncMock()
    return ws


async def test_ws_invalid_token_closes_4401():
    """Невалидный JWT → accept + close(4401)"""
    ws = make_ws()
    await ws_applications(ws, token="invalid-token")

    ws.accept.assert_awaited_once()
    ws.close.assert_awaited_once_with(code=4401)


async def test_ws_empty_token_closes_4401():
    """Пустой токен → accept + close(4401)"""
    ws = make_ws()
    await ws_applications(ws, token="")
    ws.accept.assert_awaited_once()
    ws.close.assert_awaited_once_with(code=4401)


async def test_ws_token_without_sub_closes_4401():
    """JWT без sub → accept + close(4401)"""
    from jose import jwt
    from utils.security import ALGORITHM, SECRET_KEY

    token = jwt.encode({"other": "field"}, SECRET_KEY, algorithm=ALGORITHM)
    ws = make_ws()
    await ws_applications(ws, token=token)
    ws.accept.assert_awaited_once()
    ws.close.assert_awaited_once_with(code=4401)