---
name: blockcrew
description: Generate a matching set of blocky, low-resolution pixel-art voxel character avatars for a fleet of AI agents — one upper-body bust per role, built so the whole crew reads as siblings while every member stays instantly distinguishable at sidebar size. Use when creating avatars, profile pictures, or identity art for multiple agents, bots, team members, or services that appear together in a list.
---

# Blockcrew

Give a fleet of agents faces. Not one mascot — a **crew**: a set of blocky
voxel *people* who obviously work at the same place and are never mistaken
for each other.

## The problem this solves

A single mascot only has to be memorable. A crew has a harder job: the avatars
appear **side by side in a sidebar, a config file, a dashboard row**, usually
at 32–64px. They must answer two questions at once:

1. *Are these the same team?* — solved by shared geometry and a shared neutral
2. *Which one is the trading agent?* — solved by silhouette first, colour second

🔴 **Optimising only for the second question produces six characters that
look unrelated. Optimising only for the first produces six that look
identical.** Every rule below exists to hold both.

## Starting from a photo or character

A user can supply a picture — themselves, a character, a mascot — and the crew
is built as **variations of that base**.

```sh
python3 scripts/render.py --base me.jpg --roster my-crew.json --out avatars/
```

The renderer samples four regions and snaps each to its nearest palette slot,
then prints what it chose:

```
🎨 Base image: me.jpg
   hair        sampled #221911 → black (#1D1D21)
   skin        sampled #C6885B → brown (#835432)
   sleeve      sampled #A13A2D → brown (#835432)
   background  sampled #2C3D70 → gray (#474F52)
```

Any slot can be overridden: `--skin`, `--hair`, `--sleeve`, `--background`.

### 🔴 Be honest about what transfers

| Transfers | Does not transfer |
|---|---|
| Skin tone | Facial features |
| Hair colour | Expression, face shape |
| Clothing colour | Hairstyle detail, glasses, age |
| Background | Any likeness at all |

**At 8 texels across a head face an eye is one texel.** There is no likeness
available at this resolution, and promising one would be dishonest.

⭐ **The useful framing is "same person rendered as a crew", not "portrait".**
Deriving the *shared* slots from one photo makes every agent read as a
variation of one character — which is what the shared-slot architecture
already does. The photo just supplies the values instead of the user choosing
them.

⚠️ **Regions are fixed fractions of the frame**, assuming a roughly centred
head-and-shoulders subject. No face detection: it would add a heavy dependency
to guess something the user can override in one flag. A full-body shot or an
off-centre crop samples the wrong areas — say so and offer the overrides
rather than silently producing wrong colours.

---

## 🔴 Two production methods — prefer the renderer

**Method A — `scripts/render.py` (default).** Constructs the PNGs directly on
the texel grid. No image model, no API key, no network.

```sh
python3 scripts/render.py --roster my-crew.json --out avatars/
python3 scripts/render.py --list          # palette, headwear, props
```

**Method B — an image model**, using the same spec as a prompt. Only when a
role needs a prop the sprite library does not have.

### Why the renderer is the default

Every quantity in this spec is a number: head 8×8×8, torso 8×12×4, arms
4×12×4, eight texels per head face, sixteen hex values, base-plus-shade
lighting, a fixed crop, a fixed camera angle.

⭐ **That is a rendering problem, not a generation problem.** Asking a
probabilistic model to land on exact integers is the wrong tool, and it fails
the way probabilistic tools fail — plausibly, and differently each run.

Everything Method B needs — an invariant block pasted verbatim, a six-point
consistency check, *"no anti-aliasing"*, *"do not accept a smooth render"* —
exists **only to fight drift that the renderer cannot produce**. Consistency
stops being something to verify and becomes something guaranteed.

📌 It also removes the API key. A public skill that runs free and offline is
usable by everyone; one that needs a paid image model is not.

### The sprite library is the extension point

⚠️ **The renderer can only draw props it has sprites for.** A legal agent
needs a gavel; a support agent needs a headset. Adding one is a small block of
text in `scripts/render.py`:

```python
"gavel": [("......PPPP......", 13), ("......PppP......", 14)],
```

⭐ **This is better than the prompt it replaces.** A prompt cannot be extended
by anyone but its author; a sprite table takes pull requests. Ask the user
whether to add a sprite or fall back to Method B when a role has no match —
never silently substitute a prop that means something else.

