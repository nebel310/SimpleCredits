import base64




def encode_cursor(value: int) -> str:
    """Кодирует целое число в строку курсора (base64)."""
    return base64.b64encode(str(value).encode()).decode()

def decode_cursor(token: str) -> int | None:
    """Декодирует строку курсора обратно в int. При ошибке None."""
    try:
        return int(base64.b64decode(token.encode()).decode())
    except (ValueError, TypeError):
        return None