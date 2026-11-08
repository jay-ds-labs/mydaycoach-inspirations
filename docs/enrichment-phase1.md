# Existing library enrichment — Phase 1

Use [Enrich and review existing inspirations](../.github/workflows/enrich-library.yml) → **Run workflow** with a batch size of 5 for the first quality pilot. This requires the existing repository `OPENAI_API_KEY` Actions secret. Subsequent runs resume from `enrichment-review.json`. The job commits article details and status after each entry.

**Scope:** 70 unpublished online entries. The three published benchmark examples are unchanged. The Android app may display three additional bundled-only items; those need a separate app content synchronization step.

**Card UX:** Existing `id`, `category`, `title`, `body`, `attribution` and `source` are retained. The long article is stored in `detail`, not the card summary.

**Safety:** This pipeline does not automatically publish. A model-generated reviewer approval is only a preliminary quality check. The review report's `approved` means AI review passed, not that an editor approved publication. Every article stays `draft` until a separate publication process verifies its source, quotations, attribution, image usage rights and editorial quality. If source evidence cannot be retrieved, the article is flagged. Images are not sourced by this workflow; a verified image sourcing stage is still needed.

**Progress:** `enrichment-status.json` contains `state`, `stage`, `completed`, `total`, `batchCompleted`, `generated`, `reviewed`, `approved`, `needsReview` and `currentId`. `enrichment-review.json` stores per-entry findings.

**Caveat:** The existing Android app does not yet show the enrichment workflow's progress. It only shows the separate 15-item Refresh status. Do not use Refresh to start this upgrade; it generates new articles instead.

After a 5-article pilot, inspect all five articles and review findings before running larger batches. Run subsequent batches until all 70 entries have been processed, then reconcile the three local-only entries and implement image sourcing and final publication.
