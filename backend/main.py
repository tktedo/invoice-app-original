from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
import models
from models import Client, InvoiceStatus, Invoice, InvoiceItem
import schemas
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader
import os

Base.metadata.create_all(bind=engine)

app = FastAPI()

templates_env = Environment(
    loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates"))
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/clients", response_model=list[schemas.ClientResponse])
def get_clients(db: Session = Depends(get_db)):
    clients = db.query(models.Client).all()
    return clients

@app.post("/clients", response_model=schemas.ClientResponse)
def create_clients(client: schemas.ClientCreate, db: Session = Depends(get_db)):
    db_client = models.Client(**client.model_dump())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@app.get("/invoices/{invoice_id}/pdf")
def generate_pdf(invoice_id: str, db: Session = Depends(get_db)):
    invoice = db.query(models.Invoice).filter(
        models.Invoice.id == invoice_id
    ).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    subtotal = sum(item.quantity * item.unit_price for item in invoice.items)
    tax_amount = sum(item.quantity * item.unit_price * item.tax_rate for item in invoice.items)
    total = subtotal + tax_amount

    template = templates_env.get_template("invoice.html")
    html_content = template.render(
        invoice_number=invoice.invoice_number,
        client_name=invoice.client.name,
        client_address=invoice.client.address or "",
        issue_date=invoice.issue_date.strftime("%Y年%m月%d日"),
        due_date=invoice.due_date.strftime("%Y年%m月%d日"),
        items=invoice.items,
        subtotal=float(subtotal),
        tax_amount=float(tax_amount),
        total=float(total),
    )

    pdf = HTML(string=html_content).write_pdf()

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=invoice.pdf"}
    )

@app.post("/invoices", response_model=schemas.InvoiceResponse)
def create_invoice(invoice: schemas.InvoiceCreate, db: Session = Depends(get_db)):
    client = db.query(models.Client).filter(
        models.Client.id == invoice.client_id
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    db_invoice = models.Invoice(
        client_id=invoice.client_id,
        invoice_number=invoice.invoice_number,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
    )
    db.add(db_invoice)
    db.flush()

    total = 0
    for item in invoice.items:
        db_item = models.InvoiceItem(
            invoice_id=db_invoice.id,
            **item.model_dump()
        )
        db.add(db_item)
        total += item.quantity * item.unit_price * (1 + item.tax_rate)

    db_invoice.total_amount = total
    db.commit()
    db.refresh(db_invoice)
    return db_invoice