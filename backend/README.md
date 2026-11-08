# MyDayCoach Inspire generation backend

The Android Refresh button POSTs to a **deployed Cloudflare Worker**, which authenticates the request and dispatches a GitHub Actions workflow. The worker keeps GitHub credentials off the device. The workflow generates 5 Quotes, 5 Stories, and 5 Philosophy **draft** articles, writing progress to `refresh-status.json`. The Android app polls that file every 5 seconds during generation.

## Deployment (owner action required)

1. Create a Cloudflare account and install Wrangler. In this repository run `cd backend && npx wrangler deploy`.
2. Create a fine-grained GitHub PAT with **Actions: Read and write** and **Contents: Read-only** permissions scoped ONLY to `jay-ds-labs/mydaycoach-inspirations`. Set it in Cloudflare with `npx wrangler secret put GITHUB_DISPATCH_TOKEN` from `backend/`.
3. Generate a long random personal refresh token (e.g. `openssl rand -hex 32`). Set `npx wrangler secret put APP_REFRESH_TOKEN` in Cloudflare. Do not put it in Git, an APK, or chat. This is a personal app; for multi-user distribution replace the shared secret with proper user authentication and rate limits.
4. In GitHub repository **Settings → Secrets and variables → Actions**, add `OPENAI_API_KEY` for the generator workflow. GitHub workflow has contents:write permission; confirm repository Actions workflow permissions allow writes.
5. In Android **Inspire Library → Content generation setup**, enter the deployed `https://....workers.dev` URL and your personal refresh token. Tap Save.
6. Tap Refresh. The worker queues the workflow. It does not wait for generation; Android polls public status and downloads the latest feed.

## Important operational limits

- Content remains **draft** until facts, quote attribution, source URLs, image licensing and the article itself are checked and an editor changes status to published with an ISO-8601 publishedAt timestamp.
- The generator currently does NOT provide verified licensed images. It intentionally leaves image empty rather than claiming image rights it cannot verify.
- GitHub Actions jobs have a 180-minute timeout here. No guarantee of unlimited background processing time.
- Progress updates are eventually consistent through raw.githubusercontent.com caching. Concurrent requests are serialized by GitHub Actions; the status check is best-effort, not a transactional lock.
- Generated content is not a guaranteed source of truth: all citations and claims need independent editorial verification.
- Secrets in Android SharedPreferences are not encrypted; use only a dedicated revocable personal refresh token. Do not paste a GitHub or OpenAI token into the Android settings.
- No worker is deployed by committing this code. Deployment and secrets are required before Refresh can launch jobs.

## API

`GET /health` returns `{"ok":true}`.
`GET /status` requires `Authorization: Bearer <APP_REFRESH_TOKEN>` and returns the latest GitHub Actions progress without relying on the GitHub raw-file CDN. It is polled by Android at 5-second intervals during active generation.\n`GET /feed` uses the same authorization and fetches the latest committed library through the GitHub Contents API; the Android app uses it for a post-generation download.
`POST /start` requires `Authorization: Bearer <APP_REFRESH_TOKEN>` and returns `202 {"state":"queued","total":15}` when dispatched, `200 {"state":"running"}` if already running, or an error status.

## Upgrading the original 40 drafts

Run **Expand existing inspiration drafts** from GitHub Actions after adding the OpenAI secret. This expands the articles but retains draft status until source and image verification. It is separate from new-batch Refresh.

## Publishing generated drafts (editorial verification)

The generator deliberately saves articles with `status: "draft"`. **This is not an automatically completed review step:** the current project has no fact-checker or image-licensing verifier, and GitHub Actions success means generation succeeded, not that the articles are verified.

For each candidate in `library.json`:

1. Read the entire `detail` and verify each material historical/factual assertion against primary or reputable independent sources. Check that the provided `source` link loads and supports the claims. A valid HTTPS URL alone is not verification.
2. Check any quotation word-for-word against a primary source, identify the original speaker and context, and remove fabricated or misleading attribution. Verify the story or philosophy subject really matches its category.
3. Check word count, originality, grammar, coherence, appropriate takeaway, and duplication with existing inspirations.
4. Only add an `image` if its URL, usage license, attribution requirements and display permissions have been verified. A blank image is allowed, and is preferable to using an unlicensed image.
5. After all checks pass, change that entry to `"status": "published"` and set `"publishedAt": "<current UTC ISO timestamp>"`. Commit `library.json` to `main` in the content repository. Android downloads it on the next library refresh, and the publication-aware reader and scheduler then become eligible to show it.

Never publish all 15 drafts automatically solely because the generator finished. An editorial review tool can later streamline these checks and approvals, but it is not implemented yet.

When updating the Cloudflare Worker from this repository, replace the complete editor contents with the current `backend/worker.js` and redeploy. Existing Cloudflare secrets remain configured. Test `/health`; authenticated `/status` is accessed from the app, not from a bare browser URL.
