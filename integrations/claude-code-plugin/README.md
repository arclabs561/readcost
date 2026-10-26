# readcost plugin for Claude Code

Registers three hooks. One is on by default: after Claude writes or edits a
file that matches `hooks.paths` (Markdown, reStructuredText and text files),
PostToolUse adds readcost's findings next to the tool result. It never blocks
unless you set `hooks.mode = "block"`. The other two do nothing until
`readcost.toml` turns them on. `hooks.mode = "off"` turns all of them off.

| Hook | Default | Turned on by |
| --- | --- | --- |
| PostToolUse on Write and Edit | on, advisory | `hooks.mode = "advise"` (default) or `"block"` |
| PreToolUse on Write and Edit | off | `hooks.mode = "block"` |
| Stop | off | `hooks.stop = "report"` or `"revise"` |

The plugin does not register MessageDisplay, which Claude Code would start for
every streamed batch. To get `hooks.display = "note"`, add the hook to your
settings as shown in `docs/hooks.md`.

Requirements: `pip install git+https://github.com/arclabs561/readcost` (or
`pip install -e` from a checkout) and
`readcost setup`, so that `readcost` is on the PATH Claude Code uses.

See `docs/hooks.md` for what each hook sends back.
