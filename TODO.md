# TODO

## Completed Items

- [x] 690a1ef Game list view filtering
- [x] 4912efd Game list view shows player scores
- [x] b8698c6 Seed Progressive Rummy
- [x] 40f7f2e Promote to leaderlodge.com on Railway
- [x] 40e0409 Game list view: Put header row at the bottom too
- [x] 40e0409 Game list view filter: When a location is selected, omit the 'Location' column.
- [x] 40e0409 Game list view shows stats summary for filtering selection
- [x] 0b7c505 Game list stats table: highlight winners, losers, and ties
- [x] 016a9f3 Game stats view: Remove thick bar to the left of 'All' gray highlight is enough
- [x] 889c970 Login UI: If user is not logged in, show a Login button with a unicode user icon. If user is logged in, make the username a drop-down menu with options: System Admin and Logout (more options will be added later)
- [x] 2aacef7 In the Record Game form, don’t show all names, instead make user choose from a fuzzy predictive drop-down list of Users and Guests from auto-completion or add a new Guest if the user types in a unique new name.
- [x] 5795da3 Game Stats: For two person games, the "Ties" row is not necessary to have entries for both players, as the will always be equivalent. Add a mechanism for merging adjacent cells and displaying a single tie count for the pair of players.
- [x] 5795da3 Game Stats: Need first date, last date, and date range. Range in humanize formatting. Use cell merge as necessary from the Game Stat Ties todo item.
- [x] 3be4f0c Game list view: Move 2x and 1/2 into their own column so they can be retained when filtering on game type.
- [x] 92f7a5b Games View: Never display different kinds of games together in the games list. There is always exactly one type. Remove the 'All Games' option.
- [x] 4cd7e8b Leaderboard: Add rank column and order the list by rank. Initial rank formula: r=sum(nummber-of-players-in-each-game-you-won)/number-of-games-you-played
- [x] 467e060 Leaderboard rank score uses field-weighted finish placement points.
- [x] 6d4e2ec Rank detail view shows how a player's rank was calculated for a particular view.
- [x] 71d081d Dashboard view: Show leaderboard cards for each sport
- [x] e16e281 Game list view filter by player (shows only games that player was in)
- [x] fd3b9e3 Game Stats: Implement a way to hide undesirable Guest/Players
- [x] f4e5de0 Bug: Record Game wrong date - At 10:12pm default date shows tomorrow's date
- [x] 08a0075 Demo mode: Public read-only Demo group with demo seed spreadsheets for all game types
- [x] a2f9848 Game selection persistent storage or central location affecting all views. Use setting per logged in user. Add reset settings option. When user selects Record Game or Leaderboard, the current game type is maintained.
- [x] 5c0653f Mah Jongg: Wall Game (aka Tie with all zeros): Verify Leaderboard behavior
- [x] 6cfcec0 Tests (pytest): Make another pass at optimizing and speeding up tests. Remove redundant and unnecessary tests. Look for shared setup opportunities
- [x] 99bf8ae Rank Algorithm (Progressive Rummy): Unvested dampening via vesting^2 (not divide).
      Descending sort like other game types. Half-game rank penalty deferred.
      Zach: raw 4.0 x 0.518^2 = ~1.07, rank ~13 on manpearl (beats one-game losers).
- [x] 0f549ae Rank Algorithm: Finish credit = placement x score magnitude (linear, no ^1.5).
      High-wins use raw score; PR winners use reference minus score; other PR
      finishers use field max minus score. Score strength removed.
