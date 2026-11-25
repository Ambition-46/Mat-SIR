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

class DescriptionUnits(unittest.TestCase):
    def test_description_formats(self):
        from .units import description_unit
        for text,expected in [('长度，单位为米','m'),('压缩模量(GPa)，描述','GPa'),('Strength (MPa)','MPa'),('Length; unit: cm','cm'),('累计深度，常见单位为μm','um')]:
            self.assertEqual(description_unit(text),expected)
    def test_no_guesses(self):
        from .units import description_unit
        for text in ['长度','单位依数据来源定义，例如μm/a','单位为m或cm','单位MPa；单位GPa']:
            self.assertIsNone(description_unit(text))
    def test_preserve_equal_and_absent_units(self):
        from .units import normalize_value
        self.assertEqual(normalize_value('1.500','厘米','cm'),'1.500')
        self.assertEqual(normalize_value('2.00',None,'m'),'2.00')
        with self.assertRaises(ValueError):normalize_value(2,'m',None)
    def test_reads_property_description(self):
        from unittest.mock import Mock
        from .units import standard_units,normalize_sir
        cur=Mock();cur.fetchall.return_value=[{'property_name':'length','property_description':'长度，单位m'}]
        units=standard_units(cur)
        self.assertIn('FROM property_table',cur.execute.call_args[0][0])
        sir={'groups':[{'conditions':[{'field':'length','unit':'cm','value':120}]}]}
        self.assertEqual(normalize_sir(sir,units)['groups'][0]['conditions'][0]['value'],1.2)
