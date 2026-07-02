# RDX Validator Gate — Implementation Plan V5 → V6

> **Status tracking**: Each item is marked `[ ]` (pending), `[~]` (in progress), or `[x]` (done with evidence).
> Evidence references the artifact (commit, file, spike report section) proving completion.
> Branch: `rdx-improvements`. Source-of-truth report: `RDX_VALIDATOR_ARCHITECTURE_VERIFICATION.md`.

---

## 1. Цель проекта

Развить Rust Dev eXpert из системы LLM-инструкций в гибридную систему, где:

- RDX Knowledge Base определяет Rust-правила;
- `rdx-dev-story` организует их применение внутри BMAD;
- `rdx-validator` детерминированно проверяет Cat-1 и Cat-2 требования;
- git hook и CI обеспечивают реальное enforcement вне LLM-сессии;
- RDX Rule Auditor проверяет Cat-3 требования;
- specialist/owner approval закрывает Cat-4 требования;
- стандартный BMAD Developer Amelia сохраняется;
- BMAD core и `bmad-dev-story` не форкаются.

## 2. Целевая архитектура

### Первый production milestone — V5

- [ ] Независимый `rdx-validator`
- [ ] Evidence Schema v1
- [ ] Machine-readable Risk Router mapping
- [ ] `rdx-dev-story` BMAD-wrapper
- [ ] Menu override `DS → rdx-dev-story`
- [ ] Опциональный pre-push hook
- [ ] GitHub Actions CI gate
- [ ] Базовый regression/eval suite

### Конечная архитектура — V6

- [ ] `rdx-judgment` / RDX Rule Auditor
- [ ] Интеграция RDX-аудита в BMAD Code Review
- [ ] Cat-3 structured judgments
- [ ] Cat-4 specialist routing
- [ ] CODEOWNERS/approval trail
- [ ] High Assurance mode
- [ ] Подписи / attestations (только при доказанной необходимости)

---

# Phase 0 — закрытие интеграционных предпосылок

**Цель:** До изменения production-файлов доказать, что выбранная BMAD-интеграция работает в реальной Claude Code/BMAD-сессии.

## 0.1. Реальный multi-skill spike

- [x] Создать `rdx-test-wrapper` SKILL — `spikes/0.1-multi-skill/wrapper.SKILL.md`
- [x] Создать `rdx-test-child` SKILL — `spikes/0.1-multi-skill/child.SKILL.md`
- [x] Проверить: успешный child → wrapper resumes — trace.log: BEFORE→CHILD→AFTER
- [x] Проверить: child с ошибкой → wrapper resumes с error info — validator stub FAIL captured (exit 1, JSON read)
- [x] Проверить: child с неполным результатом → wrapper detects — covered by error case
- [x] Проверить: wrapper instructions сохраняются после child — Step 3 AFTER marker written, proven by trace.log
- [x] Проверить: отсутствие рекурсии — single CHILD entry in trace.log
- [x] Проверить: возврат к post-child steps — Step 3 + Step 4 executed
- [x] Проверить: результаты child доступны для wrapper — wrapper read CHILD_DONE return
- [x] Проверить: поведение при context pressure — N/A in this spike; will retest in real story workflow
- [x] **GO criterion**: wrapper надёжно продолжает исполнение после child — **MET**, subagent self-report confirms unambiguous flow
- [x] **Fallback path** документирован (CLI launcher, V4) — `RDX_PHASE0_SPIKE_REPORT.md` §0.1

## 0.2. Review propagation spike

- [x] Получает ли parent reviewer RDX persistent facts? — **Yes** (workflow.persistent_facts merged via resolver)
- [x] Получают ли их review subagents? — **No** (intentional isolation per step-02-review.md)
- [x] Можно ли передавать активные RDX rules через `also_consider`? — Not via that mechanism; via `on_complete` and persistent_facts on parent
- [x] Можно ли добавить RDX Rule Auditor как дополнительный review layer? — **Yes**, as post-pass via `on_complete`
- [x] Возвращаются ли его findings в штатный triage? — Via parent appending to final report under "RDX Rule Auditor" section
- [x] Можно ли сделать это customization-механизмом без копирования стандартных step files? — **Yes**
- [x] **GO criterion** — **MET** (via on_complete + persistent_facts hybrid; see spike report §0.2)
- [x] **Fallback path** документирован (rdx-judgment as standalone skill invoked from CI) — spike report §0.2

