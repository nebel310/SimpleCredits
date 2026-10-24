from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from starlette.websockets import WebSocketState

from repositories.auth import UserRepository
from utils.security import ALGORITHM, SECRET_KEY
from services.ws_manager import ws_manager


router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/applications")
async def ws_applications(websocket: WebSocket, token: str = Query(...)):
    """Канал обновлений статусов заявок пользователя"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise JWTError("no sub")
    except JWTError:
        await websocket.accept()
        await websocket.close(code=4401)
        return

    user = await UserRepository.get_user_by_email(email)
    if user is None:
        await websocket.accept()
        await websocket.close(code=4401)
        return

    await ws_manager.connect(user.id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(user.id, websocket)
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            ws_manager.disconnect(user.id, websocket)