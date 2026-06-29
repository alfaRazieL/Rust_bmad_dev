# Phase Runner Prompt — Universal Template

This is the prompt to paste into a **fresh Claude Code / Codex CLI session** to execute a single RDX implementation phase. Replace `{PHASE}` with the phase number (1, 2, 3, 4, 5, 6, 7, 8, 9, or 10). The agent commits and pushes to the `rdx-improvements` branch at the end of the phase.

**For each new phase: open a new context window, paste the prompt below (with the phase number filled in), let the agent work until it stops.**

When all phases are done, return to the long-running session for final merge into `main`.

---

## How to use

1. Open a fresh Claude Code window (or Codex CLI session)
2. Copy the entire block in the "📋 PROMPT TO COPY" section below
3. Replace `{PHASE}` with the phase number you want to run
4. Paste into the new session and submit
5. Wait for the agent to finish (it will commit + push and stop)
6. Open the GitHub branch to verify the new commit appeared
7. Repeat for the next phase

---

## 📋 PROMPT TO COPY (replace `{PHASE}` everywhere)

```
Ты — инженер реализации RDX (Rust Dev eXpert) — публичного BMAD модуля.
Твоя задача — выполнить ровно одну фазу плана реализации: **Phase {PHASE}**.

Контекст работы у тебя чистый. Все исходники архитектуры и тестов уже находятся в репозитории. Прочитай их полностью, прежде чем что-то писать.

═══════════════════════════════════════════════════════════
1. РЕПОЗИТОРИЙ И ПЕРВЫЕ ДЕЙСТВИЯ
═══════════════════════════════════════════════════════════

Репозиторий: https://github.com/alfaRazieL/Rust_bmad_dev.git
Ветка работы: rdx-improvements (всегда)
Базовая ветка: main (НЕ трогать)

Первое что сделай:

1. Проверь, есть ли уже клон в /tmp/rust-bmad-dev:
   ls /tmp/rust-bmad-dev 2>/dev/null

2. Если нет — склонируй:
   git clone https://github.com/alfaRazieL/Rust_bmad_dev.git /tmp/rust-bmad-dev

3. Перейди в репо и переключись на ветку с pull-ом:
   cd /tmp/rust-bmad-dev
   git fetch origin
   git checkout rdx-improvements
   git pull origin rdx-improvements

4. Покажи последний коммит и убедись что состояние чистое:
   git log --oneline -3
   git status

═══════════════════════════════════════════════════════════
2. ОБЯЗАТЕЛЬНОЕ ЧТЕНИЕ (в этом порядке)
═══════════════════════════════════════════════════════════

Перед написанием ЛЮБОГО кода прочитай эти документы в репозитории:

ПРИОРИТЕТ 1 (читать целиком):
- RDX_IMPLEMENTATION_PLAN_TESTED.md — АВТОРИТЕТНЫЙ план с entry/exit gates. ТВОЯ КАРТА. Чекбоксы фазы [x] ставишь ТОЛЬКО здесь.
- RDX_TEST_CASES.yaml — каталог ~135 тест-кейсов. ОТФИЛЬТРУЙ ПО phase: {PHASE}.
- RDX_TEST_STRATEGY.md — архитектура тестов, status taxonomy, CI trust model.

ВАЖНО про два плана:
- RDX_IMPLEMENTATION_PLAN.md — ИСТОРИЧЕСКИЙ оригинал, ЗАМОРОЖЕН. НЕ читать как руководство и НЕ обновлять. Снимок плана на момент создания.
- RDX_IMPLEMENTATION_PLAN_TESTED.md — РАБОЧИЙ план с phase gates и привязкой к test IDs. Этот файл единственный обновляешь чекбоксами.

ПРИОРИТЕТ 2 (читать релевантные секции):
- RDX_TEST_TRACEABILITY_MATRIX.md — какие requirement и rule покрывает фаза.
- RDX_VALIDATOR_ARCHITECTURE_VERIFICATION.md — финальный verdict GO с корректировками; объясняет почему wrapper НЕ enforced.
- RDX_PHASE0_SPIKE_REPORT.md — результаты Phase 0 (multi-skill spike, validator prototype).
- RDX_TEST_DESIGN_REPORT.md — summary всех корректировок.

ПРИОРИТЕТ 3 (по запросу при необходимости):
- spikes/0.3-standalone-validator/rdx_validator.py — Python прототип для Phase 2.
- spikes/0.1-multi-skill/ — тестовые SKILL.md fixtures из Phase 0.
- .claude/skills/rdx-setup/ — текущий production RDX v1.0 (только если фаза его меняет).
- _bmad/scripts/resolve_customization.py в системе пользователя (для понимания merge semantics).

КРИТИЧЕСКИ ВАЖНО: НЕ начинай работу без понимания всех приоритет-1 документов. Если что-то противоречит — приоритет тестового плана выше старого плана.

═══════════════════════════════════════════════════════════
3. НЕПРИКОСНОВЕННЫЕ ПРИНЦИПЫ (нарушение = остановка)
═══════════════════════════════════════════════════════════

1. **Test-first.** Сначала пишешь тест (failing red), потом production код (green). Никакого кода без YAML-каталогизированного теста.

2. **Никакого "hard enforcement" для wrapper / Mode 0 / Mode 1.** Wrapper — это soft gate (LLM-cooperative). Hard enforcement живёт ТОЛЬКО в git hooks и CI. Документация должна это явно отражать.

3. **Status taxonomy зафиксирован.** 14 verdicts + 3 severities (WARNING — severity, не verdict). См. RDX_TEST_STRATEGY.md §5. Exit codes: 0/1/2/3/4 по таблице §5.3.

4. **LLM никогда не устанавливает Cat-1 PASS.** Schema это запрещает (T-L0-SCHEMA-004). PASS для Cat-1 требует command + exit_code + output digest.

5. **R2 wrapper для Code Review (НЕ R1).** Если Phase 7 — реализуй wrapper-pattern. R1 (on_complete) только как control test.

6. **CI loads validator from BASE BRANCH, не из PR head.** См. RDX_TEST_STRATEGY.md §7 (Option B). Это критично для tamper-resistance.

7. **НЕ форкать BMAD core.** Все интеграции через `_bmad/custom/` overrides и menu replacement.

8. **НЕ добавлять HMAC в V5.** Это специально отклонено в верификационном отчёте. CI re-runs покрывают trust model.

9. **Weak signals НЕ блокируют без story tag.** Ops, Perf claims, etc. — STORY_TAG_REQUIRED, не AUTO_ACTIVATE.

10. **НЕ менять production RDX v1.0** (`.claude/skills/rdx-setup/`) без явной необходимости фазы. Если фаза требует — действуй через `_bmad/custom/` overrides или новые skill folders.

═══════════════════════════════════════════════════════════
4. ВЫПОЛНЕНИЕ ФАЗЫ {PHASE}
═══════════════════════════════════════════════════════════

Найди в RDX_IMPLEMENTATION_PLAN_TESTED.md секцию "## Phase {PHASE}". Эта секция содержит:

A. **Entry gate** (тесты которые должны быть написаны ПЕРВЫМИ).
B. **Implementation tasks** (что реализовать).
C. **Exit gate** (тесты которые должны пройти зелёными для завершения).

Порядок работы:

### Шаг 1 — Author tests (Entry gate)
Для каждого item из Entry gate:
- Найди соответствующий test ID в RDX_TEST_CASES.yaml (по полю phase: {PHASE} и test ID)
- Создай fixture(s) под `tests/fixtures/...` с canonical expected verdict (sibling .expected.json)
- Создай pytest или driver файл под `tests/<layer>/...`
- Запусти тест → должен fail (red phase)
- Закоммить fixtures + tests с префиксом "test:" в commit message

### Шаг 2 — Implement (Implementation tasks)
Для каждой Implementation task:
- Реализуй минимальный production код, чтобы red тесты стали green
- НЕ пиши код "впрок" — только то что нужно для тестов
- Если код требует новой структуры папок — создай (rdx-validator/, rdx-dev-story/, etc.)
- Закоммить production code с префиксом "feat:" или "impl:"

### Шаг 3 — Verify (Exit gate)
- Запусти ВСЕ тесты из Exit gate
- Запусти L0 регрессию (контракты не сломаны)
- Запусти любые предыдущие L1/L2/L3 тесты если они есть (regression)
- Все должны быть зелёные

### Шаг 4 — Update plan
Открой RDX_IMPLEMENTATION_PLAN_TESTED.md, найди секцию Phase {PHASE} и отметь [x] для всех выполненных пунктов. Добавь запись в Progress Log в конце файла:

| дата | Phase {PHASE} | <название> | x | <evidence: commit hash / test ID / artifact path> |

═══════════════════════════════════════════════════════════
5. PHASE-SPECIFIC ПОДСКАЗКИ
═══════════════════════════════════════════════════════════

**Если PHASE = 1 (Contracts):**
- Создай JSON Schemas, status definitions, authority matrix, drift checker
- Никакого валидатор кода ещё нет — только контракты
- Главное: T-L0-* тесты должны существовать и проходить

**Если PHASE = 2 (Validator):**
- Используй прототип spikes/0.3-standalone-validator/rdx_validator.py как отправную точку
- Перенеси и расширь в `rdx-validator/` директорию верхнего уровня репо
- Никаких BMAD импортов!
- Закрой 6 fixture gaps из Phase 2 entry gate (FFI doc-only-negative, Macro doc-only-negative, и т.д.)
- Закрой 2 status gaps (BASELINE_BLOCKS_VALIDATION, TOOL_UNAVAILABLE)

**Если PHASE = 3 (Wrapper):**
- Создай `.claude/skills/rdx-dev-story/SKILL.md`
- НЕ модифицируй существующий `.claude/skills/rdx-setup/` — добавь menu override через assets
- Wrapper-resume тесты (T-L4-WR-*) — semi-automated, могут требовать subagent или manual session

**Если PHASE = 4 (Modes):**
- Расширь `.claude/skills/rdx-setup/SKILL.md` для интерактивного выбора режима
- Запиши `enforcement_level` в config
- Документация: НЕ называй Mode 1 "Enforced"

**Если PHASE = 5 (Hook + CI):**
- Pre-push hook — opt-in installer script
- GitHub Actions workflow loads validator from `main` (target branch)
- Адверсариальные тесты L7 ОБЯЗАТЕЛЬНЫ перед закрытием фазы

**Если PHASE = 6 (Evals):**
- Использует bmad-eval-runner skill
- Statistical thresholds (≥90% / ≥95% / 100%) — см. RDX_TEST_STRATEGY.md §6
- Rolling-window метрики

**Если PHASE = 7 (Rule Auditor):**
- ОБЯЗАТЕЛЬНО эмпирически закрой T-L4-CR-001 (R2 wrapper) — это закрывает Spike 0.2 gap
- Создай `.claude/skills/rdx-code-review/` как wrapper
- `.claude/skills/rdx-judgment/` — Cat-3 evaluator skill
- Если R2 не работает в реальной сессии — fallback на R1, документируй

**Если PHASE = 8 (Cat-4 approvals):**
- CODEOWNERS template
- Approval schema с diff_digest binding
- T-L7-APPROVAL-REUSE-001 — критический тест

**Если PHASE = 9 (HA hardening):**
- Только если есть реальный demand
- HMAC только при подтверждённой threat model

**Если PHASE = 10 (Docs):**
- T-V5-ACC-06 — финальная проверка на forbidden phrases
- compatibility matrix актуализирована

═══════════════════════════════════════════════════════════
6. COMMIT И PUSH
═══════════════════════════════════════════════════════════

После того как exit gate Phase {PHASE} проходит зелёным:

1. Финальный коммит фазы — объединяющий или последний из серии:
   ```
   git add -A
   git status
   git commit -m "Phase {PHASE}: <название фазы> complete

   <2-4 строки о том что сделано, какие тесты добавлены,
    какие фикстуры созданы, какие test IDs закрыты>

   Co-Authored-By: Claude <noreply@anthropic.com>"
   ```

2. Push в ветку rdx-improvements:
   ```
   git push origin rdx-improvements
   ```

3. Покажи финальную сводку:
   - какие test IDs закрыты (из YAML)
   - какие файлы добавлены/изменены
   - exit code последнего test run
   - ссылка на GitHub: https://github.com/alfaRazieL/Rust_bmad_dev/tree/rdx-improvements

═══════════════════════════════════════════════════════════
7. УСЛОВИЯ ОСТАНОВКИ
═══════════════════════════════════════════════════════════

ОСТАНОВИСЬ И НЕ ПРОДОЛЖАЙ если:

- Тест fails после 3 попыток исправить — сообщи о блокере, опиши ошибку
- Production код требует изменения архитектуры, противоречащего верификационному отчёту — сообщи и остановись
- Phase {PHASE} требует prerequisite из другой фазы которая ещё не сделана — сообщи
- Невозможно эмпирически проверить L4/L5 тест в текущей среде (например нужен GitHub repo, а Codex CLI не в нём) — пометь как BLOCKED и опиши workaround
- Изменение нарушает один из 10 принципов из секции 3 — стоп
- LLM eval показывает pass rate ниже threshold — стоп, не маркируй фазу complete

ВСЕГДА:
- Финальный коммит push-ни даже если фаза partial, с пометкой "Phase {PHASE}: partial — blocked on X"
- Обнови progress log с реальным статусом ([~] для partial)
- Никогда не используй --no-verify, --force-push, --amend на запушенных коммитах

═══════════════════════════════════════════════════════════
8. ЧЕГО ДЕЛАТЬ НЕЛЬЗЯ
═══════════════════════════════════════════════════════════

- Не сливать в main (это будет сделано вручную после всех фаз)
- Не пушить в другие ветки (только rdx-improvements)
- Не менять main ветку локально
- Не выполнять следующую фазу — только {PHASE}
- Не модифицировать spike артефакты (`spikes/`) — они исторические доказательства
- Не модифицировать research документы (`RDX improve research.md`, `RDX_VALIDATOR_ARCHITECTURE_VERIFICATION.md`, `RDX_PHASE0_SPIKE_REPORT.md`, `RDX_TEST_DESIGN_REPORT.md`) — они снимки во времени
- Можно обновлять только: `RDX_IMPLEMENTATION_PLAN_TESTED.md` (progress log + checkboxes), `RDX_TEST_CASES.yaml` (только если phase обнаруживает новый необходимый test ID), и любые файлы под `tests/`, `rdx-validator/`, `.claude/skills/rdx-*/`, `.github/`
- Не убирать `[x]` чекбоксы предыдущих фаз
- Не считать "проверил визуально, выглядит правильно" зелёным тестом
- Не игнорировать flaky тест — если flaky, см. RDX_TEST_STRATEGY.md §10
- Не использовать subagent для production кода без необходимости — для phase-work работай напрямую сама
- Не публиковать GitHub release / тэги — это делает пользователь

═══════════════════════════════════════════════════════════
9. ФИНАЛЬНЫЙ ВЫХОД
═══════════════════════════════════════════════════════════

После push-а сообщи пользователю в ЭТОЙ структуре (никаких вольных форматов):

1. **Phase {PHASE}: COMPLETE / PARTIAL / BLOCKED**

2. **Commit(s):** hash + название каждого коммита фазы

3. **Что произведено — раздели на 3 категории явно:**

   **A. Production-артефакты** (контракты, схемы, конфиги, скрипты которые будут использоваться runtime — НЕ тесты):
   - перечисли пути файлов + одну строку зачем каждый

   **B. Verifier scripts / runtime guards** (если фаза такие создаёт — например drift-check, dedup-check):
   - перечисли пути + что они проверяют в runtime

   **C. Тесты + fixtures** (которые проверяют A и B):
   - перечисли test files + fixtures + сколько тестов в каждом + статус (red/green)

4. **CI workflows** добавленные в .github/workflows/ — если есть

5. **Test IDs закрытые в этой фазе** (из YAML, по полю phase: {PHASE})

6. **URL:** https://github.com/alfaRazieL/Rust_bmad_dev/commits/rdx-improvements

7. **Что НЕ сделано** (явно, чтобы пользователь не путался) — какие test IDs ИЗ Phase {PHASE} остались open и почему:
   - либо отложены в более позднюю фазу
   - либо BLOCKED с описанием блокера
   - либо просто не входили в текущую фазу scope

8. **Открытые блокеры** (если есть) с конкретными следующими шагами

9. **Готовность Phase {NEXT}:**
   - какие prerequisites из {PHASE} проверены
   - есть ли новые зависимости которые пользователь должен подготовить (env vars, GitHub repo, секреты, и т.д.)

10. **Граница ответственности:** одной фразой объясни — реализовала ли эта фаза какую-то пользовательскую функциональность (validator работает? wrapper можно вызвать? hook реально блокирует?), или это пока только фундамент для будущих фаз. Не делай вид что фаза "завершила улучшение RDX" если она только заложила контракты или тесты.

И ОСТАНОВИСЬ. Не переходи к следующей фазе. Пользователь откроет новое окно с обновлённым {PHASE} = {NEXT}.

═══════════════════════════════════════════════════════════
Начинай. Phase {PHASE}.
```

