# ESPHome

## Purpose

ESPHome provides two interfaces between the physical Dumpster Fire and Home Assistant:

1. A momentary **Trigger** button.
2. A real **Flame State** binary sensor.

The hardware trigger is intentionally modeled as a button rather than a switch because the toy's input is a toggle action, not a stateful digital control.

## Trigger

The working trigger GPIO is `GPIO25`.

Representative configuration:

```yaml
output:
  - platform: gpio
    pin: GPIO25
    id: dumpster_trigger

button:
  - platform: template
    name: "Trigger"
    icon: "mdi:fire"
    on_press:
      - output.turn_on: dumpster_trigger
      - delay: 100ms
      - output.turn_off: dumpster_trigger
```

The physical GPIO output drives the **input side of the trigger PC817**, not the toy's sensitive trigger node directly.

## Flame state

A second PC817 watches the original flame LED supply.

Its output is connected to a spare ESP32 GPIO. The signal follows the physical flame flicker, so ESPHome applies a delayed-off filter to present a stable state to Home Assistant.

Representative configuration:

```yaml
binary_sensor:
  - platform: gpio
    pin:
      number: GPIO27
      mode:
        input: true
        pullup: true
      inverted: true
    name: "Flame State"
    id: dumpster_flame_state
    filters:
      - delayed_off: 1s
```

The exact delayed-off value can be tuned. The purpose is simply to bridge the natural dark intervals in the flickering flame effect.

## Home Assistant entity

The deployed Home Assistant flame-state entity is:

```text
binary_sensor.office_dumpster_fire_flame_state
```

This entity is treated as authoritative physical truth.

The Trigger entity is treated only as a command.

## Why this distinction matters

The physical toy can change state independently of Home Assistant.

Therefore this model is deliberately used:

```text
command:
  Trigger button

truth:
  Flame State binary sensor
```

Home Assistant never assumes that a previous Trigger press means the light must currently be on.
