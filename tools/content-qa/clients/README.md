# clients/

Each client gets its own folder here, named by slug, holding one file:

```
clients/<client-slug>/voice-profile.md
```

Build it once per client with the wizard:

```bash
python3 run.py --build-profile post1.md post2.md post3.md --client <client-slug>
```

Then run QA against it:

```bash
python3 run.py draft.md --client <client-slug>
```

`clients/acme-example/` ships committed as a runnable demo (see `examples/` at
the tool root). Everything else under `clients/` is gitignored by default —
real client voice profiles stay on your machine, they never get committed.
