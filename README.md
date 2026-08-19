# LaxasFit BLE Smart Watch — Home Assistant Integration

![HA](https://img.shields.io/badge/Home%20Assistant-2024.1+-blue)
![HACS](https://img.shields.io/badge/HACS-Custom-orange)
![Protocol](https://img.shields.io/badge/Protocol-BLE%20%2B%20BT%20Classic-green)
![Chip](https://img.shields.io/badge/Chip-Bluetrum%20AB5610-red)

Full Home Assistant integration for cheap Chinese smartwatches that use the **LaxasFit** companion app. Reverse-engineered from the APK — no cloud dependency.

## Features

### Sensors (auto-polling every 60s)
| Sensor | Unit | Description |
|--------|------|-------------|
| Steps | steps | Daily step count |
| Distance | meters | Distance walked |
| Calories | kcal | Calories burned |
| Heart Rate | bpm | Real-time HR |
| Blood Pressure (Sys) | mmHg | Systolic |
| Blood Pressure (Dia) | mmHg | Diastolic |
| Blood Oxygen (SpO2) | % | Oxygen saturation |
| Body Temperature | °C | Skin temperature |
| Battery | % | Watch battery level |
| Deep Sleep | min | Deep sleep minutes |
| Light Sleep | min | Light sleep minutes |
| Wake Count | times | Times woken during sleep |
| Sport Mode | — | Current exercise type |
| Sport Duration | s | Exercise session length |

### Buttons
| Button | Action |
|--------|--------|
| Find Watch | Makes the watch vibrate |
| Sync Time | Syncs HA time to the watch |
| Sync Data | Requests all sensor data from watch |
| Play / Pause / Next / Prev | Controls phone media via watch |
| Voice Assistant Trigger | Triggers HA conversation agent via watch mic (BT HFP) |
| Announce TTS | Speaks HA TTS message through watch speaker (BT A2DP) |

### Media Player (A2DP + BLE)
- Full media player with play/pause/next/prev
- Volume control via PulseAudio (Linux)
- Mute support
- Routes audio through the watch's Bluetooth speaker

### Other Entities
| Type | Entity | Description |
|------|--------|-------------|
| Binary Sensor | Connected | BLE connection status |
| Switch | Sedentary Reminder | Enable/disable |
| Switch | Drink Reminder | Enable/disable |
| Select | Language | Set watch language (36 languages) |
| Number | Step Target | Set daily step goal (1000-50000) |
| Notify | Watch Notifications | Push messages to watch display |

## Supported Watches

Any watch that uses the **LaxasFit** (or similar) companion app with BLE protocol based on **Bluetrum AB5610** chip. Common brands:

- LaxasFit watches
- Generic Chinese smartwatches sold on AliExpress, Banggood, etc.
- Look for watches that pair with "LaxasFit" or "Hryfine" app

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → **Explore & Download Repositories**
3. Search for **LaxasFit BLE Smart Watch**
4. Click **Download**
5. Restart Home Assistant

### Manual Installation

```bash
# Clone the repo
git clone https://github.com/victorbillyph/chinese-smartwatch-homeassistant.git

# Copy to your HA config
cp -r chinese-smartwatch-homeassistant/custom_components/laxasfit \
      /config/custom_components/
```

Then restart Home Assistant.

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **LaxasFit BLE Smart Watch**
3. Select your watch from the BLE scan (or enter MAC address manually)
4. The integration will auto-connect, bind, and sync time

### BT Classic Setup (for Audio)

The watch acts as a Bluetooth speaker (A2DP) + microphone (HFP). To enable audio:

1. The integration auto-detects the BT Classic address (BLE MAC with last byte XOR'd with `0x55`)
2. Pair the watch via BT Classic in your OS Bluetooth settings
3. On Linux, ensure PulseAudio sees the watch as a sink
4. The `Watch Speaker` media player entity will then control audio

## BLE Protocol Reference

See [docs/PROTOCOL.md](docs/PROTOCOL.md) for the complete reverse-engineered protocol documentation.

### Quick Reference

| Command ID | Name | Description |
|------------|------|-------------|
| `0x02` | Setting | Time sync, alarms, notifications, weather |
| `0x03` | Bind | Bind device |
| `0x05` | Sport Data | Health data (steps, HR, BP, SpO2, temp, sleep) |
| `0x08` | Alarm | Set/query alarm clocks |
| `0x0C` | Device Control | Find phone, music control, BT pairing |
| `0x0F` | Watch Face | Query/set/custom watch faces |
| `0x13` | OTA Info | Firmware version and update check |

### Packet Format

```
Header:  0xDF
Length:  2 bytes (big-endian) = data_len + 5
Checksum: sum of all bytes (mod 256), inserted at byte[3]
Cmd ID:  1 byte
Version: 1 byte (always 0x01)
Key:     1 byte (sub-command)
DataLen: 2 bytes (big-endian)
Data:    variable
```

## Development

### Project Structure

```
custom_components/laxasfit/
├── __init__.py          # Integration setup
├── manifest.json        # HA metadata
├── config_flow.py       # Config flow (BLE scan)
├── ble_protocol.py      # Full BLE protocol handler
├── coordinator.py       # DataUpdateCoordinator
├── const.py             # Protocol constants
├── sensor.py            # 14 sensor entities
├── binary_sensor.py     # Connection status
├── button.py            # Actions + voice trigger + TTS
├── switch.py            # Setting toggles
├── select.py            # Language selector
├── number.py            # Step target
├── media_player.py      # A2DP + BLE media control
├── notify.py            # Push notifications to watch
├── strings.json         # Translation strings
└── translations/
    ├── en.json
    └── pt-BR.json
```

### Reverse Engineering Notes

This integration was built by decompiling the LaxasFit APK (v1.5.7) using **jadx**. Key findings:

- **Chip**: Bluetrum AB5610 (RTOS-based SoC for wearables)
- **BLE Service**: Nordic UART Service (NUS) — `6E400001-...`
- **Checksum**: Sum of all packet bytes mod 256, inserted as extra byte at position 3
- **BT Classic**: Same MAC as BLE but last byte XOR'd with `0x55`
- **OTA Server**: `https://ota.lianhezhuli.com/api/hry/get_update` (MD5 signed)
- **API Base**: `https://lafei.howruf.com/api/`

## License

MIT
