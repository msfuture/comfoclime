import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

API_PATH = (
    Path(__file__).parents[1] / "custom_components" / "comfoclime" / "comfoclime_api.py"
)
API_SPEC = importlib.util.spec_from_file_location("comfoclime_api", API_PATH)
API_MODULE = importlib.util.module_from_spec(API_SPEC)
REQUESTS_STUB = types.ModuleType("requests")
REQUESTS_STUB.put = Mock()
REQUESTS_STUB.get = Mock()
with patch.dict(sys.modules, {"requests": REQUESTS_STUB}):
    API_SPEC.loader.exec_module(API_MODULE)
ComfoClimeAPI = API_MODULE.ComfoClimeAPI


class VentilationTests(unittest.TestCase):
    def test_get_alarms_returns_errors_by_connected_device(self):
        api = ComfoClimeAPI(
            "http://comfoclime.local", entry=SimpleNamespace(options={})
        )
        api.uuid = "MBE4022d83940b9"
        response = Mock()
        response.json.return_value = {
            "devices": [
                {"uuid": "SIT17004997", "errors": [0, 4, 0]},
                {"uuid": "MBE4022d83940b9", "errors": [0, 0, 0]},
            ]
        }

        with patch.object(REQUESTS_STUB, "get", return_value=response) as get:
            alarms = api.get_alarms()

        get.assert_called_once_with(
            "http://comfoclime.local/system/MBE4022d83940b9/alarms", timeout=5
        )
        response.raise_for_status.assert_called_once_with()
        self.assertEqual(
            alarms,
            {"SIT17004997": [0, 4, 0], "MBE4022d83940b9": [0, 0, 0]},
        )

    def test_filter_days_remaining_decodes_unsigned_two_byte_telemetry(self):
        api = ComfoClimeAPI(
            "http://comfoclime.local", entry=SimpleNamespace(options={})
        )
        response = Mock()
        response.json.return_value = {"data": [164, 0]}

        with patch.object(REQUESTS_STUB, "get", return_value=response) as get:
            value = api.read_telemetry_for_device(
                "SIT17004997", 192, byte_count=2, signed=False
            )

        get.assert_called_once_with(
            "http://comfoclime.local/device/SIT17004997/telemetry/192", timeout=5
        )
        self.assertEqual(value, 164)

    def test_modes_send_expected_comfonet_timer_commands(self):
        expected = (
            ("away", 0x0B, 0x00),
            ("low", 0x01, 0x01),
            ("medium", 0x01, 0x02),
            ("high", 0x01, 0x03),
            ("boost", 0x06, 0x03),
        )

        for mode, timer, value in expected:
            with self.subTest(mode=mode):
                api = ComfoClimeAPI("http://comfoclime.local")
                response = Mock()
                with patch.object(REQUESTS_STUB, "put", return_value=response) as put:
                    api.set_ventilation_mode("SIT17004997", mode)

                others = [t for t in (0x0B, 0x01, 0x06) if t != timer]
                cancel_url = (
                    "http://comfoclime.local/device/SIT17004997/method/21/1/133"
                )
                self.assertEqual(
                    put.call_args_list,
                    [
                        *(
                            call(cancel_url, json={"data": [t]}, timeout=5)
                            for t in others
                        ),
                        call(
                            "http://comfoclime.local/device/SIT17004997/method/21/1/132",
                            json={"data": [timer, 0, 0, 0, 0, 0x10, 0x0E, 0, 0, value]},
                            timeout=5,
                        ),
                    ],
                )

    def test_auto_cancels_all_preset_timers(self):
        api = ComfoClimeAPI("http://comfoclime.local")
        response = Mock()

        with patch.object(REQUESTS_STUB, "put", return_value=response) as put:
            api.set_ventilation_mode("SIT17004997", "auto")

        cancel_url = "http://comfoclime.local/device/SIT17004997/method/21/1/133"
        self.assertEqual(
            put.call_args_list,
            [
                call(cancel_url, json={"data": [0x0B]}, timeout=5),
                call(cancel_url, json={"data": [0x01]}, timeout=5),
                call(cancel_url, json={"data": [0x06]}, timeout=5),
                call(
                    "http://comfoclime.local/device/SIT17004997/method/21/8/133",
                    json={"data": [1]},
                    timeout=5,
                ),
            ],
        )

    def test_set_ventilation_mode_uses_requested_duration(self):
        api = ComfoClimeAPI("http://comfoclime.local")
        response = Mock()

        with patch.object(REQUESTS_STUB, "put", return_value=response) as put:
            api.set_ventilation_mode("SIT17004997", "boost", duration_minutes=90)

        self.assertEqual(
            put.call_args.kwargs["json"]["data"],
            [6, 0, 0, 0, 0, 0x18, 0x15, 0, 0, 3],
        )
        self.assertEqual(put.call_count, 3)

    def test_set_ventilation_mode_rejects_invalid_duration(self):
        api = ComfoClimeAPI("http://comfoclime.local")

        for duration in (0, 1441, True, 1.5):
            with self.subTest(duration=duration):
                with self.assertRaisesRegex(ValueError, "1–1440 minutes"):
                    api.set_ventilation_mode(
                        "SIT17004997", "low", duration_minutes=duration
                    )

    def test_set_ventilation_mode_rejects_unknown_mode(self):
        api = ComfoClimeAPI("http://comfoclime.local")

        with self.assertRaisesRegex(ValueError, "'auto'.*'boost'"):
            api.set_ventilation_mode("SIT17004997", "unknown")


if __name__ == "__main__":
    unittest.main()
