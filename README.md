# Edlo

Edlo is a production system for a live podcast (*The Sozzled Pod*), built to fix a real bottleneck: episodes were taking around two weeks to go from recording to published, with no visibility into where they were stuck.

It replaces that with a tracked pipeline — episodes move through explicit stages (registered → mixing → plan_ready → editing → review → published), every transition is recorded with who moved it and why, and audio files are checksummed so the same upload can't be duplicated.

**Status:** in active development.

## Why this exists

The users are real (the show's editors), the constraint is real (a two-week delay), and the goal is a measured before/after — not a demo. Design decisions follow from that: AI features are bounded and grounded, with a human approving anything before it ships. Nothing publishes itself.