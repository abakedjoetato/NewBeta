# Tower of Temptation PvP Statistics Bot - New Features

This document outlines the three new features that have been added to the Tower of Temptation PvP Statistics Bot: Factions, Rivalries, and Player Linking.

## 1. Factions System

The Factions system allows players to organize into groups with customizable colors, tags, and descriptions. Faction leaders can manage membership and view faction-specific statistics.

### Commands

- `/faction create <name> <tag> <color>` - Create a new faction
- `/faction join <faction_name>` - Join an existing faction
- `/faction leave` - Leave your current faction
- `/faction info [faction_name]` - View information about a faction
- `/faction list` - View all factions on the server
- `/faction stats [faction_name]` - View faction statistics
- `/faction manage members <add/remove> <player_name>` - Manage faction members (leader only)
- `/faction manage settings <setting> <value>` - Adjust faction settings (leader only)
- `/faction leaderboard` - View faction leaderboards

### Features

- Faction-specific colors for embeds
- Customizable faction tags displayed next to player names
- Faction statistics tracked separately from individual statistics
- Faction vs. faction kill tracking
- Faction territory control metrics
- Automatic notifications for faction achievements

## 2. Prey/Nemesis Rivalry System

The Prey/Nemesis system automatically tracks natural rivalries between players by identifying each player's most frequent target (Prey) and most frequent killer (Nemesis).

### Implementation

Rather than using command-based rivalries, the system works automatically in the background:

- An hourly background task updates each player's Prey and Nemesis relationships
- A player's "Prey" is the player they've killed the most
- A player's "Nemesis" is the player who has killed them the most
- Minimum threshold of 3 kills required to establish a Prey or Nemesis relationship
- Data is displayed directly in player stats embeds with 🎯 Prey and ☠️ Nemesis icons
- Resource-efficient hourly updates instead of real-time processing

### Features

- Automatic tracking without player input required
- Natural rivalry detection based on actual gameplay
- Server-specific rivalries for multi-server support
- Hourly updates to balance accuracy and performance
- Integrated directly into player statistics display
- Fallback to legacy victim/killer tracking when hourly data isn't available yet

## 3. Player Linking System

The Player Linking system allows Discord users to link their accounts to in-game player accounts for seamless integration.

### Commands

- `/link player <player_name>` - Link your Discord account to an in-game player
- `/link remove <player_name>` - Remove a link between your Discord account and a player
- `/link list` - List all player accounts linked to your Discord account
- `/link info <discord_user>` - View information about linked accounts for a Discord user

### Features

- Discord users can access their in-game statistics directly
- Receive Discord notifications for in-game events related to linked accounts
- Verify player identity for faction management
- Link multiple accounts if needed (for alt characters)
- Integration with permission systems for faction commands
- Automated role assignment based on in-game achievements

## Integration Points

These three features integrate with each other and the core bot functionality:

1. **Factions + Rivalries**: Faction-wide rivalries can be tracked, and rival factions receive special highlight in embeds.

2. **Factions + Player Linking**: Faction management is simplified through player linking, allowing Discord role integration.

3. **Rivalries + Player Linking**: Discord users receive notifications about rivalry events through their linked accounts.

4. **All Features + Core Bot**: All three new features leverage the existing kill tracking and statistics systems.

## Technical Implementation

These features are implemented as modular components:

- New database models in `models/faction.py`, `models/rivalry.py`, and `models/player_link.py`
- New command cogs in `cogs/factions.py`, `cogs/rivalries.py`, and `cogs/player_links.py`
- Web API endpoints at `/api/stats/factions/<server_id>`, `/api/stats/rivalries/<server_id>`, and `/api/stats/playerlinks/<server_id>`
- Shared utilities for embed styling in `utils/embed_builder.py`