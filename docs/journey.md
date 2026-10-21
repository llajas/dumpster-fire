# The Journey

## The idea

The premise was simple:

> When Austin reports an actual dumpster fire, make a tiny plastic Dumpster Fire on my desk light up.

The implementation was not simple.

## Starting point

The base device was a 100% Soft Dumpster Fire Night Light with:

- flickering flame LEDs,
- tap activation,
- 3× AAA batteries,
- an approximately one-hour automatic shutoff.

The initial assumption was that somewhere inside there would be a button-like signal we could emulate with an ESP32.

That assumption lasted only briefly.

## Discovering the trigger

Shorting obvious switch-area points did not reproduce the tap behavior.

Eventually a point around `Q3` / `R18` was found where merely touching it with a meter probe triggered the toy.

The measurements became stranger:

- the node sat around half a volt,
- the other side of R18 sat near the supply rail,
- R18 was marked `106`, or 10 MΩ,
- a floating meter probe could trigger it,
- a completely disconnected Dupont wire could trigger it,
- touching insulated wire connected to the node could sometimes be enough.

The trigger was not behaving like a normal logic input. It was an extremely high-impedance capacitive/noise-sensitive node.

## The first ESP32 attempt

The first approach was obvious:

```text
ESP32 GPIO → trigger node
```

It was also unreliable.

The toy would randomly turn on and off, especially around ESP32 boot/reset activity. Moving GPIOs did not solve the fundamental problem.

The ESP32 itself was electrically polluting the sensitive node.

## The capacitor

A 1 nF ceramic capacitor was inserted between the control lead and trigger node.

That reproduced the behavior of the successful floating-wire experiments: the toy wanted a transient disturbance, not a sustained logic level.

It helped, but direct GPIO attachment was still too noisy.

## The optocoupler breakthrough

A PC817 optocoupler module was already available.

The input side was driven by ESP32 GPIO25.

The output side was powered from the toy supply, and its OUT terminal was connected through the 1 nF capacitor to the R18/Q3 trigger node.

Once VCC was connected on the output side, it worked cleanly.

That became the final trigger interface.

## Permanent power

The toy had already been running for years from a 4.5 V wall supply feeding a fake-AAA adapter.

After adding the ESP32 and boost converter, the fake-AAA assembly failed.

The wall brick itself still measured 4.5 V; the faux battery assembly measured zero.

That failure pushed the project toward a cleaner permanent external-power arrangement rather than returning to batteries.

## State becomes the real problem

At this stage Home Assistant could trigger the toy, but the input was still fundamentally a toggle.

That meant Home Assistant could not know whether the lamp was actually on.

A trigger press might mean:

- OFF → ON,
- ON → OFF.

The toy could also change state on its own through physical taps and its built-in timeout.

The project needed feedback.

## Sensing the flame circuit

The flame LED output measured:

- millivolts when off,
- roughly 3.0–3.5 V while on,
- a brief turn-on spike near 5 V.

A second PC817 was added across the existing flame LED supply.

Its indicator LED visibly flickered exactly with the toy flame, proving that the sensing path was observing the real output.

The PC817 output went back to the ESP32, and ESPHome used a delayed-off filter to turn that flickering pulse train into a stable binary sensor.

At that point the project finally had a clean separation:

```text
Trigger = command
Flame State = truth
```

## The soldering side quest

Getting there involved some less glamorous work.

The original flame wires were accidentally desoldered from tiny pads. New wires were run through the plated holes and soldered back to the annular rings, then spliced to the original flame leads.

This part of the project provided several lessons about:

- tip oxidation,
- flux,
- pre-tinning,
- solder wick,
- mechanical strain,
- not repeatedly reheating tiny pads.

## Finding the Austin data

Austin publishes real-time fire incident data through Socrata.

The exact labels needed for the joke turned out to exist:

```text
DUMP - Dumpster Fire
TRASH - Trash Fire
```

That removed the need for fuzzy text matching.

Historical queries also revealed an important implementation detail: matching incidents could already be `ARCHIVED` by the time Home Assistant polled.

The design therefore shifted from "watch ACTIVE fires" to "watch for previously unseen incident IDs."

## Making it reliable

The final software design uses:

- exact dispatch labels,
- `traffic_report_id` as event identity,
- first-run seeding,
- persistent seen-ID state,
- atomic writes,
- five-minute polling,
- a monotonic `new_run_id`,
- real physical flame state,
- a configurable activity timer,
- fail-safe behavior when the sensor or API is unavailable.

If several new incidents arrive in one polling cycle, the toy is still triggered at most once.

If another incident arrives while the lamp is already on, the timer is extended rather than toggling the toy.

## The final meaning

The light no longer means merely:

> A dumpster fire happened at some point.

It means:

> Austin has had dumpster/trash-fire activity recently.

That distinction is what turned a funny hardware hack into a surprisingly robust little event-driven system.
