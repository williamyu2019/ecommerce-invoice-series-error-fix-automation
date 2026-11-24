import json,re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class DashboardAssets(unittest.TestCase):
 def test_both_original_dashboard_versions_are_included(self):
  folder=ROOT/'dashboards';meta=json.loads((folder/'sources.json').read_text())
  self.assertEqual(meta['evolution']['origin'],'Codex original dashboard')
  self.assertEqual(meta['evolution']['phase_count'],5)
  self.assertEqual(meta['monitoring']['origin'],'Claude returned Operations dashboard')
  self.assertEqual(meta['monitoring']['source_data_generated_at'],'2026-11-12T15:10:41-03:00')
  evo=(folder/'evolution.html').read_text();ops=(folder/'monitoring.html').read_text()
  self.assertIn('Workflow evolution',evo);self.assertIn('Automation across five iterations',evo)
  self.assertIn('BRSIP Operations',ops);self.assertIn('Minutes per order',ops);self.assertIn('Human interventions per day',ops)
  for page in [evo,ops]:self.assertIn('SYNTHETIC',page);self.assertNotRegex(page,r'<script[^>]+src=["\x27]https?://')
 def test_phases_and_monitoring_population_match_declared_scope(self):
  f=ROOT/'dashboards';e=json.loads((f/'evolution-data.json').read_text());d=json.loads((f/'monitoring-core-results.json').read_text())
  self.assertEqual(len(e['phases']),5);self.assertEqual([x['number'] for x in e['phases']],['01','02','03','04','05'])
  self.assertEqual(len(d['batches']),16)
  self.assertEqual(sum(x['orders_checked'] for x in d['batches']),11)
  self.assertEqual(sum(x['issued'] for x in d['batches']),5)
  self.assertEqual(sum(x['already_issued'] for x in d['batches']),1)
  self.assertEqual(sum(x['skipped'] for x in d['batches']),1)
  self.assertEqual(sum(x['open'] for x in d['batches']),4)
  self.assertTrue(all(x['minutes_per_order'] is None and x['human_count'] is None for x in d['batches']))
 def test_monitoring_has_fourteen_explicitly_illustrative_days(self):
  import datetime
  f=ROOT/'dashboards';d=json.loads((f/'monitoring-data.json').read_text());rows=d['batches']
  self.assertEqual(d['kind'],'SYNTHETIC_ILLUSTRATIVE')
  self.assertFalse(d['measured_from_core_runs']);self.assertEqual(len(rows),14)
  dates=[datetime.date.fromisoformat(x['date']) for x in rows]
  self.assertEqual(len(set(dates)),14)
  self.assertTrue(all((b-a).days==1 for a,b in zip(dates,dates[1:])))
  self.assertTrue(any(x['orders_checked']==0 for x in rows))
  self.assertTrue(any(x['open']>0 for x in rows))
  self.assertTrue(any(x['minutes_per_order'] is None for x in rows))
  self.assertTrue(any(isinstance(x['minutes_per_order'],float) and x['minutes_per_order']>0 for x in rows))
  self.assertTrue(any(x['human_count'] is None for x in rows))
  for x in rows:
   self.assertEqual(x['orders_checked'],sum(x[k] for k in ['issued','already_issued','skipped','open']))
   self.assertLessEqual(x['orders_checked'],x['series_errors'])
   self.assertEqual(x['problems_total'],x['series_errors']+x['tax_regime']+x['other_problems'])
   self.assertEqual(x['time_coverage'],'SYNTHETIC')
  page=(f/'monitoring.html').read_text()
  self.assertIn('14 illustrative days',page)
  self.assertIn('not measured business or core-run performance',page)
  embedded=page.split('const localSources={batches:',1)[1].split('};const draws=',1)[0]
  self.assertEqual(json.loads(embedded),rows)
if __name__=='__main__':unittest.main()
