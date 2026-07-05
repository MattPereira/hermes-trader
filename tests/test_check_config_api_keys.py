import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / ".agents/scripts/check-config-api-keys.py"
SPEC = importlib.util.spec_from_file_location("check_config_api_keys", SCRIPT)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


class ConfigApiKeyTests(unittest.TestCase):
    def validate_text(self, text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.yaml"
            path.write_text(text, encoding="utf-8")
            return validator.validate(path)

    def test_allows_empty_null_and_environment_references(self):
        self.assertEqual(
            self.validate_text(
                "empty: {api_key: ''}\n"
                "null_value: {api-key: null}\n"
                "environment: {api_key: '${VENICE_API_KEY}'}\n"
            ),
            [],
        )

    def test_rejects_literals_without_printing_values(self):
        self.assertEqual(
            self.validate_text("providers:\n  - name: example\n    api_key: literal-secret-value\n"),
            ["providers[0].api_key"],
        )

    def test_rejects_non_string_values(self):
        self.assertEqual(self.validate_text("provider: {api_key: 12345}\n"), ["provider.api_key"])


if __name__ == "__main__":
    unittest.main()
