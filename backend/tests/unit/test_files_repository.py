import magic
import pytest

from repositories.files import FileRepository


def test_get_content_type_returns_mime(monkeypatch):
    """Возвращает MIME-тип из magic"""
    monkeypatch.setattr(
        "repositories.files.magic.from_buffer",
        lambda data, mime=False: "image/png",
    )
    assert FileRepository._get_content_type(b"data") == "image/png"


def test_get_content_type_passes_mime_true(monkeypatch):
    """Передаёт mime=True в magic.from_buffer"""
    captured = {}

    def fake_from_buffer(data, mime=False):
        captured["data"] = data
        captured["mime"] = mime
        return "application/pdf"

    monkeypatch.setattr("repositories.files.magic.from_buffer", fake_from_buffer)
    FileRepository._get_content_type(b"test bytes")
    assert captured["mime"] is True
    assert captured["data"] == b"test bytes"


def test_get_content_type_magic_error(monkeypatch):
    """Кидает ValueError при ошибке magic"""

    def raise_error(data, mime=False):
        raise magic.MagicException("boom")

    monkeypatch.setattr("repositories.files.magic.from_buffer", raise_error)
    with pytest.raises(ValueError, match="MIME"):
        FileRepository._get_content_type(b"x")


def test_get_extension_png(monkeypatch):
    """Возвращает png для image/png"""
    monkeypatch.setattr(
        FileRepository, "_get_content_type", staticmethod(lambda b: "image/png")
    )
    assert FileRepository._get_extension(b"x") == "png"


def test_get_extension_corrects_jpe_to_jpg(monkeypatch):
    """Корректирует jpe в jpg"""
    monkeypatch.setattr(
        FileRepository, "_get_content_type", staticmethod(lambda b: "image/jpeg")
    )
    monkeypatch.setattr(
        "repositories.files.mimetypes.guess_extension", lambda mime: ".jpe"
    )
    assert FileRepository._get_extension(b"x") == "jpg"


def test_get_extension_corrects_svg_xml(monkeypatch):
    """Корректирует svg+xml в svg"""
    monkeypatch.setattr(
        FileRepository, "_get_content_type", staticmethod(lambda b: "image/svg+xml")
    )
    monkeypatch.setattr(
        "repositories.files.mimetypes.guess_extension", lambda mime: ".svg+xml"
    )
    assert FileRepository._get_extension(b"x") == "svg"


def test_get_extension_fallback_uses_subtype(monkeypatch):
    """Берёт подтип mime как расширение при неудаче guess_extension"""
    monkeypatch.setattr(
        FileRepository,
        "_get_content_type",
        staticmethod(lambda b: "application/x-nonexistent-12345"),
    )
    monkeypatch.setattr(
        "repositories.files.mimetypes.guess_extension", lambda mime: None
    )
    assert FileRepository._get_extension(b"x") == "x-nonexistent-12345"


def test_get_extension_fallback_corrects_quicktime(monkeypatch):
    """Заменяет quicktime на mov в fallback"""
    monkeypatch.setattr(
        FileRepository, "_get_content_type", staticmethod(lambda b: "video/quicktime")
    )
    monkeypatch.setattr(
        "repositories.files.mimetypes.guess_extension", lambda mime: None
    )
    assert FileRepository._get_extension(b"x") == "mov"