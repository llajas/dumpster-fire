# Standalone controller migration

The cutover is complete. The homelab Home Assistant chart no longer packages the
legacy incident automation or poller; it retains the ESPHome integration and a
status/manual-light package. The legacy HA files remain in this repository for
reference and rollback, but restoring them requires restoring the chart support too.

The ESPHome firmware stays unchanged. Home Assistant keeps the ESPHome integration,
including the physical `Trigger` button and `Flame State` binary sensor. The
standalone service owns incident polling, durable deduplication, an activity
deadline and decisions to press the toggle. It talks directly to the ESP32's
encrypted native API, not through Home Assistant.

## Prepare (historical)

1. The `.woodpecker/default.yaml` pipeline builds from the root `Dockerfile`
   and publishes `registry.lajas.tech/dumpster-fire-controller` as both
   `latest` and the commit SHA. It follows the existing registry plugin and
   credentials (`registry_username` and `registry_token`) and runs on pushes
   to `main` and the `Rebuild` cron. The current homelab cluster nodes are
   `linux/amd64`; verify the published image architecture before syncing the
   deployment. CI does not deploy the homelab chart or change replica count.
 2. Identify the ESP32's stable LAN address reachable from the Kubernetes pod
   on TCP port 6053. Do not assume `.local` mDNS resolves from a pod.
 3. Create a 1Password item named **Dumpster Fire Controller** in the shared
    `homelab` vault, then add two fields: `host` (the ESP32's stable LAN IP or
    DNS hostname) and `api-key` (the existing ESPHome native API encryption
    key). The Kubernetes Secret is
   `dumpster-fire-api` in namespace `dumpster-fire`; the existing key remains
   configured in ESPHome and Home Assistant, and native API supports multiple
   clients. `host` is the exact field name to use for the IP address. Never
   commit either value. The homelab chart references the supplied item ID.
4. The workload reads those item fields into `AUSTIN_FIRE_HOST` and
   `AUSTIN_FIRE_API_KEY`. The controller defaults to a 15-minute activity
   timeout; set `AUSTIN_FIRE_TIMEOUT_MINUTES` if the old HA helper has a
   different setting. The service does not consume HA helpers, so behavior
   remains independent of HA availability.
5. Leave the old HA package enabled and do **not** start the new controller
   yet. Verify the HA activity timer is idle and the physical lamp is off;
   the old HA timer is not stored in the poller's JSON and cannot be copied.

## Exclusive cutover (historical)

The trigger is a toggle, not an idempotent on/off switch. **Never run the old
HA automation and an enabled new controller at the same time.**

1. The former chart cutover disabled the legacy HA package and enabled the
   status package. The current chart has removed the legacy package option and
   continues to remove stale copies from persistent `/config`. Confirm the old
   HA automations and command-line sensor are no longer running. Their entity
   registry entries can persist as unavailable until removed manually. Do
   **not** remove the ESPHome integration/device.
2. Copy `/config/austin_dumpster_fire_state.json` from the Home Assistant PVC
   into the new controller PVC as
   `/data/austin_dumpster_fire_state.json`, with permissions writable by UID
   10001. Copy while the legacy poller is stopped and the new controller is
   scaled to zero. The old `initialized`, `seen` and `new_run_id` fields are
   accepted by the new service. Preserve a backup of the original file.
   The first successful poll after importing an unversioned legacy state
   seeds all currently returned IDs without pressing the toggle: the old
   48-hour pruning could have forgotten an incident still in the feed.
   Incidents that arrive during this brief cutover may therefore be consumed
   without activating the lamp.
3. In homelab `apps/dumpster-fire/values.yaml`, set `replicas: 1` and
   `AUSTIN_FIRE_ENABLED: "true"`, then sync the Argo CD application. The
   chart provides the retained `dumpster-fire` PVC, image, and 1Password
   Secret. Keep `Recreate`; only one writer may own the
   state and trigger. If the state file is missing, the first successful poll
   seeds recent incidents without activating the lamp. Invalid state causes
   startup to fail instead of silently resetting deduplication.
4. Verify a successful poll, a readable flame state, and Home Assistant's
   existing ESPHome button and binary sensor. Exercise an incident with a
   controlled feed in a **non-production** instance before trusting a real
   incident. Confirm expiry only presses when the physical flame is on.

Home Assistant's status package (synced by the homelab chart) reads the
controller's read-only `/status` endpoint through an internal ClusterIP
service every 60 seconds. It replaces the command-line poll entity with
`sensor.austin_dumpster_fire_controller`;
the existing last-poll, last-incident, seen-count, and poll-health template
entities continue to use their previous unique IDs. An activity-deadline
entity is added. The status package also exposes `light.office_dumpster_fire`,
whose state follows the measured flame sensor and whose manual on/off actions
press the Trigger only when needed. Manual actions can still race with the
standalone controller because the physical input is a toggle. The old
command-line poll entity may remain as an unavailable registry entry until
removed in HA's entity settings. If the controller is unavailable, its
diagnostic entities become unavailable; the ESPHome device remains on its own
integration. The controller never needs HA to operate the toy.

## Failure semantics and rollback

- Feed/JSON/write failures do not consume incidents or toggle the lamp.
  New incident IDs are consumed even when the controller is disabled.
- When the ESP32 is unreachable, the service does not guess the flame state.
  A pending deadline is retained for reconciliation. The toy itself has an
  approximately one-hour stock auto-shutoff.
- A press has no acknowledgment. The service deliberately persists the
  attempt before submitting a non-idempotent command; a crash can lose an
  activation or an expiry press, but it must not replay a toggle blindly.
- The feed requests the newest 25 matching incidents, so an extended outage
  or a burst of more than 25 can miss older unseen IDs. The controller retains
  seen IDs still present in the feed past the 48-hour pruning threshold.
- To roll back, first restore the removed legacy HA chart packaging from
  version control, then scale the standalone controller to zero. Copy its state
  JSON back to the HA PVC before restarting HA with the legacy package. Do not
  run both controllers during rollback. HA cannot import a new controller's
  active deadline, so wait for the lamp to be off before rolling back, or manage
  its state explicitly using the physical flame sensor.

The controller, image, Secret, HA diagnostics, and manual light are now deployed.
The legacy HA package files remain in this repository for rollback/reference only;
the homelab chart no longer ships them.
