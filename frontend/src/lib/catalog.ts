import { api, type Product, type ProductType } from '../api';
import { PRODUCT_TYPE_NAME } from './labels';

// Каталог продуктов меняется редко — загружаем один раз на вкладку
let cache: Promise<Product[]> | null = null;

export function loadProducts(): Promise<Product[]> {
  if (!cache) {
    cache = api.products().catch((e) => {
      cache = null;
      throw e;
    });
  }
  return cache;
}

export const productByType = (list: Product[] | undefined, t: ProductType) => list?.find((p) => p.product_type === t);
export const productName = (list: Product[] | undefined, t: ProductType) => productByType(list, t)?.name ?? PRODUCT_TYPE_NAME[t];
