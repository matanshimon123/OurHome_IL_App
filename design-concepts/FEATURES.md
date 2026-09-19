# Native-feeling features — brainstorm

Planning notes only. Current stack: Flask backend, Jinja templates loaded from a remote URL inside a Capacitor 8 WebView (`server.url` in `capacitor.config.json`), plugins already installed: `@capacitor/push-notifications`, `@capacitor/share`, `@capacitor/status-bar`.

Legend: **[installed]** already in `package.json` · **[core]** official `@capacitor/*` plugin · **[community]** third-party plugin, verify Capacitor 8 support before committing · **[web]** no plugin needed.

---

## 1. Feasible now in Capacitor

### Notifications

- **Per-module notification toggles (baby / shopping / finance / chores)**
  - Store per-user preferences server-side (new columns or a `notification_prefs` table next to `push_tokens`); `send_push_to_family` filters recipients by module before sending.
  - Mirror them as **Android notification channels** with `PushNotifications.createChannel()` **[installed]** so users can also mute a module from OS settings; the FCM payload sets `android.notification.channel_id`.
  - Cache prefs locally with `@capacitor/preferences` **[core]** so the settings screen renders instantly offline.
  - Mock UI: `concept-b/notifications.html`.

- **Quiet hours**
  - Server-side check in the send path (family/user timezone from `family_settings`); non-urgent pushes are held or dropped, urgent ones (feeding reminder) can bypass.
  - On-device: `@capacitor/local-notifications` **[core]** lets the app schedule its own reminders and honor quiet hours without a server round-trip.
  - Android 13+ needs the `POST_NOTIFICATIONS` runtime permission (already declared); iOS needs `requestPermissions()`.

- **Actionable push notifications** ("סמן כמסולק", "רשום האכלה", "הוסף לרשימה")
  - Send **data-only** FCM messages and display them locally with `LocalNotifications.registerActionTypes()` + `schedule()` **[core]**, which supports action buttons on both Android and iOS. (`PushNotifications.registerActionTypes` is iOS-only.)
  - Handle `localNotificationActionPerformed` and call the existing JSON API with the stored JWT.
  - Bundled/grouped notifications (one banner for several shopping items) via `group`/`threadIdentifier`.

- **Deep-link from a push to the right screen**
  - Put a `route` in the FCM `data` payload; on `pushNotificationActionPerformed` navigate the WebView (already partially wired in `base.html`). `@capacitor/app` **[core]** `appUrlOpen` covers links from outside the app (Android App Links / iOS Universal Links need the domain association files on the Flask server).

- **On-device feeding reminder**
  - Today the Flask loop polls every 60 s. Instead, when a feeding is logged, schedule a local notification at `logged_at + interval` and cancel it on the next log. Works with the phone offline and survives server restarts. Keep the server path as a fallback for the partner's device.

### Security & privacy

- **Biometric lock on sensitive screens (finance, settings)**
  - Community plugin, e.g. `@aparajita/capacitor-biometric-auth` or `capacitor-native-biometric` **[community]**; fall back to device PIN.
  - Re-lock on `App.addListener('appStateChange')` **[core]** after N minutes in background; blur the WebView content while locked (CSS class on `body`).
  - Store the JWT in `@capacitor-community/secure-storage` or the biometric plugin's keychain helper instead of `localStorage`.

- **Privacy screen** (hide balances in the app switcher): `@capacitor-community/privacy-screen` **[community]**.

### Offline & sync

- **Offline support with sync queue**
  - Prerequisite: the app currently loads *everything* from `server.url`, so with no network the WebView shows the `www/index.html` retry page. To work offline the HTML/CSS/JS must ship in `webDir` (or be cached aggressively by `static/sw.js`) and talk to the API over fetch.
  - Local store: `@capacitor/preferences` **[core]** for small state, `@capacitor-community/sqlite` **[community]** for a real local table set (payments, shopping items, feedings).
  - Detect connectivity with `@capacitor/network` **[core]**; queue writes with client-generated UUIDs and replay them on reconnect; server needs idempotent upserts (the API mostly keys on `id`, so add a `client_id` column).
  - Conflict policy: last-write-wins per row is enough for this app; show a "synced 14:32" indicator (Concept C top bar).

- **Background refresh** (pull new family data before the user opens the app): `@capacitor/background-runner` **[core]** runs a small JS worker on a schedule; limited API surface, no DOM, and the OS may throttle it. Fine for "prefetch summary", not for guaranteed delivery.

### Location

- **Location-based reminders ("you're near the supermarket, 6 items left")**
  - Foreground version: `@capacitor/geolocation` **[core]** + local notification when the app is open or resumed. Cheap and reliable.
  - Background geofencing needs a community plugin (`@transistorsoft/capacitor-background-geolocation` (paid) or similar) and "always" location permission; expect OS throttling and store-review questions. Treat as a stretch goal.

### Feel & polish

