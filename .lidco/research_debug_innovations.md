# Debug Mode — Research & Innovation Backlog

> Синтез академических исследований 2023–2025 + анализ пробелов текущей реализации LIDCO.
> Цель: идеи для Q26–Q30, ранжированные по соотношению usability/effort.

---

## Реализовано (Q19–Q25)

| Техника | Файл | Сигнал для LLM |
|---------|------|----------------|
| Error History (ring buffer) | `core/errors.py` | Последние N ошибок + causal chain |
| Error Ledger (SQLite) | `core/error_ledger.py` | Cross-session recurring errors |
| Error Timeline | `core/error_timeline.py` | ASCII bar chart по временным bucket-ам |
| Fix Memory | `core/fix_memory.py` | Прошлые патчи для похожих ошибок |
| Traceback Parser | `core/traceback_parser.py` | Структурированные фреймы + root_cause_hint |
| Syntax Fixer (9 паттернов) | `core/syntax_fixer.py` | Deterministic SyntaxError fix hint |
| Module Advisor (Levenshtein) | `core/module_advisor.py` | Pip-install suggestions |
| Coverage Gap Locator | `core/coverage_gap.py` | Непокрытые строки/ветви failing-файла |
| Branch Hit Counter | `core/branch_counter.py` | hit/miss статистика per branch arc |
| Coverage Delta Tracker | `core/coverage_delta.py` | До/после delta по коммиту |
| Coverage Injector | `graph.py` | `## Coverage Gaps` в debugger context |
| SBFL Ochiai (Q26) | `core/sbfl.py` | `## Suspicious Lines` по spectra |
| Semantic Fingerprint (Q26) | `core/error_fingerprint.py` | Stable cross-version error dedup |
| Trace Recorder (Q26) | `core/trace_recorder.py` | Variable snapshots at failure point |
| File Risk Score (Q26) | `core/risk_scorer.py` | `## High-Risk Files` в planner |
| Delta Debugger (Q26) | `core/delta_debugger.py` | Minimal reproducer via ddmin |

---

## Q27 — Backward Program Slicing

**Концепция:** Backward slice от точки падения — минимальный набор строк, которые математически могли повлиять на значение сбойной переменной.

**Почему инновационно:**
- SBFL ранжирует все строки статистически; slicing *доказывает* зависимость
- Для `AttributeError: 'NoneType'` slice сразу показывает все присваивания, где X мог стать None
- Debugging Book (Python): полная реализация через `sys.settrace` dependency tracking ~300 строк

**Алгоритм:**
```
backward_slice(target_var, target_line, trace_events):
  deps = {(target_file, target_line)}
  queue = [(target_var, target_line)]
  while queue:
    var, line = queue.pop()
    for event in trace_events where event.line < line:
      if var in event.locals and event was an assignment:
        deps.add(event.line)
        queue.extend(rhs_variables(event, var))
  return sorted(deps)
```

**Реализация:**
- `SlicingCriterion` dataclass: `variable: str`, `file: str`, `line: int`
- `BackwardSlice` dataclass: `criterion`, `slice_lines: list[int]`, `slice_events: list[TraceEvent]`
- `compute_backward_slice(trace_session, criterion)` → `BackwardSlice`
- `format_backward_slice(bslice)` → `## Backward Slice` Markdown
- Интеграция: вызывается после TraceRecorder (Q26), если anomaly detected

**Источник:** ACM OOPSLA 2024 — Predictive Program Slicing, ~90% accuracy at line level. Debugging Book Python implementation.

**Effort:** 2d | **Impact:** ОЧЕНЬ ВЫСОКИЙ — сужает поиск с 500 строк до ~10-15

---

## Q27 — Mutation-Sensitive Line Detector

**Концепция:** Запустить mutmut на failing-файле (только!) с коротким таймаутом. Строки, где мутация меняет тест с PASS на FAIL, — это линии с "тонкой логикой", требующей внимания.

**Почему инновационно:**
- Coverage gap: "строка не была выполнена" — слабый сигнал
- SBFL: "строка выполнялась в failing тестах" — средний сигнал
- Mutation: "строка *критична* — малейшее изменение ломает тесты" — СИЛЬНЫЙ сигнал
- LLM 2025 paper (arXiv:2503.08182): mutation как генератор гипотез для LLM outperforms SBST

