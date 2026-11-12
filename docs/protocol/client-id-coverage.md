# Client Id Coverage by Build

The rest of these docs describe what the reference server sends and accepts. This page
records the other side: which packet ids each **original client** build sends, which ids it
handles, and in what order it talks at login. A server that serves old clients can use it
to know what it will receive, and which ids a given client silently ignores.

Everything on this page is from static reads and lab captures of the original client
binaries, written up in squirelworks' public client-analysis notes,
[Graal_analysis](https://github.com/squirelworks/Graal_analysis/): chapters
[2.4 PLI](https://github.com/squirelworks/Graal_analysis/blob/main/manual/02-protocol/04-pli.md) and [2.5 PLO](https://github.com/squirelworks/Graal_analysis/blob/main/manual/02-protocol/05-plo.md) of its manual, each row there with its own
source. None of it is verified against the reference server, which holds no client code.

## How a client reads a PLO

| Rule | Builds |
| --- | --- |
| Every handler checks a minimum length first and drops a short message silently | 2.05, 2.17.1, 2.22, 2.31 |
| An id with no case in the receive switch falls to one shared default arm and is ignored without error | 2.05 to 2.31 |
| 2.05 keeps two level pointers: the *named level*, set by every `PLO_LEVELNAME`, and the *object level*, which receives NPC messages (3, 150, 151, 166) and is set by `PLO_SETACTIVELEVEL`, or by each `PLO_LEVELNAME` when there is no NPC server | 2.05 |
| Handlers for level objects (bombs, arrows, items, explosions, hits, trigger actions, horses, push-away) act only while the player stands in the named level | 2.05 |
| A message the server re-emits for another player starts with `s player id`; with an unknown id, bombs, arrows, explosions and items are still shown without an owner, while fire spy, throw carried and player hits are dropped | 2.05 |
| 2.17.1, 2.22 and 2.31 read "comma text" through the client's comma-text parser, which allows double quotes | 2.17.1, 2.22, 2.31 |
| The receive dispatcher takes the id as the first byte minus 32, checks it against a bound, and goes through an index table; the bound is id 185 in 2.17.1, 186 in 2.22 and 189 in 2.31 | 2.17.1, 2.22, 2.31 |
| 4.20r6 and 4.20r8 take 100 and 108 before the main switch | 4.20r6, 4.20r8 |

## Server-to-client ids handled, by build

*Bound* is the highest id the receive switch tests. Builds before 2.00 are listed in the
notes' version matrix ([`manual/app-c-version-matrix.md`](https://github.com/squirelworks/Graal_analysis/blob/main/manual/app-c-version-matrix.md)).
For the 2.02 and 2.05 revisions the rows mean distinct static receive routes, not proven
runtime handling.

| Build | Count | Ids handled |
| --- | ---: | --- |
| NewMain 24, 26 | 51 | 0–45, 75, 100, 150, 151, 153 (bound `0x99`) |
| 2.00 (rev0–rev3) | 53 | 0–45, 75, 100, 150, 151, 153–155 (bound `0x9b`) |
| 2.01 (+rev1) | 55 | 0–46, 75, 100, 150, 151, 153–156 |
| 2.02 (rev0–rev2) | 56 | 0–47, 75, 100, 150, 151, 153–156 |
| 2.03 | 58 | 0–48, 75, 100, 150, 151, 153–156, 165 |
| 2.04 | 58 | 0–25, 27–48, 75, 100, 150, 151, 153–156, 165, 166 (26 dropped) |
| 2.05 (rev0–rev2) | 59 | 0–25, 27–48, 75, 100, 150, 151, 153–156, 165, 166, 168 (bound `0xa8`) |
| 2.1 test 2, test 3 | 61 | the 2.05 set plus 49, 169 |
| NewWorld beta 1 | 53 | the 2.05 set without 2, 4, 17, 18, 154, 155 |
| NewWorld beta 2 | 55 | the beta 1 set plus 49, 169 |
| 2.17.1 | 79 | 0–25, 27–49, 68, 69, 75, 100, 150, 151, 153–156, 165, 166, 168–185 |
| 2.22 | 80 | the 2.17.1 set plus 186 |
| 2.31 | 81 | the 2.22 set without 44, plus 84 and 189 |
| 3.04 (Linux) | 79 | 0–49, 68, 69, 75, 84, 100–102, 150, 151, 153–156, 165, 166, 168, 169, 171–176, 178–181, 184–186 |
| 3.153 (Mac OS X) | 88 | the 3.04 set without 44, plus 67, 74, 82, 104, 131–134, 187, 189 |
| 4.20r8 | 101 | 0–25, 27–43, 45–49, 67–69, 74, 75, 82, 84, 100–102, 104–108, 131–134, 150, 151, 153–156, 165, 166, 168–176, 178–187, 189–191, 193–196 |
| 4.20r6 (Mac) | 99 | the 4.20r8 set without 41 and 196 |
| 5.00r7 | 100 | 0–25, 27–43, 45–49, 67–69, 74, 75, 82, 84, 101, 102, 104–107, 131–134, 140, 150, 151, 153–156, 165, 166, 168–176, 178–187, 189–191, 193–195, 197 |
| 6.01r1 | 91 | the 6.03r7 set without 111 |
| 6.03r7 | 92 | 0–25, 27–40, 42, 43, 45–49, 67–69, 74, 82, 84, 101, 102, 104–107, 109, 111, 131, 134, 140, 150, 151, 153–156, 166, 168, 170, 172–174, 176, 178–180, 182, 183, 185–187, 189–191, 194, 195, 197, 198 |

Notes on the gaps and steps in that table:

| Rule | Builds |
| --- | --- |
| No build in the notes handles 26 (`PLO_NPCACTION`) after 2.03 (it is handled from 1.28 beta 2), or 152 and 167 | 2.04 to 6.03 |
| Revisions of one version share every handler shape (2.05 rev1 differs by one constant in 8), so any revision stands for the others; on the wire only 2.02 rev2 differs, by its token and id 37 | 2.00 to 2.05 |
| 2.00 has no active-level reference, since 156 arrives in 2.01; level-addressed messages act on the current level | 2.00 |
| 2.01 rewrites 0, 14 and 15 so the handler no longer waits for and then requests the level, the code side of map preloading; 154 and 155 go through a shared helper | 2.01 |
| 0, 6 and 14 gain checks that skip reloading a level that is already loaded | 2.1 test 3 |
| NewMain 24 and 26 have one handler set between them, but differ from 2.00 more than any 2.0x revision does, so NewMain is a separate branch | NewMain |
| 2.31 drops 44 (`HASNPCSERVER`); the 2.3 release notes say Classic switched to the NPC server | 2.31 |
| 3.04 lacks 170, 177, 182 and 183, which 2.22 handles, and adds 84, 101 and 102 | 3.04 |
| 4.20r8 drops nothing against 3.153 and adds 13 ids | 4.20r8 |
| 5.00r7's list does not include 100 | 5.00r7 |
| Against 5.00r7, 6.x drops 41, 75, 132, 133, 165, 169, 171, 175, 181, 184 and 193 and adds 109, 111 and 198 | 6.01r1, 6.03r7 |
| A later client (5.07 and up, or 6.037, as the source note marks each id) ignores 26, 41, 44, 55, 56, 60, 78, 80, 81, 83, 132, 157, 159–164, 165, 167, 171, 175, 188 and 192 | 5.07, 6.037 |

## Client-to-server ids sent, by build

A list marked *floor* holds only the ids the binary passes to its send routine as
constants; sends that pass the id in a register are not counted. "Disputed" rows have an
open question in the notes.

| Build | Ids sent | Complete? |
| --- | --- | --- |
| 1.21 | 0, 10–13, 15–26 | floor; disputed |
| 1.28 beta 2 | 0, 15–21, 23, 25, 28, 29 | floor (fewer constants than 1.21 for the reason above) |
| 1.3 test | 0, 14–21, 23, 25, 28–30 | floor |
| 1.31, 1.32 | 0, 10–21, 23–30 | floor; 1.32 disputed |
| 1.33 to 1.37 | 0–31 | yes for constant ids; a few register sends uncounted |
| 1.38 | 0–24, 26–33 | as above |
| 1.39 | 0–24, 26–33, 80, 81 | as above |
| 1.41 rev1 | 0–24, 26–30, 32, 33, 80, 81 | unmeasured |
| 1.42 (NewMain), NewMain 24 and 26, 2.00 (rev0–rev3) | 0–24, 26–30, 32–34, 80, 81 | unmeasured |
| 2.01 (+rev1), 2.02, 2.02 rev1 | 0–24, 26–30, 32–36, 80, 81 | unmeasured |
| 2.02 rev2 | 0–24, 26–30, 32–37, 80, 81 | unmeasured |
| 2.03, 2.04, 2.05 (rev0–rev2), 2.1 test 2 and test 3 | 0–24, 26–30, 32–38, 80, 81 | unmeasured |
| NewWorld beta 1, beta 2 | the 2.1 test set without 7, 8, 11, 15, 16, 17, 20; disputed | unmeasured |
| 2.14 to 2.16 | the 2.1 set plus 41 | inferred; no binaries of 2.1 to 2.16 in the archive |
| 2.17 (the 2.17.1 binary) | 0–24, 26–30, 32–41, 43–45, 80, 81 | unmeasured |
| 2.22 | 0–24, 26–30, 32–35, 37–41, 43, 44, 80 | floor; 36, 42 and 45 not matched to a call site |
| 2.31 | the 2.22 set without 21, plus 46 | floor |
| 3.04 (Linux) | 0–24, 26–30, 32–38, 40, 41, 43, 80, 81 | yes, every game-code send site; listserver sends excluded |
| 3.153 (Mac OS X) | the 3.04 set plus 46, 50, 93, 96–98, 152, 154–158 | no: 2, 3, 15, 24, 29 and 80 assumed from 3.04 |
| 4.04r2 | 1, 2, 4–10, 12–19, 21–24, 26, 28, 29, 32, 33, 35–37, 41, 44, 50, 79–81, 92, 96, 130, 152, 154, 157, 158, 161 | floor |
| 4.20r6 (Mac) | the 4.04r2 set plus 34, 46, 162 | floor |
| 4.20r8 | 1, 2, 4–10, 12–19, 21–24, 26, 28, 29, 32, 33, 35–37, 41, 44, 50, 79–81, 92, 96, 130, 152, 154, 157, 158, 161, 162 | floor; some sends pass the id in a register |
| 5.00r7 | 1, 2, 4–10, 12–19, 21–24, 26, 28, 29, 32–37, 41, 44, 47, 50, 79–81, 92, 93, 96–98, 130, 152, 154–159, 161 | floor; whether 11 is in the list is disputed |
| 5.12 | 1, 2, 11, 23, 24, 34, 37, 38, 44, 47, 157 (seen in capture) | floor |
| 5.24r4 | the 5.12 set plus 158 (seen in capture) | floor |
| 5.30r3 | 1, 11, 37, 38 (seen in capture) | floor |
| 5.31r4 | 2, 37 (seen in capture) | floor |
| 6.00r2, 6.015 | 0–20, 22–24, 26–30, 32–38, 41, 44–48, 50, 79, 92, 93, 96–98, 130, 152, 154–159, 161, 162 | inferred from the 6.01 and 6.03 reads |
| 6.01r1 | the 6.03r7 set without 160 | unmeasured |
| 6.034 | as 6.03r7 | inferred |
| 6.03r7 | 0–20, 22–24, 26–30, 32–38, 41, 44–48, 50, 79, 92, 93, 96–98, 130, 152, 154–162 | yes |

Exceptions found in particular builds:

| Rule | Builds |
| --- | --- |
| No sender was found for 25 (`PLI_TOWEAPON`) or 31 (`PLI_PACKETCOUNT`) | 2.05 |
| 6.x sends none of 21 (`PUTNPC`), 25, 31, 39 (`TAMPERCHECK`) or 40 (`SHOOT`) as a constant | 6.01r1, 6.03r7 |
| 3.04 and 3.153 send no 39 or 44, unlike their Windows twin, and add 36 and 81 | 3.04, 3.153 |
| 6 (`PLI_TOALL`) is a real sender in every build of the family, with the chat text cut to 200 characters before sending | 2.00 to 2.1 test |
| No id is removed anywhere from 2.00 to 2.1 test 3, and none of 25, 31 or any id from 39 up has a constant send, so the tamper check (39) is not part of this family | 2.00 to 2.1 test |
| 36 and 38 look like TCP copies of UDP 25 and 26: one routine sends the UDP message, then repeats it over TCP when a flag says the server needs it; what sets the flag is unknown | 2.01 to 2.1 test |
| 2.02 rev1 has no `PLI_LANGUAGE` (37) send site and sends none in the lab; rev2 is the first build that sends 37 | 2.02 rev1, rev2 |
| Ids 4.x adds over 3.x: 44 (window list for PLO 182), 50 (large-packet length), 157 and 161 (file requests carrying an `i5` time), 158 (weapon by name), 162 | 4.20r8 |

## What the client sends right after login

The login packet itself is in [Versions and Encryption](versions-encryption.md). What the
client sends next, by build:

| Build | Messages after the login message, in order |
| --- | --- |
| 1.41 rev1 | one `PLI_PLAYERPROPS` with the login props, right after the first server message; no file requests |
| 2.02 rev1 | file requests and the login props; no 37 |
| 2.17 | 37, then 39 once; 44 with the window titles just before the login props |
| 2.22 | 37 `English`, 39, then 34 for the default images (sword, shield, body, bomb), 23, and 2; 44 in answer to the server's 182 |
| 2.31 | 37, 39, then in the second frame 46 before the props, 35 and 44 |
| 6.01r1, 6.03r7 | 37 right after login; no 39 |
