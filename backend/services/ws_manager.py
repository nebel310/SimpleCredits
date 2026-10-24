from fastapi import WebSocket


class WSManager:
    """Реестр WebSocket-соединений по user_id"""

    def __init__(self):
        self._connections: dict[int, list[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        """Принимает соединение и добавляет его в реестр"""
        await websocket.accept()
        self._connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        """Удаляет соединение из реестра"""
        if user_id not in self._connections:
            return
        self._connections[user_id] = [
            ws for ws in self._connections[user_id] if ws is not websocket
        ]
        if not self._connections[user_id]:
            del self._connections[user_id]

    async def broadcast(self, user_id: int, message: dict) -> None:
        """Рассылает сообщение во все соединения пользователя"""
        for ws in list(self._connections.get(user_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(user_id, ws)

    def has_connections(self, user_id: int) -> bool:
        """Проверяет есть ли у пользователя активные соединения"""
        return bool(self._connections.get(user_id))

    def clear(self) -> None:
        """Сбрасывает реестр (для тестов)"""
        self._connections.clear()


ws_manager = WSManager()