**Реализация:**
- `MutantResult` dataclass: `line: int`, `operator: str` (AOR/ROR/COR), `survived: bool`
- `run_focused_mutation(file_path, timeout_s=30)` — subprocess mutmut с `--paths-to-mutate`
- `MutationReport` dataclass: `survived_mutants`, `killed_mutants`, `mutation_score: float`
- `format_mutation_report(report, top_n=5)` → `## Mutation-Sensitive Lines`
- Tool: `mutation_probe` (permission: ASK)

**Caveat:** Медленный (30-120s). Только по явному запросу агента, не автоматически.

**Effort:** 2d | **Impact:** ВЫСОКИЙ для сложных логических ошибок

---

## Q27 — Causal Error Attribution (Bayesian)

**Концепция:** Байесовское обновление подозрения на каждый файл после каждой ошибки. Prior = ErrorLedger history, Likelihood = stack frame appearance, Posterior = ranked suspicion list.

**Формула:**
```
P(bug in file F | error E) ∝ P(error E | bug in F) × P(bug in F)
  P(error E | bug in F) = hits(F, E) / total_errors(E)  -- из ErrorLedger
  P(bug in F) = 1 - (1 - base_rate) ^ age_factor        -- prior
```

**Реализация:**
- `BayesianSuspicion` dataclass: `file_path: str`, `prior: float`, `likelihood: float`, `posterior: float`
- `BayesianAttributor` class: maintains `_priors: dict[str, float]` per file
- `update(error_record)` — Bayesian update from new ErrorRecord
- `get_ranked(top_n=10)` → sorted `list[BayesianSuspicion]`
- Inject `## Suspected Files (Bayesian)` into debugger context after error history

**Источник:** BayesFLo (arXiv:2403.08079), SmartFL (arXiv:2503.23224) — оба подтвердили что Bayesian лучше pure-SBFL при multiple faults.

**Effort:** 1.5d | **Impact:** СРЕДНИЙ (особенно полезен в multi-fault scenarios)

---

## Q28 — LLM Hypothesis Test Loop (RepairAgent-style)

**Концепция:** Вместо одного LLM-вызова для генерации гипотез — цикл GATHER→GENERATE→VALIDATE с tool-use на каждом шаге. Inspired by RepairAgent (ICSE 2025), который фиксил 164 Defects4J bugs.

**Конечный автомат:**
```
GATHER_INFO → GENERATE_HYPOTHESIS → VALIDATE_FIX → GATHER_INFO (if fail) | DONE (if pass)
```

**Реализация в graph.py:**
- Новый граф-маршрут: `execute_debugger_loop` вместо `execute`
- State: `{hypotheses: [], patches_tried: [], current_hypothesis_index: 0}`
- Agent tools в debugger loop: `file_read`, `grep`, `bash` (run tests), `file_edit`
- Ограничение: max 3 hypothesis rounds (configurable via `AgentsConfig.debug_max_rounds`)
- Termination: тесты проходят OR max_rounds исчерпан

**Почему это ДРУГОЕ чем текущий `auto_debug`:**
- Текущий `auto_debug`: просто trigger debugger agent один раз при N errors
- RepairAgent loop: structured multi-round with hypothesis validation

**Effort:** 3d | **Impact:** ОЧЕНЬ ВЫСОКИЙ для сложных bugs (30-40% improvement per RepairAgent paper)

---

## Q28 — Coverage-Guided Test Amplification

**Концепция:** Взять uncovered branches из Q25, передать их в test_autopilot как target, сгенерировать тесты *специально для этих веток*. Подтверждено 2025 research (arXiv:2602.21997): −40% токенов, +coverage.

**Алгоритм:**
1. Запустить `coverage_guard` (Q25) → получить `missing_branches`
2. Для каждой ветки `(from_line, to_line)`: прочитать код, понять условие ветки
3. Сгенерировать тест специально для этой ветки через LLM
4. Проверить coverage после каждого добавленного теста
5. Повторять до threshold достигнут или budget исчерпан

**Интеграция:**
- Расширить `TestAutopilotTool` параметром `target_branches: list[tuple[int,int]]`
- Новый метод `_build_branch_test_prompt(file_path, branch, source_context)` → str
- `AgentsConfig.test_amplification: bool = False` (opt-in)

