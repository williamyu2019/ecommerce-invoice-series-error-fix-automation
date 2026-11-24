import argparse,json,sys
from pathlib import Path
if sys.version_info<(3,10):raise SystemExit('Python 3.10+ required; Python 3.12 is the tested version.')
from .simulation import run_all
p=argparse.ArgumentParser(description='Offline invoice core demo. Synthetic inputs; no model or business service calls.')
p.add_argument('--output',type=Path,required=True,help='A new directory; existing directories are never overwritten.')
a=p.parse_args()
try:
 r=run_all(a.output);print(json.dumps(dict(environment='SIMULATION',passed=r['passed'],scenarios=len(r['scenarios']),review=str(a.output/'review.html')),indent=2));raise SystemExit(0 if r['passed'] else 1)
except (ValueError,FileExistsError) as e:
 print(str(e),file=sys.stderr);raise SystemExit(2)
