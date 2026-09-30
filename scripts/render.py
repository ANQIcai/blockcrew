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
from boxes import Box, draw_box, project, FACE_FRONT, FACE_TOP, FACE_SIDE
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


# ------------------------------------------------------------------ species --
# 🔴 A crew does not have to be human. The shared-slot architecture is
# species-agnostic: swap the head map and the same rules produce a crew of
# animals, robots or creatures.
#
# Species heads are written across the FULL canvas width (20) because ears and
# muzzles sit outside the 8-texel skull. Rows are 8 tall, same as a human head.
#
#   f/F  fur base / fur shadow      n  muzzle (light)
#   e    eye        k  black         w  white
#   d    dark mask patch             i  inner ear

# Headwear that is HAIR rather than a hat. Never applied to an animal head.
HAIR_HEADWEAR = {"none", "flat_hair", "side_part", "headset", "visor"}


def _body(shared: dict) -> str:
    """The exposed-body material: fur on a species crew, skin on a human one."""
    if shared.get("species", "human") != "human":
        return shared.get("fur", shared["skin"])
    return shared["skin"]


SPECIES_HEADS: dict[str, list[str]] = {
    # The default: a plain blocky person. Written by HEAD_DEFAULT + headwear.
    "human": [],

    # Raccoon — the mask IS the identity, and the ears break the square skull
    # outline so it survives the silhouette test.
    "raccoon": [
        "....FF........FF....",
        "....FiF......FiF....",
        "......ffffffff......",
        "......dddddddd......",
        "......dwddddwd......",   # 🔴 eyes must be LIGHT inside a dark mask
        "......ffffffff......",
        "......ffnnnnff......",
        "......ffnkknff......",
    ],

    # Cat — tall pointed ears, small muzzle.
    "cat": [
        "......F......F......",   # 🔴 ears must TOUCH the skull (cols 6-13)
        "......FF....FF......",   # or they render as floating debris
        "......ffffffff......",
        "......fkffffkf......",
        "......ffffffff......",
        "......ffnnnnff......",
        "......fnnkknnf......",
        "......ffnnnnff......",
    ],

    # Fox — wide ears, pale muzzle, dark chin.
    "fox": [
        ".....F........F.....",
        ".....FiF....FiF.....",
        "......ffffffff......",
        "......fkffffkf......",
        "......ffffffff......",
        "......ffnnnnff......",
        "......fnnkknnf......",
        "......ffFFFFff......",
    ],

    # Bear — small round ears, broad flat muzzle.
    "bear": [
        "....FF........FF....",
        "....FiF......FiF....",
        "......ffffffff......",
        "......ffkffkff......",
        "......ffffffff......",
        "......ffnnnnff......",
        "......ffnkknff......",
        "......ffnnnnff......",
    ],
}


# ----------------------------------------------------------------- sprites --
# Sprites are text maps. One character per texel, so adding a role means
# adding a small block of text rather than editing code.
#
#   .  transparent        s/S  skin base/shade       h/H  hair base/shade
#   e  eye (black)        m    mouth (shade of skin)
#   a/A sleeve base/shade t/T  top (role hue) base/shade
#   c   accent            k    black       w    white
#   p/P prop base/shade

# 🔴 Style-guide entity rule: top and front brighter than bottom and back.
# On a front-facing bust that becomes a highlight row at the top of each mass
# and a shadow row at its lower edge. This is NOT pillow shading — the shades
# follow the form's top and bottom, not concentric rings from the centre.
# 🔴 NO FULL-WIDTH SHADE ROWS. A row of one shade across the whole face is a
# "fat line" — the guide's banding artifact. Shading arrives as material
# clusters (see apply_material), not as stripes.
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
    "......ssssssss......",   # neck
    "..aaaaccccccccaaaa..",   # collar accent
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



# ------------------------------------------------------------ base image ---
# 🔴 WHAT A BASE IMAGE CAN AND CANNOT DO
#   At 8 texels across a head face an eye is one texel. There is no likeness
#   available at this resolution and promising one would be dishonest.
#
#   What DOES transfer, and transfers well:
#     - skin tone, hair colour, clothing colour, background — snapped to the
#       nearest palette slots
#   What does not transfer at all:
#     - facial features, expression, face shape, glasses, age, hairstyle detail
#
#   ⭐ The useful framing is "same person, rendered as a crew", not "portrait".
#   Deriving the SHARED slots from one photo makes every agent read as a
#   variation of that one character, which is exactly what the shared-slot
#   architecture already does — the photo just supplies the values.