---

## Workflow

1. **Read THIS user's roster before asking for it.** 🔴 The crew is whatever
   agents *they* run — never a default set. If the workspace is an agent
   project, look for agent definitions, profile directories, config files, or
   a README that names the agents and their jobs. Infer the roster from
   evidence when the roles and their purposes are clear.
2. **Ask once, if you must.** One consolidated question: which agents exist,
   what each is for, and whether any house palette must be honoured. Do not
   run a second round of discovery.
3. **Propose the crew map before generating anything.** One row per agent:

   ```
   <agent> — <role in three words> — <headwear> — <top> — <prop> — <accent> — <hue>
   ```

   Above the table, state the **filled-in invariant block** — camera angle,
   crop height, texel size, light direction, skin, sleeves, background. These
   are decisions, and making them once in the open is what stops six
   generations from each deciding differently.
   Wait for approval unless the request already authorises generation.
4. **Render one avatar per agent.** Write the approved crew map to a roster
   JSON and run `scripts/render.py`. One square PNG per agent — never a grid
   or contact sheet; individual files are what the user actually needs.
   ⚠️ Only fall back to an image model when a role needs a prop the sprite
   library lacks, and say so rather than substituting a different object.
5. **Parallelise with subagents when the runtime supports them.** Each subagent
   receives the **invariant block verbatim** plus one agent's row. 🔴 Never
   summarised, never shortened for later members — a paraphrased spec is how
   crews lose coherence, and the drift only becomes visible once every image
   is lined up together.
6. **Run the consistency check and the silhouette test** (both below) before
   delivering. Report both results honestly, including failures.
7. **Deliver every generated result.** Report each agent name, prop, hue, file
   path, and dimensions. Do not silently discard, retry, or post-process a
   candidate. If one is weak, say so and offer a redraw.

## Shape language — the figure is a PERSON

🔴 **Every avatar is a blocky humanoid character, not an object, animal, or
abstract mascot.** A viewer should read it as *a little person who does this
job*, in the same instant they read the role.

- **Hard 90° edges only.** Flat faces, square corners, no bevels, no rounded
  contours, no curves anywhere — not on the head, not on a limb, not on a
  prop. A single curve breaks the voxel read.
- 🔴 **Upper body only.** Head, torso and arms. **No legs, no hips, no feet.**
  The figure is cropped at roughly chest-to-waist height — a bust, like a
  profile picture, not a full character standing on the ground.
- **Anatomy, all rectangular prisms:** one cube head, one rectangular torso,
  two arms. Blunt square ends. No hands or feet as separate shapes — the arm
  simply ends.
- **Proportions are specified exactly** in the texel spec below: head 8×8×8,
  torso 8 wide × 12 tall × 4 deep, arms 4×12×4. 🔴 **The head is exactly as
  wide as the torso** — a model left to itself always makes it narrower, and
  that single error is what makes an output look generic rather than voxel.
  In a bust the head is ~55% of visible height and should look slightly too big.
- **The crop is the same for every member:** the bottom edge cuts the torso at
  the same height across the crew. ⚠️ One member cropped at the shoulders and
  another at the waist reads as two different sets.
- **The head reads as a face, not a box.** Two square eyes on the front face,
  optionally one small rectangular mouth. A separate flat colour block across
  the top of the head for hair. No eyebrows, pupils, nostrils, blush,
  highlights, or outlines.
- 🔴 **Camera angle is FIXED, not chosen: straight-on front view, or turned
  very slightly to the viewer's right (about 10–15°).** Eyes meet the viewer
  either way. Shoulders stay square to camera even when the head turns.
- **Upright, neutral, symmetrical.** No action poses, no leaning, no profile
  views, no three-quarter turns beyond 15°, no looking away or down.
- ⚠️ **Pick ONE of those two angles for the whole crew and state it in the
  crew map before generating.** Not "front-facing or 3/4" as a per-avatar
  decision — one angle, written down, applied to every member.
- **Visible chunk size stays constant across the crew.** If one avatar is built
  from visibly finer blocks than another, they stop looking like the same
  species.
- **One view angle for the entire crew**, fixed above. Never mix within a set:
  a single member at a different angle is the most visible inconsistency
  possible, more noticeable than a wrong colour.
- Bust fills **80–90% of the canvas width**, centred horizontally, head near
  the top with a small even margin. The torso runs off the bottom edge — do
  not float the bust in the middle with empty space beneath it.

