# Practical inspiration review

The November 14 batch accepted one of fifteen slots. Recorded failures: eight UNSUPPORTED_QUOTE (often an incorrect catch-all for interpretation/evidence gaps), three editorial quality failures, two evidence failures and one malformed card. Failed drafts and prior reviews are retained.

## Acceptance

Publish a useful, coherent full article with a finished ending when its central historical account has relevant support and no substantial factual or attribution problem remains. Minor style, wording, category labels, ordinary background details missing from excerpts, unused extra sources, and clearly framed original reflections/paraphrases are not publication vetoes. Save suggestions as reviewNotes. No mandatory word count. Do not publish mere outlines or unfinished articles.

Material blockers only: MATERIAL_FACT_ERROR, FALSE_ATTRIBUTION, INSUFFICIENT_EVIDENCE (central account has no relevant support), WRONG_TOPIC and INCOMPLETE_ARTICLE. Direct quotations attributed as exact words need support; labeled paraphrases do not require exact-word matching. A missing passage is not proof of falsehood. Up to three repair/review attempts; a material blocker left unresolved stays out of the feed with the final reason preserved.

## Retrieval and correction

Read more of each source and select relevant passages throughout the document. Wikipedia exact subject lookup precedes broader search; keep relevant candidates instead of accepting a country/general-topic page as a substitute. Blocked sources trigger alternatives. Update takeaway along with card title/body/attribution. Only select a citation URL actually present in retrieved evidence. Keep article output intact rather than slicing at 11,500 characters. Retry malformed/missing card fields up to three times.

## Recovery and deployment

No APK or Cloudflare Worker update is needed: these are GitHub pipeline changes. The owner-authorized recovery request is pinned to batch startedAt 2026-11-14T13:02:48.709534Z. Merging the request file into main runs Recover failed inspirations from requested batch. It reprocesses only failed slots, skips accepted ones, preserves prior audits and checkpoints each outcome. It uses existing Worker URL/access-code settings, with the Anthropic key remaining on Cloudflare. The workflow can be manually resumed; accepted recovered IDs are skipped, avoiding duplicates. A newer batch timestamp fails closed rather than touching a different batch. Ordinary code commits do not launch paid recovery; only an explicit change to recovery/latest-batch-request.json on main or a manual workflow run does.

After recovery, tap Sync Library in the app. New Generate 15 calls use the practical review rules automatically. No model fallback is allowed.

## Verification

Regression coverage includes warning-only acceptance, exact quotation/material blocker rejection, malformed review rejection, unfinished-article repair/re-review, revised card takeaway, evidence beyond the old truncation, unrelated fallback exclusion, bounded card repair, recovery of missing cards, accepted-story preservation and repeat recovery without duplicate IDs. Worker auth/provider tests remain required. Synthetic tests prove contracts, not historical truth; the recovery run supplies live integration evidence and records final per-item outcomes.

Live verification follow-up: an explicit empty material-blocker list with an unexplained grounded=false verdict is recorded as uncertainty in notes, rather than an unrepairable veto. Missing/malformed blocker lists still fail validation. Search the story subject (e.g. Hypatia) before its historical source author (e.g. Socrates Scholasticus). Regression suite now executes 34 Python tests plus 9 Worker tests.
