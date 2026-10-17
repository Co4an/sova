#!/usr/bin/env python3
"""Read-only OOXML audit. Does not calculate formulas or certify workbook correctness."""
import argparse
import json
from pathlib import Path
import posixpath
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

NS = {'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def audit(path):
    result = {'file':str(Path(path).resolve()),'recalculation_verified':False,
              'verdict':'requires_engine_and_logic_checks','sheets':[], 'findings':[],
              'limitations':['Reads stored OOXML only; cached values may be stale.',
                             'Does not detect all formula, reference, circularity or business-logic errors.']}
    findings = result['findings']
    with ZipFile(path) as book:
        infos = book.infolist()
        if sum(i.file_size for i in infos) > 512*1024*1024 or any(i.file_size > 64*1024*1024 for i in infos):
            raise ValueError('Workbook exceeds audit memory limits; use native Excel inspection')
        names = set(book.namelist())
        if len(names) != len(infos):
            raise ValueError('Workbook contains duplicate ZIP entries')
        result['features'] = {
            'pivot_tables':sum(n.startswith('xl/pivotTables/') and n.endswith('.xml') for n in names),
            'charts':sum(n.startswith('xl/charts/chart') and n.endswith('.xml') for n in names),
            'tables':sum(n.startswith('xl/tables/') and n.endswith('.xml') for n in names),
            'macros':'xl/vbaProject.bin' in names,
            'connections':'xl/connections.xml' in names,
            'external_links':sum(n.startswith('xl/externalLinks/externalLink') and n.endswith('.xml') for n in names)
        }
        if result['features']['external_links']:
            findings.append({'code':'external_links','severity':'review','message':'Check linked books and refresh state in Excel'})
        if result['features']['macros'] or result['features']['connections']:
            findings.append({'code':'native_features','severity':'review','message':'Preserve macros/connections; verify in target Excel version'})
        workbook = ET.fromstring(book.read('xl/workbook.xml'))
        calc = workbook.find('m:calcPr',NS)
        result['calculation'] = dict(calc.attrib) if calc is not None else {}
        if calc is not None and calc.get('calcMode') == 'manual':
            findings.append({'code':'manual_calculation','severity':'review','message':'Manual calculation mode; stored results may be stale'})
        rels = ET.fromstring(book.read('xl/_rels/workbook.xml.rels'))
        targets = {r.get('Id'):r.get('Target') for r in rels
                   if r.get('TargetMode') != 'External' and r.get('Type','').endswith('/worksheet')}
        for sheet in workbook.findall('m:sheets/m:sheet',NS):
            target = targets.get(sheet.get('{'+NS['r']+'}id'))
            if target is None:
                continue
            member = posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/'+target)
            if not member.startswith('xl/'):
                raise ValueError('Invalid worksheet relationship target')
            xml = ET.fromstring(book.read(member))
            stats = {'name':sheet.get('name'),'state':sheet.get('state','visible'),
                     'cells':0,'formulas':0}
            for cell in xml.findall('.//m:sheetData/m:row/m:c',NS):
                stats['cells'] += 1
                formula, value = cell.find('m:f',NS), cell.find('m:v',NS)
                loc = {'sheet':stats['name'],'cell':cell.get('r')}
                if cell.get('t') == 'e':
                    findings.append(dict(loc,code='cached_error',severity='error',value=value.text if value is not None else None))
                if formula is not None:
                    stats['formulas'] += 1
                    # Empty string results legitimately have an empty <v/> with t=str.
                    if value is None or (value.text is None and cell.get('t') != 'str'):
                        findings.append(dict(loc,code='formula_without_cached_result',severity='review'))
                    import re
                    expression = re.sub(r'"(?:[^"]|"")*"','""',formula.text or '')
                    if '#REF!' in expression.upper():
                        findings.append(dict(loc,code='broken_reference',severity='error',formula=formula.text))
            result['sheets'].append(stats)
    if any(f['severity']=='error' for f in findings):
        result['verdict'] = 'structural_errors_found'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file',type=Path)
    parser.add_argument('--out',type=Path,help='Optional JSON audit file')
    args = parser.parse_args()
    try:
        result = audit(args.file)
        text = json.dumps(result,ensure_ascii=False,indent=2)+'\n'
        if args.out:
            if args.out.resolve() == args.file.resolve():
                raise ValueError('Audit output must not overwrite the workbook')
            args.out.parent.mkdir(parents=True,exist_ok=True)
            args.out.write_text(text,encoding='utf-8')
        print(text,end='')
        return 2 if result['verdict']=='structural_errors_found' else 0
    except (OSError,ValueError,KeyError,BadZipFile,ET.ParseError) as exc:
        print(str(exc),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
