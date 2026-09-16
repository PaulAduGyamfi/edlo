# Edlo

Edlo is a production system for a live podcast (*The Sozzled Pod*), built to fix a real bottleneck: episodes were taking around two weeks to go from recording to published, with no visibility into where they were stuck.

It replaces that with a tracked pipeline — episodes move through explicit stages (registered → mixing → plan_ready → editing → review → published), every transition is recorded with who moved it and why, and audio files are checksummed so the same upload can't be duplicated.

**Status:** in active development.

## Why this exists

The users are real (the show's editors), the constraint is real (a two-week delay), and the goal is a measured before/after — not a demo. Design decisions follow from that: AI features are bounded and grounded, with a human approving anything before it ships. Nothing publishes itself.
## Running it locally

One terminal, the whole stack:

```bash
scripts/dev.sh
```

It starts Redis (Docker), runs migrations, then the API with reload on port 8000, one worker, and the web app on port 5173. Uploads, transcription, plans and packs are all background jobs, so **nothing moves without the worker**. If a page sits on "Waiting for a worker", that is what is missing; run it by hand with `python -m apps.worker.main`.

To wipe every episode from the dev database and start again:

```bash
python -m scripts.reset_dev
```

## Turning the AI on

AI is off by default, and the workflow runs without it: the plan is the flagged moments and the checklist. To have Claude propose cuts, cold opens and the publishing copy, set four lines in `.env`:

```
AI_ENABLED=true
MODEL_PROVIDER=anthropic
MODEL_NAME=claude-sonnet-5
MODEL_API_KEY=sk-ant-...
```

`.env` is git-ignored and is the only place the key goes locally. In production the key is read from Secrets Manager: supply it once as `TF_VAR_model_api_key` when running `terraform apply`, and both ECS tasks receive it as `MODEL_API_KEY`. Every proposal the model makes is still checked against the transcript before anyone sees it, and the owner still approves the pack.
