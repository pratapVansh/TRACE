# Salvaged: report-generation prompts

Extracted from `backend/app/agents/framework/agents/report_tools.py`
(`ReportGenerationTool` and `ExecutiveSummaryTool`) before the agent framework
was deleted. **This is prompt text kept for reference, not working code.**
Nothing imports it and nothing runs it.

## What this was for

The agent framework registered a `report_generation` tool and a
`ReportGenerationAgent` that routed on words like "report", "executive
summary" and "incident report". The intent was: a user asks for a compliance
or incident report, prior agents in the workflow deposit their findings, and
the report agent renders those findings into a fixed section structure with
strict anti-fabrication rules.

## Why only the prompts survived

The module itself was not portable. It depended on `FrameworkTool`,
`ToolMetadata`, `ToolContext` and three `ToolContext` accumulators
(`build_conversation_summary`, `build_accumulated_findings`,
`build_accumulated_evidence`) that read multi-agent DAG state — prior agent
outputs and `metadata["step_outputs"]` — which has no equivalent outside the
framework.

**More decisively: it never ran.** `ReportGenerationAgent` opened with a
zero-evidence guard on `context.retrieved_documents`, and that field was
never written on any live path — `PlanExecutor` called
`init_working(task=question)` without documents, and the only other writer
(`WorkingMemory.add_entry`) had no callers anywhere in the codebase. Verified
by execution before deletion:

```
context.retrieved_documents = []
confidence: 0.0
tools_used: []
answer: '## No Supporting Evidence Found ...'
```

Every request for a report returned the no-evidence stub. `report_generation`
was never invoked.

## What was deliberately NOT kept

`_build_report_prompt`'s companion `_fallback_report` is **not** reproduced
here. It emitted placeholder scaffolding — `[To be determined]`, `[Date]`,
`[List parts]`, `[Pass/Fail]` — whenever the LLM was unavailable. That is
exactly the fabricated-looking output the product is removing: a document that
looks like a filled-in report but asserts nothing. If report generation is
ever rebuilt, the no-LLM path should refuse, not produce a shaped blank.

## The section templates

Appended to the prompt according to report type. The value here is the STRICT
RULES blocks — they are a reasonable anti-fabrication contract and worth
reusing verbatim.

### `incident`

```text
STRICT RULES:
- Never invent root causes, failure modes, or impact assessments.
- Every claim MUST be grounded in the reference data.
- If evidence is missing for a section, write: 'No supporting evidence found.'
Format as:
## Incident Report
### Incident Details
- Date/Time
- Location
- Equipment
### Description
### Findings
### Supporting Evidence
### Actions Taken
### Attachments/References
```

### `maintenance`

```text
STRICT RULES:
- Never invent part numbers, labor hours, schedules, or test results.
- Only include information present in the reference data.
- If evidence is missing, write: 'No supporting evidence found.'
Format as:
## Maintenance Report
### Equipment Info
### Maintenance Type
### Work Performed
### Findings
### Supporting Evidence
```

### `compliance`

```text
STRICT RULES:
- Never invent non-compliances or corrective actions not in evidence.
- Every finding MUST cite specific reference documents.
- If evidence is missing, write: 'No supporting evidence found.'
Format as:
## Compliance Report
### Scope
### Standards Referenced
### Findings
### Evidence
### Recommendations
```

## The prompt skeleton

Assembled by `_build_report_prompt(rtype, title, ctx, author, docs, ...)`
before the section template above was appended:

```text
Generate a {rtype} report.
Title: {title}
Author: {author}

User notes:
{ctx}

## Conversation History      <- only when non-empty
{conversation_summary}

## Prior Findings            <- only when non-empty
{accumulated_findings}

## Prior Evidence            <- only when non-empty
{accumulated_evidence}

## Reference Documents       <- top 3 retrieved passages
{docs[:3]}
```

Retrieval used the concatenation of `title`, the user's request, the report
type and the first 200 characters of the conversation summary as its query,
taking the top 5 passages.

## Executive summary prompt

From `ExecutiveSummaryTool`, which was registered but never invoked by any
agent:

```text
Generate a {audience}-focused executive summary from the following content.
Use at most {max_bullets} bullet points. Keep each point concise.

Content:
{content[:4000]}
```

`audience` was one of `executive` | `technical` | `general`; `max_bullets`
was capped at 10.

## If this is rebuilt

It is a new feature, not a port. Three things need deciding that the framework
never settled:

1. **A trigger.** There is no way for a Copilot user to ask for a report as a
   report. Routing on the word "report" was the framework's answer and it is
   not a good one.
2. **What fills the sections.** The Copilot has conversation history and
   retrieved chunks; it has no notion of "prior agent findings".
3. **The empty case.** See `_fallback_report` above — refuse rather than
   render a blank form.
