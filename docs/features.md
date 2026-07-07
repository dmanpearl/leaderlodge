# LeaderLodge Features

LeaderLodge is a mobile-friendly web application for tracking scores, rankings,
and leaderboards for social games played by groups of people.

---

## Game Recording

- Record scores for 5 supported game types: Dominos, Backgammon, Progressive
  Rummy, Mah Jongg, and Pickleball
- Easy to add additional game types and scoring rules
- Games support Users, Players (roster members), or Teams
- Fuzzy auto-complete for player name entry
- Location tracking with fuzzy auto-complete and "last location used"
  pre-population
- Reuse previous game's player roster with one click
- Support for 2x (double) and 0.5x (half) game weighting
- Automatic score-to-result and placement assignment based on game-type rules
- Notes field per game
- Dynamic team compositions (up to 2 players per team)
- Pickleball: traditional or rally scoring modes

## Game Editing and Auditing

- Users can edit their own games; staff can edit any game
- Score change logs capture old and new snapshots with editor and timestamp
- Change history visible in admin

## Game History Import

- Import from Excel ScoreKeeper workbooks (.xlsx)
- Idempotent: re-importing skips already-imported rows
- Automated player name matching (username, first name, display name)
- Automatic guest player creation for unmatched names
- Dry-run mode to validate without writing

## Leaderboards and Rankings

- Per-game-type leaderboards scoped to each group
- Rank score formula: field-weighted finish placement points accounting for
  player count, placement distance, game weight, and score magnitude
- Vesting system: ranks stabilize after a minimum number of games played,
  damping early outlier performance
- Filtering by period: all time, by year, or by specific month
- Top-5 preview cards on the dashboard
- Rank detail page showing a full breakdown (wins, losses, ties, points,
  games played)

## Hall of Fame

- Period-based rankings showing yearly or monthly trends
- Granularity selector (year or month)
- AI-powered insights on hall-of-fame winners

## Matchup View

- Head-to-head comparison of 2 or more players in the same group and game type
- Game-by-game results filtered to shared games
- Computed rankings for matched players
- Accessible from the game list, game detail, or leaderboard
- AI insights on matchup dynamics

## Groups and Membership

- Create and manage groups with descriptions
- Membership roles: Owner, Editor, Member
- Public demo mode (read-only) or private group visibility
- Bulk roster view with active/inactive status
- Hide individual players from game stats
- Team support: pairs of players appear as a combined roster entry with
  individual leaderboard credit still applied

## Invitations

- Email-based group invites with expiration
- Share links for roster-building without email
- Invite token tracking and revocation
- Acceptance confirmation email

## Accounts and Authentication

- User signup with email verification
- Email or username login
- Password reset flow with email confirmation
- Email re-verification on address change
- Welcome email on signup
- CSRF token auto-refresh when a browser tab wakes from sleep

## User Preferences

- Per-user UI settings stored as JSON (persistent across sessions):
  - Last game type viewed
  - Last group viewed
  - AI model preference
  - Insights panel preferences
- Settings reset option in the user profile

## AI Insights

### Contextual Insights (page-bound)

- Available on Player Rank Detail, Leaderboard, Hall of Fame, Matchup, and
  Game Detail pages
- Preset questions (e.g., Strengths, Weaknesses, Standouts, Dynamics) or
  custom free-form questions
- Markdown-formatted responses with regenerate option
- "Show data sent to AI" debug toggle

### Ask the Lodge (tool-calling interface)

- Free-form natural language queries at `/insights/ask/`
- Multi-round tool calling (up to 5 rounds) against structured game data
- Available tools: leaderboard query, placement leaders, month leaders, rank
  trends, player detail, head-to-head, hall of fame, loss leaders, player
  comparison, date-range leaderboard, location leaderboard, and more
- Scoped to group, game type, and optional period

### AI Model Options (owner-paid API)

- GPT-4o mini (OpenAI, default)
- Gemini 2.5 Flash (Google)
- Gemini 2.5 Flash-Lite (Google, lightweight)
- Model selection stored per user

### Rate Limiting

- Tiered daily caps by user type (anonymous, authenticated, staff)
- Per-model and global daily limits
- Per-user overrides configurable by admin

### Insight Logging

- All AI interactions logged: source, question, model, token usage, tools used,
  success/failure, regeneration chain
- Audit trail visible in admin

## Feedback and Bug Tracking

- Feedback form accessible from the account menu (guests see a login prompt)
- Feedback types: Bug, Feature, Suggestion, Question, Comment
- Game-type scoping per submission
- Title, description, and priority
- Admin triage workflow: New, Open, In Progress, Resolved, Closed, Won't Fix
- Priority levels: Low, Normal, High, Urgent
- Staff assignment, internal notes, public visibility toggle, approval flag
- Read and response timestamps for admin tracking
- Confirmation email to submitter; admin notification email on new submissions

## Fuzzy Search

- Fuzzy player/user/guest name auto-complete on game recording forms
- Fuzzy location name auto-complete on game recording forms
- Substring matching for locations and players

## Admin Interface

- SiteSettings singleton: per-event email notification toggles (signup, invite
  sent, invite accepted, game change, feedback) and destination address
- Admin panels for games, score change logs, groups, players, teams, locations,
  invites, memberships, feedback, and insight logs
- UserProfile admin with email verification tracking, UI settings, and
  per-model AI rate limit overrides

## Demo Mode

- Public read-only demo group with seeded data for all 5 game types
- Anonymous users can browse without logging in
- Setup command: `python manage.py setup_demo`

## Mobile and Responsive Design

- Mobile-first responsive layout (Bootstrap-based)
- Collapsible filter panels
- Touch-friendly tap targets
- Native selects on mobile for dropdowns
- Compact date and score formatting
- Header row repeated at bottom of long tables for easy scrolling

## Email and Notifications

- Transactional email via Brevo HTTPS API in production
- Console email in development
- Emails: welcome, email verification, password reset, invite acceptance, group
  invite, feedback confirmation, admin alerts

## Deployment and Infrastructure

- Django 5.0+ on Railway (auto-deploy from `dev` branch)
- PostgreSQL in production, SQLite in development
- WhiteNoise for static file serving (no CDN required)
- Environment-variable-driven configuration for secrets, timezone, email, AI
  API keys, and demo mode toggle
