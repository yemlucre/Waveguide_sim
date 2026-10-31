"""Presentation contract tests; numerical benchmarks remain in test_optics.py."""
from pathlib import Path
from dataclasses import asdict
import json
import re
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'/'Agamemnon.Optics'))
from optics import Parameters,find_design
from report import build_report_data,write_report


class ReportChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=Parameters(points=256,window_um=80,separation_um=10,length_um=50)
        cls.result,cls.runs=find_design(p,[10.],target=.3)
        cls.result.update(input={'parameters':asdict(p),'separations_um':[10.],'target':.3},
                          model_version='slab-ssfft-1',timestamp_utc='2026-10-30T10:00:00+00:00',
                          parameter_origin='assumed_not_measured',scan_numerics_passed=True)

    def test_intensity_and_coordinates_come_from_raw_fields(self):
        data=build_report_data(self.result,self.runs,[10.])
        r=data['runs'][0]
        source=self.runs[0]
        mask=abs(source['x_um'])<=25
        np.testing.assert_allclose(r['intensity'],abs(source['fields'][:,mask])**2,atol=5.1e-9)
        np.testing.assert_array_equal(r['x_um'],source['x_um'][mask])
        np.testing.assert_array_equal(r['right'],source['right_power'])
        self.assertEqual(data['result']['target'],.3)
        self.assertIsNone(data['result']['selected_index'])

    def test_invalid_report_dimensions_rejected(self):
        with self.assertRaises(ValueError):build_report_data(self.result,self.runs,[])

    def test_offline_export_no_candidate_and_safe_embedded_json(self):
        fixture=dict(self.result,model_version='</script><script>unexpected()</script>')
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)
            write_report(output,fixture,self.runs,[10.])
            text=(output/'index.html').read_text(encoding='utf-8')
            self.assertNotIn('@@DATA@@',text)
            self.assertNotIn('@@SCRIPT@@',text)
            self.assertNotIn('<script>unexpected()',text)
            payload=json.loads(re.search(r'<script id="report-data" type="application/json">(.*?)</script>',text,re.S).group(1))
            self.assertEqual(payload['result']['status'],'target_not_reached')
            self.assertEqual(payload['result']['model_version'],fixture['model_version'])
            self.assertTrue((output/'spacing-0.png').exists())
            self.assertIn('getElementById',text)
            self.assertNotIn('<script src=',text)


if __name__=='__main__':unittest.main(verbosity=2)
