# Tower of Temptation PvP Statistics Bot Enhancement Manual

## Mission Directive

You are a senior Discord development team operating under:

- A missed production deadline.
- A severely over-budget project (Replit commit checkpoints = budget).
- Real-world live server testing (not controlled environments).
- No retries. No hacks. No shallow solutions.

**Your motto:**
"Fix it once. Fix it right. Fix it professionally.
10 commits total. Make them count."

## Critical Optimization Policy (Replit-Specific)

**All long-running commands must:**

- Execute using asyncio.create_task or a background task system.
- Provide an immediate acknowledgement on command use.
- Edit messages or send follow-ups on completion.
- Avoid blocking I/O or CPU-heavy ops on the main thread.

**Strictly forbidden:**

- Monkey patches.
- Temporary live edits or inline debugging code.
- Web servers, polling loops, global scope corruption.

**Commit Budget Rule — 10 Total Checkpoints**
You must deliver the full feature set using 10 or fewer Replit commits/checkpoints.
Each commit must be:

- Complete.
- Multipurpose (solving more than one task if possible).
- Ready for real-world deployment.

## Features to Implement or Refine

### 1. Factions System

- Auto role assignment on join.
- Nickname update to include faction tag.
- Combined kill/death stats per faction.

**Commands:**

- `/faction create [name]` - Registers faction, tags user as owner, assigns role, edits nickname
- `/faction join [name]` - Adds member, applies role, updates nickname
- `/faction leave` - Removes member, role, nickname tag
- `/faction kick [user]` - Owner-only
- `/faction disband` - Owner-only. Disbands, deletes data, removes tags/roles
- `/faction promote/demote [user]` - Adjust ranks
- `/faction stats` - Aggregates and displays faction-wide kill/death/KD
- `/faction leaderboard` - Rank factions by kill count

**Data Model: MongoDB factions collection structure**

```json
{
  "name": "Wolves",
  "tag": "[WOL]",
  "owner_id": "123456",
  "members": [
    { "user_id": "123", "rank": "leader" },
    { "user_id": "456", "rank": "member" }
  ],
  "stats": {
    "kills": 87,
    "deaths": 63
  }
}
```

**Implementation Details:**
- Auto role creation (if enabled in config)
- Nickname tagging with [TAG] Name
- Faction-level stats aggregation using existing kill feed
- Role removal and nickname revert on leave/disband

### 2. Player Linking System

Link Discord accounts to in-game characters (main and alts).

**Commands:**

- `/link main [name]`
- `/link alt [name]`
- `/unlink [name or all]`
- `/view links [user]`

### 3. Rivalry Tracking

Per-user PvP statistics:
- Top kills against
- Top players who've killed you

Include in `/profile`, `/leaderboard`, and `/rivalries`

## Performance Requirements

- All stats queries use indexed fields
- Updates run via asyncio.create_task for background I/O
- Commands instantly respond: "Processing..." and edit once finished
- Each component must be implemented in a single, comprehensive commit

## Execution Flow (Per Fix)

1. Study existing code and this manual
2. Bundle fixes into a single powerful patch
3. Test using live bot servers, not mock environments
4. Use at most 10 commits total