# MyDayCoach 0.15.0 — usage and cost setup

Install the new APK over the existing app. Your goals, course progress, coaching data and saved connection settings stay in place.

This feature requires updating **both existing Workers** and adding one database binding to the Inspire Worker. No new database, queue, Firebase setup, API key or GitHub secret is needed.

## 1. Update the coaching Worker

Cloudflare → Workers & Pages → **mydaycoach-coach** → Edit code. Replace the complete code with **mydaycoach-coach-0.15.0.mjs** and Deploy.

Keep its existing `ANTHROPIC_API_KEY`, `COACH_APP_TOKEN`, `LEARNING_DB`, `LEARNING_QUEUE` and Firebase settings. Do not replace the secrets. The usage tables are created automatically in the existing database; do not rerun the Learning or News schema.

## 2. Update the Inspire Worker and connect the same database

Cloudflare → Workers & Pages → **mydaycoach-inspire** → Settings/Bindings → Add binding → D1 database:

- Binding/variable name: **LEARNING_DB**
- Database: select the **same existing database** currently bound to mydaycoach-coach (normally **mydaycoach-learning**).

Do not create another database. Both Workers must use the same physical D1 database, not simply the same binding name.

In mydaycoach-inspire → Edit code, replace the complete code with **mydaycoach-inspire-usage.mjs** and Deploy. This is a self-contained file: paste the whole file. Keep the existing `APP_REFRESH_TOKEN`, `GITHUB_DISPATCH_TOKEN` and `ANTHROPIC_API_KEY`. Keep your GitHub Inspire Worker URL/access-code settings unchanged. Do not paste this file into the coaching Worker.

For CLI deployment, replace the placeholder database ID in the corresponding wrangler.toml with that same existing D1 ID before deploying. Dashboard users do not need to edit Wrangler files.

## 3. Verify and open the tracker

1. Open `https://mydaycoach-inspire.jay-imt.workers.dev/health` in a browser. It should report `usageStorageReady: true`. This makes no model call and initializes the Inspire coverage marker.
2. In the app, open the navigation menu and tap **💰** opposite MyDayCoach.
3. Tap **Refresh totals**. An empty tracker is normal until real model calls occur after deployment. Missing historical usage is never filled with guesses.
4. Use one normal coach turn or a connection check, then refresh totals. Its tokens/cost should appear under the correct coach. Connection checks are actual small paid model calls and are included. Learning and News calls, background authoring/reviews, and Inspire generation/image reviews are recorded automatically.
5. Select dates/features and switch Daily/Weekly. All totals and the pie chart use the same selection. Weekly bars include only dates inside the selected range.

If the app says usage is unavailable: check the coaching Worker code and its existing D1 binding. If Inspire remains unrecorded after opening its health URL: check that its LEARNING_DB is the same database as the coaching Worker's. A successful health response alone does not prove that a real model call was recorded.

## What the amounts mean

Amounts are estimated **USD API spend**, not an invoice or credit balance. They include actual provider-reported uncached input, cache reads, five-minute/one-hour cache writes, output and successful web searches. Paid retries, continuations and review calls count individually; a cached app response does not create a second charge. Rejected 4xx calls without usage and token-count estimates are not priced as generation. Unmeasured/unknown-price or interrupted calls are labelled; estimates may undercount incomplete usage. Hosting, infrastructure bills, taxes and account-specific credits/discounts are separate.

Rates verified November 14, 2026 from Anthropic's [Haiku overview](https://platform.claude.com/docs/en/models/haiku-5-5/overview) and [pricing documentation](https://platform.claude.com/docs/en/about-claude/pricing). Per million tokens, standard prompts up to 100,000 total input tokens: input $0.10, output $0.50, 5m writes $0.125, 1h writes $0.20, reads $0.01. Prompts above that threshold use $0.50/$2.50/$0.625/$1/$0.05 respectively. Search is $0.01 per billed search. Standard calls from a GitHub batch are not the discounted Anthropic Batch API. Each ledger row stores costs and rate version at the time of recording, so future rate updates must not reprice history.

Only usage counts, costs, timestamps, feature/purpose, model and provider request IDs are stored. No prompts, conversations, API keys or access codes enter the usage ledger. The authenticated coaching connection is used to read your totals.
