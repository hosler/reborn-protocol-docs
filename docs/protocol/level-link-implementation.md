# Level Link Implementation Guide

This document gives instructions to implement level links in Reborn clients. The
instructions come from implementation experience with the Reborn client.

## Overview

Level links are rectangular areas in a level. When a player touches a level link, the
link moves the player to a different level. Reborn worlds use level links for navigation.

## Packet Structure

### PLO_LEVELLINK (1)

The server sends **one `PLO_LEVELLINK` packet per link**
(`StaticLevelData::sendLinksToPlayer`, `server/src/level/Level.cpp:156-167`):

```
[STRING: link_data] // Raw string, one link, ended by the packet's 0x0A terminator
```

The server sends links only when it also sends the level's board data, that is when the
client's cached copy is missing or older than the level, and only if one of these holds
(`server/src/player/PlayerClient.cpp:1457-1482`):

- the server has no NPC-server (`serverside = false`), or
- the `clientsidelinks` option is set, or
- the level is a sub-level on a bigmap. The server sends links there because a client
  that waits for the warp can run past the level edge and overflow its position
  (`PlayerClient.cpp:1479-1480`).

When an NPC-server is present and none of the other conditions holds, the server tests
links itself and warps the player (`PlayerClient.cpp:1843-1895`). It skips this on bigmaps
(`:1855-1859`) and leaves out probable map links (see
[Edge Link Filtering](#edge-link-filtering)) when the level is on a map. The pre-2.x client
path sends links without the NPC-server conditions, but only in the branch that sends the
board (`PlayerClientOriginal.cpp:141-156`); it sends none when the level was already entered
this session or the client's cache is current (`:132-137`).

**Critical Implementation Note**: This data is NOT a GSTRING (length-prefixed string).
The string runs to the end of the packet; the only newline is the packet terminator
(`server/src/level/Level.cpp:165`). This difference has
caused many parsing errors.

### Link Data Format

Each link is encoded as a space-separated string:
```
destlevel x y width height destx desty
```

- **destlevel**: Target level filename (e.g., "level2.nw", "house.nw")
- **x, y**: Link area position in tiles (0-63)
- **width, height**: Link area size in tiles
- **destx, desty**: Destination coordinates (see special values below)

Each packet holds exactly one link. Do not expect several links per packet.

The destination level name may contain spaces. The server parses the **last six**
space-separated tokens as geometry and destination, and joins the rest into the level
name (`server/src/level/LevelLink.cpp:78-90`). A client that reads `split()[0]` as the
level name misreads such links.

`destx` and `desty` are not always numbers. They may be `playerx`, `playery` or a GS1 math
expression. The server evaluates an expression only when an NPC-server exists
(`LevelLink.cpp:24-29`, `:117-129`), so a link that reaches a client may carry an
expression that the client must not parse as a float.

### Coordinate Frame of a Link

Every link field is in the **local tile frame** of a single 64×64 level:

- `x` and `y` are the local top-left corner of the trigger rectangle.
- `width` and `height` are local tile spans, not an ending coordinate and not
  a world-space distance.
- Numeric `destx` and `desty` are local coordinates in `destlevel`.
  One exception: when `destlevel` ends in `.gmap` or names the gmap level itself, the
  server reads the warp position as gmap-global, with origin (0, 0)
  (`PlayerClientPackets.cpp:66-69`, `:85-88`). See [GMAP](gmap.md#which-frame-the-wire-carries).

This rule also applies when the source or destination is a GMAP segment. Do not add
the source segment origin to `x`/`y`, and do not serialize stored world
coordinates directly into `PLI_LEVELWARP`. Convert the player's world position
to target-local coordinates first. Segment/grid coordinates are separate
metadata; screen coordinates are only for rendering.

For collision, the rectangle is **inclusive on both ends**:
`x <= player_local_x <= x + width` and
`y <= player_local_y <= y + height`. For example, `x=62 width=2` covers local
X values 62, 63 and 64. It does not describe a world span starting at tile 62
of the whole GMAP.

The server test is `server/src/level/Level.cpp:2541` and `:2566`, which use `>=` and `<=` on both axes on whole-tile positions.
`pyreborn/client_warp.py` matches it. A half-open test misses the far edge tile
of every link, so a player who steps onto the last row of a door triggers
nothing.

## Special Coordinate Values

The destination coordinates accept special values:

- **"playerx"**: Keep player's current X coordinate
- **"playery"**: Keep player's current Y coordinate
- **"-1"**: Server converts to "playerx" or "playery" respectively when it parses the link
  (`LevelLink.cpp:54-64`, `:102-111`), so `-1` never reaches the wire

Example: A link with `destx="playerx" desty="32"` keeps the player's X position. It puts
the player at Y=32 in the destination level.

## GMAP Implementation

### Understanding GMAP Links

In GMAP (Game Map) mode, the system arranges levels in a grid. Each level can have links
to:
1. **Adjacent GMAP segments** (edge links)
2. **Non-GMAP levels** (indoor/dungeon links)

### Edge Link Filtering

The reference server calls the edge links between segments *probable map links* and
filters them itself: with an NPC-server present, its own link test skips them on a map
(`PlayerClient.cpp:1864`). Reborn clients likewise ignore edge links between GMAP segments, because the
GMAP system handles seamless transitions automatically. This client-side practice is
unverified against the decompiled reference client. The server sends links to clients
under the conditions in the Packet Structure section, not "for backward compatibility".

#### Where the original client tests a link

A lab test of the 2.05 rev2 client against one server (straight walks only, measured to half
a tile; [`protocol/link-test-2026-11-04.md`](https://github.com/squirelworks/Graal_analysis/blob/main/protocol/link-test-2026-11-04.md)) found that the client takes a link when **one point** enters the link
rectangle: the player's centre, (x + 1.5, y + 2), pushed 1 to 1.5 tiles ahead in the walking
direction. So a 1×1 link that is off that centre line is walked past without triggering.
2.17.1 and 2.22 also have a helper that builds a default link with `destx` and `desty` preset
to `playerx` and `playery`, used for editor and edge cases ([`version-profiles/plo-levellink-layouts.tsv`](https://github.com/squirelworks/Graal_analysis/blob/main/version-profiles/plo-levellink-layouts.tsv)).

### Implementation Strategy

```python
def should_process_link(link, current_level, gmap_manager):
    """Determine if a level link should be processed"""
    
    # Always process links in non-GMAP mode
    if not gmap_manager.is_gmap_level(current_level):
        return True
    
    # Check if destination is a GMAP level
    if gmap_manager.is_gmap_level(link.destination):
        # This is an edge link - check if we should filter it
        if is_edge_link(link):
            return False  # Ignore edge links in GMAP mode
    
    # Process indoor/dungeon links
    return True

def is_edge_link(link):
    """The reference's probable-map-link test (LevelLink::isProbableMapLink,
    server/src/level/LevelLink.cpp:142-149): a one-tile-wide strip on the
    left or right border that keeps the player's Y, or a one-tile-high
    strip on the top or bottom border that keeps the player's X.
    """
    return (((link.x == 0 or link.x == 63)
             and link.width == 1 and link.dest_y == "playery")
            or ((link.y == 0 or link.y == 63)
                and link.height == 1 and link.dest_x == "playerx"))
```

The Reborn client's own filter (`ActionsMixin._is_edge_link`, `pyreborn/game/actions.py`)
is wider. It also treats a rectangle within one tile of any border as an edge link
(`x <= 1`, `x + width >= 63`, and the same on Y). That is our heuristic, not the
reference rule, and it drops ordinary doors close to a border.

## Complete Implementation Example

```python
class LevelLinkManager:
    def __init__(self, gmap_manager):
        self.gmap_manager = gmap_manager
        self.current_links = []
    
    def parse_level_links(self, link_data, current_level):
        """Parse PLO_LEVELLINK packet data"""
        self.current_links.clear()
        
        # One link per PLO_LEVELLINK packet. A level name may contain
        # spaces, so the last six tokens are the geometry.
        for line in link_data.strip().split('\n'):
            parts = line.strip().split()
            if len(parts) >= 7:
                link = LevelLink(
                    destination=" ".join(parts[:-6]),
                    x=int(parts[-6]),
                    y=int(parts[-5]),
                    width=int(parts[-4]),
                    height=int(parts[-3]),
                    dest_x=parts[-2],  # Keep as string for special values
                    dest_y=parts[-1]   # and for math expressions
                )
                
                # Apply GMAP filtering if needed
                if self.should_add_link(link, current_level):
                    self.current_links.append(link)
    
    def should_add_link(self, link, current_level):
        """Determine if link should be added based on GMAP rules"""
        # In GMAP mode, filter edge links to other GMAP levels
        if self.gmap_manager.is_in_gmap_mode():
            if self.gmap_manager.is_gmap_level(current_level.name):
                if self.gmap_manager.is_gmap_level(link.destination):
                    # Check if it's an edge link
                    if self.is_edge_link(link):
                        return False  # Skip GMAP edge links
        
        return True  # Keep all other links
    
    def check_collision(self, player_x, player_y):
        """Check if player is touching any link"""
        for link in self.current_links:
            # Inclusive on both ends, matching Level.cpp:2541 and :2566.
            if (link.x <= player_x <= link.x + link.width and
                link.y <= player_y <= link.y + link.height):
                return link
        return None
    
    def calculate_destination_coords(self, link, current_x, current_y):
        """Calculate actual destination coordinates"""
        # Handle special values
        # dest_x/dest_y may also be a GS1 math expression, which float()
        # rejects. The server evaluates those only with an NPC-server.
        dest_x = current_x if link.dest_x == "playerx" else float(link.dest_x)
        dest_y = current_y if link.dest_y == "playery" else float(link.dest_y)
        
        return dest_x, dest_y
```

## Sending Warp Request

When a player touches a link, send PLI_LEVELWARP:

```python
def send_warp_request(connection, link, current_player):
    # Calculate destination coordinates
    # current_player.local_x/local_y must be local in the destination segment.
    # Do not substitute stored GMAP world coordinates here.
    dest_x, dest_y = calculate_destination_coords(
        link, current_player.local_x, current_player.local_y)
    
    # Create PLI_LEVELWARP packet
    packet = PacketBuilder()
    packet.add_byte(PLI_LEVELWARP)
    # Half-tile units on the wire. The server reads this back as gchar * 8
    # pixels, so sending the bare tile number lands the player at half the
    # intended coordinate.
    packet.add_gchar(int(dest_x * 2))
    packet.add_gchar(int(dest_y * 2))
    packet.add_string(link.destination)  # Level name
    
    connection.send(packet.build())
```

### Warp Failure

`PLI_LEVELWARPMOD` is `PLI_LEVELWARP` with a `GInt5` modtime before the position
(`PlayerClientPackets.cpp:56-58`). If the destination level does not exist or cannot be
entered, the server sends `PLO_WARPFAILED` with the level name
(`PlayerClient.cpp:1211`, `:1294`). It then warps the player back to the current level and,
if that also fails, to the `unstickmelevel` position (`PlayerClientPackets.cpp:92-104`).
A client should expect to stay in, or return to, a level after a failed warp.

## Common Implementation Pitfalls

1. **Parsing Error**: The parser treats PLO_LEVELLINK as GSTRING instead of a raw string
2. **Coordinate Confusion**: Link positions, spans, and destinations use
   level-local tiles, not world tiles, segment coordinates, or screen pixels
3. **GMAP Edge Links**: Not filtering edge links causes unwanted warps
4. **Special Values**: Not handling "playerx"/"playery" correctly
5. **Half-open collision**: Using `<` on the far edge. The test is inclusive on
   both ends, so a half-open test drops the last row and column of every link
6. **Tile units in the warp packet**: `PLI_LEVELWARP` carries half-tiles.
   Sending the bare tile number halves the destination
5. **Timing**: The server sends links after PLO_BOARDPACKET. Make sure that packets stay
   in the correct order.

## Testing Recommendations

1. **Test with serverside=false** to make sure that the client receives links
2. **Verify special coordinates** work correctly
3. **Test GMAP transitions** don't trigger edge links
4. **Test indoor transitions** work from GMAP levels
5. **Monitor packet flow** to make sure that the parser operates correctly

## Visual Debugging

During development, you can show visual indicators for links:

```python
def render_links(surface, links, camera_offset,
                 segment_origin_x, segment_origin_y):
    """Render link areas for debugging"""
    for link in links:
        # Convert to screen coordinates
        # Convert the owning segment's local link position to world tiles
        # before applying the world-to-screen camera transform.
        world_x = segment_origin_x + link.x
        world_y = segment_origin_y + link.y
        screen_x = world_x * 16 - camera_offset.x
        screen_y = world_y * 16 - camera_offset.y
        
        # Choose color based on link type
        if is_edge_link(link):
            color = (255, 0, 0, 100)  # Red for edge links
        elif link.dest_x == "playerx" or link.dest_y == "playery":
            color = (255, 255, 0, 100)  # Yellow for special coords
        else:
            color = (0, 255, 0, 100)  # Green for normal links
        
        # Draw semi-transparent rectangle
        pygame.draw.rect(surface, color, 
                        (screen_x, screen_y, 
                         link.width * 16, link.height * 16))
```

This visual feedback helps you verify the link parsing and filtering logic during
development.
