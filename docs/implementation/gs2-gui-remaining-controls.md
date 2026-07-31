# GS2 GUI audit — tail classes + the TreeView/TabCtrl question

Oracle root: `/home/hosler/Projects/opengraal2/Preagonal/FourPlay/quattroplay/`.
I opened and read every `file:line` below. I make no assertion for a body that
was not read.

---

## PRIORITY: why `GuiTreeViewCtrl` and `GuiTabCtrl` have no `*Properties.cpp`

**Answer: the FourPlay oracle decompiles a DIFFERENT, smaller client binary than
the one Login's content targets. Those two controls do not exist in the oracle's
binary at all. That is not "not decompiled yet". They are genuinely absent.
They DO exist in the other client build we have a symbol dump for. Our implementations are
therefore *directionally faithful* (the classes are real engine controls) but
their property/method surface is unverifiable from this oracle.**

Evidence, in order of strength:

1. **Neither name occurs anywhere in FourPlay.** `grep -rn "GuiTabCtrl"` and
   `grep -rn "GuiTreeViewCtrl"` over the whole `Preagonal/FourPlay/` checkout
   (`src/`, `include/`, `asm/**/*.s_decomped`, everything) return **zero** hits.
   The only near-hit is the string `"Taskbar.Button"` inside
   `src/gui/GuiButtonCtrl.cpp:202-204`, which is a *style-name prefix test*
   (`buttonName.starts("Taskbar.Button")`), not a class.

2. **The script-creatable class registry is complete and does not list them.**
   `TObjectCreator` serves `new <Class>(...)`. Every registration is a
   `new TObjectCreator("Name", …)` inside `TInitStatics.cpp`, the decompilation
   recovered them contiguously as one `*_initStaticScriptVars()` per class
   (`src/TInitStatics.cpp:5403-5564` and `:6048-6066`, read). That is **22
   creatable Gui classes**: BitmapButton, Bitmap, Button, CheckBox, Control,
   Graal, MLText, Radio, Scroll, Stretch, Text, TextEdit, Array, ContextMenu,
   PopUpMenu, Progress, TextList, DrawingPanel, ShowImg, Window, Browser,
   ControlProfile. No Tab, no TreeView, no Taskbar, no StartMenu, no
   AccountPassword, no MLTextEdit, no PopUpEdit, no Frame.

3. **The binary's own symbol table confirms it.** `FourPlay/libqplay_symbols.txt`
   (5815 lines, the symbol list of the `libqplay` binary under decompilation)
   normalises to exactly **24 `Gui*` classes**, the 22 above plus the two
   non-creatable helpers `GuiContextTextListCtrl` and `GuiPopUpContextMenuCtrl`,
   plus `GuiCanvas`/`GuiEvent`/`GuiTextListEntry`. `GuiTabCtrl`,
   `GuiTreeViewCtrl` and `GuiTaskbar` appear **nowhere** in it. So this is not
   an incomplete decompilation. The code is simply not in the binary.

4. **They exist in the other client.** `Preagonal/graal-revlib-osx/` is a dylib
   project for the macOS `Era.app` client, and `docs/symbol_dump.log` is a
   symbol dump of it. The build obfuscates its class names, but `_GLOBAL__sub_I_*`
   translation-unit names survive verbatim. Grepping
   `_GLOBAL__sub_I_Gui*.cpp` yields **43 Gui TUs**, including:

   - `symbol: _GLOBAL__sub_I_GuiTabCtrl.cpp`, `graal-revlib-osx/docs/symbol_dump.log:4326`
   - `symbol: _GLOBAL__sub_I_GuiTreeViewCtrl.cpp`, `:4811`

   …and also `GuiTaskbar.cpp`, `GuiStartMenuCtrl.cpp`, `GuiAccountPasswordCtrl.cpp`,
   `GuiMLTextEditCtrl.cpp`, `GuiPopUpEditCtrl.cpp`, `GuiFrameCtrl.cpp`,
   `GuiSliderCtrl.cpp`, `GuiMenuCtrl.cpp`, `GuiAccordionCtrl.cpp`,
   `GuiAnimationCtrl.cpp`, `GuiPMCtrl.cpp`, `GuiSelectFile.cpp`,
   `GuiSlideShowCtrl.cpp`, `GuiTextEditSliderCtrl.cpp`, `GuiTextureCtrl.cpp`,
   `GuiBitmapBorderCtrl.cpp`, `GuiCursor.cpp`.

   The classes we invented beyond the oracle's 24 are `GuiTaskbar`,
   `GuiStartMenuCtrl`, `GuiAccountPasswordCtrl`, `GuiMLTextEditCtrl`,
   `GuiPopUpEditCtrl`, `GuiTabCtrl`, and `GuiTreeViewCtrl`. That they map
   **1:1 onto TUs in this second build** is strong independent corroboration
   that the prior wave guessed the right class set. The one loose end is our
   `GuiFrameSetCtrl`, whose nearest TU is `GuiFrameCtrl.cpp`. The name may be
   wrong.

   Note also `_ZN31WxcBwVWGWsGwXdFBwxbcvPropertiesC2Ev` and friends immediately
   after the `GuiTabCtrl.cpp` marker (`symbol_dump.log:4327-4332`): the class has
   a `…Properties` type in that build, i.e. it registers a script table under an
   obfuscated name we cannot decode.

