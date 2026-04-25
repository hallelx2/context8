# Context8 — Hackathon Demo Video Script

> **Format:** 1080p, ~125 seconds, mixed-media (lifestyle illustrations + UI mockups + terminal/code + diagram overlays). Voice: `af_heart` (Kokoro, warm female). Background music: synthesized ambient pad + sound-effect cues at key beats. Tagline locked: **"Context8 — The Next Generation of Problem Solving for AI."**
>
> **Closing line locked (user's words):** *"It makes your coding smooth and easy."*

---

## Story arc

```
PAIN → LIVED MOMENT → CONTEXT7 (known) → CONTEXT8 (new layer) →
INSTALL → 4 FEATURE DEMOS → ROADMAP (website + skills scaffold) → BRAND CLOSE
```

Eleven scenes. Lifestyle/illustration scenes carry emotion; terminal scenes carry proof; diagram overlays carry technical credibility; the close carries the brand line.

---

## Scene-by-scene

### Scene 1 — The Pain (0:00 – 0:12)
**Visual style:** flat illustration. Late-night developer at a desk, glow from a laptop, multiple browser tabs hovering above. Terminal in the background with red error glyphs. The chat window then collapses and the solution dissolves into floating pixels that drift offscreen.

**Voice:** *"Every coding agent runs into problems that aren't in the docs. Hours of debugging. A breakthrough at 2 a.m. And then... the chat closes, and the answer is gone."*

**SFX:** keyboard typing under the line; soft "whoosh + glass-shatter" when the chat dissolves; brief silence after.
**Music:** ambient pad starts low.

---

### Scene 2 — The Lived Moment (0:12 – 0:24)
**Visual style:** stylized UI mockup. Two nested sidebars on the left of a fake app layout. Inner sidebar + nav refusing to anchor under the outer sidebar + nav — the inner one wobbles, drifts, snaps wrong. Then a coral "✓" pops, locking it in place. Then everything fades.

**Voice:** *"Last week I spent two hours getting a nested sidebar to anchor properly. I cracked it. Then I closed the tab — and the fix was gone with it."*

**SFX:** subtle UI clicks while the sidebar wobbles; positive chime when the fix lands; ambient drop when the layout fades.

---

### Scene 3 — Context7 Is Useful, But… (0:24 – 0:36)
**Visual style:** diagram/card. The Context7 card slides in (Upstash teal). Behind it, stylized doc panels fan out — React, Next.js, FastAPI, PyTorch — each labeled with its library name.

**Voice:** *"Context7 from Upstash gives your agent live documentation. The known knowns. What library authors wrote down. Useful — but documentation only covers what's documented."*

**SFX:** soft page-turn whoosh as docs fan out; gentle synth swell.

---

### Scene 4 — Introducing Context8 (0:36 – 0:48)
**Visual style:** hero card. Big "Context8" wordmark fades up center-screen in the project's violet. Tagline below: *"Collective problem-solving memory for coding agents."* Subtitle: *"Powered by Actian VectorAI DB."*

**Voice:** *"Context8 is the next layer. A live directory of hard problems other developers have already solved — searchable by your agent, right inside your terminal."*

**SFX:** confident chord swell on the wordmark reveal; small bubble-pop on the tagline.

---

### Scene 5 — Install & Add to Claude Code (0:48 – 1:00)
**Visual style:** terminal in the Claude Code TUI aesthetic we already built. Commands type out one by one:
```bash
$ pip install context8
$ context8 start          # Docker container starts
$ context8 init --seed    # 24 curated solutions loaded
$ context8 add claude     # registered with Claude Code
$ context8 doctor
✓ Named vectors (≥3)   ✓ Sparse vectors  ✓ Hybrid fusion ready  ✓ Filtered search
```

**Voice:** *"One pip install. One Docker command. Add it to Claude Code, Cursor, or Windsurf. Your agent now has three new tools — search, log, and rate."*

**SFX:** soft mechanical typing; positive confirm chime on each green ✓.

---

### Scene 6 — Demo 1 · Named Vectors (1:00 – 1:14)
**Visual style:** terminal running `context8 demo` for the asyncio-in-Jupyter scenario. **Diagram overlay** appears beside the terminal: three vector spaces (`problem` 384d · `solution` 384d · `code_context` 768d) lighting up in sequence as each query type retrieves the same record three different ways.

**Voice:** *"Three named vector spaces — problem text, code patterns, and solution approach. The same record, three doors in. That's Actian's named vectors at work."*

**SFX:** ascending three-pop sequence as each vector lights up; light reverb tail on the third.

---

### Scene 7 — Demo 2 · Hybrid Fusion (1:14 – 1:28)
**Visual style:** terminal split-screen. Left pane: dense-only search for `ERESOLVE unable to resolve dependency tree` returns nothing useful (red ✗). Right pane: dense + sparse RRF lights up the exact record at #1 (green ✓).

**Voice:** *"Hybrid fusion. Dense vectors catch meaning, sparse vectors catch the exact error code. Together, they find what neither could alone."*

**SFX:** glitch/static on the failing left pane; bright success chime on the right pane.

---

### Scene 8 — Demo 3 · Filtered Search (1:28 – 1:40)
**Visual style:** terminal with the same query — *"out of memory error during build"* — and a language toggle pill above it: **python** ↔ **javascript**. Pill animates between states; the result list swaps server-side both times.

**Voice:** *"Filtered search. Same query, different stack — server-side, by Actian's FilterBuilder. A Python agent never sees JavaScript noise."*

**SFX:** physical-toggle click each time the pill flips; subtle whoosh on result swap.

---

### Scene 9 — Demo 4 · The Self-Improving Loop (1:40 – 1:54)
**Visual style:** small choreographed animation. Agent A retrieves a solution → applies it → calls `context8_rate(worked=True)` → record's `worked_ratio` ticks up (counter animates 5/6 → 6/7 → 7/8 with the percentage rising). Then a second agent searches the same problem — the record floats to position #1 with a small upward arrow.

**Voice:** *"And every time an agent applies a fix, it rates it. Solutions that work float to the top. Your knowledge base actually learns."*

**SFX:** soft positive ping on each rating; ascending tick when the record rises in rank.

---

### Scene 10 — Roadmap · The Website (1:54 – 2:08)
**Visual style:** mockup of the Context8 website. Search bar with *"starting a Next.js 15 + Prisma project"*. Below it, results appear: top community-solved problems for that stack (hydration mismatch, Prisma serverless pool, Tailwind v4 dark mode, Next.js caching change). A *"Generate skill"* button glows. Click → animation shows files dropping into a `.claude/skills/nextjs-gotchas/SKILL.md` panel. Then a Claude Code TUI lights up beside it — already aware of the dragons before any code is written.

**Voice:** *"Soon: a hosted Context8. Scaffold any project from the website — and your agent walks into your repo already knowing the dragons."*

**SFX:** crisp UI clicks; satisfying "drop" thunk when the skill file lands; ambient lift.

---

### Scene 11 — The Close (2:08 – 2:18)
**Visual style:** background dims to near-black. Center: **Context8 — The Next Generation of Problem Solving for AI** in large type, the violet wordmark glowing above. Sub-line fades in below: *"Built on Actian VectorAI DB."* Tiny third line, slightly smaller, in the user's voice: *"It makes your coding smooth and easy."* GitHub URL faintly at the bottom.

**Voice:** *"Context8. The next generation of problem solving for AI. It makes your coding smooth and easy."*

**SFX:** warm pad swell into a final, gentle chord; light reverb tail.

---

## Audio inventory

All synthesized locally with FFmpeg or Kokoro — no external assets needed.

| Asset | Source | Length | Use |
|---|---|---|---|
| Narration × 11 segments | Kokoro `af_heart` | ~95s total | Per-scene voiceover |
| Background ambient pad | FFmpeg sine + tremolo + lowpass + echo | 130s | Underbed (~30% volume) |
| Bubble pop (small) | FFmpeg sine 880Hz, 80ms, exp envelope | 0.08s | Tool calls, vector lights |
| Bubble pop (large) | FFmpeg sine 440Hz, 200ms, exp envelope | 0.2s | Wordmark reveal |
| Confirm chime | FFmpeg dual sine (660+880Hz), 300ms, slight bell | 0.3s | Each green ✓ |
| Success chime | FFmpeg three-sine arpeggio (C5-E5-G5), 600ms | 0.6s | Hybrid-fusion right pane |
| Glitch / static | FFmpeg white noise + bandpass + bitcrush, 300ms | 0.3s | Hybrid-fusion left pane (failure) |
| Page-turn whoosh | FFmpeg pink noise + envelope + reverb, 600ms | 0.6s | Docs fan-out, scene transitions |
| UI click | FFmpeg short transient, 60ms | 0.06s | Toggles, buttons |
| Drop / thunk | FFmpeg sine 220Hz + lowpass + short decay | 0.4s | Skill file landing |

---

## Visual style guide

- **Brand colors:** Context8 violet `#8B6FE3` as accent (matches the README badge), warm coral `#D97757` from the Claude Code aesthetic for active highlights, near-black `#1A1A1A` canvas, cream `#ECE7D9` for the Claude Code TUI header card we reuse.
- **Typography:** Inter for display + UI, JetBrains Mono for code/terminal — same as the previous video.
- **Illustration scenes (1, 2, 10):** flat geometric, no skeuomorphism. Abstract figures, not photo-real.
- **Diagram overlays (3, 6):** glowing nodes + thin connecting lines, matching the brand violet.
- **Terminal scenes (5–9):** the Claude Code TUI we already built, ported in.
- **Scene transitions:** 0.6s crossfade between scenes; transitions land on a beat in the underbed music.

---

## Production plan

1. **Generate narration** — 11 Kokoro segments, save to `audio/narration-XX.wav`. Measure each duration to lock scene timing.
2. **Synthesize SFX library** — 9 short clips with FFmpeg, save to `audio/sfx/`.
3. **Synthesize ambient pad** — 130s underbed at low volume.
4. **Build composition** — single HyperFrames `index.html`, 11 sub-compositions or one root with scene transitions, total ~125s, 30fps.
5. **Lint + render** — `npx hyperframes lint`, then `npx hyperframes render`.
6. **Move + play** — drop the MP4 into `~/Downloads/` and review.

---

## What changes vs the Claude Code demo we already shipped

- **Mixed media** — illustrations and UI mockups, not just the terminal. ~half the scenes are non-terminal.
- **Longer** — ~125s vs 67s — to give all four Actian features real screen time.
- **Sound-effect layer** — punch beats with FFmpeg-synthesized pops/chimes/whooshes, not just narration + bgm.
- **Brand-forward close** — locked tagline + the user's "smooth and easy" line, not a generic outro.
- **Roadmap scene** — the hosted Context8 + scaffold-from-website + skills download flow, which the existing project doesn't yet ship but the video should preview.
