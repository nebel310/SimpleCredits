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


class ProductMismatchError(Exception):
    """Выбранный клиентом продукт не подходит под заявку или недоступен"""

    def __init__(self, product_name: str, reasons: list[str]):
        self.product_name = product_name
        self.reasons = reasons
        super().__init__(f"Продукт «{product_name}» не подходит: " + "; ".join(reasons))
