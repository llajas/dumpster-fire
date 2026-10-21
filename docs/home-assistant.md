# Home Assistant Integration

## Overview

The Home Assistant implementation is split into two pieces:

- `austin_dumpster_fire_poll.py` — polling and durable event detection
- `austin_dumpster_fire.yaml` — Home Assistant policy and physical-device behavior

This split keeps external API/state-management logic out of Home Assistant templates while keeping all physical-lamp decisions inside Home Assistant.

## Poller

The poller runs approximately every five minutes through a Home Assistant `command_line` sensor.

Responsibilities:

- query the City of Austin Socrata API,
- validate JSON and expected schema,
- load persistent state,
- seed existing incidents on first run,
- identify unseen `traffic_report_id` values,
- persist those IDs atomically,
- prune old state,
- emit JSON for Home Assistant.

The poller never presses the physical button and never inspects the flame-state entity.

## Monotonic event state

The poller exposes a numeric `new_run_id`.

That value increments **only when one or more previously unseen matching incidents are discovered**.

This is used as the state of the Home Assistant polling sensor.

That means Home Assistant can react to a clean monotonic transition rather than trying to infer event changes from incident count or a list attribute.

## First-run behavior

The first successful run intentionally does not trigger the lamp.

Instead:

1. Fetch the current recent matching incidents.
2. Seed all of their IDs into the persistent seen set.
3. Mark the state initialized.
4. Report zero new incidents.

This prevents historical incidents from firing the lamp immediately after deployment.

## Persistent state

The poller stores state at:

```text
/config/austin_dumpster_fire_state.json
```

Writes are atomic:

1. write temporary file,
2. flush,
3. `fsync`,
4. `os.replace()`.

If persistence fails, the poller deliberately suppresses the new incident report so that Home Assistant does not act on an event that was not durably recorded.

## Activity timer

Home Assistant exposes:

```text
timer.austin_dumpster_fire_activity
```

The default timeout is controlled by:

```text
input_number.austin_dumpster_fire_timeout_minutes
```

Default: 15 minutes.

A new incident batch:

- turns the lamp on if it is currently off,
- leaves it alone if it is already on,
- restarts the activity timer in either case.

When the timer expires:

- if Flame State is ON, press Trigger once,
- if Flame State is OFF, do nothing,
- if Flame State is unavailable/unknown, do nothing.

This makes the lamp mean:

> There has been Austin dumpster/trash-fire activity recently.

## Enable / disable

The entire Austin-driven behavior can be disabled without touching ESPHome:

```text
input_boolean.austin_dumpster_fire_enabled
```

The physical Trigger and Flame State entities remain available.

## Observability

The package exposes helper sensors for:

- last successful poll,
- last incident,
- recent/seen count,
- poll health.

Operational decisions are also logged under:

```text
austin_dumpster_fire
```

This makes it possible to determine why the lamp turned on or off.

## Failure behavior

Failures are intentionally fail-safe.

On HTTP, DNS, JSON, schema, or state-write failure:

- no new physical trigger is requested,
- no activity timer is restarted,
- durable seen state is not cleared,
- poll health reports failure,
- the next polling cycle retries.

## Deployment in the homelab

The production Home Assistant instance runs in Kubernetes.

The homelab Helm chart packages the two project files into a ConfigMap, mounts them into the Home Assistant pod, and copies them into `/config` during initialization.

A ConfigMap checksum annotation participates in Deployment rollout behavior.

The standalone project repo contains the source and documentation; the homelab repo owns deployment.
