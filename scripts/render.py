#!/usr/bin/env python3
"""
render.py — construct blockcrew avatars on a fixed pixel grid.

WHY THIS IS NOT AN IMAGE MODEL
  Every quantity in the blockcrew spec is a number: head 8x8x8, torso 8x12x4,
  arms 4x12x4, 8 texels per head face, sixteen hex values, base-plus-shade
  lighting, a fixed crop and a fixed camera angle.

  🔴 That is a rendering problem, not a generation problem. Asking a
  probabilistic model to land on exact integers is the wrong tool, and it
  fails in the way probabilistic tools fail: plausibly, and differently each
  run. Constructing the pixels makes drift impossible rather than detectable.

  Everything the prompt-based version needed — an invariant block, a
  consistency check, "no anti-aliasing", "do not accept a smooth render" —
  existed only to fight that drift. None of it is needed here.

DEPENDENCIES
  None. PNG is written with zlib and struct from the standard library, so the
  skill runs anywhere Python does, with no API key, no account and no network.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys
import zlib

# ---------------------------------------------------------------- palette ---
# The locked 16-value dye palette. Each entry is (base, shade); the shade is
# used for any face turned away from the light, so shading is a lookup rather
# than a judgement.
PALETTE: dict[str, tuple[str, str]] = {
    "white":      ("#F9FFFE", "#E6E6E6"),
    "light_gray": ("#9D9D97", "#757571"),
    "gray":       ("#474F52", "#353B3D"),
    "black":      ("#1D1D21", "#151518"),
    "brown":      ("#835432", "#623F25"),
    "red":        ("#B02E26", "#84221C"),
    "orange":     ("#F9801D", "#BA6015"),
    "yellow":     ("#FED83D", "#BEA22D"),
    "lime":       ("#80C71F", "#609517"),
    "green":      ("#5E7C16", "#465D10"),
    "cyan":       ("#169C9C", "#107575"),
    "light_blue": ("#3AB3DA", "#2B86A3"),
    "blue":       ("#3C44AA", "#2D337F"),
    "purple":     ("#8932B8", "#66258A"),
    "magenta":    ("#C74EBD", "#953A8D"),
    "pink":       ("#F38BAA", "#B6687F"),
}

# Reserved for shared slots — too low in chroma to carry identity at 32px.
LOW_CHROMA = {"white", "light_gray", "gray", "black", "brown"}
ROLE_HUES = [k for k in PALETTE if k not in LOW_CHROMA]

# ---------------------------------------------------------------- geometry --
# Canvas is 16x16 texels: 16 wide = arm(4) + torso(8) + arm(4).
# Rows 0-1 headroom, 2-9 head (8 tall), 10-15 torso crop (6 of 12 visible).
GRID_W, GRID_H = 20, 18
HEAD_TOP, HEAD_LEFT = 1, 6
BODY_TOP = 9

# 🔴 The head is exactly as wide as the torso — both 8. This is the single
# most identifying proportion and the first thing a generative model gets
# wrong. Here it is structural and cannot drift.
HEAD_W = 8
TORSO_W = 8
ARM_W = 4

# ----------------------------------------------------------------- sprites --
# Sprites are text maps. One character per texel, so adding a role means
# adding a small block of text rather than editing code.
#
#   .  transparent        s/S  skin base/shade       h/H  hair base/shade
#   e  eye (black)        m    mouth (shade of skin)
#   a/A sleeve base/shade t/T  top (role hue) base/shade
#   c   accent            k    black       w    white
#   p/P prop base/shade

HEAD_DEFAULT = [
    "hhhhhhhh",
    "hhhhhhhh",
    "ssssssss",
    "seessees",
    "ssssssss",
    "ssssssss",
    "sssmmsss",
    "ssssssss",
]

# Headwear replaces the top rows of the head. It is the separator that
# survives to 32px: at that size a held prop is a smudge and the outline of
# the head is still legible.
HEADWEAR = {
    "none":      [],
    "flat_hair": ["hhhhhhhh", "hhhhhhhh"],
    "side_part": ["hhhhhhhh", "hhhhhhhH"],
    "hard_hat":  ["..tttt..", "tttttttt"],
    "cap_back":  ["..tttt..", "tttttttt"],
    "beanie":    ["..tttt..", "tttttttt"],
    "beret":     ["..tttt..", ".tttttt."],
    "headset":   ["hhhhhhhh", "khhhhhhk"],
    "visor":     ["hhhhhhhh", "tttttttt"],
}

BODY_DEFAULT = [
    "......ssssssss......",   # neck row, skin
    "..aaaaccccccccaaaa..",   # collar / accent
    "..aaaaTTTTTTTTaaaa..",
    "..aaaaTTTTTTTTaaaa..",
    "..aaaaTTTTTTTTaaaa..",
    "..aaaaTTTTTTTTaaaa..",
    "..aaaaTTTTTTTTaaaa..",
    "..aaaaTTTTTTTTaaaa..",
    "..aaaaTTTTTTTTaaaa..",
]

# Props are drawn over the body layer, held at chest height or raised —
# anything held low falls outside a bust crop entirely.
PROPS: dict[str, list[tuple[str, int]]] = {
    "none":      [],
    "briefcase": [("......PPPPPPPP......", 14), ("......PppppppP......", 15)],
    "candles":   [("....PP..PP..PP......", 13), ("....PP..PP..PP......", 14)],
    "tray":      [(".....PPPPPPPPPP.....", 13), ("......pppppppp......", 14)],
    "wrench":    [("....PP........PP....", 13), ("....PP........PP....", 14)],
    "camera":    [(".....PPPPPPPP.......", 13), (".....PppppPPP.......", 14)],
    "megaphone": [(".....PPPP...........", 13), ("....PPPPPP..........", 14)],
    "magnifier": [("....PPPP............", 13), ("....PppP............", 14)],
    "toolbox":   [("......PPPPPPPP......", 14), ("......PppppppP......", 15)],
}


def _prop_rows(name: str) -> list[tuple[str, int]]:
    """Prop sprite rows as (row_text, row_index). Unknown names draw nothing."""
    return PROPS.get(name, [])


# ------------------------------------------------------------------- roles --
# A worked example, NOT the menu. Any roster the user actually runs gets its
# own rows; see "Deriving a kit" in SKILL.md.
EXAMPLE_ROLES = {
    "career":    {"hue": "blue",       "headwear": "side_part", "prop": "briefcase"},
    "trading":   {"hue": "cyan",       "headwear": "headset",   "prop": "candles"},
    "admin":     {"hue": "light_gray", "headwear": "flat_hair", "prop": "tray"},
    "engineer":  {"hue": "yellow",     "headwear": "hard_hat",  "prop": "wrench"},
    "filmer":    {"hue": "magenta",    "headwear": "cap_back",  "prop": "camera"},
    "marketing": {"hue": "light_blue", "headwear": "beret",     "prop": "megaphone"},
    "research":  {"hue": "purple",     "headwear": "visor",     "prop": "magnifier"},
    "ops":       {"hue": "lime",       "headwear": "beanie",    "prop": "toolbox"},
}

# Shared slots — identical for every member. This is the family resemblance,
# and it carries more weight in a bust than in a full-body crew because
# cropping removes shared area.
SHARED = {
    "skin": "brown",
    "sleeve": "gray",          # darker than the torso so arms read as arms
    "background": "light_gray",
    "hair": "black",
    "prop_dark": "black",      # props contrast with every role hue
    "prop_light": "white",
}


# ---------------------------------------------------------------- plumbing --
def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def write_png(path: pathlib.Path, pixels: list[list[tuple[int, int, int]]]) -> None:
    """Minimal RGB PNG writer — stdlib only, no anti-aliasing by construction."""
    h, w = len(pixels), len(pixels[0])
    raw = b"".join(
        b"\x00" + b"".join(struct.pack("3B", *px) for px in row) for row in pixels
    )

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">2I5B", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    path.write_bytes(png)


def build_grid(role: str, cfg: dict, shared: dict) -> list[list[str | None]]:
    """Compose one avatar as a GRID_H x GRID_W map of palette keys."""
    hue = cfg["hue"]
    colours = {
        "s": (shared["skin"], 0),    "S": (shared["skin"], 1),
        "m": (shared["skin"], 1),
        "h": (shared["hair"], 0),    "H": (shared["hair"], 1),
        "e": ("black", 0),           "k": ("black", 0),   "w": ("white", 0),
        "a": (shared["sleeve"], 1),  "A": (shared["sleeve"], 1),
        "t": (hue, 0),               "T": (hue, 0),
        "c": (hue, 1),
        # 🔴 The prop must NOT use the torso hue — a yellow wrench on a yellow
        # torso is invisible, which defeats the one-prop rule entirely.
        "p": (shared["prop_dark"], 0), "P": (shared["prop_light"], 0),
    }

    grid: list[list[str | None]] = [[None] * GRID_W for _ in range(GRID_H)]

    head = list(HEAD_DEFAULT)
    for i, row in enumerate(HEADWEAR.get(cfg["headwear"], [])):
        head[i] = row
    for r, row in enumerate(head):
        for c, ch in enumerate(row):
            if ch != ".":
                grid[HEAD_TOP + r][HEAD_LEFT + c] = ch

    for r, row in enumerate(BODY_DEFAULT):
        for c, ch in enumerate(row[:GRID_W]):
            if ch != ".":
                grid[BODY_TOP + r][c] = ch

    for row_text, row_idx in _prop_rows(cfg["prop"]):
        if 0 <= row_idx < GRID_H:
            for c, ch in enumerate(row_text[:GRID_W]):
                if ch != ".":
                    grid[row_idx][c] = ch

    return [[colours.get(ch) if ch else None for ch in row] for row in grid]


def render(role: str, cfg: dict, shared: dict, scale: int) -> list[list[tuple[int, int, int]]]:
    grid = build_grid(role, cfg, shared)
    bg = hex_to_rgb(PALETTE[shared["background"]][0])
    out = []
    for row in grid:
        line = []
        for cell in row:
            rgb = bg if cell is None else hex_to_rgb(PALETTE[cell[0]][cell[1]])
            line.extend([rgb] * scale)
        out.extend([line] * scale)
    return out


def check_hues(roster: dict) -> list[str]:
    """Report palette problems rather than silently producing a broken crew."""
    problems = []
    used = [c["hue"] for c in roster.values()]
    for name, cfg in roster.items():
        if cfg["hue"] in LOW_CHROMA:
            problems.append(f"{name}: '{cfg['hue']}' is a shared-slot colour; "
                            f"it cannot carry identity at 32px")
    if "red" in used and "green" in used:
        problems.append("red and green are both role hues — roughly 1 in 12 men "
                        "cannot separate them, and a sidebar is where that fails")
    dupes = {h for h in used if used.count(h) > 1}
    for h in dupes:
        problems.append(f"'{h}' is the role hue of more than one agent — separate "
                        f"them on headwear and prop, or reassign")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="Construct blockcrew avatars on a fixed pixel grid.")
    ap.add_argument("--roster", type=pathlib.Path,
                    help="JSON: {role: {hue, headwear, prop}}. Omit for the example crew.")
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("out"))
    ap.add_argument("--scale", type=int, default=64,
                    help="pixels per texel (default 64 -> 1024x1024)")
    ap.add_argument("--list", action="store_true", help="show palette, headwear and props")
    a = ap.parse_args()

    if a.list:
        print("role hues :", ", ".join(ROLE_HUES))
        print("shared    :", ", ".join(sorted(LOW_CHROMA)))
        print("headwear  :", ", ".join(HEADWEAR))
        print("props     :", ", ".join(PROPS))
        return 0

    roster = json.loads(a.roster.read_text()) if a.roster else EXAMPLE_ROLES
    if not a.roster:
        print("⚠️  No --roster given, rendering the EXAMPLE crew.")
        print("   These are demonstration roles, not a menu — pass your own.\n")

    for p in check_hues(roster):
        print(f"⚠️  {p}")

    a.out.mkdir(parents=True, exist_ok=True)
    for role, cfg in roster.items():
        px = render(role, cfg, SHARED, a.scale)
        path = a.out / f"{role}.png"
        write_png(path, px)
        print(f"✅ {path}  {len(px[0])}x{len(px)}  hue={cfg['hue']} "
              f"headwear={cfg['headwear']} prop={cfg['prop']}")

    print(f"\n{len(roster)} avatars — identical geometry, palette and lighting by "
          f"construction, not by inspection.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