⭐ **A person carries a role better than a symbol does.** An icon of a
briefcase says "career"; a small blocky person *holding* a briefcase says
"this is the agent who handles my career". The second is what an avatar is
for — it stands in for someone.

## Colour — a fuller palette, held together by what is shared

Each avatar carries **five to six materials**. A three-colour figure was too
sparse to read as a person: skin, hair, sleeves and a collar are four
different things before the job is even named.

🔴 **The crew coheres through the SHARED slots, not through scarcity.** Three
of the slots below are identical for every member — that is the family
resemblance. The rest are free to vary, and should.

| Slot | Shared or per-agent | Notes |
|---|---|---|
| Skin | **shared** | One tone for the whole crew, or match the user's own if they ask |
| Background | **shared** | One flat colour, or transparent — same choice for every member |
| Sleeves / base layer | **shared** | The arms' garment. The quiet neutral that ties the set together, and the only large shared area left once the legs are gone |
| Hair | per-agent | Can differ freely; it is also a separator |
| Chest / uniform front | per-agent | The largest per-agent area. Carries the role hue |
| Prop | per-agent | Role hue, or its own accent |
| Accent | per-agent, optional | One upper-body extra: collar, lanyard, badge, hatband, strap, earpiece |

**Each material gets a three-shade hue-shifted ramp** derived from its palette
midtone: shadow (darker, toward blue, more saturated), midtone, highlight
(brighter, toward yellow, less saturated). Three flat values, no blending —
computed by one rule, so every material in the crew is lit identically.

### Keeping it from turning into confetti

- **One dominant role hue per agent**, high chroma, unique in the crew. Every
  other per-agent colour stays **lower in chroma** than it. A figure with four
  equally loud colours has no role hue at all.
- 🔴 **All values come from the locked 16-colour palette below.** Do not invent
  intermediate tones, and do not tint a palette value to make it fit.
- 🔴 **Never assign Red and Green as the role hues of two crew members.**
- Light source is **constant across the crew** — same direction, same strength.
  Shading steps that disagree between members break the set faster than colour
  choices do.
- No smooth gradients, no soft shadows, no ambient occlusion, no glow. All
  shading is quantised to the texel grid.

⭐ **Richness and coherence are not opposites — they are different slots.** The
earlier three-colour rule bought coherence by making every figure poor. Fixing
the shared slots buys the same coherence while letting each member be a fully
dressed character.

## Naming the role: outfit, headwear, one prop

A person carries a job three ways. Use **all three**, and keep each one simple.

**1. Outfit — a flat colour block on the torso.** Not a rendered garment: one
or two rectangular colour regions reading as a uniform. A collar line, a
lapel, an apron, a hi-vis band. Nothing smaller than a visible chunk.

**2. Headwear or hair — the fastest role signal at small size.** A hard hat, a
cap, a headset, a visor, a particular hair block colour. 📌 This is what stays
legible when the figure is 32px tall and the prop has become a smudge.

**3. Exactly ONE held prop.** Not two.

- Blocky, chunky and **oversized** — roughly a third of the figure's height.
  A realistic-scale prop vanishes at avatar size.
- 🔴 **Held at chest height or raised, in one or both hands.** With the lower
  body cropped away, anything held low falls outside the frame — the prop must
  sit between the chin and the crop line to be visible at all.
- Readable **as a pure black silhouette**. If identifying it needs colour, it
  is the wrong prop.

Worked examples, tested for silhouette separation:

| Role | Headwear / hair | Top | Prop | Accent | Role hue |
|---|---|---|---|---|---|
| Career / job search | neat side-part | collared shirt + tie | briefcase held at chest | pocket square | indigo |
| Trading / investment | headset | open collar | candlestick bar | lanyard | teal |
| Admin / butler | slicked flat hair | waistcoat + lapels | serving tray held up | bow tie | warm grey |
| Building / engineering | **hard hat** | hi-vis chest band | wrench raised | chin strap | amber |
| Content / filming | **backwards cap** | plain tee | boxy camera raised | camera strap | magenta |
| Marketing | **beret** | bold-panel top | megaphone | scarf | cyan |
| Research | round flat-top hair | lab-coat lapels | square-lens magnifier | breast-pocket block | violet |
| Ops / infrastructure | **beanie** | zip-up panel | wrench-and-bolt block | collar zip | slate blue |

