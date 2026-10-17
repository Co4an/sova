# Roles and artifact formats

The current assistant is the coordinator. It owns plan.json, sources.json, state.json
and final artifacts. A native subagent receives a focused question, output path,
relevant assignment requirements, source standard, and permitted tools. It writes
only its assigned research note and returns findings, sources, contradictions and
limitations. Keep shared JSON writes out of parallel workers.

Use these role contracts:

| Role | Input | Output |
|---|---|---|
| Planner | Assignment and rubric | Requirements and bounded research questions |
| Web researcher | One question | Original sources with excerpts and dates |
| Academic researcher | One question | Relevant papers, methods and limitations |
| Data researcher | One question | Original statistics, units, periods and calculations |
| Analyst | Collected evidence | Arguments, alternatives and reproducible calculations |
| Writer | Requirements and analysis | Cited report |
| Critic | Assignment, sources, analysis and draft | Requirement coverage and substantive issues |

Researcher dispatch example:

> Investigate question `<question>` for assignment `<scope>`. Use available native
> search/files. Open original evidence; record title, URL/file, date, exact excerpt,
> page/section and limitations. Do not fabricate findings when access fails. Save
> only `research/<task-id>.md`. Do not modify shared state or draft. Return findings
> and evidence for merging by the coordinator.

Critic dispatch example:

> Review the assignment, plan, sources and draft independently. Inspect the cited
> excerpts/originals available to you. Identify unsupported claims, wrong numerical
> inputs, contradictions, unmet rubric and overstated certainty. Save only the
> specified review output. Use review.json format below; mark approved only when no
> material issues remain. Citation IDs alone do not establish support.

## Files

`assignment.md` holds the user's task and rubric. Keep user materials in `inputs/`
when copying is useful and permitted; references may point at original files.
All paths below are relative to a single run directory.

plan.json:

```json
{
  "requirements": ["Оценить международную стратегию с опорой на первоисточники"],
  "tasks": [
    {"id": "markets", "question": "Какие рынки выбраны и чем обоснован выбор?"},
    {"id": "performance", "question": "Какие показатели подтверждают результаты?"}
  ]
}
```

sources.json (example format only; replace with actual evidence):

```json
[
  {
    "id": "S1",
    "title": "Название исходного документа",
    "url": "https://example.org/original-report",
    "accessed": "2026-10-16",
    "evidence": "retrieved_text",
    "excerpt": "Короткая точная выдержка из прочитанного источника",
    "locator": "p. 12, International operations"
  }
]
```

For a local source, use `file` instead of `url`; resolve it from the run directory
or supply an absolute path. Allowed evidence types: retrieved_text, abstract,
search_excerpt, metadata_only. These describe access, not reliability. Do not mark
a snippet as full text. Include only short permitted quotes. Keep source IDs stable
across revisions. If you find a duplicate source, merge notes into its existing ID.

analysis.md contains reasoning with `[S1]` citations; report.md contains the draft
using the same IDs. Keep direct URLs in sources.json so the bibliography is traceable.

review.json:

```json
{
  "approved": false,
  "reviewer": "independent_agent",
  "issues": ["Региональные выводы не подтверждены источником"],
  "requirements": [
    {
      "requirement": "Оценить международную стратегию с опорой на первоисточники",
      "met": false
    }
  ]
}
```

Allowed reviewer values: independent_agent, human, self_review. Copy each actual
requirement exactly once from plan.json. Approval requires all met=true and no
issues. Record actual reviewer identity/context in a research note when useful.
No software validator can prove this identity or substantive support.

## Helper commands

Use a working Python 3.10+ executable supplied by the environment. Commands:

```text
python3 <skill-dir>/scripts/project.py init <run-dir> --task "Задание"
python3 <skill-dir>/scripts/project.py status <run-dir>
python3 <skill-dir>/scripts/project.py check <run-dir>
python3 <skill-dir>/scripts/project.py advance <run-dir>
```

Stage means work still to do: plan → research → analysis → draft → review.
Fill the current stage's files, then advance. Rejected reviews return to analysis
(up to three times); the fourth rejected review produces needs_review. An approved
review produces complete and final/report.md with source list. Save after each
substantive step. A resumed session reads state and continues the pending stage.
State is a local progress record, not a running background process.
