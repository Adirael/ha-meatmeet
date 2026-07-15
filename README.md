# Meatmeet S Pro — direct BLE access

Read a **Meatmeet S Pro** 6-channel Bluetooth thermometer directly, without the
phone app — either as a Home Assistant integration or a plain Python script.

This repo contains:

| Path | What it is |
|------|-----------|
| `custom_components/meatmeet/` | **Home Assistant custom integration** (HACS-installable) |
| `meatmeet.py` | **Standalone Python CLI** using [`bleak`](https://github.com/hbldh/bleak) |

> The station allows only **one** BLE connection at a time — close the phone app
> before reading from a PC or Home Assistant.

## Home Assistant integration

### Install via HACS (custom repository)

1. HACS → ⋮ → **Custom repositories** → add
   `https://github.com/Adirael/ha-meatmeet`, category **Integration**.
2. Install **Meatmeet**, then restart Home Assistant.
3. The thermometer is auto-discovered (Settings → Devices & Services). If not,
   **+ Add Integration → Meatmeet**.

### Manual install

Copy `custom_components/meatmeet/` into your HA `config/custom_components/` and
restart.

### Entities

One device (`Meatmeet S Pro`) with:

- **Zone 1–5** temperature (°C) and **Ambient** temperature
- **Station battery** / **Probe battery** (%)
- **Zone 1–5 target** — settable target temperature (persisted)
- **Zone 1–5 target reached** — binary sensor, on when the zone hits its target
- **Connected** — diagnostic binary sensor for the live BLE connection state
- **Signal strength** — diagnostic RSSI sensor (disabled by default; enable it in
  the entity settings if you want it)

Poll interval is configurable (1–60 s) via the device's **Configure** button.
Temperature sensors go *unavailable* (rather than showing stale values) when the
connection drops. A **Download Diagnostics** button on the device page dumps the
connection state, last-frame time, RSSI, and current readings (MAC redacted).

### Example: notify when a cook is done

```yaml
automation:
  - alias: Zone 1 reached target
    trigger:
      - trigger: state
        entity_id: binary_sensor.meatmeet_s_pro_zone_1_target_reached
        to: "on"
    action:
      - action: notify.notify
        data:
          message: "Zone 1 has reached its target temperature 🍖"
```

## Standalone CLI

```bash
python3 -m venv .venv && .venv/bin/pip install bleak
.venv/bin/python meatmeet.py --scan                    # find the MAC
.venv/bin/python meatmeet.py --address <MAC> --json    # stream readings
```

## Protocol

Connect, subscribe to notify characteristic `0000f5a1-…`, and poll by writing
`01 06 02` to write characteristic `a6ed0404-…`. The station replies with a
54-byte `"ME"` frame: 5 zone temps (uint16 LE, 0.01 °C; `≥0xA000` = probe
unplugged), ambient (uint8 °C), and station/probe battery levels.

## Credits

Protocol reverse-engineered from the
[Meatmeet-S-Pro-ESPhome](https://github.com/makerwolf/Meatmeet-S-Pro-ESPhome)
package by makerwolf.

## License

[MIT](LICENSE)
