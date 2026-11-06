---
name: digital-works-dwm
description: Use when reading, editing, generating, fixing or simulating Digital Works .dwm circuit files (counters, calendars, macros, flip-flops) with the DWM-kit toolkit.
---

# Digital Works .dwm work with DWM-kit

## 0. Get the kit (Python 3.8+, stdlib only)
The kit is bundled next to this file: `SPEC.md`, `README.md`, `dwm/`, `tests/`, `examples/`.
- Copy it to a writable working folder and work there: `cp -r <this skill's folder> ./dwm-kit && cd dwm-kit`.
- Inside a clone of the DWM-kit repo (e.g. Claude Code), the kit is the repo root.
- If the bundle is missing (e.g. this SKILL.md was copied alone), get it from https://github.com/Vix0061/DWM-kit (attach/clone the repo, or ask the user to attach the zip from that repo's `dist/` folder).
- Smoke test: `python -m tests.test_kit` must print 4 `ok` lines.
Work on copies of the user's .dwm files, never on the uploads in place.

## 1. Load knowledge first
- Read `SPEC.md` completely before touching any file: binary format, device table, macros, text templates, simulation semantics, timing model, design rules R1-R7.
- Module map (details in `README.md`): `dwm.model` (read/write/load/dump), `dwm.graph` (devices, pins, wires, ext_pins, walk_macros, Flat), `dwm.tpl` (make/place from SPEC templates, new_root), `dwm.edit` (Canvas, connect, connect_pins, connect_to_net, disconnect), `dwm.router`, `dwm.sim` (UnitSim, RandomDelaySim, run_clocked), `dwm.hazard` (best, hazards), `dwm.check` (report; CLI `python -m dwm.check f.dwm`).

## 2. Understand the circuit before editing
- `head, root, _ = model.read(path)`; list canvases with `graph.walk_macros(root)`.
- Map names: macro titles (`graph.macro_title`), port labels (`graph.ext_pins`), symbol texts.
- Flatten (`graph.Flat`) and print the netlist of the part you will change. Identify roles (counter bits, FIN/reset detectors, clock gating, next-stage clock) before changing anything.
- Simulate the ORIGINAL first (UnitSim and RandomDelaySim): student files often have pre-existing bugs (floating inputs, wrong detector bits).

## 3. Edit
- Always load -> mutate graph -> dump. Never patch bytes.
- New devices: `tpl.place(canvas, 'TJKFlipFlop', x, y)`. Connections: `edit.connect(edit.Canvas(m), pin, target_pin)`; it routes orthogonally, avoids chip bodies and other pins, and taps existing nets with a solder.
- Reuse free gates inside student chip macros (74xx-style "AND"/"OR"/"Not" macros): a gate whose ext pins have no wires is free.
- Ripple-counter detectors: use `hazard.best(digits, value)` and SPEC rules R1-R7. A bit that falls and the bit it makes rise must enter the SAME gate; never pad a literal through AND(x,Vcc) chains or balance depths. Hard cases: reset = AND(FIN, x) as one gate.
- Keep user-written texts (names, university, titles) and their positions unless asked.
- When one process edits several macros, rebuild `Flat`/lookups after each edit.

## 4. Verify (mandatory before delivering)
- `python -m dwm.check out.dwm`: roundtrip True, no invariant errors, no wire over chip, no diagonal segments, no new undriven nets (compare with the original).
- UnitSim: designed sequence/values reached.
- RandomDelaySim: >=24 seeds, clock half-period >=60 steps; every stage stops/cycles exactly as designed in every mode (e.g. stop, cycle, reset). Any failing seed = likely failure in Digital Works: fix and retest ALL stages.
- Slow full runs: test each macro alone by driving its ext-pin nets, then run the full circuit once.

## 5. Deliver
- Send the .dwm with a short summary: what changed, how it was verified, what the user must set in Digital Works (input meanings, clock speed).
- Say plainly it was verified in the simulators, not in Digital Works itself; ask the user to confirm there. If they report a difference, reproduce it in RandomDelaySim before guessing.
- Answer in the user's language (often Spanish).

## 6. If SPEC.md is wrong or incomplete
For an unknown class or field, add a schema (`dwm/model.py`) or template (SPEC.md TEMPLATES) and a compact SPEC line (LLM-oriented, no code sections), then tell the user so the repo can be updated.