## 0.3. Standalone validator spike

- [x] CLI-прототип создан (Python, без BMAD-импортов) — `spikes/0.3-standalone-validator/rdx_validator.py` (260 LOC, stdlib only)
- [x] Читает реальный git diff — `--base/--head` and `--diff-file` both work
- [x] Корректно извлекает изменённые пути — fixture 4 returned `paths: ['Cargo.toml']`
- [x] Активирует Async fixture — fixture 1 returned `activated_packs: ['async']`
- [x] Активирует Unsafe fixture — fixture 3 returned `activated_packs: ['unsafe']`
- [x] Активирует Cargo fixture — fixture 4 returned `activated_packs: ['cargo']`
- [x] Игнорирует doc-only async fixture — fixture 2 returned `activated_packs: []`
- [x] Вычисляет `diff_digest` — all 4 fixtures returned distinct stable SHA-256 digests
- [x] Возвращает machine-readable verdict (JSON) — parseable by `python3 -c "json.load(sys.stdin)"`
- [x] Использует стабильные exit codes — 0/1/2/3 semantics documented in script
- [x] **GO criterion**: все 4 router fixtures обрабатываются корректно — **MET**

## 0 Output

- [x] `RDX_PHASE0_SPIKE_REPORT.md` создан с:
  - [x] командами
  - [x] окружением
  - [x] результатами
  - [x] GO/fallback решениями
  - [x] окончательной формой V5 integration

**Gate**: Не переходить к Phase 1 при незакрытом multi-skill verdict (0.1) или standalone validator verdict (0.3). Review propagation (0.2) может быть закрыт fallback-ом без блокировки. — **All three GO. Gate passed.**

---

# Phase 1 — contracts и single source of truth

## 1.1. Зафиксировать модель правил

- [ ] Cat 1 — детерминированные
- [ ] Cat 2 — проверяемое наличие evidence
- [ ] Cat 3 — judgment review
- [ ] Cat 4 — specialist approval

- [ ] Canonical mapping для каждого rule ID:
  - [ ] applicability
  - [ ] detection source
  - [ ] evidence requirement
  - [ ] verdict authority
  - [ ] blocking semantics
  - [ ] exception policy

## 1.2. Machine-readable Router mapping

- [ ] Файл `router-rules.json` создан
- [ ] Для каждого pack:
  - [ ] pack ID
  - [ ] positive deterministic signals
  - [ ] file-path signals
  - [ ] negative signals
  - [ ] confidence class
  - [ ] activation policy (AUTO_ACTIVATE / AUTO_SUGGEST / STORY_TAG_REQUIRED / REVIEW_REQUIRED)
  - [ ] related rule IDs
  - [ ] required validation family
- [ ] Markdown Risk Router остаётся нормативным human-readable документом

## 1.3. Drift prevention

- [ ] Проверка соответствия pack IDs (Markdown ↔ JSON)
- [ ] Проверка соответствия rule IDs
- [ ] Проверка версий mapping
- [ ] Проверка coverage machine-readable entries
- [ ] Изменение Router без обновления mapping ломает module CI

## 1.4. Evidence Schema v1

Обязательные разделы:

- [ ] schema/RDX/KB version
- [ ] enforcement mode
- [ ] story contract
- [ ] base/head SHA
- [ ] diff digest
- [ ] KB digest
- [ ] activated packs
- [ ] per-rule applicability
- [ ] deterministic evidence
- [ ] reasoning records
- [ ] exceptions
- [ ] baseline comparison
- [ ] blocking findings
- [ ] review required
- [ ] approval required
- [ ] aggregate verdict

## 1.5. Authority boundaries

- [ ] LLM не устанавливает Cat-1 PASS
- [ ] Validator не устанавливает Cat-3 PASS
- [ ] Evaluator не изменяет Cat-1 verdict
- [ ] Specialist approval не заменяется LLM
- [ ] CI повторно вычисляет authoritative deterministic fields
- [ ] Локальный evidence не считается источником истины для CI

### Phase 1 Output

