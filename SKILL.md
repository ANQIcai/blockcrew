---
name: blockcrew
description: Generate a matching set of blocky, low-resolution pixel-art voxel character avatars for a fleet of AI agents — one little person per role, built so the whole crew reads as siblings while every member stays instantly distinguishable at sidebar size. Use when creating avatars, profile pictures, or identity art for multiple agents, bots, team members, or services that appear together in a list.
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

   State the shared neutral and the shared view angle once, above the table.
   Wait for approval unless the request already authorises generation.
4. **Generate one avatar per agent, each as a separate full-resolution square
   image.** Never ask the model to compose a grid, sheet, or side-by-side
   comparison — a crew rendered in one image drifts in scale and lighting
   between members, and the individual files are what the user actually needs.
5. **Parallelise with subagents when the runtime supports them.** Each subagent
   receives the identical shared-constraint block plus one agent's row. Shared
   constraints must be passed verbatim, not summarised — a paraphrased spec is
   how crews lose coherence.
6. **Run the silhouette test** (below) before delivering. Report the result
   honestly, including failures.
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
- **Anatomy, all rectangular prisms:** one cube head, one rectangular torso,
  two arms, two legs. Blunt square ends. No hands or feet as separate shapes —
  the limb simply ends.
- **Proportions:** head is **30–40% of total figure height** — larger than a
  real person, smaller than a chibi mascot. Torso roughly the same width as
  the head; arms narrower and hanging at the sides or holding the prop; legs
  short and straight.
- **The head reads as a face, not a box.** Two square eyes on the front face,
  optionally one small rectangular mouth. A separate flat colour block across
  the top of the head for hair. No eyebrows, pupils, nostrils, blush,
  highlights, or outlines.
- **Standing upright, facing the viewer.** Symmetrical, neutral stance. No
  action poses, no walking, no dynamic angles.
- **Visible chunk size stays constant across the crew.** If one avatar is built
  from visibly finer blocks than another, they stop looking like the same
  species.
- **One view angle for the entire crew** — either flat front-facing or a
  consistent 3/4 isometric. Never mix within a set.
- Figure fills **80–90% of the canvas**, centred, with even margins. Framing
  is either full-body or head-and-torso, but ⚠️ **the same choice for every
  member** — a crew that mixes crops looks like unrelated files.

⭐ **A person carries a role better than a symbol does.** An icon of a
briefcase says "career"; a small blocky person *holding* a briefcase says
"this is the agent who handles my career". The second is what an avatar is
for — it stands in for someone.

## Colour — a fuller palette, held together by what is shared

Each avatar carries **five to seven materials**. A three-colour figure was too
sparse to read as a person: skin, hair, top, trousers and shoes are five
different things before the job is even named.

🔴 **The crew coheres through the SHARED slots, not through scarcity.** Three
of the slots below are identical for every member — that is the family
resemblance. The rest are free to vary, and should.

| Slot | Shared or per-agent | Notes |
|---|---|---|
| Skin | **shared** | One tone for the whole crew, or match the user's own if they ask |
| Background | **shared** | One flat colour, or transparent — same choice for every member |
| Base garment | **shared** | Trousers/lower body. The quiet neutral that ties the set together |
| Hair | per-agent | Can differ freely; it is also a separator |
| Top / uniform | per-agent | Carries the role hue |
| Prop | per-agent | Role hue, or its own accent |
| Accent | per-agent, optional | One extra: shoes, belt, collar, lanyard, hatband |

**Each material gets two to four quantised shades** on the texel grid — a base
value plus one or two steps darker for the sides facing away from the light.
That is what makes a surface read as material rather than as vector fill, and
it is why a five-material figure is not a busy one.

### Keeping it from turning into confetti

- **One dominant role hue per agent**, high chroma, unique in the crew. Every
  other per-agent colour stays **lower in saturation** than it. A figure with
  four equally loud colours has no role hue at all.
- **Pick role hues far apart on the wheel**, not neighbouring shades.
- 🔴 **Never rely on red-versus-green to separate two agents.** Roughly 1 in 12
  men cannot distinguish them; a fleet sidebar is exactly where that fails.
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
- Held at chest height in one or both hands, or resting on a shoulder.
- Readable **as a pure black silhouette**. If identifying it needs colour, it
  is the wrong prop.

