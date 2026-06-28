import httpx
import asyncio
import json

async def run_e2e():
    print("Starting e2e test for Test 2...")
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # 1. Convene Court
        print("1. Convening court...")
        resp = await client.post("/court/convene", json={
            "business_objective": "Process employee expense reimbursement of 125000 INR. Validate receipts, check GST, get manager approval if above threshold, trigger bank transfer via NEFT."
        })
        resp.raise_for_status()
        session_id = resp.json()["session_id"]
        print(f"Court Session ID: {session_id}")

        # Wait for court to finish
        print("Waiting for court to complete...")
        while True:
            resp = await client.get(f"/court/{session_id}/status")
            status = resp.json().get("session_status")
            if status == "COMPLETED" or status == "AWAITING_HUMAN":
                break
            elif status == "FAILED":
                print("Court failed!")
                return
            await asyncio.sleep(2)
        
        print("Court completed!")

        # 1.5 Resolve conflicts if any
        resp = await client.get(f"/court/{session_id}/record")
        record = resp.json().get("court_record", {})
        nodes = record.get("proposed_nodes", [])
        for node in nodes:
            if node.get("final_status") == "DISPUTED":
                print(f"Resolving dispute for node {node['node_id']}...")
                await client.post("/court/resolve", json={
                    "session_id": session_id,
                    "node_id": node["node_id"],
                    "resolution_action": "ACCEPT",
                    "modification_instruction": ""
                })
        
        # Verify it's COMPLETED now
        resp = await client.get(f"/court/{session_id}/status")
        if resp.json().get("session_status") != "COMPLETED":
            print("Failed to resolve all conflicts!")
            return
            
        # 2. Compile
        print("2. Compiling workflow...")
        resp = await client.post("/court/compile", json={"session_id": session_id})
        resp.raise_for_status()
        case_id = resp.json()["case_id"]
        print(f"Case ID: {case_id}")

        # 3. Execute
        print("3. Executing workflow...")
        resp = await client.post(f"/cases/{case_id}/execute")
        resp.raise_for_status()

        # Wait for TRC to activate (AWAITING_HUMAN)
        print("Waiting for execution to pause (TRC)...")
        while True:
            resp = await client.get(f"/cases/{case_id}")
            status = resp.json()["status"]
            if status == "AWAITING_HUMAN":
                print("TRC completed, case is AWAITING_HUMAN.")
                break
            elif status == "FAILED":
                print("Execution failed!")
                return
            elif status == "CLOSED_SUCCESS":
                print("Execution succeeded without TRC!")
                return
            await asyncio.sleep(2)

        # 4. Approve Patch
        print("4. Approving patch...")
        resp = await client.post(f"/cases/{case_id}/trc/approve")
        if resp.status_code != 200:
            print(f"Failed to approve patch: {resp.text}")
            return
        resp.raise_for_status()
        print("Patch approved!")

        # Wait for execution to finish
        print("Waiting for execution to finish...")
        while True:
            resp = await client.get(f"/cases/{case_id}")
            status = resp.json()["status"]
            if status == "CLOSED_SUCCESS":
                print("Execution completed successfully!")
                break
            elif status == "FAILED":
                print("Execution failed after patch!")
                return
            await asyncio.sleep(2)
            
        print("E2E Test completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_e2e())