**Effort:** 2d | **Impact:** ВЫСОКИЙ — coverage-gap тесты сейчас полностью ручные

---

## Q29 — Error Trend Analyzer

**Концепция:** Временной ряд из ErrorLedger + визуализация трендов: "эта ошибка стала появляться чаще", "патч от 3 недель назад перестал работать", "fix effectiveness: 67%".

**Метрики:**
- **Frequency slope**: linear regression по `(timestamp, occurrence_count)` — растёт или падает?
- **Fix effectiveness**: `fixed_errors / recurring_errors` за sliding window 7d
- **Recurrence rate**: сколько "fixed" ошибок вернулись после патча
- **MTTR** (Mean Time To Repair): `avg(fix_timestamp - first_seen)` из ledger

**Реализация:**
- `ErrorTrend` dataclass: `error_hash`, `slope: float`, `trend: str` (GROWING/STABLE/DECLINING), `fix_effectiveness: float`
- `compute_trends(ledger, window_days=30)` → `list[ErrorTrend]`
- CLI: `/errors --trends` — показывает ASCII спарклайны per error hash
- Inject в `## Pre-planning Snapshot` при `trend == GROWING`

**Effort:** 1.5d | **Impact:** ВЫСОКИЙ для долгоживущих проектов с историей

---

## Q29 — Semantic Code Smell Detector

**Концепция:** AST-based + ML-based детектор code smells как сигнал риска ПЕРЕД ошибками. Расширяет Q19 `ASTCheckerTool` до 20+ правил.

**Новые правила (сверх существующих 12):**
- `god_function`: функция > 50 строк + > 5 параметров
- `deep_nesting`: >4 уровня вложенности if/for/try
- `boolean_blindness`: `def f(x, y, flag: bool)` — bool параметры = source of bugs
- `temporal_coupling`: функции, которые ДОЛЖНЫ вызываться в определённом порядке (heuristic: `_init`, `_setup` в документации)
- `implicit_none_return`: функция возвращает `None` в одной ветке и значение в другой
- `wide_interface`: class с >15 public methods — сложно тестировать
- `feature_envy`: функция использует больше полей другого класса чем своего

**Реализация:**
- Расширить `src/lidco/tools/ast_checker.py` — добавить 8 новых правил
- `RiskLevel` enum: CRITICAL/HIGH/MEDIUM/LOW для каждого правила
- Интеграция с `risk_scorer.py` (Q26) — smells contributes to risk score

**Effort:** 1.5d | **Impact:** СРЕДНИЙ (preventive) — prevents bugs before they happen

---

## Q30 — Distributed Debug Intelligence (Team-scale)

**Концепция:** Сейчас ErrorLedger — SQLite, single-user. Для командной работы нужна shared база с агрегацией across developers.

**Архитектура:**
- **Local** (текущее): `.lidco/error_ledger.db` — per-developer
- **Shared** (Q30): HTTP sync endpoint или git-tracked JSON aggregator
- `LedgerSyncProtocol`: `push_new_records()`, `pull_recent(since)`, `merge_duplicates()`
- Conflict resolution: last-writer-wins для fix_applied, sum для occurrences

**Use cases:**
- "Эта ошибка уже была у Николая 2 недели назад — и вот как он её пофиксил"
- "Топ-3 рекуррентных ошибки команды за неделю"
- Team fix knowledge base (shared FixMemory)

**Effort:** 3d+ | **Impact:** ОЧЕНЬ ВЫСОКИЙ для команд, но требует инфраструктуры

---

## Q30 — LLM Error Severity Classifier

**Концепция:** Классифицировать каждый `ErrorRecord` по severity (CRITICAL/HIGH/MEDIUM/LOW) используя cheap LLM call, аналогично Sentry alert triage.

**Логика:**
- **CRITICAL**: тест падает в CI + файл HIGH_RISK + recurring в 3+ сессиях
- **HIGH**: assertion failure + not covered by passing tests
- **MEDIUM**: import/syntax error + first-seen
- **LOW**: timeout/resource, single occurrence

**Реализация:**
- `ErrorSeverity` enum: CRITICAL/HIGH/MEDIUM/LOW
- `classify_severity(record, ledger, risk_scores)` — rule-based (no LLM needed для 90% случаев)
- LLM fallback только для "неоднозначных" случаев (confidence < 0.7)
- Sort `errors --history` по severity DESC вместо chronological

