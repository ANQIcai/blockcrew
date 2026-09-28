---
name: blockcrew
description: Generate a matching set of blocky voxel avatars for a fleet of AI agents, one per role, built so the whole crew reads as siblings while every member stays instantly distinguishable at sidebar size. Use when creating avatars, profile pictures, or identity art for multiple agents, bots, team members, or services that appear together in a list.
---

# Blockcrew

Give a fleet of agents faces. Not one mascot — a **crew**: a set of blocky
voxel characters that obviously belong together and are never mistaken for
each other.

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

1. **Read the roster before asking for it.** If the workspace is an agent
   project, look for agent definitions, profile directories, config files, or
   a README that names the agents and their jobs. Infer the roster from
   evidence when the roles and their purposes are clear.
2. **Ask once, if you must.** One consolidated question: which agents exist,
   what each is for, and whether any house palette must be honoured. Do not
   run a second round of discovery.
3. **Propose the crew map before generating anything.** One row per agent:

   ```
   <agent> — <role in three words> — <prop> — <role hue>
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

## Shape language

- **Hard 90° edges only.** Flat faces, square corners, no bevels, no rounded
  contours, no curves anywhere — not on the head, not on a prop, not on a
  hand. A single curve breaks the voxel read.
- **Head is a cube and dominates**: 45–55% of total figure height. This is what
  makes the set cute rather than architectural.
- **Body is a rectangular prism**, narrower than the head. Limbs are plain
  rectangular prisms with blunt square ends.
- **Face: two square eyes, optionally one square or rectangular mouth.** No
  eyebrows, pupils, nostrils, blush, highlights, or outlines.
- **Visible chunk size stays constant across the crew.** If one avatar is built
  from visibly finer blocks than another, they stop looking like the same
  species.
- **One view angle for the entire crew** — either flat front-facing or a
  consistent 3/4 isometric. Never mix within a set.
- Figure fills **80–90% of the canvas**, centred, standing upright, with even
  margins. ⚠️ Unlike single-mascot work, a crew must be **centred and
  consistently scaled** — corner-anchored compositions look broken when tiled
  in a list.

## Colour

Exactly **three semantic colours per avatar**:

| Slot | Rule |
|---|---|
| Shared neutral | **Identical across the whole crew.** Body and limbs. This is the family resemblance |
| Role hue | One per agent, high chroma, unique within the crew. Used on the prop and exactly one body region |
| Background | One flat colour, or transparent. Same choice for every member |

- Pick role hues **far apart on the wheel**, not neighbouring shades.
- 🔴 **Never rely on red-versus-green to separate two agents.** Roughly 1 in 12
  men cannot distinguish them; a fleet sidebar is exactly where that fails.
- No gradients, no shadows, no ambient occlusion, no texture noise. Flat fills
  only — shading defeats the point of the form.

## The one prop rule

Each agent carries **exactly one** object that names its job. Not two.

- The prop must be **blocky, chunky, and oversized** — roughly a third of the
  figure's height. A realistic-scale prop vanishes at avatar size.
- It sits **on the head or held at chest height**, never as a small detail on
  clothing.
- It must be readable **as a pure black silhouette**. If identifying it
  requires colour, it is the wrong prop.

Worked examples, tested for silhouette separation:

| Role | Prop | Suggested hue |
|---|---|---|
| Career / job search | briefcase | indigo |
| Trading / investment | blocky candlestick bar | teal |
| Admin / butler | serving tray | warm grey |
| Building / engineering | hard hat | amber |
| Content / filming | boxy camera held up | magenta |
| Marketing | megaphone | cyan |
| Research | magnifying glass, square lens | violet |
| Ops / infrastructure | wrench | slate blue |

📌 These are starting points, not a closed list. A role with no obvious object
gets an abstract one — a stacked block tower, a floating cube — rather than a
vague or generic gesture.

## 🔴 The silhouette test

**Before delivering, mentally render every crew member as a flat black shape
at 32×32.**

- If any two are confusable, **change the silhouette, not the colour.** Colour
  identifies fastest; silhouette identifies reliably. Silhouette is what
  survives greyscale, dark mode, colourblindness, and a compressed thumbnail.
- The fix is a different prop shape or a different head-mounted element —
  never a darker shade of the same hue.
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

**Do not vary the neutral** between crew members to make them distinct. That is
the one colour holding the set together.

**Do not centre-crop differently per avatar.** Inconsistent framing is the
fastest way to make a coherent set look like a collection of unrelated files.

**Do not soften the geometry** because a shape looks harsh. Harshness is the
style. A rounded voxel is just a blurry sphere.

**Do not generate the whole crew in one image** to save calls. The user needs
individual square files, and multi-figure compositions drift in scale.
