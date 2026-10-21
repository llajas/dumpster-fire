# Hardware

## Overview

The project preserves the original Dumpster Fire night-light electronics and adds an ESP32-based control and sensing layer around them.

The final hardware has two independent optocoupler interfaces:

1. **Trigger interface** — lets the ESP32 emulate the original tap behavior without directly exposing the high-impedance trigger node to GPIO noise.
2. **Flame-state interface** — watches the original flame LED supply and reports the actual physical light state back to ESPHome/Home Assistant.

## Main components

- 100% Soft Dumpster Fire Night Light
- ESP32-WROOM-32 DevKit-style board
- MT3608 boost converter
- 2× PC817 optocoupler modules
- 1 nF ceramic capacitor
- 4.5 V external DC supply
- Female barrel-to-screw-terminal adapter
- Hookup wire
- Heat-shrink
- Solder and flux

## Power

The original toy ran from 3× AAA batteries.

The finished build uses an external 4.5 V supply. The 4.5 V rail powers the original toy electronics directly and also feeds an MT3608 boost converter adjusted to approximately 5 V for the ESP32.

Conceptually:

```text
4.5 V external supply
        │
        ├── original Dumpster Fire PCB
        │
        └── MT3608
             │
             └── ~5 V → ESP32 VIN
```

The original physical ON/OFF switch is retained in the power path.

## Trigger discovery

The original board does not expose a conventional pushbutton input.

A trigger point was discovered around `Q3` / `R18`. `R18` is marked `106`, corresponding to **10 MΩ**.

The node behaved as an extremely high-impedance input:

- touching it with a meter probe could trigger the toy,
- a floating Dupont lead could trigger it,
- even capacitive coupling through insulated wire could be enough.

Direct ESP32 GPIO control was therefore unreliable. Boot transitions and general electrical noise could randomly toggle the toy.

## Trigger interface

The stable trigger path became:

```text
ESP32 GPIO25
    │
    ▼
PC817 INPUT
    │
    ▼
PC817 transistor output
    │
   1 nF
    │
    ▼
R18/Q3 trigger node
```

The output side of the PC817 is powered from the toy supply so that its output transition is clean and well-defined.

The 1 nF capacitor AC-couples the transition into the sensitive trigger node rather than applying a sustained DC level.

This arrangement proved dramatically more stable than attaching the ESP32 directly.

## Flame-state sensing

The trigger is a toggle. That means sending a command does not tell us the resulting state with certainty.

The toy can also change state through:

- a physical tap or bump,
- its built-in auto-off timer,
- a manual Home Assistant button press,
- power interruption.

The flame LED supply was measured at approximately:

- OFF: millivolts
- ON: 3.0–3.5 V
- brief turn-on spike: approximately 5 V

A second PC817 optocoupler is wired **in parallel** with the existing flame LED supply.

The original flame LED wires remain connected normally; the optocoupler merely observes the same voltage.

Conceptually:

```text
Original toy flame output
        │
        ├── original flame LEDs
        │
        └── PC817 INPUT
                 │
                 ▼
             PC817 OUT
                 │
                 ▼
             ESP32 GPIO
```

Because the flame effect flickers, the optocoupler output also flickers. ESPHome smooths this into a stable binary state with a delayed-off filter.

## Mechanical lessons

The smallest solder pads in the toy are fragile.

A few practices mattered:

- Keep the R18 trigger lead mechanically strain-relieved.
- Do not leave long exposed conductors on tiny pads.
- Route small wires so they leave pads parallel to the PCB when possible.
- Pre-tin both the wire and pad before joining them.
- Avoid repeatedly reheating tiny pads.
- Insulate the undersides of the ESP32, MT3608, and PC817 boards from the original PCB.
- Leave enough service slack that opening the toy does not pull on delicate solder joints.

## External connector

The original fake-AAA barrel-power adapter failed during the project.

Rather than return to batteries, the final build uses a female barrel-to-screw-terminal adapter and dedicated hookup wire routed into the toy, preserving a permanent external-power setup.
