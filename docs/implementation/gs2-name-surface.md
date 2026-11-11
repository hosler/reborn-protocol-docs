# GS2 script-visible name surface: reference vs. ours

This page lists the **official** GS2 name surface. This surface contains every
script-visible free function, object property, and object method that the
reference client's interpreter registers. The page compares this surface with what
`reborn-protocol/reborn_protocol/gs2/vm.py` and
`pyReborn/pyreborn/gs2_client/` answer today.

## Status (2026-07-26, re-checked 2026-11-11)

This started as a **specification for implementers** with nothing implemented.
That is no longer true. The tiers below still use the future tense. Read them
as the *survey*. Read this section as the list of implemented items.

**Landed:**

- All of **T1** (44 names): every string-typed name the reference registers
  now answers `""`-or-better on globals, `player`, other players, an NPC
  `this`, `level`, `showimg` handles and `new`-ed objects
  (`pyReborn/pyreborn/gs2_client/`).
- All five items under **Things our implementation gets actively wrong**,
  except that item 3 landed on the VM side rather than the host: `player.nick`
  offers read-only access, `client`/`clientr`/`serverr` resolve player properties (reads
  only — a write through them stays a flag write), `level` is a real object
  with all 14 chain properties plus the `test*` probe family, and `levelname`
  receives an answer alongside our own `player.level` extension.
- The **T2 top-20**, including the clamped/validated setters (`freezetime`,
  `zoomfactor`, `selectedweapon`, `selectedsword`, `glovepower`).
- **T3's `TGraalVar` root methods**: `addarray`/`sortbyvalue` on the VM side
  (`reborn_protocol/gs2/vm.py`), and `savelines`/`sortascending`/
  `sortdescending`/`settimer` on the host, which had to move off their
  `isinstance(obj, list)` gate. The system consults the host *before* the VM.
  Thus, a gate that misses passes the VM's root surface and ends at `0.0`.
