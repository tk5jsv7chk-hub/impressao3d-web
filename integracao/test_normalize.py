import base64
import unittest
from enum import Enum
from types import SimpleNamespace
from normalize import authenticated, normalize_printer


class Tests(unittest.TestCase):
    def test_auth(self):
        header = "Basic " + base64.b64encode("operador:uma-senha-longa-123".encode()).decode()
        self.assertTrue(authenticated(header, "operador", "uma-senha-longa-123"))
        self.assertFalse(authenticated(header, "operador", "outra-senha-longa-123"))
        self.assertFalse(authenticated("Basic !!!", "operador", "uma-senha-longa-123"))
        self.assertFalse(authenticated(header, "", "uma-senha-longa-123"))
        self.assertFalse(authenticated(header, "operador", "curta"))

    def test_unknown_is_not_zero(self):
        row = normalize_printer(SimpleNamespace(id=17, name="Kobra X"))
        self.assertEqual(row["id"], "17")
        self.assertIsNone(row["status"])
        self.assertIsNone(row["progress_percent"])
        self.assertIsNone(row["remaining_minutes"])

    def test_enum(self):
        class State(Enum):
            PRINTING = "printing"
        row = normalize_printer(SimpleNamespace(id=18, name="X 2", current_status=State.PRINTING))
        self.assertEqual(row["status"], "printing")

    def test_identifier_required(self):
        with self.assertRaises(ValueError):
            normalize_printer(SimpleNamespace(name="X"))

    def test_no_secret_passthrough(self):
        row = normalize_printer(SimpleNamespace(id=1, name="X", key="segredo", user_id=99))
        self.assertNotIn("key", row)
        self.assertNotIn("user_id", row)


if __name__ == "__main__":
    unittest.main()
