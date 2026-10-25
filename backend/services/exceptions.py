class EnrichmentError(Exception):
    """Ошибка обогащения данных через мок-госуслуги"""

    def __init__(self, message: str, source: str | None = None):
        super().__init__(message)
        self.message = message
        self.source = source


class EnrichmentError(Exception):
    """Ошибка обогащения данных через мок-госуслуги"""

    def __init__(self, message: str, source: str | None = None):
        super().__init__(message)
        self.message = message
        self.source = source


class ProfileIncompleteError(Exception):
    """Профиль компании не заполнен и данных в теле заявки недостаточно"""


class ManualDecisionNotAllowedError(Exception):
    """Ручное решение доступно только для заявки из серой зоны"""
