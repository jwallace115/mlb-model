# 2026-05-12 Session Rebase Hash Mappings

## Purpose

`shared/git_push.sh` may rebase local commits onto a moved `origin/main`, producing new origin hashes while preserving commit content. This artifact maps local/session hashes to their durable origin hashes so future sessions do not conclude that commits were lost.

## Scope

This artifact covers May 12, 2026 session pushes only.

Prior-session mappings, including WNBA registry mapping `4dd98546` → `63fb5713`, are out of scope and should be captured separately if needed.

## Verification Method

Mappings were verified by matching exact commit messages on `origin/main` with:

```
git log --oneline origin/main --grep="<exact commit message>"
```

Each mapping returned exactly one match. All mappings are VERIFIED.

## Mapping Table

### Rebased commits (local hash differs from origin hash)

| Local/session hash | Origin hash | Commit message | Verification | Notes |
|---|---|---|---|---|
| `be4f3fc0` | `538cdeea` | docs: add MLB system registry review | VERIFIED | Rebased during git_push.sh |
| `9ebc6ddb` | `69a85fec` | docs: add MLB system registry v2 | VERIFIED | Rebased during git_push.sh |
| `2acf51fc` | `fcc6af72` | feat: add standalone P09 shadow runner | VERIFIED | Rebased during git_push.sh |
| `a109934b` | `b05dc137` | docs: verify P09 runner feature identity | VERIFIED | Rebased during git_push.sh |
| `5bf2f2dd` | `58a5452f` | docs: reconcile P09 feature identity verdict | VERIFIED | Rebased during git_push.sh |

### Non-rebased commits (local hash preserved on origin)

| Local/session hash | Origin hash | Commit message | Verification | Notes |
|---|---|---|---|---|
| `192add48` | `192add48` | docs: add P09 standalone shadow spec | VERIFIED | No rebase; hash preserved |
| `94e49089` | `94e49089` | docs: accept P09 spec v1 with PIT implementation caveat | VERIFIED | No rebase; hash preserved |
| `219e7a6d` | `219e7a6d` | docs: P09 PIT verification and open-question resolution | VERIFIED | No rebase; hash preserved |
| `7de14f25` | `7de14f25` | docs: P09 canonical sportsbook = DraftKings, alt-book capture preferred | VERIFIED | No rebase; hash preserved |
| `7d3b1050` | `7d3b1050` | docs: add P09 preflight verification | VERIFIED | No rebase; hash preserved |
| `e0c083b4` | `e0c083b4` | feat: add P09 shadow grading utility | VERIFIED | No rebase; hash preserved |

## Current P09 Origin Chain

Durable origin hashes for the P09 standalone shadow tracker (in chronological order):

- `192add48` — P09 standalone shadow spec v1
- `94e49089` — spec review acceptance
- `219e7a6d` — PIT verification and open-question resolution
- `7de14f25` — canonical sportsbook = DraftKings
- `7d3b1050` — preflight verification (all 7 gates PASS)
- `fcc6af72` — standalone P09 shadow runner
- `b05dc137` — feature-identity check
- `58a5452f` — verdict reconciliation
- `e0c083b4` — P09 shadow grading utility

## Audit Note

Future references should prefer origin hashes. If older session notes mention local/session hashes, use this mapping artifact before concluding a commit is missing.