def _load_pixels(path: pathlib.Path) -> tuple[list[list[tuple[int, int, int]]], int, int]:
    """Decode an image to RGB rows. Pillow if present, else ffmpeg, else fail."""
    try:
        from PIL import Image  # type: ignore
        im = Image.open(path).convert("RGB")
        im.thumbnail((128, 128))
        w, h = im.size
        px = list(im.getdata())
        return ([list(px[r * w:(r + 1) * w]) for r in range(h)], w, h)
    except ImportError:
        pass

    import shutil
    import subprocess
    import tempfile
    if not shutil.which("ffmpeg"):
        raise SystemExit(
            "❌ --base needs Pillow or ffmpeg to read the image.\n"
            "   pip install pillow      (or)      brew install ffmpeg\n"
            "   Alternatively pass the colours directly with --skin/--hair/--background."
        )
    with tempfile.TemporaryDirectory() as td:
        raw = pathlib.Path(td) / "s.ppm"
        subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-i", str(path),
                        "-vf", "scale=128:-1", "-pix_fmt", "rgb24", str(raw)], check=True)
        data = raw.read_bytes()
    # P6 header: magic, width height, maxval, then binary RGB
    parts, idx = [], 0
    while len(parts) < 4:
        while data[idx:idx + 1].isspace():
            idx += 1
        if data[idx:idx + 1] == b"#":
            while data[idx:idx + 1] != b"\n":
                idx += 1
            continue
        start = idx
        while not data[idx:idx + 1].isspace():
            idx += 1
        parts.append(data[start:idx])
    idx += 1
    w, h = int(parts[1]), int(parts[2])
    body = data[idx:]
    rows = []
    for r in range(h):
        off = r * w * 3
        rows.append([tuple(body[off + c * 3: off + c * 3 + 3]) for c in range(w)])
    return (rows, w, h)


