import unittest

from failurebench.config import ConfigError, load_config, parse_config


class ConfigTest(unittest.TestCase):
    def test_demo_fixture_loads_deterministically(self) -> None:
        first = load_config("config/demo.json")
        second = load_config("config/demo.json")

        self.assertEqual(first, second)
        self.assertEqual(1, first.version)
        self.assertEqual(("etch-101", "etch-201"), tuple(item.id for item in first.equipment))
        self.assertEqual(("TEMP_HIGH",), first.equipment[0].alarms)

    def test_duplicate_equipment_id_is_rejected(self) -> None:
        equipment = {"id": "etch-101", "temperature_c": 84.5, "alarms": []}

        with self.assertRaisesRegex(ConfigError, "duplicate equipment id"):
            parse_config({"version": 1, "equipment": [equipment, equipment]})

    def test_unsupported_config_version_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, "unsupported config version"):
            parse_config({"version": 2, "equipment": [{}]})

    def test_invalid_alarm_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, "unique non-empty strings"):
            parse_config(
                {
                    "version": 1,
                    "equipment": [
                        {
                            "id": "etch-101",
                            "temperature_c": 84.5,
                            "alarms": ["TEMP_HIGH", "TEMP_HIGH"],
                        }
                    ],
                }
            )


if __name__ == "__main__":
    unittest.main()
