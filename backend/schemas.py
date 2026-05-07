from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid
from datetime import date
from decimal import Decimal
from models import InvoiceStatus


class ClientCreate(BaseModel):
    name: str
    registration_no: Optional[str] = None
    address: Optional[str] = None
    email: Optional[EmailStr] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
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


class InvoiceItemUpdate(BaseModel):
    description: Optional[str] = None
    quantity: Optional[int] = None
    unit_price: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None


class InvoiceUpdate(BaseModel):
    client_id: Optional[uuid.UUID] = None
    invoice_number: Optional[str] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    items: Optional[list[InvoiceItemCreate]] = None


class StatusUpdate(BaseModel):
    status: InvoiceStatus


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