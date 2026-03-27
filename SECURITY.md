# Security Policy

## Reporting

Do not file sensitive disclosures in public issues.

`archility` is expected to inspect repository structure and architecture documentation, so bug reports should avoid exposing private paths, secrets, credentials, or unpublished internal service details.

## Scope

- Do not commit credentials, tokens, API keys, or local-only configuration.
- Do not commit unnecessary machine-specific absolute filesystem paths or other local-environment identifiers.
- Treat generated architecture summaries as potentially sensitive when they expose internal hosts, service names, or unpublished repository structure.
- Keep transient workflow notes in local-only `CHATHISTORY.md`.

## Safe Documentation Practices

- Prefer relative paths such as `./util-repos/archility` and `../..` in committed docs when they are sufficient.
- Keep durable guidance in tracked docs such as `AGENTS.md` and `LESSONSLEARNED.md`.
- Keep private architecture observations that should not be published out of tracked files.