- [x] dc93a1e Record Game: Location field: type-ahead doesn't allow sub-text of a saved location. Example: Doesn't allow 'Preston' if 'Preston - Passover' already exists.
- [x] 1ef6ab1 Record Game: Default initial values to zero, so user doesn't have to enter a score if the player scored zero. However, do not do this for games like Progressive Rummy where lowest score wins.
- [x] 7be3a97 Bug: Mobile: Option menus for Player or Location are too high. Anchor suggestion lists to the field and flip within the viewport so typing + keyboard still work.
- [x] 3383e25 Guest Mode: Must showcase Groups and +Add pages even though access is meaningless.
- [x] 61619da Home page title: use "LeaderLodge" only (drop "Dashboard") so mobile URL/history previews show the brand name.
- [x] e75fda5 Record Game: Add an option to use the same players from the previous game of the same game-type.
- [x] fe3de40 Record Game: Make the add player name field more prominent so the user knows what to enter next.
- [x] 207772c Navbar Mobile: Instead of drop-down menu of items, display Games, Leaders, Groups, and Add as icons only for limited width environments
- [x] db9edd3 Record Game view: "Type player name" and "Save" buttons should be vertically justified. Instead, "Save" is too high. It is vertically top justified with the "Add Players" label. This is only a desktop issue. Mobile stacks the buttons, so non-issue
- [x] 4c63ee3 Stats view: Spin-up/Spin-down control is wrong. Should be down/right, not down/up.
- [x] fe6126e Filter leaderboards by year and month
- [x] 5914a36 CSRF: Auto-refresh stale form tokens when a tab or phone wakes from sleep (visibility/bfcache fetch to `/accounts/api/csrf-token/`); extend session and CSRF cookie lifetimes
- [x] af74338 Bug: Games View: Menu item 'Dominos' truncated off part of trailing 's' by the spindown char, move the chevron icon to the right
- [x] ddbfa18 Matchup View: Create new screen to compares a list of players head-to-head in their group for a given game-type. Navigate directly to the matchup screen after saving a game.
- [x] ded329e Matchup View: Game list - click a game row to open matchup for that game's players
- [x] 7ba260e Matchup View: Game detail - Matchup button in footer (Games / Leaderboard / Matchup)
- [x] 61f17e9 User Account: Self-service signup, login, password reset, welcome email, email verification
- [x] 18f0d62 Groups: Owner/Editor/Member roles with member management (remove member, assign roles; editors cannot modify owners)
- [x] 618eca8 Dashboard welcome uses display-name rules (e.g. "Welcome, David" not username)
- [x] ad419e3 Tables use compact text and n/j/y dates (Dashboard, Groups, Game list, Group detail)
- [x] ad419e3 User Account: Group email invites with guest roster, join-page signup, and member/player removal rules (618eca8, 98e61c2, 0ec9266)
- [x] b61a500 Profile view: Account menu profile page with user information (Navbar > Account > Profile)
- [x] 909a7dc Groups View: Make entire row a link to the Group detail view, so the hyperlink style group name can be normal
- [x] b3c9af0 Record Game View > Points fields: When the user types a digit into the field populated with a leading zero, the new digit replaces the zero
- [x] db89c5e Dashboard: Click on a Recent Game row navigates to Game Detail view (currently date is a link, entire row instead; remove underline link format from date)
- [x] 1b26602 Dashboard: Recent Games: Move Group column to the right of Winner
- [x] b540e80 After creating a new Group and navigating to 'View all', the new Group should be selected, but the last saved persistent group is displayed instead
- [x] b4f1812 Record Game View > Mobile Undo Zoom after score entry: iOS automatically zooms in for typing in score values. Clicking out of the field dismisses the keyboard, but does not restore the original zoom factor
- [x] cb01060 Mobile: Games list filters — collapse Group, Player, Location, and Date behind a 'Filter' spin-down (same pattern as Stats)
- [x] 336ebed Hall of Fame view
- [x] 10df048 Navbar: Selected item should be visibly highlighted
- [x] bd71ee7 AI rate limits: defaults + settings + per-user ui_settings + cache counters
- [x] dcff5f8 AI Player Insights on rank detail (see [docs/ai-insights.md](docs/ai-insights.md))
- [x] d9a69ac AI Group / Hall of Fame trend analysis
- [x] fa3d96f AI Matchup insights on matchup view (see [docs/ai-insights.md](docs/ai-insights.md))
- [x] 43c2453 AI Game detail insights (shared game-set context with precomputed rankings)
- [x] 9415913 Insights: Show progress indicator after Generate triggered so user does not think the system is hung
- [x] 9415913 Insights: Remove 'Generate' button. When user selects a non-'Ask' option, auto-force Generate immediately (ie Dynamics, Head to Head, This Game, Strengths, Struggles, Superpower). Also invoke Generate progress indicataor. For 'Ask', add Generate on Enter and add Action button to the right of the question text field
- [x] e4f2e88 Games View > Filters and Leaderboards > Filters: Add Filter by number of players (Game Size). Filter menu options include: All, 2, 3, 4, etc (show numbers actually represented in current set)

## Open Items

