from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
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


def _recalc_total(invoice: Invoice) -> None:
    invoice.total_amount = sum(
        item.quantity * item.unit_price * (1 + item.tax_rate)
        for item in invoice.items
    )


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


# --- Clients ---

@app.get("/clients", response_model=list[schemas.ClientResponse])
def get_clients(db: Session = Depends(get_db)):
    return db.query(models.Client).all()


@app.post("/clients", response_model=schemas.ClientResponse, status_code=201)
def create_client(client: schemas.ClientCreate, db: Session = Depends(get_db)):
    db_client = models.Client(**client.model_dump())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client


@app.get("/clients/{client_id}", response_model=schemas.ClientResponse)
def get_client(client_id: str, db: Session = Depends(get_db)):
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@app.put("/clients/{client_id}", response_model=schemas.ClientResponse)
def update_client(client_id: str, data: schemas.ClientUpdate, db: Session = Depends(get_db)):
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return client


@app.delete("/clients/{client_id}", status_code=204)
def delete_client(client_id: str, db: Session = Depends(get_db)):
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()


# --- Invoices ---

@app.get("/invoices", response_model=list[schemas.InvoiceResponse])
def get_invoices(db: Session = Depends(get_db)):
    return db.query(models.Invoice).all()


@app.post("/invoices", response_model=schemas.InvoiceResponse, status_code=201)
def create_invoice(invoice: schemas.InvoiceCreate, db: Session = Depends(get_db)):
    if not db.query(models.Client).filter(models.Client.id == invoice.client_id).first():
        raise HTTPException(status_code=404, detail="Client not found")

    db_invoice = models.Invoice(
        client_id=invoice.client_id,
        invoice_number=invoice.invoice_number,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
    )
    db.add(db_invoice)
    db.flush()

    for item in invoice.items:
        db.add(models.InvoiceItem(invoice_id=db_invoice.id, **item.model_dump()))

    db.refresh(db_invoice)
    _recalc_total(db_invoice)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Invoice number already exists")

    db.refresh(db_invoice)
    return db_invoice


@app.get("/invoices/{invoice_id}", response_model=schemas.InvoiceResponse)
def get_invoice(invoice_id: str, db: Session = Depends(get_db)):
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@app.put("/invoices/{invoice_id}", response_model=schemas.InvoiceResponse)
def update_invoice(invoice_id: str, data: schemas.InvoiceUpdate, db: Session = Depends(get_db)):
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if data.client_id:
        if not db.query(models.Client).filter(models.Client.id == data.client_id).first():
            raise HTTPException(status_code=404, detail="Client not found")

    for field in ("client_id", "invoice_number", "issue_date", "due_date"):
        value = getattr(data, field)
        if value is not None:
            setattr(invoice, field, value)

    if data.items is not None:
        for item in invoice.items:
            db.delete(item)
        db.flush()
        for item in data.items:
            db.add(models.InvoiceItem(invoice_id=invoice.id, **item.model_dump()))
        db.flush()
        db.refresh(invoice)

    _recalc_total(invoice)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Invoice number already exists")

    db.refresh(invoice)
    return invoice


@app.patch("/invoices/{invoice_id}/status", response_model=schemas.InvoiceResponse)
def update_invoice_status(invoice_id: str, data: schemas.StatusUpdate, db: Session = Depends(get_db)):
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.status = data.status
    db.commit()
    db.refresh(invoice)
    return invoice


@app.delete("/invoices/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: str, db: Session = Depends(get_db)):
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    db.delete(invoice)
    db.commit()


# --- PDF ---

@app.get("/invoices/{invoice_id}/pdf")
def generate_pdf(invoice_id: str, db: Session = Depends(get_db)):
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
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
        headers={"Content-Disposition": "attachment; filename=invoice.pdf"},
    )