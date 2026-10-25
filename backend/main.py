import os

import uvicorn

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from database import create_tables
from database import delete_tables
from minio.client import s3_client
from ml_grpc.client import ScoringClient
from repositories.applications import ApplicationRepository
from repositories.auth import UserRepository
from repositories.products import ProductRepository
from router.applications import router as applications_router
from router.auth import router as auth_router
from router.files import router as file_router
from router.mock import router as mock_router
from router.products import router as products_router
from router.scoring import router as scoring_router
from router.ws import router as ws_router
from router.admin import router as admin_router




@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    await create_tables()
    print("База готова к работе")

    await s3_client.ensure_bucket()
    print(f"Бакет {s3_client.bucket_name} создан")

    await ProductRepository.ensure_products()
    print("Продукты загружены")

    backfilled = await ApplicationRepository.backfill_outcomes()
    if backfilled:
        print(f"Тип результата проставлен старым заявкам: {backfilled}")

    await UserRepository.ensure_admin(
        email=os.getenv("ADMIN_EMAIL", "admin@example.com"),
        password=os.getenv("ADMIN_PASSWORD", "admin123"),
        username=os.getenv("ADMIN_USERNAME", "admin"),
    )
    print("Администратор готов")

    scoring_client = ScoringClient(
        host=os.getenv("ML_GRPC_HOST", "ml"),
        port=int(os.getenv("ML_GRPC_PORT", "50051")),
        timeout=float(os.getenv("ML_GRPC_TIMEOUT", "10.0")),
    )
    await scoring_client.start()
    app.state.scoring_client = scoring_client
    print(f"gRPC-клиент подключён к {scoring_client.host}:{scoring_client.port}")

    yield

    await scoring_client.close()
    print("Выключение")


def custom_openapi():
    """Кастомная OpenAPI схема с настройками безопасности."""
    if app.openapi_schema:
        return app.openapi_schema
        
    openapi_schema = get_openapi(
        title="FastAPI REST API FOR ALFA HACK",
        version="1.0.0",
        description="""API для кредитной платформы""",
        routes=app.routes,
    )
    
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    
    secured_paths = {
        ("/auth/me", "get"): [{"Bearer": []}],
        ("/auth/me", "patch"): [{"Bearer": []}],
        ("/auth/logout", "post"): [{"Bearer": []}],
        ("/auth/users", "get"): [{"Bearer": []}],
        ("/files/", "post"): [{"Bearer": []}],
        ("/files/{file_id}", "get"): [{"Bearer": []}],
        ("/files/{file_id}/info", "get"): [{"Bearer": []}],
        ("/files/{file_id}", "delete"): [{"Bearer": []}],
        ("/applications", "post"): [{"Bearer": []}],
        ("/applications", "get"): [{"Bearer": []}],
        ("/applications/{application_id}", "get"): [{"Bearer": []}],
        ("/applications/{application_id}/events", "get"): [{"Bearer": []}],
        ("/applications/{application_id}/accept", "post"): [{"Bearer": []}],
        ("/applications/{application_id}/issue", "post"): [{"Bearer": []}],
        ("/applications/{application_id}/reject", "post"): [{"Bearer": []}],
        ("/scoring/batch", "post"): [{"Bearer": []}],
        ("/scoring/model-info", "get"): [{"Bearer": []}],
        ("/admin/applications", "get"): [{"Bearer": []}],
        ("/admin/stats/overview", "get"): [{"Bearer": []}],
        ("/admin/applications/{application_id}/decision", "post"): [{"Bearer": []}],
    }
    
    for (path, method), security in secured_paths.items():
        if path in openapi_schema["paths"] and method in openapi_schema["paths"][path]:
            openapi_schema["paths"][path][method]["security"] = security
    
    app.openapi_schema = openapi_schema
    
    return app.openapi_schema


app = FastAPI(lifespan=lifespan)
app.openapi = custom_openapi


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(file_router)
app.include_router(scoring_router)
app.include_router(products_router)
app.include_router(mock_router)
app.include_router(applications_router)
app.include_router(ws_router)
app.include_router(admin_router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        reload=True,
        port=3001,
        host="0.0.0.0"
    )