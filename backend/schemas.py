from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid
from datetime import date
from decimal import Decimal

class ClientCreate(BaseModel):
    name: str
    registration_no: Optional[str] = None
    address: Optional[str] = None
    email: Optional[EmailStr] = None

class ClientResponse(BaseModel):
    id: uuid.UUID
    name: str
    registration_no: Optional[str] = None
    address: Optional[str] = None
    email: Optional[EmailStr] = None

    class Config:
        from_attributes = True

class InvoiceItemCreate(BaseModel):
    description: str
    quantity: int
    unit_price: Decimal
    tax_rate: Decimal = Decimal("0.10")

class InvoiceCreate(BaseModel):
    client_id: uuid.UUID
    invoice_number: str
    issue_date: date
    due_date: date
    items: list[InvoiceItemCreate]

class InvoiceItemResponse(BaseModel):
    id: uuid.UUID
    description: str
    quantity: int
    unit_price: Decimal
    tax_rate: Decimal

    class Config:
        from_attributes = True

class InvoiceResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    invoice_number: str
    issue_date: date
    due_date: date
    status: str
    total_amount: Decimal
    items: list[InvoiceItemResponse]

    class Config:
        from_attributes = True