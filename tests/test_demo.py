import copy,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXPECTED=json.loads((ROOT/'examples/expectations.json').read_text())
class DemoContract(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def test_frozen_scenarios_and_structured_logs(self):
  from invoice_demo.simulation import run_scenario
  for name,expected in EXPECTED.items():
   with self.subTest(scenario=name):
    out=self.root/name;r=run_scenario(name,out)
    self.assertEqual({k:r[k] for k in expected},expected)
    self.assertEqual(r['environment'],'SIMULATION')
    logs=[json.loads(x) for x in (out/'run-log.jsonl').read_text().splitlines()]
    self.assertTrue(logs);self.assertTrue(all(x['run_id'] and x['module'] and x['step'] and x['status'] and x['recorded_at'] for x in logs))
    self.assertEqual(json.loads((out/'result.json').read_text()),r)
 def test_resume_and_checkpoint_tamper(self):
  from invoice_demo.simulation import run_scenario,load_checkpoint
  out=self.root/'resume';r=run_scenario('resume-unknown',out);path=out/'checkpoint.json';c=load_checkpoint(path)
  self.assertEqual(c['state']['tasks'][0]['orders']['DEMOORDER001']['attempts'],1)
  self.assertEqual(r['attempts'],1);self.assertEqual(r['recovery_action'],'VERIFY_INVOICE_READ_ONLY');self.assertFalse(r['closeout_verified'])
  d=json.loads(path.read_text());d['payload']['state']['tasks'][0]['orders']['DEMOORDER001']['attempts']=0;path.write_text(json.dumps(d))
  with self.assertRaisesRegex(ValueError,'checkpoint.*hash'):load_checkpoint(path)
 def test_existing_output_and_unknown_scenario(self):
  from invoice_demo.simulation import run_scenario,run_all
  out=self.root/'existing';out.mkdir();(out/'sentinel').write_text('keep')
  for action in [lambda:run_scenario('normal539',out),lambda:run_all(out)]:
   with self.assertRaises(FileExistsError):action()
  self.assertEqual((out/'sentinel').read_text(),'keep');self.assertEqual(len(list(out.iterdir())),1)
  bad=self.root/'bad'
  with self.assertRaisesRegex(ValueError,'Unknown scenario'):run_scenario('../other',bad)
  self.assertFalse(bad.exists())
 def test_malformed_fixture(self):
  from invoice_demo.simulation import validate_fixture
  base=json.loads((ROOT/'examples/scenarios.json').read_text())[0]
  for patch in [{'order_id':'../wrong'},{'shop_id':'notnumeric'},{'buyer':''},{'error_code':'999'},{'target_series':'123'}]:
   with self.subTest(patch=patch),self.assertRaises(ValueError):validate_fixture(dict(base,**patch))
 def test_tracker_conflict_and_duplicate_rows_preserved(self):
  from invoice_demo.simulation import apply_mock_writeback
  plan=[dict(shop_id='9001',order_id='DEMOORDER001',action='fixed',date_fixed='2026-01-15',note='fixture')]
  row=dict(shop_id='9001',order_id='DEMOORDER001',row=9,action='',date_fixed=None,note='')
  for rows in [[dict(row,action='other')],[row,dict(row,row=10)]]:
   before=copy.deepcopy(rows)
   with self.assertRaises(ValueError):apply_mock_writeback(plan,rows)
   self.assertEqual(rows,before)
 def test_stale_check_and_cancelled_order(self):
  from invoice_demo.simulation import new_task,configuration
  from invoice_demo.state_machine import reduce_event
  cfg=configuration();t=new_task();now='2026-01-15T10:00:00-03:00'
  check=dict(type='order_check',order_id='DEMOORDER001',observed_order_id='DEMOORDER001',observed_shop_id='9001',buyer='demo.buyer',status='PENDING_ERROR',error_code='539',evidence='SIMULATION')
  for e in [dict(type='open',observed_shop_id='9001'),dict(type='scan',complete=True,orders=[dict(order_id='DEMOORDER001',buyer='demo.buyer',status='PENDING_ERROR',error_code='539')]),check]:t=reduce_event(t,e,cfg,now)
  with self.assertRaises(ValueError):reduce_event(t,dict(type='series_intent',before='004'),cfg,'2026-01-15T10:06:00-03:00')
  for e in [dict(type='series_intent',before='004'),dict(type='series_save_result',success=True,evidence='SIMULATION'),dict(type='series_verified',before='004',after='747',reloaded=True,evidence='SIMULATION'),dict(check,status='CANCELLED')]:t=reduce_event(t,e,cfg,now)
  with self.assertRaises(ValueError):reduce_event(t,dict(type='issue_intent',order_id='DEMOORDER001',observed_order_id='DEMOORDER001',observed_shop_id='9001',buyer='demo.buyer',error_code='539'),cfg,now)
  self.assertEqual(t['orders']['DEMOORDER001']['attempts'],0)
 def test_valid_custom_fixture_is_used_end_to_end(self):
  from unittest.mock import patch
  from invoice_demo.simulation import run_scenario
  fixture=json.loads((ROOT/'examples/scenarios.json').read_text())[0]
  fixture.update(shop_id='9100',order_id='DEMOORDER099',buyer='example.buyer',series_before='005')
  out=self.root/'custom'
  all_fixtures=json.loads((ROOT/'examples/scenarios.json').read_text());all_fixtures[0]=fixture
  with patch('invoice_demo.simulation.fixtures',return_value=all_fixtures):r=run_scenario('normal539',out)
  state=json.loads((out/'state.json').read_text());t=state['tasks'][0]
  self.assertEqual(t['shop_id'],'9100');self.assertIn('DEMOORDER099',t['orders'])
  self.assertEqual(t['orders']['DEMOORDER099']['buyer'],'example.buyer');self.assertEqual(r['series_before'],'005')
  self.assertTrue(r['closeout_verified'])
 def test_matrix_validated_before_any_output(self):
  from unittest.mock import patch
  from invoice_demo.simulation import run_all
  original=json.loads((ROOT/'examples/scenarios.json').read_text())
  for label,items in [('empty',[]),('missing',original[:-1]),('duplicate',original+[original[0]]),('undeclared',[dict(original[0],id='../escape')]+original[1:]),('bad-later',[original[0],dict(original[1],buyer='')]+original[2:])]:
   out=self.root/label
   with patch('invoice_demo.simulation.fixtures',return_value=items),self.assertRaises(ValueError):run_all(out)
   self.assertFalse(out.exists())
 def test_unrelated_refusal_cannot_pass_wrong_order_case(self):
  from unittest.mock import patch
  from invoice_demo.simulation import run_all,Simulation
  original=Simulation.observation
  def unrelated(sim):
   if sim.name=='wrong-order':sim.stage='evidence';raise ValueError('unrelated injected evidence failure')
   return original(sim)
  with patch.object(Simulation,'observation',unrelated):report=run_all(self.root/'injected')
  wrong=next(x for x in report['scenarios'] if x['id']=='wrong-order')
  self.assertFalse(wrong['passed']);self.assertFalse(report['passed']);self.assertIn('rejection_stage',wrong['mismatches'])
 def test_actual_tracker_reorder_preserves_old_row(self):
  from invoice_demo.simulation import run_scenario
  out=self.root/'moved';run_scenario('writeback-moved',out)
  before=json.loads((out/'tracker-before.json').read_text());after=json.loads((out/'tracker-after.json').read_text())
  self.assertEqual(before[0]['row'],2)
  target=next(x for x in after if x['order_id']=='DEMOORDER001');other=next(x for x in after if x['row']==2)
  self.assertEqual(target['row'],13);self.assertNotEqual(other['order_id'],'DEMOORDER001');self.assertEqual(other['action'],'Unrelated preserved value')
 def test_recovery_writer_exits_before_fresh_reader(self):
  from invoice_demo.simulation import run_scenario
  for name in ['resume-unknown','resume-confirmed']:
   out=self.root/name;r=run_scenario(name,out)
   log=[json.loads(x) for x in (out/'run-log.jsonl').read_text().splitlines()]
   writer=next(x['process_id'] for x in log if x['step']=='interrupted_after_intent')
   reader=next(x['process_id'] for x in log if x['step']=='recover')
   self.assertNotEqual(writer,reader);self.assertEqual(r['attempts'],1)
 def test_cli_and_evaluation(self):
  out=self.root/'cli';r=subprocess.run([sys.executable,'-B','-m','invoice_demo','--output',str(out)],cwd=ROOT,capture_output=True,text=True)
  self.assertEqual(r.returncode,0,r.stderr)
  d=json.loads((out/'evaluation-results.json').read_text());self.assertEqual(len(d['scenarios']),16);self.assertTrue(all(x['passed'] for x in d['scenarios']))
  self.assertEqual(d['environment'],'SIMULATION');self.assertTrue((out/'run-log.jsonl').is_file());self.assertIn('No model calls',(out/'review.html').read_text())
if __name__=='__main__':unittest.main()
