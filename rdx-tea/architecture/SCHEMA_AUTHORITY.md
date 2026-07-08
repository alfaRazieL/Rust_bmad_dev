# Schema authority — `rdx-tea-run.v1.schema.json` (Wave 3 decision)

**Decision (W3):** the copy shipped under
`poc/install-tree/_bmad/rdx-tea/canonical/rdx-tea-run.v1.schema.json` is
the **authoritative** schema. The copy under
`architecture/rdx-tea-run.v1.schema.json` is a **byte-identical mirror**
kept for architecture-document readability only.

## Why `canonical/` is authoritative

- `canonical/**` is the **shipped surface** — it is what the installer
  writes into a user project (`PRODUCTION_EVAL_SPLIT.md` §2) and what the
  binder / verifier resolve at runtime. `architecture/**` is classified
  **HISTORICAL** and never installs.
- The schema is source-locked with the rest of `canonical/`; making the
  shipped copy authoritative keeps the schema inside the same integrity
  boundary as the KB and JSON contracts it governs.
- Runtime code never loads the schema from `architecture/`. Production
  `prepare.py` does not read the schema at all; the binder emits a sidecar
  whose shape is fixed by `binder.py`, and the (deferred) external RDX
  validator consumes the shipped canonical copy.

## What the schema governs

`rdx-tea-run.v1` is the **sidecar** contract — the deterministic
`<artifact>.rdx-tea.json` the binder writes after a TEA workflow completes
(`binder.py`). It is NOT the `run-manifest.json` shape. The manifest that
`prepare.py` emits is a superset used to *build* the sidecar; the binder
projects the manifest's identity block + `active_packs` + `core_rules`
into a schema-valid sidecar and adds artefact hashes.

W3 schema coverage therefore validates **both** levels
(`tests/integration/test_l3_w3_bundle_builder.py`):

- `test_w3_schema_manifest_fields_conform` — every manifest field that
  feeds the sidecar satisfies the schema's field-level constraints
  (SHA patterns, `pack_id` enum, rule-id patterns, `workflow` enum,
  `execution_mode` const, `schema_version` const).
- `test_w3_schema_binder_sidecar_validates_against_rdx_tea_run_v1` — the
  real binder sidecar validates against the shipped canonical schema
  (including the empty-bundle / docs-only case).

## Drift guard

`architecture/` MUST stay byte-identical to `canonical/`. A test enforces
it and fails closed on divergence:

- `test_w3_schema_authority_canonical_is_mirror_of_architecture`.

If the schema must change, edit the **canonical** copy first, then re-sync
the mirror (`cp canonical/rdx-tea-run.v1.schema.json architecture/`) in the
same commit. A schema change is a `canonical/` change and additionally
requires a source-lock re-pin + `SOURCE_LOCK` addendum, and re-pinning the
W3 golden signature if the manifest shape changes.

## Note on `$id`

Both copies carry `"$id": ".../architecture/rdx-tea-run.v1.schema.json"`.
That URI is a stable document identifier, not a filesystem authority claim
and not a fetch target for runtime; it is intentionally left unchanged so
the schema bytes (and their source-lock hash) remain stable. Authority is
defined by this document, not by the `$id` path.
