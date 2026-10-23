class GrpcServiceError(Exception):
    """Базовая ошибка вызова ML-сервиса"""
    pass


class GrpcUnavailableError(GrpcServiceError):
    """ML-сервис недоступен"""
    pass


class GrpcInvalidArgumentError(GrpcServiceError):
    """ML-сервис отклонил запрос как некорректный"""
    pass


class GrpcDeadlineExceededError(GrpcServiceError):
    """Вызов ML-сервиса не уложился в таймаут"""
    pass