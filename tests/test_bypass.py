import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

API_PATH = (
    Path(__file__).parents[1] / "custom_components" / "comfoclime" / "comfoclime_api.py"
)
API_SPEC = importlib.util.spec_from_file_location("comfoclime_api", API_PATH)
API_MODULE = importlib.util.module_from_spec(API_SPEC)
REQUESTS_STUB = types.ModuleType("requests")
REQUESTS_STUB.put = Mock()
with patch.dict(sys.modules, {"requests": REQUESTS_STUB}):
    API_SPEC.loader.exec_module(API_MODULE)
ComfoClimeAPI = API_MODULE.ComfoClimeAPI


class BypassTests(unittest.TestCase):
    def test_modes_send_expected_comfonet_methods(self):
        expected = (
            ("on", 0x84, [1, 0, 0, 0, 0, 0x10, 0x0E, 0, 0, 1]),
            ("off", 0x84, [1, 0, 0, 0, 0, 0x10, 0x0E, 0, 0, 2]),
            ("auto", 0x85, [1]),
        )

        for mode, method, data in expected:
            with self.subTest(mode=mode):
                api = ComfoClimeAPI("http://comfoclime.local")
                response = Mock()
                with patch.object(REQUESTS_STUB, "put", return_value=response) as put:
                    api.set_bypass_mode("SIT17004997", mode)

                response.raise_for_status.assert_called_once_with()
                put.assert_called_once_with(
                    f"http://comfoclime.local/device/SIT17004997/method/21/2/{method}",
                    json={"data": data},
                    timeout=5,
                )

    def test_set_bypass_mode_uses_requested_duration(self):
        api = ComfoClimeAPI("http://comfoclime.local")
        response = Mock()

        with patch.object(REQUESTS_STUB, "put", return_value=response) as put:
            api.set_bypass_mode("SIT17004997", "on", duration_minutes=90)

        self.assertEqual(
            put.call_args.kwargs["json"]["data"],
            [1, 0, 0, 0, 0, 0x18, 0x15, 0, 0, 1],
        )

    def test_set_bypass_mode_accepts_integral_selector_value(self):
        api = ComfoClimeAPI("http://comfoclime.local")
        response = Mock()

        with patch.object(REQUESTS_STUB, "put", return_value=response) as put:
            api.set_bypass_mode("SIT17004997", "on", duration_minutes=60.0)

        self.assertEqual(put.call_args.kwargs["json"]["data"][5:9], [0x10, 0x0E, 0, 0])

    def test_set_bypass_mode_rejects_invalid_duration(self):
        api = ComfoClimeAPI("http://comfoclime.local")

        for duration in (0, 1441, True, 1.5):
            with self.subTest(duration=duration):
                with self.assertRaisesRegex(ValueError, "1–1440 minutes"):
                    api.set_bypass_mode("SIT17004997", "on", duration_minutes=duration)

    def test_set_bypass_mode_rejects_unknown_mode(self):
        api = ComfoClimeAPI("http://comfoclime.local")

        with self.assertRaisesRegex(ValueError, "'auto', 'on', or 'off'"):
            api.set_bypass_mode("SIT17004997", "unknown")


if __name__ == "__main__":
    unittest.main()
