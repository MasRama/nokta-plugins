# Nokta plugins

Plugins for [Nokta](https://github.com/MasRama/nokta), shared by the people
who use it. Each one puts a card of its own in the notch: a row in home, a
list it opens, a badge in the closed notch, an alert.

| Plugin | Shows | Runs on |
| --- | --- | --- |
| [`days-until`](plugins/days-until) | The days left until a date you pick, with a badge | Linux, macOS, Windows |
| [`hello`](plugins/hello) | A greeting with a list of links, and two options | Linux, macOS, Windows |
| [`prayer-times`](plugins/prayer-times) | The five daily prayer times for your city, a countdown in the closed notch and an alert on time; worked out offline | Linux, macOS, Windows |
| [`site-status`](plugins/site-status) | Whether a site answers: a badge and an alert while it is down | Linux, macOS, Windows |
| [`water`](plugins/water) | Glasses of water today with `+1` and `Undo`; it keeps running | Linux, macOS, Windows (Python) |

## Install one

In Nokta's settings: **Plugins → Catalog → Browse**, then **Install**. Or
from a terminal:

```sh
nokta plugin catalog              # what is here, and what you have
nokta plugin install days-until   # installed off
nokta plugin enable days-until
nokta plugin update days-until    # when the catalog has a newer version
```

A plugin starts off, so you can read it first. Plugins run as you, with your
files and your network. Each one here was read before it was merged, but
read it yourself too: its folder holds all of it.

## How Nokta gets them

On every push to `main`, the [Catalog](.github/workflows/catalog.yml)
workflow checks each plugin and publishes the `catalog` branch:
`index.json`, which lists every file of every plugin with its size and
SHA-256, and the files themselves. Nokta asks for `index.json` only when you
press Browse or run a `nokta plugin` catalog command. It downloads a
plugin's files one by one and installs nothing if one does not match.

## Add yours

See [CONTRIBUTING.md](CONTRIBUTING.md). How to write a plugin is in
Nokta's [docs/plugins.md](https://github.com/MasRama/nokta/blob/main/docs/plugins.md).

## License

GPL-3.0-or-later, like Nokta. A plugin sent here is shared under it.