5. **The scripts do not define them.** The scripts use them as engine classes:
   `new GuiTabCtrl("Serverlist_TablesTab")` at
   `Preagonal/graal-loginserver/weapons/weapon-Rescripted_Serverlist.txt:2141`
   (also `:1036`, `:2468`) and
   `new GuiTreeViewCtrl("Serverlist_ServerList")` at `:2417`. There is no
   `classes/` dir in that corpus and no script defines either name. The
   "script-defined class masquerading as a binding" pattern (`destroyobject` on
   `-ReShared`) does **not** apply here.

**Consequence for us.** Keep both implementations. They are real controls, not
inventions. But every property/method name on them (and on Taskbar/StartMenu/
PopUpEdit/AccountPassword/MLTextEdit/FrameSet) comes from *script usage*,
not from a table, and must stay marked as such. The corpora and the `.gasm` /
`gbf/bytecode/login/*.gs2bc.gs2` decompiles are the only oracle available for
them. Related dead end: `Serverlist_TaskButton_Server.icon.drawimagestretched(...)`
(`weapon-Rescripted_Serverlist.txt:278`) implies the taskbar button exposes an
`icon` sub-control, also unmodellable from FourPlay.

---

## Cross-cutting mechanism finding (affects three of my classes)

Two `TProperties` features the earlier waves did not describe, both verified:

**(a) `propertyStrings` is a REMOVAL list, not a delegation list.**
`TProperties::compileProperties` copies the parent table, applies the child's own
entries, then walks `propertyStrings` and calls `removeObjectEncoded` on each
name (`src/TProperties.cpp:132-161`, specifically the removal at `:147`). So a
class listing a name there **deletes** an inherited property. (Corroborated by
`src/TServerWeaponProperties.cpp:27`, which lists ~100 player property names.
A weapon is not a player, so stripping them is the obvious intent.) The exact
skip behaviour of that decompiled `while(true)/goto` loop is spaghetti and I do
not assert it beyond "the code removes the listed names".

**(b) `addPropertyObject` installs a real delegation target.**
`TGraalVar::getProperty` checks the object's own compiled table first, then walks
`propertyObjects` recursively (`src/TGraalVar.cpp:1652-1679`, and the hashcode
overload `:1682-1705`). Three of my/the sibling classes use it:
`GuiShowImgCtrl` → embedded `TShowImg` (`src/gui/GuiShowImgCtrl.cpp:83`),
`GuiContextMenuCtrl` → its embedded `GuiTextListCtrl`
(`src/gui/GuiContextMenuCtrl.cpp:158`), `GuiPopUpMenuCtrl` → its context menu
(`src/gui/GuiPopUpMenuCtrl.cpp:93`).

---

## Per-class results

### `GuiCheckBoxCtrl` — 0 own properties, 0 own methods

Chain: `GuiCheckBoxCtrl → GuiButtonBaseCtrl → GuiControl → TGraalVar`
(`src/gui/GuiCheckBoxCtrlProperties.cpp:3-4`,
`src/gui/GuiButtonBaseCtrlProperties.cpp:128-129`). The whole file is the ctor.
It registers **nothing**. It inherits its entire script surface.

`GuiButtonBaseCtrl` (the real surface, `src/gui/GuiButtonBaseCtrlProperties.cpp`):

| Name | Type | R/W | Table line | Semantics (body read) |
| --- | --- | --- | --- | --- |
| `buttontype` | s | RW | `:68-77` | one of `"PushButton"`, `"ToggleButton"`, `"RadioButton"` (`:5-9`). Setter is a **silent no-op on an unrecognised string** (`:16-26`, loop falls out, no error, no default). |
| `checked` | b | RW | `:78-86` | getter `:28-31`, setter → `GuiButtonBaseCtrl::setChecked` (`src/gui/GuiButtonBaseCtrl.cpp:42-46`) |
| `groupnum` | i | RW | `:87-95` | radio-group id, **defaults to `-1`** (`GuiButtonBaseCtrl.cpp:33`) |
| `text` | s | RW | `:96-104` | button label |

Methods: `gettext()` → s, `settext(s)` → v (`:107-126`).

Defaults from `GuiCheckBoxCtrl::initObject` (`src/gui/GuiCheckBoxCtrl.cpp:25-35`):
extent **140 × 30**, `buttontype` index 1 = `"ToggleButton"`, unchecked.

**Counter-intuitive #1 (the big one).** *Writing `.checked` does NOT enforce
radio-group exclusivity.* `setChecked` only sets the flag and invalidates
(`GuiButtonBaseCtrl.cpp:42-46`). Group exclusivity lives **exclusively in
`onAction()`** (`:59-94`), which fires only on a user click. Also, the code
limits it to the control's `m_parentObject`'s direct children, matching on
`buttontype == RadioButton` **and** equal `groupnum` (`:82-83`). Live proof the
scripts know this: `graal-loginserver/weapons/weapon-Rescripted_IRC_Login2.txt:48-49`
does `StartMemberCheck.checked = true; StartGuestCheck.checked = !StartMemberCheck.checked;`
Also, it clears the sibling by hand.

