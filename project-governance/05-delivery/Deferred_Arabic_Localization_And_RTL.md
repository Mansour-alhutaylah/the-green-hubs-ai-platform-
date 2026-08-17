# Deferred — Arabic Localization and Full RTL Acceptance

| Field | Value |
|---|---|
| Document ID | GH-SIP-DEFER-I18N-001 |
| Status | **Deferred to a dedicated post-MVP phase.** Recorded, not scheduled. |
| Decided during | Frontend F2A (core operating pages) |
| Decision date | 2026-08-17 |
| Supersedes | The Arabic/RTL completion and synchronized EN/AR dictionary criteria in the F2A acceptance list |

---

## The decision

The current MVP ships **English only**.

Arabic localization and full right-to-left acceptance are deferred to a dedicated
later phase, because completing *and reviewing* the Arabic product experience now
would materially increase delivery time — and a partially translated interface is
harder to trust than an honest English one.

This is a scope decision, not a reversal. Nothing in the Arabic or RTL foundation
was removed.

## What ships in the MVP

- English is the only selectable and publicly presented language, in both Live and
  Preview.
- Every language selector is **hidden**, not disabled and not shown with a single
  option: the Context Bar toggle and the auth-screen toggle both render `null`
  while one language ships.
- Settings → Language is a statement rather than a control. It names English as the
  current product language and discloses that Arabic is planned for a future
  release.
- Locale resolution **fails closed to English**. A stored `ar` preference — from an
  earlier build, from devtools, or from any other source — resolves to English, and
  the resolved value is what gets persisted.

## What was preserved, deliberately

The point of deferring rather than deleting is that the later phase should be a
translation exercise, not a re-implementation.

| Preserved | Where |
|---|---|
| The Arabic dictionary | `frontend/src/lib/i18n/strings/ar.ts` |
| Locale context, provider, and `dir` handling | `frontend/src/lib/i18n/` |
| Logical CSS properties (`ps-*`, `pe-*`, `start-*`, `end-*`, `border-s/e`) | Throughout the design system and pages |
| Direction-aware primitives (e.g. `Tabs` arrow-key reversal, mirrored icons) | `frontend/src/design-system/` |
| The language toggle components themselves | `LocaleToggle.tsx`, `AuthSplitLayout.tsx` |

The Arabic dictionary is now typed `Partial<Record<StringKey, string>>`, and
`LocaleProvider` falls back to the authoritative English text for any key it does
not carry. That is what allows the later phase to land Arabic **incrementally**
without ever shipping a half-blank screen.

The cost of that choice, stated plainly: it gave up the compile-time completeness
check. What keeps a half-translated interface off the screen today is
`AVAILABLE_LOCALES` excluding `ar` — a *policy* gate, not an enforced parity
check. No test or type currently fails when a key goes untranslated. Restoring an
enforced gate is a prerequisite for re-enabling Arabic, not a nicety; see step 2
below.

No English string was copied into the Arabic dictionary to pad its coverage. An
untranslated key is absent, and absence renders as visibly English.

## The gate for re-enabling Arabic

Adding `'ar'` to `AVAILABLE_LOCALES` in `frontend/src/lib/i18n/availability.ts` is
the **last** step, not the only one. An earlier draft of this document described it
as the only code change required; that was inaccurate and is corrected here.

Restoring the selector, the `dir` switch, and RTL layout requires **all four** of
the following, in order:

1. **Complete Arabic translations for every active key**, including every key F2A
   added — reviewed, not machine-translated, and never English text wearing an
   Arabic label.
2. **Restore the locale completeness gate.** Typing `ar` as
   `Partial<Record<StringKey, string>>` removed the compile-time check that
   previously made a missing translation a build error; a missing key now falls
   back silently to English. Either restore the exhaustive
   `Record<StringKey, string>` type or add a test asserting EN/AR key parity.
   Until one of these exists, nothing fails when a new key goes untranslated.
3. **Add `'ar'` to `AVAILABLE_LOCALES`.**
4. **Real-browser RTL visual QA** across every supported route at 360px, 768px,
   and 1280px. jsdom performs no layout and cannot substitute for this step.

Alongside these, the standing quality bars still apply: Arabic copy passes the same
voice review as the English source (institutional, declarative, no exclamation
marks), and the RTL acceptance tests removed from the F2A criteria are reinstated
in full.

**Known gap as of F2A:** `ar.ts` is already missing four keys —
`settings.language.current`, `settings.language.onlyOption`,
`settings.language.future.title`, and `settings.language.future.description` —
all introduced by the English-only decision itself. Enabling Arabic today would
render a mixed Arabic/English Settings → Language section. This is harmless while
`AVAILABLE_LOCALES` excludes `ar`, and is exactly what step 2 exists to catch.

## Acceptance criteria for the future phase

- Full EN/AR dictionary parity, enforced by a test.
- RTL rendering verified per route at 360px, 768px, and 1280px.
- Direction-aware behaviour verified for tabs, pagination, breadcrumbs, icons that
  encode direction, and every form control.
- Numeric and timestamp values remain LTR inside RTL text (already implemented via
  `dir="ltr"` on figures and `<time>` elements).
- A language preference that survives a reload, with the storage/account
  distinction stated truthfully wherever it is presented.

---

*Recorded during F2A. The MVP's English-only behaviour is covered by
`frontend/src/lib/i18n/__tests__/MvpLanguage.test.tsx`.*