- [ ] Evidence Schema v1
- [ ] Router mapping v1
- [ ] Rule-check mapping v1
- [ ] Status and authority specification
- [ ] Schema/mapping tests

---

# Phase 2 — standalone `rdx-validator`

## 2.1. CLI contract

Inputs:

- [ ] project root
- [ ] story/spec path
- [ ] base ref
- [ ] head ref
- [ ] enforcement mode
- [ ] evidence input/output
- [ ] project policy config

Outputs:

- [ ] human-readable summary
- [ ] machine-readable JSON
- [ ] stable exit code
- [ ] evidence файл

## 2.2. Первый набор checks

- [ ] **CORE-007** — protected boundaries (FAIL on unauthorized boundary)
- [ ] **CORE-015** — Router parity (FAIL on unjustified mismatch)
- [ ] **CORE-011** — compile/check evidence (EVIDENCE_REQUIRED → FAIL)
- [ ] **CORE-014** — suppression/test weakening (EVIDENCE_REQUIRED → FAIL without authorization)
- [ ] **CORE-008** — panic discipline subset (WARNING / EVIDENCE_REQUIRED)

## 2.3. Status taxonomy (15 статусов)

- [ ] `PASS`
- [ ] `FAIL`
- [ ] `NOT_APPLICABLE`
- [ ] `NOT_RUN`
- [ ] `BASELINE_FAILURE_OBSERVED`
- [ ] `BASELINE_BLOCKS_VALIDATION`
- [ ] `REGRESSION_FAILURE`
- [ ] `REGRESSION_FIXED`
- [ ] `ENVIRONMENT_UNAVAILABLE`
- [ ] `TOOL_UNAVAILABLE`
- [ ] `EVIDENCE_REQUIRED`
- [ ] `REVIEW_REQUIRED`
- [ ] `APPROVAL_REQUIRED`
- [ ] `BLOCKED`

## 2.4. Base/head comparison

- [ ] Dual-run для CI: одинаковая toolchain, features, policy
- [ ] Структурированные Cargo diagnostics
- [ ] Comparison per check
- [ ] Отделение baseline от regression
- [ ] Локальный hook может использовать сокращённый режим

## 2.5. Test suite

- [ ] unit tests
- [ ] fixture-based tests
- [ ] real Cargo project integration tests
- [ ] diff parsing tests
- [ ] renames/deletions tests
- [ ] invalid schema tests
- [ ] stale evidence tests
- [ ] mapping drift tests
- [ ] baseline/regression tests

### Phase 2 Done criteria

- [ ] Validator работает без BMAD
- [ ] Воспроизводимо возвращает verdict
- [ ] Не доверяет LLM Cat-1 PASS
- [ ] Корректно обрабатывает exceptions
- [ ] Имеет документированный CLI
- [ ] Проходит собственный test suite

---

# Phase 3 — `rdx-dev-story` и BMAD integration

## 3.1. Wrapper responsibility

- [ ] Contract intake
- [ ] Story risk tag extraction
- [ ] Router pre-pass
- [ ] Запуск стандартного `bmad-dev-story`
- [ ] Evidence collection
- [ ] Запуск `rdx-validator`
- [ ] Представление результата
- [ ] Маркировка результата как cooperative/local validated
- [ ] Wrapper НЕ заявляет hard enforcement

## 3.2. Menu integration

- [ ] Через RDX override заменить `DS → rdx-dev-story`
- [ ] Сохранить стандартное описание (или явно переопределить)
- [ ] Совместимость со всеми остальными menu items
- [ ] Совместимость с пользовательскими overrides
- [ ] Update-safe merge при повторном setup
- [ ] Отдельный menu item для ручного validator запуска (`VG` или подобное)

## 3.3. Resolver compatibility

- [ ] Setup определяет поддерживаемую версию resolver
- [ ] Setup проверяет merge-by-code
- [ ] Setup предупреждает при несовместимости
- [ ] Setup не изменяет BMAD core
- [ ] Setup имеет rollback/uninstall path
- [ ] Setup не затирает чужие customizations

## 3.4. Context discipline

Wrapper передаёт в child только:

- [ ] story
- [ ] contract
- [ ] active risk tags
- [ ] нужные KB sections
- [ ] applicable validation expectations
- [ ] НЕ загружает все conditional packs