**Counter-intuitive #2.** `onAction()` returns early when `!m_active`
(`:61-62`), so an inactive toggle silently does not toggle.

### `GuiRadioCtrl` — 0 own properties, 0 own methods

Chain: `GuiRadioCtrl → GuiCheckBoxCtrl → GuiButtonBaseCtrl → GuiControl`
(`src/gui/GuiRadioCtrlProperties.cpp:3-4`). Registers nothing.
`GuiRadioCtrl::initObject` (`src/gui/GuiRadioCtrl.cpp:18-24`) sets only
`buttontype` index 2 = `"RadioButton"`. It does **not** reset the extent, so a
radio inherits the checkbox's 140 × 30 default via the base ctor chain.

**Counter-intuitive.** A `GuiCheckBoxCtrl` with `buttontype = "RadioButton"` is a
fully functional radio, and a `GuiRadioCtrl` with `buttontype = "PushButton"`
stops being one. The behaviour is driven by the *property*, not the class.

### `GuiProgressCtrl` — 1 property, 0 methods

`TProperties("GuiProgressCtrl", "GuiControl")` (`src/gui/GuiProgressCtrlProperties.cpp:19`).

| Name | Type | R/W | Table line | Semantics |
| --- | --- | --- | --- | --- |
| `progress` | f | RW | `:16` | getter `:5-8`, setter → `GuiProgressCtrl::setProgress`, **clamped to 0.0…1.0**, early-returns on no-change (`src/gui/GuiProgressCtrl.cpp:30-42`). Init `0.0f` (`:22-28`). |

Not 0–100. Corpus agrees (`weapon-IRC_Installer.txt:95-101`, `progress = 0`).

### `GuiShowImgCtrl` — 5 own properties, 0 methods, + a removal list + a delegate

`TProperties("GuiShowImgCtrl", "GuiControl")` (`src/gui/GuiShowImgCtrlProperties.cpp:77`).

| Name | Type | R/W | Table line | Semantics |
| --- | --- | --- | --- | --- |
| `ani` | s | RW | `:70` | forwards to the embedded `TShowImg`'s `getAni`/`setAni`, the setter **also clears the playerlook flag** (`:12-20`) |
| `dir` | i | RW | `:71` | ditto for direction, same playerlook clear (`:27-35`) |
| `layer` | i | RW | `:72` | setter `:42-45`. **Getter body is broken as transcribed**, `:37-40` is declared `void`, calls `getLayer()` and discards the result, while the table declares `'i'`. No `propfun_*` symbol exists in `asm/` (they are static), so the asm cannot arbitrate. Recorded as *type + R/W only*, do not infer a return value. |
| `offsetx` | i | RW | `:73` | pixel offset, calls `updateImagePosition()` (`:52-56`) |
| `offsety` | i | RW | `:74` | ditto (`:63-67`) |

**Counter-intuitive #1: the ctor DELETES seven inherited properties.** It does
`propertyStrings->SetCommaText2("red,green,blue,alpha,mode,style,rotation")`
(`:84`). Per mechanism (a) those names are *removed* from the compiled table.
`GuiControl` registers all seven (`src/gui/GuiControlProperties.cpp:649,
653, 666, 673, 686, 689, 695`). The child removes them so they do not shadow the
delegate's versions.

**Counter-intuitive #2, this control's real surface is `TShowImg`'s.**
`initObject` creates a `TShowImg`, seeds it (`name = "showimg"`, `m_layer = 10`),
and calls `addPropertyObject(showImg)` (`src/gui/GuiShowImgCtrl.cpp:40-84`). So,
per mechanism (b), the whole showimg property table resolves through it. Verified
by name against `src/TShowImgProperties.cpp`: `image` `:171`, `shadowcolor`
`:216`, `textshadow` `:243`, `mode` `:315`, `partx` `:342`, `party` `:351`,
`red` `:369`, `stretchx` `:405`, `zoom` `:468`. `listPropertiesForDocumentation`
merges the two tables for exactly this reason (`GuiShowImgCtrlProperties.cpp:87-96`).

**So `GuiShowImgCtrl` is NOT a bitmap control.** It is a showimg host. Its
`red/alpha/mode/rotation` are `TShowImg`'s, not `GuiControl`'s, and it gains
`zoom`, `stretchx/y`, `partx/party`, `textshadow`, `shadowoffset/shadowcolor`,
`font`, `text`, which is precisely the set the corpus assigns (see below).

### `GuiStretchCtrl` — 3 properties, 0 methods

`TProperties("GuiStretchCtrl", "GuiControl")` (`src/gui/GuiStretchCtrlProperties.cpp:51`).

