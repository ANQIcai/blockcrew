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
from boxes import Box, draw_box, order_boxes, canvas_bounds, FACE_RAMP
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
    # 🔴 TWO WARM SLOTS ADDED, MEASURED FROM A REFERENCE THAT READS AS PRETTY.
    #   In that reference the two dominant colours are 62% of the image:
    #   a warm cream background (39.5%) and a near-white face (22.8%).
    #   ⭐ Prettiness comes from a large calm warm area, not from more detail.
    #   A mid-grey background reads as a technical diagram; cream reads as art.
    "cream":      ("#FFF3DE", "#EEE5D7"),
    "ivory":      ("#FFFDF5", "#EEE5D7"),
    "white":      ("#F9FFFE", "#E6E6E6"),
    "light_gray": ("#B8B1A6", "#948D83"),   # warm grey, measured from the reference
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
LOW_CHROMA = {"cream", "ivory", "white", "light_gray", "gray", "black", "brown"}
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
HEAD_W = 12
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

    # 🔴 12 ROWS x 20 COLS. The face is sliced [6:18], so the skull occupies
    #   columns 6-17. Ears are separate BOXES (SPECIES_EARS), not texels here.
    #   Eyes are taller than wide and set far apart, with a large blank cheek
    #   area — the proportions measured off reference art that reads as pretty.
    "raccoon": [
        "......ffffffffffff..",
        "......ffffffffffff..",
        "......dddddddddddd..",   # the mask band
        "......dddddddddddd..",
        "......dwwdddddwwdd..",   # light eyes inside the dark mask
        "......dwwdddddwwdd..",
        "......dwwdddddwwdd..",
        "......dddddddddddd..",
        "......ffffffffffff..",
        "......ffffnnnnffff..",   # muzzle
        "......ffffnkknffff..",
        "......ffffffffffff..",
    ],

    "cat": [
        "......ffffffffffff..",
        "......ffffffffffff..",
        "......ffffffffffff..",
        "......ffkkffffkkff..",
        "......ffkkffffkkff..",
        "......ffkkffffkkff..",
        "......ffffffffffff..",
        "......ffffffffffff..",
        "......ffffnnnnffff..",
        "......fffnkkknfff..f",
        "......ffffnnnnffff..",
        "......ffffffffffff..",
    ],

    "fox": [
        "......ffffffffffff..",
        "......ffffffffffff..",
        "......ffffffffffff..",
        "......ffkkffffkkff..",
        "......ffkkffffkkff..",
        "......ffkkffffkkff..",
        "......ffffffffffff..",
        "......ffffnnnnffff..",
        "......fffnnnnnnfff..",
        "......fffnkkkknfff..",
        "......ffffnnnnffff..",
        "......ffffffffffff..",
    ],

    "bear": [
        "......ffffffffffff..",
        "......ffffffffffff..",
        "......ffffffffffff..",
        "......fffkkffkkfff..",
        "......fffkkffkkfff..",
        "......ffffffffffff..",
        "......ffffffffffff..",
        "......ffffnnnnffff..",
        "......fffnnnnnnfff..",
        "......fffnkkkknfff..",
        "......ffffnnnnffff..",
        "......ffffffffffff..",
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
# 🔴 A 12x12 FACE, NOT 8x8 — MEASURED AGAINST A REFERENCE THAT READS AS PRETTY.
#   Eyes are 2 wide x 3 tall: TALLER THAN WIDE, set far apart, low on the face,
#   with a large blank cheek area around them.
#   ⭐ Appeal in small character art comes from big calm areas, not from detail
#   density. In the reference, 62% of the image is just two colours.
HEAD_DEFAULT = [
    "hhhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "hhhhhhhhhhhh",
    "ssssssssssss",
    "ssssssssssss",
    "sseessseeess",
    "sseessseeess",
    "sseessseeess",
    "ssssssssssss",
    "sssssmmsssss",
    "ssssssssssss",
    "ssssssssssss",
]

# Headwear replaces the top rows of the head. It is the separator that
# survives to 32px: at that size a held prop is a smudge and the outline of
# the head is still legible.
HEADWEAR = {
    "none":      [],
    "flat_hair": ["hhhhhhhhhhhh", "hhhhhhhhhhhh"],
    "side_part": ["hhhhhhhhhhhh", "hhhhhhhhhhhH"],
    "hard_hat":  ["...tttttt...", "tttttttttttt"],
    "cap_back":  ["...tttttt...", "tttttttttttt"],
    "beanie":    ["...tttttt...", "tttttttttttt"],
    "beret":     ["...tttttt...", "..tttttttt.."],
    "headset":   ["hhhhhhhhhhhh", "khhhhhhhhhhk"],
    "visor":     ["hhhhhhhhhhhh", "tttttttttttt"],
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
    # 🔴 MEASURED DEFAULTS. In the reference that reads as pretty, the two
    #   dominant colours are 62% of the image: cream background + ivory face.
    #   ⭐ The calm warm field IS the prettiness. Grey-on-grey reads technical.
    "skin": "ivory",
    "sleeve": "light_gray",    # darker than the face so arms read as arms
    "background": "cream",
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


def shade_for_face(ramp_steps, idx: int, face: str) -> tuple[int, int, int]:
    """Pick the ramp step a texel shows on a given face. NO multipliers.

    🔴 THE SKIN RENDERERS APPLY NO BRIGHTNESS MULTIPLIERS. Crafatar, Mineatar
    and NMSR composite the texture's own pixels onto each face unchanged; the
    texture carries the shading. Four iterations here borrowed the BLOCK
    renderer's 1.0/0.8/0.6 constants (then rebased them) — a problem the
    recognised renderers never had, because they never introduced it.

    Our texture is a hue-shifted ramp, so a face selects the step instead:
    top = HIGHLIGHT, front = MID, side = SHADOW. A texel that already carries
    its own step (eye, mouth, collar accent, material cluster) keeps it on
    every face — that is what a painted texture does.
    """
    if idx == MID:
        idx = FACE_RAMP[face]
    return ramp_steps[idx]


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


# ------------------------------------------------------------ props (3D) --
# 🔴 PROPS LIVE IN TEXTURE SPACE, NOT SCREEN SPACE. The previous renderer
# painted them onto measured screen rows, which broke the moment the camera
# moved. Here a prop is painted into the TORSO'S FRONT TEXEL MAP before the
# box is projected, so it shears with the face like a printed logo would.
#
# The torso front is 10 texels wide and 9 tall (a bust crops the 18-tall
# torso at half); a prop is 10x4 and sits on rows 3-6. Rows 0-2 are the
# collar zone, partly under the head's overhang in the isometric view.
PROPS_3D = {
    "none": [],
    "briefcase": ["..PPPPPP..",
                  ".PPPPPPPP.",
                  ".PppppppP.",
                  ".PPPPPPPP."],
    "candles":   ["....PP....",
                  "..P.PP.P..",
                  "..P.PP.P.P",
                  "..PPPPPPPP"],
    "tray":      ["..........",
                  "..pppppp..",
                  "PPPPPPPPPP",
                  "...P..P..."],
    "wrench":    [".....PPP..",
                  "....PPP...",
                  "..PPP.....",
                  ".PPP......"],
    "camera":    ["..PPPPPP..",
                  "..PppppP..",
                  "..PpPPpP..",
                  "..PPPPPP.."],
    "megaphone": [".....PP...",
                  "...PPPPP..",
                  "..PPPPPP..",
                  "...PPPPP.."],
    "magnifier": ["..PPPP....",
                  "..PppP....",
                  "..PPPP....",
                  ".....PP..."],
    "toolbox":   ["....PP....",
                  "..PPPPPP..",
                  "..PppppP..",
                  "..PPPPPP.."],
}

TORSO_W3D, TORSO_H3D, TORSO_D3D = 10, 9, 6
PROP_ROW = 3


def torso_front_map(prop_name: str) -> list[list[str]]:
    """The torso's front texture: role hue, material clusters, then the prop.

    Material keys 'T+' / 'T-' are the hue at MAT_HIGHLIGHT / MAT_SHADOW. They
    are applied only where the texel is still plain hue, so a cluster never
    lands on the prop.
    """
    rows = [["T"] * TORSO_W3D for _ in range(TORSO_H3D)]
    for r in range(TORSO_H3D):
        for c in range(TORSO_W3D):
            m = TORSO_MATERIAL[r % len(TORSO_MATERIAL)][c % 8]
            if m == "H":
                rows[r][c] = "T+"
            elif m == "S":
                rows[r][c] = "T-"
    for r, row in enumerate(PROPS_3D.get(prop_name) or []):
        y = PROP_ROW + r
        if 0 <= y < TORSO_H3D:
            for c, ch in enumerate(row[:TORSO_W3D]):
                if ch != ".":
                    rows[y][c] = ch
    return rows


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
    # Material clusters: only on a role hue. On a shared-slot hue they would
    # read as dirt, so they collapse to the plain midtone.
    if hue in ROLE_HUES:
        colours["T+"] = (hue, MAT_HIGHLIGHT)
        colours["T-"] = (hue, MAT_SHADOW)
    else:
        colours["T+"] = colours["T-"] = (hue, MID)
    return colours


# ------------------------------------------------------------ isometric head --
# 🔴 THE HEAD IS TWO BOXES. The 64x64 skin has a second layer over the head
# (the "hat" layer), and every renderer people recognise composites it. In-
# game it is inflated 0.5 texel beyond the skull, which is why hair and hats
# sit PROUD of the head instead of being painted flat onto it.
#
#   base    : 12x12x12 cube — face, hair, side, crown
#   overlay : 13x13x13 cube, offset −0.5 on every axis — headwear only,
#             transparent wherever there is no hat
#
# The head is a CUBE. The previous 12x12x8 depth was a crowding fix for the
# cabinet projection; a true isometric view of a cube is the shape Crafatar
# draws, and anything shallower reads as a tile.
HEAD_SIZE = 12
OVERLAY_INFLATE = 0.5

# Head model origin (texels). The bust hangs below this.
HEAD_X, HEAD_Y, HEAD_Z = 2, 2, 2


# 🔴 EARS ARE BOXES, NOT TEXELS.
#   On a real model an ear is a separate cuboid with its own three faces.
#   Offsets are in head texels: (x from the head's left edge, y offset from
#   the head's top — ears STAND on the skull, so their bottom is at head top
#   plus this offset, w, h, d). Mirror pairs straddle the head's top corners.
SPECIES_EARS = {
    "human":   [],
    "raccoon": [(-2, 0, 4, 3, 4), (10, 0, 4, 3, 4)],
    "cat":     [(0, 0, 3, 4, 3), (9, 0, 3, 4, 3)],
    "fox":     [(-1, 0, 4, 4, 3), (9, 0, 4, 4, 3)],
    "bear":    [(-2, 0, 4, 3, 4), (10, 0, 4, 3, 4)],
}


def _first_key(row) -> str | None:
    for ch in row:
        if ch != ".":
            return ch
    return None


def head_boxes(cfg: dict, shared: dict) -> list:
    """Base cube + overlay cube (+ species ears), back to front order free."""
    species = cfg.get("species", shared.get("species", "human"))
    sp_head = SPECIES_HEADS.get(species) or []
    hw_name = cfg["headwear"]

    if sp_head:
        face = [list(r[HEAD_LEFT:HEAD_LEFT + HEAD_W]) for r in sp_head]
        # Hair-type headwear never applies to an animal head.
        hat = [] if hw_name in HAIR_HEADWEAR else HEADWEAR.get(hw_name, [])
        crown = "f"
    else:
        face = [list(r) for r in HEAD_DEFAULT]
        hat = HEADWEAR.get(hw_name, [])
        crown = "h" if face[0][0] == "h" else "s"

    # Side texture: one key per row, taken from the face's leading column, so
    # hair rows stay hair and a mask band wraps around the skull.
    side = [[_first_key(row) or crown] * HEAD_SIZE for row in face]
    top = [[crown] * HEAD_SIZE for _ in range(HEAD_SIZE)]

    boxes = [Box(HEAD_X, HEAD_Y, HEAD_Z, HEAD_SIZE, HEAD_SIZE, HEAD_SIZE,
                 {"front": face, "top": top, "side": side})]

    # The overlay cube is ALWAYS present — fully transparent when there is no
    # headwear — so the canvas size does not depend on which hat a role wears.
    # (A crew whose PNGs differ in size cannot be tiled or swapped in a UI.)
    n = HEAD_SIZE
    ov_front = [["."] * n for _ in range(n)]
    ov_top = [["."] * n for _ in range(n)]
    ov_side = [["."] * n for _ in range(n)]
    if hat:
        for r, row in enumerate(hat[:n]):
            for c, ch in enumerate(row[:n]):
                ov_front[r][c] = ch
        # Crown of the hat: the hat material covers the whole top of the
        # overlay cube, so from above it reads as a cap, not a plank.
        crown_key = _first_key(hat[0]) or "."
        ov_top = [[crown_key] * n for _ in range(n)]
        # Side of the hat: each hat row's material wraps round the skull.
        ov_side = [[(_first_key(hat[r]) if r < len(hat) else None) or "."] * n
                   for r in range(n)]
    o = OVERLAY_INFLATE
    boxes.append(Box(HEAD_X - o, HEAD_Y - o, HEAD_Z - o,
                     HEAD_SIZE + 2 * o, HEAD_SIZE + 2 * o, HEAD_SIZE + 2 * o,
                     {"front": ov_front, "top": ov_top, "side": ov_side}))

    for (ex, ey, ew, eh, ed) in SPECIES_EARS.get(species, []):
        boxes.append(Box(HEAD_X + ex, HEAD_Y + ey - eh, HEAD_Z + 2, ew, eh, ed,
                         {"front": "f", "top": "f", "side": "f"}))
    return boxes


def bust_boxes(cfg: dict, shared: dict) -> list:
    """Head plus a torso and two arms hanging beneath it.

    Mineatar's proportions, scaled 1.5x to match the 12-texel face: the
    torso's front face sits 2 texels behind the head's (a 4-deep torso under
    an 8-deep head, i.e. 6-deep under 12), NOT centred under the skull — a
    centred torso falls so far back that the head's underside hides it.
    """
    boxes = head_boxes(cfg, shared)
    ty = HEAD_Y + HEAD_SIZE
    tz = HEAD_Z + 2
    tx = HEAD_X + (HEAD_SIZE - TORSO_W3D) // 2
    torso = Box(tx, ty, tz, TORSO_W3D, TORSO_H3D, TORSO_D3D,
                {"front": torso_front_map(cfg["prop"]), "top": "c", "side": "T"})
    arm_w = 3
    arms = [
        Box(tx - arm_w, ty, tz, arm_w, TORSO_H3D, TORSO_D3D,
            {"front": "a", "top": "a", "side": "a"}),
        Box(tx + TORSO_W3D, ty, tz, arm_w, TORSO_H3D, TORSO_D3D,
            {"front": "a", "top": "a", "side": "a"}),
    ]
    return boxes + [torso] + arms


def render(role: str, cfg: dict, shared: dict, scale: int, view: str = "head"):
    """Render one avatar in true isometric projection, square, nearest-neighbour."""
    colours = colour_map(cfg, shared)
    boxes = bust_boxes(cfg, shared) if view == "bust" else head_boxes(cfg, shared)

    W, H, ox, oy = canvas_bounds(boxes, scale, margin=1.0)
    # Square, centred — an avatar is a square.
    size = max(W, H)
    ox -= (size - W) / (2 * scale)
    oy -= (size - H) / (2 * scale)
    W = H = size

    bg = ramp(shared["background"])[MID]
    canvas = [[bg] * W for _ in range(H)]

    ramp_cache: dict[str, list] = {}

    def resolve(key, face):
        pal = colours.get(key)
        if pal is None:
            return None
        name, idx = pal
        if name not in ramp_cache:
            ramp_cache[name] = ramp(name)
        return shade_for_face(ramp_cache[name], idx, face)

    for box in order_boxes(boxes):
        draw_box(canvas, box, scale, ox, oy, resolve)
    return canvas


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
                    help="pixels per texel (default 64)")
    ap.add_argument("--base", type=pathlib.Path,
                    help="portrait to derive skin/hair/top/background from. "
                         "Colours only — faces do not survive an 8-texel grid.")
    ap.add_argument("--skin"); ap.add_argument("--hair")
    ap.add_argument("--sleeve"); ap.add_argument("--background")
    ap.add_argument("--species", help="human (default) or: " + "/".join(
        k for k in SPECIES_HEADS if k != "human"))
    ap.add_argument("--fur"); ap.add_argument("--muzzle"); ap.add_argument("--mask")
    ap.add_argument("--list", action="store_true", help="show palette, headwear and props")
    ap.add_argument("--view", choices=("head", "bust"), default="head",
                    help="head (default): the isometric head with its overlay, "
                         "the unit every skin renderer serves first. "
                         "bust: head plus torso, arms and the role prop.")
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
        px = render(role, cfg, shared, a.scale, a.view)
        path = a.out / f"{role}.png"
        write_png(path, px)
        print(f"✅ {path}  {len(px[0])}x{len(px)}  hue={cfg['hue']} "
              f"headwear={cfg['headwear']} prop={cfg['prop']}")

    print(f"\n{len(roster)} avatars — identical geometry, palette and lighting by "
          f"construction, not by inspection.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
