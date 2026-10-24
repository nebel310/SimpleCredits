# Статусы заявки

По `USERFLOW.md` §5 и `backend/services/scoring.py`.

```mermaid
stateDiagram-v2
  [*] --> pending: POST /applications
  pending --> pending: enriched (ЕГРЮЛ, ФНС, БКИ)
  pending --> confirmed: approve и продукт выбран
  pending --> different: approve без продукта
  pending --> different: approve_with_conditions
  pending --> different: manual_review
  pending --> declined: decline
  pending --> failed: ошибка ML, сети или обогащения
  confirmed --> [*]
  different --> [*]
  declined --> [*]
  failed --> [*]
```

`different` — не отказ: банк одобряет на других условиях, подобрал продукт сам или заявке нужна ручная проверка. Какой именно случай, фронтенд определяет по `scoring_result.decision.decision`.

События заявки (`GET /applications/{id}/events`): `created` → `enriched` → `scored` → `status_changed` (или `failed`). По ним строится трекер: «Заявка создана → ЕГРЮЛ, ФНС, БКИ → Скоринг → Решение».

Дальнейших этапов (подписание, выдача, сопровождение) в MVP нет — путь заканчивается на статусе.
