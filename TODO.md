# TODO

## Completed Items

- [x] Game list view filtering
- [x] Game list view shows player scores
- [x] Seed Progressive Rummy
- [x] Promote to leaderlodge.com on Railway
- [x] Game list view: Put header row at the bottom too
- [x] Game list view filter: When a location is selected, omit the 'Location' column.
- [x] Game list view shows stats summary for filtering selection
- [x] Game list stats table: highlight winners, losers, and ties
- [x] Game stats view: Remove thick bar to the left of 'All' gray highlight is enough
- [x] Login UI: If user is not logged in, show a Login button with a unicode user icon. If user is logged in, make the username a drop-down menu with options: System Admin and Logout (more options will be added later)
- [x] In the Record Game form, don’t show all names, instead make user choose from a fuzzy predictive drop-down list of Users and Guests from auto-completion or add a new Guest if the user types in a unique new name.
- [x] Game Stats: For two person games, the "Ties" row is not necessary to have entries for both players, as the will always be equivalent. Add a mechanism for merging adjacent cells and displaying a single tie count for the pair of players.
- [x] Game Stats: Need first date, last date, and date range. Range in humanize formatting. Use cell merge as necessary from the Game Stat Ties todo item.
- [x] Game list view: Move 2x and 1/2 into their own column so they can be retained when filtering on game type.
- [x] Games View: Never display different kinds of games together in the games list. There is always exactly one type. Remove the 'All Games' option.
- [x] Leaderboard: Add rank column and order the list by rank. Initial rank formula: r=sum(nummber-of-players-in-each-game-you-won)/number-of-games-you-played
- [x] Leaderboard rank score uses field-weighted finish placement points.
- [x] Rank detail view shows how a player's rank was calculated for a particular view.
- [x] Dashboard view: Show leaderboard cards for each sport
- [x] Game list view filter by player (shows only games that player was in)
- [x] Game Stats: Implement a way to hide undesirable Guest/Players
- [x] Bug: Record Game wrong date - At 10:12pm default date shows tomorrow's date
- [x] Demo mode: Public read-only Demo group with demo seed spreadsheets for all game types
- [x] Game selection persistent storage or central location affecting all views. Use setting per logged in user. Add reset settings option. When user selects Record Game or Leaderboard, the current game type is maintained.
- [x] Mah Jongg: Wall Game (aka Tie with all zeros): Verify Leaderboard behavior
- [x] Tests (pytest): Make another pass at optimizing and speeding up tests. Remove redundant and unnecessary tests. Look for shared setup opportunities
- [x] Rank Algorithm (Progressive Rummy): Unvested dampening via vesting^2 (not divide).
      Descending sort like other game types. Half-game rank penalty deferred.
      Zach: raw 4.0 x 0.518^2 = ~1.07, rank ~13 on manpearl (beats one-game losers).
- [x] Rank Algorithm: Finish credit = placement x score magnitude (linear, no ^1.5).
      High-wins use raw score; PR winners use reference minus score; other PR
      finishers use field max minus score. Score strength removed.
- [x] Record Game: Location field: type-ahead doesn't allow sub-text of a saved location. Example: Doesn't allow 'Preston' if 'Preston - Passover' already exists.
- [x] Record Game: Default initial values to zero, so user doesn't have to enter a score if the player scored zero. However, do not do this for games like Progressive Rummy where lowest score wins.
- [x] Bug: Mobile: Option menus for Player or Location are too high. Anchor suggestion lists to the field and flip within the viewport so typing + keyboard still work.
- [x] Guest Mode: Must showcase Groups and +Add pages even though access is meaningless.
- [x] Home page title: use "LeaderLodge" only (drop "Dashboard") so mobile URL/history previews show the brand name.
- [x] Record Game: Add an option to use the same players from the previous game of the same game-type.
- [x] Record Game: Make the add player name field more prominent so the user knows what to enter next.

## Open Items

- [ ] Navbar Mobile: Instead of drop-down menu of items, display Games, Leaders, Groups, and Add as icons only for limited width environments
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
- [ ] Stats view: Spin-up/Spin-down control is wrong. Should be down/right, not down/up.
- [ ] Game detail view (maybe)
- [ ] Calculate leaderboards
- [ ] Filter leaderboards (month, game)
- [ ] Merge similar locations tool
