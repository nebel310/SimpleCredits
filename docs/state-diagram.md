# Статусы заявки

```mermaid
stateDiagram-v2
  [*] --> DRAFT
  DRAFT --> SUBMITTED: владелец отправил
  DRAFT --> CANCELLED: отозвал
  SUBMITTED --> CHECKS
  CHECKS --> WAITING_SOURCE: источник TIMEOUT/ERROR
  WAITING_SOURCE --> CHECKS: повтор успешен
  CHECKS --> SCORING: все источники ответили

  state "Развилка после оценки" as fork
  SCORING --> fork
  fork --> OFFER: APPROVE / COUNTER_OFFER (авто)
  fork --> DOCS_REQUESTED: REQUEST_DOCS (не хватает данных)
  fork --> MANUAL_REVIEW: MANUAL_REVIEW (категория C/D, сумма выше лимита, комплаенс)
  fork --> DECLINED: DECLINE (стоп-фактор)

  MANUAL_REVIEW --> SCORING: комплаенс снял совпадение
  MANUAL_REVIEW --> OFFER: андеррайтер / комитет одобрил или предложил другие условия
  MANUAL_REVIEW --> DOCS_REQUESTED: андеррайтер или менеджер запросил документы
  MANUAL_REVIEW --> DECLINED: отказ с причинами

  DOCS_REQUESTED --> DOCS_REVIEW: клиент отправил документы
  DOCS_REVIEW --> DOCS_REQUESTED: документ возвращён на исправление
  DOCS_REVIEW --> SCORING: документы приняты → новый раунд, пересчёт

  OFFER --> SIGNING: клиент принял (offerId + version)
  OFFER --> OFFER_REJECTED: клиент отказался
  OFFER --> EXPIRED: срок предложения истёк

  SIGNING --> SIGNING: ошибка подписи → повтор
  SIGNING --> DISBURSEMENT: договор подписан
  DISBURSEMENT --> DISBURSEMENT: АБС не ответила → сверяем операцию, без повторной выдачи
  DISBURSEMENT --> ACTIVE: выдача подтверждена
  ACTIVE --> REPAID: погашен

  SUBMITTED --> CANCELLED
  CHECKS --> CANCELLED
  MANUAL_REVIEW --> CANCELLED
  DOCS_REQUESTED --> CANCELLED
```

`REQUEST_DOCS`, `MANUAL_REVIEW` и `WAITING_SOURCE` — промежуточные состояния, не отказ. Клиент видит их как «Нужен документ», «Дополнительная проверка» и «Ждём источник» без риск-балла.

Трекер клиента (6 этапов): Отправлена → Проверка данных → Оценка → Решение → Подписание → Выдача.
