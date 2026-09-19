# design-concepts/

Standalone, non-functional **design exploration** for OurHome IL. Nothing in this folder is imported by the Flask app, the templates, or the Android project. It is safe to ignore, delete, or ship as-is.

## How to view

- Open `index.html` in a browser. It shows all three concepts side by side in live 390×844 phone frames with tabs per screen.
- Or open any screen directly, e.g. `concept-b/home.html`. On a wide window the page renders inside a phone bezel; on a real phone (or a 390px-wide viewport in DevTools) it fills the screen.
- To try it inside the Capacitor shell, point `server.url` at a static server that serves this folder (for example `python -m http.server` from the repo root and use `http://<pc-ip>:8000/design-concepts/concept-b/home.html`). Do **not** commit that config change.

Every page is plain HTML + CSS + JS with no build step and no libraries. Fonts load from Google Fonts (Rubik, Varela Round, Frank Ruhl Libre, Heebo, IBM Plex Sans Hebrew, IBM Plex Mono); without internet the pages fall back to system fonts and still work.

## What is in here

| Folder | Direction | Screens |
|---|---|---|
| `concept-a/` | Pop: bold, colorful, playful | `home`, `finance`, `baby` |
| `concept-b/` | Quiet Luxury: premium, minimal, glass + neumorphic, light/dark | `home`, `finance`, `baby`, `notifications` |
| `concept-c/` | Mission Control: data-forward bento dashboard | `home`, `finance`, `baby` |

Each concept folder has a `concept.css` (design tokens, phone frame, nav, primitives) and a `concept.js` (helpers: count-up, toast, sheets, confetti / theme toggle / treemap depending on the concept). Pages link to each other through their bottom nav; "Shopping" and "Settings" are placeholders except in Concept B where Settings opens the notification-settings mock.

`SUMMARY.md` describes and compares the three directions and gives a recommendation. `FEATURES.md` is the native-feature brainstorm (what Capacitor can do now vs. what needs native code or the planned Flutter migration).

## Mock data

All screens share the same fictional family so numbers line up across concepts:

- Family "לוי": נועה (current user), יובל, baby אלה (7 months).
- Billing cycle day 10 → current cycle 10.09.2026–09.10.2026, today is day 9 of 30 (Friday 18.09.2026).
- Budget ₪10,000; spent ₪4,730 (₪3,150 fixed + ₪1,580 variable); projection ₪8,420; previous cycle ₪9,140.
- Categories are the app's real defaults (קבועים, קניות - סופר, רכב, משק בית, תינוק, בילויים / פנאי …).
- Baby day frozen at 14:32 for the visualizations; the "time since last feeding" timers tick live from 2:07:14.

## What is interactive (still all mock)

- Tap shopping items / chores to check them (progress + confetti in A).
- Radial FAB (A), center "+" (B): opens an add-expense keypad sheet.
- Bubble split (A) and category tapestry (B) and treemap (C): tap to filter the transaction list.
- Swipe a transaction row right to "split 50/50" (A); long-press a row (B).
- Cycle overlay chart (B finance): drag to scrub days.
- Quick-log buttons (all baby screens): prepend a real entry to the timeline.
- Notification settings (B): all switches, module cascade, quiet-hours dial, wheel time picker, "preview" shows a mock OS banner.
- Theme toggle (B): light/dark; also follows `prefers-color-scheme`.
- What-if simulator (C finance): slider + toggles recompute the projection.
- Natural-language quick add (C home): type "שופרסל 240" and watch the parsed chips.

## How it was verified

Every screen was rendered headlessly in Chrome inside an exact 390px-wide iframe and probed for JavaScript errors and horizontal overflow (document width must equal 390). Tall screenshots were reviewed visually at 390px. Interactive states (sheets, pickers) were captured by triggering them after load.
