# Issue tracker: GitHub

Issues and PRDs for this repository live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue:** `gh issue create --title "..." --body-file <path>`.
- **Read an issue:** `gh issue view <number> --comments`, including its labels.
- **List issues:** `gh issue list --state open --json number,title,body,labels,comments`, with suitable label and state filters.
- **Comment on an issue:** `gh issue comment <number> --body "..."`.
- **Apply or remove labels:** `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- **Close an issue:** `gh issue close <number> --comment "..."`.

Infer the repository from `git remote -v`; `gh` does this automatically when run inside the clone.

## Pull requests as a triage surface

**PRs as a request surface: no.** External pull requests are not included in the issue triage queue.

## Skill terminology

- When a skill says "publish to the issue tracker", create a GitHub issue.
- When a skill says "fetch the relevant ticket", run `gh issue view <number> --comments`.
