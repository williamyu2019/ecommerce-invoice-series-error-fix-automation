"""Internal process boundary for an interrupted synthetic workflow."""
import argparse
from .simulation import prepare_recovery,recover_scenario
p=argparse.ArgumentParser();p.add_argument('mode',choices=['write','read']);p.add_argument('scenario');p.add_argument('output');a=p.parse_args()
if a.mode=='write':prepare_recovery(a.scenario,a.output)
else:recover_scenario(a.output)
