# AAOS exploration notes (E8)

Status: research, 2026-10-31. Feeds E4.S4 (Cockpit) and E2.S2 (launcher). Checked against AOSP `main`; AAOS pieces
move between releases, so treat file names as pointers, not contracts.

Our target: unprivileged Android 10 app, Slint UI, 1280x768 landscape, no Play services, no car service.
Short answer: we reuse no AAOS code. We borrow ideas. Almost everything useful is design.

## Table

| Component | Runs app-level on Android 10? | Licence | What we take |
|---|---|---|---|
| CarLauncher (`packages/apps/Car/Launcher`) | No. Manifest asks for `INJECT_EVENTS`, `MANAGE_ACTIVITY_TASKS`, `ACTIVITY_EMBEDDING`, `android.car.permission.*`. It also needs `android.car` APIs. | Apache 2.0 (header in `CarLauncher.java`) | Home = cards (map, media, assistant) plus a separate app grid. Design only. |
| Car UI library (`libs/car-ui-lib`) | Technically yes as a static library, but it is Android Views and Car-specific RRO theming. We do not embed Views. | Apache 2.0 (AOSP) | Component sizes and the idea of "tokens that can be overlaid". Design only. |
| Car rotary lib (`libs/car-rotary-lib`) | Views only (`FocusParkingView`, `FocusArea`). Useless under Slint. | Apache 2.0 | The focus model (see below). |
| Car App Library (`androidx.car.app`) | No. It is a client API. A host (Android Auto or AAOS system app) renders the templates. | Apache 2.0 (AndroidX) | Template vocabulary and step limits as design rules. |
| Media centre (`packages/apps/Car/Media`) | No as an app (`MEDIA_CONTENT_CONTROL` is signature/privileged). The pattern, yes: see below. | Apache 2.0 | Client pattern with `MediaBrowser`. Card layout. |
| Car Settings (`packages/apps/Car/Settings`) | No. `sharedUserId="android.uid.system"`. | Apache 2.0 | The page list and order. Design only. |
| CarService / VHAL | No. System service, `android.car.*` permissions, HAL on the vehicle side. | Apache 2.0 | Nothing. Our `VehicleBridge` is already the equivalent. |
| UX restrictions (`CarUxRestrictionsManager`) | No. It lives in CarService. | Apache 2.0 | The three-state model and the "DO" rule. |

Licence note. All of these are Apache 2.0. Apache 2.0 code may be included in a GPL-3.0 work (one-way compatible).
So reading and even copying is legal if we keep the notices. We still copy nothing: the code depends on Views, Car
APIs and system privileges. Layout numbers and ideas are not copyrightable code.

## Why each is out of reach

- **CarLauncher.** It embeds a maps activity in a task view and talks to `CarService`. Those need system permissions
  and platform hidden APIs. A normal app gets none of them. Build our own Slint grid (E2.S2 already does).
- **Car UI library.** It is a View library. Slint has no Views. Embedding it means a second UI toolkit in a
  one-window Slint process. Plan fact: Slint on Android has one window. No.
- **Car App Library.** The app only describes models. The host turns them into views. Hosts are Android Auto
  (phone) and AAOS (system app). Google's docs say so ("the host is installed as a system app" on AAOS).
  Android Auto's host also gates apps by category and Play listing. No documented way to supply a third-party host,
  and writing one means implementing the client protocol ourselves with no spec. On this head unit there is no
  host, so a templated app would show nothing. E7 is the correct route for AA: a separate receiver app.
- **Media centre.** It is a privileged client (`MEDIA_CONTENT_CONTROL`). We cannot see other apps' sessions through
  that permission. Alternative below.
- **Car Settings.** System UID app built on the preference framework.
- **CarService / VHAL.** CarService is a privileged platform service. VHAL is the vehicle abstraction below it.
  Our scooter has neither. Our CAN data reaches us through the vendor interface (`VehicleBridge`). Adding
  `android.car` would only add a fake layer.

## Borrow as design

