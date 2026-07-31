# Level Link Implementation Guide

This document gives instructions to implement level links in Reborn clients. The
instructions come from implementation experience with the Reborn client.

## Overview

Level links are rectangular areas in a level. When a player touches a level link, the
link moves the player to a different level. Reborn worlds use level links for navigation.

## Packet Structure

### PLO_LEVELLINK (1)

If `serverside = false`, the server sends level link data to clients:

```
[STRING: link_data] // Raw newline-terminated string
```

**Critical Implementation Note**: This data is NOT a GSTRING (length-prefixed string).
The server sends raw string data until a newline character (0x0A). This difference has
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

The server sends multiple links as one string with newline separators.

### Coordinate Frame of a Link

Every link field is in the **local tile frame** of a single 64×64 level:

- `x` and `y` are the local top-left corner of the trigger rectangle.
- `width` and `height` are local tile spans, not an ending coordinate and not
  a world-space distance.
- Numeric `destx` and `desty` are local coordinates in `destlevel`.

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

The server test is `Level.cpp:2417`, which uses `>=` and `<=` on both axes.
`pyreborn/client_warp.py` matches it. A half-open test misses the far edge tile
of every link, so a player who steps onto the last row of a door triggers
nothing.

## Special Coordinate Values

The destination coordinates accept special values:

- **"playerx"**: Keep player's current X coordinate
- **"playery"**: Keep player's current Y coordinate
- **"-1"**: Server converts to "playerx" or "playery" respectively

Example: A link with `destx="playerx" desty="32"` keeps the player's X position. It puts
the player at Y=32 in the destination level.

## GMAP Implementation

### Understanding GMAP Links

In GMAP (Game Map) mode, the system arranges levels in a grid. Each level can have links
to:
1. **Adjacent GMAP segments** (edge links)
2. **Non-GMAP levels** (indoor/dungeon links)

### Edge Link Filtering

In GMAP mode, clients should usually ignore edge links between GMAP segments because:
- GMAP system handles seamless transitions automatically
- Edge links would interfere with smooth world navigation
- Server still sends these for backward compatibility

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
    """Check if a link sits against a level edge.

    This mirrors the Reborn client's actual heuristic
    (ActionsMixin._is_edge_link, pyreborn/game/actions.py). It is a
    GameClient-only filter, and the base Client does not apply it:
    a link is treated as an edge link if its rectangle touches any of the
    four borders of the 64-tile level. The thresholds are <=1 / >=63 (not
    an exact x==0 && width==1 match), so links one tile in from the border
    still count.
    """
    return (link.x <= 1
            or link.x + link.width >= 63
            or link.y <= 1
            or link.y + link.height >= 63)
```

## Complete Implementation Example

```python
class LevelLinkManager:
    def __init__(self, gmap_manager):
        self.gmap_manager = gmap_manager
        self.current_links = []
    
    def parse_level_links(self, link_data, current_level):
        """Parse PLO_LEVELLINK packet data"""
        self.current_links.clear()
        
        # Split by newlines (server sends all links in one string)
        lines = link_data.strip().split('\n')
        
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 7:
                link = LevelLink(
                    destination=parts[0],
                    x=int(parts[1]),
                    y=int(parts[2]),
                    width=int(parts[3]),
                    height=int(parts[4]),
                    dest_x=parts[5],  # Keep as string for special values
                    dest_y=parts[6]   # Keep as string for special values
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
            # Inclusive on both ends, matching Level.cpp:2417.
            if (link.x <= player_x <= link.x + link.width and
                link.y <= player_y <= link.y + link.height):
                return link
        return None
    
    def calculate_destination_coords(self, link, current_x, current_y):
        """Calculate actual destination coordinates"""
        # Handle special values
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
