"""Adapted original transition rules. See PROVENANCE.md. No I/O or model calls."""
import copy,re
from datetime import datetime,timedelta
GOOD={"ISSUED","ALREADY_ISSUED"}
def supports_series_error(cfg,shop_id,order_id,code):
    return code in {"539","206"} and code in cfg.get("supported_error_codes",["539"])

def fresh_eligible_check(task,oid,now,cfg=None):
    check=task.get('last_order_checks',{}).get(oid,{})
    try:age=datetime.fromisoformat(now)-datetime.fromisoformat(check['checked_at'])
    except (ValueError,KeyError):return False
    code=check.get('error_code')
    return (timedelta(0)<=age<=timedelta(minutes=5) and check.get('status')=='PENDING_ERROR'
            and code==task['orders'][oid]['error_code']
            and supports_series_error(cfg or {},task['shop_id'],oid,code))


def reduce_event(t, event, cfg, now):
    t = copy.deepcopy(t)
    kind = event["type"]
    if kind == "open":
        if str(event.get("observed_shop_id")) != t["shop_id"]:
            raise ValueError("Observed Shop ID does not match this task")
        t.update(shop_verified=True, scan_complete=False, status="RUNNING", reason="", last_step="SHOP_OPENED",last_order_checks={})
    elif kind == "scan":
        if not t["shop_verified"]:
            raise ValueError("Verify shop before scanning orders")
        if not isinstance(event.get("complete"), bool):
            raise ValueError("scan.complete must explicitly be true or false")
        previous, found = t["orders"], {}
        for item in event["orders"]:
            oid = str(item["order_id"])
            if not re.fullmatch(r"[A-Za-z0-9]{8,30}", oid) or oid in found:
                raise ValueError("Invalid or duplicate order ID")
            buyer = str(item.get("buyer", "")).strip()
            if buyer.casefold() not in {b.casefold() for b in cfg["buyers"]}:
                raise ValueError(f"{oid}: buyer is outside the configured scope")
            observed = item["status"]
            if observed not in {"PENDING_ERROR", "ALREADY_ISSUED", "SKIPPED", "REVIEW"}:
                raise ValueError("Invalid scan order status")
            code = str(item.get("error_code", ""))
            status = "READY" if observed == "PENDING_ERROR" and supports_series_error(cfg,t['shop_id'],oid,code) else observed
            if status == "PENDING_ERROR":
                status = "REVIEW"
            old = previous.get(oid, {})
            reason = item.get("reason", "")
            if status == "REVIEW" and not reason:
                reason = f"Unsupported or unclear invoice error {code or '(not readable)'}"
            if old.get("attempts", 0):
                if status == "ALREADY_ISSUED":
                    status = "ISSUED"
                elif old.get("status") in GOOD:
                    status, reason = "REVIEW", "Previously issued order now has an inconsistent UI state"
                else:
                    status = "REVIEW"
                    reason = reason or "Prior issue attempt exists; verify outcome, do not reissue"
            found[oid] = {"order_id": oid, "buyer": buyer, "error_code": code, "status": status,
                          "attempts": old.get("attempts", 0), "reason": reason,
                          "evidence": item.get("evidence", old.get("evidence", ""))}
            if status in GOOD and not found[oid]["evidence"]:
                raise ValueError("Issued order requires observed invoice evidence")
        for oid, old in previous.items():
            if oid not in found and old.get("attempts", 0):
                found[oid] = copy.deepcopy(old)
                if old["status"] not in GOOD:
                    found[oid].update(status="REVIEW", reason="Prior attempt missing from scan; inspect that order directly")
        t.update(orders=found, scan_complete=event["complete"], status="RUNNING",
                 reason=event.get("reason", ""), last_step="ORDER_CHECKED")
    elif kind == 'order_check':
        oid=event['order_id']
        if not t['shop_verified'] or oid not in t['orders'] or str(event.get('observed_order_id'))!=oid or str(event.get('observed_shop_id'))!=t['shop_id']:
            raise ValueError('Fresh order check shop/order mismatch')
        if str(event.get('buyer','')).strip().casefold() not in {b.casefold() for b in cfg['buyers']} or not event.get('evidence'):
            raise ValueError('Fresh exact configured order evidence is required')
        t.setdefault('last_order_checks',{})[oid]=dict(event,checked_at=now)
    elif kind == 'series_save_result':
        if not t.get('series_save_pending') or not event.get('success') or not event.get('evidence'):
            raise ValueError('Series save success must be observed after the persisted intent')
        if t.get('series_saved_at'):raise ValueError('Series save already recorded; verify read-only')
        t['series_saved_at']=event.get('saved_at',now)
        t['last_order_checks']={}
    elif kind in {"series_intent", "series_verified"}:
        if t["status"] != "RUNNING" or not t["shop_verified"] or not t["scan_complete"] or not any(o["status"] == "READY" for o in t["orders"].values()):
            raise ValueError("Series operation needs a verified shop, complete scan and eligible order")
        before = str(event.get("before", "")).strip()
        if not before:
            raise ValueError("Record actual series value before proceeding")
        if kind=='series_intent' and cfg.get('workflow_version')==2:
            if t.get('series_save_pending') or t['series_status'] in {'UPDATED','ALREADY_747'}:
                raise ValueError('Series save pending or already completed; inspect readback, do not submit again')
            if not any(o['status']=='READY' and fresh_eligible_check(t,oid,now,cfg) for oid,o in t['orders'].items()):
                raise ValueError('Series change requires a fresh eligible order recheck')
            t['series_save_pending']=True
        if not t["series_before"]:
            t["series_before"] = before
        t["last_step"] = "SERIES_SAVING"
        if kind == "series_verified":
            after = str(event.get("after", "")).strip()
            if after != cfg["target_series"] or not event.get("evidence"):
                raise ValueError("Verify saved series is 747 and record page evidence")
            if cfg.get('workflow_version')==2:
                if event.get('reloaded') is not True:
                    raise ValueError('Reload/revisit and read back the stored series before verification')
                if t['series_before']!=after and not t.get('series_saved_at'):
                    raise ValueError('Actual save time is unknown; inspect the saved-operation evidence, do not invent a fix date')
            t.update(series_after=after, series_status="ALREADY_747" if t["series_before"] == after else "UPDATED",
                     last_step="SERIES_SAVED",series_save_pending=False)
    elif kind == "issue_intent":
        o = t["orders"][event["order_id"]]
        if t["status"] != "RUNNING" or not t["shop_verified"] or not t["scan_complete"] or t["series_after"] != cfg["target_series"]:
            raise ValueError("Complete shop, order scan and series verification before issuance")
        if str(event.get("observed_order_id")) != o["order_id"] or str(event.get("observed_shop_id")) != t["shop_id"]:
            raise ValueError("Reverify order and shop before clicking issue")
        if str(event.get("buyer", "")).strip().casefold() != o["buyer"].casefold():
            raise ValueError("Reverify configured buyer before clicking issue")
        if str(event.get("error_code", "")) != o["error_code"]:
            raise ValueError("Invoice error changed; rescan before issuance")
        if o["status"] != "READY" or o["attempts"]:
            raise ValueError("Issuance already attempted or order not eligible. Verify outcome, do not reissue")
        if cfg.get('workflow_version')==2:
            check=t.get('last_order_checks',{}).get(o['order_id'],{})
            try:age=datetime.fromisoformat(now)-datetime.fromisoformat(check['checked_at'])
            except (ValueError,KeyError):raise ValueError('A fresh exact order recheck is required before issuance')
            if not fresh_eligible_check(t,o['order_id'],now,cfg):
                raise ValueError('A fresh eligible configured series-error recheck is required; cancelled/invoiced/changed errors cannot issue')
            if t.get('series_saved_at') and check['checked_at']<t['series_saved_at']:
                raise ValueError('Recheck the order after the series save')
        o.update(status="ISSUING", attempts=1)
        t["last_step"] = "ISSUING"
    elif kind == "order_result":
        if not t["shop_verified"] or t["status"] != "RUNNING":
            raise ValueError("Reopen and verify shop before recording results")
        o = t["orders"][event["order_id"]]
        if str(event.get("observed_order_id")) != o["order_id"] or str(event.get("observed_shop_id")) != t["shop_id"]:
            raise ValueError("Result shop/order ID does not match")
        status = event["status"]
        if status not in GOOD | {"FAILED", "REVIEW", "SKIPPED"}:
            raise ValueError("Invalid result")
        if status == "ISSUED" and not o["attempts"]:
            raise ValueError("Use ALREADY_ISSUED when no attempt was made")
        if status in GOOD:
            if not event.get("download_available") or not event.get("evidence"):
                raise ValueError("Success needs the order's real invoice download state")
        elif not event.get("reason"):
            raise ValueError("Non-success result requires a reason")
        o.update(status=status, reason=event.get("reason", ""), evidence=event.get("evidence", ""))
        t["last_step"] = "INVOICE_VERIFIED" if status in GOOD else "ORDER_REVIEWED"
    elif kind == "finish":
        orders = list(t["orders"].values())
        attempted = [o for o in orders if o["attempts"]]
        problems = [o for o in orders if o["status"] not in GOOD | {"SKIPPED"}]
        if not t["shop_verified"]:
            raise ValueError("Cannot finish an unverified shop")
        if not t["scan_complete"]:
            t["status"] = "REVIEW"
            t["reason"] = t["reason"] or "Order scan incomplete"
        elif problems:
            t["status"] = "PARTIAL" if any(o["status"] in GOOD for o in attempted) else (
                "FAILED" if attempted and all(o["status"] == "FAILED" for o in problems) else "REVIEW")
        elif attempted and any(o["status"] in GOOD for o in attempted):
            t["status"] = ("SUCCESS" if all(o["status"] in GOOD for o in attempted) else "PARTIAL") if t["series_after"] == cfg["target_series"] else "REVIEW"
        else:
            t["status"] = "SKIPPED"
            t["reason"] = t["reason"] or "No eligible configured invoice-series error; no issuance needed"
        t["last_step"] = "FINISHED"
    elif kind == "stop":
        if event["status"] not in {"BLOCKED", "REVIEW", "FAILED"} or not event.get("reason"):
            raise ValueError("Stop needs BLOCKED/REVIEW/FAILED and a reason")
        t.update(status=event["status"], shop_verified=False, scan_complete=False,
                 reason=event["reason"], last_step=event.get("last_step", t["last_step"]))
    else:
        raise ValueError(f"Unknown event type {kind}")
    t["updated_at"] = now
    return t
