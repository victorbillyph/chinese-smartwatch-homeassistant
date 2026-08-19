# BLE Protocol Reference — Bluetrum AB5610 Smartwatches

Complete reverse-engineered protocol documentation from the LaxasFit APK (v1.5.7).

## BLE Services & Characteristics

### Primary Data Service (Nordic UART)
| UUID | Role |
|------|------|
| `6E400001-B5A3-F393-E0A9-E50E24DCCA9F` | Service |
| `6E400002-B5A3-F393-E0A9-E50E24DCCA9F` | Write (App → Watch) |
| `6E400003-B5A3-F393-E0A9-E50E24DCCA9F` | Notify (Watch → App) |

### Device Information
| UUID | Content |
|------|---------|
| `00002A26` | Firmware Revision |
| `00002A27` | Hardware Revision |
| `00002A25` | Platform Revision |
| `00002A28` | Feature Flags (27+ bytes) |

### Battery
| UUID | Content |
|------|---------|
| `00002A19` | Battery Level (0-100) |

### OTA (Bluetrum CYS5610)
| UUID | Role |
|------|------|
| `000018A8` | OTA Service |
| `00002AA8` | OTA Notify |
| `00002AA9` | OTA Write |

## Packet Format

### Command Packet (App → Watch)

```
Byte 0:    0xDF (header)
Byte 1-2:  Length (big-endian) = data_len + 5
Byte 3:    Checksum (sum of all bytes mod 256)
Byte 4:    Command ID
Byte 5:    Protocol Version (always 0x01)
Byte 6:    Sub-key
Byte 7-8:  Data Length (big-endian)
Byte 9+:   Data payload
```

### ACK Packet (Watch → App)

```
Byte 0:    0xFD (header)
Byte 1-2:  Length
Byte 3:    Checksum
Byte 4:    Command ID
Byte 5:    Version
Byte 6:    Key
Byte 7:    Status (0=received, 1=executed)
```

### Checksum Algorithm

```python
def checksum(packet):
    # Sum ALL bytes excluding byte[3], then insert at byte[3]
    pkt = bytearray(packet)
    pkt[3] = 0  # zero out
    return sum(pkt) & 0xFF
```

**CRITICAL**: The checksum is an EXTRA byte inserted at position 3, not a replacement. The original bytes 3+ shift right by 1.

## Command IDs

| ID | Name | Description |
|----|------|-------------|
| `0x01` | OTA | Legacy firmware update |
| `0x02` | Setting | All configurable settings |
| `0x03` | Bind | Bind device to app |
| `0x04` | Unbind | Unbind device |
| `0x05` | Sport Data | Health/sport data sync |
| `0x06` | Reset | Reset device |
| `0x08` | Alarm | Alarm clock management |
| `0x09` | Dev Setting | Device settings query |
| `0x0C` | Dev Control | Device control (find, music, BT) |
| `0x0D` | Factory Reset | Restore factory settings |
| `0x0F` | Watch Face | Watch face management |
| `0x11` | Drink | Drink water reminder |
| `0x12` | Msg Notify | Notification settings |
| `0x13` | OTA New | New OTA protocol |
| `0x14` | Sedentary | Sedentary reminder |
| `0x19` | Get Feature | Read device feature flags |
| `0x1A` | Get Func | Read device functions |

## Setting Sub-keys (cmd=0x02)

| Key | Name | Data Format |
|-----|------|-------------|
| 1 | Time Sync | Packed BCD: `[month<<4\|year_lo][day<<4\|year_hi][hour<<4\|min_hi][min_lo<<4\|sec]` |
| 2 | Alarm | Array of alarms: `[year,month,day,hour,min,id,repeat_bitmask]` |
| 3 | Step Target | 4-byte big-endian step count |
| 4 | Profile | `[sex<<7\|age][height_hi][height_lo<<7\|weight]` |
| 5 | Sedentary | `[lunch,switch,thresh_h,thresh_l,interval,start_end,repeat]` |
| 7 | Notify (old) | Byte array: tel,sms,wechat,qq,facebook,twitter,skype,line,whatsapp,instagram,viber |
| 11 | Find Bracelet | `[0x01]` to vibrate |
| 15 | Notify (new) | 20-byte array with show+vibrate bits per app |
| 17 | Incoming Call | `[call_action][...caller_name_utf8]` |
| 18 | Message Push | `[type_id,0,0,...utf8_title:content]` (max 196 bytes) |
| 19 | Weather Today | `[code,min_temp,max_temp,cur_temp,name_len,...city]` |
| 21 | Language | `[lang_code]` (0=English, 6=Portuguese) |
| 22 | HR Auto | `[switch,sleep_mode,cycle,start_h,end_h]` |
| 26 | Hour Format | `[0=24h, 1=12h]` |
| 27 | Unit System | `[0=Metric, 1=Imperial]` |
| 33 | Drink Remind | `[lunch,switch,interval,start_end,repeat]` |
| 35 | 7-Day Weather | Array of 7 forecasts |

