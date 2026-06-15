# ThreadOS — Notification Architecture

Defines every channel through which the automation system reaches the founder,
what triggers each notification, and how to set each one up.

The design constraint: **no custom notification server**. Every notification travels
through GitHub's existing email/mobile infrastructure. There is nothing to host,
nothing to monitor, and nothing that can silently fail.

---

## Notification Channels

### Primary — GitHub Email (`vencyjain143@gmail.com`)

GitHub sends email automatically when:

| Event | Email trigger | No setup needed |
|-------|---------------|-----------------|
| Auto-sprint PR opened | "You've been assigned" or "New PR on repo you watch" | Watch the repo |
| PR CI passes | "All checks passed on #N" | Enable Actions notifications |
| PR CI fails | "Checks failed on #N" | Enable Actions notifications |
| Escalation issue opened and assigned | "You've been assigned to issue #N" | Watch the repo |
| Escalation issue commented on | "New comment on issue #N" | Subscribe to the issue |
| Advisory escalation reminder | "New comment on issue #N" | Automatic on issue assignment |

**Setup:** GitHub → Settings → Notifications:
- Watching: `vencyjain800-del/threados` → "All Activity"
- Email: enabled for "Pull Requests" and "Issues"
- Actions: enabled for "Failed workflows only" (CI passes are less urgent)

### Secondary — GitHub Mobile App

Install GitHub's mobile app (iOS or Android) for push notifications. Same events as email,
but arrives faster and is visible on lock screen.

**Push notifications to enable:**
- Assigned issues
- Pull request reviews requested
- CI failures
- Mentions in comments

### Tertiary — GitHub Web (polling fallback)

For any notification that slips through, the founder can visit
`github.com/vencyjain800-del/threados` and see all open PRs and issues in the Issues tab.

---

## Notification Event Map

Every notification Claude sends maps to exactly one GitHub action:

```
Sprint complete          → PR opened (auto-sprint label)
                           → GitHub emails: "New PR opened"
                           → Mobile push: "PR ready for review"

CI passes on PR          → GitHub emails: "All checks passed"
                           (no Claude action required)

CI fails on PR           → GitHub emails: "Checks failed"
                           → Claude pushes a fix commit (no separate notification)
                           → CI re-runs automatically

Escalation triggered     → Issue opened with [Escalation] title + assigned to founder
                           → GitHub emails: "Assigned to issue #N"
                           → Mobile push: "Assigned to issue"

PR open 72 hours         → Claude comments on the PR: "Awaiting review — 72h reminder"
                           → GitHub emails: "New comment on PR #N"

PR open 7 days           → Claude opens escalation issue (see ESCALATION_POLICY.md)
                           → GitHub emails: "Assigned to issue #N"

Roadmap exhausted        → Claude opens issue: "[Automation] Roadmap exhausted"
                           → No assignment (informational only)

Advisory escalation      → Claude comments on advisory issue after window expires
                           → GitHub emails: "New comment on issue #N"

Weekly health report     → Claude opens issue: "[Weekly] Automation health — YYYY-MM-DD"
                           → No assignment (informational only)
```

---

## What the Founder Sees Per Sprint

Assuming a normal sprint with no escalations:

1. **Email #1 (sprint start + few minutes):** "New PR: [Auto] Sprint N — {title}"
2. **Email #2 (CI passes, ~5 minutes later):** "All checks passed on PR #N"
3. **Founder action:** Open PR → read two-line summary comment → click Merge

Total founder time per sprint: **under 2 minutes**.

If CI fails:

1. **Email #1:** "New PR: [Auto] Sprint N — {title}"
2. **Email #2:** "Checks failed on PR #N"
3. Claude detects failure, pushes fix, CI re-runs
4. **Email #3:** "All checks passed on PR #N"
5. Founder action: same as above

If escalation:

1. **Email #1:** "Assigned to issue #N — [Escalation] {reason}"
2. Founder reads the structured escalation body
3. Founder closes issue with a comment (or comments without closing)
4. Claude resumes on the next session trigger

---

## Notification Anti-Patterns to Avoid

These patterns would create noise and train the founder to ignore notifications:

| Anti-pattern | Why it's bad | What to do instead |
|---|---|---|
| Notifying on every file save or test run | Notification fatigue | Only notify on PR open and escalation |
| Opening multiple issues for the same escalation | Inbox flooding | Reuse the same issue; add a comment |
| Notifying before CI has had a chance to run | False urgency | Wait for CI to pass before expecting review |
| Weekly health report sent as email | Low-signal noise | Open as a GitHub issue; founder reads if curious |
| Slack/SMS/webhook fallback channels | Infrastructure to maintain | GitHub email is reliable enough |

---

## How Claude Sends Notifications (Technical)

All notifications are sent via the GitHub REST API using the PAT stored in Windows
Credential Manager at target `git:https://github.com`. The token is read once per session,
used for all API calls, and never written to any file.

### PR open

```http
POST /repos/vencyjain800-del/threados/pulls
Authorization: Bearer {token}
Content-Type: application/json

{
  "title": "[Auto] Sprint {N} — {issue title}",
  "body": "{sprint delivery report + review checklist}",
  "head": "auto-sprint-{N}",
  "base": "main"
}
```

### Label PR

```http
POST /repos/vencyjain800-del/threados/issues/{pr_number}/labels
{ "labels": ["auto-sprint", "{roadmap-group}"] }
```

### 72-hour reminder comment

```http
POST /repos/vencyjain800-del/threados/issues/{pr_number}/comments
{ "body": "⏰ 72-hour reminder: this PR is awaiting review." }
```

### Escalation issue

```http
POST /repos/vencyjain800-del/threados/issues
{
  "title": "[Escalation] {reason}",
  "body": "{escalation template — see ESCALATION_POLICY.md}",
  "labels": ["escalation"],
  "assignees": ["{founder_github_username}"]
}
```

### Check for open auto-sprint PRs (session startup guard)

```http
GET /repos/vencyjain800-del/threados/pulls?state=open&labels=auto-sprint
```

Returns an array. If non-empty, the previous sprint's PR is unmerged — do not start a new sprint.

---

## Setup Checklist (one-time, done by founder)

```
[ ] Watch the repo: github.com/vencyjain800-del/threados → Watch → All Activity
[ ] Verify GitHub sends email to vencyjain143@gmail.com (Settings → Emails)
[ ] Enable email notifications for Issues and Pull Requests (Settings → Notifications)
[ ] Enable Actions email for workflow failures (Settings → Notifications → GitHub Actions)
[ ] Install GitHub mobile app and sign in
[ ] Enable mobile push for: Assigned issues, PR review requests, Mentions
[ ] Create label `auto-sprint` on the repo (Settings → Labels)
[ ] Create label `escalation` on the repo (Settings → Labels, colour: #e11d48)
[ ] Verify founder's GitHub username is the one receiving assignments
     (edit ESCALATION_POLICY.md assignees line if different)
```

Total setup time: approximately 10 minutes.

---

## Degraded Mode

If GitHub email stops working for any reason:

1. GitHub mobile push still fires (separate delivery path)
2. The founder can check `github.com/vencyjain800-del/threados/pulls` directly
3. No automation work is lost — PRs and issues persist on GitHub regardless

There is no scenario where Claude's work is invisible to the founder as long as
the GitHub repo is accessible.