Worked examples, tested for silhouette separation:

| Role | Headwear / hair | Top | Prop | Accent | Role hue |
|---|---|---|---|---|---|
| Career / job search | neat side-part | collared shirt + tie | briefcase | polished shoes | indigo |
| Trading / investment | headset | open collar | candlestick bar | lanyard | teal |
| Admin / butler | slicked flat hair | waistcoat + lapels | serving tray | white gloves | warm grey |
| Building / engineering | **hard hat** | hi-vis band | wrench | tool belt | amber |
| Content / filming | **backwards cap** | plain tee | boxy camera | camera strap | magenta |
| Marketing | **beret** | bold-panel top | megaphone | scarf | cyan |
| Research | round flat-top hair | lab-coat lapels | square-lens magnifier | breast-pocket block | violet |
| Ops / infrastructure | **beanie** | zip-up panel | toolbox | boots | slate blue |

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
4. **One optional accent.** Shoes, belt, lanyard, hatband, strap. Lower
   saturation than the role hue. Skip it if nothing fits; do not invent
   decoration to fill the slot.

**If a role is purely abstract** — "memory", "router", "orchestrator" — give
the figure an abstract prop rather than a vague gesture: a stacked block
tower, a floating cube, a key, a clipboard of stacked bars. ⚠️ Never leave the
hands empty and never fall back to a generic office worker; an unidentifiable
member defeats the point of a crew.

**If two roles genuinely overlap** — "backend" and "infra", "research" and
"analysis" — separate them on **headwear first, prop second, hue last**. If
they still collide, ask the user which distinction matters to them rather
than guessing.

## Resolution and surface — the pixelated read

🔴 **Blocky geometry alone is not enough.** A cube-headed figure rendered with
smooth, perfectly flat surfaces looks like a modern low-poly toy, not a
low-resolution character. The pixelated quality comes from the **surface**, not
only the shape.

Three things produce it, and all three are required:

**1. A visible texel grid.** Every surface is divided into large square texels
— roughly **8–16 across the width of the head**, held consistent across the
whole figure and the whole crew. The texels must be individually visible at
full size. If a surface reads as one unbroken colour field, the resolution is
too high.

**2. Quantised variation within each colour region.** Adjacent texels of the
same material differ by small steps in brightness — two to four discrete
shades of the role hue, assigned per texel, never blended. This is what makes
a surface read as *material* rather than as vector fill.

⚠️ **This is not noise and not texture detail.** It is a handful of flat
values snapped to the texel grid. No grain, no speckle, no photographic
texture, no per-pixel randomness.

**3. Hard pixel edges — nearest-neighbour, never anti-aliased.** Every boundary
between colours is a stepped square edge. No feathering, no soft transitions,
no smoothed diagonals. A diagonal is a visible staircase of squares.

⭐ **Low resolution is a design constraint being displayed, not a defect being
hidden.** The staircase edge is the whole aesthetic — smoothing it produces a
cleaner image that has lost the point.

**Say it in the prompt explicitly.** Image models default to smooth, polished
output, so the words that matter are: *low-resolution texel grid, visible
square pixels, nearest-neighbour edges, no anti-aliasing, no gradients,
quantised flat shading*. Omitting them yields a glossy 3D render of a blocky
character — geometrically correct and stylistically wrong.

⚠️ **Render at high pixel dimensions with a low apparent resolution.** The file
is 1024×1024 or larger; the *apparent* grid is coarse. Do not generate a small
image and upscale it — that softens the edges, which destroys the only quality
this section exists to produce.

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

## Pitfalls

**Do not add a second prop** to make a role clearer. Two props read as clutter
at small size and destroy the silhouette. Choose a better single prop.

**Do not vary the shared slots to add interest.** Skin, background and the
base garment are the three things holding the crew together. Varying them is
how a set becomes a collection.

**Do not vary the neutral** between crew members to make them distinct. That is
the one colour holding the set together.

**Do not centre-crop differently per avatar.** Inconsistent framing is the
fastest way to make a coherent set look like a collection of unrelated files.

**Do not accept a smooth render.** The most common failure is a glossy 3D
model of a blocky character: correct geometry, soft lighting, anti-aliased
edges, no visible texels. It looks competent and it is the wrong style. Check
for a visible square grid before delivering.

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
