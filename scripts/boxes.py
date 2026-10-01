"""True isometric box renderer — the projection the modder renderers use.

🔴 WHY THE PREVIOUS VERSIONS NEVER READ AS THE GAME

Four iterations used cabinet oblique: the front face stayed an exact rectangle
and depth stepped half a pixel per texel. That is generic pixel art. Every
renderer people recognise (Crafatar, Mineatar, NMSR) uses the SAME three fixed
2x2 matrices, ported here verbatim from mineatar-io/skin-render `matrix.go`:

    side  = rotate(+30°) · skewX(+30°) · scaleY(0.86603)
    front = rotate(-30°) · skewX(-30°) · scaleY(0.86603)
    top   = rotate(+30°) · skewX(-30°) · scaleY(0.86603)     (plantMatrix)

0.86603 = cos 30°. The front face comes out SHEARED — vertical edges stay
vertical, horizontal edges rise to the right at 1:2. ⭐ That shear is the
signature, not a cost.

The three matrices are the one linear 3D→2D isometric map restricted to each
face, so a point (x, y, z) in model space (x right, y DOWN, z away) lands at

    X = front[0]·x + front[1]·y − top[0]·z
    Y = front[2]·x + front[3]·y − top[2]·z

and the camera looks along (+1, +1, +1): from above, from the front, and from
the character's RIGHT (viewer's left). The visible side face is therefore the
x = x0 face, drawn on the LEFT of the front face — exactly Mineatar's layout.

SHADING: no per-face brightness multipliers. The skin renderers apply none —
they trust the texture. Here the texture is a hue-shifted ramp per material,
and the face picks the ramp step: top = HIGHLIGHT, front = MID, side = SHADOW.
A texel that already carries its own step (an eye, a mouth, a material
cluster) keeps it on every face.

SAMPLING: nearest-neighbour. Every output pixel takes exactly one texel
colour: no blending, no anti-aliasing. Faces are scaled first and transformed
second (as `compositeTransform` does), so the sloped edges step at ONE OUTPUT
PIXEL, not one texel — which is why the edges read as crisp isometric lines
rather than a staircase of blocks.

OCCLUSION: painter's order, back to front, no z-buffer — the same as
`body.go`. Boxes are sorted by the separating-axis rule (a box entirely on
the smaller side of any axis is nearer), with centre depth as the tie-break
for interpenetrating boxes.
"""

import math

# ----------------------------------------------------------------- matrix --
# Transcribed from matrix.go. A matrix is [a, b, c, d] meaning
#     X = a·x + b·y
#     Y = c·x + d·y

COS30 = 0.86603          # the literal constant used in matrix.go, not cos(30°)


def rotate(a):
    return [math.cos(a), -math.sin(a), math.sin(a), math.cos(a)]


def skew_x(a):
    return [1.0, math.tan(a), 0.0, 1.0]


def scale_y(a):
    return [1.0, 0.0, 0.0, a]


def multiply(A, B):
    return [A[0] * B[0] + A[1] * B[2], A[0] * B[1] + A[1] * B[3],
            A[2] * B[0] + A[3] * B[2], A[2] * B[1] + A[3] * B[3]]


def inverse(m):
    d = m[0] * m[3] - m[1] * m[2]
    return [m[3] / d, -m[1] / d, -m[2] / d, m[0] / d]


def apply(m, x, y):
    return m[0] * x + m[1] * y, m[2] * x + m[3] * y


_R = math.radians
SIDE_MATRIX = multiply(multiply(rotate(_R(30)), skew_x(_R(30))), scale_y(COS30))
FRONT_MATRIX = multiply(multiply(rotate(_R(-30)), skew_x(_R(-30))), scale_y(COS30))
TOP_MATRIX = multiply(multiply(rotate(_R(30)), skew_x(_R(-30))), scale_y(COS30))

# Which ramp step a face takes for a MID texel. Set by render.py's constants;
# the values here only have to agree with SHADOW, MID, HIGHLIGHT = 0, 1, 2.
FACE_RAMP = {"top": 2, "front": 1, "side": 0}


