"""Adapted original tracker guards; used only with simulation proofs in this demo."""
import hashlib,json,re
from datetime import datetime,timedelta,timezone
SPREADSHEET_ID="synthetic-tracker"
SHEET="Synthetic outcomes"
METHODS=set()
FINAL={"SUCCESS","SKIPPED","PARTIAL","REVIEW","FAILED","BLOCKED"}

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def required_pairs(store, state):
    shops = {str(t['shop_id']) for t in state['tasks']}
    references = store.cfg.get('reference_orders')
    if not isinstance(references, dict) or set(references) != shops:
        raise ValueError('Current reference_orders must cover every input shop exactly; rebuild from the current queue')
    pairs = set()
    for shop, orders in references.items():
        if not isinstance(orders, list) or not orders:
            raise ValueError('Every batch shop needs its current source order IDs')
        pairs.update((str(shop), str(oid)) for oid in orders)
    for task in state['tasks']:
        pairs.update((str(task['shop_id']), str(oid)) for oid in task['orders'])
    owners = {}
    for shop, oid in pairs:
        if not re.fullmatch(r'\d{1,20}', shop) or not re.fullmatch(r'[A-Za-z0-9]{8,30}', oid):
            raise ValueError('Invalid tracker identity')
        if oid in owners and owners[oid] != shop:
            raise ValueError('One order is associated with different shops')
        owners[oid] = shop
    return sorted(pairs)


def identity(store, state):
    current = hashlib.sha256(store.input.read_bytes()).hexdigest()
    if current != state['input_sha256']:
        raise ValueError('Input changed; do not reuse this batch ledger')
    pairs = required_pairs(store, state)
    return {'input_sha256': current, 'orders_sha256': digest(pairs)}, pairs


def check_readback(store, state, path):
    if not path.exists():
        raise ValueError(f'Missing live tracker readback: {path.name}. Read the simulated tracker; do not infer saving from user confirmation')
    proof = json.loads(path.read_text(encoding='utf-8'))
    keys, pairs = identity(store, state)
    if proof.get('schema_version') != 1 or proof.get('spreadsheet_id') != SPREADSHEET_ID or proof.get('sheet') != SHEET:
        raise ValueError('Tracker proof has the wrong schema, spreadsheet or tab')
    simulation=store.cfg.get('workflow_version')==2 and store.cfg.get('test_mode') is True
    methods={'simulation'} if simulation else METHODS
    expected_live=not simulation
    if store.cfg.get('workflow_version')==2 and proof.get('environment')!=('SIMULATION' if simulation else 'LIVE'):
        raise ValueError('Tracker evidence environment mismatch')
    if proof.get('method') not in methods or proof.get('live_readback') is not expected_live or not str(proof.get('evidence', '')).strip():
        raise ValueError('Actual connector/browser readback and concrete evidence are required')
    try:
        checked = datetime.fromisoformat(proof['checked_at'].replace('Z', '+00:00'))
        now = datetime.fromisoformat(store.now())
        if checked.tzinfo is None or now.tzinfo is None:
            raise ValueError('Timestamp must contain timezone')
        if not timedelta(minutes=-5) <= now - checked <= timedelta(hours=12):
            raise ValueError('Tracker readback expired; refresh it before repair/resume')
    except (KeyError, TypeError) as exc:
        raise ValueError('Missing tracker timestamp') from exc
    if any(proof.get(k) != v for k, v in keys.items()):
        raise ValueError('Tracker proof belongs to a different batch/order scope')
    observed, row_numbers = {}, set()
    for row in proof.get('rows', []):
        pair = (str(row.get('shop_id', '')), str(row.get('order_id', '')))
        n = row.get('row')
        if not isinstance(n, int) or isinstance(n, bool) or n < 2:
            raise ValueError('Every observed order needs its real Sheet row number')
        if pair in observed or n in row_numbers:
            raise ValueError('Duplicate tracker order or row; resolve before repair')
        observed[pair], row_numbers = row, row_numbers | {n}
    if set(observed) != set(pairs):
        raise ValueError('Tracker membership does not match ALL current batch orders, including newly discovered orders')
    return proof, observed


def require_tracker_membership(store, state):
    proof, _ = check_readback(store, state, store.out / 'Tracker_Enrollment_Verification.json')
    return {'verified_orders': len(proof['rows']), 'checked_at': proof['checked_at']}


def scope_plan(store, state):
    keys, pairs = identity(store, state)
    return dict(schema_version=1, spreadsheet_id=SPREADSHEET_ID, sheet=SHEET,
                **keys, required_pairs=[{'shop_id': s, 'order_id': o} for s, o in pairs],
                proof_path=str(store.out / 'Tracker_Enrollment_Verification.json'),
                instruction='Read the simulated tracker and match all pairs. Fill only from observed rows. This plan is not proof.')


