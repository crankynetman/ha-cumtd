# CUMTD Bus - Home Assistant Integration

Never miss your CUMTD bus again! This integration tracks CUMTD bus arrivals and sends audio announcements to your speakers when it's time for you to leave.

## What This Does

Creates sensors that track how many minutes until your next bus arrives at a defined stop/line/direction. Each sensor polls the CUMTD API every 15 seconds and shows arrival predictions for buses that are currently running.

**GPS tracking:** Most CUMTD buses have GPS. The `is_real_time` attribute tells you if a specific bus prediction is based on GPS tracking (true) or schedule data (false).

You configure which stop(s) you care about and optionally filter by route and direction; The sensors are automatically updated so that you can use them (and their state changes) in the provided automations or your own custom automations.

## Automation Blueprints

Pre-built automations for providing TTS alerts. Importing these blueprints provides an easy way to get alerts for your configured stops to a specified list of speakers.

> **Note:** These blueprints require a TTS service to be configured in Home Assistant. Google Translate TTS works great and is free - just add it via Settings → Devices & Services → Add Integration → "Google Translate Text-to-Speech".

### Bus Arrival Alert

[![Import Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fcrankynetman%2Fha-cumtd%2Fblob%2Fmain%2Fcustom_components%2Fcumtd_bus%2Fblueprints%2Fautomation%2Fbus_arrival_alert.yaml)

Announces when your bus is approaching. Triggers when the sensor drops below your threshold (default 5 minutes).

#### Configure Arrival Alert

- Bus sensor to monitor
- Alert threshold in minutes
- Time window (weekdays 7-9am only, etc.)
- Which TTS service to use
- Which speaker(s) to announce on
- Optional: custom name and message template

**Default output:** "Jean Luc, your 5 Green bus is arriving in 5 minutes at Illinois Terminal"

**Custom template example:**

```jinja2
Bus {{ headsign }} arriving in {{ minutes }} minutes. {{ 'GPS tracked' if is_real_time else 'Scheduled time' }}.
```

Output: "Bus 5 Green arriving in 5 minutes. GPS tracked."

Available variables: `name`, `headsign`, `route`, `direction`, `minutes`, `stop_name`, `is_real_time`

### Time to Leave Alert

[![Import Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fcrankynetman%2Fha-cumtd%2Fblob%2Fmain%2Fcustom_components%2Fcumtd_bus%2Fblueprints%2Fautomation%2Ftime_to_leave_alert.yaml)

Tells you when to head out the door. You set your walk time and a buffer, it does the math.

#### Configure Time To Leave

- Bus sensor to monitor
- Walk time to stop (minutes)
- Buffer time (safety cushion)
- Time window for alerts
- TTS service and speaker(s)
- Optional: custom name

**Example:** Walk time is 5 minutes, buffer is 2 minutes. When the sensor shows 7 minutes, you get: "Jean Luc, time to leave! Your 5 Green bus arrives in 7 minutes"

## Requirements

- Home Assistant (tested on 2026.1)
- CUMTD API key from [developer.cumtd.com](https://developer.cumtd.com) (free, approval is automatic.)

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click the three dots menu (⋮) in the top right corner
3. Select **Custom repositories**
4. Add this repository URL: `https://github.com/crankynetman/ha-cumtd`
5. Select **Integration** as the category
6. Click **Add**
7. Search for "CUMTD Bus" in HACS and click **Download**
8. Restart Home Assistant
9. Add via Settings → Devices & Services → Add Integration → "CUMTD Bus"

### Manual Install

1. Copy `custom_components/cumtd_bus/` to your HA config directory
2. Restart Home Assistant
3. Add via Settings → Devices & Services → Add Integration → "CUMTD Bus"

## Setup

The config flow walks you through three steps:

1. **API Key** - Paste your CUMTD developer key
2. **Stop Search** - Type a street name or intersection, pick your stop
3. **Filters** (optional) - Narrow down to specific routes/directions

You can configure multiple stops by going through the integration options. Each stop gets its own sensor.

## Sensors

Creates one sensor per configured stop/route combo.

**State:** Integer minutes until arrival (or `unavailable` if no buses coming)

**Attributes:**

- `headsign` - Route and direction like "5E Green"
- `route` - The route number like "5"
- `direction` - "Eastbound", "Westbound", etc.
- `stop_name` - The actual stop name
- `expected` - ISO timestamp of expected arrival
- `scheduled` - ISO timestamp of scheduled arrival
- `is_real_time` - Boolean, true if GPS-tracked
- `trip_id` - CUMTD trip identifier
- `stop_id` - CUMTD stop identifier

If you configure the same stop with different route filters, the sensor names include the filters to avoid collisions. For example:

- `sensor.illinois_terminal_next_bus` (all routes)
- `sensor.illinois_terminal_route_5_next_bus` (only route 5)
- `sensor.illinois_terminal_route_5_eastbound_next_bus` (route 5 eastbound only)

## Writing Your Own Automations

The blueprints above handle most use cases, but here's how to write custom automations:

**Simple threshold alert:**

```yaml
alias: "Bus Alert - Morning Route 5"
trigger:
  - platform: numeric_state
    entity_id: sensor.illinois_terminal_route_5_eastbound_next_bus
    below: 5
condition:
  - condition: time
    after: "07:00:00"
    before: "09:00:00"
    weekday:
      - mon
      - tue
      - wed
      - thu
      - fri
action:
  - service: tts.speak
    data:
      entity_id: tts.google_translate
      media_player_entity_id: media_player.bedroom
      message: "Your bus arrives in {{ states('sensor.illinois_terminal_route_5_eastbound_next_bus') }} minutes"
mode: single
```

**Conditional on real-time data:**

```yaml
condition:
  - condition: template
    value_template: "{{ state_attr('sensor.illinois_terminal_next_bus', 'is_real_time') }}"
```

**Only if bus is actually tracked:**

```yaml
condition:
  - condition: template
    value_template: "{{ states('sensor.illinois_terminal_next_bus') not in ['unknown', 'unavailable'] }}"
```

## Troubleshooting

**"Unable to connect to CUMTD API"**
Check your API key by trying it directly: `https://developer.cumtd.com/api/v2.2/json/getstops?key=YOUR_KEY`

**Sensor shows "unavailable"**
No buses scheduled/running for your stop+filter combo. Check the CUMTD site or the Transit app to verify.

## Development

### Dependency Management

This project uses [uv](https://docs.astral.sh/uv/) for dependency management:

```bash
# Install dependencies
uv sync

# Add a new dependency
uv add package_name

# Add a dev dependency
uv add --dev package_name

# Update all dependencies
uv lock --upgrade
```

### Pre-commit Hooks

Install pre-commit hooks to automatically run ruff, pyright, and tests before each commit:

```bash
uv run pre-commit install
```

Run manually on all files:

```bash
uv run pre-commit run --all-files
```

### Tests

 `uv run pytest`
 > **Note:** API tests use VCR to mock the API.

**Type checking:** `uv run pyright`
**Linting:** `uv run ruff check`

### Re-recording API Cassettes

Tests use [VCR.py](https://vcrpy.readthedocs.io/) to record/replay API responses.

To re-record when the CUMTD API changes:

```bash
export CUMTD_API_KEY=your_api_key_here
export VCR_RECORD_MODE=all
uv run pytest tests/test_api.py
```

This regenerates all cassettes with fresh API responses (API keys are automatically scrubbed).

To run in a dev Home Assistant instance, use the included docker-compose setup.

## Contributing

File issues or PRs at [github.com/crankynetman/ha-cumtd](https://github.com/crankynetman/ha-cumtd).
