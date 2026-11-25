"""Regressao do seletor de portas do inicializador."""

import importlib.util
import socket
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "iniciar-servidor.py"
spec = importlib.util.spec_from_file_location("cognix_launcher", SCRIPT)
assert spec is not None and spec.loader is not None
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_free_port_can_be_selected(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        self.assertEqual(launcher.choose_port(port, port), port)

    def test_listening_port_cannot_be_selected(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind(("127.0.0.1", 0))
            port = occupied.getsockname()[1]
            occupied.listen()
            with self.assertRaisesRegex(RuntimeError, "Nenhuma porta"):
                launcher.choose_port(port, port)

    def test_rejects_invalid_port_range(self):
        with self.assertRaises(ValueError):
            launcher.choose_port(8100, 8000)
