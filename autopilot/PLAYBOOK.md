# News Nepal autopilot (the "CEO" run)

A scheduled Claude session follows this file every day. Its job, set by the owner (Unique, GitHub
`uniquepoudell`) on 2026-11-26: **keep improving the site's quality, speed and features without waiting for
approval, learn from similar sites, and push hard on income.** Everything it learns and decides is kept in this
`autopilot/` folder, so the whole history moves with the repo when the site gets its own domain.

## Files in this folder
| File | What it holds |
|---|---|
| `PLAYBOOK.md` | These rules and the daily steps. |
| `ROADMAP.md` | The ranked backlog. Pick the top item you can finish today. Re-rank weekly. |
| `INCOME.md` | Every way the site can earn, its status, and what only the owner can do (signups). |
| `competitors.md` | What similar sites do well, with the date checked, and which ideas we took. |
| `learnings.md` | Short findings, newest at the top. |
| `log.md` | One row per run: date, change, PR, result, problems. |
| `DOMAIN.md` | How to move the site to the owner's own domain. |

## Authority
- The owner pre-approved: open a PR, run the tests, and **merge it yourself when tests pass and the build is
  green**. This covers features, design, performance, SEO and content, not only small fixes.
- Revert your own change straight away if a later build, deploy or health check fails because of it.
- Leave a PR open and say so in the weekly report only when it: deletes a section or many stories, changes
  where money goes (payment links, wallet addresses, prices), adds a paid service or a new secret, or touches
  files an open PR by someone else is changing.

## Hard rules (never break these, even to make money)
- Never sign up, pay, post, email or message anyone, or accept terms in the owner's name. Prepare it, then list
  it in `INCOME.md` under "Waiting on owner" with the exact steps.
- Never change payment links, wallet addresses or prices. Never ask for or store keys in files.
- Crypto trading is illegal in Nepal: news and education only, no exchange or trading referrals aimed at Nepal,
  no price predictions or "buy" advice.
- Visa content is general information with a MARA disclaimer. No personal visa, tax or investment advice.
- Don't copy other sites' articles, images or design. Link out, quote a headline and a short summary, credit
  the publisher. Learn ideas from competitors, never their content or branding.
- Never invent numbers: traffic, revenue, rates, fees, dates. Cite what you read this run, with link and date.
- No dark patterns: no fake urgency, fake reviews, fake counters, popups that block reading, or misleading ads.
- Never weaken, skip or delete a test to get green. Never force-push `main` or rewrite others' history.

## Each run, in order
1. **Health first.** Check the latest "Build and publish" runs and any "Site health" issue. If red, fix it
   before anything else. Read the build log lines `images:`, `illustrations:`, `forex:` and the feed report;
   fix a feed that keeps returning 0 or errors.
2. **Learn.** Once a week (Sunday or if `competitors.md` is older than 7 days) study 2 or 3 similar sites from
   the list in `competitors.md` with web search or web-fetch: features, page types, how they get search and
   social traffic, how they earn. Add dated notes and turn good ideas into `ROADMAP.md` items.
3. **Build.** Take the top `ROADMAP.md` item that fits in one run (split big ones). Branch
   `autopilot/news-<YYYY-MM-DD>` from fresh `origin/main`, make the change, add or update tests in
   `tests/test_build.py`, run `python tests/test_build.py`, open a PR assigned to `uniquepoudell`, merge it when
   green, then check the next build and deploy succeed.
4. **Measure.** Prefer changes that bring readers (search, sharing, return visits) or money. Check page weight
   and that pages still work without JavaScript. Note any data you actually have; never guess traffic.
5. **Record.** Update `ROADMAP.md` (done, new, re-ranked), `INCOME.md` if anything changed, one line in
   `learnings.md` if you learned something, and one row in `log.md`.
6. **Weekly report (Sundays).** Open a GitHub issue "News Nepal weekly report <date>" assigned to
   `uniquepoudell`: what shipped, what's next, what's waiting on the owner (signups, decisions), with links. Close
   last week's report issue.

## Working alongside others
Other sessions (the GorkhaPay daily run, people) may change this repo. Always start from a fresh
`origin/main`, list open PRs first and avoid their files, merge `main` into your branch if it moved, and re-run
the tests before merging.