🔴 **Where two roles share a prop shape, the headwear must differ sharply.**
Engineer and ops both hold tools; the hard hat versus the beanie is what
separates them at 32px, not the tool.

⚠️ **This table is a worked example, not the product.** These eight roles are
common ones, shown to demonstrate the spacing of silhouettes and hues. Most
fleets will contain roles that are not here — a support agent, a legal agent,
a scheduling agent, a game-master, a household bot. **Derive their kit; do not
force them into a row above.**

## Deriving a kit for a role not in the table

For each role the user actually has, answer three questions in order:

1. **What does this role physically carry or touch?** Take the most
   object-like answer and make it blocky and oversized. A legal agent holds a
   gavel or a stamped document; a support agent holds a headset or a ticket
   card; a scheduling agent holds a calendar block.
2. **What would this person wear on their head?** Pick the most
   role-specific option available: a uniform cap, a visor, a headset, a
   particular hair shape. 🔴 **Check it against every headwear already
   assigned in this crew** — this is the separator that survives to 32px.
3. **What does the top look like?** A collar, an apron, a sash, a panel — one
   or two rectangles carrying the role hue, nothing finer than a visible chunk.
4. **One optional accent, above the crop line.** Collar, lanyard, badge,
   hatband, strap, earpiece. Lower saturation than the role hue. Skip it if
   nothing fits; do not invent decoration to fill the slot. ⚠️ Shoes, belts and
   trouser details are invisible in a bust — do not assign them.

**If a role is purely abstract** — "memory", "router", "orchestrator" — give
the figure an abstract prop rather than a vague gesture: a stacked block
tower, a floating cube, a key, a clipboard of stacked bars. ⚠️ Never leave the
hands empty and never fall back to a generic office worker; an unidentifiable
member defeats the point of a crew.

**If two roles genuinely overlap** — "backend" and "infra", "research" and
"analysis" — separate them on **headwear first, prop second, hue last**. If
they still collide, ask the user which distinction matters to them rather
than guessing.

## The locked 16-colour palette

🔴 **Every colour in every avatar comes from this table. No other values.**

These are the classic voxel-game dye values — a fixed, functional 16-colour
set. Using a locked palette is not decoration: it is the constraint that makes
a crew cohere without being told to.

| Name | Base | Shade (darker step) |
|---|---|---|
| White | `#F9FFFE` | `#E6E6E6` |
| Light Gray | `#9D9D97` | `#757571` |
| Gray | `#474F52` | `#353B3D` |
| Black | `#1D1D21` | `#151518` |
| Brown | `#835432` | `#623F25` |
| Red | `#B02E26` | `#84221C` |
| Orange | `#F9801D` | `#BA6015` |
| Yellow | `#FED83D` | `#BEA22D` |
| Lime | `#80C71F` | `#609517` |
| Green | `#5E7C16` | `#465D10` |
| Cyan | `#169C9C` | `#107575` |
| Light Blue | `#3AB3DA` | `#2B86A3` |
| Blue | `#3C44AA` | `#2D337F` |
| Purple | `#8932B8` | `#66258A` |
| Magenta | `#C74EBD` | `#953A8D` |
| Pink | `#F38BAA` | `#B6687F` |

⚠️ **The second column is a starting point, not the shading system.** It is a
*straight* darker variant, and the style guide rejects straight ramps as dull.
🔴 **Use the hue-shifted ramp instead** — see "Matching the voxel-game art
style" below. The palette supplies the midtone; shadow and highlight are
derived from it by a fixed HSV rule, applied identically to every material.

### Why a locked palette helps

**"Pick hues far apart on the wheel" is vague; "pick two of sixteen named
slots" is not.** A closed palette turns colour choice into a discrete decision
that can be checked, and it removes the most common source of crew drift —
six generations each inventing a slightly different teal.

📌 **It also buys the look for free.** These sixteen values *are* the palette
the aesthetic is recognised by. Matching them does more for the style than any
adjective.

### Assignment

| Slot | Palette choice |
|---|---|
| Skin (shared) | one value, held for the whole crew |
| Sleeves / base layer (shared) | a **low-chroma** slot: White, Light Gray, Gray, Brown, Black |
| Background (shared) | Light Gray, Gray, or a low-chroma value that no role hue uses |
| Role hue (per agent) | one **high-chroma** slot: Orange, Yellow, Lime, Cyan, Light Blue, Blue, Purple, Magenta, Pink, Red, Green |
| Accent (per agent) | any remaining value, lower chroma than that agent's role hue |

