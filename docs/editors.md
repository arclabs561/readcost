# Editors

`readcost lsp` runs a language server that speaks the Language Server
Protocol over stdin and stdout. Any editor with a generic LSP client can show
readcost's findings as diagnostics, underlined in the text as you write.

```sh
pip install 'readcost[lsp]'   # adds pygls; without it, `readcost lsp` exits with status 2
readcost setup
```

## What the server does

- It checks a document when you open it, when you save it, and half a second
  after you stop typing.
- It reads the same `readcost.toml` that `readcost check` reads, found by
  walking up from the document's directory. `[readcost.src]` `include` and
  `exclude` choose the files it checks, so a file outside `include` gets no
  diagnostics. The globs are matched against the path relative to the config
  file's directory.
- It picks the format from the file name, as `readcost check` does: Markdown
  for `.md`, doc comments for source files, and so on.
- Each diagnostic covers the flagged words when they sit on one line, and the
  whole line otherwise. The code is the feature id, such as `stacked-nouns`,
  and links to the README's [What it flags](../README.md#what-it-flags) table.
  The message ends with the suggested fix.
- Severity follows the finding: info is Information, warn is Warning, and
  error is Error.
- The server loads the spaCy model once and checks documents on a worker
  thread, so a long document does not stall the editor.
- Untitled buffers are not checked: without a path there is no config to read
  and no format to pick.

Below, `readcost` must be on the `PATH` that the editor sees. If it is not, use
the full path, for example `/path/to/venv/bin/readcost`.

## VS Code

VS Code has no built-in way to add a language server from settings, so use
the [Generic LSP Client (v2)](https://marketplace.visualstudio.com/items?itemName=zsol.vscode-glspc)
extension (`zsol.vscode-glspc`). Then add to `settings.json`:

```json
{
  "glspc.server.command": "readcost",
  "glspc.server.commandArguments": ["lsp"],
  "glspc.server.languageId": ["markdown", "plaintext", "restructuredtext"]
}
```

That extension runs one server at a time. Its output appears in the "Generic
LSP Client" output panel.

## Neovim

Neovim 0.11 and later define servers with `vim.lsp.config`; nvim-lspconfig is
not needed for a server it does not ship. In `init.lua`:

```lua
vim.lsp.config('readcost', {
  cmd = { 'readcost', 'lsp' },
  filetypes = { 'markdown', 'text', 'rst' },
  root_markers = { 'readcost.toml', '.git' },
})
vim.lsp.enable('readcost')
```

To keep the config in its own file, put the table in `lsp/readcost.lua` on the
runtime path (`return { cmd = ..., ... }`) and call only `vim.lsp.enable`.

## Helix

In `~/.config/helix/languages.toml`, or `.helix/languages.toml` in a project:

```toml
[language-server.readcost]
command = "readcost"
args = ["lsp"]

[[language]]
name = "markdown"
language-servers = ["marksman", "markdown-oxide", "rumdl", "readcost"]
```

Setting `language-servers` replaces the built-in list, so name the servers you
still want. The three above are the defaults in Helix's own `languages.toml`.
Helix merges diagnostics from every server in the list.

## Zed

Zed starts only the language servers that Zed or an installed extension
registers. Its `lsp` settings can change the binary of a registered server,
but cannot add a new one. Running readcost in Zed would need a small Zed
extension, which readcost does not provide yet.

