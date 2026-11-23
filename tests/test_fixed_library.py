"""Approved assets stay stable, override only with an explicit spec flag."""
import copy
import hashlib
import os
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import build_diagram as B
from components import Components
from cables import Cables


class FixedLibraryTests(unittest.TestCase):
    def setUp(self):
        self.c = Components()

    def spec(self, **kwargs):
        return {'shapes': [dict(id='a', label='Ethernet switch', x=1, y=1, **kwargs)]}

    def prepare(self, spec):
        return B.prepare(spec, self.c, Cables(), tempfile.gettempdir())

    def test_five_fixed_assets_have_transparency_and_approved_hashes(self):
        self.assertEqual(set(self.c.fixed), {'ethernet_switch', 'ethernet_switch_variant', 'fiber_optic_patch_panel', 'laptop', 'video_wall'})
        self.assertNotIn('firewall', self.c.fixed)                 # web-first now; its picture is only an offline fallback
        self.assertIsNone(self.c.fixed_for('Firewall'))
        self.assertIsNotNone(self.c.picture_path('firewall'))
        self.assertNotIn('gsm_module', self.c.by_id)
        self.assertIsNone(self.c.fixed_for('GSM module'))
        self.assertIsNone(self.c.fixed_for('GSM modem'))
        for cid in self.c.fixed:
            p = self.c.picture_path(cid)
            with Image.open(p) as im:
                self.assertEqual(im.mode, 'RGBA')
                low, high = im.getchannel('A').getextrema()
                self.assertEqual(low, 0)
                self.assertGreaterEqual(high, 254)  # supplied display has native alpha capped at 254
                self.assertGreaterEqual(max(im.size), 600)

    def test_exact_label_aliases_choose_fixed_images_not_model_guesses(self):
        self.assertEqual(self.c.fixed_for('Fibre optic patch panel'), 'fiber_optic_patch_panel')
        self.assertEqual(self.c.fixed_for('Engineering laptop'), 'laptop')
        self.assertIsNone(self.c.fixed_for('Unknown model 123'))
        with patch.object(B.pictures, 'prepare', side_effect=AssertionError('Must not edit approved pixels')):
            shapes, _, _ = self.prepare(self.spec())
        self.assertEqual(shapes[0]['pic'], self.c.picture_path('ethernet_switch'))

    def test_fixed_asset_tamper_is_rejected(self):
        self.c.by_id['ethernet_switch'] = copy.deepcopy(self.c.by_id['ethernet_switch'])
        self.c.by_id['ethernet_switch']['sha256'] = '0'*64
        with self.assertRaisesRegex(B.BuildError, 'Fixed image changed'):
            self.prepare(self.spec(component='ethernet_switch'))

    def test_replacement_requires_explicit_override_flag(self):
        image = self.c.picture_path('laptop')
        with self.assertRaisesRegex(B.BuildError, 'image_override'):
            self.prepare(self.spec(component='ethernet_switch', image=image))
        shapes, _, _ = self.prepare(self.spec(component='ethernet_switch', image=image, image_override=True, image_source='User-requested replacement'))
        self.assertTrue(shapes[0]['web'])
        self.assertIn('User-requested replacement', shapes[0]['key'])
        with self.assertRaisesRegex(B.BuildError, 'requires an image'):
            self.prepare(self.spec(image_override=True))

    def test_visio_contains_exact_approved_bitmap_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'fixed.vsdx')
            B.build(self.spec(component='ethernet_switch'), os.path.join(B.ROOT, 'base', 'base.vsdx'), out, spec_dir=d)
            with open(self.c.picture_path('ethernet_switch'), 'rb') as fh:
                approved = fh.read()
            with zipfile.ZipFile(out) as z:
                self.assertTrue(any(z.read(n) == approved for n in z.namelist() if n.startswith('visio/media/')))


if __name__ == '__main__':
    unittest.main()
