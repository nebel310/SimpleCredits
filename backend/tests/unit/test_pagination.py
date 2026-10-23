import base64

import pytest

from utils.pagination import decode_cursor, encode_cursor


def test_encode_cursor_positive():
    """Кодирует положительное число в base64 строку"""
    assert encode_cursor(123) == base64.b64encode(b"123").decode()


def test_encode_cursor_zero():
    """Кодирует ноль"""
    assert encode_cursor(0) == base64.b64encode(b"0").decode()


def test_encode_cursor_large():
    """Кодирует очень большое число"""
    assert base64.b64decode(encode_cursor(10**20)).decode() == str(10**20)


def test_decode_cursor_valid():
    """Декодирует корректный курсор"""
    assert decode_cursor(base64.b64encode(b"456").decode()) == 456


def test_decode_cursor_roundtrip():
    """encode и decode взаимно обратны"""
    assert decode_cursor(encode_cursor(789)) == 789


def test_decode_cursor_invalid_base64():
    """Возвращает None для невалидного base64"""
    assert decode_cursor("!!!not_base64!!!") is None


def test_decode_cursor_not_an_int():
    """Возвращает None если base64 содержит не число"""
    assert decode_cursor(base64.b64encode(b"not-a-number").decode()) is None


def test_decode_cursor_empty_string():
    """Возвращает None для пустой строки"""
    assert decode_cursor("") is None