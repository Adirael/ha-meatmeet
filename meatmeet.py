#!/usr/bin/env python3
"""
Read live temperatures from a Meatmeet S Pro 6-channel Bluetooth thermometer
directly from a PC with a Bluetooth (BLE) adapter — no ESPHome / Home Assistant.

Reverse-engineered protocol (from the Meatmeet-S-Pro-ESPhome package):

  * The station advertises two GATT services:
      - Control service   A6ED0401-D344-460A-8075-B9E8EC90D71B
        write char        A6ED0404-D344-460A-8075-B9E8EC90D71B
      - Notify service    0000F5A0-0000-1000-8000-00805F9B34FB
        notify char       0000F5A1-0000-1000-8000-00805F9B34FB
  * To get a reading you WRITE the 3-byte poll command [0x01, 0x06, 0x02] to the
    write char.  The station answers with a 54-byte notification on the notify
    char.  Repeat the write every few seconds to keep readings flowing.
  * The 54-byte packet starts with the header "ME" (0x4D 0x45) and encodes:
      byte  8      station battery      uint8   (%)
      byte 11-12   zone 1 temperature   uint16 LE, 0.01 °C
      byte 13      ambient temperature  uint8   (°C)
      byte 15      probe battery        uint8   (%)
      byte 16-17   zone 2 temperature   uint16 LE, 0.01 °C
      byte 18-19   zone 3 temperature   uint16 LE, 0.01 °C
      byte 20-21   zone 4 temperature   uint16 LE, 0.01 °C
      byte 22-23   zone 5 temperature   uint16 LE, 0.01 °C
    A raw zone value >= 0xA000 means "probe not connected" and is ignored.

Usage:
    python meatmeet.py --scan                 # find your device's MAC address
    python meatmeet.py --address AA:BB:...     # connect and stream readings
    python meatmeet.py --address AA:BB:... --interval 3 --json
"""

import argparse
import asyncio
import contextlib
import json
import struct
import sys
from datetime import datetime

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

# --- BLE identifiers ---------------------------------------------------------
CONTROL_SERVICE_UUID = "a6ed0401-d344-460a-8075-b9e8ec90d71b"
WRITE_CHAR_UUID = "a6ed0404-d344-460a-8075-b9e8ec90d71b"
NOTIFY_CHAR_UUID = "0000f5a1-0000-1000-8000-00805f9b34fb"
POLL_COMMAND = bytes([0x01, 0x06, 0x02])

PACKET_LEN = 54
HEADER = b"ME"  # 0x4D 0x45
TEMP_INVALID = 0xA000  # raw zone value at/above this = probe not connected


def parse_packet(data: bytes) -> dict | None:
    """Parse a 54-byte Meatmeet notification into a dict of readings.

    Returns None if the buffer is not a valid station packet.
    """
    if len(data) < PACKET_LEN or data[0:2] != HEADER:
        return None

    def zone(offset: int) -> float | None:
        raw = struct.unpack_from("<H", data, offset)[0]
        return None if raw >= TEMP_INVALID else raw / 100.0

    ambient_raw = data[13]
    return {
        "station_battery": data[8],
        "probe_battery": data[15],
        "zone1": zone(11),
        "zone2": zone(16),
        "zone3": zone(18),
        "zone4": zone(20),
        "zone5": zone(22),
        "ambient": float(ambient_raw) if 0 < ambient_raw < 250 else None,
    }


def format_reading(r: dict) -> str:
    ts = datetime.now().strftime("%H:%M:%S")
    zones = " ".join(
        f"Z{i}={r[f'zone{i}']:.2f}°C" if r[f"zone{i}"] is not None else f"Z{i}=--"
        for i in range(1, 6)
    )
    amb = f"{r['ambient']:.0f}°C" if r["ambient"] is not None else "--"
    return (
        f"[{ts}] {zones}  Amb={amb}  "
        f"Batt(station)={r['station_battery']}%  Batt(probe)={r['probe_battery']}%"
    )


async def cmd_scan(timeout: float) -> int:
    print(f"Scanning for BLE devices for {timeout:.0f}s ...", file=sys.stderr)
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    if not devices:
        print("No BLE devices found.", file=sys.stderr)
        return 1

    print(f"\nFound {len(devices)} device(s):\n")
    # Devices whose name looks like a Meatmeet float to the top.
    def sort_key(item):
        _, (dev, adv) = item
        name = (adv.local_name or dev.name or "").lower()
        return (0 if "meat" in name else 1, -adv.rssi)

    for address, (dev, adv) in sorted(devices.items(), key=sort_key):
        name = adv.local_name or dev.name or "(unknown)"
        services = adv.service_uuids or []
        is_meat = "meat" in name.lower() or CONTROL_SERVICE_UUID in [
            s.lower() for s in services
        ]
        marker = "  <-- likely Meatmeet" if is_meat else ""
        print(f"  {address}  RSSI={adv.rssi:>4} dBm  {name}{marker}")
    print(
        "\nUse the MAC address (left column) of your thermometer:\n"
        "    python meatmeet.py --address <MAC>",
        file=sys.stderr,
    )
    return 0


async def cmd_stream(address: str, interval: float, as_json: bool) -> int:
    loop = asyncio.get_running_loop()

    def on_notify(_char, data: bytearray):
        reading = parse_packet(bytes(data))
        if reading is None:
            return
        if as_json:
            reading["timestamp"] = datetime.now().isoformat()
            print(json.dumps(reading), flush=True)
        else:
            print(format_reading(reading), flush=True)

    print(f"Connecting to {address} ...", file=sys.stderr)
    async with BleakClient(address) as client:
        print("Connected. Subscribing to notifications ...", file=sys.stderr)
        await client.start_notify(NOTIFY_CHAR_UUID, on_notify)

        async def poller():
            while True:
                try:
                    await client.write_gatt_char(
                        WRITE_CHAR_UUID, POLL_COMMAND, response=False
                    )
                except BleakError as exc:
                    print(f"poll write failed: {exc}", file=sys.stderr)
                    return
                await asyncio.sleep(interval)

        task = loop.create_task(poller())
        print(
            f"Streaming (polling every {interval:.0f}s). Press Ctrl-C to stop.\n",
            file=sys.stderr,
        )
        try:
            # Run until disconnect or Ctrl-C.
            while client.is_connected:
                await asyncio.sleep(1)
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            with contextlib.suppress(BleakError):
                await client.stop_notify(NOTIFY_CHAR_UUID)

    print("Disconnected.", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="Read a Meatmeet S Pro thermometer over BLE.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--scan", action="store_true", help="scan for BLE devices and exit")
    p.add_argument("--address", "-a", help="MAC address of the thermometer")
    p.add_argument(
        "--interval",
        "-i",
        type=float,
        default=3.0,
        help="seconds between poll requests (default: 3)",
    )
    p.add_argument(
        "--timeout", type=float, default=8.0, help="scan duration in seconds (default: 8)"
    )
    p.add_argument("--json", action="store_true", help="emit readings as JSON lines")
    args = p.parse_args()

    try:
        if args.scan:
            return asyncio.run(cmd_scan(args.timeout))
        if not args.address:
            p.error("provide --address <MAC>, or use --scan to find it")
        return asyncio.run(cmd_stream(args.address, args.interval, args.json))
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        return 0
    except BleakError as exc:
        print(f"BLE error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
