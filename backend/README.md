# MyDayCoach Inspire Worker

The app's Generate button authenticates to this Worker and dispatches the existing GitHub generation workflow. Feed and status endpoints remain unchanged. Generation, enrichment, final editorial review and optional image relevance review now all use **claude-haiku-5-5**, with the private model key stored only on this Worker.

Follow [the Haiku migration instructions](../docs/HAIKU_MIGRATION.md). GitHub uses a Worker URL and private access code; it does not hold a model API key. The existing generation/review pipeline, three-attempt limit, final failure notes, library records and images are preserved by this provider-only change.

Secrets: `APP_REFRESH_TOKEN`, `GITHUB_DISPATCH_TOKEN`, `ANTHROPIC_API_KEY`. Native Android uses only its existing revocable app access code. Never put a GitHub dispatch or provider key in the APK.

Routes:
- GET /health: model/configuration metadata, not proof of live quality.
- GET /status and /feed: authenticated status and library proxy.
- POST /start: authenticated generation dispatch; duplicate running batches are not dispatched.
- POST /ai/messages: authenticated Haiku-only text/vision calls for the generation workflows. Output truncation and wrong models are rejected. Images are Wikimedia HTTPS references. No raw prompts, source contents or model keys are logged.

The Worker is not deployed automatically by a git commit. Follow the owner setup steps and run the small live integration workflow before normal generation.
