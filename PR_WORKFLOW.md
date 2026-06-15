# ThreadOS — PR Workflow

Defines exactly how Claude opens, labels, and closes pull requests. This is the
mechanical contract between the automation system and the founder's review process.

---

## Principles

1. **One sprint, one PR.** Each sprint is one atomic PR against `main`. No stacked PRs,
   no draft PRs that stay open for multiple sessions.

2. **PRs are opened by Claude, merged by the founder.** Claude never merges to `main`.
   The founder's merge is the approval signal.

3. **A PR not merged within 7 days is escalated.** Claude will comment once after 72 hours
   ("Awaiting review") and open an escalation issue after 7 days if still unmerged.
   See `ESCALATION_POLICY.md`.

4. **CI must be green before the founder reviews.** If CI fails on a PR that Claude opened,
   Claude fixes the failure and force-pushes the branch. The founder should never see a
   red CI badge on an auto-sprint PR.

---

## Branch Naming

```
auto-sprint-{N}
```

Where `N` is the sprint number from `PROJECT_STATUS.md` Sprint History (e.g. `auto-sprint-14`).

If the branch already exists (e.g. a previous failed session), Claude deletes it and
recreates it from a fresh `main`.

---

## Commit Convention

Each sprint is a single commit (squash all session changes):

```
Sprint {N}: {issue title}

Issue: #{github_issue_number}
Tests: {baseline} → {new_count} ({delta:+d})
Files: {comma-separated list of changed files, max 5; "and N more" if > 5}
```

Example:
```
Sprint 13: Worker job duration metrics (O-02)

Issue: #8
Tests: 283 → 285 (+2)
Files: worker/jobs/forecast.py, worker/jobs/recommendations.py, worker/jobs/sync.py, tests/test_forecast.py, tests/test_recommendations.py
```

---

## PR Title and Body

**Title format:**
```
[Auto] Sprint {N} — {issue title}
```

Example: `[Auto] Sprint 13 — Worker job duration metrics`

**Body:** The full contents of `SPRINT_N_DELIVERY.md`, verbatim, followed by this footer:

```markdown
---

## Review Checklist

- [ ] CI is green
- [ ] Test delta is ≥ 0 (no tests removed)
- [ ] `PROJECT_STATUS.md` Sprint History updated
- [ ] No files outside task scope changed

**To approve:** merge this PR.
**To reject:** close this PR with a comment explaining why. Claude will not retry the same task
without a new instruction.
**To request changes:** leave a review comment. Claude will address it in the next session.
```

---

## Labels

Every auto-sprint PR gets exactly these labels:

| Label | Meaning |
|-------|---------|
| `auto-sprint` | Created by Claude automation |
| `observability` / `hardening` / `merchant-exp` / `platform` | Roadmap group of the issue |

Label for the roadmap group is derived from the issue's own label. If the issue has no group
label, use `auto-sprint` only.

---

## PR Opening Procedure (step-by-step)

Claude follows these steps at the end of every sprint, after all verification passes:

```
1. Confirm working directory is a git repo with remote origin pointing at
   vencyjain800-del/threados. If not, stop and escalate.

2. Fetch latest main:
   git fetch origin main

3. Create branch from origin/main (not local main):
   git checkout -b auto-sprint-{N} origin/main

4. Stage all changed files explicitly (never `git add .`):
   git add <file1> <file2> ...

5. Commit:
   git commit -m "{commit message as above}"

6. Push:
   git push -u origin auto-sprint-{N}

7. Open PR via GitHub API (PATCH /repos/vencyjain800-del/threados/pulls):
   {
     "title": "[Auto] Sprint {N} — {issue title}",
     "body": "<SPRINT_N_DELIVERY.md contents + review checklist>",
     "head": "auto-sprint-{N}",
     "base": "main",
     "draft": false
   }

8. Add labels via GitHub API:
   POST /repos/vencyjain800-del/threados/issues/{pr_number}/labels

9. Close the GitHub issue that was being worked on:
   PATCH /repos/vencyjain800-del/threados/issues/{issue_number}
   { "state": "closed" }

10. Post the PR URL as the final line of terminal output.
```

---

## After PR is Merged

When the founder merges the PR, GitHub closes the branch. Claude's next session detects
this by checking for open `auto-sprint` PRs at startup. If none are found, it proceeds
with the next sprint.

**Claude does not pull the merged changes to local `main`.** It always branches from
`origin/main` (step 3 above), which ensures the merged state is always the base.

---

## After PR is Closed Without Merging

If the founder closes a PR without merging:

1. Claude reads the closing comment on the next session startup.
2. If the comment explains a reason → Claude logs it as a note in `PROJECT_STATUS.md`
   under Known Issues and moves to the next roadmap item.
3. If no reason is given → Claude opens a GitHub issue labelled `escalation` asking
   for clarification before proceeding.

---

## Prohibited PR Actions

Claude must never:

- Merge a PR (not even via API)
- Force-push to `main`
- Delete branches on `main`
- Close a PR opened by a human
- Open more than one `auto-sprint` PR at a time
- Include secrets, credentials, or `.env` files in any commit