class Box:
    """A cuboid in texel space. y increases downward, z increases away.

    faces: dict with "front" / "top" / "side" → either a single key (str) or
    a 2D list of keys. In a 2D list, None (or ".") is a transparent texel.
    A face that is absent, or None, is not drawn. The texel grid of a face
    may have a different count from its geometric size — that is how the
    overlay box stretches a 12x12 texture over 13x13 texels.
    """

    __slots__ = ("x", "y", "z", "w", "h", "d", "faces")

    def __init__(self, x, y, z, w, h, d, faces):
        self.x, self.y, self.z = x, y, z
        self.w, self.h, self.d = w, h, d
        self.faces = faces

    def corners(self):
        for dx in (0, self.w):
            for dy in (0, self.h):
                for dz in (0, self.d):
                    yield self.x + dx, self.y + dy, self.z + dz


def project(x, y, z):
    """Model texel → screen texel units, under the three matrices above."""
    return (FRONT_MATRIX[0] * x + FRONT_MATRIX[1] * y - TOP_MATRIX[0] * z,
            FRONT_MATRIX[2] * x + FRONT_MATRIX[3] * y - TOP_MATRIX[2] * z)


# ---------------------------------------------------------------- ordering --
def _nearer(a, b):
    """True if a is in front of b, False if behind, None if undetermined."""
    for amin, alen, bmin, blen in ((a.x, a.w, b.x, b.w),
                                   (a.y, a.h, b.y, b.h),
                                   (a.z, a.d, b.z, b.d)):
        if amin + alen <= bmin + 1e-9:
            return True
        if bmin + blen <= amin + 1e-9:
            return False
    # Interpenetrating: fall back to centre depth along the view ray.
    da = a.x + a.w / 2 + a.y + a.h / 2 + a.z + a.d / 2
    db = b.x + b.w / 2 + b.y + b.h / 2 + b.z + b.d / 2
    if abs(da - db) < 1e-9:
        return None
    return da < db


def order_boxes(boxes):
    """Back-to-front: repeatedly take a box that is not in front of any other."""
    remaining = list(boxes)
    out = []
    while remaining:
        pick = remaining[-1]
        for b in remaining:
            if not any(_nearer(b, o) for o in remaining if o is not b):
                pick = b
                break
        remaining.remove(pick)
        out.append(pick)
    return out


# ------------------------------------------------------------------ canvas --
def canvas_bounds(boxes, scale, margin=1.0):
    """(W, H, ox, oy): pixel size and the screen-texel coordinate of pixel 0,0."""
    xs, ys = [], []
    for box in boxes:
        for cx, cy, cz in box.corners():
            px, py = project(cx, cy, cz)
            xs.append(px)
            ys.append(py)
    ox, oy = min(xs) - margin, min(ys) - margin
    W = int(math.ceil((max(xs) + margin - ox) * scale))
    H = int(math.ceil((max(ys) + margin - oy) * scale))
    return W, H, ox, oy


# ---------------------------------------------------------------- drawing --
def _grid(face):
    """Normalise a face spec to (cells, nu, nv) with None for transparent."""
    if isinstance(face, str):
        return [[face]], 1, 1
    rows = [[(None if c in (None, ".") else c) for c in row] for row in face]
    nv = len(rows)
    nu = max(len(r) for r in rows) if rows else 0
    rows = [r + [None] * (nu - len(r)) for r in rows]
    return rows, nu, nv


def _next_change(k, A, B, i):
    """First pixel index > i at which floor(A·i + B) leaves cell k."""
    if A == 0:
        return 1 << 30
    if A > 0:
        n = int(math.ceil((k + 1 - B) / A))
    else:
        n = int(math.floor((k - B) / A)) + 1
    n = max(n, i + 1)
    # Guard float drift at the boundary.
    while n > i + 1 and int(math.floor(A * (n - 1) + B)) != k:
        n -= 1
    while int(math.floor(A * n + B)) == k:
        n += 1
    return n


