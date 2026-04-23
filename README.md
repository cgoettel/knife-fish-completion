# knife-fish-completion

Fish shell completions for Chef's `knife` CLI. Covers all knife subcommands and flags, including multi-token namespaces (`data bag show`, `client key edit`, …).

## Install

Copy `knife.fish` into your fish completions directory:

```fish
cp knife.fish ~/.config/fish/completions/knife.fish
```

Or symlink it if you'd rather track updates:

```fish
ln -s (pwd)/knife.fish ~/.config/fish/completions/knife.fish
```

Completions load automatically on the next fish session. No sourcing needed.

## What it does

| You type                    | You get                                                 |
| --------------------------- | ------------------------------------------------------- |
| `knife <TAB>`               | Top-level subcommands (`node`, `cookbook`, `data`, …)   |
| `knife node <TAB>`          | Second-level subcommands (`list`, `show`, `edit`, …)    |
| `knife data bag show <TAB>` | All flags for `knife data bag show`, with descriptions  |

Flag descriptions come straight from `knife <cmd> --help`. Top-level category descriptions are hand-written because `knife` doesn't provide them.

## Supported knife version

Generated against Chef Infra Client **18.10.17** (via the `chef/chefworkstation` Docker image). Older and newer knives are mostly compatible — flags that don't exist simply won't complete, and new flags can be picked up by regenerating.

## Regenerating

The flag completions and subcommand tree are generated from live `knife --help` output. To refresh:

```fish
./generate.py
```

Requirements: Docker and Python 3. The generator pulls `chef/chefworkstation:latest`, enumerates every subcommand, dumps `--help` for each in a single container invocation, and splices the result into the `BEGIN GENERATED` / `END GENERATED` block in `knife.fish`.

On Apple Silicon the amd64 image runs under emulation, so expect a few minutes.

## License

See [LICENSE](LICENSE).
