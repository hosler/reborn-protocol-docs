# Server-Side Behavior and Level Links

This document explains how the GServer `serverside` setting changes level link handling
and client-server interactions.

## The `serverside` Setting

The `serverside` option in `serveroptions.txt` controls whether the server automatically
handles some game mechanics:

```ini
# Determines whether the server handles certain things like signs and links.
# Enabled so the GS2/GS1 npc-server loads (drives NC NPC/class coverage).
serverside = true
```

**Default Value**: `true` (`Server.cpp` reads `serverside` with `.value_or(true)`, and the
shipped `serveroptions.txt` sets it to `true`). This value loads the NPC server. The NPC
server changes whether the server sends links and signs clientside. See the source
reference below.

## How It Affects Level Links

### When `serverside = true` (Default)
- Server automatically handles level link collisions
- When a player walks into a level link area, the server warps them
- Server does NOT send PLO_LEVELLINK packets to clients
- Server does NOT send sign data to clients

### When `serverside = false`
- Server sends PLO_LEVELLINK packets to clients when entering levels
- Server sends sign data to clients
- Client must detect when player touches a level link
- Client must send PLI_LEVELWARP to request the warp
- Server respects `warptoforall` setting for warp permissions

## Client Implementation Requirements

If `serverside = false`, clients must do these tasks:

1. **Parse PLO_LEVELLINK packets** to track level links
   - Sent immediately after PLO_BOARDPACKET when entering a level
   - Contains ALL links as a single newline-terminated string
   - Format: "destlevel x y width height destx desty" (space-separated)
   - Coordinates are in tiles (0-63), not pixels
2. **Monitor player position** to detect link collisions
3. **Send PLI_LEVELWARP** when player touches a link
4. **Handle special destination values**:
   - `"playerx"` or `-1` for X: Keep player's current X position
   - `"playery"` or `-1` for Y: Keep player's current Y position

## GMAP Considerations

When you implement level links in GMAP mode:
- **Edge links between GMAP segments**: typically ignore these (automatic GMAP transitions handle them)
- **Indoor/dungeon links**: honor these (transition to single-level mode)
- Client should track whether current level is part of the GMAP to make this distinction

## GServer Source Code References

From `GServer-v2/server/src/player/PlayerClient.cpp:1481-1489`:
```cpp
// Send clientside links/signs only when there is NO NPC server
// (or when explicitly forced, or on a bigmap segment).
if (!m_server->hasNPCServer() || m_server->cached.forceClientsideLinks.getValue()
        || (subLevel && subLevel->isOnBigMap))
    staticLevelData->sendLinksToPlayer(self, false);

if (!m_server->hasNPCServer() || m_server->cached.forceClientsideSigns.getValue())
    staticLevelData->sendSignsToPlayer(self);
```

> **Note**: The real gate is **whether the server has loaded an NPC server**
> (`hasNPCServer()`), not the `serverside` config bool directly. Enabling
> `serverside` loads the NPC server, so the two track together. But the precise
> condition checked at send time is `hasNPCServer()` (plus the
> `forceClientsideLinks/Signs` overrides and the bigmap case). Older docs quoted
> a `getBool("serverside", false)` check that no longer exists in source.

From `GServer-v2/server/src/level/LevelLink.cpp:53-64` (handling special
values):
```cpp
if (m_destinationX == "-1")
{
    m_constantX = true;
    m_destinationX = "playerx";
}
```

## Event Audience and Visibility

The reference server uses more than one audience rule. Implementers should not
collapse them into a generic notion of "nearby."

### In-range delivery is an inclusive box

**The box only applies to gmaps by default.** `Level::findInRangePlayers` opens
with a fast path: `if (isInsideLevel && !syncInside) { yield every player in
m_players; return; }`, where `isInsideLevel` is `!isGmap()` and `syncInside` is
the `syncbydistanceinside` setting, which defaults to **false**
(`GServer-v2/server/src/level/Level.cpp:2989-2998`, `Server.h:119`). So on an
ordinary non-gmap level the stock server delivers to every player in the level,
unfiltered, and never reaches the distance comparison at all. Box-filtering a
non-gmap level hides events the reference server shows.

