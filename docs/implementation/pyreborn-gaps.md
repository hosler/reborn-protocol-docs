# PyReborn Implementation Gaps

This page separates current gaps from completed refactoring work.

## Closed architecture gaps

| Former stale claim | Current state |
|---|---|
| Packet dispatch is a 1,279-line, 90-branch method | Closed: a registry dispatches 93 handlers from seven `pyreborn.handlers` domain modules. |
| `Client` owns about 156 flat attributes | Closed: components in `client_state.py` own the state. A total of 150 historical names remain property aliases. |
| `client.py` is 4,111 lines | Closed: it is now 675 lines. A later refactor split the facade into mixins (`client_actions.py`, `client_appearance.py`, `client_combat.py`, `client_files.py`, `client_gmap.py`, `client_movement.py`, `client_warp.py`). |
| List-server code has private encryption, codec, and G-type readers | Closed: the code imports the shared implementations. It uses `ListServerSession` plus socket/WebSocket adapters. |
| Property parsing is duplicated across six client/server paths | Closed: all use the declarative tables and stream policy in `reborn_protocol.props`. |
| Coordinate terminology is scattered | Closed: `reborn_protocol.coords` owns the level/GMAP/pixel/camera vocabulary. |
| Script-host builtin dispatch is a long conditional | Closed: client and server hosts use registry tables. The client exposes 414 names. |
| pygserver `Player` is a 1,702-line monolith | Closed: the roughly 571-line façade delegates to services and handler mixins. |
| Visibility recipients are selected ad hoc | Closed: `pygserver.audience.AudienceService` owns audience selection. |
| List-server `PacketReader` is duplicated | Closed: the compatibility adapter wraps the shared `reborn_protocol.codec.PacketReader`. |
| GS2 execution is missing | Closed: bytecode is transported, parsed, stored, and executed. |
| Inbound `PLO_SHOOT2` is unverified | Closed at dispatch level: both projectile packet forms are registered and parsed. |
| NC and RC management are incomplete | Closed: their packet families have dedicated clients and coverage harnesses. |

## Open implementation gaps

### List-server top-level text codepage

Server-list entry fields use the correct cp1252 reader. But
`pyreborn.listserver.build_response` still decodes `PLO_STATUS`, `PLO_SITEURL`,
`PLO_UPGURL`, and `PLO_ERROR` bodies as latin-1. This is a live mismatch for
bytes such as `0x92`. Those four paths should use cp1252 too.

### Duplicated live builtin behavior

Approximately 57 builtin names exist in both the client host and pygserver's
server host. They were deliberately not unified during the registry refactor.
For some names, both implementations are live and differ. A person must make
compatibility decisions and run targeted oracle tests.

### GEN_6

`ENCRYPT_GEN_6` remains unimplemented. The reference server also leaves the
relevant packet family unimplemented, so this is a protocol-wide limit rather
than a PyReborn-only regression.

### GS1 visual commands

The GS1 interpreter still lacks `hidepoly`. This affects rendering, not framing.

`changeimgpart`, `showpoly`, `drawoverplayer` and `drawunderplayer` all landed
with the Bomber Arena lobby work. They live in
`pyreborn/gs1_client/host_commands_layer.py` and
`pyreborn/gs1_client/host_commands_npc.py`, and
`game_tester/gs1_client_conformance.py` pins them.

### Ground-item art

The `LevelItemType` to `pics1.png` crop table is incomplete. Item packets work,
but some drops use placeholder art.

### Corrupt board diagnostics

If level-board decompression fails, the code intentionally returns an empty
64×64 board. The fallback is safe. But callers receive no structured error
and can mistake corrupt input for a genuinely empty level.

### Byte-level projectile oracle

The code handles both `PLO_SHOOT` and `PLO_SHOOT2`. But an independent
byte-for-byte oracle pass must still check their complete field layouts. This
is a documentation confidence gap, not a missing dispatch path.

## Verification guidance

Use `/usr/bin/python3.13` for the test suites. The system `python3` is 3.14 and
does not have Hypothesis installed.

```bash
cd ../pyReborn
/usr/bin/python3.13 -m pytest
/usr/bin/python3.13 -m game_tester
```

For property formats, consult [Packet Structures](../protocol/packet-structures.md)
and [NPC Properties](../protocol/npc-properties.md) rather than duplicating
their descriptor tables here.
