"""Audit failures are checked against real OOXML fixtures, not mocked workbook APIs."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

SCRIPT = Path(__file__).resolve().parents[1]/'skill/sova/scripts/excel_audit.py'


class ExcelAuditTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('excel_audit', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'book.xlsx'

    def workbook(self, cells, mode='auto', extras=None):
        with ZipFile(self.path,'w') as z:
            z.writestr('xl/workbook.xml',f'''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Расчёт" sheetId="1" r:id="rId1"/></sheets><calcPr calcMode="{mode}"/></workbook>''')
            z.writestr('xl/_rels/workbook.xml.rels','''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>''')
            z.writestr('xl/worksheets/sheet1.xml',f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1">{cells}</row></sheetData></worksheet>')
            for key, value in (extras or {}).items():
                z.writestr(key,value)
        return self.module.audit(self.path)

    def test_cached_error_identifies_cell_and_sheet(self):
        result = self.workbook('<c r="A1" t="e"><f>1/0</f><v>#DIV/0!</v></c>')
        errors = [f for f in result['findings'] if f['code']=='cached_error']
        self.assertEqual(errors[0]['sheet'],'Расчёт')
        self.assertEqual(errors[0]['cell'],'A1')
        self.assertEqual(errors[0]['value'],'#DIV/0!')

    def test_missing_formula_cache_is_not_accepted_as_success(self):
        result = self.workbook('<c r="A1"><f>SUM(B1:B3)</f></c>')
        self.assertIn('formula_without_cached_result',{f['code'] for f in result['findings']})
        self.assertFalse(result['recalculation_verified'])

    def test_cached_number_does_not_prove_recalculation(self):
        result = self.workbook('<c r="A1"><f>1+1</f><v>2</v></c>')
        self.assertFalse(result['recalculation_verified'])
        self.assertEqual(result['verdict'],'requires_engine_and_logic_checks')

    def test_broken_reference_found_in_formula(self):
        result = self.workbook('<c r="A1"><f>SUM(#REF!)</f><v>0</v></c>')
        self.assertIn('broken_reference',{f['code'] for f in result['findings']})

    def test_manual_mode_and_external_links_flagged(self):
        result = self.workbook('<c r="A1"><v>1</v></c>',mode='manual',
                               extras={'xl/externalLinks/externalLink1.xml':'<externalLink/>'})
        codes = {f['code'] for f in result['findings']}
        self.assertIn('manual_calculation',codes)
        self.assertIn('external_links',codes)

    def test_advanced_features_preserved_in_inventory(self):
        result = self.workbook('<c r="A1"><v>1</v></c>',extras={
            'xl/pivotTables/pivotTable1.xml':'<pivotTableDefinition/>',
            'xl/vbaProject.bin':'not executable test data',
            'xl/connections.xml':'<connections/>'})
        self.assertEqual(result['features']['pivot_tables'],1)
        self.assertTrue(result['features']['macros'])
        self.assertTrue(result['features']['connections'])

    def test_valid_empty_string_formula_cache_not_reported_missing(self):
        result = self.workbook('<c r="A1" t="str"><f>IF(1=1,&quot;&quot;,1)</f><v/></c>')
        self.assertNotIn('formula_without_cached_result',{f['code'] for f in result['findings']})


if __name__=='__main__':
    unittest.main()