When the function does reach the comparison — on a gmap, or on a non-gmap level
where an operator enabled `syncbydistanceinside` — it compares each axis
independently: `abs(dx) <= syncx && abs(dy) <= syncy`. The audience is then an
axis-aligned **box**, not a radius or circle. A player at `(syncx, syncy)` from
the event still counts, even though its Euclidean distance exceeds either
individual limit. The comparison is inclusive at both boundaries.

Inclusive versus strict comparison is an observable hitbox difference. A
recipient exactly `syncx` tiles away receives the event. Changing `<=` to `<`
drops that recipient. It is not a rounding detail.

The search iterates the level's own `m_players` set, not a server-wide player
list. Level-part delivery preserves that membership rule:
`Server::sendPacketToOneLevelPart` delegates to
`Level::findPlayersInLevelPart`, which filters the same `m_players` set by map
cell (`GServer-v2/server/src/Server.cpp:2370-2378`,
`GServer-v2/server/src/level/Level.cpp:3105-3115`).

### Explosion damage uses a plus, and only targets NPCs

**`Level::addExplosion` returns immediately when there is no NPC server.** The
guard `if (!m_server->hasNPCServer()) return;` is the first statement of the
function (`GServer-v2/server/src/level/Level.cpp:2111-2112`), and the informing
overload carries the same guard (`:2099-2101`). A server without an NPC server
therefore does no server-side explosion handling for any target type, and sends
no `PLO_EXPLOSION`. Everything below describes the NPC-server case only.

`Level::addExplosion` does **not** use either audience shape. It constructs a
one-tile-wide vertical rectangle of height `1 + 2r` tiles and a one-tile-high
horizontal rectangle of width `1 + 2r` tiles. Their union is a **plus/cross**,
and NPCs intersecting either strip receive `hurtAndPush`
(`GServer-v2/server/src/level/Level.cpp:2131-2144`).

That code only searches NPC collision results. The reference server applies no
server-side explosion damage there to players or baddies. It relies on client
reports through `PLI_HURTPLAYER` and `PLI_BADDYHURT`. Consequently, a server
that wants authoritative blast damage has no reference player/baddy shape to
copy. It must define and document its own shape, boundary comparison,
occlusion, and de-duplication policy.

## NPC Ownership and Client Mutation

When an NPC server is present, the reference server refuses all three
client-originated NPC mutation operations before parsing their payload:

| Handler | Early-return source |
|---------|---------------------|
| `msgPLI_NPCPROPS` | `GServer-v2/server/src/player/packets/PlayerClientPackets.cpp:189-196` |
| `msgPLI_PUTNPC` | `GServer-v2/server/src/player/packets/PlayerClientPackets.cpp:753-761` |
| `msgPLI_NPCDEL` | `GServer-v2/server/src/player/packets/PlayerClientPackets.cpp:782-790` |

The packets return `Handled`, but no mutation occurs. Treating that return as
authorization would let the client and NPC server disagree about ownership.

## Chat Change Semantics

The server compares the current chat value before assignment. An unchanged
value exits without firing the player-chat event. A change to the empty
string continues through `processChat` and can queue `PLAYERCHATS`
(`GServer-v2/server/src/player/PlayerProps.cpp:348-367`).

Implementations must therefore distinguish **empty** from **absent**. Empty is
a present chat property that clears a previous value and fires the change
event. Absent means no chat update. Repeating the already-current value,
including repeating empty after clearing it, does not fire the event.

## Reborn Client Implementation

The Reborn client handles this by:
1. Checking level links on every movement (`client.py` edge-link detection + `game/actions.py`)
2. Performing a client-side warp when the player touches a non-edge link
3. Treating GMAP edge links as automatic segment transitions rather than warps

## Recommendations

- Servers should generally keep `serverside = true` unless they have custom level link handling
- Clients should support both modes for maximum compatibility
