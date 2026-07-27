# GS1 client host

This page records the client-side GS1 surface hosted by `pyReborn`. Language
execution belongs to `reborn-protocol`; `pyreborn/gs1_client.py` supplies the
player, NPC, board, rendering, and wire effects that a client script can see.

## Executable verification

The primary suite is `pyReborn/game_tester/gs1_client_conformance.py`. Its 73
case rows each carry a decompiled-client citation. One throwaway `pygserver`
instance supplies a real login, boards, signs, NPC properties, weapon grants,
and a packet sink. The subject is the real headless `GameClient` over a real
`Client`, including the normal NPC loader, touch handler, board patching, HUD
state, and render loop. This verifies integration rather than calling host
methods in isolation.

Weapon cases are delivered as text through `PLO_NPCWEAPONADD`. Every fixture
has an empty, newer `.gs2bc` sibling. `pygserver` otherwise prefers cached
bytecode or invokes its compiler; an empty cache deliberately makes the server
take the classic text path instead of compiling GS1-shaped source and silently
running it in the GS2 VM.

Level NPCs need a narrower seam. `pygserver` sends their image and position but
does not ship `NPCPROP_SCRIPT`; it attaches that source to its server-side GS1
host. The suite therefore inserts source at `client.npcs[id]["script"]`, then
calls the normal `_load_new_npcs()` path. Delivery is simulated, but parsing,
events, host calls, rendering, and assertions all use the real client stack.

Evidence:

- `pyReborn/game_tester/gs1_client_conformance.py:1-48,93-105`
- `pyReborn/game_tester/gs1_client_conformance.py:1135-1180,1184-1235,1255-1272`
- `pygserver/pygserver/gs2.py:349-382`

The older `pyReborn/game_tester/gs1_conformance.py` covers the other boundary.
It runs identical level-NPC scripts on `pygserver` and the `GServer-v2`
`gs2emu` oracle, then compares decoded client-visible effects. It verifies the
server-side host and shared interpreter; it is complementary to, not a
replacement for, the client-host suite.

Evidence:

- `pyReborn/game_tester/gs1_conformance.py:1-32,70-96`

## NPC collision and touch

NPC tile types have precedence over the level board. A `setshape` or
`setshape2` cell is considered first; otherwise a visible, solid NPC uses its
character or image footprint. Explicit shape geometry overrides image
geometry. Image footprints use the `setimgpart` dimensions when present and
the complete image dimensions otherwise. When image pixels are available, a
transparent pixel does not hit; an unavailable opacity result remains solid.

`dontblock` and `dontblocklocal` set only the wall-test flag. They do not erase
the footprint, so touch tests still use it and `blockagain` can make it solid
immediately. Hidden or destroyed NPCs neither block nor touch. A script-only
NPC with no image and no shape has no footprint.

Evidence:

- `pyReborn/pyreborn/gs1_client.py:3319-3365,3367-3384`
- `pyReborn/pyreborn/gs1_client.py:3386-3464`
- `Preagonal/FourPlay/quattroplay/src/TServerLevel.cpp:688-708`
- `pyReborn/game_tester/gs1_client_conformance.py:150-221`

Player-to-NPC touch uses two facing-specific points from `touchtestd`, not the
separate grab/read reach table. For direction `d`, the client probes entries
`d` and `d + 4`, merges the NPC results, and fires each NPC once. The Reborn
host preserves all eight offsets and tests them against the same
transparency-aware footprint used by wall checks.

Evidence:

- `Preagonal/FourPlay/quattroplay/src/TInitStatics.cpp:1492-1501`
- `Preagonal/FourPlay/quattroplay/src/TPlayer.cpp:1792-1818`
- `pyReborn/pyreborn/npc_handler.py:35-50,223-250`
- `pyReborn/game_tester/gs1_client_conformance.py:224-242`

## Timers, animation, and signs

Assigning `timeout` arms one pending event. A value less than or equal to
`0.0001` cancels it for both NPC and weapon contexts. The slot is cleared
before the event runs, so repeating behavior must explicitly re-arm itself.

`setani` always targets the local player, including when called by an NPC
script. `setcharani` is the NPC-targeting command.

`say n` indexes the current level's ordered, zero-based sign list. Coordinate
maps are insufficient because several say-only signs may share a position.
An invalid or out-of-range index displays nothing; `say2` displays literal
text and `message` remains an NPC bubble.

Evidence:

- `Preagonal/FourPlay/quattroplay/src/TScriptSpace.cpp:121-129`
- `pyReborn/pyreborn/gs1_client.py:261-264,849-871`
- `pyReborn/pyreborn/gs1_client.py:1126-1155`
- `Preagonal/FourPlay/quattroplay/src/TInitStatics.cpp:3805-3831`
- `pyReborn/pyreborn/gs1_client.py:1613-1640,3622-3645`
- `pyReborn/game_tester/gs1_client_conformance.py:245-278,758-797`

## Boards and GMAP coordinates

`tiles[x,y]` reads and writes layer zero. A standalone level uses local
`0..63` coordinates. On a GMAP segment, scripts use world tile coordinates
and the host resolves the owning segment; a rectangle may therefore span
several levels. Reads wait for the active board instead of consulting stale
tiles from the previous level. Writes go through the client's board-modify
path so the level cache, active render/collision board, and callback agree.

`updateboard x,y,width,height` and `updateboard2` redraw the current contents
of that rectangle. Their coordinates use the same standalone-or-GMAP frame as
`tiles[]`; GMAP redraws are split into per-segment rectangles.

Evidence:

- `Preagonal/FourPlay/quattroplay/src/TServerLevel.cpp:563-612`
- `pyReborn/pyreborn/gs1_client.py:70-207,806-821,840-848`
- `pyReborn/pyreborn/gs1_client.py:1004-1010`
- `pyReborn/game_tester/gs1_client_conformance.py:798-815`

## Scripted combat and palettes

Scripted combat separates network authority from immediate presentation.
`putbomb` creates the local timed bomb and emits `PLI_BOMBADD` without
consuming player ammunition. `putexplosion` and `putexplosion2` emit
`PLI_EXPLOSION` and also create the local burst, sound, bush effects, and
damage response. The `shoot` family queues `setshootparams`, hands the
projectile and queued parameters to the wire callback, then clears the queue.
Local projectile presentation begins when the corresponding packet is
processed, avoiding a second speculative projectile.

Evidence:

- `Preagonal/FourPlay/quattroplay/src/TServerLevel.cpp:1087,1494`
- `pyReborn/pyreborn/gs1_client.py:1828-1853,1883-1935`
- `pyReborn/pyreborn/gs1_client.py:2189-2202`
- `pyReborn/game_tester/gs1_client_conformance.py:835-847`

`setbackpal filename` is an indexed-palette swap, not a replacement tileset or
RGBA tint. The named image contributes its 256 palette entries while the
existing tile indices remain unchanged; using the stock tileset restores the
stock palette.

Evidence:

- `pyReborn/pyreborn/gs1_client.py:1220-1237`
- `pyReborn/pyreborn/sprites.py:624-648`
- `pyReborn/tests/unit/test_gs1_combat_family.py:445-492`