- **Haptics** on toggles, check-offs, keypad, pull-to-refresh: `@capacitor/haptics` **[core]** (`impact`, `selectionChanged`). The concepts use `navigator.vibrate` as a placeholder.
- **Native share** of a shopping list or cycle summary/CSV: `@capacitor/share` **[installed]** + `@capacitor/filesystem` **[core]** to write the file first.
- **Receipt photos** on an expense: `@capacitor/camera` **[core]** (the shopping list already accepts item images).
- **Status bar / edge-to-edge**: `@capacitor/status-bar` **[installed]** with per-screen style (light text on Concept A's colored headers, dark mode in B/C) and `viewport-fit=cover` + `env(safe-area-inset-*)` padding as in the concept pages.
- **Keyboard behavior** for the keypad sheets: `@capacitor/keyboard` **[core]** (`resize: body`, `setAccessoryBarVisible` on iOS).
- **App badge** with pending chores / items: `@capawesome/capacitor-badge` **[community]**.
- **Screen orientation lock** to portrait: `@capacitor/screen-orientation` **[core]**.
- **Splash + launch**: `@capacitor/splash-screen` **[core]**; hide it from JS once the first screen has data instead of the current fixed spinner page.
- **Pull-to-refresh, swipe-to-reveal actions, bottom sheets, skeletons, view transitions** — all **[web]**. Android WebView ≥ 111 supports the View Transitions API for same-document transitions, which gives the "shared element" feel between the home card and the finance screen.
- **Dark mode following the system** — **[web]** `prefers-color-scheme` (Concept B does this) plus a status-bar style switch.
- **Text size / accessibility**: respect the OS font scale; `@capacitor/text-zoom` **[core]** if the WebView needs a manual override.

### Smart features that are pure backend + web

- Predictive end-of-cycle projection (fixed vs. variable split), anomaly detection per category vs. 6-month mean, recurring-charge detection ("bill detective"), feeding-pattern windows, chore streaks. All are SQL over existing tables; the concept screens show how they surface as cards, banners and actionable pushes.
- Natural-language quick add (Concept C): a small rule-based parser on the client, optionally a server endpoint that maps merchant names to categories from the family's history.

---

## 2. Requires native code / would need the planned Flutter migration

- **Home screen widgets** (today's spend, last feeding timer, shopping count)
  - Widget UI is rendered by the OS from native code (Android `AppWidgetProvider` + RemoteViews / Jetpack Glance, iOS WidgetKit + SwiftUI). A WebView cannot draw a widget. Community bridges only pass data to a widget you still have to write natively. Note: Flutter's `home_widget` package also requires the native widget code; Flutter only makes the data bridge easier.

- **App shortcuts / quick actions** (long-press the icon → "הוסף הוצאה", "רשום האכלה")
  - Static Android shortcuts are just manifest XML and technically possible today, but routing them into the WebView and keeping them in sync with the user's modules needs native handling. Dynamic/pinned shortcuts and iOS quick actions need native code; Flutter's `quick_actions` package wraps both.

- **Android 12+ dynamic color (Material You)**
  - Requires reading the system color scheme from native resources (`android.R.color.system_accent1_*`); no Capacitor core plugin exposes it. Flutter's `dynamic_color` package does. In Capacitor the closest you get is dark/light via CSS.

- **Live feeding timer on the lock screen / ongoing notification with chronometer, iOS Live Activities**
  - Needs a foreground service + custom notification layout on Android and ActivityKit on iOS. Flutter still needs platform channels for Live Activities, but the notification side has mature packages.

- **Predictive back gesture (Android 14+) and true native navigation feel**
  - WebView back handling stays a JavaScript history hack; nested scroll + gesture conflicts (e.g. swipe-to-delete inside a scrolling list on a bottom sheet) are where a WebView feels "webby". Flutter renders its own gestures and animations at native frame rate.

- **Share target** (share a receipt photo or a text list *into* OurHome from another app)
  - Requires intent filters + native activity to hand the payload to the web layer; community plugins are thin. Flutter: `receive_sharing_intent`.

- **Wear OS / Apple Watch complications** (log a feeding from the wrist): entirely native.

- **Quick Settings tile / Siri & Assistant App Actions / Android Auto & CarPlay**: native integrations with no web bridge.

- **Reliable background sync and scheduled work** (guaranteed re-sync every hour, upload receipts in the background)
  - `background-runner` is best-effort with a restricted runtime; Android WorkManager / iOS BGTaskScheduler through Flutter's `workmanager` is the dependable route.

- **Widgets and complications aside, the strongest argument for Flutter** is rendering: 120 Hz lists, physics-based swipe/drag, and low-end Android devices where `backdrop-filter` (Concept B) and large SVG animations (Concept C) drop frames in a WebView. If the team goes that way, Concept B's tokens and Concept C's chart specs port cleanly to Flutter (Material 3 + `fl_chart`/custom painters).
