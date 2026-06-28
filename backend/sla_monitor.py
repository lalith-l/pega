import asyncio
from datetime import datetime
from sqlalchemy import select
from db import AsyncSessionLocal
from models import Case
from audit import log_event

async def sla_monitor_loop():
    """Background task to monitor active cases and escalate SLA breaches."""
    print("[SLA Monitor] Started.")
    while True:
        try:
            async with AsyncSessionLocal() as db:
                now_str = datetime.utcnow().isoformat()
                
                # Find executing/paused cases past SLA
                stmt = select(Case).where(
                    Case.status.in_(["EXECUTING", "PAUSED", "AWAITING_HUMAN"]),
                )
                result = await db.execute(stmt)
                active_cases = result.scalars().all()
                
                for case in active_cases:
                    compiled = case.compiled_workflow
                    if isinstance(compiled, dict) and "sla_deadline" in compiled:
                        if now_str > compiled["sla_deadline"]:
                            print(f"[SLA Monitor] 🚨 SLA Breach on case {case.case_id}!")
                            await log_event(db, case.case_id, "SLA_BREACH", "SYSTEM", {
                                "deadline": compiled["sla_deadline"],
                                "current_time": now_str
                            })
                            # Trigger escalation notification via SSE
                            from sse_manager import sse_manager
                            await sse_manager.publish(case.case_id, "SLA_BREACH", {
                                "message": f"SLA Breach: Case {case.case_id} missed deadline {compiled['sla_deadline']}",
                                "deadline": compiled["sla_deadline"],
                                "current_time": now_str
                            })
                            
        except Exception as e:
            print(f"[SLA Monitor] Error: {e}")
            
        await asyncio.sleep(60) # Run every 60 seconds
