# Tech progress bar — update rule

Source: `site/tech-progress.json`, rendered by `site/js/tech-progress.js` (index + verify).

**Rule:** the bar changes only when real PoV-R / token code ships:
1. Code for the milestone is committed and its tests are green.
2. Run `scripts/bump-tech-progress.py --done <id> --commit <sha> --note "..."`
   (or `--active <id> --pct N --now "..."` when work on a milestone actually starts in the repo).
3. Commit the JSON, push, republish the site.

**Never** bump for X posts, raise/grant emails, applications, or marketing.
Statuses: `done`, `active` (max one), `next`, `blocked` (e.g. `mint-reservoir` until LP + audit).
`--check` validates the schema without writing.
