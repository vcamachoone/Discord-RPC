#!/usr/bin/env python3
"""
test_milestone1.py - Milestone 1 Dedicated Unit Test Suite

Tests:
  - assets_gen.py:
      - Icon generation and output dictionary structure
      - 1x (22x22 px) and 2x Retina (44x44 px) resolutions
      - Color metrics: normal monochrome, active #00A8FC dot, paused 35% alpha
      - Boundary edge bleed protection
      - CLI execution
  - status_item.py:
      - LoLStatusItemController lifecycle and NSSquareStatusItemLength configuration
      - Dynamic template / non-template mode transitions
      - Button action callback dispatching (sender-aware and parameterless)
      - Accessors and properties (get_button, get_status_item, get_current_state, state)
      - Resilience against None, empty, and invalid state strings
      - Idempotent cleanup and resource management
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

import assets_gen
import status_item


class TestAssetsGenDedicated(unittest.TestCase):
    """Deep verification of assets_gen module and icon rendering logic."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="m1_assets_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_status_icons_contract(self):
        """Verify return dictionary keys and file existence."""
        icons = assets_gen.generate_status_icons(self.test_dir)
        self.assertIsInstance(icons, dict)

        required_keys = [
            "normal", "active", "paused",
            "normal@2x", "active@2x", "paused@2x",
            "normal_2x", "active_2x", "paused_2x",
            "normal_1x", "active_1x", "paused_1x",
        ]
        for key in required_keys:
            self.assertIn(key, icons, f"Missing key '{key}' in icons dict")
            path = icons[key]
            self.assertTrue(os.path.isabs(path), f"Path '{path}' is not absolute")
            self.assertTrue(os.path.exists(path), f"File '{path}' does not exist")
            self.assertGreater(os.path.getsize(path), 50)

    def test_icon_resolutions(self):
        """Verify 1x icons are 22x22 px and 2x icons are 44x44 px RGBA."""
        icons = assets_gen.generate_status_icons(self.test_dir)
        for state in ("normal", "active", "paused"):
            with Image.open(icons[state]) as im1x:
                self.assertEqual(im1x.size, (22, 22))
                self.assertEqual(im1x.mode, "RGBA")

            with Image.open(icons[f"{state}@2x"]) as im2x:
                self.assertEqual(im2x.size, (44, 44))
                self.assertEqual(im2x.mode, "RGBA")

    def test_normal_icon_monochrome_template(self):
        """Normal icon must be pure monochrome (R==G==B) for macOS template rendering."""
        icons = assets_gen.generate_status_icons(self.test_dir)
        for key in ("normal", "normal@2x"):
            with Image.open(icons[key]) as im:
                for r, g, b, a in im.getdata():
                    if a > 10:
                        self.assertEqual(r, g, f"RGB mismatch in {key}: R={r}, G={g}")
                        self.assertEqual(g, b, f"RGB mismatch in {key}: G={g}, B={b}")

    def test_active_icon_blue_dot_metrics(self):
        """Active icon must have blue dot (#00A8FC) in the bottom-right quadrant."""
        icons = assets_gen.generate_status_icons(self.test_dir)
        with Image.open(icons["active@2x"]) as im:
            w, h = im.size
            blue_pixels = []
            for x in range(w // 2, w):
                for y in range(h // 2, h):
                    r, g, b, a = im.getpixel((x, y))
                    if a > 200 and b > 200 and r < 50:
                        blue_pixels.append((r, g, b, a))

            self.assertGreater(len(blue_pixels), 40, "Too few blue pixels found")
            sample = blue_pixels[len(blue_pixels) // 2]
            # Verify #00A8FC (R:0, G:168, B:252) tolerance
            self.assertLess(sample[0], 25)
            self.assertGreaterEqual(sample[1], 150)
            self.assertLessEqual(sample[1], 185)
            self.assertGreaterEqual(sample[2], 240)

    def test_paused_icon_alpha_dimmed(self):
        """Paused icon must be dimmed with ~35% alpha."""
        icons = assets_gen.generate_status_icons(self.test_dir)
        with Image.open(icons["paused@2x"]) as im:
            alphas = [p[3] for p in im.getdata() if p[3] > 10]
            self.assertTrue(len(alphas) > 0)
            max_alpha = max(alphas)
            # 35% of 255 is ~89
            self.assertGreaterEqual(max_alpha, 70)
            self.assertLessEqual(max_alpha, 110)

    def test_border_bleed_protection(self):
        """Outer border pixels should have alpha 0 to avoid touching menubar bounds."""
        icons = assets_gen.generate_status_icons(self.test_dir)
        for key in ("normal", "active", "paused", "normal@2x", "active@2x", "paused@2x"):
            with Image.open(icons[key]) as im:
                w, h = im.size
                # Corner pixels
                self.assertEqual(im.getpixel((0, 0))[3], 0)
                self.assertEqual(im.getpixel((w - 1, 0))[3], 0)
                self.assertEqual(im.getpixel((0, h - 1))[3], 0)
                self.assertEqual(im.getpixel((w - 1, h - 1))[3], 0)

    def test_cli_execution(self):
        """Verify CLI entry point can be executed with --output-dir."""
        cli_out = os.path.join(self.test_dir, "cli_output")
        res = subprocess.run(
            [sys.executable, "assets_gen.py", "--output-dir", cli_out],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(cli_out, "menubar_normal.png")))
        self.assertTrue(os.path.exists(os.path.join(cli_out, "menubar_active@2x.png")))


class TestStatusItemDedicated(unittest.TestCase):
    """Deep verification of status_item.LoLStatusItemController."""

    def setUp(self):
        self.controllers = []

    def tearDown(self):
        for c in self.controllers:
            c.cleanup()
        self.controllers.clear()

    def _create_controller(self, *args, **kwargs):
        c = status_item.LoLStatusItemController(*args, **kwargs)
        self.controllers.append(c)
        return c

    def test_status_item_instantiation(self):
        """Verify status item and button accessors."""
        ctrl = self._create_controller()
        self.assertIsNotNone(ctrl.get_status_item())
        self.assertIsNotNone(ctrl.get_button())
        self.assertEqual(ctrl.get_current_state(), "normal")
        self.assertEqual(ctrl.state, "normal")

    def test_state_template_modes(self):
        """Verify template mode flag for normal, active, and paused states."""
        ctrl = self._create_controller()
        btn = ctrl.get_button()

        # normal -> template True
        ctrl.set_state("normal")
        self.assertEqual(ctrl.get_current_state(), "normal")
        self.assertTrue(btn.image().isTemplate())

        # active -> template False (preserves blue dot)
        ctrl.set_state("active")
        self.assertEqual(ctrl.get_current_state(), "active")
        self.assertFalse(btn.image().isTemplate())

        # paused -> template False (preserves dimmed alpha)
        ctrl.set_state("paused")
        self.assertEqual(ctrl.get_current_state(), "paused")
        self.assertFalse(btn.image().isTemplate())

    def test_button_click_dispatch(self):
        """Verify clicking the button triggers popover toggle callback."""
        clicks = []
        ctrl = self._create_controller(on_toggle_popover=lambda s: clicks.append(s))
        btn = ctrl.get_button()

        ctrl.handle_click(btn)
        self.assertEqual(len(clicks), 1)
        self.assertEqual(clicks[0], btn)

        # Trigger via Cocoa action
        btn.sendAction_to_(btn.action(), btn.target())
        self.assertEqual(len(clicks), 2)

    def test_parameterless_callback_dispatch(self):
        """Verify parameterless callback functions are supported."""
        clicks = []
        ctrl = self._create_controller(on_toggle=lambda: clicks.append(True))
        ctrl.handle_click()
        self.assertEqual(len(clicks), 1)

    def test_resilience_unknown_states(self):
        """Verify invalid, empty, or None state strings fall back gracefully without error."""
        ctrl = self._create_controller()
        ctrl.set_state("unknown_xyz")
        self.assertEqual(ctrl.get_current_state(), "normal")

        ctrl.set_state("")
        self.assertEqual(ctrl.get_current_state(), "normal")

        ctrl.set_state(None)
        self.assertEqual(ctrl.get_current_state(), "normal")

    def test_set_callback_and_tooltip(self):
        """Verify updating callback and tooltip dynamically."""
        invoked = []
        ctrl = self._create_controller()
        ctrl.set_callback(lambda: invoked.append("updated"))
        ctrl.set_tooltip("League Status")

        ctrl.handle_click()
        self.assertEqual(invoked, ["updated"])
        self.assertEqual(ctrl.get_button().toolTip(), "League Status")

    def test_cleanup_idempotent(self):
        """Verify cleanup can be called multiple times safely."""
        ctrl = self._create_controller()
        ctrl.cleanup()
        self.assertIsNone(ctrl.get_status_item())
        self.assertIsNone(ctrl.get_button())
        # Safe second call
        ctrl.cleanup()


if __name__ == "__main__":
    unittest.main()
