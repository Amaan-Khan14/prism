<!-- codedocket:begin -->
## Project knowledge (codedocket)

This repo accumulates project understanding — decisions, constraints, bugs,
assumptions, rationale — in `.codedocket/knowledge.json`. It exists so you do not
re-derive what is already known.

**Read first.** Before planning or editing unfamiliar areas, query it:
- MCP tools: `codedocket_explore` (query for topics, paths for files you will touch,
  key for exact lookup, include_superseded for history).
- CLI: `codedocket explore --query <topic>` or `codedocket explore --path <paths>`.
- Fallback: read `.codedocket/knowledge.json` directly — it is plain JSON.
Statuses matter: `superseded` = historical position, kept for history — do not
follow it; `disputed` = contested — weigh in or proceed carefully. Scope `.`
means project-wide.

**Record what you learn.** When you discover something non-obvious — a
decision and its why, a constraint, a bug's root cause, an assumption —
record it so the next session does not rediscover it:
- MCP tools: `codedocket_record`; CLI: `codedocket record --key K --kind K --statement S --scope P`.
- Key: a stable dot.case slug naming the TOPIC, e.g. `storage.format`.
  One decision per key.
- Kind: decision | constraint | bug | assumption | rationale | fact.
- Statement: the current position, 1-2 sentences.
- Scope: paths it applies to (`.` for project-wide).
- Do not duplicate: explore first; same topic -> record again with the SAME
  key (re-observation strengthens it). A decision replacing an earlier one ->
  new key + `supersedes`.
- `codedocket_dispute` flags knowledge as contested; it is not a correction mechanism —
  correct by recording.

**Capture without interrupting.** Structure on demand, not mid-execution:
- Mid-task, when you learn something non-obvious but are busy executing:
  `codedocket_note` (MCP) / `codedocket note "one sentence"` (CLI) —
  no key, no kind; it is reviewed at session end.
- When finishing (your client's Stop hook may insist): run
  `codedocket finalize`, then for each proposal record it — `codedocket_record`
  with the note text as evidence note and the session id shown — or skip it
  deliberately.
<!-- codedocket:end -->

<!-- BEGIN AWS Agent Toolkit rules -->
# AWS Guidance

- Where these AWS rules conflict with the project's own instructions, the
  project's instructions take precedence.
- Prefer the AWS MCP Server for AWS interactions — it provides sandboxed
  execution, observability, and audit logging. If unavailable, use the
  AWS CLI directly.
- Before starting a task, check whether a relevant AWS skill is available.
  Load the skill with `retrieve_skill` and prefer its guidance over
  general knowledge.
- When uncertain about specific AWS details (API parameters, permissions,
  limits, error codes), verify against documentation rather than guessing.
  State uncertainty explicitly if you cannot confirm.
- When creating infrastructure, prefer infrastructure-as-code (AWS CDK or
  CloudFormation) over direct CLI commands.
- When working with infrastructure, follow AWS Well-Architected Framework
  principles.
- Do not use em dashes in AWS resource names or descriptions. Use
  hyphens instead.

## Secret Safety

- MUST load the `aws-secrets-manager` skill first for any secret,
  credential, API key, token, or password task. MUST NOT call
  `secretsmanager get-secret-value` or `batch-get-secret-value`, and MUST
  NOT hit the Secrets Manager Agent daemon directly. MUST use
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` with
  `asm-exec` so the secret resolves at runtime without entering context.
<!-- END AWS Agent Toolkit rules -->

## PRism AWS Scope

- Limit AWS resource reads and changes to resources created for PRism. Do not modify unrelated or shared account resources.
- Before provisioning PRism resources, identify the PRism project resources by their names, tags, or infrastructure-as-code stack and keep changes within that boundary.
