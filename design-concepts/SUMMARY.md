# Design concepts — summary & recommendation

Three standalone visual directions for the same three screens (home dashboard, finance/expenses, baby tracker), all Hebrew RTL, all built for a 390px phone viewport, all with hardcoded mock data. Open `index.html` to compare them side by side.

## Concept A — "Pop" (`concept-a/`)

Bold and playful: cream canvas, candy palette (coral, sunflower, mint, sky, grape), thick ink outlines with hard offset shadows so every card reads like a sticker, Rubik + Varela Round type, springy easing everywhere. Distinctive pieces: a liquid **budget jar** that fills with an animated wave, a **week-of-coins** strip sized by daily spend, a **bubble split** of categories, a **spending race** between the two partners with a settle-up card, a **24-hour radial baby clock** with sleep arcs and feeding dots, a **pillow-stack** sleep chart, and a radial quick-action FAB. Smart layer: predictive end-of-cycle banner, "bill detective" that spots a recurring Netflix charge, and a detected feeding-pattern reminder with a chunky toggle. Micro-interactions include confetti on check-offs, squishy log buttons that prepend real timeline entries, and swipe-to-split on transactions.

*Feels like:* a friendly consumer app; great for the baby and chores modules, a bit loud for money.

## Concept B — "Quiet Luxury" (`concept-b/`)

Premium and calm: warm stone canvas with a slowly drifting color mesh behind frosted-glass cards, neumorphic switches/segmented controls/keypad, Frank Ruhl Libre serif for headlines and amounts with Heebo for UI text, and a restrained gold/sage/rose/lilac accent set. It is the only concept with **light and dark themes** (system-following plus a manual toggle). Distinctive pieces: a **watch-dial budget gauge** with a "today" marker on the cycle, a **cycle overlay chart** (this cycle vs. last, projection, budget line) you can scrub with your finger, a **category tapestry** bar, a **moon-phase sleep week**, a 24h day band, and a fully mocked **Notification Settings** screen with per-module cascades, a quiet-hours dial, an iOS-style wheel time picker, delivery style, and a "preview" that slides a mock OS banner in. Smart layer: insight chips with a detail sheet, subscription detection, and a nap-window forecast that links to quiet hours.

*Feels like:* a banking or health app you would trust; slow, deliberate motion; easy to extend to the remaining screens.

## Concept C — "Mission Control" (`concept-c/`)

Data-forward and dark: instrument-panel background, 1px-bordered **bento tiles**, IBM Plex Sans Hebrew with IBM Plex Mono for every number, and neon-but-restrained cyan/lime/amber/rose/violet accents that double as category colors. Distinctive pieces: a segmented **fuel-gauge budget** with a projection marker, a **family activity heatmap** (7 days × 4-hour buckets), a **cycle calendar heatmap**, a **category river** (stacked stream) with a fixed-costs toggle, a **squarified treemap**, upcoming fixed charges with countdown bars, a **what-if simulator** that recomputes the projection live, a **7×24 sleep heatmap**, a feeding-interval timeline with a predicted next feed, and a **natural-language quick-add** bar that parses "שופרסל 240" into amount/category/member chips. Smart layer: anomaly detection with a one-tap "mark as one-off", forecast with confidence, sleep streaks.

*Feels like:* an ops dashboard for the household; the strongest finance screen of the three, the least cozy for 3 a.m. baby logging.

## Side by side

| | A · Pop | B · Quiet Luxury | C · Mission Control |
|---|---|---|---|
| Personality | playful, loud, warm | calm, premium, trustworthy | precise, dense, technical |
| Type | Rubik / Varela Round | Frank Ruhl Libre / Heebo | IBM Plex Sans Hebrew / Plex Mono |
| Themes | light only | light + dark | dark only |
| Signature viz | liquid jar, radial baby clock, bubble split | dial gauge, scrubbable overlay chart, moon phases | heatmaps, river, treemap, simulator |
| Smart feature | bill detective, pattern reminder | subscription detection, nap-window → quiet hours | anomaly card, what-if model, NL quick add |
| Notification settings mock | – | ✔ | – |
| WebView performance risk | low (solid colors, transforms) | medium (`backdrop-filter` blur on many cards) | medium (many SVG nodes, fine on modern devices) |
| Effort to roll out to all screens | medium (illustrations per module) | low-medium (token system, few components) | medium (every screen needs a data story) |

## Recommendation

**Go with Concept B as the base direction, and borrow two things from the others.**

Why B: this is a daily-use family finance app; the calm surface, serif numbers and native-feeling controls make money and settings feel trustworthy, it already supports dark mode (parents use this at night), its component set is small enough to apply to the shopping, settings, history and auth screens quickly, and it is the only concept that already includes the notification-settings screen we need for per-module toggles and quiet hours. Its main risk is `backdrop-filter` cost on low-end Android WebViews; the fix is cheap (reduce blur radius or fall back to solid `--card` surfaces below a device-class threshold) and does not change the look much.

What to borrow: Concept C's finance density — the calendar heatmap, treemap and what-if simulator belong in the "Finance" screen as an expandable "analytics" section, restyled with B's tokens. And Concept A's tactile feedback for the baby tracker and chores — squishy one-tap logging, confetti on a completed list, live timers — because those modules reward delight more than restraint.

If the team prefers a single, cheaper direction with no performance caveats, Concept A is the safe second choice; Concept C works best as a "pro" mode rather than the default look.