| Name | Type | R/W | Table line | Semantics |
| --- | --- | --- | --- | --- |
| `clientextent` | s | RW | `:46` | `"x y"` point string of `m_size`, on change calls `resizeChildren(old, new)` (`:6-17`) |
| `clientheight` | i | RW | `:47` | `m_size.y`, same resize hook (`:19-30`) |
| `clientwidth` | i | RW | `:48` | `m_size.x`, same resize hook (`:32-43`) |

**Counter-intuitive.** All three names are **already registered on `GuiControl`**
(`src/gui/GuiControlProperties.cpp:657, 658, 659`) with different bodies. Child
replaces parent, so on a stretch control these mean "the virtual content size,
and writing it proportionally rescales every child", not "the inner client
rect". Same spelling, different field, plus a side effect.

### `GuiDrawingPanel` — 6 properties, 14 methods

`TProperties("GuiDrawingPanel", "GuiControl")` (`src/gui/GuiDrawingPanelProperties.cpp:209`).

Properties (table `:183-190`): `partx` i **RO** (`:28-31`), `party` i **RO**
(`:33-36`), `partw` i **RO** (`:38-41`), and `parth` i **RO** (`:43-46`). Also:
`availablefilters` o **RO** (`:48-51`, forwards to a `TDrawingPanel` free
function whose body is not in this file, signature only). And `enablecache`
b RW (`:53-65`): setting it false also calls `clearCache()`.

Methods (table `:192-207`), params verbatim from the `params` string:

| Name | Params | Ret | Line | Notes |
| --- | --- | --- | --- | --- |
| `clearall` | none | v | `:193` | body `:67-73` |
| `clearrectangle` | `iiii` | v | `:194` | `:75-81` |
| `drawcurve` | `iiiiiif` | v | `:195` | 3 points + width, `:83-97` |
| `drawimage` | `iis` | v | `:196` | `:99-103` |
| `drawimagestretched` | `iiiisiiii` | v | `:197` | `(x,y,w,h,image,srcX,srcY,srcW,srcH)`, **image is the 5th arg, and there are four trailing source-rect args**, `:105-111` |
| `drawimagerectangle` | `iisiiii` | v | `:198` | `(x,y,image,srcX,srcY,srcW,srcH)`, `:113-118` |
| `drawobject` | `iio` | v | `:199` | silently no-ops unless the object casts to `TLevelObject` (`:120-125`) |
| `drawline` | `iiiif` | v | `:200` | `:127-141` |
| `drawtext` | `iis` | v | `:201` | `:143-150` |
| `saveimage` | `s` | v | `:202` | path is rewritten by `TFileScripting::getScriptWriteBitmapFilename`, **and the caller drops the call entirely if that returns empty** (`:152-157`), sandbox gate |
| `saveimage2` | `si` | v | `:203` | same gate (`:159-164`) |
| `filterrectangle` | `iiiis` | **b** | `:204` | table says bool, the transcribed body `:166-170` is `void` and discards `filterRectangle_Impl`'s result. Same unrecovered-return artifact as `showimg.layer`, type recorded, no semantics asserted. |
| `maskimage` | `iiss` | v | `:205` | `:172-176` |
| `setdrawpalette` | `si` | v | `:206` | `:178-181` |

**Counter-intuitive.** `drawcurve` and `drawline` take the width as a **`double*`**
(`:84`, `:128`, the float-param calling convention). Also, three of the draw
calls (`drawcurve`, `drawline`, `drawtext`) push the *control's* profile into the
drawing panel first via `setGuiDrawingPanelProfile` (`:14-26`). So pen colour
and font come from the control profile, not from any draw-state property.

### `GuiGraalCtrl` — 1 property, 0 methods

`TProperties("GuiGraalCtrl", "GuiControl")` (`src/gui/GuiGraalCtrlProperties.cpp:27-28`).
`isrendering` b RW (`:15-25`, getter `:5-8`, setter `:10-13`) is a plain bool on
the control. It is the in-GUI game viewport toggle.

### `GuiBrowserCtrl` — 3 properties, 0 methods

`TProperties("GuiBrowserCtrl", "GuiControl")` (`src/gui/GuiBrowserCtrlProperties.cpp:41`).
`allowzoom` b RW (`:36`), `text` s RW (`:37`, setter → `setText`), `url` s RW
(`:38`, setter → `setURL`). Registered late, in a separate init block
(`src/TInitStatics.cpp:6048`), not with the other 21.

### `GuiContextMenuCtrl` — 6 properties, 4 methods, + a delegate

`TProperties("GuiContextMenuCtrl", "GuiControl")` (`src/gui/GuiContextMenuCtrlProperties.cpp:171`).

| Name | Type | R/W | Table line | Semantics |
| --- | --- | --- | --- | --- |
| `maxpopupheight` | i | RW | `:156` | plain field (`:12-20`) |
| `scrollprofile` | o | RW | `:157` | the embedded **scroll** control's profile (`:22-42`) |
| `textprofile` | o | RW | `:158` | the embedded **text list**'s profile (`:44-64`) |
| `profile` | o | RW | `:159` | **aliased to `scrollprofile`**, identical getter and setter pointers |
| `rows` | o | **RO** | `:160` | the text list's `rows` dynamic var, fetched by name (`:106-114`), returns null if the list has no vars |
| `width` | i | RW | `:161` | **asymmetric**, see below |