⚠️ **Reserve the greys and browns for the shared slots.** If a role hue comes
from the low-chroma group it cannot carry identity at 32px.

🔴 **Red and Green are both in the palette — never assign them as the role hues
of two members of the same crew.** Roughly 1 in 12 men cannot separate them,
and a sidebar is exactly where that fails. Pick one, or neither.

📌 With eleven usable high-chroma slots, a crew larger than eleven agents must
reuse hues. When that happens, **separate the duplicates on headwear and prop
silhouette** and say so in the crew map — do not invent an off-palette colour
to avoid the collision.

## Resolution and surface — the exact texel spec

🔴 **Blocky geometry alone is not enough.** A cube-headed figure with smooth
flat surfaces is a modern low-poly toy, not a low-resolution character. The
pixelated read comes from the **surface**, not only the shape.

### The proportional system

Vague instructions ("blocky", "pixelated") produce vague output. Use the
classic voxel-character proportions instead — a functional geometry spec, in
texels:

| Part | Width | Height | Depth |
|---|---|---|---|
| Head | 8 | 8 | 8 |
| Torso | 8 | 12 | 4 |
| Arm (each) | 4 | 12 | 4 |

⭐ **Three consequences make this style recognisable, and all three are
counter-intuitive:**

1. **The head is exactly as wide as the torso.** Not narrower. This is the
   single most identifying proportion, and a model left to itself will always
   make the head narrower.
2. **The torso is deep-thin** — 8 wide but only 4 deep, a slab rather than a
   box.
3. **Arms are half the torso width** — 4 to the torso's 8.

For a bust cropped mid-torso, the visible figure is 8 texels of head above
roughly 6 of torso, so the head is **~55% of the visible height**. It should
look slightly too big. That is correct.

### The texel grid

**Every face of the head is exactly 8 × 8 texels.** Not "roughly 8–16" — eight.
Every other surface uses the same texel size, so a 4-wide arm face is 4 texels
across. **One texel size for the whole figure and the whole crew.**

This is the number that does the work: at 8 texels across a face, an eye is one
or two texels, and detail below that is impossible. **The grid enforces the
simplicity that a written rule only requests.**

### Surface shading

- **Two to three quantised shades per material**, snapped to the texel grid.
  Never blended.
- Faces pointing away from the light are a **flat step darker across the whole
  face** — not gradient-shaded within it.
- ⚠️ **Not noise, not texture detail.** A handful of flat values on the grid.
  No grain, no speckle, no per-pixel randomness, no photographic texture.

### Edges

**Hard nearest-neighbour, never anti-aliased.** Every colour boundary is a
stepped square edge. No feathering, no smoothed diagonals. A diagonal is a
visible staircase.

⭐ **Low resolution is a constraint being displayed, not a defect being
hidden.** The staircase edge is the aesthetic; smoothing it gives a cleaner
image that has lost the point.

### Say it explicitly in every prompt

Image models default to polished output. The words that matter:

> *8×8 texels per head face, visible square texel grid, flat per-face shading,
> hard nearest-neighbour edges, no anti-aliasing, no gradients, no gloss, no
> outlines, no ambient occlusion*

⚠️ **Render large with a coarse grid.** The file is 1024×1024 or more; the
*apparent* resolution stays at 8 texels per head face. Do not generate small
and upscale — that softens edges and destroys the only quality this section
exists to produce.

## Species — a crew of animals, not only people

`--species raccoon|cat|fox|bear` swaps the head map and leaves every other
rule untouched: same geometry, same hue-shifted ramps, same one-prop rule,
same shared neutral.

**Shared slots become fur slots.** `--fur`, `--muzzle`, `--mask` replace skin
and hair; the neck and any exposed body use fur, not human skin.

🔴 **Hair-type headwear is suppressed on an animal head.** `flat_hair`,
`side_part`, `headset` and `visor` paint a helmet over the ears and destroy
the silhouette. Real hats (`hard_hat`, `beret`, `cap_back`, `beanie`) still
apply.

🔴 **Ears must touch the skull.** Ears written outside columns 6–13 with a gap
render as floating debris beside the head — measured, not theorised.

### Two contrast pairs decide whether a species crew reads

