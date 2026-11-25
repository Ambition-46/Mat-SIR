import unittest
from .units import convert,normalize_sir

class Units(unittest.TestCase):
    def test_ingestion_and_threshold(self):
        stored=convert(150,'cm','m')
        sir={'groups':[{'conditions':[{'field':'length','value':120,'unit':'cm','operator':'>'}]}]}
        normalized=normalize_sir(sir,{'length':'m'})
        self.assertGreater(stored,normalized['groups'][0]['conditions'][0]['value'])
        self.assertEqual(sir['groups'][0]['conditions'][0]['value'],120)
    def test_pressure_and_offsets(self):
        self.assertAlmostEqual(convert(.5,'GPa','MPa'),500)
        self.assertAlmostEqual(convert(0,'℃','K'),273.15)
        self.assertAlmostEqual(convert(32,'°F','degC'),0)
    def test_incompatible_missing_and_nonfinite(self):
        for v,a,b in [(1,'m','s'),(1,'','m'),(float('nan'),'m','m')]:
            with self.assertRaises(ValueError):convert(v,a,b)
    def test_ranges_and_missing_query_unit(self):
        sir={'groups':[{'conditions':[{'field':'length','value':[100,200],'unit':'cm'}]}]}
        self.assertEqual(normalize_sir(sir,{'length':'m'})['groups'][0]['conditions'][0]['value'],[1,2])
        sir['groups'][0]['conditions'][0]={'field':'length','value':2}
        self.assertEqual(normalize_sir(sir,{'length':'m'})['groups'][0]['conditions'][0]['value'],2)