## 3.5. Failure behavior

- [ ] `FAIL/BLOCKED` — сообщить, что story не прошла RDX validation
- [ ] `EVIDENCE_REQUIRED` — запросить/создать evidence
- [ ] `REVIEW_REQUIRED` — направить в Cat-3 layer (Phase 7)
- [ ] `APPROVAL_REQUIRED` — заблокировать high-assurance completion и передать в CI/governance
- [ ] НЕ выдавать ложный hard-enforcement claim

### Phase 3 Done criteria

- [ ] Обычный BMAD Developer workflow работает через RDX wrapper без форка
- [ ] Validator автоматически запускается на happy path

---

# Phase 4 — operating modes и setup UX

## 4.1. Advisory

- [ ] KB
- [ ] Existing agent overrides
- [ ] Report-only behavior
- [ ] Маркировка: `enforcement_level = advisory`

## 4.2. Local Validated

- [ ] Wrapper
- [ ] Validator
- [ ] Evidence
- [ ] Нет hard blocking — явно документировано

## 4.3. Local Gated

- [ ] Opt-in pre-push hook
- [ ] Validator запускается до push
- [ ] Exit code блокирует push
- [ ] Hook installation только с явным согласием пользователя

## 4.4. CI Enforced

- [ ] CI template
- [ ] Required status check instructions
- [ ] Clean checkout validation
- [ ] Base/head comparison
- [ ] Independent recomputation

## 4.5. High Assurance (Phase 8+)

- [ ] Cat-3 reviewer
- [ ] Cat-4 approval
- [ ] Protected validator
- [ ] CODEOWNERS
- [ ] Diff-pinned approvals
- [ ] Provenance при необходимости

## 4.6. Installation policy

- [ ] Setup спрашивает режим
- [ ] Объясняет силу гарантий каждого режима
- [ ] Записывает mode в config
- [ ] Показывает недоступные зависимости
- [ ] НЕ называет advisory/local validated детерминированным enforcement
- [ ] Поддерживает update/uninstall

---

# Phase 5 — git hook и CI enforcement

## 5.1. Pre-push hook

- [ ] Opt-in
- [ ] Использует тот же validator core
- [ ] Не дублирует проверочную логику
- [ ] Сохраняет существующий hook или chain-ит его корректно
- [ ] Имеет uninstall
- [ ] Сообщает о `--no-verify` bypass
- [ ] НЕ является заменой CI для командных проектов

## 5.2. GitHub Actions

- [ ] Запускается на pull request
- [ ] Использует validator из доверенного источника
- [ ] Проверяет реальный diff
- [ ] Повторно вычисляет Cat-1/2
- [ ] Не доверяет локальному evidence verdict
- [ ] Публикует понятный summary
- [ ] Завершается non-zero при blocking status
- [ ] Поддерживает branch protection required check

## 5.3. Fork PR

Cat-1/2 workflow:

- [ ] Работает без secrets
- [ ] Безопасен для fork PR
- [ ] НЕ исполняет недоверенный privileged code с secrets

Cat-3 LLM review:

- [ ] НЕ входит в V5 blocking workflow
- [ ] Позднее запускается через trusted review process

## 5.4. GitLab portability

- [ ] GitLab CI template после GitHub template
- [ ] Validator core не меняется

### V5 Definition of Done (см. также §"Definition of Done — V5" ниже)

Демонстрационный проект подтверждает:

- [ ] Корректный PR проходит
- [ ] Protected boundary violation блокируется
- [ ] Router mismatch блокируется
- [ ] Failed Cargo check классифицируется
- [ ] Stale evidence отвергается
- [ ] Baseline и regression различаются
- [ ] Изменение workflow в PR не позволяет обойти trusted CI check

---

# Phase 6 — evals и regression protection

## 6.1. Deterministic tests

- [ ] Router positive signals
- [ ] Router negative signals
- [ ] Diff path parsing
- [ ] Protected files
- [ ] Evidence schema
- [ ] Exception handling
- [ ] Baseline comparison
- [ ] Stale evidence
- [ ] Unsupported environment

## 6.2. BMAD behavioral evals (via bmad-eval-runner)

