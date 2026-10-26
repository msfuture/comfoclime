import importlib.util
import unittest
from pathlib import Path

SCENARIOS_PATH = (
    Path(__file__).parents[1] / "custom_components" / "comfoclime" / "scenarios.py"
)
SCENARIOS_SPEC = importlib.util.spec_from_file_location(
    "comfoclime_scenarios", SCENARIOS_PATH
)
SCENARIOS_MODULE = importlib.util.module_from_spec(SCENARIOS_SPEC)
SCENARIOS_SPEC.loader.exec_module(SCENARIOS_MODULE)


class ScenarioTests(unittest.TestCase):
    def test_scenario_confirmation_helper_exists(self):
        self.assertTrue(
            SCENARIOS_MODULE.scenario_update_confirmed(
                4, {"scenario": 4, "scenarioTimeLeft": 10}
            ),
        )

    def test_scenario_confirmation_rejects_ignored_or_expired_update(self):
        self.assertFalse(
            SCENARIOS_MODULE.scenario_update_confirmed(
                7, {"scenario": 5, "scenarioTimeLeft": 300}
            )
        )
        self.assertFalse(
            SCENARIOS_MODULE.scenario_update_confirmed(
                7, {"scenario": 7, "scenarioTimeLeft": 0}
            )
        )


class ScenarioActivationTests(unittest.IsolatedAsyncioTestCase):
    async def test_scenario_activation_reports_rejected_dashboard_update(self):
        class FakeAPI:
            async def async_update_dashboard(self, hass, **kwargs):
                self.update = kwargs

        class FakeCoordinator:
            data = {"scenario": 5, "scenarioTimeLeft": 300}

            async def async_request_refresh(self):
                return None

        api = FakeAPI()
        coordinator = FakeCoordinator()

        activated = await SCENARIOS_MODULE.async_activate_scenario(
            api, coordinator, object(), scenario=7, duration_minutes=60
        )

        self.assertFalse(activated)
        self.assertEqual(api.update, {"scenario": 7, "scenario_time_left": 3600})


if __name__ == "__main__":
    unittest.main()