def _draw_face(canvas, W, H, scale, ox, oy, origin, M, span_u, span_v, cells, nu, nv, resolve):
    """Rasterise one parallelogram face with nearest-neighbour texel lookup.

    Each pixel centre is inverse-mapped through M to face-local (u, v); the
    texel is floor(u·nu/span_u), floor(v·nv/span_v). Rows are filled as runs
    between texel-boundary crossings, so cost is proportional to texels, not
    pixels.
    """
    Minv = inverse(M)
    Ox, Oy = origin
    # Pixel rows covered by the face.
    ys = [apply(M, u, v)[1] + Oy for u in (0, span_u) for v in (0, span_v)]
    j0 = max(0, int(math.floor((min(ys) - oy) * scale)))
    j1 = min(H, int(math.ceil((max(ys) - oy) * scale)) + 1)
    eps = 1e-7

    # u(i) = au·i + bu(row);  v(i) = av·i + bv(row)   with i the pixel column
    au = Minv[0] / scale
    av = Minv[2] / scale
    # Cell index functions: cu = floor(Au·i + Bu), cv = floor(Av·i + Bv)
    Au = au * nu / span_u
    Av = av * nv / span_v

    colour_cache = {}

    def colour(cu, cv):
        key = cells[cv][cu]
        if key is None:
            return None
        if key not in colour_cache:
            colour_cache[key] = resolve(key)
        return colour_cache[key]

    for j in range(j0, j1):
        sy = oy + (j + 0.5) / scale - Oy
        sx0 = ox + 0.5 / scale - Ox            # screen x of pixel column 0 centre
        bu = Minv[0] * sx0 + Minv[1] * sy
        bv = Minv[2] * sx0 + Minv[3] * sy
        lo, hi = 0, W
        for a, b, span in ((au, bu, span_u), (av, bv, span_v)):
            if a > 0:
                lo = max(lo, int(math.ceil((-eps - b) / a)))
                hi = min(hi, int(math.ceil((span + eps - b) / a)))
            elif a < 0:
                lo = max(lo, int(math.floor((span + eps - b) / a)) + 1)
                hi = min(hi, int(math.floor((-eps - b) / a)) + 1)
            else:
                if not (-eps <= b < span + eps):
                    lo, hi = 0, 0
        if lo >= hi:
            continue
        Bu = bu * nu / span_u
        Bv = bv * nv / span_v
        row = canvas[j]
        i = lo
        while i < hi:
            cu = int(math.floor(Au * i + Bu))
            cv = int(math.floor(Av * i + Bv))
            nxt = min(_next_change(cu, Au, Bu, i), _next_change(cv, Av, Bv, i), hi)
            cu = min(max(cu, 0), nu - 1)
            cv = min(max(cv, 0), nv - 1)
            rgb = colour(cu, cv)
            if rgb is not None:
                row[i:nxt] = [rgb] * (nxt - i)
            i = nxt


def draw_box(canvas, box, scale, ox, oy, resolve):
    """Paint one box's three visible faces (top, side, front) into canvas.

    resolve(key, face) → rgb tuple or None, where face ∈ {"top","side","front"}.
    canvas is a list of H rows of W rgb tuples; ox, oy from canvas_bounds().
    """
    H, W = len(canvas), len(canvas[0])
    x0, y0, z0, w, h, d = box.x, box.y, box.z, box.w, box.h, box.d

    # FRONT face: z = z0. Local u → +x, v → +y. Origin: near-top-left corner.
    front = box.faces.get("front")
    if front is not None:
        cells, nu, nv = _grid(front)
        _draw_face(canvas, W, H, scale, ox, oy, project(x0, y0, z0), FRONT_MATRIX,
                   w, h, cells, nu, nv, lambda k: resolve(k, "front"))

    # SIDE face: x = x0 (the character's right). Local u runs far → near
    # (−z), v → +y. Origin: far-top corner. Side maps are indexed [y][z-from-far].
    side = box.faces.get("side")
    if side is not None:
        cells, nu, nv = _grid(side)
        _draw_face(canvas, W, H, scale, ox, oy, project(x0, y0, z0 + d), SIDE_MATRIX,
                   d, h, cells, nu, nv, lambda k: resolve(k, "side"))

    # TOP face: y = y0. The plant matrix takes u → −z (far→near) and v → −x
    # (right→left); its origin is the far-right corner. Top maps are indexed
    # [z-from-front][x-from-left], so both axes are flipped on lookup.
    top = box.faces.get("top")
    if top is not None:
        cells, nu, nv = _grid(top)
        flipped = [[cells[nv - 1 - r][nu - 1 - c] for c in range(nu)] for r in range(nv)]
        # After the flip, local u indexes rows (depth) and v indexes columns (x):
        # transpose so the rasteriser's cells[cv][cu] reads cells[x][z].
        transposed = [[flipped[r][c] for r in range(nv)] for c in range(nu)]
        _draw_face(canvas, W, H, scale, ox, oy, project(x0 + w, y0, z0 + d), TOP_MATRIX,
                   d, w, transposed, nv, nu, lambda k: resolve(k, "top"))
