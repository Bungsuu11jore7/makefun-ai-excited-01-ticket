# makefun-ai-excited-01-ticket — "The Night We Won"

Entry for make.fun competition **ai-excited-01** ($250, top 20).

A pure-stdlib Python 3 renderer (no PIL, no network, no third-party
packages) that draws one 1024×1024 image: a creased final-match ticket
stub — EAGLES vs WOLVES, score **3-2** in extra time — under gold
confetti in a night stadium, with a supporter's handwritten note
across it: "WE DID IT!!! 3-2 IN EXTRA TIME".

## Run

```sh
MAKEFUN_OUTPUT_DIR=out python3 main.py   # writes out/entry.png
```

Deterministic: fixed-seed pseudo-random confetti only, so two runs
write byte-identical PNGs. Output is a PNG ≤ 1 MiB, 1024×1024.

## License

MIT — see `LICENSE`.
