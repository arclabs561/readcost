# readcost plugin for Claude Code

Registers four hooks. Each one exits at once unless `readcost.toml` turns it on
or the file matches `hooks.paths`, so installing the plugin changes nothing
until you configure it.

| Hook | Default | Turned on by |
| --- | --- | --- |
| PostToolUse on Write and Edit | on, advisory | `hooks.mode = "advise"` (default) or `"block"` |
| PreToolUse on Write and Edit | off | `hooks.mode = "block"` |
| Stop | off | `hooks.stop = "report"` or `"revise"` |
| MessageDisplay | off | `hooks.display = "note"` |

Requirements: `pip install git+https://github.com/arclabs561/readcost` (or
`pip install -e` from a checkout) and
`readcost setup`, so that `readcost` is on the PATH Claude Code uses.

See `docs/hooks.md` for what each hook sends back.