**Cockpit theme card home (E4.S4).**
- Home is a row of large cards, not an app grid. AAOS CarLauncher home cards: navigation (largest), media, assistant.
  Our set: navigation or trip, media, vehicle (battery, range, temperature), plugin widgets.
- One card, one job, one primary action. Tap target the whole card.
- Card sizes from one grid; the first card is about double width. At 1280x768: three cards across with 24 px gaps,
  card min height 360 px. Use `host-ui-tokens.md` radius 20, `surface`, `line` border.
- Cards show state, not controls. Controls (play, pause) are 64 px minimum (token rule 6).
- Calm mode idea: a low-information home when nothing needs attention. Matches our "one fact per screen" rule.
- Plugin widgets get a fixed card size and the same stale/unknown rules (guarantee 3). A widget cannot be taller than a card.

**Launcher (E2.S2).**
- Keep home and "all apps" separate. AAOS does this too. The dock holds favourites; the grid holds the rest.
  Already in E2.S2 (5 columns, favourites dock).
- Alphabetical, no folders, no drag-and-drop. AAOS has none while driving; we have none ever.
- Hide system and vendor packages by default (AAOS has an app-block list; ours is E2.S2.T2).
- Recent apps row: optional, last three launched. Cheap with the usage-stats grant we already need.

**Settings IA (host Settings, E1).**
- Car Settings homepage order (`res/xml/homepage_fragment.xml`): Bluetooth, Network and internet, Notifications,
  Sound, Display, Profiles and accounts, Location, Privacy, Accessibility, Security, Apps, Assistant, System.
- Pattern: two panes, left list, right detail, one level deep. Matches our rail plus pane.
- Take: Display (brightness, night mode), Sound, Apps (launcher visibility), Security (lock), System (about, recovery).
- Drop: accounts, location, assistant. We never sign in (guarantee 7).
- Each row: label, one-line state, chevron. Switches live in the row, not on a second page.

**Distraction rules (our parked gate, guarantees 4 and 5).**
- AAOS default states (source.android.com car_uxr): Parked = no restrictions; Idling (not in Park, speed 0) = no video,
  no config, and only distraction-optimised (DO) activities; Moving = fully restricted, DO only.
- Take the model: restrictions are a function of one driving state, defined in one place. Ours is `TrunkGate`.
- Take the DO tag: every host screen declares if it is allowed while not parked. Default is "no". Only the strip,
  alerts, lock and the theme are DO. A new screen must opt in, not opt out.
- Our gate is stricter than AAOS: AAOS allows DO apps while moving. We allow none. Keep it: "idling" is not parked.
- Take the content limits idea (max string length, max items, max depth; `CarUxRestrictionsConfiguration`) for
  anything shown while riding: plugin widgets and Cockpit cards. Suggested start: card text at most 24 characters,
  no scrolling lists, no keyboard.
- Car App Library step limit: at most five templates per task. As a rule for our flows: no host flow deeper than
  five screens from home. Launcher to app is two.
- On parked to not parked: close interactive screens. Same as AAOS blocking non-DO activities. Already guarantee 5.

**Rotary / D-pad focus (handlebar buttons story).**
- AAOS rotary model (source.android.com `rotary_controller`): the screen is split into `FocusArea`s (rectangular
  regions). Nudge (four directions) moves between areas. Rotate moves between items inside an area, in Tab order.
  Centre press acts. Back works as usual. Nudging off the screen edge can trigger Back.
- Map to our D-pad (up, down, left, right, press; no Back on the panel):
  - Areas = rail, pane, dock. Left/right moves between areas, up/down moves inside one.
  - Remember last focus per area (nudge history) so left then right returns.
  - Press acts. A long press or left-from-the-rail-edge = Back/close (the panel has no Back key).
  - First press after a touch only shows focus, it does not act (AAOS ignores the first action after touch).
  - Always show one visible focus: the thick sunny pill (token rule 4). Never an unfocused state while a
    screen is open. AAOS parks focus in an invisible `FocusParkingView`; we simply keep the first item focused.
  - Sliders: press enters "adjust", up/down changes, press or left exits (direct manipulation mode).
- Implementation is plain Slint `FocusScope` with host-owned focus order. Nothing to import.