Methods (`:164-169`): `close()` v (`:116-119`), `isopen()` b (`:121-124`),
`open(i,i)` v (`:126-138`), `openatmouse()` v (`:140-153`).

**Counter-intuitive #1.** `profile` is **redeclared** and therefore *replaces*
`GuiControl`'s `profile` (`GuiControlProperties.cpp:685`). Setting `.profile` on
a context menu styles the **scroll** control. Row/text styling needs
`textprofile`. Both writes are silently dropped if the argument does not cast to
a `GuiControlProfile` (`:39-41`, `:61-63`).

**Counter-intuitive #2.** `width` **reads the text list's extent** (`:66-72`) but
**writes the scroll control's** (`:74-84`), and the setter clamps to `>= 1`. A
write followed by a read is not guaranteed to round-trip.

**Counter-intuitive #3.** `open(x, y)` / `openatmouse()` do not parent the popup
to *this* control: they reparent to the top-most moused control's
`getContextMenuParent()`, falling back to the canvas (`:126-153`).

**Delegation:** `addPropertyObject(this->m_textListCtrl)`
(`src/gui/GuiContextMenuCtrl.cpp:158`) makes the entire `GuiTextListCtrl`
property and row-method surface reachable on a context menu.
`listPropertiesForDocumentation` merges them (`GuiContextMenuCtrlProperties.cpp:177-185`).

### `GuiTextListEntry` — 18 properties, 2 methods

`TProperties("GuiTextListEntry", "TGraalVar")` (`src/gui/GuiTextListEntryProperties.cpp:197`)
Also, note it hangs off `TGraalVar`, **not** off `GuiControl`. It is not
creatable from script (no `TObjectCreator`). The text list mints them.

Table `:170-189`. Read/write: `active` b (`:171`), `flickering` b (`:173`),
`flickertime` f (`:174`), `hint` s (`:176`), `id` i (`:177`), `image` i (`:178`),
`profile` o (`:180`, `AcceptStringProperty`), `selectedimage` i (`:181`),
`sortgroup` i (`:182`), `sortvalue` i (`:183`), `text` s (`:184`),
`useownprofile` b (`:185`).
**Read-only** (`nullptr` setter): `extent` s (`:172`), `height` i (`:175`),
`position` s (`:179`), `width` i (`:186`), `x` i (`:187`), `y` i (`:188`).
Methods (`:191-194`): `gettext()` → s, `settext(s)` → v, both reusing the `text`
property functions.

**Counter-intuitive #1, `image` and `selectedimage` are INTEGERS, not filenames**
(`:53-61`, `:63-71`, declared `'i'` at `:178`/`:181`). They are icon indices.

**Counter-intuitive #2, the decompiled header's field names for `text`/`hint`
are SWAPPED relative to their meaning, the property table is the correct one.**
The `text` property reads the field named `hint` (`:150-155`) and the `hint`
property reads the field named `text` (`:123-131`). The property table is right
and the *field labels* in `include/gui/GuiTextListEntry.h:23-24` are a decompiler
guess: `GuiTextListCtrl` uses the field named `hint` as the row text everywhere:
sorting (`src/gui/GuiTextListCtrl.cpp:62-63, 74, 78-79`), rendering (`:480`,
`:719`), `setRowById` (`:539`, `:911`), and text search (`:753`). It uses the
field named `text` only for the tooltip: `root->setHintNoHide(entry->text, …)`
(`:826-829`). Anyone implementing from the struct rather than the table will
swap row text and tooltip.

**Counter-intuitive #3, `text` can be silently write-protected.** When
`field_0xe0` is set, the getter returns `""` and the setter returns without
storing (`:150-168`). The owning list copies that flag at row-add time
(`src/gui/GuiTextListCtrl.cpp:543`, `entry->field_0xe0 = this->m_guiControl_unknown8`).
It starts false (`src/gui/GuiTextListEntry.cpp:38`). I did not identify
what sets `m_guiControl_unknown8`, unresolved.

**Counter-intuitive #4, `useownprofile` is a derived read.** The getter is
`ownProfile != nullptr` (`:98-101`), not a stored bool, and `profile`'s getter
prefers `ownProfile` over `profile` (`:138-141`).

---

## Bottom-up: what real scripts actually use

Corpora scanned: `Preagonal/graal-{lttp,loginserver,loginserver-dev,loginserver-mobile,bomber-gs2,gta}/`.
Counts are *distinct files*. I extracted construction-block fields from the
brace body of each `new <Class>(…) { … }`, with nested `new Gui*` blocks stripped.

| Class | files mentioning | files with `new` |
| --- | ---: | ---: |
| `GuiShowImgCtrl` | 15 | 12 |
| `GuiCheckBoxCtrl` | 11 | 11 |
| `GuiRadioCtrl` | 6 | 6 |
| `GuiStretchCtrl` | 5 | 5 |
| `GuiProgressCtrl` | 3 | 3 |
| `GuiDrawingPanel` | 1 | 1 |
| `GuiContextMenuCtrl` | 1 | 1 |
| `GuiGraalCtrl` | **0** | 0 |
| `GuiBrowserCtrl` | **0** | 0 |
| `GuiTextListEntry` | **0** (never named, produced by the list) | 0 |

