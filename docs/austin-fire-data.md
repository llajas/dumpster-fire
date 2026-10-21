# Austin Fire Data

## Source

The project uses the City of Austin Socrata dataset:

```text
Dataset ID: wpu4-x69d
```

API:

```text
https://data.austintexas.gov/resource/wpu4-x69d.json
```

## Matching incident types

The exact dispatch labels used by the project are:

```text
DUMP - Dumpster Fire
TRASH - Trash Fire
```

These labels were confirmed against real historical records.

## Fields used

The poller requests:

```text
traffic_report_id
published_date
issue_reported
address
traffic_report_status
```

The critical identity field is:

```text
traffic_report_id
```

That ID is used for deduplication.

Address is deliberately not used as an identity because multiple real incidents can occur at the same location.

## Query

The effective SoQL query is:

```sql
SELECT
  traffic_report_id,
  published_date,
  issue_reported,
  address,
  traffic_report_status
WHERE
  issue_reported IN (
    'DUMP - Dumpster Fire',
    'TRASH - Trash Fire'
  )
ORDER BY published_date DESC
LIMIT 25
```

Example curl:

```bash
curl -sS --get \
  'https://data.austintexas.gov/resource/wpu4-x69d.json' \
  --data-urlencode '$select=traffic_report_id,published_date,issue_reported,address,traffic_report_status' \
  --data-urlencode "\$where=issue_reported IN('DUMP - Dumpster Fire','TRASH - Trash Fire')" \
  --data-urlencode '$order=published_date DESC' \
  --data-urlencode '$limit=25' \
  | jq .
```

## Why the project does not filter only ACTIVE incidents

An early design queried only:

```text
traffic_report_status = ACTIVE
```

That is unsafe for this use case.

A fire can become `ARCHIVED` before the next five-minute poll. If the automation only watched currently active records, a short-lived incident could disappear before Home Assistant ever observed it.

Instead, the project fetches the most recent matching incidents regardless of status and deduplicates by `traffic_report_id`.

## Poll cadence

The Home Assistant side polls approximately every five minutes.

Polling much more aggressively is unnecessary for this project and provides little practical benefit.

## Event semantics

The feed is interpreted as an event stream, not desired state.

A new incident means:

> A qualifying Austin fire report has appeared.

Once an incident ID is seen, it is considered consumed.

It is never held as a pending command to be replayed later if the lamp happens to be off.