- [ ] Developer не пропускает Router
- [ ] Wrapper вызывает validator
- [ ] Failing result не представляется как PASS
- [ ] Active packs передаются
- [ ] Irrelevant packs не загружаются
- [ ] Risk tags сохраняются
- [ ] Current mode называется корректно
- [ ] `NOT_RUN` не скрывается
- [ ] Validator output не подменяется LLM

## 6.3. Mutation/adversarial tests

- [ ] Вручную записанный PASS отвергается
- [ ] Изменённый evidence отвергается
- [ ] Изменённый diff после evidence отвергается
- [ ] Удалённый test обнаруживается
- [ ] Изменённый mapping ломает CI
- [ ] Отключённый pack обнаруживается
- [ ] Изменённый validator обнаруживается
- [ ] Другой base SHA отвергается
- [ ] Пропущенный hook документирован как bypass
- [ ] Изменённый CI workflow обнаруживается governance

## 6.4. Release gate для RDX

Каждое изменение KB / Router / schema / mapping / validator policy / agent override / CI template должно проходить:

- [ ] RDX module CI
- [ ] Behavioral evals

---

# Phase 7 — RDX Rule Auditor и BMAD Code Review

## 7.1. Создать переиспользуемый `rdx-judgment`

Принимает:

- [ ] diff
- [ ] surrounding code
- [ ] story/spec
- [ ] active packs
- [ ] `review_required_rules`
- [ ] reasoning evidence
- [ ] deterministic validator findings

НЕ должен:

- [ ] повторно устанавливать Cat-1 verdict
- [ ] загружать неактивные packs
- [ ] назначать specialist approval
- [ ] считать отсутствие findings автоматическим доказательством soundness
- [ ] требовать фиксированное количество findings

## 7.2. Review output

Каждый finding:

- [ ] Rule ID
- [ ] Affected location
- [ ] Contract/evidence reference
- [ ] Reasoning
- [ ] Verdict
- [ ] Confidence
- [ ] Suggested routing

Статусы:

- [ ] `PASS`
- [ ] `FAIL`
- [ ] `DECISION_REQUIRED`
- [ ] `SPECIALIST_REQUIRED`
- [ ] `INSUFFICIENT_EVIDENCE`

## 7.3. Интеграция в `bmad-code-review`

Предпочтительная схема:

- [ ] Blind Hunter
- [ ] Edge Case Hunter
- [ ] Acceptance Auditor
- [ ] **RDX Rule Auditor** (добавляется)
- [ ] НЕ заменять существующие review layers
- [ ] RDX Rule Auditor проверяет только активные Rust requirements

## 7.4. Parent triage

- [ ] Дедуплицирует findings
- [ ] Читает surrounding code
- [ ] Назначает final severity
- [ ] Связывает finding со story
- [ ] Переводит unresolved findings в action items
- [ ] НЕ принимает Cat-3 reviewer за детерминированный источник истины

## 7.5. Documentation review

RDX Rule Auditor активируется для:

- [ ] Rust API contracts
- [ ] ADR
- [ ] unsafe safety contracts
- [ ] FFI/ABI docs
- [ ] persistence schemas
- [ ] security boundaries
- [ ] operational contracts
- [ ] validation policy
- [ ] RDX KB / Router / validator policy
- [ ] НЕ применять Rust KB к нерелевантной документации

### Phase 7 Done criteria

- [ ] Cat-3 правила получают independent structured review без копирования полного стандартного code-review workflow

---

# Phase 8 — Cat-4 specialist approval

## 8.1. Категории

- [ ] unsafe/soundness
- [ ] FFI/ABI
- [ ] security
- [ ] public API/SemVer
- [ ] migrations/distributed state
- [ ] validator governance
- [ ] KB/schema/mapping policy

## 8.2. Approval contract

Approval связан с:

- [ ] rule ID
- [ ] reviewer identity
- [ ] role
- [ ] head SHA
- [ ] diff digest
- [ ] timestamp
- [ ] scope
- [ ] decision
- [ ] conditions
- [ ] Изменение diff инвалидирует approval

## 8.3. CODEOWNERS integration

Template ownership для:

- [ ] unsafe areas
- [ ] FFI
- [ ] security
- [ ] public API
- [ ] RDX protected artifacts

## 8.4. CI behavior