| fur / background | fur–bg | mask–fur | mask–bg | result |
|---|---|---|---|---|
| light grey on grey | 79 | 127 | 48 | washed out |
| light grey on black | 127 | 127 | 0 | mask lost |
| brown on light grey | 65 | 62 | **127** | reads |

⭐ **The working combination has the lowest fur-vs-background contrast.** A
gate that checks fur-vs-background passes every failing case. The
discriminating pairs are **mask vs background** (the mask spans the full head
width, so it touches the silhouette edge) and **mask vs fur as a band** — too
close and the marking vanishes, too far and the mask becomes the whole head.

⚠️ **A contrast rule invented from intuition will pass its own failures.**
Calibrate it against renders you have looked at, then verify it fires on the
known-bad and stays silent on the known-good.

---

## Matching the voxel-game art style — the real rules

Researched 30 Sep 2026 against the **Blockbench Minecraft Style Guide**, the
document modders use to make new content look native. Three of our earlier
rules were wrong.

### 🔴 1. A straight ramp is the wrong ramp

A *straight ramp* varies only brightness. The style guide is blunt: straight
ramps *"often aren't used due to their dull look"*.

**Vanilla ramps are hue-shifted.** Shadows shift toward blue and gain
saturation; highlights shift toward yellow and lose it.

| | shades |
|---|---|
| straight (wrong) | `#107575` → `#169C9C` |
| hue-shifted (right) | `#09616D` → `#169C9C` → `#29B8A7` |

⭐ **This is why a technically-correct palette still looks flat.** The palette
supplies the *midtone*; the ramp is derived from it by rule — a fixed HSV
offset applied to every material, which is also what keeps a crew lit
identically.

### 🔴 2. Entities are lit top-and-front — BETWEEN FACES, not within one

The guide: *"the top and front of the entity need to be brighter than the
bottom and back. This applies to shading the faces individually, as well as
how the faces are shaded relative to each other."*

⚠️ **This governs the faces of the 3D box relative to each other** — the top
face brighter than the bottom face. Applying it as a bright row at the top of
one flat face and a dark row at the bottom is **pancake shading**, which the
guide lists as an artifact: *"placing the highlights on one side and shadows
on the opposite side of a surface. It disregards the shape."*

The first version of this renderer did exactly that, and the torso came out as
`AAAAAAAA / BBBBBBBB / CCCCCCCC` — measured on the shipped sheet.

### 🔴 2b. The procedure has FOUR steps and stopping at two is what looks wrong

The guide's entity procedure:

1. Generate a texture template
2. **Sketch the colour distribution, add a shadow and a highlight**
3. Add more shades to the palette
4. **Define the material by editing the relative position of CLUSTERS of
   certain shades. Get rid of banding and any other shading artifacts.**

⭐ **Stopping after step 2 gives flat blocks with stripes.** Step 4 is where a
texture stops looking like a coloured rectangle and starts looking like cloth.
It is also the step that is easy to skip, because steps 1–3 already produce
something that renders without error.

**What step 4 means concretely:** small irregular groups of 2–3 adjacent
texels in a slightly different shade, never forming a row, column or diagonal
run. Fixed patterns, not random ones — every crew member gets the same
material map in a different hue, so the set stays identical by construction.

🔴 **Material needs its own ramp, much subtler than the form ramp.** The
display ramp here is ±30%/+18% brightness; material clusters at those values
read as blotches, which is the guide's *noise* artifact — *"adds no
information to the texture"*. The material ramp is ±11%/+8%, about 20 units of
perceptual distance from the midtone.

🔴 **No clusters on the face.** A head face is 8×8 with eyes and a mouth in
it. Scattered shade texels there read as dirt or stubble — measured: the first
attempt gave every crew member a blemished face. ⭐ **Material belongs on
large uniform surfaces, and a face is not one.**

### 🔴 3. No black outlines on an entity

Black outlines are an **item-texture** convention — the guide prescribes them
for the 16×16 inventory sprites, *"a significantly darker outline"*, lit from
the top left. Entities do not get them.

So an edge is the **shadow shade of its own material**, never a separate
black. Using item rules on an entity is the most common way a fan texture
looks off without the artist being able to say why.

### The artifacts to avoid, named

The guide names these, and each is a real failure mode for a generator:

