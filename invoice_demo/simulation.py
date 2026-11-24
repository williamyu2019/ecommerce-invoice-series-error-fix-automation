"""Offline harness around adapted real transition/tracker rules. No service clients."""
from __future__ import annotations
import copy,hashlib,html,json,os,re,subprocess,sys,uuid
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from .state_machine import reduce_event
from .tracker import digest,scope_plan,require_tracker_membership,writeback_plan,verify_closeout

ROOT=Path(__file__).resolve().parents[1]
SCENARIO_IDS=('normal539','normal206','already-issued','cancelled','wrong-shop','wrong-order','missing-authorization','agent-authored-authorization','resume-unknown','resume-confirmed','save-unconfirmed','reload-old-series','writeback-moved','writeback-conflict','evidence-environment','evidence-hash')
EXPECTED_FIELDS={'outcome','attempts','series_saves','closeout_verified','recovery_action','rejected_actions','order_status','rejection_stage','tracker_action','tracker_date','tracker_note'}
NOW='2026-01-15T10:00:00-03:00'  # Synthetic observation clock, never actual business timing.

def save(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def configuration(fixture=None):
 f=fixture or dict(shop_id='9001',order_id='DEMOORDER001',buyer='demo.buyer')
 return dict(workflow_version=2,test_mode=True,buyers=[f['buyer']],supported_error_codes=['539','206'],target_series='747',reference_orders={f['shop_id']:[f['order_id']]})
def new_task(shop_id='9001'):return dict(agent_id='9000',shop_id=shop_id,status='PENDING',shop_verified=False,scan_complete=False,series_before='',series_after='',series_status='NOT_CHECKED',orders={},reason='',last_step='PENDING',updated_at='')
def validate_fixture(f):
 for key in ['shop_id','order_id','buyer','error_code','target_series','series_before']:
  if not isinstance(f.get(key),str) or not f[key].strip():raise ValueError('Missing fixture field: '+key)
 if not re.fullmatch(r'\d{1,20}',f['shop_id']) or not re.fullmatch(r'[A-Za-z0-9]{8,30}',f['order_id']):raise ValueError('Invalid fixture identity')
 if f['error_code'] not in {'539','206'} or f['target_series']!='747':raise ValueError('Unsupported fixture configuration')

def checkpoint(path,state,cfg,run_id=None):
 payload=dict(environment='SIMULATION',state=state,cfg=cfg,observation_clock=NOW,run_id=run_id)
 save(path,dict(payload=payload,sha256=digest(payload)))
def load_checkpoint(path):
 c=json.loads(Path(path).read_text(encoding='utf-8'))
 if c.get('sha256')!=digest(c.get('payload')):raise ValueError('checkpoint content hash mismatch')
 payload=c['payload']
 if payload.get('environment')!='SIMULATION' or payload.get('cfg',{}).get('test_mode') is not True:raise ValueError('checkpoint environment mismatch')
 return payload

def apply_mock_writeback(plan,rows):
 """Validate all targets/conflicts first; return a new table. Never alter the input."""
 result=copy.deepcopy(rows);targets={};positions=set()
 for row in result:
  key=(row['shop_id'],row['order_id'])
  if key in targets or row['row'] in positions:raise ValueError('Duplicate tracker identity or row')
  targets[key]=row;positions.add(row['row'])
 planned=set()
 for item in plan:
  key=(item['shop_id'],item['order_id'])
  if key in planned or key not in targets:raise ValueError('Missing or repeated tracker target')
  planned.add(key);row=targets[key]
  if any(row.get(k) not in (None,'',item.get(k)) for k in ['action','date_fixed','note']):raise ValueError('Tracker value conflict; preserve existing row')
 for item in plan:
  row=targets[(item['shop_id'],item['order_id'])]
  row.update({k:item.get(k) for k in ['action','date_fixed','note']})
 return result

class Simulation:
 def __init__(self,name,out,fixture):
  self.name=name;self.out=out;self.f=fixture;self.cfg=configuration(fixture);self.state=dict(tasks=[new_task(fixture['shop_id'])],events=[],phase='REPAIR')
  self.run_id='sim-'+uuid.uuid4().hex[:12];self.rejected=0;self.recovery=None;self.closeout=False;self.stage='startup';self.rejection_stage=None
  out.mkdir(parents=True,exist_ok=False);(out/'evidence').mkdir();save(out/'input.json',fixture)
  self.state['input_sha256']=hashlib.sha256((out/'input.json').read_bytes()).hexdigest()
  self.store=SimpleNamespace(input=out/'input.json',out=out,cfg=self.cfg,now=lambda:NOW)
  self.rows=[dict(shop_id=self.f['shop_id'],order_id=self.f['order_id'],row=2,action='',date_fixed=None,note='')]
  save(out/'tracker-before.json',self.rows)
 def log(self,step,status,inputs=None,outputs=None,error=None,module='core'):
  entry=dict(run_id=self.run_id,process_id=os.getpid(),recorded_at=datetime.now(timezone.utc).isoformat(),environment='SIMULATION',observation_clock=NOW,module=module,step=step,status=status,inputs=inputs,outputs=outputs,tool='simulated fixture / adapted Python core',model_calls=0,error=error)
  with (self.out/'run-log.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
 def emit(self,event):
  self.stage=event['type'];old=self.state['tasks'][0]
  if event['type'] in {'series_intent','series_verified','issue_intent'}:require_tracker_membership(self.store,self.state)
  try:t=reduce_event(old,event,self.cfg,NOW)
  except ValueError as e:
   self.log(self.stage,'REJECTED',event,error=dict(type=type(e).__name__,message=str(e),location='state_machine.reduce_event'));raise
  self.state['tasks'][0]=t;self.state['events'].append(dict(at=NOW,shop_id=self.f['shop_id'],event=event))
  self.log(self.stage,'COMPLETED',event,dict(status=t['status'],series=t['series_after'],attempts={k:v['attempts'] for k,v in t['orders'].items()}))
  save(self.out/'state.json',self.state)
 def observation(self):
  self.stage='evidence'
  payload=dict(environment='SIMULATION',shop_id=self.f['shop_id'],order_id=self.f['order_id'],source='synthetic fixture')
  text=json.dumps(payload,sort_keys=True);raw=self.out/'evidence/observation.txt';raw.write_text(text)
  receipt=dict(environment='LIVE' if self.name=='evidence-environment' else 'SIMULATION',raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),raw_file='evidence/observation.txt')
  if self.name=='evidence-hash':raw.write_text('SIMULATION: changed fixture text')
  save(self.out/'evidence/receipt.json',receipt)
  if receipt['environment']!='SIMULATION':raise ValueError('Evidence environment mismatch')
  if receipt['raw_sha256']!=hashlib.sha256(raw.read_bytes()).hexdigest():raise ValueError('Evidence raw hash mismatch')
  self.log('evidence','COMPLETED',receipt,module='evidence')
 def authorization(self):
  self.stage='simulated_authorization'
  auth=dict(environment='SIMULATION',input_origin='agent' if self.name=='agent-authored-authorization' else 'fixture-operator',confirmed=self.name!='missing-authorization')
  save(self.out/'simulated-authorization.json',auth)
  if not auth['confirmed'] or auth['input_origin']!='fixture-operator':raise ValueError('Missing valid simulated operator confirmation')
  self.log(self.stage,'COMPLETED',auth,module='simulation adapter')
 def proof(self,closeout=False):
  plan=writeback_plan(self.store,self.state) if closeout else scope_plan(self.store,self.state)
  keys={k:plan[k] for k in ['schema_version','spreadsheet_id','sheet','input_sha256','orders_sha256']}
  pairs={(x['shop_id'],x['order_id']) for x in plan['rows' if closeout else 'required_pairs']}
  observed=[copy.deepcopy(x) for x in self.rows if (x['shop_id'],x['order_id']) in pairs]
  proof=dict(keys,checked_at=NOW,method='simulation',live_readback=False,environment='SIMULATION',evidence='SIMULATION only: in-memory fixture tracker readback',rows=observed)
  if closeout:proof['state_sha256']=plan['state_sha256']
  save(self.out/('Tracker_Closeout_Verification.json' if closeout else 'Tracker_Enrollment_Verification.json'),proof)
  return proof
 def check(self,wrong=False):
  self.emit(dict(type='order_check',order_id=self.f['order_id'],observed_order_id=('WRONGORDER01' if self.f['order_id']!='WRONGORDER01' else 'WRONGORDER02') if wrong else self.f['order_id'],observed_shop_id=self.f['shop_id'],buyer=self.f['buyer'],status='PENDING_ERROR',error_code=self.f['error_code'],evidence='SIMULATION exact current order detail'))
 def issue(self):self.emit(dict(type='issue_intent',order_id=self.f['order_id'],observed_order_id=self.f['order_id'],observed_shop_id=self.f['shop_id'],buyer=self.f['buyer'],error_code=self.f['error_code']))
 def close(self):
  self.stage='tracker_writeback';plan=writeback_plan(self.store,self.state);save(self.out/'writeback-plan.json',plan)
  if self.name=='writeback-moved':
   self.rows[0]['row']=13;self.rows.append(dict(shop_id='9999',order_id='OTHERORDER001',row=2,action='Unrelated preserved value',date_fixed=None,note='Unrelated fixture row'))
  if self.name=='writeback-conflict':self.rows[0]['action']='Existing other decision'
  save(self.out/'tracker-prewrite.json',self.rows)
  self.rows=apply_mock_writeback(plan['rows'],self.rows);save(self.out/'tracker-after.json',self.rows)
  self.proof(True);self.closeout=verify_closeout(self.store,self.state)['verified'];self.log('tracker_readback','COMPLETED',outputs=dict(verified=self.closeout,rows=self.rows),module='tracker')
 def execute(self,stop_after_intent=False):
  outcome='BLOCKED'
  try:
   self.log('startup','STARTED',self.f,module='simulation adapter');self.observation();self.authorization()
   self.emit(dict(type='open',observed_shop_id=str(int(self.f['shop_id'])+1) if self.name=='wrong-shop' else self.f['shop_id']))
   status='ALREADY_ISSUED' if self.name=='already-issued' else 'SKIPPED' if self.name=='cancelled' else 'PENDING_ERROR'
   self.emit(dict(type='scan',complete=True,orders=[dict(order_id=self.f['order_id'],buyer=self.f['buyer'],status=status,error_code=self.f['error_code'],evidence='SIMULATION observed invoice download' if status=='ALREADY_ISSUED' else '',reason='SIMULATION order cancelled' if status=='SKIPPED' else '')]))
   self.proof();require_tracker_membership(self.store,self.state)
   if status in {'ALREADY_ISSUED','SKIPPED'}:
    self.emit(dict(type='finish'));self.close();outcome='SKIPPED'
   else:
    self.check(self.name=='wrong-order');self.emit(dict(type='series_intent',before=self.f['series_before']))
    if self.name!='save-unconfirmed':self.emit(dict(type='series_save_result',success=True,evidence='SIMULATION save success'))
    self.emit(dict(type='series_verified',before=self.f['series_before'],after=self.f['series_before'] if self.name=='reload-old-series' else '747',reloaded=True,evidence='SIMULATION series reload'))
    self.check();self.issue()
    if self.name.startswith('resume-'):
     checkpoint(self.out/'checkpoint.json',self.state,self.cfg,self.run_id)
     self.log('interrupted_after_intent','INTERRUPTED',outputs=dict(attempts=1),module='recovery')
     if stop_after_intent:return dict(interrupted=True)
     raise RuntimeError('Recovery must start in a new process')
    if self.name=='resume-unknown':
     self.emit(dict(type='order_result',order_id=self.f['order_id'],observed_order_id=self.f['order_id'],observed_shop_id=self.f['shop_id'],status='REVIEW',reason='SIMULATION outcome unknown; manual inspection required'))
     self.emit(dict(type='finish'));outcome='REVIEW'
    else:
     self.emit(dict(type='order_result',order_id=self.f['order_id'],observed_order_id=self.f['order_id'],observed_shop_id=self.f['shop_id'],status='ISSUED',download_available=True,evidence='SIMULATION same-order invoice download available'))
     self.emit(dict(type='finish'));self.close();outcome='COMPLETE'
  except ValueError as e:
   self.rejected+=1;self.rejection_stage=self.stage;outcome='WRITEBACK_CONFLICT' if self.stage=='tracker_writeback' else 'BLOCKED'
   self.log(self.stage,'REJECTED',error=dict(type=type(e).__name__,message=str(e),location='offline simulation adapter'))
   save(self.out/'tracker-after.json',self.rows)
  return self.finalize(outcome)
 def finalize(self,outcome):
  t=self.state['tasks'][0];order=t['orders'].get(self.f['order_id'],{})
  row=next((x for x in self.rows if x['shop_id']==self.f['shop_id'] and x['order_id']==self.f['order_id']),{})
  result=dict(rejection_stage=self.rejection_stage,tracker_action=row.get('action',''),tracker_date=row.get('date_fixed'),tracker_note=row.get('note',''),scenario=self.name,run_id=self.run_id,environment='SIMULATION',outcome=outcome,order_status=order.get('status','NOT_CHECKED'),attempts=order.get('attempts',0),series_saves=sum(x['event']['type']=='series_save_result' and x['event'].get('success',False) for x in self.state['events']),series_before=t['series_before'],series_after=t['series_after'],closeout_verified=self.closeout,recovery_action=self.recovery,rejected_actions=self.rejected,model_calls=0,live_business_actions=0)
  save(self.out/'tracker-after.json',self.rows);save(self.out/'result.json',result);save(self.out/'state.json',self.state);self.log('result','COMPLETED',outputs=result,module='simulation adapter');return result

def fixtures():return json.loads((ROOT/'examples/scenarios.json').read_text(encoding='utf-8'))
def expectations():return json.loads((ROOT/'examples/expectations.json').read_text(encoding='utf-8'))
def validate_matrix(items,wants):
 if not isinstance(items,list) or len(items)!=len(SCENARIO_IDS):raise ValueError('Required scenario matrix must contain all 16 cases')
 ids=[x.get('id') for x in items if isinstance(x,dict)]
 if len(ids)!=len(items) or len(set(ids))!=len(ids) or set(ids)!=set(SCENARIO_IDS):raise ValueError('Unsupported, duplicate or missing scenario ID')
 if not isinstance(wants,dict) or set(wants)!=set(SCENARIO_IDS):raise ValueError('Required expectation matrix does not match supported scenarios')
 for item in items:
  validate_fixture(item)
  if not isinstance(wants[item['id']],dict) or set(wants[item['id']])!=EXPECTED_FIELDS:raise ValueError('Missing or extra required expectation fields')
 return items,wants

def prepare_recovery(name,output):
 items,_=validate_matrix(fixtures(),expectations())
 if name not in {'resume-unknown','resume-confirmed'}:raise ValueError('Not a recovery scenario')
 fixture=next(x for x in items if x['id']==name)
 return Simulation(name,Path(output),fixture).execute(stop_after_intent=True)

def recover_scenario(output):
 out=Path(output);payload=load_checkpoint(out/'checkpoint.json');f=json.loads((out/'input.json').read_text())
 sim=Simulation.__new__(Simulation);sim.out=out;sim.f=f;sim.name=f['id'];sim.cfg=payload['cfg'];sim.state=payload['state'];sim.run_id=payload['run_id'];sim.rejected=0;sim.closeout=False;sim.stage='recover';sim.rejection_stage=None
 sim.rows=json.loads((out/'tracker-before.json').read_text());sim.store=SimpleNamespace(input=out/'input.json',out=out,cfg=sim.cfg,now=lambda:NOW)
 orders=list(sim.state['tasks'][0]['orders'].values())
 if len(orders)!=1 or orders[0]['attempts']!=1 or orders[0]['status']!='ISSUING':raise ValueError('Checkpoint has no uncertain single issuance to reconcile')
 sim.recovery='VERIFY_INVOICE_READ_ONLY';sim.log('recover','COMPLETED',outputs=dict(next_action=sim.recovery),module='recovery')
 try:sim.issue()
 except ValueError:sim.rejected=1;sim.rejection_stage='issue_intent'
 else:raise RuntimeError('Duplicate issuance was allowed')
 if sim.name=='resume-unknown':
  sim.emit(dict(type='order_result',order_id=f['order_id'],observed_order_id=f['order_id'],observed_shop_id=f['shop_id'],status='REVIEW',reason='SIMULATION outcome unknown; manual inspection required'));sim.emit(dict(type='finish'));outcome='REVIEW'
 elif sim.name=='resume-confirmed':
  sim.emit(dict(type='order_result',order_id=f['order_id'],observed_order_id=f['order_id'],observed_shop_id=f['shop_id'],status='ISSUED',download_available=True,evidence='SIMULATION same-order invoice download available'));sim.emit(dict(type='finish'));sim.close();outcome='COMPLETE'
 else:raise ValueError('Unsupported recovery fixture')
 return sim.finalize(outcome)

def run_scenario(name,output):
 if name not in SCENARIO_IDS:raise ValueError('Unknown scenario: '+name)
 items,_=validate_matrix(fixtures(),expectations());f=next(x for x in items if x['id']==name);out=Path(output)
 if out.exists():raise FileExistsError(str(out))
 if name.startswith('resume-'):
  for mode in ['write','read']:
   child=subprocess.run([sys.executable,'-B','-m','invoice_demo.recovery',mode,name,str(out.resolve())],cwd=ROOT,capture_output=True,text=True)
   if child.returncode:raise RuntimeError('Recovery child failed: '+child.stderr)
  return json.loads((out/'result.json').read_text())
 return Simulation(name,out,f).execute()

def run_all(output):
 items,expect=validate_matrix(fixtures(),expectations());out=Path(output);out.mkdir(parents=True,exist_ok=False);results=[]
 for f in items:
  r=run_scenario(f['id'],out/f['id']);want=expect[f['id']];mismatch={k:dict(expected=v,actual=r.get(k)) for k,v in want.items() if r.get(k)!=v}
  results.append(dict(id=f['id'],evaluation=f['evaluation'],description=f['description'],expected=want,actual={k:r.get(k) for k in want},passed=not mismatch,mismatches=mismatch,result=f['id']+'/result.json',log=f['id']+'/run-log.jsonl'))
 report=dict(version='0.3.0',environment='SIMULATION',recorded_at=datetime.now(timezone.utc).isoformat(),model_calls=0,live_business_actions=0,scenarios=results,passed=all(x['passed'] for x in results),limitations=['No model calls or live browser.','Fixture authorization labels do not establish actual user provenance.','Timing and tokens are not business savings evidence.'])
 save(out/'evaluation-results.json',report)
 with (out/'run-log.jsonl').open('w',encoding='utf-8') as log:
  for f in items:log.write((out/f['id']/'run-log.jsonl').read_text(encoding='utf-8'))
 from .review import render
 (out/'review.html').write_text(render(report),encoding='utf-8');return report