def series_history(state,cfg=None):
    """Date and affected orders from real series-verified events, not Updated At."""
    from .state_machine import supports_series_error
    latest_scan, first_before, fixed, verified_shops, saved_at = {}, {}, {}, set(), {}
    for record in state.get('events', []):
        sid, event = str(record.get('shop_id', '')), record.get('event', {})
        kind = event.get('type')
        if kind == 'scan':
            latest_scan[sid] = {str(o['order_id']) for o in event.get('orders', [])
                                if o.get('status') == 'PENDING_ERROR' and supports_series_error(cfg or {},sid,str(o['order_id']),str(o.get('error_code')))}
        elif kind == 'series_save_result' and event.get('success'):
            saved_at[sid]=event.get('saved_at',record['at']) if (cfg or {}).get('workflow_version')==2 else record['at']
        elif kind == 'series_intent' or kind == 'series_verified':
            first_before.setdefault(sid, str(event.get('before', '')))
            if kind == 'series_verified' and sid not in verified_shops and str(event.get('after')) == '747' and first_before[sid] != '747':
                verified_shops.add(sid)
                stamp = datetime.fromisoformat(saved_at.get(sid,record['at']).replace('Z', '+00:00'))
                if stamp.utcoffset() != timedelta(hours=-3):
                    stamp = stamp.astimezone(timezone(timedelta(hours=-3)))
                for oid in latest_scan.get(sid, set()):
                    fixed.setdefault((sid, oid), stamp.date().isoformat())
    return fixed


def writeback_plan(store, state):
    keys, pairs = identity(store, state)
    if any(t['status'] not in FINAL for t in state['tasks']):
        raise ValueError('Finish/account for every shop before final tracker closeout')
    tasks = {str(t['shop_id']): t for t in state['tasks']}
    fixed = series_history(state,store.cfg)
    first_seen, verified_747, discovered_after_save = set(), set(), set()
    if store.cfg.get('workflow_version')==2:
        for record in state.get('events',[]):
            sid=str(record.get('shop_id',''));event=record.get('event',{})
            if event.get('type')=='series_verified' and str(event.get('after'))=='747':verified_747.add(sid)
            elif event.get('type')=='scan':
                for order in event.get('orders',[]):
                    pair=(sid,str(order['order_id']))
                    if pair not in first_seen and sid in verified_747:discovered_after_save.add(pair)
                    first_seen.add(pair)
    rows, unresolved = [], []
    for sid, oid in pairs:
        task = tasks[sid]
        order = task['orders'].get(oid, {})
        status = order.get('status', 'NOT_CHECKED')
        date = fixed.get((sid, oid))
        if date:
            action = f'Fixed invoice # to 747; invoice {status}'
        elif status == 'ALREADY_ISSUED':
            action = 'Skipped - invoice already issued; series unchanged'
        elif status == 'SKIPPED':
            action = 'Skipped - order no longer eligible; series unchanged'
        elif status == 'ISSUED' and (task.get('series_status') == 'ALREADY_747' or (sid,oid) in discovered_after_save):
            action = 'Series already 747; invoice ISSUED'
        elif status in {'REVIEW', 'FAILED'}:
            action = f'Review - no series repair recorded; invoice {status}'
        else:
            action = 'Review - result not confirmed'
            unresolved.append({'shop_id': sid, 'order_id': oid})
        if task.get('series_status') == 'UPDATED' and status in {'ISSUED', 'FAILED'} and not date and (sid,oid) not in discovered_after_save:
            unresolved.append({'shop_id': sid, 'order_id': oid, 'reason': 'Missing series event/date; inspect actual logs'})
        rows.append({'shop_id': sid, 'order_id': oid, 'action': action, 'date_fixed': date,
                     'invoice_status': status, 'note': order.get('reason') or order.get('evidence') or task.get('reason', '')})
    return dict(schema_version=1, spreadsheet_id=SPREADSHEET_ID, sheet=SHEET, **keys,
                state_sha256=digest(state), rows=rows, needs_review=unresolved,
                instruction='Match Sheet rows by order AND shop. Preserve A:AJ snapshots; write AK action, AL actual series-fix date only. Read back all rows.')


def verify_closeout(store, state):
    plan = writeback_plan(store, state)
    if plan['needs_review']:
        raise ValueError('Some results/dates are unconfirmed; do not claim full closeout')
    proof, observed = check_readback(store, state, store.out / 'Tracker_Closeout_Verification.json')
    if proof.get('state_sha256') != plan['state_sha256']:
        raise ValueError('Closeout proof does not match the current ledger')
    for row in plan['rows']:
        actual = observed[(row['shop_id'], row['order_id'])]
        if actual.get('action') != row['action'] or actual.get('date_fixed') != row['date_fixed']:
            raise ValueError('Sheet action/date mismatch; missing dates and skipped orders must not be marked fixed')
        if row['note'] and actual.get('note') != row['note']:
            raise ValueError('Closeout reason/evidence note was not verified')
    return {'verified': True, 'orders': len(plan['rows']), 'checked_at': proof['checked_at']}