| Artifact | What it is |
|---|---|
| **Banding** | Shades lined up brightest→darkest in a row, revealing the pixel grid |
| **Pillow shading** | Shades applied concentrically from the centre outward, ignoring the form |
| **Pancake shading** | Highlight on one side, shadow on the opposite side, ignoring the shape |
| **Noise** | Brush-like speckle. *"Adds no information to the texture"* |
| **Mixels** | Mixed resolutions in one image — elements finer than the texel grid |
| **Jaggies** | Diagonals with an inconsistent step |

🔴 **Anti-aliasing is explicitly not used.** Neither is dithering, here: the
guide permits it for rough materials, but on a 20×18 bust it costs more
legibility than it buys.

### ⚠️ Form shading must not invent features

Measured while building this: a full-width shadow row along the bottom of the
head — correct by the top-brighter rule — **read as a beard on every member of
the crew.**

⭐ **A shading rule applied without looking at the result produces a feature
nobody asked for.** The rule was right and the placement was wrong. Render it,
look at it, then keep the rule.

### Simplicity is the founding principle

*"Minecraft's art style is founded in simplicity. The overall shape of an
object should be defined by the model and most of the detail by the texture."*

📌 That is the argument for the whole design: shape carries identity, texture
carries material, and **detail that does not survive the grid is removed
rather than shrunk.**

---

## 🔴 The invariant block — Method B only

📌 **Skip this entire section when using `render.py`.** Identical geometry,
palette and lighting are structural there. This exists because independent
generations drift, which is a property of image models, not of the spec.

Each avatar is a separate generation. **Independent generations drift**: the
model re-decides camera angle, texel size, lighting and crop height every time
unless the same words appear in every prompt.

⭐ **Consistency is not a quality to aim for, it is text that must be
identical.** "Keep them consistent" is an instruction to the model; an
invariant block is a guarantee. Write it once, paste it **verbatim** into every
single generation, and never paraphrase or shorten it for the later members.

Fill this in before generating anything, then reuse it unchanged:

```
CREW INVARIANTS — identical in every image
- Framing: upper-body bust, cropped at <exact chest/waist point>
- Camera: <straight-on front view | turned 10-15° to viewer's right>
- Head: cube, exactly as wide as the torso, ~55% of visible height, eyes to viewer
- Texel grid: 8 texels per head face (head 8x8x8, torso 8x12x4, arms 4x12x4)
- Light: from <direction>; faces away from light use that material's shade value
- Palette: locked 16-value dye palette, base + shade column only
- Skin: <palette name + hex>
- Sleeves / base layer: <palette name + hex>
- Background: <palette name + hex, or transparent>
- Canvas: <N>×<N> square, bust fills 80-90% of width, centred
- Style: flat quantised shading, hard nearest-neighbour edges,
  no anti-aliasing, no gradients, no gloss, no outlines
```

**Per-avatar, only these change:** hair, chest/uniform, prop, accent, role hue.

⚠️ **When parallelising across subagents, each one receives this block byte for
byte.** A subagent given a summary produces a sibling that is visibly off, and
the drift is invisible until all six are lined up.

📌 **The order matters.** Keep the invariants first in the prompt and the
per-avatar details last, in the same order every time. Prompt position affects
weighting, so moving the block around between generations reintroduces the
drift it exists to prevent.

### Check consistency before delivering

Line all outputs up side by side and verify, in this order — each is a failure
that requires a redraw, not a note:

1. **Same camera angle?** One member turned differently is the most visible
   error possible.
2. **Same crop height?** Shoulders on one and waist on another reads as two sets.
3. **Same texel size?** Finer blocks on one member breaks the species.
4. **Same light direction?** Shadows on opposite sides look like different art.
5. **Same skin, sleeves, background — and are all values on the palette?** Any
   off-palette tone breaks the set, and shared-slot drift destroys the family
   resemblance.
6. **Same head proportion, and is the head as wide as the torso?** A narrower
   head is the most common drift and makes the figure read as generic rather
   than voxel.

⚠️ **Report every mismatch found, including ones left unfixed.** A consistency
check whose result is never stated is indistinguishable from one that never ran.

## 🔴 The silhouette test

**Before delivering, mentally render every crew member as a flat black shape
at 32×32.**

- If any two are confusable, **change the silhouette, not the colour.** Colour
  identifies fastest; silhouette identifies reliably. Silhouette is what
  survives greyscale, dark mode, colourblindness, and a compressed thumbnail.
