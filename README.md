# blockcrew

**Blocky voxel avatars for a fleet of AI agents — one per role, built as a
matching set.**

An Agent Skill. Point it at your agents, get back a crew that looks like a
family and never gets confused in a sidebar.

```
npx skills@latest add ANQIcai/blockcrew
```

Then ask your agent:

> give my agents avatars with blockcrew

---

## Why a crew, not a mascot

Most avatar generators make **one** character. That is a different, easier
problem.

A fleet of agents shows up **side by side** — in a sidebar, a config file, a
dashboard row — usually at 32–64 pixels. The set has to answer two questions
at the same time:

| Question | Solved by |
|---|---|
| Are these the same team? | Shared geometry, shared neutral colour, shared view angle |
| Which one is the trading agent? | Silhouette first, colour second |

Optimise only for the first and you get six characters nobody can tell apart.
Optimise only for the second and you get six characters that look like they
came from six different projects.

**blockcrew is the constraint set that holds both.**

---

## What it produces

One square image per agent. Flat colour, hard 90° edges, cube head, one
oversized prop that names the job.

| Role | Prop | Hue |
|---|---|---|
| Career / job search | briefcase | indigo |
| Trading / investment | candlestick bar | teal |
| Admin / butler | serving tray | warm grey |
| Building / engineering | hard hat | amber |
| Content / filming | boxy camera | magenta |
| Marketing | megaphone | cyan |

Starting points, not a closed list. A role with no obvious object gets an
abstract one rather than a vague one.

---

## The rules that do the work

**Three colours per avatar.** A shared neutral identical across the whole crew
— that is the family resemblance. One role hue, unique per agent. One
background, same choice for everyone.

**Exactly one prop.** Not two. A second prop reads as clutter at avatar size
and destroys the silhouette.

**The silhouette test.** Before delivery, every member is checked as a flat
black shape at 32×32. If two are confusable, the fix is a different
*silhouette*, never a different shade.

> Colour identifies fastest. Silhouette identifies reliably — it survives
> greyscale, dark mode, colourblindness, and a compressed thumbnail.

**No red-versus-green** as the only separator between two agents. Roughly 1 in
12 men cannot distinguish them, and a sidebar is exactly where that fails.

---

## Requirements

A capable image model — GPT Image 2, Nano Banana Pro, Seedance Pro, or
equivalent. The skill will ask you to enable one rather than silently falling
back to something worse.

Works with any agent that reads Agent Skills.

---

## ⚖️ On style and names

This skill generates a **generic blocky aesthetic**. It will not reproduce
characters, mobs, skins, or logos from any existing game or franchise, and it
will decline to name outputs after them.

Style is not protectable under copyright; specific characters and names are.
Borrow the aesthetic, never the vocabulary.

---

## Licence

MIT. Do what you like with it.
