# MyDayCoach Haiku-only model migration

## Audit

| Feature | Before | After |
|---|---|---|
| Life Coach, Career Coach, weekly coaching reviews | Direct Anthropic Haiku 5.5 | Unchanged |
| Learning chat, feedback, authoring and review | Direct Anthropic Haiku 5.5 | Unchanged |
| News search and summaries | Direct Anthropic Haiku 5.5 | Unchanged |
| Insights statistics, streaks and awards | Local deterministic calculations | Unchanged; no model |
| Inspiration cards/articles and legacy enrichment | OpenAI gpt-4.1 | Haiku 5.5 through Inspire Worker |
| Inspiration final editorial review | OpenAI gpt-4.1 | Haiku 5.5 through Inspire Worker |
| Optional image relevance review | OpenAI gpt-4.1-mini | Haiku 5.5 vision through Inspire Worker |
| Inspiration image retrieval | Wikimedia Commons / existing repository assets | Unchanged; no image-generation model |

The model is fixed to `claude-haiku-5-5` with no fallback, model override, OpenRouter or direct OpenAI call. Existing saved articles/images are retained. References to OpenAI in educational content or source links are not API use.

## One-time owner setup

Use the separate **mydaycoach-inspire** Cloudflare Worker. Do not replace mydaycoach-coach with this file.

1. Cloudflare → Workers & Pages → mydaycoach-inspire → Settings → Variables and Secrets: add encrypted secret `ANTHROPIC_API_KEY`. Enter the private Anthropic key only there, never in chat, GitHub or the phone. Existing account/billing may be reused. Keep `APP_REFRESH_TOKEN` and `GITHUB_DISPATCH_TOKEN` unchanged.
2. In this Worker → Edit code, replace the code with the supplied `worker.js`, then Deploy.
3. GitHub → jay-ds-labs/mydaycoach-inspirations → Settings → Secrets and variables → Actions → Variables: add `INSPIRE_WORKER_URL`, with the existing HTTPS Inspire Worker URL (no /start suffix). Use the same URL already saved in Inspire Library → Content generation setup.
4. In the GitHub Actions Secrets tab, add `INSPIRE_WORKER_TOKEN`. Its value must match the existing Cloudflare `APP_REFRESH_TOKEN` / the Inspire backend access code saved in the phone. This is an access code, not a model API key. Never put the Anthropic key here.
5. After the migrated workflow code is on the content repository's main branch, use Inspire Library → Generate 15 New Inspirations as normal. The worker dispatches the same GitHub workflow, and GitHub sends writing/review requests to the authenticated Worker. Only the Worker sends requests to Anthropic.

The former GitHub OpenAI secret is no longer used and may be removed after setup. Do not remove the GitHub dispatch credential, app access code or existing Firebase settings.

## Verification

Offline Python editorial/image/publication regression tests and Worker provider/auth/dispatch tests must pass. These use synthetic model responses and do not prove provider content quality. The public /health endpoint reports the pinned model and whether the Worker key is configured; it does not claim a live model test.

For a small live integration check, run the manual **Check live Haiku connection** workflow after setting the URL/token. It makes one short paid Haiku call and expects a JSON confirmation. Then generate one normal batch when desired, confirm progress, 15 outcomes, full detail/images and existing final-review reason codes. No production generation or secret access is performed automatically during testing.

## App update

Install MyDayCoach 0.13.0 (26) over the existing application. The phone status bar is explicitly shown with dark icons on the app's light background. Inspire Library is directly under Insights in the drawer. Knowledge contains News Feed and Learning. Internal routes, saved preferences, source records, goals and learning progress remain unchanged.

No update is needed to the combined coaching/Learning/News Worker or Firebase.