- [ ] AI Ask the Lodge (natural-language queries + tool calling)
- [ ] Add recent_updates.yaml list and behavior aka rating-ranch
- [ ] Matchup View: Pick or change players for ad-hoc comparison (`?group=&game_type_code=&players=`; optional `&game=` to anchor before/after deltas; picker UI)
- [ ] Matchup View: Entry points from stats panel and leaderboard (after player picker)
- [ ] Offline mode: Allow game entry in limited connection environments
- [ ] Leaderboard graphs of leaders over time
- [ ] User Account: 2FA and phone login options
- [ ] Record Game > "Recording For" label: The 3 text items for <group>, <game-type>, and <date> should be links/buttons to allow each of those items to be changed. Avoid word-wrap for each of these items (date seems to wrap often in mobile). Place an icon next to each item. Also remove the label "Recording for"
- [ ] Bug: Demo group description is unnecessarily truncated/elipsized despite enough room for more text. Implement wrapping. Example: "Test group with example game data. Login and use '+ Create Group' … "
- [ ] Mobile: Record Game player picker — on viewports ≤767px, replace fuzzy combobox (`static/js/player_picker.js`, `templates/games/game_form.html` `#player-picker-input`) with native `<select>` of roster players (from `data-player-picker` JSON roster) plus an "Add new guest…" option that reveals a plain text input. Keep desktop combobox unchanged. Reuse `appendParticipantRow` logic; ensure new rows still work with `game_record_form.js` score preview. Match existing guest vs linked-player behavior in `player_picker.js`.
- [ ] Mobile: Record Game location — on viewports ≤767px, replace fuzzy combobox (`static/js/location_autocomplete.js`, `GameRecordForm.location_name` in `leaderlodge/games/forms.py`) with native `<select>` of group locations (fetch via `groups:locations` JSON or server-rendered options) plus "Other…" revealing a text field for new locations. Keep desktop fuzzy autocomplete (sub-string match per `dc93a1e`). Setup form is `templates/games/game_form.html` when `show_roster` is false.
- [ ] Mobile: Record Game roster header — replace static "Recording for" card (`templates/games/game_form.html` when `show_roster`) with inline native controls: Group `<select>`, Game `<select>`, Date `<input type="date">`, optional Location (select/datalist per location mobile item). Remove "Recording for" label; use icons + nowrap chips; submit to change context without returning to setup step. Extends open item "Recording For" links/buttons UX. Preserve hidden fields / POST shape expected by `game_create` save action in `leaderlodge/games/views.py`.
- [ ] Mobile: Games list game-type title — `templates/games/game_list.html` `#filter-game-type` uses `appearance: none` and custom chevron (`static/css/games.css` `.game-list-title-select`). On mobile, restore native `<select>` appearance (full-width, platform picker) or move game type into the filter card. Do not break `game_list.js` title width measurement on desktop.
- [ ] Mobile: Leaderboard and group roster period — replace separate Year/Month `<select>`s (`templates/includes/leaderboard_period_filters.html`, used on `leaderboard.html` and `group_detail.html` roster) with `<input type="month">` when a specific month is needed, plus "All years" / clear option. Wire to existing `year`/`month` GET params and period logic in leaderboard views.
- [ ] Mobile: Group roster row actions — replace Bootstrap dropdown (`templates/groups/includes/roster_player_actions.html`, "Invite with email", "Remove from Group") with inline icon buttons or a native `<select>` action menu on ≤767px. Avoid dropdown scroll clipping and small hit targets. Keep desktop dropdown if preferred.
- [ ] Mobile: Group roster invite — replace Bootstrap modal (`#roster-invite-modal` in `templates/groups/group_detail.html`) with inline expandable form below the row or a dedicated page on mobile. Email field should stay `type="email"` in normal document flow (keyboard-safe). Preserve POST to `groups:player_invite`.
- [ ] Mobile: Group members role select — inline `form-select-sm` role dropdown in members table (`templates/groups/group_detail.html`) needs ≥44px tap targets on mobile; consider row action sheet or full-width select below username. POST to `groups:member_update_role` unchanged.
- [ ] If we are happy with points * place, remove 'FINISH_POINTS_EXPONENT' (give it some time)
- [ ] Game Stats and Game List: Provide capability to selectively hide group players via a list of 'hidden' attributes
- [ ] Games and Groups: Explore moving selection UI into a global settings area since they stay persistent for all screens
- [ ] Ranking and other player data need sort by columns
- [ ] Database settings: Move hardcoded MIN_GAMES_FOR_LEADERBOARD into configurable settings
- [ ] Mobile Game list must fit entire table for 2 player games. Ellipsize location
- [ ] Bug: Domino stats do not match seed spreadsheet. Trace and resolve.
- [ ] Merge similar locations tool
- [ ] Add About Box and contact us form.
- [ ] iOS: Build native mobile app for iPhone and iPad
- [ ] Android: Build native mobile app for Android
- [ ] Delete Group: Make a UI for deleting group, warn user about deleting x number of games, access from Groups View, Group Detail View, and/or Group Edit
