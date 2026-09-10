---
appendix: data-rights-conventions
appendix_version: 1.0.0
title: Data-rights conventions
scope: global — startup entitlement assertions; referenced by the §S6/T5 Data rights row
---

# Appendix J — Data-rights conventions

Data rights are stated as **startup assertions**: what we assert we are
entitled to do with each dataset at company formation, and what must be
re-checked before scale-up. Every module's §S6/§T5 carries a Data rights row
per dataset; the row references this appendix rather than re-explaining the
convention.

## J.1 Startup entitlement assertions (the five assertions)

For each dataset in `§0.datasets`, the chapter asserts:

1. **License scope:** the vendor product/license tier named in `§0` covers the
   declared use (research + the stated production symbol count). Quote the
   product name, not the price page.
2. **Redistribution boundary:** raw vendor data never leaves our systems; only
   derived features and aggregates are stored in fixtures and shared artifacts.
   Fixtures contain synthetic or fully-derived data unless the vendor license
   explicitly permits redistribution of samples.
3. **Exchange entitlements:** for exchange-sourced data, the entitlement
   (e.g. non-professional vs professional, internal vs display use) is named;
   any step that changes the entitlement class (adding display, adding users)
   is an escalation trigger in §1.5.
4. **Retention & deletion:** retention period and the vendor's deletion/return
   obligations on termination are stated; the chapter's runbook names where
   the data lives so it can be purged.
5. **Derived-data rights:** features, labels, and models derived from the data
   are ours; third-party redistribution of derived data follows the vendor's
   derived-data clause, cited by name.

## J.2 Vendor mapping rules

- Canonical logical dataset names are used in prose (`US equities L1`,
  `options chain snapshot`); the per-vendor column mapping lives once in
  `§S0/§T0` ("Mapping to canonical Event/Bar schema").
- Dataset fingerprints (hash of schema + first/last timestamps + row count)
  are recorded in `§0.datasets[].fingerprint` so a re-download is detectable.
- `vintage` = the as-of date of the data pull; `rights` = one of
  `licensed | exchange-entitled | synthetic | public-domain`.
- **Cheapest-source verdict row** (session 04): `min_tier, latency_class,
  required_fields, price_band, build_or_buy` — stated once in §1.5, referenced
  never restated in §S6/§T5.
- Single cost-assumption register: data-cost assumptions live in §1.5/§1;
  §S6/§T5 reference them, never restate them.

## J.3 What counts as a violation (CI-relevant)

- A dataset in `§0.datasets` with no Data rights row in §S6/§T5.
- A `rights: licensed` dataset with no named product/license tier.
- A fixture containing raw vendor ticks (fixtures must be synthetic or
  derived-aggregate; the TYPE header declares which).
