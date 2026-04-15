# Phase 47e — Bilingual user language (KO/EN)

- **Phase**: `phase47e_bilingual_user_language`
- **Generated**: `2026-04-14T06:15:51.370890+00:00`
- **Design source**: `/Users/hyunminkim/GenAIProacTrade/docs/DESIGN_V3_MINIMAL_AND_STRONG.md`

## Runtime

- `GET /api/home/feed?lang=ko|en` — localized Home blocks.
- `GET /api/overview?lang=` — `user_first` brief + navigation.
- `GET /api/user-first/section/{id}?lang=` — localized section payloads.
- `GET /api/runtime/health?lang=` — localized health card.
- `GET /api/locale?lang=` — flat string map for static shell (`data-i18n`).

## Supported languages

`['ko', 'en']`

## String counts (flat locale export)

```json
{
  "ko": 118,
  "en": 118
}
```

## Phase 47f recommendation (from core)

```json
{
  "phase47f_recommendation": "per_asset_narrative_strip_and_digest_reading_modes_v1",
  "focus": "Per-asset story strip on Home, optional “plain / standard / deep” reading depth for long research objects — still governed, no substrate expansion."
}
```
