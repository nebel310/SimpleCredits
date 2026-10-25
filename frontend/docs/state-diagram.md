# Статусы заявки

По `USERFLOW.md` §5 и `backend/services/`.

```mermaid
stateDiagram-v2
  [*] --> pending: POST /applications
  pending --> pending: enriched (ЕГРЮЛ, ФНС, БКИ)
  pending --> confirmed: approve, продукт выбрал клиент
  pending --> different: ALTERNATIVE_PRODUCT / COUNTER_OFFER / MANUAL_REVIEW
  pending --> declined: decline или нет подходящего продукта
  pending --> failed: ошибка ML, сети или обогащения
  failed --> pending: retry
  different --> confirmed: решение банка — одобрить
  different --> different: решение банка — другая сумма
  different --> declined: решение банка — отказать
  confirmed --> accepted: accept
  different --> accepted: accept (кроме MANUAL_REVIEW)
  accepted --> issued: issue — модельный договор
  confirmed --> rejected_by_client: reject
  different --> rejected_by_client: reject (кроме MANUAL_REVIEW)
  accepted --> rejected_by_client: reject
  issued --> [*]
  declined --> [*]
  rejected_by_client --> [*]
```

`different` — не отказ, его уточняет `outcome`:

- `ALTERNATIVE_PRODUCT` — банк предлагает другой продукт или подобрал продукт сам (клиент не выбирал);
- `COUNTER_OFFER` — тот же продукт на другую сумму;
- `MANUAL_REVIEW` — заявку смотрит сотрудник банка. Это не оффер: принять нечего, пока банк не решит.

События заявки (`GET /applications/{id}/events`): `created` → `enriched` → `scored` → `status_changed` (или `failed`), затем `retry_started`, `bank_decision`, `offer_accepted`, `issued`, `offer_rejected`. По ним строится трекер: «Заявка отправлена → Данные получены → Оценка завершена → Решение готово → Предложение принято → Кредит выдан».

Выдача модельная: номер договора и запись в журнале, реальных проводок и документооборота нет.
