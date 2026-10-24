from unittest.mock import AsyncMock, MagicMock

import pytest

from services.ws_manager import WSManager


def make_ws():
    """Возвращает мок WebSocket с async accept/send_json"""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


async def test_connect_accepts_and_stores():
    """connect вызывает accept и сохраняет соединение"""
    manager = WSManager()
    ws = make_ws()

    await manager.connect(1, ws)

    ws.accept.assert_awaited_once()
    assert manager.has_connections(1)


async def test_connect_multiple_same_user():
    """Несколько соединений одного пользователя"""
    manager = WSManager()
    ws1, ws2 = make_ws(), make_ws()

    await manager.connect(1, ws1)
    await manager.connect(1, ws2)

    assert manager.has_connections(1)


async def test_connect_different_users():
    """Разные пользователи — независимые списки"""
    manager = WSManager()
    ws1, ws2 = make_ws(), make_ws()

    await manager.connect(1, ws1)
    await manager.connect(2, ws2)

    assert manager.has_connections(1)
    assert manager.has_connections(2)


def test_has_connections_empty():
    """Пустой менеджер"""
    manager = WSManager()
    assert not manager.has_connections(1)


async def test_disconnect_removes_single():
    """disconnect убирает соединение из реестра"""
    manager = WSManager()
    ws = make_ws()
    await manager.connect(1, ws)

    manager.disconnect(1, ws)
    assert not manager.has_connections(1)


def test_disconnect_unknown_user_noop():
    """disconnect для неизвестного user_id не падает"""
    manager = WSManager()
    manager.disconnect(1, make_ws())


async def test_disconnect_unknown_ws_noop():
    """disconnect для неизвестного ws не падает"""
    manager = WSManager()
    ws = make_ws()
    await manager.connect(1, ws)

    manager.disconnect(1, make_ws())
    assert manager.has_connections(1)


async def test_disconnect_keeps_other_connections():
    """После disconnect одного соединения остаётся второе"""
    manager = WSManager()
    ws1, ws2 = make_ws(), make_ws()

    await manager.connect(1, ws1)
    await manager.connect(1, ws2)
    manager.disconnect(1, ws1)

    assert manager.has_connections(1)


async def test_broadcast_no_connections():
    """broadcast без соединений — no-op"""
    manager = WSManager()
    await manager.broadcast(1, {"type": "test"})


async def test_broadcast_single():
    """broadcast отправляет сообщение в единственное соединение"""
    manager = WSManager()
    ws = make_ws()
    await manager.connect(1, ws)

    await manager.broadcast(1, {"type": "status_changed", "status": "confirmed"})

    ws.send_json.assert_awaited_once_with(
        {"type": "status_changed", "status": "confirmed"}
    )


async def test_broadcast_multiple():
    """broadcast отправляет во все соединения пользователя"""
    manager = WSManager()
    ws1, ws2 = make_ws(), make_ws()
    await manager.connect(1, ws1)
    await manager.connect(1, ws2)

    await manager.broadcast(1, {"type": "event"})

    ws1.send_json.assert_awaited_once()
    ws2.send_json.assert_awaited_once()


async def test_broadcast_to_other_user_noop():
    """broadcast в чужой user_id не задевает соединения других"""
    manager = WSManager()
    ws1 = make_ws()
    await manager.connect(1, ws1)

    await manager.broadcast(2, {"type": "event"})

    ws1.send_json.assert_not_awaited()


async def test_broadcast_removes_broken_connection():
    """send_json с ошибкой → соединение отписывается"""
    manager = WSManager()
    ws1 = make_ws()
    ws1.send_json = AsyncMock(side_effect=RuntimeError("broken"))
    ws2 = make_ws()

    await manager.connect(1, ws1)
    await manager.connect(1, ws2)
    await manager.broadcast(1, {"type": "event"})

    assert manager.has_connections(1)
    ws2.send_json.assert_awaited_once()


async def test_broadcast_removes_broken_last_connection():
    """send_json с ошибкой и единственное соединение → user удалён"""
    manager = WSManager()
    ws = make_ws()
    ws.send_json = AsyncMock(side_effect=RuntimeError("broken"))

    await manager.connect(1, ws)
    await manager.broadcast(1, {"type": "event"})

    assert not manager.has_connections(1)


async def test_clear():
    """clear сбрасывает реестр"""
    manager = WSManager()
    ws = make_ws()
    await manager.connect(1, ws)

    manager.clear()
    assert not manager.has_connections(1)