- The **`GuiTextListCtrl` row API** (T3's GUI section): `rowcount`,
  `isrowselected`, `isidselected`, `getrownumbyid`, `getselectedid`,
  `getselectedids`, `getselectedrows`, `getrowatpoint`, `getrowidatpoint`,
  `findtextid`, `setselectedbytext`, `setselectedbyids`, `setselectedrows`,
  `clearselection`, `insertrow`, `removerow`, `removerowbyid`, `setrowbyid`,
  `setrowactivebyid`, `makevisible`, `makevisiblebyid`, the `selected*`
  properties and the sort enums. Plus `resize` on every control and `reflow`
  on `GuiMLTextCtrl` (**not** on the text list, where a call-count sweep had
  placed it).

**Still open:**

- The GUI control tables are **no longer sampled**. The audit examined the
  remaining 21 classes plus `GuiControlProfile` entry-by-entry. The results are in
  {doc}`gs2-gui-core-controls`, {doc}`gs2-gui-layout-controls` and
  {doc}`gs2-gui-remaining-controls`. The per-class caveats now live there. The
  counts in the table below predate that audit and undercount.

  That audit also established that **this oracle is not the whole client**:
  `FourPlay/libqplay_symbols.txt` carries 24 `Gui*` classes while the Era
  build's `graal-revlib-osx/docs/symbol_dump.log` carries 43. Thus, absence
  from FourPlay does not show that a name does not exist.
  `GuiTabCtrl`, `GuiTreeViewCtrl`, `GuiAccountPasswordCtrl` and
  `GuiMLTextEditCtrl` are all real, all used by Login content, and all absent
  here.
- The **T2 runners-up** list below has landed, apart from the names named at
  the end of this bullet: `getkeycode`/`keyname`/`keyname2`, `findlevel`,
  `findnpcbyid`, `findani`, `format2`, `getascii`, `strcmp`,
  `getnearestplayer`, `trace`, `aindexof`, `randomstring`, `hasfunction`,
  `level.findareanpcs`/`getmappartfile`, the attachment read-back
  (`attachedtoobject`), NPC geometry and `peltwith*`, and the
  `isinvincible`/`isinvincible2`/`paused`/`reading`/`isjumping`/`map`/
  `isobserver` set are all registered in `gs2_client/` (`host_bare.py`,
  `host_objmethods.py`, `objects.py`, `objects_player.py`). Still unregistered
  in the host: `getfunctions` (the VM only carries it in its name set),
  `preloadimage`, `resetimageanimation`, `preloadanimation`, and an NPC
  `layer`.
- **T3 beyond the root methods and the text list** (the `level.putbomb2`,
  emoticon/sign UI, and `level.test*` probes have since landed; see the T3 and
  T4 lists), and the remainder of **T4**.

### Method caveat: this page was built top-down only

I found every name below in the reference's *registration tables*. I did not
search the production script corpora for names that they use. That gap hid
real bugs. See "Bottom-up findings" at the end.

## Where the oracle is and how it was read

The oracle is the reference client's interpreter. The checkout at
`Preagonal/FourPlay/quattroplay/` contains its C++ decompilation. It outranks
GServer-v2, the C# client, and every doc in this tree.

Static tables declare the names in one part of the code.

```c
typedef struct TPropertyPropDef {          // include/TPropertyPropDef.h
    const char* propertyName;
    bool        alreadyEncoded;
    char        returnType;   // 's' string, 'd'/'f' float, 'i'/'u' int,
                              // 'b' bool, 'o' object, 'v' void
    void*       inPtr;        // getter  (nullptr => not readable)
    void*       outPtr;       // setter  (nullptr => READ-ONLY)
    const char* propertyName2;
    PropType    propType;
} TPropertyPropDef;

typedef struct TPropertyFuncDef {          // include/TPropertyFuncDef.h
    const char* propertyName;
    bool        alreadyEncoded;
    char        returnType;
    const char* params;       // one char per parameter, "X" = varargs
    void*       functionPtr;
    const char* functionName;
    bool        test7;
} TPropertyFuncDef;
```

`TScriptProperty::addProps` / `addFuncs` installs each table. The first
argument specifies the *scope*:

- `addProps(nullptr, …)` installs onto `TScriptUniverse_properties` — the
  **global** name surface (`src/TScriptProperty.cpp:27-49`).
- `addProps(this, …)` installs onto one class's `TProperties` — a **per-object**
  surface.

The `TProperties(type, parentType)` constructor specifies a class's parent
chain. `TProperties::compileProperties()` first copies the parent's table.
It then **replaces** each entry that the child declares again
(`src/TProperties.cpp:108-129`). The child wins.

Chains that matter:

| Script name | C++ class | Chain (child → root) |
| --- | --- | --- |
| `player` (local) | `TPlayer` | TPlayer → TServerPlayer → TGaniObject → TGraalVar |
| other players (`findplayer`, `findnearestplayers`) | `TServerPlayer` | TServerPlayer → TGaniObject → TGraalVar |
| `this` in an NPC / weapon script | `TServerNPC` | TServerNPC → TServerPlayer → TGaniObject → TGraalVar |
| `level` | `TServerLevel` | TServerLevel → TGraalVar |
| a `showimg` handle | `TShowImg` | TShowImg → TLevelObject → TGraalVar |
| GUI controls | `Gui*Ctrl` | (control) → … → GuiControl → TGraalVar |

`TScriptMachine::resolveObjectMember` resolves bare names
(`src/TScriptMachine.cpp:5042`). Fixed aliases live at the top of it:

| Name | Resolves to | Line |
| --- | --- | --- |
| `temp` | the current call-stack entry (or the universe) | `TScriptMachine.cpp:5071` |
| `params` | the parameter array | `:5079` |
| `this` | the executing script object | `:5085` |
| `thiso` | ditto, object form | `:5094` |
| `player` | `actionplayer` | `:5098` |
| `playero` | `executingplayer` | `:5102` |
| `level` | `actionplayer->serverLevel` | `:5105` |
| `client`, `clientr`, `serverr` | **`executingplayer`** | `:5123-5130` |

Everything else walks: `with` targets → call-stack locals → `this` → the
current level → the universe globals.

### Counts

| Category | Distinct official names | We answer |
| --- | ---: | ---: |
| Global functions (all `addFuncs(nullptr, …)` tables) | 459 | 154 |
| Global properties (all `addProps(nullptr, …)` tables) | 106 | 23 |
| `player` properties (whole chain) | 107 | 34 |
| other-player properties | 85 | 32 |
| NPC `this` properties | 102 | 16 |
| `level` properties (whole chain) | 14 | 14 |
| `player` methods (whole chain) | 59 | 23 |
| NPC `this` methods | 109 | 79 |
| `level` methods | 62 | 29 |
| GUI control properties (**sampled**, see below) | 189 | not audited |
| GUI control methods (**sampled**) | 123 | 129 |

The `level` and GUI-method cells were recounted on 2026-11-11. The other "We
answer" cells are the pre-landing snapshot and were not recounted. The GUI
method cell (129) is the union of every control class's method names. It
includes names outside the sampled reference set, so it is not a coverage
figure against the 123.

The extraction found **1474** table entries across 43 `*Properties.cpp` files.
It also examined `TInitStatics.cpp`, `TClient.cpp`, and the `src/gui/` tree. Extraction is
complete for every table whose declared array size is a literal. All tables
use a literal, and each declared size matched the entry count.

### Honest coverage statement

- The audit covers all global functions and properties. It also covers all
  `player` / other-player / NPC / `level` property and method chains.
- The GUI control tables (`src/gui/*Properties.cpp`) were **sampled** when this
  page took shape. At that time, the audit had read only `GuiControl`'s own
  table entry-by-entry. Thus, the GUI counts below are not a completeness
  claim. A later audit examined the remaining classes. See the three
  `gs2-gui-*-controls` pages, which supersede the GUI rows here.
- Roughly 20 % of property entries and 9 % of function entries carry a **raw
  address** (`(void*)0x27f150`) instead of a named function, because the
  decompilation did not recover those bodies and no symbol map exists in
  `asm/`. For those, this page records the **registered type and read/write
  flags only**. The T1 rule below uses only this information. The page says
  when this limit applies. It does not assert semantics for an unread body.

---

## The unanswered-name hazard (why T1 exists)

Three verified facts cause a silent-wrong-answer bug:

1. A name that resolves to nothing becomes **Number 0.0**:
   `TScriptStackEntry::resolve()` calls `makeProperty()`, and when both the
   property and the variable come back null it sets
   `this->type = Number; this->doubleVal = 0.0;`
   (`src/TScriptStackEntry.cpp:228-229`).
2. Comparing a Number against a String converts the **string** to a float:
   `return compareNumberValues(left->doubleVal, strtofloat(right->stringVal));`
   (`src/TScriptMachine.cpp:1463`).
3. `compareNumberValues` calls values equal within 1e-4
   (`src/TScriptMachine.cpp:37-43`).

`strtofloat("anything")` is `0.0`, so an unanswered name compares **equal to
every non-numeric string literal**. Comparing two Strings instead goes through
`compareIgnoreCase` (`src/TScriptMachine.cpp:1450`) and behaves.

Therefore: **any name the reference registers with `returnType == 's'` that we
leave unanswered is a latent wrong-answer bug**, because our host returns
`None`, which the lattice resolves to Number 0.0 for exactly the same reason
(`reborn_protocol/gs2/values.py` module docstring, "NUMBER … and None").

This is not hypothetical. Two live outages came from it: `serverstartconnect`
(unanswered → `serverstartconnect == "skills"` true → the serverlist request
the code skipped) and `player.platform` (unanswered → 48 `== "linuxstream"` tests
per session all true). We now answer both as `""`. Comments describe the fixes
in `gs2_client/host_objects.py` (`serverstartconnect`) and
`gs2_client/objects_player.py` (`player.platform`).

Note that "answer a string" does **not** mean "answer `""`". Several globals
are pre-seeded with non-empty defaults, e.g. `spritesimage` = `"sprites.png"`
and `statusimage` = `"state.png"` (`src/TInitStatics.cpp:4809-4813`), and
`servername` = `"Offline"` (`:4930-4932`). The pre-allocated-`TString` globals
are all created in the `*_initStaticVars()` functions. The ones for the
serverlist are at `src/TInitStatics.cpp:4928-4937`.

---

## T1 — latent wrong-answer hazards (these are bugs)

Every entry: official `returnType` is `'s'`, we answer nothing, so the read
yields Number 0.0 and every `== "literal"` against it is true.

### Global (bare-name) reads

| Name | R/W | Citation | Semantics |
| --- | --- | --- | --- |
| `emoticonchar` | RO | table `src/TInitStatics.cpp:2746`, getter `:2371-2376` | `TInput::emoticonchar` stringified as an integer |
| `spritesimage` | RW | table `:2779`, getter `:2674`, default `:4810-4811` | sprite-sheet filename. Defaults to `"sprites.png"` |
| `statusimage` | RW | table `:2780`, getter `:2678`, default `:4812-4813` | status-bar image filename. Defaults to `"state.png"` |
| `downloadfile` | RO | `src/TFileDownload.cpp:69` | file currently downloading |
| `lastdownloadfile` | RO | `src/TFileDownload.cpp:70` | last completed download |
| `disabledsoundeffects` | RW | `src/sound/TSounds.cpp:214` | CSV of suppressed effect names |
| `allowedimageanimations` | RW | `src/TTexture.cpp:70` | CSV allow-list for animated images |
| `installedlanguages` | RO | `src/TTranslations.cpp:39` | CSV of installed translation languages |
| one plugin-cookie option | RO | `src/TOptions.cpp:457` | web-plugin session cookie (name spelled verbatim at that line. It contains a term the naming policy scrubs, so it is not repeated here) |
| **six** `$pref::`-namespaced string options | RW | `src/TOptions.cpp:471,472,473`, `src/TFontOptions.cpp:124,142`, `src/TTranslations.cpp:38` | GUI-style, screenshot-format, font and language preferences (same spelling caveat). An earlier revision of this page said *five* while listing six lines. Each of those six is a distinct registered name. |

### Every object (the `TGraalVar` root — `player`, other players, NPCs, `level`, every `new`-ed object)

| Name | R/W | Citation | Semantics |
| --- | --- | --- | --- |
| `name` | RW | table `src/TGraalVarProperties.cpp:627`, getter `:147-152`, setter `:154-` | the object's own name. For `level` it is the **lower-cased level filename**: `TServerLevel::TServerLevel` passes `TFiles::lowerCaseFilename(levelName)` to the `TGraalVar` base (`src/TServerLevel.cpp:352-354`). The setter is a no-op once code sets a name and links the object (`:156-158`). |

`level.name == "somelevel.nw"` is a common script idiom and today evaluates
true in **every** level.

### `player` and other players

| Name | R/W | Citation | Semantics |
| --- | --- | --- | --- |
| `levelname` | RO | table `src/TServerPlayerProperties.cpp:573`, getter `:181` | `player->levelname` |
| `language` | RO | table `:555`, getter `:176` | the player's language token |
| `languagedomain` | RO | table `:564`, getter `:177-180` | `TTranslations::getLanguageDomain(language)` |
| `chatoffset` | RW | table `:339` | raw-address getter. Type only |
| `horseimg` | RW | `src/TPlayerProperties.cpp:117` (local), `src/TServerPlayerProperties.cpp:429` (remote) | raw-address getter. Type only. We answer this on NPCs but not on players. |
| `alliedguilds` | RW | `src/TPlayerProperties.cpp:54` | raw-address getter. Type only |
| `letters` | RW | `src/TPlayerProperties.cpp:234` | raw-address getter. Type only |
| `aniparams` | RO | `src/TGaniObjectProperties.cpp:55` | raw-address getter. Type only |
| `rotationcenter` | RW | `src/TGaniObjectProperties.cpp:208` | raw-address getter. Type only |

### NPC `this` — additionally

Our `_NPC_THIS_ATTR` (`gs2_client/objects.py:26-41`) covers 14 names. These
string-typed inherited ones are not among them:

| Name | R/W | Citation |
| --- | --- | --- |
| `account` | RO | `src/TServerPlayerProperties.cpp:267` |
| `communityname` | RO | `:330` |
| `guild` | RO | `:384` |
| `platform` | RO | `:627` |
| `head` | RW | `:393` |
| `body` | RW | `src/TGaniObjectProperties.cpp:109` (getter `:33-41`) |
| `shield` | RW | `src/TGaniObjectProperties.cpp:181` |
| `sword` | RW | `src/TGaniObjectProperties.cpp:190` |

**Verified alias pairs** (identical getter *and* setter pointers in the same
table, so they are the same slot under two names):

- `head` / `headimg` — `src/TGaniObjectProperties.cpp:154` and `:163`
- `body` / `bodyimg` — `:109` and `:118` (both `propfun_ganiobject_body_r/_w`)
- `shield` / `shieldimg` — `src/TPlayerProperties.cpp:297` and `:306`
- `sword` / `swordimg` — `src/TPlayerProperties.cpp:333` and `:342`
- `maxhp` / `fullhearts` — `src/TServerPlayerProperties.cpp:585` reuses
  `propfun_serverplayer_fullhearts_r`

So `player.shield` is the shield **image name**, not the shield power. Our
mapping already gets this right (`_PLAYER_MEMBER_ATTR` → `shield_image`). The
NPC side does not have it at all.

### `showimg` handles (sampled)

`TShowImgProperties` registers 11 string-typed properties in the range
`src/TShowImgProperties.cpp:198-558` — `font` (`:198`), `shadowoffset`
(`:207`), `shadowcolor` (`:216`), `style` (`:225`), `text` (`:234`), `code`
(`:270`), `position` (`:360`), `rotationcenter` (`:387`), `attachoffset`
(`:477`), `movementvector` (`:531`), `sound` (`:558`). The class registers
**13** in total: `ani` (`:144`) and `image` (`:171`) sit above that range and
have string types too. Our `_ShowImgObject` (now `_LayerImage`,
`gs2_client/objects.py:302-343`) stores unknown keys on the record so writes
round-trip, but an **unset** one still reads `None` → Number 0.0. Lower
priority than the player/level cases (reading back a never-written showimg
string is rare), but the same class of bug.

**T1 total: 44 names** — 15 global (8 tabulated individually, plus the
plugin-cookie option and the six `$pref::` string options), 1 universal
(`name`, which lands on every object including `level`), 9 on
`player`/other players, 8 more that only bite on an NPC `this`, and the 11
`showimg` strings.

---

## T2 — needed by real scripts for gameplay or rendering

Ranked. "Source" says whether pyReborn can answer from data it already holds,
needs a new wire field, or cannot.

| # | Name | Type | Citation | One-line semantics | Source |
| ---: | --- | --- | --- | --- | --- |
| 1 | `level.width`, `level.height` | i RO | table `src/TServerLevelProperties.cpp:107` / `:62`, getters `:43-53` / `:6-16` | `64` for a plain level. On a gmap, the map's segment count `<< 6` | have |
| 2 | `level.name` | s RW | see T1 | lower-cased level filename | have |
| 3 | `player.levelname` | s RO | `src/TServerPlayerProperties.cpp:181` | current level filename | have |
| 4 | `testplayer(x,y)`, `level.testnpc(x,y)` | i | `src/TInitStatics.cpp:4278` (body `:3880-3900`), `src/TServerLevelProperties.cpp:263` | index of the player / blocking NPC covering the tile, `-1` on a miss | **Fixed.** `gs1_client/host_functions.py:172-213` `_test_at` implements the probe, and `_GS1_LEVEL_PROBES` now carries `testnpc`/`testplayer`, which `_GS1_FUNCTIONS` unions in (`gs2_client/registry.py:77-85`). Formerly they were missing from that table, so every GS2 spelling read 0.0 — "index 0", a hit on the first NPC, for a probe whose miss value is negative. |
| 5 | `level.testsign`, `testitem`, `testbomb`, `testexplo` | i | `src/TServerLevelProperties.cpp:254`, `:245`, `:227`, `:236` | same probe shape for the other level-object kinds (raw-address bodies. Signature only) | have (level object lists) |
| 6 | `player.glovepower` | i RW | `src/TServerPlayerProperties.cpp:366` | glove power | have (`playerglovepower`) |
| 7 | `player.swimming`, `.onhorse`, `.online` | b RO | `src/TPlayerProperties.cpp:324`, `:261`, `:270` | state flags (raw-address bodies. Type only) | have (GS1 `playerswimming` / `playeronhorse` / `playeronline`) |
| 8 | `player.freezetime` | d RW | table `src/TPlayerProperties.cpp:99`, getter `:11-16`, setter `:18-37` | freeze remaining in **seconds**, and **`-1.0`, not 0, when not frozen** (`DOUBLE_004023f0 = -1.0`, `src/TInitStatics.cpp:1269`). The counter runs at 20 ticks/second (`DOUBLE_004023f8`, `:1264`), so the setter's 600-tick clamp is 30 s (`DOUBLE_00402518`, `:1254`). It quantises with `int(seconds * 20 + 1e-4)`, ignores writes on 2002-era servers, and cancels the action mode | have (`playerfreezetime`) |
| 9 | `player.hp`, `player.maxhp` | d/i | `src/TPlayerProperties.cpp:135`, `src/TServerPlayerProperties.cpp:582` | `maxhp` shares `fullhearts`' getter (`:585`) | have |
| 10 | `player.hurt`, `.hurted`, `.hurtdx`, `.hurtdy`, `.hurtpower` | b/b/d/d/d RO | `src/TPlayerProperties.cpp:144`, `:171`, `:153`, `:162`, `:180` | last-hit feedback (raw-address bodies. Type only) | partial — `PLO_HURTPLAYER` carries dx/dy/power |
| 11 | `iscarrying` | b RO | table `src/TInitStatics.cpp:2754`, getter `:2418-2421` | the active player carries something | have (GS1 `carrying`) |
| 12 | `isonmap` | b RO | table `:2756`, getter `:2428-2431` | the acting player is on a gmap | have |
| 13 | `levelorgx`, `levelorgy` | d RO | table `:2757` / `:2758`, getters `:2445-2455`, helper `:2433-2443` | **local** x/y of the acting NPC attachment. For the player-attached NPC, this is the active player's attach target. `0` when nothing has an attachment. Not a level origin. | partial (attachment state) |
| 14 | `selectedweapon` | i RW | table `:2778`, getter `:2657-2660`, setter `:2662-2668` | the active player's weapon index, `-1` if none. The setter checks bounds against the weapon array | have (inventory selection) |
| 15 | `selectedsword` | i RW | table `:2777` | selected sword index | have |
| 16 | `mousebuttons` | i RO | table `:2760`, getter `:2471-2474` | button mask, forced to `0` when the game viewport lacks focus. Also `mousebuttonsglobal` (`:2759`), `rightmousebutton` (`:2766`), `middlemousebutton` (`:2764`), `mousewheeldelta` (`:2767`) and the four `*global` variants | have (pygame) |
| 17 | `worldx(sx,sy)`, `worldy(sx,sy)` | d | table `:4284` / `:4285`, bodies `:3906-3921` | inverse of `screenx`/`screeny`: floor the argument after adding 1e-4, then `screenToWorldX/Y`. We already implement `screenx`/`screeny`. | have |
| 18 | `player.zoomfactor` | f RW | table `src/TPlayerProperties.cpp:351`, getter `:39-42`, setter `:44-50` | per-player camera zoom, clamped to a fixed range | have (camera) |
| 19 | `player.defaultwalkspeed`, `.diagonalwalkspeed` | d RW | `src/TPlayerProperties.cpp:81`, `:90` | movement speeds (raw-address bodies. Type only) | have (movement code) |
| 20 | gani display transform on players **and** NPCs: `rotation`, `zoom`, `stretchx`, `stretchy`, `red`, `green`, `blue`, `alpha`, `mode`, `useowncenter` | f/i RW | `src/TGaniObjectProperties.cpp:199`, `:244`, `:217`, `:226`, `:253`, `:262`, `:271`, `:280`, `:289`, `:235` | per-object render transform and colour/blend. Our equivalents exist only for showimg records | have (renderer) |

Runners-up, same tier:

- `getkeycode(name)` (`src/TInitStatics.cpp:4213`, body `:3394-3397`), `keyname(i)` / `keyname2(i)` (`:4229` / `:4230`) — code at `src/TInitStatics.cpp:4825-4829` builds the key-name table. `TInput::getKeyCode` searches it (`src/TInput.cpp:310-324`). We have the map. Only the lookups are missing.
- `findlevel(name)` (`:4206`, body `:3341-3356`) — lower-cased filename match over the loaded maps, then `getLevel`.
- `findnpcbyid(id)` (`:4207`, body `:3358-3361`), `findani(name)` (`:4205`, body `:3336-3339`).
- `format2(fmt, paramArray)` (`:2307`, body `:2203-2209`) — printf-style formatting with an array of parameters.
- `getascii(s)` (`:2308`, body `:2211-2216`) — first byte of the string, `0` for empty.
- `strcmp(a,b)` (`:2317`, body `:2267-2270`) — three-way, **case-insensitive**. Do not implement it as a case-sensitive `strcmp`.
- `getnearestplayer(x,y)` (`:2293`) — the index form of `findnearestplayer`.
- `trace(s)` (`:2292`) — registered as an alias of `echo`, same function pointer.
- `aindexof(value, array)` (`:2282`, body `:1841-1851`) — index of a **number** in an array. Returns `0` (not `-1`) when the array is null.
- `randomstring(csv)` (`:2316`, body `:2251-2265`) — picks a random CSV field. As an exception, it removes the last character from a string ending in `,` and returns that string instead.
- `hasfunction(name)` on any object (`src/TGraalVarProperties.cpp:341`), `getfunctions()` (`:332`).
- `level.findareanpcs(x,y,w,h)` (`src/TServerLevelProperties.cpp:128`), `level.getmappartfile(x,y)` (`:119`) — raw-address bodies. Signature only.
- `player.attachedtoobject` (`src/TServerPlayerProperties.cpp:294`, RW object), `.attached` (`:285`), `attachid` / `attachtype` (`src/TGaniObjectProperties.cpp:73`, `:82`) — we can *set* attachment (`attachplayertoobj`) but not read it back.
- NPC geometry and layering: `width` / `height` (`src/TServerNPCProperties.cpp:1233`, `:1044`), `layer` (`:1116`), `isblocking` (`:1098`), `isblockingprojectiles` (`:1107`), `actionplayer` (`:1026`), `npcsindex` (`:1125`), and the six `peltwith*` flags (`:1134`-`:1179`).
- `player.isinvincible` / `isinvincible2` (`src/TPlayerProperties.cpp:198`, `:207`), `player.paused` (`:279`), `player.reading` (`:288`), `player.isjumping` (`:126`), `player.map` (`:243`), `player.isobserver` (`:225`, body `src/TPlayerProperties.cpp:7-10`: true only in ghost mode 2).
- `preloadimage(file, b)` / `resetimageanimation(file)` (`src/TTexture.cpp:74`, `:75`), `preloadanimation(name)` (`src/TGraalAni.cpp:586`).

---

## T3 — cosmetic or rare

- `TGraalVar` object methods registered on **every** object that we answer only
  in a narrower form (see "Actively wrong" below for the exact mismatch):
  `savelines`, `savestring`, `savevarstoarray`, `loadlines`, `loadstring`,
  `loadini`, `loadjson`, `loadjsonfromstring`, `savejson`, `savejsontostring`,
  `sortascending`, `sortdescending`, `subarray2`, `insertarray`,
  `addarraymember`, `addnamedstring`, `getarraymember`, `copyfrom`,
  `clearemptyvars`, `getstaticvarnames`, `geteditvarnames`, `ignoreevent`,
  `ignoreevents` — `src/TGraalVarProperties.cpp:215-593`.
- Emoticon and sign UI on the local player: `showemoticon`,
  `showemoticonbykey`, `hideemoticon`, `scrollsign`, `hidesign`, `getnohit` —
  `src/TPlayerProperties.cpp:381-426`. All six are now implemented
  (`gs2_client/host_objmethods.py`, `_obj_player_display`).
- Particle system: `TParticleEmitterProperties` (28 properties, 8 methods) and
  `TParticleModifierProperties` — `src/TParticleEmitterProperties.cpp:5-323`.
- Crypto helpers beyond the three we answer: `checksum`, `des_decrypt`,
  `rsa_*`, `rc4_cipher`, `aes_encrypt` / `aes_decrypt`, `sha256` —
  `src/TEncryption/TEncryption_WolfSSL.cpp:23-34`.
- Unicode helpers: `convertlatintoutf8`, `convertutf8tolatin`, `isstringutf8` —
  `src/TUnicode.cpp:19-21`.
- Time formatting: `formattimestring`, `converttimetostring`,
  `convertstringtotime`, `getutctime` — `src/TTime.cpp:64-67`.
- Sound extras: `issoundplaying`, `ismusicplaying`, `stopmusic`, `playlooped2`,
  `setsoundpitch`, `setsoundpitchbynote`, `musicpos`, `musiclen`,
  `soundoffscreendistance` — `src/sound/TSounds.cpp:222-271`.
- `level.putbomb2` (`src/TServerLevelProperties.cpp:146`) — the four-argument
  form. Landed: `gs2_client/host_objmethods.py` registers `putbomb` and
  `putbomb2`.
- `parsejson(obj, text)` — `src/TGraalVarProperties.cpp:613`.
- `chessrating` helpers `updateratings`, `updateratingdeviation` —
  `src/TInitStatics.cpp:6090-6091`.

### GUI controls (sampled — not a completeness claim)

The `src/gui/` tree registers **189 distinct property names** and **123
distinct method names** across 24 control classes plus `GuiControlProfile`. Our
`control_method_names()` in `pyReborn/pyreborn/game/gs2_gui/factory.py` now
returns 129 names (the original sample named 36 of the 123).
`GuiControlProperties::propDefs` alone is 55 entries
(`src/gui/GuiControlProperties.cpp:895` is the constructor. The table precedes
it), of which 13 have string types: `bounds`, `clientextent`, `color`, `cursor`,
`extent`, `hint`, `horizsizing`, `minextent`, `minsize`, `position`,
`rotationcenter`, `style`, `vertsizing` — each a T1 candidate on any control
that never gets it written. A full GUI audit is out of scope for this pass and
should be its own wave.

---

## T4 — not implementable client-side

The reference registers these names, which an implementer will otherwise waste time on.

- **`TClient::funcDefs`, 85 entries** (`src/TClient.cpp:4586-4670`). Every one
  but `triggerserver` is a `tclient_*` packet-injection entry point
  (`tclient_setnpcprops`, `tclient_setlevelboard`, `tclient_addbomb`, …). They
  exist so a *scripted network layer* can feed the client decoded packets. They
  are not a gameplay surface, and pyReborn's decoder occupies that role.
- **`main_android_funcDefs`, 44 entries** (`src/TInitStatics.cpp:5977-6020`):
  Tapjoy, Google Play billing, Facebook, Distimo, Fabzat, TrialPay, Android
  accelerometer and virtual keyboard.
- Installer / patcher: `TUpdatePackage` (8 functions, 19 properties),
  `TFileDownload`'s `adventure_*` set, and the four desktop-installer entry
  points at `src/TInitStatics.cpp:4154-4160` (`adventure_addmenulink`,
  `adventure_adddesktopicon`, an installer call whose registered name contains
  a term the naming policy scrubs, and `adventure_getinstallationpath`).
- Local-filesystem scripting: most of `TFileScripting::funcDefs`
  (`src/TFileScripting.cpp:462-488`) — `deletefile`, `adventure_setfilecontent`,
  `adventure_getfolder`, `adventure_opendefaultviewer`. Sandbox policy, not
  capability.
- Raw sockets and HTTP: `TSocketProperties` (15 properties, 5 methods),
  `TSocketConnection`, most of `THTTPRequest::funcDefs`
  (`src/THTTPRequest.cpp:126-135`). We deliberately stub the URL surface.
- Video playback: `openvideoplayer`, `stopvideoplayer`, `isvideoplayeropen`
  (`src/TInitStatics.cpp:4186-4188`).
- Premium/offline gating: `ispremiumversion`, `isdemoversion`,
  `getclassicversion` (`src/TGameEnvironment.cpp:77-104`), `isofflinemode`,
  `ischosenofflinemode` (`src/TInitStatics.cpp:4185`, `:4189`).
- Desktop preference storage (`TOptions::propDefs`, 17 entries,
  `src/TOptions.cpp:457-473`) and `TFontOptions` / `TTranslations` prefs.
- Screenshots: `makescreenshot2`, `makescreenshotgame`, `makescreenshotfull`
  (`src/TInitStatics.cpp:4234-4236`) — implementable, but only as a policy
  decision about writing files. Now implemented: `gs2_client/host_bare.py`
  (`_bi_make_screenshot`) writes under the prefs `screenshots` directory.

---

## Things our implementation gets actively wrong

Each verified against the oracle table entry, not inferred. All five landed
(see Status above); this section keeps the historical bug description because
it explains why the fix looks the way it does.

1. **`player.nick` was writable for us, read-only in the reference. Fixed.**
   `TPlayerProperties`'s own entry registers `nick` with a getter and a
   **`nullptr` setter** (`src/TPlayerProperties.cpp:252-258`), and the child
   table replaces the parent's read/write `nick`
   (`src/TServerPlayerProperties.cpp:609`) per
   `TProperties::compileProperties` (`src/TProperties.cpp:117-129`). So on the
   **local** player a write was a no-op; on a **remote** `TServerPlayer` it was
   not. Our `_PlayerObject.set` used to write through `_PLAYER_MEMBER_ATTR` in
   both cases. It now checks `_PLAYER_READONLY` (`{"nick", "maxhp",
   "levelname"}`, `gs2_client/registry.py:143`) first and no-ops the write on
   the local player before it reaches `_PLAYER_MEMBER_ATTR`
   (`gs2_client/objects_player.py`, the `_PLAYER_READONLY` gate). Remote players are plain
   `GS2Object`s (`gs2_client/runtime.py`,
   `ClientGS2.script_player_object`), so a write to one still lands,
   preserving the reference's local/remote asymmetry.

2. **`client` / `clientr` / `serverr` were a standalone flag store for us;
   the reference resolves all three to the executing PLAYER object. Fixed.**
   `resolveObjectMember` binds all three (and `player`, `playero`) to
   `executingplayer` (`src/TScriptMachine.cpp:5123-5130`). Flags are that
   object's dynamic vars, so `client.<anything the player class registers>`
   resolves against the player property table. Our `_obj_flag_scope` used to
   return a dedicated flag object with no player fallback, so `clientr.x`,
   `client.nick`, `serverr.account` and friends read 0.0 instead of the
   player's value. `_FlagScopeObject.get` now falls back to a `player` object
   handed in by `flag_scope_object()` once the flag store says it does not
   have the name (`gs2_client/objects_player.py:63-133`,
   `gs2_client/runtime.py`, `ClientGS2.flag_scope_object`). Only reads take the fallback — a write
   through `client`/`clientr`/`serverr` still lands as a flag write, and
   `server` (which the reference does not alias to the player) gets no
   fallback at all.

3. **The reference registers `savelines`, `sortascending`, `sortdescending`, `settimer`
   on `TGraalVar` — i.e. on *every* object — but we used to answer them only
   in a narrower form. Fixed on the host side (the VM-side `addarray`/
   `sortbyvalue` widening is covered in Status above).** `savelines` /
   `sortascending` / `sortdescending` used to live in `_GS2_LIST_METHODS`,
   gated on `isinstance(obj, list)`. `settimer` lived in `_GS2_BARE`, reachable
   only as a bare call. `this.savelines("f.txt", 0)` and `this.settimer(1)` are
   valid official spellings (`src/TGraalVarProperties.cpp:494`, `:548`) that
   used to return 0.0 for us. All four now live in `_GS2_OBJ_METHODS`, which
   the host dispatches for any object regardless of type
   (`gs2_client/host_objmethods.py`: the `sortascending`/
   `sortdescending` handler, `savelines`, and the `settimer` handler); the array-only
   check moved inside each handler instead of gating dispatch, so a
   non-array object is now *answered* (with 0.0) rather than falling through
   unhandled. `sortbyvalue` is likewise a `TGraalVar` method (`:575`) that our
   VM now implements on its own root object surface rather than only for
   Python lists.

4. **`level` was an empty object. Fixed.** `ClientGS2.__init__` used to do
   `self.level_object = GS2Object(name="level")` and nothing ever populated
   it. All 14 official `level` properties read 0.0, including the
   string-typed `name`. The 14 is the **whole chain**, not one table:
   `TServerLevelProperties::propDefs` is six entries — `height`,
   `isnopkzone`, `issparringzone`, `nopkzone`, `tilelayercount`, `width`
   (`src/TServerLevelProperties.cpp:60-115`) — and `TGraalVarProperties::
   propDefs` adds eight more — `name`, `initialized`, `ispaused`,
   `joinedclasses`, `maxlooplimit`, `scripterrors`,
   `scriptlogmissingfunctions`, `timeout` (`src/TGraalVarProperties.cpp:
   625-698`). `level`'s *methods* mostly worked by
   accident, because the code routes the bare-name forms (`putbomb`, `tiletype`, …)
   through the GS1 host — but the property surface used to be entirely
   absent. `ClientGS2.__init__` now does `self.level_object =
   _LevelObject(self)` (`gs2_client/runtime.py`, `ClientGS2.__init__`), a real object that
   answers `name`, `width`, `height`, `tilelayercount`,
   `joinedclasses`/`scripterrors` (empty arrays) and the remaining
   numeric/boolean entries from the same two tables with `0.0`
   (`gs2_client/objects.py:370-452`).

5. **`player.level` was ours, not the reference's, and the official
   `levelname` spelling used to read 0.0. Fixed.** No property named `level`
   exists on any player class. The official spelling is `levelname` (string).
   The reference registers `level` only on `TLevelObject`
   (`src/TLevelObjectProperties.cpp:6`, object-typed), which players are not.
   Our `player.level` (`gs2_client/objects_player.py`, the `level` key) is a
   deliberate extension that fixed a real bug and stays. `player.levelname`
   now answers too, returning the same value as `player.level`
   (`gs2_client/objects_player.py`, the `levelname` key), so content written against the
   reference's spelling no longer reads 0.0.

### Deliberate divergences (verified, not bugs)

- `graalversion` returns `6.15401` unconditionally in the reference
  (`src/TInitStatics.cpp:2331-2334`). We return the version negotiated at
  login, on purpose (`pyReborn/pyreborn/gs1_client/host_builtins.py`, the `graalversion` builtin).
- `allstats` returns `0x7ff` = 2047 (`src/TInitStatics.cpp:2340`). Our
  hard-coded `2047.0` (`gs2_client/host_objects.py`, `_obj_allstats`; also `gs1_client/host_builtins.py`) is now
  oracle-confirmed. The
  neighbouring constants are `allfeatures` = `0xffff` (`:2336`) and
  `allrenderobjecttypes` = `0x3f` (`:2338`), both unanswered.
- `player.x` / `player.y` are world-frame in the reference too:
  `getlocalx() + (mapX << 6)` (`src/TServerPlayerProperties.cpp:230-238`),
  matching the comment already in `_PlayerObject.get`.
- `player.ani` is object-typed (`'o'`), returning the animation handle
  (`src/TGaniObjectProperties.cpp:15-18`, table `:46`) — our `_NameObject`
  wrapper is the right shape.

---

## Suggested implementation order

1. **T1 in one pass.** Mechanical: give every string-typed name an
   `""`-or-better answer. Highest value per line of code in this document, and
   the only tier where *not* implementing is worse than implementing wrongly.
2. **Populate `level`.** `name`, `width`, `height` from data the client
   already has. The rest can follow.
3. **Route the probes that already exist.** Done for `testnpc` and
   `testplayer`, which now sit in `_GS1_LEVEL_PROBES`. The sign, item, bomb and
   explosion probes are now registered too (`gs2_client/host_any.py`,
   `_any_test_level_object`).
4. The rest of T2, then T3. T4 should be left registered-but-inert, with the
   existing `stubbed` mechanism, so `builtins_missing` stops reporting them.

---

## Bottom-up findings

The tiers above came from the reference's registration tables. This section
comes from the opposite direction: grepping the production script corpora
(`Preagonal/graal-{lttp,loginserver,loginserver-dev,loginserver-mobile,
bomber-gs2,gta}`) for names scripts actually reference, then diffing against
what we answer. It found things the top-down sweep structurally could not.

### The option store is SEEDED, and content reads the seeds

T4 lists `TOptions` / `TFontOptions` / `TTranslations` as "not implementable
client-side". That is true of the *persistence* and false of the *values*:
each `*_initStaticVars()` gives these names a default, and scripts
read the default. Answering `""` is as wrong as answering nothing.

| Name | Type | Reference default | Citation |
| --- | --- | --- | --- |
| `$pref::video::defaultguistyle` | s | `"toon_small.wba"` | `src/TInitStatics.cpp:4789` |
| `$pref::video::externalguistyle` | s | `"toon_small.wba"` | `:4790` |
| `$pref::video::screenshotformat` | s | `"PNG"` | `:4777` |
| `$pref::graal::language` | s | `"English"` | `:4841` |
| `$pref::graal::defaultfontname` | s | `"Arial"` | `:4983` |
| `$pref::graal::utf8fontfile` | s | `"DroidSansFallback.ttf"` | `:4984` |
| `$pref::graal::defaultfontsize` | **i** | `0x18` = 24 | `:4981` |
| `$pref::graal::dontsavepasswords` | **b** | `false` | `src/TOptions.cpp:25` |
| the plugin-cookie option | s | genuinely empty | `:4784-4786` |

Corpus reference counts (references / distinct files):
`$pref::video::defaultguistyle` 96/17, `$pref::graal::dontsavepasswords` 28/9,
`$pref::graal::language` 15/5, `$pref::graal::defaultfontsize` 1/1,
`$pref::graal::defaultfontname` 1/1. `$pref::` is the *entire* `$`-prefixed
name surface the corpora use — no other option-style bare names appear.

### Two of those were invisible to the T1 rule

`defaultfontsize` is `'i'` and `dontsavepasswords` is `'b'`, so neither is a
string and neither could ever appear in T1, whose entry criterion is
`returnType == 's'`. They are still latent wrong answers, just with a
different failure mode: **an unanswered NUMERIC name is `0`, and `0` is a
perfectly plausible number**, so nothing looks wrong.

The live case: `graal-lttp/weapons/weapon-Player_Movement.txt:101` computes

```
zoom = $pref::graal::defaultfontsize/24;
```

and the adjacent line `:93` draws every nearby player's nickname with
`showtext(200+i, pl.x+1.5, pl.y+3, $pref::graal::defaultfontname, "bc",
pl.nick)` at that zoom. Unanswered, `zoom` is `0` and the labels never render.
answered, the ratio is exactly `1`. The same two lines also want
`defaultfontname` to be `"Arial"`, not `""`.

**Generalised lesson:** read the T1 criterion as "any registered
name we leave unanswered is a latent wrong answer", with the string case being
merely the one that is *provably* always wrong. A numeric or boolean name with
a non-zero/non-false reference default is the same bug and is harder to see.

### Branch sensitivity worth knowing about

Login content branches on `defaultguistyle` being *empty*, e.g.
`if ($pref::Video::defaultguistyle != "")` and
`visible = (isLoginServer() && $pref::Video::defaultguistyle == "" ||
style.pos("toon") >= 0)`. We answer the reference's seed
(`"toon_small.wba"`), which is what a fresh install with no options file has,
so those branches take the "a style has a value" path. If a future capture shows
the real client taking the other path, this is the value to revisit first.

### Where the extraction method should change

Any future wave over this surface should run **both** directions and diff
them: the tables say what users *can* ask, the corpora say what users *do* ask.
Rank the work by distinct-script reference count, not by table position —
`$pref::video::defaultguistyle` (17 scripts) and the `GuiTextListCtrl` row
API (up to 12 scripts per name) both outrank most of T2, and neither was
prioritised by the top-down pass.
