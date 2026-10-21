# ESPHome Source

The sanitized production ESPHome configuration is:

- [`dumpster-fire-alert.yaml`](dumpster-fire-alert.yaml)

The committed file preserves the actual deployed GPIO behavior:

- `GPIO25` → trigger PC817 → physical toggle input
- `GPIO27` ← flame-state PC817 → binary sensor
- 100 ms trigger pulse
- 500 ms delayed-off filter for the flickering flame output

Secrets are intentionally not committed. The API encryption key and fallback-hotspot password are replaced with `OMITTED`, while Wi-Fi credentials remain referenced through ESPHome `!secret`.

See [../docs/esphome.md](../docs/esphome.md) for the hardware/software behavior in context.