## Device Control (cmd=0x0C)

| Code | Action |
|------|--------|
| 1 | Find Phone (ring+vibrate) |
| 3 | Enter Remote Camera |
| 4 | Exit Remote Camera |
| 5 | Close HR Test |
| 6 | Close BP Test |
| 8 | Bind Accept |
| 9 | Bind Reject |
| 10 | Music Play |
| 11 | Music Pause |
| 12 | Next Track |
| 13 | Previous Track |
| 15 | Exit Find Phone |
| 18 | BT Status Report |
| 19 | BT Classic Bond (createBond) |

## Notification Types (Message Push)

| ID | App |
|----|-----|
| 1 | SMS |
| 2 | QQ |
| 3 | WeChat |
| 4 | Facebook |
| 5 | Twitter |
| 6 | Skype |
| 7 | LINE |
| 8 | WhatsApp |
| 9 | KakaoTalk |
| 10 | Instagram |
| 11 | Viber |
| 12 | Zalo |
| 13 | Other/Generic |
| 14 | DingDing |
| 17 | MS Teams |
| 18 | Snapchat |
| 19 | Messenger |
| 20 | LinkedIn |
| 21 | Telegram |
| 22 | VK |
| 23 | Outlook |

## Sport Data (cmd=0x05)

| Sub-key | Data Type | Format |
|---------|-----------|--------|
| 2 | Step Data | `[steps_32bit, dist_16bit, cal_16bit, ...]` |
| 4 | Heart Rate | `[0, hr_value, ...]` |
| 5 | Blood Pressure | `[0, sys, dia, ...]` |
| 9 | Sleep | `[deep_min, light_min, wake_count, ...]` |
| 13 | Temperature | `[temp_16bit_be]` (÷10 for °C) |
| 14 | SpO2 | `[0, spo2_value]` |
| 15 | Sport Mode | `[mode, dur_32bit, cal_16bit, ...]` |

## Sport Modes

| ID | Type |
|----|------|
| 0 | Running |
| 1 | Rope Skipping |
| 2 | Sit-ups |
| 3 | Cycling |

## Watch Face Commands (cmd=0x0F)

| Sub-key | Action |
|---------|--------|
| 1 | Query available faces |
| 2 | Face list response |
| 3 | Set active face |
| 4 | Query custom face settings |
| 5 | Set custom face |

## BT Classic Address Derivation

The watch has two Bluetooth addresses:
- **BLE address**: Shown during scan (e.g., `41:42:2D:B7:8D:C6`)
- **BT Classic address**: Last byte XOR'd with `0x55` (e.g., `41:42:2D:B7:8D:93`)

```
BLE:   41:42:2D:B7:8D:C6
XOR:   C6 ^ 55 = 93
Classic: 41:42:2D:B7:8D:93
```

## Feature Flags (from 00002A28)

27+ bytes of feature flags read on connection:

| Byte | Bit | Feature |
|------|-----|---------|
| 0 | 7 | BLE 3.0 mode |
| 0 | 6 | Contact sync support |
| 0 | 4 | Temperature sensor |
| 0 | 3 | 12/24h toggle |
| 0 | 2 | Metric/Imperial toggle |
| 0 | 1 | Language selection |
| 0 | 0 | Blood Oxygen sensor |
| 1 | 7 | Watch face set |
| 1 | 6 | Custom watch faces |
| 1 | 5 | Watch face push |
| 14 | 5 | Incoming call push |
| 14 | 4 | SOS support |
| 15 | 6 | BT Classic pairing |
| 15 | 2 | Drink water reminder |
| 19 | 4 | MAC XOR security |

## OTA Firmware Update

### Server
```
GET https://ota.lianhezhuli.com/api/hry/get_update
```

### Parameters
```
appid=oaa648257e8
bundle_id=5
lang=en
nonce=<random>
unique_code=<from_watch>
timestamp=<unix_epoch>
sign=<md5_sorted_params>
```

### Sign Algorithm
1. Sort all params alphabetically by key
2. Build: `key1=val1&key2=val2&...&key=ead8ff5fe2f9385b55e6e509cf311a35`
3. MD5 hash (uppercase hex)

### Watch unique_code
Sent in response to cmd=0x13 key=1. The full payload bytes 9-end, hex-encoded uppercase.

## Supported Languages

| Code | Language |
|------|----------|
| 0 | English |
| 1 | Chinese (Simplified) |
| 2 | Chinese (Traditional) |
| 3 | French |
| 4 | Spanish |
| 5 | Polish |
| 6 | Portuguese |
| 7 | Italian |
| 8 | German |
| 9 | Dutch |
| 10 | Turkish |
| 11 | Russian |
| 24 | Korean |
| 25 | Japanese |
