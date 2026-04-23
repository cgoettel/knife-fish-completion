#!/usr/bin/env python3
"""Regenerate the GENERATED block of knife.fish from knife's --help output.

Runs the chef/chefworkstation Docker image, enumerates knife subcommands,
dumps `--help` for each in a single container invocation, and splices the
resulting fish `complete` lines into knife.fish between the BEGIN/END markers.

Requires: docker, python3.
"""
import re
import subprocess
import sys
from pathlib import Path

IMAGE = "chef/chefworkstation:latest"
PLATFORM = "linux/amd64"
KNIFE_FISH = Path(__file__).resolve().parent / "knife.fish"
BEGIN_MARKER = "# ---------- BEGIN GENERATED ----------"
END_MARKER = "# ---------- END GENERATED ----------"


def docker_knife_bare():
    r = subprocess.run(
        ["docker", "run", "--rm", "--platform", PLATFORM, IMAGE, "knife"],
        capture_output=True, text=True,
    )
    return r.stdout + r.stderr


_CAPS = re.compile(r"^[A-Z][A-Z0-9_]+$")


def extract_path(line):
    s = line.strip()
    if not s.startswith("knife "):
        return None
    rest = s[len("knife "):]
    path = []
    for tok in rest.split():
        if tok[:1] in "[(<" or _CAPS.match(tok):
            break
        path.append(tok)
    return " ".join(path) if path else None


def parse_paths(listing):
    paths = set()
    for line in listing.splitlines():
        p = extract_path(line)
        if p:
            paths.add(p)
    paths.discard("")
    return sorted(paths)


# Option line in `knife <cmd> --help`:
#   -s, --long VALUE   Description.
#       --long VALUE   Description.
#       --[no-]flag    Description.
_OPT = re.compile(
    r"""
    ^\s{0,12}
    (?:-(?P<short>[A-Za-z]),\s+)?
    --(?P<nobool>\[no-\])?(?P<long>[A-Za-z][A-Za-z0-9-]*)
    (?:[=\ ](?P<value>[A-Z][A-Z0-9_=/\-]*))?
    \s+
    (?P<desc>\S.*?)\s*$
    """,
    re.VERBOSE,
)


def parse_options(help_text):
    out = []
    seen = set()
    for line in help_text.splitlines():
        m = _OPT.match(line)
        if not m:
            continue
        key = (m.group("short"), m.group("long"))
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "short": m.group("short"),
            "long": m.group("long"),
            "nobool": bool(m.group("nobool")),
            "takes_value": bool(m.group("value")),
            "desc": m.group("desc").strip(),
        })
    return out


def fish_quote(s):
    return s.replace("\\", "\\\\").replace("'", "\\'")


def emit_flag(path, opt):
    cond = f'__fish_knife_path_is "{path}"'
    lines = []
    parts = [f"complete -c knife -n '{cond}'"]
    if opt["short"]:
        parts.append(f"-s {opt['short']}")
    parts.append(f"-l {opt['long']}")
    if opt["takes_value"]:
        parts.append("-r")
    parts.append(f"-d '{fish_quote(opt['desc'])}'")
    lines.append(" ".join(parts))
    if opt["nobool"]:
        neg = [f"complete -c knife -n '{cond}'",
               f"-l no-{opt['long']}",
               f"-d '{fish_quote(opt['desc'])}'"]
        lines.append(" ".join(neg))
    return lines


def dump_all_help(paths):
    script = []
    for p in paths:
        script.append(f'printf "===BEGIN %s===\\n" "{p}"')
        script.append(f'knife {p} --help 2>&1 || true')
        script.append(f'printf "===END %s===\\n" "{p}"')
    r = subprocess.run(
        ["docker", "run", "--rm", "--platform", PLATFORM,
         "--entrypoint", "bash", IMAGE, "-c", "\n".join(script)],
        capture_output=True, text=True,
    )
    return r.stdout


def split_dump(dump):
    out = {}
    current = None
    buf = []
    for line in dump.splitlines():
        if line.startswith("===BEGIN "):
            current = line[len("===BEGIN "):].rstrip("=").rstrip()
            buf = []
        elif line.startswith("===END "):
            if current is not None:
                out[current] = "\n".join(buf)
            current = None
        elif current is not None:
            buf.append(line)
    return out


def build_block(paths, help_sections):
    out = [BEGIN_MARKER,
           "# Regenerate with ./generate.py. Do not edit this block by hand.",
           ""]

    # Expand to include intermediate prefixes so the commandline-path helper
    # can match partial paths like "node" or "data bag" even when only the
    # leaves ("node list", "data bag show", ...) come back from knife.
    all_paths = set(paths)
    for p in paths:
        toks = p.split()
        for i in range(1, len(toks)):
            all_paths.add(" ".join(toks[:i]))
    sorted_paths = sorted(all_paths)

    out.append("set -g __fish_knife_paths \\")
    for i, p in enumerate(sorted_paths):
        sep = " \\" if i < len(sorted_paths) - 1 else ""
        out.append(f'    "{p}"{sep}')
    out.append("")

    by_parent = {}
    for p in sorted_paths:
        toks = p.split()
        for i in range(1, len(toks)):
            parent = " ".join(toks[:i])
            by_parent.setdefault(parent, set()).add(toks[i])

    out.append("# Subcommand edges")
    for parent in sorted(by_parent):
        for child in sorted(by_parent[parent]):
            out.append(f"complete -c knife -n '__fish_knife_path_is \"{parent}\"' -a {child}")
    out.append("")

    out.append("# Flags per subcommand")
    for p in paths:
        opts = parse_options(help_sections.get(p, ""))
        if not opts:
            continue
        out.append(f"# knife {p}")
        for opt in opts:
            out.extend(emit_flag(p, opt))
    out.append("")
    out.append(END_MARKER)
    return "\n".join(out)


def splice(original, block):
    lines = original.splitlines(keepends=True)
    start = end = None
    for i, line in enumerate(lines):
        stripped = line.rstrip("\n")
        if stripped == BEGIN_MARKER:
            start = i
        elif stripped == END_MARKER:
            end = i
            break
    if start is None or end is None:
        sys.exit("ERROR: BEGIN/END GENERATED markers not found in knife.fish")
    return "".join(lines[:start]) + block + "\n" + "".join(lines[end + 1:])


def main():
    print("Fetching subcommand listing...", file=sys.stderr)
    listing = docker_knife_bare()
    paths = parse_paths(listing)
    print(f"  found {len(paths)} subcommand paths", file=sys.stderr)

    print("Dumping --help for all subcommands (one container, may take a while)...", file=sys.stderr)
    dump = dump_all_help(paths)
    sections = split_dump(dump)
    print(f"  captured help for {len(sections)} paths", file=sys.stderr)

    block = build_block(paths, sections)
    original = KNIFE_FISH.read_text()
    KNIFE_FISH.write_text(splice(original, block))
    print(f"Updated {KNIFE_FISH.name}.", file=sys.stderr)


if __name__ == "__main__":
    main()
