"""Low-cardinality Prometheus instruments for the controller lifecycle."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

REGISTRY = CollectorRegistry()
POLL_TOTAL = Counter(
    "dumpster_fire_polls",
    "Austin feed poll attempts by outcome.",
    ("result",),
    registry=REGISTRY,
)
POLL_DURATION = Histogram(
    "dumpster_fire_poll_duration_seconds",
    "Time spent fetching and consuming an Austin feed poll.",
    registry=REGISTRY,
)
POLL_SUCCESS = Gauge(
    "dumpster_fire_poll_success",
    "Whether the most recent Austin feed poll succeeded.",
    registry=REGISTRY,
)
LAST_POLL = Gauge(
    "dumpster_fire_last_poll_timestamp_seconds",
    "Unix timestamp of the most recent Austin feed poll attempt.",
    registry=REGISTRY,
)
LAST_SUCCESS = Gauge(
    "dumpster_fire_last_success_timestamp_seconds",
    "Unix timestamp of the most recent successful Austin feed poll.",
    registry=REGISTRY,
)
CURRENT_RECORDS = Gauge(
    "dumpster_fire_feed_records",
    "Qualifying records in the latest Austin feed response.",
    registry=REGISTRY,
)
SEEN_INCIDENTS = Gauge(
    "dumpster_fire_seen_incidents",
    "Incident IDs retained for deduplication.",
    registry=REGISTRY,
)
INCIDENT_BATCHES = Counter(
    "dumpster_fire_incident_batches",
    "New qualifying incident batches since this process started.",
    registry=REGISTRY,
)
INCIDENT_RUN_ID = Gauge(
    "dumpster_fire_incident_run_id",
    "Persistent monotonic incident batch ID exposed by the controller.",
    registry=REGISTRY,
)
FRESH_INCIDENTS = Counter(
    "dumpster_fire_new_incidents",
    "New qualifying incident IDs observed during this process lifetime.",
    registry=REGISTRY,
)
ACTIVITY_ACTIVE = Gauge(
    "dumpster_fire_activity_active",
    "Whether a recent-incident activity deadline is pending.",
    registry=REGISTRY,
)
ACTIVITY_DEADLINE = Gauge(
    "dumpster_fire_activity_deadline_timestamp_seconds",
    "Unix timestamp when the activity window expires, or zero if inactive.",
    registry=REGISTRY,
)
CONTROLLER_ENABLED = Gauge(
    "dumpster_fire_controller_enabled",
    "Whether the controller is permitted to submit trigger commands.",
    registry=REGISTRY,
)
FLAME_STATE_KNOWN = Gauge(
    "dumpster_fire_flame_state_known",
    "Whether the latest flame-state observation is known.",
    registry=REGISTRY,
)
FLAME_STATE = Gauge(
    "dumpster_fire_flame_state",
    "Latest observed flame state (one means on; check known and observation age).",
    registry=REGISTRY,
)
FLAME_STATE_OBSERVED = Gauge(
    "dumpster_fire_flame_state_observed_timestamp_seconds",
    "Unix timestamp of the latest flame-state observation.",
    registry=REGISTRY,
)
TRIGGER_SUBMISSIONS = Counter(
    "dumpster_fire_trigger_submissions",
    "Trigger commands submitted to ESPHome; the toggle has no acknowledgement.",
    ("desired_state",),
    registry=REGISTRY,
)
