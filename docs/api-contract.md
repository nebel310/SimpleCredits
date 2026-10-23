# Контракт API для бэкенда

Типы запросов и ответов — в `src/api/types.ts`, интерфейс — в `src/api/client.ts`, HTTP-реализация — в `src/api/http.ts`. Базовый путь `VITE_API_URL` (по умолчанию `/api`).

## Общие правила

- Пользователь демо-входа передаётся заголовком `X-Demo-User: <userId>`. Роль и компанию сервер определяет сам.
- Действия, которые нельзя выполнить дважды, приходят с заголовком `Idempotency-Key`. Повтор с тем же ключом возвращает текущее состояние без второго действия.
- Ответ на любое действие с заявкой — полный `ApplicationView` (заявка, отфильтрованная по роли, плюс `permissions`).
- Ошибка: HTTP 4xx/5xx и тело `{ "code": string, "message": string, "retryable": boolean }`. `message` показывается пользователю как есть, поэтому пишется простыми словами.
- Клиенту не отдаются: `scoring` (балл, категория, версия правил), `internalComment`, `assignee`, события без текста для клиента. Вместо скоринга — `afford: { cashFlow, currentPayments }` для «запаса прочности».
- Наблюдателю не отдаются файлы и поля документов.
- Чувствительные данные (`sensitive`) маскируются: полностью видят андеррайтер и комплаенс.

## Эндпоинты

| Метод | Путь | Тело | Ответ | Кто |
|---|---|---|---|---|
| GET | `/demo/accounts` | — | `DemoAccounts` | все |
| GET | `/me` | — | `User` | все |
| GET | `/products` | — | `Product[]` | все |
| GET | `/companies/:id` | — | `Company` | клиент своей компании, банк |
| GET | `/companies/:id/chances?refresh=1` | — | `ChancesResult` (`state`: ready, insufficient, error) | клиент |
| POST | `/companies/:id/consents/bki` | — | 204 | владелец |
| GET | `/applications` | — | `ApplicationSummary[]` | клиент |
| GET | `/applications/:id` | — | `ApplicationView` | клиент своей компании, банк |
| POST | `/applications` | `DraftInput` | `ApplicationView` (черновик; один на компанию) | владелец, бухгалтер |
| PATCH | `/applications/:id` | `Partial<DraftInput> & { finance?, delegatedToAccountant? }` | `ApplicationView` | владелец, бухгалтер; только DRAFT |
| POST | `/applications/:id/company/lookup` | `{ inn }` | `LookupResult` (`found`, `not_found`, `unavailable`, `invalid`) | клиент |
| POST | `/applications/:id/company/confirm` | `{ how: 'registry' \| 'manual', note? }` | `ApplicationView` | клиент |
| POST | `/applications/:id/statement` | `FileInput` (в проде multipart) | `ApplicationView` (`statement.status = extracting`) | клиент |
| POST | `/applications/:id/statement/confirm` | `{ fields: ExtractedField[] }` | `ApplicationView` | клиент |
| DELETE | `/applications/:id/statement` | — | `ApplicationView` | клиент |
| POST | `/applications/:id/consents` | — | `ApplicationView` | владелец |
| POST | `/applications/:id/submit` | — + `Idempotency-Key` | `ApplicationView` | владелец |
| POST | `/applications/:id/cancel` | — + `Idempotency-Key` | `ApplicationView` | владелец, до решения |
| POST | `/applications/:id/documents/:docId/file` | `FileInput` | `ApplicationView` | владелец, бухгалтер |
| POST | `/applications/:id/documents/:docId/confirm` | `{ fields }` | `ApplicationView` | владелец, бухгалтер |
| POST | `/applications/:id/documents/:docId/answer` | `{ answer }` | `ApplicationView` | владелец, бухгалтер |
| POST | `/applications/:id/documents/send` | — + `Idempotency-Key` | `ApplicationView` (→ DOCS_REVIEW) | владелец, бухгалтер |
| POST | `/applications/:id/offer/accept` | `{ offerId, version }` + `Idempotency-Key` | `ApplicationView` (→ SIGNING) | владелец |
| POST | `/applications/:id/offer/reject` | `{ offerId }` + `Idempotency-Key` | `ApplicationView` | владелец |
| POST | `/applications/:id/sign` | — + `Idempotency-Key` | `ApplicationView` (`signing.status = signing`) | владелец |
| GET | `/bank/tasks` | — | `BankTask[]` (`actionable` — для роли текущего пользователя) | банк |
| GET | `/bank/applications` | — | `ApplicationSummary[]` | банк |
| POST | `/bank/applications/:id/take` | — + `Idempotency-Key` | `ApplicationView` (запись в журнал) | роль задачи |
| POST | `/bank/applications/:id/document-requests` | `DocRequestInput` + `Idempotency-Key` | `ApplicationView` (→ DOCS_REQUESTED) | менеджер, андеррайтер |
| POST | `/bank/applications/:id/documents/:docId/review` | `{ verdict: 'accept' \| 'reject', reason }` | `ApplicationView` (все приняты → новый раунд, SCORING) | менеджер, взявший задачу |
| POST | `/bank/applications/:id/compliance` | `{ verdict: 'clear' \| 'confirmed', comment }` | `ApplicationView` | комплаенс |
| POST | `/bank/applications/:id/escalate` | — | `ApplicationView` (кредитный комитет) | андеррайтер |
| POST | `/bank/applications/:id/decision` | `DecisionInput` + `Idempotency-Key` | `ApplicationView` | андеррайтер, взявший задачу |
| POST | `/bank/applications/:id/checks/rerun` | — | `ApplicationView` | менеджер, андеррайтер |
| POST | `/bank/applications/:id/decision/draft-text` | `{ outcome, reasons, amount }` | `{ text }` | андеррайтер |
| POST | `/ai/ask` | `{ ctx: AiContext, question }` | `AiAnswer` | все |
| GET | `/demo/sources` | — | `SourceState[]` (с `affected`) | демо |
| PATCH | `/demo/sources/:id` | `{ enabled?, mode? }` | `SourceState[]` | демо |
| GET | `/demo/log` | — | `SimLogEntry[]` | демо |
| POST | `/demo/scenarios/:name` | — | `{ applicationId }` | демо |
| POST | `/demo/reset` | — | 204 | демо |

`question = "__steps__"` в `/ai/ask` — режим «что делать дальше».

## Проверки на сервере для решения андеррайтера

- Статус `MANUAL_REVIEW`, заявка взята этим пользователем, комплаенс закрыт, все внешние проверки ответили.
- Одно решение на раунд рассмотрения (`round`). Новое — только после новых данных.
- Для одобрения и встречного: сумма и срок в границах продукта, DSCR ≥ 1,3, сумма ≤ лимита полномочий или заявка на кредитном комитете.
- Для запроса документов: что нужно, зачем, срок. Для отказа: хотя бы одна причина из справочника `REASON_CATALOG`.
- `aiTextChecked = true` — сотрудник подтвердил текст для клиента. ИИ не меняет исход и условия.

## Обновления

Сейчас HTTP-клиент опрашивает данные раз в 3 секунды. Для мгновенного обновления можно добавить SSE `GET /events?applicationId=…` — фронтенд перечитает данные по событию.
