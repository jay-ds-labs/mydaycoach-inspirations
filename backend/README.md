# MyDayCoach Inspire generation backend

The Android Refresh button POSTs to a **deployed Cloudflare Worker**, which authenticates the request and dispatches a GitHub Actions workflow. The worker keeps GitHub credentials off the device. The workflow generates 5 Quotes, 5 Stories, and 5 Philosophy **draft** articles, writing progress to `refresh-status.json`. The Android app polls that file every 5 seconds during generation.

## Deployment (owner action required)

1. Create a Cloudflare account and install Wrangler. In this repository run `cd backend && npx wrangler deploy`.
2. Create a fine-grained GitHub PAT with **Actions: Read and write** permission scoped ONLY to `jay-ds-labs/mydaycoach-inspirations`. Set it in Cloudflare with `npx wrangler secret put GITHUB_DISPATCH_TOKEN` from `backend/`.
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
`POST /start` requires `Authorization: Bearer <APP_REFRESH_TOKEN>` and returns `202 {"state":"queued","total":15}` when dispatched, `200 {"state":"running"}` if already running, or an error status.

## Upgrading the original 40 drafts

Run **Expand existing inspiration drafts** from GitHub Actions after adding the OpenAI secret. This expands the articles but retains draft status until source and image verification. It is separate from new-batch Refresh.
