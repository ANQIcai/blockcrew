"""3/4-view box renderer — the part that makes it read as the real game.

🔴 WHY A FLAT SPRITE NEVER LOOKED RIGHT

A vanilla character is six BOXES seen at an angle, and the game shades every
face by a fixed multiplier decided purely by which way it points:

    top     1.0        north / south   0.8
    bottom  0.5        east  / west    0.6

Those numbers are not artistic choices; they are constants in the renderer.
Blocks cast no shadows on each other at all — the sun's position never darkens
anything — so a face's brightness depends ONLY on its orientation.

⭐ That is the whole look. Three faces of one box, at 1.0 / 0.8 / 0.6, is what
the eye recognises. A flat front-facing sprite has exactly one orientation, so
it renders as one tone and reads as generic pixel art no matter how correct the
palette is.

MODEL (the real dimensions, w x h x d in texels):

    head   8 x 8 x 8    the only cube; all six faces identical
    body   8 x 12 x 4   the only part with three face sizes
    arms   4 x 12 x 4   square cross-section

PROJECTION: cabinet oblique at 1:2 depth. The front face stays an exact
rectangle, which keeps the eyes and mouth crisp -- an isometric view shears the
face and at 8 texels wide there is no detail left to shear. Depth steps half a
pixel per texel, giving a consistent 2:1 staircase on the diagonals.
"""

# Vanilla face multipliers.
FACE_TOP, FACE_FRONT, FACE_SIDE, FACE_BOTTOM = 1.0, 0.8, 0.6, 0.5


class Box:
    """A cuboid in texel space. y increases downward, z increases away."""

    __slots__ = ("x", "y", "z", "w", "h", "d", "faces")

    def __init__(self, x, y, z, w, h, d, faces):
        self.x, self.y, self.z = x, y, z
        self.w, self.h, self.d = w, h, d
        # faces: dict with "front" / "top" / "side" -> 2D texel maps or a key
        self.faces = faces


def project(x, y, z):
    """Cabinet oblique: half a pixel right and up per unit of depth."""
    return x + z // 2, y - z // 2


def draw_box(buf, box, depth, W, H, oy):
    """Paint one box's three visible faces into buf with a depth test."""
    x0, y0, z0, w, h, d = box.x, box.y, box.z, box.w, box.h, box.d

    def put(sx, sy, key, mult, dist):
        sy += oy
        if not (0 <= sx < W and 0 <= sy < H):
            return
        if dist <= depth[sy][sx]:
            depth[sy][sx] = dist
            buf[sy][sx] = (key, mult)

    # 🔴 Depth is a real distance to the camera, not a per-face constant.
    # The camera sits at -z, above and to the right, so a texel is nearer when
    # z is smaller, y is larger (lower down) and x is larger.
    def dist(px, py, pz):
        return pz * 2 - py - px * 0.01

    # TOP face: y = y0, spans w x d.
    top = box.faces.get("top")
    if top:
        for pz in range(d - 1, -1, -1):
            for px in range(w):
                sx, sy = project(x0 + px, y0, z0 + pz)
                put(sx, sy, _cell(top, px, pz), FACE_TOP,
                    dist(x0 + px, y0, z0 + pz))

    # SIDE face: the +x face, spans d x h.
    side = box.faces.get("side")
    if side:
        for pz in range(d - 1, -1, -1):
            for py in range(h):
                sx, sy = project(x0 + w - 1, y0 + py, z0 + pz)
                put(sx, sy, _cell(side, pz, py), FACE_SIDE,
                    dist(x0 + w - 1, y0 + py, z0 + pz))

    # FRONT face: z = z0, spans w x h. Nearest plane of the box.
    front = box.faces.get("front")
    if front:
        for py in range(h):
            for px in range(w):
                sx, sy = project(x0 + px, y0 + py, z0)
                put(sx, sy, _cell(front, px, py), FACE_FRONT,
                    dist(x0 + px, y0 + py, z0))


def _cell(face, a, b):
    """A face is either a single key or a 2D list of keys."""
    if isinstance(face, str):
        return face
    try:
        row = face[b]
        return row[a] if a < len(row) else face[0][0]
    except (IndexError, TypeError):
        return face[0][0] if face else None
