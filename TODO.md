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

## Open Items

- [ ] Demo mode: Use new demo-seed Excel files with representative player names. Use group 'Demo'. May need seed command for demo group. The demo-seed files are based on the manpearl seed files.
- [ ] Game selection persistent storage. Use setting per logged in user. Add reset settings option.
- [ ] Ranking and other player data need sort by columns
- [ ] Database settings: Move hardcoded MIN_GAMES_FOR_LEADERBOARD into configurable settings
- [ ] When user begins the Record Game process, implement an optional way to use same participants as the previous game.
- [ ] Group members: Replace all-users dropdown with a secure, private, scalable invite method (email/link, not a public account picker)
- [ ] Mobile Game list must fit entire table for 2 player games. Ellipsize location
- [ ] Bug: Domino stats do not match seed spreadsheet. Trace and resolve.
- [ ] Stats view: Spin-up/Spin-down control is wrong. Should be down/right, not down/up.
- [ ] Bug: Record Game wrong date - At 10:12pm default date shows tomorrow's date
- [ ] Game detail view (maybe)
- [ ] Calculate leaderboards
- [ ] Filter leaderboards (month, game)
- [ ] Merge similar locations tool
- [ ] Persistent UI selection storage
