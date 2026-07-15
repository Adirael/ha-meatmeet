# Meatmeet — Home Assistant custom integration

Native Home Assistant integration for the **Meatmeet S Pro** 6-channel Bluetooth
thermometer. Uses Home Assistant's own Bluetooth stack (no ESPHome device
required) — any BT adapter/proxy HA can see will work.

## Entities

Exposed as one device (`Meatmeet S Pro`) with these sensors:

| Sensor | Unit | Notes |
|--------|------|-------|
| Zone 1–5 | °C | 0.01 °C resolution; shows *unavailable* when a probe is unplugged |
| Ambient | °C | integer grip temperature |
| Station battery | % | diagnostic |
| Probe battery | % | diagnostic |
| Zone 1–5 target | °C | settable target temperature (`number`), persisted across restarts |
| Zone 1–5 target reached | on/off | `binary_sensor`, on once the zone reaches its target — use as an automation trigger |
| On station | on/off | `binary_sensor`, on while the probe is docked on the charging station |
| Connected | on/off | diagnostic `binary_sensor` — live BLE connection state |
| Signal strength | dBm | diagnostic RSSI sensor (disabled by default) |

The integration also supports **Download Diagnostics** (device page → ⋮) for a
JSON snapshot of connection state, last-frame time, RSSI, and readings.

Target temperatures are stored in Home Assistant (the station's BLE protocol is
read-only), so they drive HA-side alarms/notifications rather than the device's
own alarm.

## Install

1. Copy the `custom_components/meatmeet` folder into your Home Assistant
   `config/custom_components/` directory.
2. Restart Home Assistant.
3. The thermometer should be **auto-discovered** (Settings → Devices & Services →
   *Discovered*). If not, add it manually via **+ Add Integration → Meatmeet**.
   Make sure the phone app is **closed** — the station only allows one BLE
   connection at a time.

## Options

Settings → the Meatmeet device → **Configure** → *Poll interval* (1–60 s,
default 3). Increase it if you see connection drops at range.

## How it works

The station only reports when polled: HA keeps a BLE connection open, writes the
3-byte command `01 06 02` to the control characteristic
(`a6ed0404-…`) every poll interval, and decodes the 54-byte `"ME"` frame that
comes back as a notification on `0000f5a1-…`. Protocol reverse-engineered from
the [Meatmeet-S-Pro-ESPhome](https://github.com/makerwolf/Meatmeet-S-Pro-ESPhome)
package.
