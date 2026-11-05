# Adding a plugin

1. Write it and try it in Nokta from a folder first:
   `nokta plugin install path/to/your-plugin`, then turn it on. The contract
   is Nokta's [docs/plugins.md](https://github.com/MasRama/nokta/blob/main/docs/plugins.md).
2. Put it in `plugins/<id>/`; the folder's name is its `id`.
3. Run the checks CI runs:

   ```sh
   python3 tools/build_index.py   # plugin.toml and every file
   python3 tools/run_once.py <id> # one run prints a card
   shellcheck plugins/<id>/*.sh
   ```

4. Open a pull request that says what the plugin shows and what it reaches
   over the network, if anything.

## What a plugin here must be

- **Readable.** Plain source in the folder. No binaries, no minified or
  obfuscated code, nothing downloaded and run at run time.
- **Small.** Only what it needs; at most 500 files and 20 MiB. No hidden
  files, no links. Names are letters, digits, `.`, `_` and `-`.
- **Honest.** It does what its `description` says. It sends nothing
  anywhere the description and the pull request do not name, and never
  reads files it does not need.
- **Complete.** `name`, `description`, `version` and `author` set; a
  `windows` command too when it can run on Windows.
- **Polite.** An `every` that fits what it shows; no alert on every run.

## Updating a plugin

Change its files and raise `version` in its `plugin.toml`. Nokta offers
**Update** to everyone who has it when the catalog's version is newer; an
update keeps their switch and options. An update gets the same review as a
new plugin, and only its author or a maintainer may send one.

## Review

A maintainer reads every file before a merge. A plugin can be removed from
the catalog when it breaks these rules; Nokta does not remove it from
computers that installed it.
