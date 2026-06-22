# Server-Side Behavior and Level Links

This document explains how the GServer `serverside` setting affects level link handling and client-server interactions.

## The `serverside` Setting

The `serverside` option in `serveroptions.txt` controls whether the server automatically handles certain game mechanics:

```ini
# Determines whether the server handles certain things like signs and links.
# Enabled so the GS2/GS1 npc-server loads (drives NC NPC/class coverage).
serverside = true
```

**Default Value**: `true` (`Server.cpp` reads `serverside` with `.value_or(true)`, and the
shipped `serveroptions.txt` sets it to `true`). Enabling it loads the NPC server, which in
turn changes whether links/signs are sent clientside — see the source reference below.

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

When connecting to a server with `serverside = false`, clients must:

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

When implementing level links in GMAP mode:
- **Edge links between GMAP segments** should typically be ignored (automatic GMAP transitions handle these)
- **Indoor/dungeon links** should be honored (transition to single-level mode)
- Client should track whether current level is part of the GMAP to make this distinction

## GServer Source Code References

From `PlayerClient.cpp` (current source, ~line 1450):
```cpp
// Send clientside links/signs only when there is NO NPC server
// (or when explicitly forced, or on a bigmap segment).
if (!m_server->hasNPCServer() || m_server->cached.forceClientsideLinks.getValue()
        || (subLevel && subLevel->isOnBigMap))
    staticLevelData->sendLinksToPlayer(self, false);

if (!m_server->hasNPCServer() || m_server->cached.forceClientsideSigns.getValue())
    staticLevelData->sendSignsToPlayer(self);
```

> **Note**: The real gate is **whether an NPC server is loaded** (`hasNPCServer()`),
> not the `serverside` config bool directly. They are correlated because enabling
> `serverside` is what loads the NPC server — but the precise condition checked at
> send time is `hasNPCServer()` (plus the `forceClientsideLinks/Signs` overrides and
> the bigmap case). Older docs quoted a `getBool("serverside", false)` check that no
> longer exists in source.

From `LevelLink.cpp` (handling special values):
```cpp
if (m_destinationX == "-1")
{
    m_constantX = true;
    m_destinationX = "playerx";
}
```

## PyReborn Implementation

PyReborn handles this by:
1. Checking level links on every movement (`client.py` edge-link detection + `game/actions.py`)
2. Performing a client-side warp when a non-edge link is touched
3. Treating GMAP edge links as automatic segment transitions rather than warps

## Recommendations

- Servers should generally keep `serverside = true` unless they have custom level link handling
- Clients should support both modes for maximum compatibility