**Effort:** 1d | **Impact:** ВЫСОКИЙ — приоритизация значительно улучшает UX

---

## Инновационный синтез — "Trace-Guided SBFL+Slice Debugging"

**Пионерская техника, которую не делает никакой другой инструмент:**

Объединение трёх сигналов для построения минимального debug context для LLM:

```
Step 1: Ochiai SBFL → top-5 suspicious lines (statistical)
Step 2: TraceRecorder → capture variable state at each suspicious line (dynamic)
Step 3: BackwardSlice from most anomalous variable → minimal statement set (causal)

Result: ## Trace-Guided Suspicion Map
  Line 47 (score=0.87): x = config.get('timeout', None)
    ↳ ANOMALY: x is None in failing run, was 30 in 12 passing runs
    ↳ BACKWARD SLICE: assignments at lines [12, 47, 89]
    ↳ ROOT CAUSE CANDIDATE: line 12 — config initialized without 'timeout' key
```

**Почему это работает:** LLM получает не "посмотри на файл 500 строк", а "вот 3 строки, где математически гарантированно находится баг, и вот конкретное значение которое пошло не так".

**Реализация:** Q26 (SBFL + Trace) + Q27 (Backward Slice) = полный пайплайн.

---

## Приоритет реализации

| Квартал | Техника | Effort | Impact |
|---------|---------|--------|--------|
| Q26 | Ochiai SBFL | 1d | ★★★★★ |
| Q26 | Semantic Fingerprint | 0.5d | ★★★★ |
| Q26 | Trace Recorder (LDB) | 1.5d | ★★★★★ |
| Q26 | File Risk Score | 1d | ★★★★ |
| Q26 | Delta Debugger | 1.5d | ★★★ |
| Q27 | Backward Slice | 2d | ★★★★★ |
| Q27 | Mutation Probe | 2d | ★★★★ |
| Q27 | Bayesian Attributor | 1.5d | ★★★ |
| Q28 | RepairAgent Loop | 3d | ★★★★★ |
| Q28 | Coverage Test Amplification | 2d | ★★★★ |
| Q29 | Error Trend Analyzer | 1.5d | ★★★★ |
| Q29 | Code Smell (20+ rules) | 1.5d | ★★★ |
| Q30 | Error Severity Classifier | 1d | ★★★★ |
| Q30 | Distributed Ledger | 3d+ | ★★★★★ (for teams) |

---

## Источники

- [FauxPy SBFL tool (arXiv:2404.18596)](https://arxiv.org/abs/2404.18596)
- [Empirical Study SBFL on Python (EMSE 2024)](https://link.springer.com/article/10.1007/s10664-024-10475-3)
- [LDB Execution Trace Debugging (ACL 2024)](https://arxiv.org/abs/2402.16906)
- [RepairAgent: Autonomous LLM APR (ICSE 2025)](https://dl.acm.org/doi/10.1109/ICSE55347.2025.00157)
- [Mutation Testing via LLM Scientific Debugging (arXiv:2503.08182)](https://arxiv.org/abs/2503.08182)
- [BayesFLo: Bayesian Fault Localization (arXiv:2403.08079)](https://arxiv.org/abs/2403.08079)
- [SmartFL: Semantics-Based Probabilistic FL (arXiv:2503.23224)](https://arxiv.org/html/2503.23224)
- [Sentry AI-Powered Issue Grouping (−40% noise)](https://blog.sentry.io/how-sentry-decreased-issue-noise-with-ai/)
- [DDMIN* Fixed-Point Iteration (Wiley 2024)](https://onlinelibrary.wiley.com/doi/10.1002/smr.2702)
- [Predictive Program Slicing (ACM OOPSLA 2024)](https://dl.acm.org/doi/10.1145/3643739)
- [Coverage-Feedback Test Generation (arXiv:2602.21997)](https://arxiv.org/html/2602.21997)
- [AgentFL: Project-Level Multi-Agent FL (arXiv:2403.16362)](https://arxiv.org/abs/2403.16362)
- [The Debugging Book — Delta Debugger, Slicer](https://www.debuggingbook.org)
