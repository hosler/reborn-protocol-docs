# PyReborn Implementation Gaps

This document tracks gaps and missing features in PyReborn relative to GServer-v2's
packet set.

> **Status (current):** The large gaps that earlier versions of this document
> described — broken chat, missing RC response handling, and a long list of
> unhandled PLO_* packets — have since been **implemented**. The automated QA
> suite (`pyReborn/game_tester`) passes its full single-bot + multi-bot set. The
> sections below have been updated to reflect the current code; the historical
> "critical issues" list is preserved at the bottom for reference.

---

## Resolved (previously listed as gaps)

| Former gap | Now |
|------------|-----|
| Chat first-character-loss bug | Fixed — `parse_chat` (`packets.py`) reads a GCHAR length then the full message; no recovery hack. |
| RC client has no response handlers | Implemented — `rc_client.py` dispatches the full PLO_RC_* family in its own `_handle_packet`. RC is not driven from `client.py`. |
| PLO_LEVELSIGN (5) — no parser | `parse_level_sign` exists (`packets.py`), dispatched in `client.py`, stored in `self.signs`. |
| PLO_EXPLOSION (36) — no handler | `parse_explosion` + dispatch; fires `on_explosion`. |
| PLO_HITOBJECTS (46) — no handler | `parse_hit_objects` + dispatch. |
| PLO_BOARDLAYER (107) | Handled in `client.py`. |
| PLO_MINIMAP (172) / PLO_BIGMAP (171) / PLO_GHOSTMODE (170) / PLO_RPGWINDOW (179) | All handled in `client.py`. |
| GATTRIB props parsed but discarded | Stored as `props['gattrib<N>']` via the `_GATTRIB_IDS` map (both parse paths). |
| Weapon selection by click | Implemented in `inventory_ui.py` (`InventoryUI.handle_click`). |
| Tile restoration always at pickup spot | Thrown tiles now land ahead of the player with collision validation (`game/actions.py`), falling back to the pickup spot only when blocked. |

Note: GATTRIB property numbering is **not** the contiguous `36–74` range the old
doc assumed. The real layout is non-contiguous (37–41, 46–49, 54–74) and is
interleaved with `ATTACHNPC`, `GMAPLEVELX/Y`, `Z`, and the connection/status
props. See [Packet Structures](../protocol/packet-structures.md) for the table.

---

## Remaining genuine gaps

### GS1 interpreter — unimplemented commands

`pyreborn/gs1_interpreter.py` implements most common commands (including
`changeimgvis` and `changeimgzoom`). Still missing:

- `changeimgpart` — change displayed image sub-rectangle
- `showpoly` / `hidepoly` — polygon display
- `drawoverplayer` / `drawunderplayer` — explicit Z-order control

### Inbound projectile handling — unverified

- Inbound **PLO_SHOOT2** handling: the client *sends* `PLI_SHOOT2`
  (`packets.py` / `client.py`), but processing of inbound projectile packets
  from the server is not confirmed.

### NC / RC management — now verified

- **NC (NPC-Control) management**: `nc_client.py` is complete. Driven against a
  GS2 npc-server (`serverside = true`), all NC PLI builders byte-match the
  server and the NC PLO family is fully parsed — verified by the
  `--coverage-nc` harness in `game_tester`. NC negotiates **ENCRYPT_GEN_2**
  (`Protocol.use_gen2`), distinct from the client's GEN_5; see
  [RC & NC Protocols](../protocol/rc-nc-protocols.md).
- **RC administration**: `rc_client.py` covers the full RC PLO family with
  byte-validated PLI builders (`--coverage-rc`).

### Level board decompression fallback (by design)

`packets.py` still returns an empty board (`[0] * 4096`) if a level board fails
to decompress. This is an intentional safe fallback rather than a live bug, but
it means a corrupt/truncated board renders as an empty level with no error
surfaced. Logging on this path would aid debugging.

### Duplicate `PacketReader`

The shared `PacketReader` now lives in `reborn-protocol` and is imported by
`pyreborn/packets.py`. However, `pyreborn/listserver.py` still defines its own
local `PacketReader`. Consolidating onto the shared class would remove the
duplication.

---

## Verifying gaps

When checking whether a gap in this document is still real, prefer the code and
the QA suite over this file:

```bash
cd pyReborn && python -m game_tester          # full QA run
grep -n "PLO_" pyreborn/client.py             # what the client dispatches
grep -n "def parse_" pyreborn/packets.py      # what parsers exist
```

---

## Historical reference (pre-fix)

The original version of this document listed the following as **critical**,
all of which are now resolved (kept here only as a changelog):

1. Chat message first-character loss
2. RC client response handlers missing (14 PLO_RC_* packets)
3. Missing handlers for PLO_LEVELSIGN, PLO_EXPLOSION, PLO_HITOBJECTS,
   PLO_BOARDLAYER, PLO_GHOSTMODE, PLO_BIGMAP, PLO_MINIMAP, PLO_RPGWINDOW
4. GATTRIB properties parsed but discarded
5. Tile restoration position / weapon click-selection TODOs
