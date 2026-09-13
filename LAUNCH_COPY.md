# TimmyTest launch copy

Use these drafts only after running the install command against the tagged release. Reply to technical questions with actual output from a real project; do not claim measured token savings until a reproducible benchmark exists.

## Short post

I built TimmyTest, a local test runner that summarizes failures and likely test gaps into a compact prompt for Claude Code, Codex or Cursor. It makes no AI API calls during the local scan and test run. I would value feedback from people trying it on a real repository: where did installation, detection or the report fail?

Try it: `python -m pip install "git+https://github.com/tugrakaymakcioglu/TimmyTest.git@v2.0.0"` then `timmytest check .`

Demo and source: https://github.com/tugrakaymakcioglu/TimmyTest

## Show HN draft

Title: Show HN: TimmyTest – local test reports for AI coding agents

I use coding agents to fix tests, but a lot of the context can become raw test output and repo exploration. TimmyTest runs the project's existing tests locally, reports likely gaps between source and tests, and generates a shorter handoff prompt for the agent. The local work makes no AI API calls; sending its output to an agent still uses that agent's tokens.

There is a terminal demo in the README and a tagged 2.0.0 release. PyPI publishing is still pending, so the install command currently uses GitHub. I would especially like feedback on false test-gap reports, unsupported project layouts and confusing first-run output. Please include your OS and a redacted output sample in an issue.

https://github.com/tugrakaymakcioglu/TimmyTest

## What to measure weekly

- GitHub unique visitors and referrers (discovery).
- Installation questions and first-run issues (activation friction).
- Reports from real repositories, including false positives (value and quality).
- Repeat contributors and discussions (retention signal).

GitHub clones do not equal active users. Avoid estimating users from clone counts.
