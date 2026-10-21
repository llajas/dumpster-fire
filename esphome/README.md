# ESPHome Source

The ESPHome side of the project currently lives on the physical device and is documented in [../docs/esphome.md](../docs/esphome.md).

The key interfaces are:

- `GPIO25` → trigger PC817 → physical toggle input
- spare input GPIO → flame-state PC817 → binary sensor

If the complete production ESPHome YAML is exported into this repository later, place it in this directory and update the documentation to reference it directly.
