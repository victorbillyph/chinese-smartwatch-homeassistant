"""BLE protocol handler for Bluetrum AB5610 smartwatches."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from bleak import BleakClient, BleakScanner

from .const import (
    BATTERY_UUID, BT_CLASSIC_XOR, CMD_DEV_CTRL, CMD_DEV_SETTING,
    CMD_GET_FEATURE, CMD_MSG_NOTIFY, CMD_SPORT, CMD_SETTING, CMD_UNBIND,
    CMD_WATCH_FACE, CONNECT_TIMEOUT, CTRL_MUSIC_NEXT, CTRL_MUSIC_PAUSE,
    CTRL_MUSIC_PLAY, CTRL_MUSIC_PREV, CTRL_FIND_PHONE, CTRL_EXIT_FIND,
    FEATURE_UUID, HEADER_ACK, HEADER_CMD, HW_REV_UUID, MSG_TYPE_MAP,
    NOTIFY_CHAR, PLAT_REV_UUID, PROTO_VER, SERVICE_UUID, SET_ALARM,
    SET_FIND_BRACE, SET_HR_AUTO, SET_HR_ON, SET_MSG_PUSH, SET_MSG_NOTIFY_EXT,
    SET_NOTIFY_NEW, SET_PROFILE, SET_SPORT_TARGET, SET_TIME,
    FW_REV_UUID, WRITE_CHAR, CMD_BIND,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class WatchState:
    """Represents all known state from the watch."""
    firmware: str = ""
    hardware: str = ""
    platform: str = ""
    battery: int = 0
    connected: bool = False
    bound: bool = False
    # Health sensors
    steps: int = 0
    distance: int = 0
    calories: int = 0
    heart_rate: float | None = None
    blood_pressure_sys: int | None = None
    blood_pressure_dia: int | None = None
    spo2: float | None = None
    temperature: float | None = None
    # Sleep
    deep_sleep_min: int = 0
    light_sleep_min: int = 0
    wake_count: int = 0
    # Sport
    sport_mode: int = 0
    sport_duration: int = 0
    sport_calories: int = 0
    # Feature flags
    features: bytes = b""
    has_temperature: bool = False
    has_spo2: bool = False
    has_heart_rate: bool = False
    has_blood_pressure: bool = False
    has_sleep: bool = False
    has_watch_face: bool = False
    has_bt_pair: bool = False
    has_sos: bool = False
    # Watch face
    current_watch_face: int = 0
    watch_face_count: int = 0
    # BT Classic
    bt_classic_address: str = ""
    bt_classic_paired: bool = False
    bt_a2dp_connected: bool = False
    bt_hfp_connected: bool = False
    # Audio
    audio_volume: int = 0
    audio_muted: bool = False
    # Voice assistant
    voice_assistant_active: bool = False
    # Callbacks
    _listeners: list[Callable] = field(default_factory=list)

    def notify_listeners(self) -> None:
        for cb in self._listeners:
            try:
                cb(self)
            except Exception:
                pass


class LaxasFitBLE:
    """Manages BLE connection and protocol with the watch."""

    def __init__(self, address: str) -> None:
        self.address = address
        self._client: BleakClient | None = None
        self._state = WatchState()
        self._resp_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=50)
        self._connect_lock = asyncio.Lock()
        self._notify_data: bytes = b""
        self._notify_pos = 0
        self._pending_packets: bytearray = bytearray()

    @property
    def state(self) -> WatchState:
        return self._state

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def connect(self, max_retries: int = 6) -> bool:
        """Connect to the watch with retry + name fallback."""
        async with self._connect_lock:
            for attempt in range(max_retries):
                try:
                    dev = await BleakScanner.find_device_by_address(
                        self.address.lower(), timeout=CONNECT_TIMEOUT
                    )
                    if not dev:
                        dev = await BleakScanner.find_device_by_address(
                            self.address, timeout=CONNECT_TIMEOUT
                        )

                    # Fallback: scan by name if MAC not found
                    if not dev and self._state.connected is False:
                        _LOGGER.debug("MAC not found, scanning by name...")
                        devices = await BleakScanner.discover(timeout=5)
                        for d in devices:
                            if d.name and d.name.lower() in (
                                "watch", "laxasfit", "hryfine"
                            ):
                                _LOGGER.info(
                                    "Found watch by name: %s [%s]",
                                    d.name, d.address,
                                )
                                dev = d
                                # Update address for next reconnect
                                self.address = d.address
                                break

                    if not dev:
                        _LOGGER.warning("Watch not found, attempt %d", attempt + 1)
                        await asyncio.sleep(2)
                        continue

                    self._client = BleakClient(
                        dev,
                        pair=(attempt % 2 == 1),
                        timeout=CONNECT_TIMEOUT,
                    )
                    await self._client.connect()
                    await asyncio.sleep(0.5)

                    await self._client.start_notify(NOTIFY_CHAR, self._on_notify)
                    self._state.connected = True
                    _LOGGER.info("Connected to watch %s", self.address)
                    return True

                except Exception as err:
                    _LOGGER.warning("Connect attempt %d failed: %s", attempt + 1, err)
                    await asyncio.sleep(2)

            self._state.connected = False
            return False

    async def disconnect(self) -> None:
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(NOTIFY_CHAR)
            except Exception:
                pass
            await self._client.disconnect()
        self._client = None
        self._state.connected = False

    def _on_notify(self, sender: Any, data: bytes) -> None:
        """Handle BLE notification — reassemble packets."""
        if len(data) < 2:
            return

        if data[0] == HEADER_ACK:
            self._resp_queue.put_nowait(bytes(data))
            return

        if data[0] == HEADER_CMD:
            pkt_len = ((data[1] & 0xFF) << 8) | (data[2] & 0xFF)
            total = pkt_len + 4
            self._pending_packets = bytearray(data)
            if len(data) >= total:
                self._resp_queue.put_nowait(bytes(self._pending_packets[:total]))
                self._pending_packets = bytearray()
            return

        # Continuation fragment
        if self._pending_packets:
            self._pending_packets.extend(data)
            pkt_len = ((self._pending_packets[1] & 0xFF) << 8) | (
                self._pending_packets[2] & 0xFF
            )
            total = pkt_len + 4
            if len(self._pending_packets) >= total:
                self._resp_queue.put_nowait(
                    bytes(self._pending_packets[:total])
                )
                self._pending_packets = bytearray()

    @staticmethod
    def build_packet(cmd: int, key: int, data: bytes = b"") -> bytes:
        """Build a complete BLE command packet with checksum.

        Format: [0xDF][Len_H][Len_L][Checksum][CmdID][Ver=1][Key][DataLen_H][DataLen_L][Data...]
        """
        dlen = len(data)
        pkt = bytearray(9 + dlen)
        pkt[0] = HEADER_CMD
        pkt[1] = ((dlen + 5) >> 8) & 0xFF
        pkt[2] = (dlen + 5) & 0xFF
        pkt[3] = 0x00  # placeholder for checksum
        pkt[4] = cmd & 0xFF
        pkt[5] = PROTO_VER
        pkt[6] = key & 0xFF
        pkt[7] = (dlen >> 8) & 0xFF
        pkt[8] = dlen & 0xFF
        if dlen > 0:
            pkt[9: 9 + dlen] = data
        # Checksum: sum of all bytes, mod 256
        pkt[3] = sum(pkt) & 0xFF
        return bytes(pkt)

    async def send_command(
        self, cmd: int, key: int, data: bytes = b"", timeout: float = 5
    ) -> tuple[bool, bytes]:
        """Send a command and wait for ACK. Returns (success, payload)."""
        if not self.connected:
            return False, b""

        pkt = self.build_packet(cmd, key, data)

        # Drain old responses
        while not self._resp_queue.empty():
            try:
                self._resp_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        await self._client.write_gatt_char(WRITE_CHAR, pkt, response=False)

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                resp = await asyncio.wait_for(self._resp_queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

            if resp[0] == HEADER_ACK and len(resp) >= 9:
                ok = resp[8]
                return ok == 1, resp[9:] if len(resp) > 9 else b""

            if resp[0] == HEADER_CMD and len(resp) >= 9:
                return True, resp[9:]

        return False, b""

    async def fire_and_forget(self, cmd: int, key: int, data: bytes = b"") -> None:
        """Send without waiting for response."""
        if not self.connected:
            return
        pkt = self.build_packet(cmd, key, data)
        await self._client.write_gatt_char(WRITE_CHAR, pkt, response=False)

    # ── High-level API ──────────────────────────────────────────

    async def read_device_info(self) -> None:
        """Read firmware, hardware, platform, and feature flags."""
        for attr, uuid in [
            ("firmware", FW_REV_UUID),
            ("hardware", HW_REV_UUID),
            ("platform", PLAT_REV_UUID),
        ]:
            try:
                val = await self._client.read_gatt_char(uuid)
                setattr(self._state, attr, val.decode("utf-8", errors="replace"))
            except Exception:
                pass

        try:
            feat = await self._client.read_gatt_char(FEATURE_UUID)
            self._state.features = feat
            self._parse_features(feat)
        except Exception:
            pass

        # Derive BT Classic address from BLE address (last byte XOR 0x55)
        if self.address:
            parts = self.address.split(":")
            if len(parts) == 6:
                last_byte = int(parts[5], 16)
                classic_last = format(last_byte ^ BT_CLASSIC_XOR, "02X")
                self._state.bt_classic_address = ":".join(parts[:5]) + ":" + classic_last

    def _parse_features(self, feat: bytes) -> None:
        if len(feat) < 1:
            return
        f1 = feat[0] if len(feat) > 0 else 0
        self._state.has_heart_rate = not bool(f1 & 0x80)
        self._state.has_blood_pressure = not bool(f1 & 0x40)
        self._state.has_temperature = bool(f1 & 0x10)
        self._state.has_spo2 = bool(f1 & 0x01)
        if len(feat) > 1:
            f2 = feat[1]
            self._state.has_watch_face = bool(f2 & 0x80)
        if len(feat) > 14:
            f14 = feat[14]
            self._state.has_sos = bool(f14 & 0x10)
            self._state.has_bt_pair = bool(feat[15] & 0x40) if len(feat) > 15 else False

    async def read_battery(self) -> int:
        try:
            val = await self._client.read_gatt_char(BATTERY_UUID)
            self._state.battery = val[0]
            return self._state.battery
        except Exception:
            return 0

    async def bind(self) -> bool:
        """Bind the device."""
        ok, _ = await self.send_command(CMD_BIND, 0)
        self._state.bound = ok
        return ok

    async def unbind(self) -> bool:
        ok, _ = await self.send_command(CMD_UNBIND, 0)
        self._state.bound = not ok
        return ok

    async def sync_time(self) -> bool:
        """Sync current time to the watch."""
        import datetime
        now = datetime.datetime.now()
        y = now.year - 2000
        data = bytearray(6)
        data[0] = y
        data[1] = now.month
        data[2] = now.day
        data[3] = now.hour
        data[4] = now.minute
        data[5] = now.second
        # Pack into 4 bytes: MMYYYY as BCD-ish, then HH, MM, SS
        packed = bytearray(4)
        packed[0] = (now.month << 4) | (y & 0x0F)
        packed[1] = (now.day << 4) | ((y >> 4) & 0x0F)
        packed[2] = (now.hour << 4) | (now.minute >> 4)
        packed[3] = ((now.minute & 0x0F) << 4) | (now.second >> 4)
        ok, _ = await self.send_command(CMD_SETTING, SET_TIME, bytes(packed))
        return ok

    async def request_ota_info(self) -> bytes:
        """Request OTA info, returns the unique_code payload."""
        resp = await self._client.write_gatt_char(
            WRITE_CHAR, self.build_packet(0x13, 1), response=False
        )
        deadline = asyncio.get_event_loop().time() + 8
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(self._resp_queue.get(), timeout=1)
                if r[0] == HEADER_CMD and len(r) >= 14 and r[4] == 0x13:
                    return r[9:]
            except asyncio.TimeoutError:
                continue
        return b""

    async def find_watch(self) -> bool:
        """Make the watch vibrate."""
        ok, _ = await self.send_command(CMD_SETTING, SET_FIND_BRACE, b"\x01")
        return ok

    async def send_notification(self, msg_type: str, title: str, content: str) -> bool:
        """Push a notification to the watch."""
        type_id = MSG_TYPE_MAP.get(msg_type.lower(), MSG_TYPE_MAP["other"])
        text = f"{title}:{content}"
        tb = text.encode("utf-8")[:196]
        data = bytearray(3 + len(tb))
        data[0] = type_id
        data[1] = 0
        data[2] = 0
        data[3:] = tb
        ok, _ = await self.send_command(CMD_SETTING, SET_MSG_PUSH, bytes(data))
        return ok

    async def send_incoming_call(self, caller_name: str) -> bool:
        """Simulate incoming call notification."""
        name_bytes = caller_name.encode("utf-8")[:60]
        data = bytearray(1 + len(name_bytes))
        data[0] = 1  # incoming
        data[1:] = name_bytes
        ok, _ = await self.send_command(CMD_SETTING, 17, bytes(data))
        return ok

    async def send_weather(
        self, city: str, code: int, temp_min: int, temp_max: int, current: int
    ) -> bool:
        """Send weather to watch display."""
        city_bytes = city.encode("utf-8")[:20]
        data = bytearray(5 + len(city_bytes))
        data[0] = code & 0xFF
        data[1] = temp_min & 0xFF
        data[2] = temp_max & 0xFF
        data[3] = current & 0xFF
        data[4] = len(city_bytes)
        data[5:] = city_bytes
        ok, _ = await self.send_command(CMD_SETTING, SET_TIME + 18, bytes(data))
        return ok

    async def set_step_target(self, target: int) -> bool:
        data = target.to_bytes(4, "big")
        ok, _ = await self.send_command(CMD_SETTING, SET_SPORT_TARGET, data)
        return ok

    async def set_profile(
        self, sex: int, age: int, height: int, weight: int
    ) -> bool:
        """Set user profile. sex: 0=male 1=female."""
        val = ((sex & 1) << 15) | ((age & 0x7F) << 8) | ((height & 0x1FF) << 0)
        # Actually: byte0=sex(1bit)+age(7bit), byte1=height(9bit), byte2=weight(8bit)
        data = bytearray(3)
        data[0] = ((sex & 1) << 7) | (age & 0x7F)
        data[1] = (height >> 1) & 0xFF
        data[2] = ((height & 1) << 7) | (weight & 0x7F)
        ok, _ = await self.send_command(CMD_SETTING, SET_PROFILE, data)
        return ok

    async def set_sedentary_reminder(
        self, enabled: bool, threshold: int = 50,
        interval_min: int = 60, start_h: int = 9, end_h: int = 18,
        repeat: int = 31,
    ) -> bool:
        data = bytearray(6)
        data[0] = 0  # lunch_break
        data[1] = 1 if enabled else 0
        data[2] = (threshold >> 8) & 0xFF
        data[3] = threshold & 0xFF
        data[4] = max(0, (interval_min - 30) // 15)
        data[5] = (start_h << 4) | (end_h & 0x0F)
        data.append(repeat)
        ok, _ = await self.send_command(CMD_DEV_SETTING, SET_TIME + 4, data)
        return ok

    async def set_drink_reminder(
        self, enabled: bool, interval_min: int = 60,
        start_h: int = 9, end_h: int = 18, repeat: int = 31,
    ) -> bool:
        data = bytearray(6)
        data[0] = 0
        data[1] = 1 if enabled else 0
        data[2] = 0
        data[3] = max(0, (interval_min - 30) // 15)
        data[4] = (start_h << 4) | (end_h & 0x0F)
        data[5] = repeat
        ok, _ = await self.send_command(CMD_DEV_SETTING, SET_TIME + 32, data)
        return ok

    async def set_hr_auto_measure(
        self, enabled: bool, cycle_min: int = 30,
        start_h: int = 0, end_h: int = 23,
    ) -> bool:
        data = bytearray(5)
        data[0] = 1 if enabled else 0
        data[1] = 0  # sleep_mode
        data[2] = max(1, cycle_min // 5)
        data[3] = start_h
        data[4] = end_h
        ok, _ = await self.send_command(CMD_DEV_SETTING, SET_TIME + 21, data)
        return ok

    async def music_control(self, action: str) -> bool:
        """Control phone media: play, pause, next, prev."""
        action_map = {
            "play": 10, "pause": 11, "next": 12, "prev": 13,
        }
        code = action_map.get(action.lower())
        if code is None:
            return False
        ok, _ = await self.send_command(CMD_DEV_CTRL, code)
        return ok

    async def trigger_bt_classic_pair(self) -> bool:
        """Ask the watch to initiate BT Classic pairing (HFP/A2DP)."""
        ok, _ = await self.send_command(CMD_DEV_CTRL, 19)
        return ok

    async def request_bt_status(self) -> bytes:
        """Request BT Classic connection status from watch."""
        ok, payload = await self.send_command(CMD_DEV_CTRL, 18)
        return payload

    async def set_volume(self, level: int) -> bool:
        """Set audio volume on the watch speaker (0-100)."""
        data = bytearray(1)
        data[0] = max(0, min(100, level))
        ok, _ = await self.send_command(CMD_DEV_SETTING, 40, data)
        return ok

    async def request_settings(self) -> dict[str, Any]:
        """Request current settings from the watch."""
        ok, payload = await self.send_command(CMD_DEV_SETTING, 0)
        return {"ok": ok, "payload": payload.hex() if payload else ""}

    async def request_sport_data(self, sub_key: int = 1) -> bytes:
        """Request sport/health data. sub_key: 1=all, 2=steps, etc."""
        ok, payload = await self.send_command(CMD_SPORT, sub_key)
        return payload

    async def request_watch_faces(self) -> bytes:
        """Query available watch faces."""
        ok, payload = await self.send_command(CMD_WATCH_FACE, 1)
        return payload

    async def set_watch_face(self, face_code: int) -> bool:
        data = face_code.to_bytes(2, "big")
        ok, _ = await self.send_command(CMD_WATCH_FACE, 3, data)
        return ok

    async def set_language(self, lang_code: int) -> bool:
        data = bytearray(1)
        data[0] = lang_code
        ok, _ = await self.send_command(CMD_DEV_SETTING, SET_TIME + 20, data)
        return ok

    async def set_hour_format(self, is_24h: bool) -> bool:
        data = bytearray(1)
        data[0] = 0 if is_24h else 1
        ok, _ = await self.send_command(CMD_DEV_SETTING, SET_TIME + 25, data)
        return ok

    async def set_unit_metric(self, metric: bool) -> bool:
        data = bytearray(1)
        data[0] = 0 if metric else 1
        ok, _ = await self.send_command(CMD_DEV_SETTING, SET_TIME + 26, data)
        return ok

    async def process_notification_packet(self, payload: bytes) -> None:
        """Process a data notification from the watch (cmd=0x05 sport data)."""
        if len(payload) < 2:
            return

        sub_key = payload[0] if len(payload) > 0 else 0

        if sub_key == 2:  # Step data
            if len(payload) >= 8:
                self._state.steps = int.from_bytes(payload[1:5], "big")
                self._state.distance = int.from_bytes(payload[5:7], "big")
                self._state.calories = int.from_bytes(payload[7:9], "big") if len(payload) >= 9 else 0

        elif sub_key == 4:  # Heart rate
            if len(payload) >= 3 and payload[1] > 0:
                self._state.heart_rate = payload[2]

        elif sub_key == 5:  # Blood pressure
            if len(payload) >= 4:
                self._state.blood_pressure_sys = payload[2]
                self._state.blood_pressure_dia = payload[3]

        elif sub_key == 9:  # Sleep
            if len(payload) >= 6:
                self._state.deep_sleep_min = payload[1]
                self._state.light_sleep_min = payload[2]
                self._state.wake_count = payload[3]

        elif sub_key == 13:  # Temperature
            if len(payload) >= 3:
                raw = int.from_bytes(payload[1:3], "big")
                self._state.temperature = raw / 10.0

        elif sub_key == 14:  # SpO2
            if len(payload) >= 2:
                self._state.spo2 = payload[1]

        elif sub_key == 15:  # Sport mode
            if len(payload) >= 8:
                self._state.sport_mode = payload[1]
                self._state.sport_duration = int.from_bytes(payload[2:6], "big")
                self._state.sport_calories = int.from_bytes(payload[6:8], "big")

        self._state.notify_listeners()
