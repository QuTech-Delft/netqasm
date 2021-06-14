How to build the docs
=====================

From the `docs/` directory, build the docs by running

```bash
make build
```

This will first install any required dependencies and build the html files. (the next time you can simply do `make html`).

To open the built docs, run

```bash
make open
```
which makes use of the command `open`. If you're on Linux and `open` does not work you can add `alias open='xdg-open` to your rc-file.

To both build the html files and open them, run
```bash
make see
```
