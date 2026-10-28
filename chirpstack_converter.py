"""
Custom uplink converter for the ThingsBoard IoT Gateway MQTT connector.
Forwards the keys ChirpStack decoded ("object") as flat telemetry, plus RSSI/SNR.
"""

import json

from thingsboard_gateway.connectors.converter import Converter
from thingsboard_gateway.gateway.entities.converted_data import ConvertedData
from thingsboard_gateway.gateway.entities.telemetry_entry import TelemetryEntry
from thingsboard_gateway.gateway.entities.datapoint_key import DatapointKey

SKIP_KEYS = {"bytes", "fPort", "thresholds"}
PLAIN_PARENTS = {"sensorValues"}  # children become top-level keys: co2, temperature, humidity


def flatten(data, prefix=""):
    out = {}
    for key, value in data.items():
        if key in SKIP_KEYS:
            continue
        if isinstance(value, dict):
            child_prefix = "" if key in PLAIN_PARENTS else f"{prefix}{key}_"
            out.update(flatten(value, child_prefix))
        elif isinstance(value, (int, float, str, bool)):
            out[f"{prefix}{key}"] = value
    return out


class ChirpstackJsonConverter(Converter):
    def __init__(self, config, logger):
        self._config = config
        self._log = logger

    def convert(self, config, data):
        try:
            payload = data if isinstance(data, dict) else json.loads(data)

            device_info = payload.get("deviceInfo") or {}
            dev_eui = device_info.get("devEui")
            device_name = device_info.get("deviceName") or dev_eui or "unknown-device"
            device_type = device_info.get("deviceProfileName") or "default"

            converted = ConvertedData(device_name, device_type)

            telemetry_values = flatten(payload.get("object") or {})

            rx_info = payload.get("rxInfo") or []
            if rx_info:
                telemetry_values["rssi"] = rx_info[0].get("rssi")
                telemetry_values["snr"] = rx_info[0].get("snr")

            telemetry_values = {k: v for k, v in telemetry_values.items() if v is not None}

            if telemetry_values:
                keyed_values = {DatapointKey(k): v for k, v in telemetry_values.items()}
                converted.add_to_telemetry(TelemetryEntry(keyed_values))

            if dev_eui:
                converted.add_to_attributes(DatapointKey("devEui"), dev_eui)
            if device_info.get("applicationName"):
                converted.add_to_attributes(DatapointKey("application"), device_info["applicationName"])

            return converted
        except Exception:
            self._log.exception("ChirpstackJsonConverter failed")
            return None