- The fix is a different **headwear** shape or a different prop silhouette —
  never a darker shade of the same hue. Headwear changes the outline of the
  head, which is the largest and most visible part of a blocky person.
- Report the outcome plainly, including which pairs were closest. ⚠️ A test
  whose result is never reported is indistinguishable from a test that never
  ran.

⭐ **A constraint that forces simplification is worth more than a rule that
forbids clutter.** "Recognisable at 32×32" does the work of twenty style notes
— and voxel art is natively suited to it, because the style was born from
low-resolution limits in the first place.

## Generation

- Require a capable image model — GPT Image 2, Nano Banana Pro, Seedance
  Pro, or equivalent. Ask the user to enable one rather than falling back to
  SVG or ASCII, and never fabricate a result.
- Generate at **1024×1024 or larger, square**, one file per agent.
- Name files by role: `career.png`, `trading.png`, `content.png`.
- ⚠️ **Do not feed one finished avatar to the model as a reference for the
  next.** Coherence comes from the identical written constraint block. Chaining
  references compounds drift — each generation inherits the previous one's
  accidents.

## ⚖️ Names and characters

**This skill produces a generic blocky aesthetic. It must never reproduce a
specific existing property.**

- Do not generate characters, mobs, skins, or logos from any existing game or
  franchise, and do not name outputs after them.
- Describe the look with generic vocabulary only: *voxel*, *blocky*, *cubic*,
  *low-resolution*, *8-bit*, *pixel*.
- If a user asks for a named character from a game or film, decline the name
  and offer an original character in the same generic style.

⭐ **Style is not protectable; specific characters and names are.** Borrow the
aesthetic, never the vocabulary — that distinction is what makes this skill
safe to publish and safe to use commercially.

📌 **On the proportions and the palette.** The 8×8×8 head and 8×12×4 torso are
a *geometric specification*, the same kind of fact as a paper size — widely
documented and reimplemented. A list of sixteen hex values is likewise factual
data, not creative expression; short colour lists are not protectable.

What would cross the line is generating a **specific named character**,
reproducing its face and outfit, using a franchise logo or font, or naming the
output after it. **The spec is a grid and the palette is a list; the character
is a design.** This skill uses the first two and refuses the third.

## Pitfalls

**Do not add a second prop** to make a role clearer. Two props read as clutter
at small size and destroy the silhouette. Choose a better single prop.

**Do not vary the shared slots to add interest.** Skin, background and the
sleeves are the three things holding the crew together. Varying them is how a
set becomes a collection.

📌 With the legs cropped away there is **less shared area than a full-body
crew has**, so these three slots carry more weight, not less.

**Do not vary the neutral** between crew members to make them distinct. That is
the one colour holding the set together.

**Do not centre-crop differently per avatar.** Inconsistent framing is the
fastest way to make a coherent set look like a collection of unrelated files.

**Do not accept a smooth render.** The most common failure is a glossy 3D
model of a blocky character: correct geometry, soft lighting, anti-aliased
edges, no visible texels. It looks competent and it is the wrong style. Check
for a visible square grid before delivering.

**Do not let the model pick "a nice teal".** Every value is a named palette
entry with a hex code. An approximate colour is off-palette, and off-palette is
the fastest way to lose the look.

**Do not rely on the model remembering the last image.** Each generation is
independent and will re-decide the camera angle, texel size and crop unless
the invariant block is in front of it again, word for word.

**Do not draw legs.** The frame is a bust. A figure with legs squeezed in
shrinks the head, and the head is what identifies the agent at 32px.

**Do not render a realistic human.** The figure is built from six or seven
rectangular prisms. Fingers, facial contours, fabric folds, and shaded muscle
all break the style and none of them survive to 32px.

**Do not generate the example roster.** The eight roles in the table are a
demonstration of silhouette spacing. Generating career/trading/admin for a user
who runs support/legal/scheduling is the single worst failure this skill can
produce — a crew of avatars for agents that do not exist.

**Do not leave the hands empty.** A blocky person with no prop, no headwear
and no outfit block is a generic figure — it identifies nobody, and a crew of
those is six copies of the same avatar in different colours.

**Do not soften the geometry** because a shape looks harsh. Harshness is the
style. A rounded voxel is just a blurry sphere.

**Do not generate the whole crew in one image** to save calls. The user needs
individual square files, and multi-figure compositions drift in scale.
