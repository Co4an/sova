# Сова — продвинутая работа с Excel

Use for workbook creation, modification and formula/model review. The goal is an
editable, correctly calculated workbook meeting the assignment, with evidence of
checks. Complexity is determined by the assignment, not by using complex formulas.

## Choose the execution surface

Read the assignment and inspect supplied workbooks before choosing tools. Extract
required Excel version/platform, deliverable format, formulas and native features.
Use native host skills for supported spreadsheet operations. No external LLM or
search API is required. Each host still supplies its own model and permissions.

- File task: use the host's spreadsheet authoring skill and required runtime. In
  Codex prefer the available Spreadsheets skill. If no such tool exists in another
  host, choose available local workbook libraries, disclosing unsupported features.
- Explicitly requested live Microsoft Excel task: follow the host's live Excel
  workflow and setup gates. Discover actual connected capabilities before calling
  them. Installation of Excel alone does not establish an automation connection.
- If the task requires Excel-specific execution, arrange actual Microsoft Excel
  validation through an available supported connection. Do not claim native Excel
  verification based on a Python library, file inspection or LibreOffice export.
- CLI-Anything is optional, not an assumed capability. Inspect the actual adapter's
  commands, dependencies and preservation limits. Its LibreOffice adapter is a
  LibreOffice route; it is not a native Microsoft Excel adapter. Do not convert a
  sophisticated supplied workbook through its intermediate format merely to gain
  CLI access. Do not install it automatically as a prerequisite for Excel work.
- Never invent support for Power Query, Power Pivot/DAX, Solver, VBA, dynamic arrays,
  native What-If Data Tables, cube functions or external data refresh. Determine
  whether the intended Excel version and selected tools support each required feature.
  Native required features must remain native; static substitutes do not satisfy them.

## Prepare an auditable working folder

Use `research/<task-name>/` or the user's chosen output location. Keep original files
unchanged and work on a copy unless editing the original is explicitly requested.
Use the original format where features require it, e.g. preserve .xlsm for macros.

Record the assignment requirements and planned implementation in
`excel-requirements.md`: requirement → sheet/range or native object → verification.
Use `excel-checks.md` for actual test inputs, expected outcomes, observed outcomes,
engine/version and unverified items. Save state in `excel-state.json` with
`stage` (inspect/build/verify/complete/needs_review), `revisions` and working file path.
This is a file checkpoint, not a background process or automatic Excel connection.
Do not use research project.py's report/citation gates for a pure spreadsheet task.

Before edits inventory sheets including hidden ones, key formulas, names, tables,
charts, pivots, validation, conditional formatting, external links, data connections,
macros and protection. Preserve unaffected content and native objects. For a new
workbook, derive a simple structure from the assignment. Keep inputs, calculations
and outputs traceable; they need not each have their own sheet.

## Build formulas and analysis

- Use actual Excel formulas where the task requires editable calculations. Do not
  replace formulas with Python-computed constants or fabricate cached results.
- Choose appropriate functions: SUMIFS/COUNTIFS, XLOOKUP or INDEX/MATCH, dynamic
  arrays, LET, date, financial or statistical functions when useful and supported.
  Preserve required named ranges and structured table references.
- Audit absolute/relative anchors, copy boundaries, units, periods, sign conventions,
  lookup matching mode, missing/duplicate keys and empty values versus zeros.
- Keep input assumptions explicit. Avoid unexplained constants embedded in formulas
  and blanket IFERROR(...,0) that hides missing data or broken logic. Legitimate
  handling of a missing value must remain visible and follow the assignment.
- For financial models reconcile appropriate totals, cash flow and roll-forwards.
  For statistical work verify definitions, sample/population choices, units and
  assumptions. These checks are task-specific; do not add unrelated modelling.
- Preserve existing macros and links without running untrusted code or updating
  external connections merely because a workbook contains them.

## Verification — all applicable layers

1. **Requirement coverage:** verify the actual formula or native object for every
   requested item. Inspect first, middle and last copied formulas and period edges.
   No arbitrary formula count proves quality.
2. **Independent arithmetic:** calculate representative critical outputs with a
   separate method from the workbook formula. Trace inputs to original data and
   reconcile totals. A check that repeats the same erroneous formula is insufficient.
3. **Engine recalculation:** in a disposable copy change representative inputs and
   confirm dependent formulas, summaries and charts update; restore original inputs.
   Record engine/version. fullCalcOnLoad, a successful save, a cached number and a
   zero error count are not proof that formulas were recalculated correctly.
4. **Boundary and scenario tests:** where relevant test zero, blank, missing lookup,
   duplicates, dates on period boundaries and rounding. If scenarios are required,
   change the selector and a driver and verify the intended calculations update.
   Actual historical values should remain intact.
5. **Formula/native feature inspection:** locate #REF!, #DIV/0!, #VALUE!, #NAME?,
   #N/A, #NUM!, #NULL!, #SPILL!, #CALC! and unexpected circular references. Separate
   deliberate missing-data markers from faults. Verify required pivots, Solver,
   Data Tables, macros, queries and other features in their intended engine. Inspect
   the delivered saved file again when export or conversion can affect those features.
6. **Visual review:** render or inspect all affected sheets and dependent outputs.
   Check clipped text, #### displays, number formats, headings, validation and charts.
7. **Critic:** if available/authorized, give a fresh reviewer the assignment, original,
   modified workbook and check evidence. It reviews logic and coverage, not just
   appearance. Otherwise label a separate self-review honestly. Up to three fix cycles.

For saved .xlsx/.xlsm files, the optional read-only structural helper is:

```text
python3 <skill-dir>/scripts/excel_audit.py <book.xlsx> --out <work-dir>/excel-audit.json
```

It inventories some native package features and scans stored cells for cached
errors, #REF! tokens, missing formula caches, manual calculation and external links.
It has no dependencies and does not execute macros, formulas or network calls.
Exit 2 means detected structural errors, 1 means audit could not run, and 0 only
means no detected hard structural errors. Its `recalculation_verified` is always
false. Shared/array formulas, dependency chains, mathematical correctness and native
features still require the other checks. Encrypted files, .xls and .xlsb require
supported host/native readers; do not rename or silently convert them for this helper.

## Finish honestly

Set complete only after assignment coverage and all required checks are satisfied.
If target-engine checks are blocked, record needs_review and state the exact missing
check, even if file creation and static checks succeeded. Preserve the useful draft.
Do not claim "error-free" or "verified in Excel" without applicable evidence.
Deliver the workbook and a brief account of performed checks and material limitations;
keep build scripts and diagnostic artifacts in the work folder unless requested.

## CLI-Anything finding

Checked 2026-10-16 against the project repository, not third-party marketing pages.
The generator builds application-specific CLI harnesses and relies on available
source code. The examined LibreOffice adapter stores cell/formula data in a project
model and exports XLSX through an ODF intermediate plus LibreOffice conversion.
This does not establish a complete, fidelity-preserving native Excel workflow.

Sources:
- https://github.com/HKUDS/CLI-Anything (installation and limitations)
- https://github.com/HKUDS/CLI-Anything/blob/main/libreoffice/agent-harness/cli_anything/libreoffice/core/calc.py
- https://github.com/HKUDS/CLI-Anything/blob/main/libreoffice/agent-harness/cli_anything/libreoffice/core/export.py
