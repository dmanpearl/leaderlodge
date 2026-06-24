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
- [x] Matchup View: Create new screen to compares a list of players head-to-head in their group for a given game-type. Navigate directly to the matchup screen after saving a game.

## Open Items

- [ ] Matchup View: How to access?
- [ ] Matchup View: Manage/change/select players for comparrison
- [ ] Leaderboard graphs of leaders over time
- [ ] User Account: Add ability for users to create accounts, email and/or phone options, 2FA options
- [ ] User Account: Lost password recovery
- [ ] Record Game > "Recording For" label: The 3 text items for <group>, <game-type>, and <date> should be links/buttons to allow each of those items to be changed. Avoid word-wrap for each of these items (date seems to wrap often in mobile). Place an icon next to each item. Also remove the label "Recording for"
- [ ] Bug: Demo group description is unnecessarily truncated/elipsized despite enough room for more text. Implement wrapping. Example: "Test group with example game data. Login and use '+ Create Group' … "
- [ ] Mobile Native Controls: Explore controls that can be converted to native as we did for the Player and Location drop-downs.
- [ ] If we are happy with points * place, remove 'FINISH_POINTS_EXPONENT' (give it some time)
- [ ] Game Stats and Game List: Provide capability to selectively hide group players via a list of 'hidden' attributes
- [ ] Games and Groups: Explore moving selection UI into a global settings area since they stay persistent for all screens
- [ ] Ranking and other player data need sort by columns
- [ ] Database settings: Move hardcoded MIN_GAMES_FOR_LEADERBOARD into configurable settings
- [ ] Group members: Replace all-users dropdown with a secure, private, scalable invite method (email/link, not a public account picker)
- [ ] Mobile Game list must fit entire table for 2 player games. Ellipsize location
- [ ] Bug: Domino stats do not match seed spreadsheet. Trace and resolve.
- [ ] Game detail view (maybe)
- [ ] Merge similar locations tool