- [ ] `APPROVAL_REQUIRED` остаётся blocking до появления валидного approval trail

---

# Phase 9 — High Assurance hardening (добавлять только после V5/V6 feedback)

- [ ] signed attestations (если threat model требует)
- [ ] protected validator source
- [ ] validator execution from trusted base ref
- [ ] immutable release artifacts
- [ ] provenance
- [ ] external policy server
- [ ] audit trail retention
- [ ] organization-level required workflows

⚠️ HMAC НЕ добавлять автоматически — сначала доказать реальную threat model.

---

# Phase 10 — documentation и distribution

## Документация

- [ ] architecture overview
- [ ] mode comparison
- [ ] installation
- [ ] update/uninstall
- [ ] evidence schema
- [ ] status semantics
- [ ] exception model
- [ ] hook behavior
- [ ] CI setup
- [ ] review integration
- [ ] specialist approvals
- [ ] troubleshooting
- [ ] compatibility matrix
- [ ] limitations

## Public positioning

Чётко объяснить, что:

- [ ] RDX НЕ доказывает корректность всех Rust-решений
- [ ] Cat-1 детерминирован
- [ ] Cat-2 проверяет evidence
- [ ] Cat-3 является judgment review
- [ ] Cat-4 требует approval
- [ ] CI является источником enforcement
- [ ] Wrapper является workflow UX

---

# Рекомендуемый порядок релизов

## RDX 1.1 — Validator foundation
Phase 0 + Phase 1 + Phase 2

## RDX 1.2 — BMAD integration
Phase 3 + Phase 4

## RDX 1.3 — CI Enforced
Phase 5

## RDX 1.4 — Review layer
Phase 6 + Phase 7

## RDX 1.5 — High Assurance
Phase 8 + selected Phase 9

---

# Definition of Done — V5

V5 считается завершённым, только если:

1. [ ] Validator не зависит от BMAD
2. [ ] Menu override работает без изменения BMAD core
3. [ ] Wrapper integration прошла real-session spike
4. [ ] Strong Router signals воспроизводимо определяются
5. [ ] Weak signals не создают необоснованный blocking FAIL
6. [ ] Evidence schema разделяет authority
7. [ ] Git hook реально блокирует push
8. [ ] CI самостоятельно пересчитывает deterministic verdicts
9. [ ] Baseline и regression различаются
10. [ ] Stale evidence отвергается
11. [ ] Документация не называет wrapper hard enforcement
12. [ ] BMAD module evals проходят
13. [ ] Установка, обновление и удаление проверены в clean project
14. [ ] Существующий RDX KB behavior не регрессировал

# Definition of Done — V6

V6 считается завершённым, только если:

1. [ ] Выполнены все V5 criteria
2. [ ] Cat-3 rules направляются RDX Rule Auditor
3. [ ] Auditor получает только активные rules/packs
4. [ ] Findings интегрируются в code-review triage
5. [ ] Cat-1 verdict нельзя изменить evaluator-ом
6. [ ] Cat-4 changes требуют named approval
7. [ ] Approvals привязаны к diff
8. [ ] Governance-sensitive RDX artifacts защищены
9. [ ] Review и approval flows имеют eval coverage
10. [ ] High Assurance mode подтверждён adversarial tests

---

## Progress Log

| Date | Phase | Item | Status | Evidence |
|------|-------|------|--------|----------|
| 2026-06-29 | Init | Plan saved to branch | x | This file in `rdx-improvements` branch |
| 2026-06-29 | 0.1 | Multi-skill spike | x | EXPERIMENT VERIFIED — see `RDX_PHASE0_SPIKE_REPORT.md` §0.1 and `spikes/0.1-multi-skill/trace.log.evidence` |
| 2026-06-29 | 0.2 | Review propagation spike | x | DOC VERIFIED — see `RDX_PHASE0_SPIKE_REPORT.md` §0.2 (on_complete + persistent_facts hybrid) |
| 2026-06-29 | 0.3 | Standalone validator prototype | x | EXPERIMENT VERIFIED — see `RDX_PHASE0_SPIKE_REPORT.md` §0.3 and `spikes/0.3-standalone-validator/` |
| 2026-06-29 | 0 | Phase 0 gate | x | All three GO. Cleared to proceed to Phase 1. |