---

## Примечания для пользователя

### Контроль качества между фазами

После каждой фазы — открой ветку на GitHub и проверь:
- Появился ли коммит с правильным prefix ("Phase N:")
- Появились ли новые файлы в `tests/`, `rdx-validator/`, etc.
- Progress log в `RDX_IMPLEMENTATION_PLAN_TESTED.md` обновлён
- Чекбоксы фазы помечены `[x]` (или `[~]` если partial)
- Нет неожиданных удалений / изменений в чужих файлах

Если что-то не так — откати ветку локально и пере-запусти фазу с уточнённым промтом.

### Откат фазы (если что-то пошло не так)

```bash
cd /tmp/rust-bmad-dev
git fetch origin
git checkout rdx-improvements

# Найди коммит ДО проблемной фазы
git log --oneline

# Откат на нужный коммит (force push в feature branch допустим, в main НЕТ)
git reset --hard <commit-hash>
git push --force-with-lease origin rdx-improvements
```

### Финальный merge в main (после всех фаз)

Это делается в нашей основной сессии, не в phase-runner промте. Я в основной сессии:
1. Просмотрю всю историю rdx-improvements
2. Создам PR rdx-improvements → main
3. Проверю CI gate на самом PR
4. Сделаем squash или merge в зависимости от истории

### Параллельная работа

Не запускай две фазы одновременно — они могут конфликтовать на одних файлах (например, прогресс-логе плана). Только последовательно.
