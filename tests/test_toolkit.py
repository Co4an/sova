import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'skill/sova/scripts/project.py'
INSTALL = ROOT / 'install.py'


class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def call(self, script, *args):
        return subprocess.run([sys.executable, str(script), *map(str,args)], capture_output=True, text=True)

    def init(self):
        result = self.call(TOOL,'init',self.root/'study','--task','Исследование LEGO')
        self.assertEqual(result.returncode,0,result.stderr)
        return self.root/'study'

    def write(self, folder, file, value):
        (folder/file).write_text(json.dumps(value,ensure_ascii=False) if not isinstance(value,str) else value)

    def test_installer_all_and_idempotence(self):
        for _ in range(2):
            result = self.call(INSTALL,'--target',self.root,'--app','all')
            self.assertEqual(result.returncode,0,result.stderr)
        for name in ('.agents','.claude'):
            self.assertTrue((self.root/name/'skills/sova/SKILL.md').is_file())
        self.assertFalse((self.root/'AGENTS.md').exists())

    def test_install_conflict_preserves_existing_file(self):
        self.call(INSTALL,'--target',self.root,'--app','codex')
        target = self.root/'.agents/skills/sova/SKILL.md'
        target.write_text('personal custom skill')
        result = self.call(INSTALL,'--target',self.root,'--app','codex')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(target.read_text(),'personal custom skill')

    def test_personal_layout_installs_for_all_three_apps(self):
        spec = importlib.util.spec_from_file_location('aaos_installer',INSTALL)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.install(self.root,'all',personal=True)
        for path in ('.codex/skills','.claude/skills','.gemini/config/skills'):
            self.assertTrue((self.root/path/'sova/SKILL.md').is_file())

    def test_init_does_not_overwrite_existing_run(self):
        folder = self.init()
        self.write(folder,'analysis.md','Existing research')
        result = self.call(TOOL,'init',folder,'--task','different')
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((folder/'analysis.md').read_text(),'Existing research')

    def test_invalid_plan_cannot_advance(self):
        folder = self.init()
        result = self.call(TOOL,'advance',folder)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(json.loads((folder/'state.json').read_text())['stage'],'plan')

    def ready_for_review(self):
        folder = self.init()
        self.write(folder,'plan.json',{'requirements':['Стратегический анализ'],
            'tasks':[{'id':'market','question':'Что изменилось?'}]})
        self.assertEqual(self.call(TOOL,'advance',folder).returncode,0)
        self.write(folder,'sources.json',[{'id':'S1','title':'Annual report','url':'https://example.org/report',
            'accessed':'2026-10-16','evidence':'retrieved_text','excerpt':'Revenue 100',
            'locator':'p. 5'}])
        self.assertEqual(self.call(TOOL,'advance',folder).returncode,0)
        self.write(folder,'analysis.md','Выручка 100 [S1].')
        self.assertEqual(self.call(TOOL,'advance',folder).returncode,0)
        self.write(folder,'report.md','# Отчёт\nВыручка 100 [S1].')
        self.assertEqual(self.call(TOOL,'advance',folder).returncode,0)
        return folder

    def test_unknown_citation_blocks_review(self):
        folder = self.ready_for_review()
        self.write(folder,'report.md','Unsupported [S999].')
        self.write(folder,'review.json',{'approved':True,'issues':[],
            'reviewer':'self_review','requirements':[{'requirement':'Стратегический анализ','met':True}]})
        self.assertNotEqual(self.call(TOOL,'advance',folder).returncode,0)
        self.assertEqual(json.loads((folder/'state.json').read_text())['stage'],'review')

    def test_complete_requires_covered_requirements_and_review(self):
        folder = self.ready_for_review()
        self.write(folder,'review.json',{'approved':True,'issues':[],
            'reviewer':'self_review','requirements':[{'requirement':'Стратегический анализ','met':True}]})
        result = self.call(TOOL,'advance',folder)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads((folder/'state.json').read_text())['stage'],'complete')
        self.assertTrue((folder/'final/report.md').is_file())
        self.assertIn('https://example.org/report',(folder/'final/report.md').read_text())

    def test_rejection_stops_after_three_revisions(self):
        folder = self.ready_for_review()
        for cycle in range(4):
            self.write(folder,'review.json',{'approved':False,'issues':['Нужен источник'],
                'reviewer':'self_review','requirements':[{'requirement':'Стратегический анализ','met':False}]})
            result = self.call(TOOL,'advance',folder)
            self.assertEqual(result.returncode,0,result.stderr)
            if cycle < 3:
                self.assertEqual(self.call(TOOL,'advance',folder).returncode,0)
                self.assertEqual(self.call(TOOL,'advance',folder).returncode,0)
        state = json.loads((folder/'state.json').read_text())
        self.assertEqual(state['stage'],'needs_review')
        self.assertEqual(state['revisions'],3)
        self.assertFalse((folder/'final/report.md').exists())

    def test_bad_source_url_rejected(self):
        folder = self.ready_for_review()
        sources = json.loads((folder/'sources.json').read_text())
        sources[0]['url'] = 'javascript:alert(1)'
        self.write(folder,'sources.json',sources)
        self.assertNotEqual(self.call(TOOL,'check',folder).returncode,0)

    def test_incomplete_requirement_coverage_blocks_approval(self):
        folder = self.ready_for_review()
        self.write(folder,'review.json',{'approved':True,'issues':[],
            'reviewer':'self_review','requirements':[]})
        self.assertNotEqual(self.call(TOOL,'advance',folder).returncode,0)
        self.assertFalse((folder/'final/report.md').exists())

    def test_lock_prevents_concurrent_state_change(self):
        folder = self.ready_for_review()
        (folder/'.state.lock').write_text('')
        result = self.call(TOOL,'advance',folder)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('locked',result.stderr)
        self.assertEqual(json.loads((folder/'state.json').read_text())['stage'],'review')

    def test_status_survives_process_restart(self):
        folder = self.ready_for_review()
        result = self.call(TOOL,'status',folder)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['stage'],'review')
        self.assertEqual(len(json.loads(result.stdout)['history']),4)


if __name__ == '__main__':
    unittest.main()