**Media card pattern (Cockpit, E2).**
- AAOS media centre: a `MediaBrowser` client connects to a `MediaBrowserService`, browses a tree
  (browsable and playable flags), and shows a `MediaSession`. Source: developer.android.com/training/cars/media.
- App-level equivalent on Android 10 without the privileged permission: read the notification media session.
  That means a `NotificationListenerService` with the owner's grant, then
  `MediaSessionManager.getActiveSessions(componentName)`. Gives title, artist, art, play state, and transport
  controls. It does not give browsing. Browse only if we connect `MediaBrowser` to one chosen app's exported service
  (many music apps export it for Android Auto). Offer that as an opt-in later. Not needed for the card.
- Needs the owner to grant "notification access". That is an ordinary user setting, not a system privilege.

## Out of reach

- CarLauncher, Car Settings, Media app as code: system UID or signature/privileged permissions.
- CarService, VHAL, `android.car.*`: platform services that do not exist on this head unit.
- Car App Library templates: need a host app that is a Google system component. No supported third-party host.
- Car UI library and rotary lib as code: Views, wrong toolkit.
- `CarUxRestrictionsManager` as an API: lives in CarService. We keep our own `TrunkGate`.
- Driving-state detection from AAOS signals (gear, speed): we have `parked` from the scooter's own data.

## Decisions for the plan

- Treat AAOS as a design reference only. No AOSP code, no Car libraries, no `androidx.car.app` in the host or themes.
  If any text or numbers are copied later, keep the Apache 2.0 notice and list it in the third-party notices.
- E4.S4 Cockpit: three cards across (trip/navigation, media, vehicle) plus a plugin row. Cards show state only.
  Media card reads the active session through notification access (opt-in, owner grants it). No `MediaBrowser`
  browsing in 1.0.
- E2.S2 launcher: keep the plan as written (home and grid separate, dock, hidden vendor apps). Add an optional
  recent-apps row (last three), cheap with the usage-stats grant.
- Distraction rules: add a "DO tag" convention to host screens (default not allowed unless parked; only strip,
  alerts, lock and theme are allowed riding). Content limits for plugin widgets: short text, no scroll, no input.
- Handlebar navigation story: adopt the FocusArea model (rail, pane, dock), per-area focus memory, first press after
  touch only shows focus, long press = Back. One visible focus at all times.
- Revisit only if the head unit turns out to ship an AAOS host: check once on the scooter with
  `pm list packages | grep -i car` (expected: nothing). If a host exists, a templated app becomes possible; until
  then, no.

## Sources

- Car App Library overview: https://developer.android.com/training/cars/apps
- Glossary (host definition): https://developer.android.com/training/cars/apps/library/glossary-concepts
- Template restrictions (five templates): https://developer.android.com/training/cars/apps/library/template-restrictions
- Template overview: https://developer.android.com/design/ui/cars/guides/templates/overview
- Car media apps: https://developer.android.com/training/cars/media
- Driver distraction guidelines (DO tag): https://source.android.com/docs/automotive/driver_distraction/guidelines
- UX restrictions states: https://source.android.com/docs/automotive/driver_distraction/car_uxr
- Rotary controller: https://source.android.com/docs/automotive/hmi/rotary_controller
- Car UI library overview: https://source.android.com/docs/automotive/hmi/car_ui
- CarLauncher: https://android.googlesource.com/platform/packages/apps/Car/Launcher/ (manifest permissions, Apache 2.0 header)
- Car Settings: https://android.googlesource.com/platform/packages/apps/Car/Settings/ (`sharedUserId`, `res/xml/homepage_fragment.xml`)
- Car Media: https://android.googlesource.com/platform/packages/apps/Car/Media/
- car-ui-lib, car-rotary-lib: https://android.googlesource.com/platform/packages/apps/Car/libs/

Not verified from a primary source: the exact car-ui-lib licence file text (assumed Apache 2.0 like the rest of AOSP),
`androidx.car.app` minSdk (believed 23), and whether Android Auto bars third-party hosts in writing (no document
describes a host SPI; absence, not a prohibition).