Members assigned, by class (refs / distinct files):

- **`GuiCheckBoxCtrl`**, `profile` 11/10, `text` 10/9, `horizSizing`/`vertSizing`/
  `position`/`extent` 8/8 each, `profile.fontColor` 5/5, `x`/`y` 3/2,
  `height` 2/1, `useownprofile` 2/2, `profile.fontType` 2/2, `profile.tab` 2/2.
  Scripts read and write `.checked` in **11** files (e.g.
  `graal-loginserver/weapons/weapon-Rescripted_IRC_Login2.txt:47-49, 306-307`).
  `buttontype` appears in 2 files (always `"PushButton"` on plain buttons, e.g.
  `weapon-Rescripted_Serverlist.txt:1018`).
- **`GuiRadioCtrl`**, `profile`/`horizSizing`/`vertSizing`/`position`/`extent`/
  `text`/**`groupNum`** 12/6 each, `visible` 6/3, `useownprofile` 6/6,
  `profile.tab` 6/6. `groupnum` overall: 8 files.
- **`GuiProgressCtrl`**, `profile`, `position`, `extent`, `horizSizing`,
  `progress`, all 9/3. Only ever `IRC_Installer`'s three bars.
- **`GuiShowImgCtrl`**, `image` 15/9, `width`/`height` 15/6, `x` 13/6,
  `useownprofile` 10/3, `profile`+`profile.fontColor` 8/2,
  `textshadow`/`shadowcolor`/`shadowoffset` 8/2, `red`/`green`/`blue`/`alpha`/
  `mode`/`zoom` 7/6, `extent` 6/6, `y` 4/4, `position` 3/3, `active` 3/3,
  `offsetx` 3/3, `ani` 3/3, `partx`/`party`/`rotation`/`stretchx`/`stretchy` 2/1.
  **Every one of `zoom`/`stretchx`/`stretchy`/`partx`/`party`/`textshadow`/
  `shadowcolor`/`shadowoffset`/`image` is a `TShowImg` name, not a `GuiControl`
  name**, which is exactly what the delete-then-delegate mechanism predicts.
- **`GuiStretchCtrl`**, `width`/`height`/`clientwidth`/`clientheight` 7/5 each,
  `x`/`y` 4/4, `horizsizing`/`vertsizing` 4/3, `useownprofile` 3/3,
  `profile.modal` 3/3, `clipchildren` 3/3, `cliptobounds` 2/2. (`clipchildren`
  `GuiControlProperties.cpp:660`, `cliptobounds` `:662`.)
- **`GuiDrawingPanel`**, one construction block
  (`graal-loginserver-dev/weapons/weapon-Staff_GraalShop.txt:109`) plus a
  bare `new GuiDrawingPanel()` at `:942`, which then calls
  `drawimagerectangle(...)` and `saveimage("temp_sprite.png")` (`:945-946`).
  the code calls `drawimagestretched` on the taskbar button's `icon` in the
  serverlist weapons (`weapon-Rescripted_Serverlist.txt:278`, `:2312`).
  **Zero** corpus use of `drawrect`, `drawtext`, `drawcurve`, `drawobject`,
  `clearrectangle`, `enablecache`, `filterrectangle`, `maskimage`,
  `setdrawpalette`.
- **`GuiContextMenuCtrl`**, one file, sets `profile` and `textprofile`.
  `maxpopupheight` 1 file, `isopen` 2 files, `openatmouse` **0** files.
- **`GuiGraalCtrl` / `GuiBrowserCtrl`**, zero references of any kind.
  `isrendering` and `allowzoom` appear nowhere.

**Dead classes, do not implement:** `GuiGraalCtrl`, `GuiBrowserCtrl`, and (as a
script-instantiable type) `GuiTextListEntry`. Also dead and not in my list but
worth recording, since they have no `TObjectCreator` and no corpus reference:
`GuiContextTextListCtrl`, `GuiPopUpContextMenuCtrl`.

---

## Diff vs `pyReborn/pyreborn/game/gs2_gui/` (read, not edited)

| Member | Class in ours | Verdict |
| --- | --- | --- |
| `progress` clamp 0..1 | `GuiProgressCtrl` `:1997-2001` | **IMPLEMENTED**, matches `GuiProgressCtrl.cpp:32-35` |
| `GuiProgressCtrl` default extent 150×20 | `:1989` | **WRONG**, oracle inherits `GuiControl`'s default, only checkbox/radio get 140×30. Cosmetic, corpus always sets `extent`. |
| `checked` | `GuiCheckBoxCtrl` `:2028-2037` | **IMPLEMENTED** |
| `value` as an alias of `checked` | `:2020` | **INVENTED**, no `value` in `GuiButtonBaseCtrlProperties::propDefs` (`:68-105`) and zero corpus use. Harmless but unsourced. |
| `buttontype` | `GuiButtonBaseCtrl` (`game/gs2_gui/basic_controls.py:279-345`) | **IMPLEMENTED, fixed 2026-07-26** (registered `:68-77`, corpus 2 files) |
| `groupnum` | `GuiButtonBaseCtrl` (`:307-308`, `:315`, `:321-322`, `:337-338`) | **IMPLEMENTED, fixed 2026-07-26.** `_TORQUE_PROPS` gating is existence-based (comment at `game/gs2_gui/base.py:121-127`). `groupNum = 1;` in 12 construction blocks across 6 files now lands on the control instead of falling through to a temp |
| `gettext` / `settext` on buttons | in `GuiControl._METHOD_NAMES` `:869` | **IMPLEMENTED** (over-broadly, they are only registered on `GuiButtonBaseCtrl` and `GuiTextListEntry`) |
| radio group exclusivity on click only | `GuiButtonBaseCtrl.on_action` (`game/gs2_gui/basic_controls.py:350-369`) | **IMPLEMENTED and correct**, matches "exclusivity lives in `onAction`, not `setChecked`" (`GuiButtonBaseCtrl.cpp:42-46` vs `:59-94`). **Fixed 2026-07-26**: now keyed on `button_type == RadioButton` **and** equal `groupnum` (`:360-368`). Previously keyed on `isinstance(GuiRadioCtrl)` and ignored `groupnum`, diverging for a mixed-`groupnum` sibling set. (Login's `StartGuestCheck`/`StartMemberCheck` are both `groupNum = 1`, so this masked the divergence in practice.) |
| docstring "there is no separate group-name property on the wire" | `:2063-2064` | **WRONG as documented**, `groupnum` is a registered `'i'` property (`GuiButtonBaseCtrlProperties.cpp:87-95`) |
| `GuiShowImgCtrl` modelled as a `GuiBitmapCtrl` subclass | `:2127-2135` | **WRONG**, oracle parent is `GuiControl` (`GuiShowImgCtrlProperties.cpp:77`), it is a `TShowImg` host, not a bitmap. Its docstring's claim that the two class names are interchangeable spellings does not hold. `GuiBitmapCtrlProperties.cpp` exists as a separate class with its own `TObjectCreator` (`TInitStatics.cpp:5419`). |
| `ani`, `dir`, `layer`, `offsetx`, `offsety` | none | **MISSING** (`GuiShowImgCtrlProperties.cpp:70-74`) |
| `zoom`/`stretchx`/`stretchy`/`partx`/`party`/`textshadow`/`shadowcolor`/`shadowoffset` on a showimg ctrl | none | **MISSING**, the `TShowImg` delegate. 7/6 to 8/2 corpus files each. |
| `red/green/blue/alpha/mode/style/rotation` sourced from `GuiControl` on a showimg ctrl | inherited | **WRONG source**, removed from `GuiControl` on this class (`GuiShowImgCtrlProperties.cpp:84`) and answered by `TShowImg` instead. Values may coincide, provenance does not. |
| `GuiStretchCtrl` | now its own class in `_CONTROL_CLASSES` (`game/gs2_gui/factory.py:41`) | **IMPLEMENTED, fixed 2026-07-26.** `GuiStretchCtrl` (`game/gs2_gui/popup_controls.py:302-339`) redeclares `clientwidth`/`clientheight`/`clientextent` against its own `client_size`, matching the child-replaces-parent shape. The `resizeChildren` side effect is still not modelled (noted in the class docstring, `:311-312`; the reference body was not read). Previously the class did not exist and construction fell back to generic `GuiControl`, whose `clientwidth`/`clientheight` derive from the outer bounds instead. 5 corpus files. |
| `GuiDrawingPanel.drawimagestretched` arg mapping | `:2507-2512` | **WRONG**, ours reads `(x, y, w, h, image)` and **discards args 5–8**. Oracle is `iiiisiiii` = `(x,y,w,h,image,srcX,srcY,srcW,srcH)` (`GuiDrawingPanelProperties.cpp:105-111, 197`). Latent only because the two live calls pass a full-image source rect (`weapon-Rescripted_Serverlist.txt:278`, `:2312`, `..., 0, 0, 32, 32` on a 32×32 icon). |
| `GuiDrawingPanel.drawimagerectangle` | `:2514-2522` | **IMPLEMENTED**, arg order matches `iisiiii` (`:198`) |
| `GuiDrawingPanel.drawrect` | `:2495-2499`, `:2476` | **INVENTED**, no such entry in `funcDefs` (`:192-207`) and zero corpus calls |
| `clearrectangle`, `drawcurve`, `drawobject`, `drawtext`, `saveimage`, `saveimage2`, `filterrectangle`, `maskimage`, `setdrawpalette` | none | **MISSING** (9 of 14 methods). Only `saveimage` has a corpus caller (`weapon-Staff_GraalShop.txt:946`). |
| `partx/party/partw/parth/availablefilters/enablecache` | none | **MISSING** (all 6 properties, 4 are RO) |
| `GuiContextMenuCtrl` parent = `GuiPopUpEditCtrl` | `:2447` | **WRONG**, oracle parent is `GuiControl` (`GuiContextMenuCtrlProperties.cpp:171`). `GuiPopUpEditCtrl` is not in this binary at all. |
| `visible = False` at construction | `:2457` | **IMPLEMENTED**, the cited `GuiContextMenuCtrl.cpp:35-46` is a real range I re-read |
| `rows`, `maxpopupheight`, `scrollprofile`, `textprofile`, `width`-override, `close`/`isopen`/`open(x,y)` | `textprofile` is in `GuiControl._TORQUE_PROPS` `:853`, `openatmouse` in `_METHOD_NAMES` `:872` | **MISSING** (5 properties + 3 methods). `isopen` has 2 corpus files. |
| `profile` aliasing to the scroll control on a context menu | none | **MISSING** (`:159`) |
| `GuiTextListEntry` | modelled as `GuiListRow` (`:793`) | **PARTIAL**. It needs an audit against the 18-entry table. In particular, `image`/`selectedimage` are ints, six members are read-only, and the `text`/`hint` split must follow the property table, not the header |
| `GuiGraalCtrl`, `GuiBrowserCtrl` | absent | **Correctly absent**, zero corpus use |

---

## Undetermined / deliberately not asserted

1. The return values of `propfun_guishowimgctrl_layer_r`
   (`GuiShowImgCtrlProperties.cpp:37-40`) and
   `scriptfun_guidrawingpanel_filterrectangle`
   (`GuiDrawingPanelProperties.cpp:166-170`). The table declares both with a value type
   in the table and transcribed as `void`. These are `static` functions with no
   mangled symbol, so there is no `asm/**/*.s_decomped` file to arbitrate, the
   `asm/gui/GuiShowImgCtrl/` and `asm/gui/GuiDrawingPanel/` dirs contain only
   the class's own member functions.
2. What sets `GuiTextListCtrl::m_guiControl_unknown8`, the flag copied into
   `GuiTextListEntry::field_0xe0` that makes a row's `text` read `""` and ignore
   writes (`GuiTextListCtrl.cpp:543`).
3. The exact index-advance behaviour of the `propertyStrings` removal loop
   (`TProperties.cpp:136-153`), the decompiled `while(true)`/`goto` may skip a
   name when an entry is not owned by the class. The *removal* itself (`:147`)
   is unambiguous, the skip is not.
4. Whether our `GuiFrameSetCtrl` corresponds to the Era build's
   `GuiFrameCtrl.cpp` (`graal-revlib-osx/docs/symbol_dump.log`, TU list). Names
   differ, not resolvable from a symbol dump.
5. `availablefilters` returns whatever `propfun_drawingpanel_availablefilters_r`
   builds, that body lives in a `TDrawingPanel` unit I did not open. Type `'o'`,
   read-only, that much is from the table (`:188`).

---

## 2026-07-26 implementation round (context menu + drawing panel)

- **`GuiContextMenuCtrl` aliasing implemented** (pyReborn
  `gs2_gui/popup_controls.py`): `profile`/`scrollprofile` are one slot
  (pointer-identical table entries, `GuiContextMenuCtrlProperties.cpp:157`
  vs `:159`) styling the frame. `textprofile` styles the rows (the popup
  row painter resolves it separately). The `width` setter clamps to >= 1
  (`:74-78`). We deliberately left two things unmodelled, and recorded them
  in the class docstring: the asymmetric `width` read, and the RO `rows`
  forward. The `width` read differs between text-list extent and scroll
  write, though one control here means ours round-trips. We did not model
  `rows` because there are 0 corpus reads of it, and claiming an invented
  shape would be guessing.
- **`GuiDrawingPanel` completed** (`gs2_gui/collection_controls.py`): all
  14 funcDefs answered and all 6 propDefs claimed. New bodies read while
  implementing: `drawcurve`'s invalidation rect spans p1..p3 padded by
  width (`GuiDrawingPanelProperties.cpp:87-96`). p1/p3 are the endpoints
  and p2 the shape point, rendered as a flattened quadratic bezier.
  `maskimage`'s `"iiss"` 4th arg is a MODE string, not a second image
  (`:172-176` forwards to `maskImage_Impl(x, y, image, mode)`).
  `setdrawpalette` is `(palette, alpha)` (`:178-181`). We model
  `saveimage`'s sandbox gate (call dropped when the filename rewrite
  returns empty, `:152-157`) as basename+image-extension. A passing name
  snapshots the op list, and this client never writes script-named files.
  `partx/party/partw/parth` answer 0 (RO, backing-field meaning
  unrecovered), and `availablefilters` answers an empty array
  (`'o'` RO, body unrecovered, typed so the read is not Number 0.0).
  `filterrectangle` stays the doc's unverifiable-return entry, answered as
  a typed no-op.
- The per-class diff table above is now stale where it says MISSING for
  these two classes. The remaining WRONG/MISSING rows (`GuiShowImgCtrl` as
  a TShowImg host, `GuiProgressCtrl` default extent) remain unchanged.
