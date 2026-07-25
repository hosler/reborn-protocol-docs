# PyReborn Implementation Gaps

This document tracks gaps and missing features in PyReborn relative to GServer-v2's
packet set.

> **Status (current):** The large gaps that earlier versions of this document
> described — broken chat, missing RC response handling, and a long list of
> unhandled PLO_* packets — have since been **implemented**. Final QA numbers:
> base suite **16/16**, tier1 **2/2** (board modify, large files), tier2 **4/4**
> (bomb/arrow/horse/flagdel relay), tier3 **4/4** (freeze/say2 cycle,
> triggeraction relay, serverwarp round-trip, synthetic parsers), tier5 **5/5**
> (GS2 bytecode transport and execution), GMAP suite **6/6**, and the packet-coverage
> harnesses (`--coverage`, `--coverage-rc`, `--coverage-nc`) report **100%** of
> emitted types parsed for base/RC/NC sessions. The version probe
> (`game_tester/version_probe.py`) passes with **live 1.411, 2.17, and 2.21
> logins** — exercising the GEN_3 and GEN_4 codecs end-to-end against GServer.
>
> Previously listed here as "in progress", now **done**: GEN_3/GEN_4 codecs
> (`reborn-protocol/reborn_protocol/codec.py` `Gen3Codec`/`Gen4Codec` — wire
> details in [Client Versions & Encryption](../protocol/versions-encryption.md#gen_3s-single-byte-insertion-precisely)),
> server-control packets (freeze/say2/serverwarp/inbound triggeraction/profile,
> `game_tester/tier3_tests.py`), GS2 bytecode **transport and execution** (parse + store of
> NPCBYTECODE/GANISCRIPT/NPCWEAPONSCRIPT/LOADGANI/LOADSCRIPT — layouts in
> [Version-Gated Behavior](../protocol/version-gated-behavior.md#bytecode-packet-family)),
> and the RC write-side builders (protocol parity tier 6, `packets.py`).

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
| PLI_BOARDMODIFY / PLO_BOARDMODIFY / PLO_BOARDMODIFY2 / PLO_BOARDHEIGHTS | Parsed and byte-validated against C++ (`tier1_tests.py:test_board_modify`); see [Packet Structures](../protocol/packet-structures.md#pli_boardmodify-1---tile-modification). |
| Large-file transfer (LARGEFILESTART/SIZE/END + chunked PLO_FILE) | Implemented and tested (`tier1_tests.py:test_large_file_transfer`). The `parse_file` modtime 8-bit-shift bug flagged earlier in this audit is now **fixed** (7-bit GINT5 decode, `packets.py:2717`) — see the historical note in [Packet Structures: PLO_FILE](../protocol/packet-structures.md#plo_file-102---file-data). |
| Bombs/arrows/horses relay (PLO/PLI 4/5/7/8/9/11/12/17/18/19) | Implemented and tested (`tier2_tests.py`: `test_bomb_relay`, `test_arrow_relay`, `test_horse_relay`). |
| PLI_FLAGDEL relay | Tested (`tier2_tests.py:test_flagdel_relay`). |

Note: GATTRIB property numbering is **not** the contiguous `36–74` range the old
doc assumed. The real layout is non-contiguous (37–41, 46–49, 54–74) and is
interleaved with `ATTACHNPC`, `GMAPLEVELX/Y`, `Z`, and the connection/status
props. See [Packet Structures](../protocol/packet-structures.md) for the table.

---

## Remaining genuine gaps

### GS2 bytecode execution

GS2 bytecode is requested, parsed, stored, and executed by the Python client.
The VM implements cooperative event execution and reports opcode and host-call
coverage. See [GS2 bytecode and client runtime](gs2-engine.md) for the
container, verified semantics, host surface, and deliberately inert calls.

### GEN_6 / v6-native encryption

`ENCRYPT_GEN_6` remains unimplemented — but so is it **server-side** (see
[Client Versions & Encryption](../protocol/versions-encryption.md#pli_set_enc_key-252--pli_bundle-253-declared-unimplemented)),
so this is a protocol-wide gap, not a pyReborn-specific one. No action possible until a
server implements it.

### Ground-item sprites — pics1.png tile table

The `LevelItemType` → pics1.png tile-rectangle mapping for ground-item rendering is
incomplete; some item drops render with placeholder art in the pygame client. Protocol
handling of items is complete — this is a client art-table gap only.

### GS1 interpreter — unimplemented commands

`pyreborn/gs1_interpreter.py` implements most common commands (including
`changeimgvis` and `changeimgzoom`). Still missing:

- `changeimgpart` — change displayed image sub-rectangle
- `showpoly` / `hidepoly` — polygon display
- `drawoverplayer` / `drawunderplayer` — explicit Z-order control

### Inbound projectile handling — now verified

- Inbound **PLO_SHOOT (175)** / **PLO_SHOOT2 (191)** are both dispatched in
  `client.py` (`elif packet_id in (PacketID.PLO_SHOOT, PacketID.PLO_SHOOT2):`,
  parsed via `parse_shoot(data, v2=...)`). This was previously listed as
  unconfirmed; it is implemented. The exact `constructShootV1()`/
  `constructShootV2()` C++ field layouts have not been independently
  re-derived for this docs pass — see the stub note on
  [Packet Structures: PLO_SHOOT](../protocol/packet-structures.md#plo_shoot-175---shoot-projectile-v1--clver_5_07)
  if byte-level verification is still needed.

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