def _median_colour(rows, x0f, x1f, y0f, y1f) -> tuple[int, int, int]:
    """Median RGB of a fractional region. Median, not mean — a mean of hair and
    background returns a colour present in neither."""
    h, w = len(rows), len(rows[0])
    sample = [rows[y][x]
              for y in range(int(y0f * h), max(int(y1f * h), int(y0f * h) + 1))
              for x in range(int(x0f * w), max(int(x1f * w), int(x0f * w) + 1))]
    if not sample:
        return (128, 128, 128)
    return tuple(sorted(c[i] for c in sample)[len(sample) // 2] for i in range(3))


def nearest_palette(rgb: tuple[int, int, int], allowed: list[str] | None = None) -> str:
    """Closest palette name, matching on hue and chroma, not raw RGB distance.

    🔴 Two traps, both measured on a tan skin tone #C6885B:

    1. Plain RGB distance makes grey a magnet. Grey sits near the centre of the
       colour cube and is therefore near everything mid-tone: light_gray scored
       14581 against brown's 26635, so the "nearest" colour was the one that
       looked least like it.
    2. Adding chroma alone then picked pink, because pink's chroma happens to
       match. Chroma says how colourful, not which colour.

    Hue is the discriminator. Tan and brown are the same hue family (~26°);
    pink is 300° away. Weighting hue difference is what makes skin tones land
    on brown instead of bubblegum.
    """
    import colorsys

    def hcl(c):
        r, g, b = (x / 255 for x in c)
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        return h * 360, (max(c) - min(c)), l * 255

    th, tc, tl = hcl(rgb)
    best, best_d = None, float("inf")
    for name in (allowed or list(PALETTE)):
        pal = hex_to_rgb(PALETTE[name][0])
        ph, pc, pl = hcl(pal)
        hue_gap = min(abs(ph - th), 360 - abs(ph - th))
        # 🔴 Hue is meaningless for near-grey colours on EITHER side. Black
        # #1D1D21 reports a hue of ~240° from three nearly equal channels;
        # weighting that against dark hair's ~28° scored 28,000 and pushed
        # black hair to brown. Fade the hue term by the LOWER of the two
        # chromas, so a grey candidate is never penalised for a hue it does
        # not really have.
        hue_w = min(tc, pc, 80) / 80
        d = (hue_gap ** 2) * 3.0 * hue_w
        # Lightness outweighs chroma: the palette has only 16 entries, so an
        # exact saturation match is rarely available while brightness almost
        # always is. Weighting chroma higher sent blond hair to brown.
        d += (pc - tc) ** 2 * 1.0
        d += (pl - tl) ** 2 * 1.5
        if d < best_d:
            best, best_d = name, d
    return best or "gray"


def derive_from_base(path: pathlib.Path) -> dict:
    """Sample a portrait for skin, hair, top and background palette slots.

    ⚠️ Regions are fixed fractions of the frame, assuming a roughly centred
    head-and-shoulders subject. No face detection — it would add a heavy
    dependency to guess what the user can simply override.
    """
    rows, w, h = _load_pixels(path)
    hair_rgb = _median_colour(rows, 0.42, 0.58, 0.06, 0.16)
    skin_rgb = _median_colour(rows, 0.44, 0.56, 0.32, 0.44)
    top_rgb  = _median_colour(rows, 0.35, 0.65, 0.80, 0.94)
    bg_rgb   = _median_colour(rows, 0.00, 0.08, 0.00, 0.08)

    # 🔴 Constrain each slot to plausible slots BEFORE matching. Unconstrained,
    # a tan skin tone (#C6885B) lands on light_gray, because the palette has no
    # skin colours and grey is numerically closest to everything mid-tone.
    # Nearest-colour matching is only meaningful inside a candidate set that
    # makes sense for the slot.
    SKIN_SLOTS = ["brown", "orange", "pink", "white", "light_gray", "black"]
    HAIR_SLOTS = ["black", "brown", "yellow", "orange", "white", "light_gray", "gray"]

    derived = {
        "hair": nearest_palette(hair_rgb, allowed=HAIR_SLOTS),
        "skin": nearest_palette(skin_rgb, allowed=SKIN_SLOTS),
        "sleeve": nearest_palette(top_rgb, allowed=sorted(LOW_CHROMA)),
        "background": nearest_palette(bg_rgb, allowed=sorted(LOW_CHROMA)),
    }
    derived["_sampled"] = {"hair": hair_rgb, "skin": skin_rgb,
                           "top": top_rgb, "background": bg_rgb}
    return derived



# ------------------------------------------------------------ colour ramps ---
# 🔴 A STRAIGHT RAMP IS THE WRONG RAMP
#   A straight ramp varies only brightness. The Minecraft style guide is blunt
#   about it: straight ramps "often aren't used due to their dull look".
#   Vanilla ramps are HUE-SHIFTED — shadows shift toward blue and gain
#   saturation, highlights shift toward yellow and lose it.
#
#   ⭐ This is why a technically-correct palette can still look flat. The
#   palette supplies the MIDTONE; the ramp is derived from it by rule.
#
#   Measured on cyan #169C9C:
#     straight  #107575 → #169C9C            (two values, same hue)
#     shifted   #09616D → #169C9C → #29B8A7  (hue rotates across the ramp)

RAMP_SPEC = (
    (-0.30, +0.020, +0.06),   # shadow:    darker, toward blue, more saturated
    (0.0,    0.0,    0.0),    # midtone:   the palette value itself
    (+0.18, -0.020, -0.08),   # highlight: brighter, toward yellow, less saturated
)


def shade(rgb: tuple[int, int, int], mult: float) -> tuple[int, int, int]:
    """Apply a vanilla face multiplier.

    🔴 THE NUMBERS ARE FROM THE GAME, NOT FROM TASTE.
        top 1.0 · north/south 0.8 · east/west 0.6 · bottom 0.5
    Blocks cast no shadows on each other — the sun's position never darkens
    anything — so a face's brightness depends ONLY on which way it points.

    ⭐ Three faces of one box at 1.0 / 0.8 / 0.6 is the look the eye
    recognises. A flat front-facing sprite has one orientation, therefore one
    tone, and reads as generic pixel art however correct the palette is.
    """
    return tuple(max(0, min(255, round(c * mult))) for c in rgb)


def ramp(palette_name: str) -> list[tuple[int, int, int]]:
    """Three-shade hue-shifted ramp derived from a palette midtone.

    The palette entry is the identity colour. The shades are computed, not
    invented: one deterministic rule applied to every material, which is what
    keeps a crew lit consistently.
    """
    import colorsys
    r, g, b = (c / 255 for c in hex_to_rgb(PALETTE[palette_name][0]))
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    out = []
    for dv, dh, ds in RAMP_SPEC + MATERIAL_SPEC[0::2]:
        rr, gg, bb = colorsys.hsv_to_rgb(
            (h + dh) % 1.0,
            max(0.0, min(1.0, s + ds)),
            max(0.0, min(1.0, v * (1 + dv))),
        )
        out.append((round(rr * 255), round(gg * 255), round(bb * 255)))
    return out


SHADOW, MID, HIGHLIGHT = 0, 1, 2

# 🔴 A SECOND, SUBTLER RAMP FOR MATERIAL.
#   The display ramp (±30% / +18%) describes FORM — which plane faces the
#   light. Using those same values for material clusters produces blotches,
#   which is the guide's "noise" artifact: it "adds no information to the
#   texture". Material variation has to be quiet enough to read as fabric
#   rather than as dirt.
MATERIAL_SPEC = (
    (-0.11, +0.010, +0.03),   # material shadow
    (0.0,    0.0,    0.0),
    (+0.08, -0.010, -0.03),   # material highlight
)
MAT_SHADOW, MAT_HIGHLIGHT = 3, 4


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



# --------------------------------------------------------- material clusters --
# 🔴 STEP 4 OF THE GUIDE'S ENTITY PROCEDURE — the one this renderer skipped.
#
#   "Sketch the colour distribution, add a shadow and a highlight. Add more
#    shades to the palette. DEFINE THE MATERIAL by editing the relative
#    position of CLUSTERS of certain shades. Get rid of banding."
#
# Stopping after "add a shadow and a highlight" is what produced flat blocks
# with horizontal stripes. Measured on the shipped sheet: the torso was
# literally AAAAAAAA / BBBBBBBB / CCCCCCCC — the guide's "fat lines", which it
# says "reveals the pixel grid, distracts the eye and the shape is
# misrepresented".
#
# ⭐ Clusters, NOT noise. The guide rejects both: noise is per-texel speckle
# that "adds no information"; banding is texels lined up brightest-to-darkest.
# The answer is small irregular GROUPS of 2-3 adjacent texels that never form
# a row, column or diagonal run.
#
# Masks are FIXED, not random — every crew member gets the same material
# pattern in a different hue, so the set stays identical by construction.

#   H = highlight cluster    S = shadow cluster    . = midtone
TORSO_MATERIAL = [
    "..HH....",
    "..H.....",
    "......S.",
    "......SS",
    "HH......",
    ".H......",
    "....SS..",
    "......H.",
]

HEAD_MATERIAL = [
    "..H.....",
    "........",
    "......S.",
    "........",
    "........",
    ".S......",
    "........",
    "....H...",
]


def apply_material(grid, top, left, mask, base_key, shade_keys):
    """Overlay material clusters onto an already-filled region.

    Only rewrites texels that currently hold the region's midtone, so clusters
    never overwrite eyes, props or clothing accents.
    """
    hi_key, lo_key = shade_keys
    for r, row in enumerate(mask):
        for c, ch in enumerate(row):
            if ch == ".":
                continue
            y, x = top + r, left + c
            if not (0 <= y < len(grid) and 0 <= x < len(grid[0])):
                continue
            cur = grid[y][x]
            if cur is None or cur[0] != base_key:
                continue
            grid[y][x] = (base_key, hi_key if ch == "H" else lo_key)


def banding_score(grid, hue: str) -> int:
    """Longest full-width uniform run of the torso MATERIAL. 0 is correct.

    🔴 The guide's definition: banding is "pixels that line up in a sequence
    from brightest to darkest ... in straight lines (a.k.a. fat lines)". It
    "reveals the pixel grid, distracts the eye and the shape is
    misrepresented".

    Scoped to the hue material only. The neck, the prop and the collar accent
    are full-width by design — they are SHAPES, not shading, and counting them
    makes the check fire on correct output.

    Verified against a forced-band control: this must return 8 for a striped
    torso and 0 for every shipped avatar.
    """
    worst = 0
    for y in range(BODY_TOP + 2, GRID_H):
        row = grid[y][HEAD_LEFT:HEAD_LEFT + TORSO_W]
        if any(c is None or c[0] != hue for c in row):
            continue
        if len(set(row)) == 1:
            worst = max(worst, len(row))
    return worst


def banding_score(buf: list[list]) -> int:
    """Longest uniform horizontal run on torso material rows.

    🔴 Measured to catch the banding the style guide names: 'pixels that line
    up in a sequence from brightest to darkest, whether in straight lines
    (a.k.a. fat lines)'.

    Scoped to rows where the torso hue dominates. The neck and collar accent
    are one-tone by design — counting them makes the gate fire on correct
    output. Only the torso material rows (12-17 in the 3/4 view) are checked.
    """
    worst = 0
    for y in range(TORSO_SCREEN_TOP + 2, TORSO_SCREEN_TOP + 8):  # rows 12-17
        if y >= len(buf):
            break
        run_len = 1
        for x in range(TORSO_SCREEN_LEFT + 1, TORSO_SCREEN_LEFT + 8):
            if x >= len(buf[y]):
                break
            prev = buf[y][x-1]
            curr = buf[y][x]
            if prev is not None and curr is not None and prev == curr:
                run_len += 1
            else:
                run_len = 1
        # Only full-width runs are banding; 6 out of 8 is base tone with clusters.
        if run_len == 8:
            worst = 8
    return worst


def check_species_contrast(shared: dict) -> list[str]:
    """Warn when a species crew's markings will not read.

    🔴 CALIBRATED AGAINST MEASURED FAILURES, not intuition. Three renders,
    luminance differences in the 0-255 range:

        combination                        fur-bg  mask-fur  mask-bg   verdict
        light_gray fur / gray bg             79      127       48      washed out
        light_gray fur / black bg           127      127        0      mask lost
        brown fur / light_gray bg            65       62      127      reads

    ⭐ The combination that READS has the LOWEST fur-vs-background contrast of
    the three. The first rule I wrote checked fur-vs-background and passed
    every failing case — it was decoration, not a gate.

    The two pairs that actually discriminate:

    1. **mask vs background.** The mask band spans the full head width, so it
       touches the silhouette edge. When it matches the background the head's
       outline breaks there and the face detaches.
    2. **mask vs fur, as a BAND not a floor.** Too little and the marking
       vanishes; too much and the mask reads as the whole head rather than as
       a stripe across it. Both failures are 127; the one that works is 62.
    """
    if shared.get("species", "human") == "human":
        return []

    def lum(name: str) -> float:
        r, g, b = hex_to_rgb(PALETTE[name][0])
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    fur = shared.get("fur", shared["skin"])
    bg = shared["background"]
    mask = shared.get("mask", "black")
    muzzle = shared.get("muzzle", "white")

    warn = []
    if abs(lum(mask) - lum(bg)) < 60:
        warn.append(f"mask '{mask}' vs background '{bg}': the mask touches the "
                    f"head's outline, so the face will detach from the skull")
    d = abs(lum(mask) - lum(fur))
    if d < 35:
        warn.append(f"mask '{mask}' vs fur '{fur}': too close, the marking "
                    f"will not read")
    elif d > 110:
        warn.append(f"mask '{mask}' vs fur '{fur}': too extreme, the mask will "
                    f"read as the whole head instead of a band across it")
    if abs(lum(muzzle) - lum(fur)) < 30:
        warn.append(f"muzzle '{muzzle}' vs fur '{fur}': too close to read")
    return warn


# --------------------------------------------------------------- props (3/4) --
# 🔴 MEASURED, NOT ASSUMED: the torso's front face occupies screen rows 10-17
# and columns 5-12. Props are drawn into that 8x8 field.
#
# The old 2-row props were invisible at 32px per texel. Four rows is the
# minimum for a shape to read as an object rather than as a stripe.
PROPS_3D = {
    "none": [],
    "briefcase": ["..PPPP..",
                  ".PPPPPP.",
                  ".PppppP.",
                  ".PPPPPP."],
    "candles":   ["...P....",
                  ".P.P.P..",
                  ".P.P.P.P",
                  ".PPPPPPP"],
    "tray":      ["........",
                  ".pppppp.",
                  "PPPPPPPP",
                  "..P..P.."],
    "wrench":    ["....PP..",
                  "...PP...",
                  "..PP....",
                  ".PP.P..."],
    "camera":    [".PPPPPP.",
                  ".PppppP.",
                  ".PpPPpP.",
                  ".PPPPPP."],
    "megaphone": ["....PP..",
                  "..PPPPP.",
                  ".PPPPPP.",
                  "..PPPPP."],
    "magnifier": [".PPPP...",
                  ".PppP...",
                  ".PPPP...",
                  "....PP.."],
    "toolbox":   ["...PP...",
                  ".PPPPPP.",
                  ".PppppP.",
                  ".PPPPPP."],
}

TORSO_SCREEN_TOP, TORSO_SCREEN_LEFT = 10, 5


def paint_prop(buf, prop_name: str) -> None:
    """Paint the prop onto the torso's front face.

    Placed at the measured location of that face rather than at an offset
    guessed from the old flat grid — which is what silently dropped props in
    the 3/4 rewrite.
    """
    art = PROPS_3D.get(prop_name) or []
    for r, row in enumerate(art):
        sy = TORSO_SCREEN_TOP + 2 + r
        if not (0 <= sy < VIEW_H):
            continue
        for c, ch in enumerate(row):
            sx = TORSO_SCREEN_LEFT + c
            if ch != "." and 0 <= sx < VIEW_W and buf[sy][sx] is not None:
                buf[sy][sx] = (ch, FACE_FRONT)


def colour_map(cfg: dict, shared: dict) -> dict:
    """Texel key -> (palette name, ramp index)."""
    hue = cfg["hue"]
    colours = {
        # On a species crew the exposed-body slots are fur, not human skin.
        "s": (_body(shared), MID),       "S": (_body(shared), SHADOW),
        "m": (_body(shared), SHADOW),
        "h": (shared["hair"], MID),      "H": (shared["hair"], SHADOW),
        "e": (shared["hair"], SHADOW),   "k": ("black", MID),
        "w": ("white", MID),
        # species layer: fur uses the SHARED slot so a crew stays one species
        "f": (shared.get("fur", shared["skin"]), MID),
        "F": (shared.get("fur", shared["skin"]), SHADOW),
        "n": (shared.get("muzzle", "white"), MID),
        "d": (shared.get("mask", "black"), MID),
        "i": (shared.get("muzzle", "white"), SHADOW),
        "a": (shared["sleeve"], MID),    "A": (shared["sleeve"], SHADOW),
        "t": (hue, MID),                 "T": (hue, MID),
        "c": (hue, HIGHLIGHT),
        # The prop must not use the torso hue — a yellow wrench on a yellow
        # torso is invisible, which defeats the one-prop rule entirely.
        "p": (shared["prop_dark"], MID), "P": (shared["prop_light"], MID),
    }

    return colours


def apply_material_3d(buf, colours):
    """Step 4 of the entity procedure, applied per visible face.

    Clusters are keyed to the texel's own face multiplier so a cluster on the
    lit top face and one on the shaded side stay distinguishable.
    """
    for y, row in enumerate(buf):
        for x, cell in enumerate(row):
            if cell is None:
                continue
            key, mult = cell
            pal = colours.get(key)
            if not pal or pal[0] not in ROLE_HUES:
                continue
            if TORSO_MATERIAL[y % len(TORSO_MATERIAL)][x % 8] == "H":
                buf[y][x] = (key, mult * 1.06)
            elif TORSO_MATERIAL[y % len(TORSO_MATERIAL)][x % 8] == "S":
                buf[y][x] = (key, mult * 0.94)


def build_grid(role: str, cfg: dict, shared: dict) -> list[list[str | None]]:
    """Compose one avatar as a GRID_H x GRID_W map of palette keys."""
    hue = cfg["hue"]
    # (palette_name, ramp_index) — SHADOW / MID / HIGHLIGHT.
    # 🔴 Entity rule from the style guide: "the top and front of the entity need
    # to be brighter than the bottom and back." So an outline is the SHADOW of
    # its own material, never a separate black — black outlines are an item-
    # texture convention and look wrong on an entity.
    colours = {
        # On a species crew the exposed-body slots are fur, not human skin.
        "s": (_body(shared), MID),       "S": (_body(shared), SHADOW),
        "m": (_body(shared), SHADOW),
        "h": (shared["hair"], MID),      "H": (shared["hair"], SHADOW),
        "e": (shared["hair"], SHADOW),   "k": ("black", MID),
        "w": ("white", MID),
        # species layer: fur uses the SHARED slot so a crew stays one species
        "f": (shared.get("fur", shared["skin"]), MID),
        "F": (shared.get("fur", shared["skin"]), SHADOW),
        "n": (shared.get("muzzle", "white"), MID),
        "d": (shared.get("mask", "black"), MID),
        "i": (shared.get("muzzle", "white"), SHADOW),
        "a": (shared["sleeve"], MID),    "A": (shared["sleeve"], SHADOW),
        "t": (hue, MID),                 "T": (hue, MID),
        "c": (hue, HIGHLIGHT),
        # The prop must not use the torso hue — a yellow wrench on a yellow
        # torso is invisible, which defeats the one-prop rule entirely.
        "p": (shared["prop_dark"], MID), "P": (shared["prop_light"], MID),
    }

    grid: list[list[str | None]] = [[None] * GRID_W for _ in range(GRID_H)]

    species = cfg.get("species", shared.get("species", "human"))
    sp_head = SPECIES_HEADS.get(species) or []

    if sp_head:
        # Species heads span the full canvas width (ears sit outside the skull),
        # so they are placed at column 0, not at HEAD_LEFT.
        rows = list(sp_head)
        # 🔴 Hair-type headwear must NOT apply to an animal head — it paints a
        # helmet over the ears and destroys the silhouette. Only real hats do.
        hw_name = cfg["headwear"]
        hat_rows = [] if hw_name in HAIR_HEADWEAR else HEADWEAR.get(hw_name, [])
        for i, hw in enumerate(hat_rows):
            if i < len(rows):
                base = list(rows[i])
                for c, ch in enumerate(hw):
                    if ch != ".":
                        base[HEAD_LEFT + c] = ch
                rows[i] = "".join(base)
        for r, row in enumerate(rows):
            for c, ch in enumerate(row[:GRID_W]):
                if ch != ".":
                    grid[HEAD_TOP + r][c] = ch
    else:
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

    # Step 4 of the guide's entity procedure: define the material by the
    # relative position of shade CLUSTERS, and remove banding.
    resolved = [[colours.get(ch) if ch else None for ch in row] for row in grid]

    torso_key = colours["T"][0]
    apply_material(resolved, BODY_TOP + 1, HEAD_LEFT, TORSO_MATERIAL,
                   torso_key, (MAT_HIGHLIGHT, MAT_SHADOW))

    # 🔴 NO CLUSTERS ON THE FACE. A head face is 8x8 with eyes and a mouth in
    # it; scattered shade texels there read as dirt or stubble, not material.
    # Measured: the first attempt gave every crew member a blemished face.
    # ⭐ Material belongs on large uniform surfaces. A face is not one.

    return resolved


# ------------------------------------------------------------- 3/4 view bust --
# Real model dimensions (texels): head 8x8x8, body 8x12x4, arms 4x12x4.
# A bust crops the body at 6 of its 12 rows.
VIEW_W, VIEW_H, VIEW_OY = 22, 22, 4


# 🔴 EARS ARE BOXES, NOT TEXELS.
#   In a flat sprite an ear is a few pixels beside the skull. On a real model
#   it is a separate cuboid with its own three faces — which is why the flat
#   ear maps, sliced to the 8-wide face, came out as vertical bars.
#
#   (x offset from head, y offset, w, h, d)
SPECIES_EARS = {
    "human":   [],
    "raccoon": [(-1, 0, 3, 2, 3), (6, 0, 3, 2, 3)],
    "cat":     [(0, -1, 2, 2, 2), (6, -1, 2, 2, 2)],
    "fox":     [(-1, -1, 3, 2, 2), (6, -1, 3, 2, 2)],
    "bear":    [(-1, 0, 3, 2, 3), (6, 0, 3, 2, 3)],
}


def build_boxes(role: str, cfg: dict, shared: dict):
    """The bust as four boxes, ordered back to front."""
    species = cfg.get("species", shared.get("species", "human"))
    sp_head = SPECIES_HEADS.get(species) or []

    if sp_head:
        face = [list(r[HEAD_LEFT:HEAD_LEFT + HEAD_W]) for r in sp_head]
        hw_name = cfg["headwear"]
        hat = [] if hw_name in HAIR_HEADWEAR else HEADWEAR.get(hw_name, [])
        crown, side_key = "f", "f"
    else:
        face = [list(r) for r in HEAD_DEFAULT]
        hat = HEADWEAR.get(cfg["headwear"], [])
        crown, side_key = ("h" if face[0][0] == "h" else "s"), "s"

    for i, row in enumerate(hat):
        if i < len(face):
            face[i] = list(row)
    if hat:
        crown = hat[0].replace(".", "")[:1] or crown

    boxes_out = []
    for (ex, ey, ew, eh, ed) in SPECIES_EARS.get(species, []):
        boxes_out.append(Box(4 + ex, 1 + ey, 2 + 1, ew, eh, ed,
                             {"front": "F", "top": "F", "side": "F"}))

    return boxes_out + [
        Box(4, 9, 2, 8, 8, 4, {"front": "T", "top": "c", "side": "T"}),
        Box(0, 9, 2, 4, 8, 4, {"front": "a", "top": "a", "side": "a"}),
        Box(12, 9, 2, 4, 8, 4, {"front": "a", "top": "a", "side": "a"}),
        Box(4, 1, 2, 8, 8, 8, {"front": face, "top": crown, "side": side_key}),
    ]


def render(role: str, cfg: dict, shared: dict, scale: int):
    """Render one avatar in 3/4 view with vanilla per-face multipliers."""
    colours = colour_map(cfg, shared)
    buf = [[None] * VIEW_W for _ in range(VIEW_H)]
    depth = [[9e9] * VIEW_W for _ in range(VIEW_H)]
    for box in build_boxes(role, cfg, shared):
        draw_box(buf, box, depth, VIEW_W, VIEW_H, VIEW_OY)

    # 🔴 REGRESSION GUARD: props live on the torso's front face. The 3/4
    # rewrite dropped them because the old code painted into a flat grid.
    paint_prop(buf, cfg["prop"])

    apply_material_3d(buf, colours)

    bg = ramp(shared["background"])[MID]
    out = []
    for row in buf:
        line = []
        for cell in row:
            if cell is None:
                rgb = bg
            else:
                key, mult = cell
                pal = colours.get(key)
                rgb = shade(ramp(pal[0])[pal[1]], mult) if pal else bg
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
    ap.add_argument("--base", type=pathlib.Path,
                    help="portrait to derive skin/hair/top/background from. "
                         "Colours only — faces do not survive an 8-texel grid.")
    ap.add_argument("--skin"); ap.add_argument("--hair")
    ap.add_argument("--sleeve"); ap.add_argument("--background")
    ap.add_argument("--species", help="human (default) or: " + "/".join(
        k for k in SPECIES_HEADS if k != "human"))
    ap.add_argument("--fur"); ap.add_argument("--muzzle"); ap.add_argument("--mask")
    ap.add_argument("--list", action="store_true", help="show palette, headwear and props")
    a = ap.parse_args()

    if a.list:
        print("species   :", ", ".join(SPECIES_HEADS))
        print("role hues :", ", ".join(ROLE_HUES))
        print("shared    :", ", ".join(sorted(LOW_CHROMA)))
        print("headwear  :", ", ".join(HEADWEAR))
        print("props     :", ", ".join(PROPS))
        return 0

    shared = dict(SHARED)
    if a.base:
        derived = derive_from_base(a.base)
        sampled = derived.pop("_sampled")
        print(f"🎨 Base image: {a.base.name}")
        for slot, name in derived.items():
            r, g, b = sampled["top" if slot == "sleeve" else slot]
            print(f"   {slot:11} sampled #{r:02X}{g:02X}{b:02X} → {name} "
                  f"({PALETTE[name][0]})")
        print("   ⚠️  Colours only. Facial features, expression and hairstyle "
              "do not survive an 8-texel grid.")
        print("   Override any slot with --skin/--hair/--sleeve/--background\n")
        shared.update(derived)

    if a.species:
        if a.species not in SPECIES_HEADS:
            print(f"❌ '{a.species}' is not a species. Options: "
                  f"{', '.join(SPECIES_HEADS)}")
            return 1
        shared["species"] = a.species

    for slot in ("skin", "hair", "sleeve", "background", "fur", "muzzle", "mask"):
        if getattr(a, slot, None):
            val = getattr(a, slot)
            if val not in PALETTE:
                print(f"❌ '{val}' is not a palette slot. Run --list.")
                return 1
            shared[slot] = val

    roster = json.loads(a.roster.read_text()) if a.roster else EXAMPLE_ROLES
    if not a.roster:
        print("⚠️  No --roster given, rendering the EXAMPLE crew.")
        print("   These are demonstration roles, not a menu — pass your own.\n")

    for p in check_hues(roster):
        print(f"⚠️  {p}")

    a.out.mkdir(parents=True, exist_ok=True)
    for w in check_species_contrast(shared):
        print(f"⚠️  {w}")

    for role, cfg in roster.items():
        px = render(role, cfg, shared, a.scale)
        path = a.out / f"{role}.png"
        write_png(path, px)
        print(f"✅ {path}  {len(px[0])}x{len(px)}  hue={cfg['hue']} "
              f"headwear={cfg['headwear']} prop={cfg['prop']}")

    print(f"\n{len(roster)} avatars — identical geometry, palette and lighting by "
          f"construction, not by inspection.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
