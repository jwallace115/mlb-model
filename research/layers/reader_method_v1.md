# Reader method v1 — how the AI turns the layers into picks (all sports)

Decided by Jeff 2026-09-27 (~14:20Z); written by Cowork. Applies to every sport in the Layers System from the first
slate frozen after this file is committed: NFL from Week 4 (Sun 2026-09-27), NCAAF from week 5, NHL from its pilot
(Tue 2026-09-29), NBA from its pilot (Tue 2026-10-20). Plan: `research/layers/LAYERS_GAMEPLAN_2026-09-27.md`.
A change to anything below is a NEW version (`reader_method_v2.md`), judged only on slates after its date (N62).

## 1. A side on every wager, with a reason
Every line on the slate gets a probability for its first side, a side (never "none"), a primary tag, the layers that
drove it (`drivers`), and a one-to-two-sentence reason. One side of every wager wins and one loses, and data not
recorded before the game can never be recreated — so we record all of it, even lines the reader barely cares about.
(Replaces the NFL `no_view` option for new slates; NHL H1 and NCAAF already work this way.)

## 2. Confidence and rank
Every line also gets:
- `conf` — 0 to 100: how strongly the reader wants THIS bet at THIS frozen price. It is conviction that the side is a
  good bet (edge over the price, and how much the reader trusts its read: layers agreeing, fresh news, a clean
  market signal), NOT the chance the side wins. A -500 favourite can win 83% of the time and still be a conf-10 bet.
- `conf_rank` — 1 = the single best bet on the slate, then 2, 3, ... through every line (ties broken by larger edge,
  then earlier kickoff). Written by the reader in the same pass as the probabilities.
- `edge` — computed by the tool, not the reader: reader probability of its side minus the book's de-vigged
  probability at the frozen price. Logged beside conf so we can see whether the reader's ranking adds anything over
  ranking by raw edge.

Why: the 100th-ranked pick missing is not the same as the number-1 pick missing. Scoring is broken out by rank band
(1-10, 11-25, 26-50, 51+). **Pre-registered expectation:** closing-line value and units per bet fall as rank rises
(band 1-10 best). If, at the 500- and 1,500-side checkpoints, band 1-10 does not beat the rest on CLV, the ranking
carries no information and that is reported plainly. Rank by `conf` vs rank by `edge` is compared on the same lines.

## 3. The Top 10
The Top 10 is conf ranks 1-10 of what is frozen at the posting time T (Jeff sets T later). It is read off the frozen
file(s), never re-picked. A game not yet frozen at T is not eligible for that day's Top 10. Whether the Top 10 is per
sport or across all sports that day is open (default: per sport). The Top 10 is scored as its own line in every report
and is what the website shows first.

## 4. What happens after the freeze
Injuries, scratches, goalie changes, lineup changes and weather that arrive AFTER the freeze are logged in a
post-freeze events file beside the slate (`postfreeze_<UTC>.csv`: game, player/team, what changed, source URL,
retrieved_utc, rows affected). Where the tool can detect it (a prop player who did not play, a starting goalie other
than the one in the packet, an NFL inactive), it is logged automatically. These notes explain misses; they never
change the record: every frozen row keeps its grade, nothing is voided or removed because news arrived later
(except where the book itself voids the bet, e.g. a player prop on a player who does not play). Reports add one cut:
rows touched by post-freeze news vs untouched.

## 5. Which model reads
Opus by default (Jeff: running several sports uses less of the plan). Every file records the model (`--reader-model`,
N62). Different models are different pickers — reported side by side, never pooled silently. To compare them fairly,
some slates are read by BOTH models from the same packet at the same time (paired slates); only paired slates settle
"is Fable better than Opus". If Fable shows a clear edge there at a checkpoint, upgrading the plan is a named decision.

## 6. Automation and the website
Coming: a scheduled daily run per sport (packet -> reader -> freeze -> hash posted -> Top 10 posted at T), and the
website back up showing the Top 10 and the running record. The method above is identical whether a chat session or
a scheduled task runs it; the file records which (`reader_session`: chat or scheduled). Design is a separate work
order; nothing in this file waits on it.

## Until the freeze tool supports conf / conf_rank / post-freeze files
The NHL work order owns `nfl/pipeline/log_ai_opinions.py`; it adds `conf`, `conf_rank`, `edge` and the post-freeze
file. Until it merges, conf and conf_rank are written to a sidecar `conf_<freezeUTC>.csv` beside the frozen file,
and its sha256 is posted in the status doc before the first game with the frozen file's hash.
