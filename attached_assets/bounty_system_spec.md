
# Bounty System – Development Specification

## Project Context

You are a **professional-grade, deadline-driven senior dev team** building a **premium, multi-guild PvP statistics Discord bot** for the game **Deadside**. The bot already ingests `.csv` kill logs and `.log` files via **SFTP**, parses them, and stores data in **MongoDB (Motor)**.

The bot uses **Pycord** and is built for modern Discord interaction systems (slash commands, embeds, modals, pagination, etc). It must run on **low-resource platforms (like Replit)** and scale up to **1,000+ guilds and 3,000+ active SFTP connections**, all while remaining performant.

---

## Responsibilities and Mandate

You are **expected to work autonomously** with complete responsibility for clean, tested, scalable, and modular systems. Do **not wait** for step-by-step instructions.

### Use All Available Resources:
- Leverage **existing logic and structure** wherever possible.
- Reference external sources: **Google, Stack Overflow, GitHub, Replit open-source bots**.
- Follow best practices from **real-world scalable architecture** patterns.

### Your Core Responsibilities:
- Maintain and extend **existing code and naming standards**.
- Ensure modern UX (slash commands, embeds, buttons, pagination, modals).
- Use **non-blocking, async logic**; prioritize **low memory footprint** and **I/O efficiency**.
- Write **modular, documented, production-ready Python**.
- Test in **realistic simulation** (including live-like SFTP, MongoDB, and Discord environments).
- Justify all technical decisions with **cost, clarity, and real-world impact**.

---

## Bounty System Specification (Premium Feature Only)

The **entire bounty system** is a **guild-level premium feature**. Integrate it into the existing premium logic (already implemented in the bot). **Do not modify** premium structure—hook into it.

### MongoDB Collection: `bounties`
```json
{
  "guild_id": str,
  "target_id": str,
  "target_name": str,
  "placed_by": str,
  "placed_at": datetime,
  "reason": str,
  "reward": int,
  "claimed_by": Optional[str],
  "claimed_at": Optional[datetime],
  "status": "active" | "claimed" | "expired"
}
```

---

### Slash Commands (Premium-Only)

#### `/bounty place [target] [reward]`
- Must validate guild premium status.
- Places bounty on a known PvP target from parsed CSV data.
- Deducts reward from placer’s currency (integrate with economy system if present).

#### `/bounties active`
- Lists all **active bounties** in current guild.
- Embed should show: Target, Reward, Time active.

#### `/bounties my`
- Shows bounties the user has **placed** and/or **claimed**.

#### `/bounty settings` *(Premium Optional)*
- Configures thresholds for auto-bounties.
- Admin-only.

---

### CSV Listener Integration

On each new parsed kill:
- If victim is a bounty `status: "active"`, and killer is in same guild:
  - Mark bounty as `claimed`, set `claimed_by` and `claimed_at`.
  - Automatically reward the killer.

---

### AI Auto-Bounty (Premium Only)

- Every 5 minutes (background task):
  - Detect players with **5+ kills in 10 minutes** or **3+ kills of the same victim**.
  - Automatically place bounty using:
    - `"placed_by": "AI"`
    - Reason: `"Killstreak"` or `"Repetition"`
  - Reward set dynamically (e.g., 100–500 killcoins).
  - Admins can disable via `/bounty settings`.

---

### Performance Rules

- Efficient Mongo queries with proper indexes.
- Never block event loop.
- Background tasks must use asyncio, backoff logic, and be fault-tolerant.
- Use cached guild-premium status to avoid repetitive DB calls.

---

## Developer Mindset

**Think like a real dev team** under a **time-boxed professional contract.**

- Be opinionated, make smart architectural decisions.
- Avoid XP, levels, or childish badges — this is for **adult retention**.
- Focus on **minigames, gambling systems, intelligent retention mechanics**.
- Minimize bloat, avoid overengineering, and never write throwaway code.
- Respect resource ceilings (Replit, etc) but don’t compromise on capability.

---

> Begin by implementing the **bounty system as described**, respecting the existing structure and premium logic. You must deliver modular, production-ready Python code that meets all the outlined constraints.
