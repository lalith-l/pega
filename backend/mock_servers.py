from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter(prefix="/mock-erp", tags=["Mock ERP"])

@router.post("/payments/post")
async def post_payment(request: Request):
    """
    Mock ERP payment posting.
    Expects v2.4 schema: vendor_ifsc_code (NOT vendor_acc_IFSC)
    """
    body = await request.json()
    
    # Check for old schema parameter
    if "vendor_acc_IFSC" in body:
        raise HTTPException(
            status_code=400, 
            detail="Invalid parameter: 'vendor_acc_IFSC'. Did you mean 'vendor_ifsc_code'?"
        )
        
    required = ["invoice_number", "vendor_id", "amount", "vendor_ifsc_code", "account_number"]
    missing = [p for p in required if p not in body]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required parameters: {missing}")

    return {
        "status": "SUCCESS",
        "transaction_id": "TXN-ERP-991823",
        "message": f"Payment of {body.get('amount')} posted to vendor {body.get('vendor_id')}"
    }

@router.post("/invoices/validate")
async def validate_invoice(request: Request):
    """
    Mock ERP invoice validation.
    Expects v2.4 schema: invoice_number, amount
    """
    body = await request.json()
    
    if "invoice_num" in body or "invoice_amt" in body:
        raise HTTPException(
            status_code=400,
            detail="Invalid parameters. Schema v2.4 requires 'invoice_number' and 'amount'"
        )

    required = ["invoice_number", "vendor_gstin", "amount"]
    missing = [p for p in required if p not in body]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required parameters: {missing}")

    return {
        "status": "VALID",
        "message": f"Invoice {body.get('invoice_number')} validated successfully."
    }
