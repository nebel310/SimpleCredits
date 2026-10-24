from fastapi import APIRouter, HTTPException

from repositories.products import ProductRepository
from schemas.base import ErrorResponse
from schemas.products import SProductListResponse, SProductResponse


router = APIRouter(prefix="/products", tags=["Продукты"])


@router.get(
    "",
    response_model=SProductListResponse,
    responses={500: {"model": ErrorResponse}},
)
async def list_products():
    """Возвращает каталог активных кредитных продуктов"""
    products = await ProductRepository.list_active()
    return SProductListResponse(
        products=[SProductResponse.model_validate(p) for p in products]
    )


@router.get(
    "/{code}",
    response_model=SProductResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def get_product(code: str):
    """Возвращает детали продукта по его slug-коду"""
    product = await ProductRepository.get_by_code(code)
    if not product:
        raise HTTPException(status_code=404, detail="Продукт не найден")
    return SProductResponse.model_validate(product)