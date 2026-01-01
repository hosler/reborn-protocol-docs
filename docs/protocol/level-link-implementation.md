# Level Link Implementation Guide

This document provides comprehensive guidance for implementing level links in Graal Reborn clients, based on real-world implementation experience with PyReborn.

## Overview

Level links are rectangular areas in a level that transport players to other levels when touched. They are a fundamental navigation mechanism in Graal worlds.

## Packet Structure

### PLO_LEVELLINK (1)

When `serverside = false`, the server sends level link data to clients:

```
[STRING: link_data] // Raw newline-terminated string
```

**Critical Implementation Note**: This is NOT a GSTRING (length-prefixed string). The server sends raw string data that continues until a newline character (0x0A). This has been a common source of parsing errors.

### Link Data Format

Each link is encoded as a space-separated string:
```
destlevel x y width height destx desty
```

- **destlevel**: Target level filename (e.g., "level2.nw", "house.nw")
- **x, y**: Link area position in tiles (0-63)
- **width, height**: Link area size in tiles
- **destx, desty**: Destination coordinates (see special values below)

Multiple links are sent as a single string with newline separators.

## Special Coordinate Values

The destination coordinates support special values:

- **"playerx"**: Keep player's current X coordinate
- **"playery"**: Keep player's current Y coordinate
- **"-1"**: Server converts to "playerx" or "playery" respectively

Example: A link with `destx="playerx" desty="32"` will maintain the player's X position but place them at Y=32 in the destination level.

## GMAP Implementation

### Understanding GMAP Links

In GMAP (Game Map) mode, levels are arranged in a grid. Each level can have links to:
1. **Adjacent GMAP segments** (edge links)
2. **Non-GMAP levels** (indoor/dungeon links)

### Edge Link Filtering

When in GMAP mode, clients should typically ignore edge links between GMAP segments because:
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
        if is_edge_link(link, current_level):
            return False  # Ignore edge links in GMAP mode
    
    # Process indoor/dungeon links
    return True

def is_edge_link(link, current_level):
    """Check if link is at the edge of the level"""
    # Edge links typically have specific patterns:
    # - X position 0 with width 1 (left edge)
    # - X position 63 with width 1 (right edge)
    # - Y position 0 with height 1 (top edge)
    # - Y position 63 with height 1 (bottom edge)
    
    if link.x == 0 and link.width == 1:  # Left edge
        return True
    if link.x == 63 and link.width == 1:  # Right edge
        return True
    if link.y == 0 and link.height == 1:  # Top edge
        return True
    if link.y == 63 and link.height == 1:  # Bottom edge
        return True
    
    return False
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
            if (player_x >= link.x and player_x < link.x + link.width and
                player_y >= link.y and player_y < link.y + link.height):
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
    dest_x, dest_y = calculate_destination_coords(link, 
                                                  current_player.x, 
                                                  current_player.y)
    
    # Create PLI_LEVELWARP packet
    packet = PacketBuilder()
    packet.add_byte(PLI_LEVELWARP)
    packet.add_gchar(int(dest_x))  # Convert to tiles
    packet.add_gchar(int(dest_y))  # Convert to tiles
    packet.add_string(link.destination)  # Level name
    
    connection.send(packet.build())
```

## Common Implementation Pitfalls

1. **Parsing Error**: Treating PLO_LEVELLINK as GSTRING instead of raw string
2. **Coordinate Confusion**: Links use tile coordinates (0-63), not pixel coordinates
3. **GMAP Edge Links**: Not filtering edge links causes unwanted warps
4. **Special Values**: Not handling "playerx"/"playery" correctly
5. **Timing**: Links are sent after PLO_BOARDPACKET - ensure proper packet ordering

## Testing Recommendations

1. **Test with serverside=false** to ensure links are received
2. **Verify special coordinates** work correctly
3. **Test GMAP transitions** don't trigger edge links
4. **Test indoor transitions** work from GMAP levels
5. **Monitor packet flow** to ensure correct parsing

## Visual Debugging

Consider implementing visual indicators for links during development:

```python
def render_links(surface, links, camera_offset):
    """Render link areas for debugging"""
    for link in links:
        # Convert to screen coordinates
        screen_x = link.x * 16 - camera_offset.x
        screen_y = link.y * 16 - camera_offset.y
        
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

This visual feedback helps verify link parsing and filtering logic during development.