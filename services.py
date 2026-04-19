from models import (
    db,
    User,
    Category,
    Supplier,
    Product,
    InventoryBatch,
    Customer,
    Prescription,
    Transaction,
    TransactionItem,
    Invoice,
    InvoiceItem,
    Payment,
    PaymentGateway,
    PaymentGatewayTransaction,
    PaymentReconciliation,
    TaxRate,
    Settings,
)
from datetime import datetime, date, timedelta
from sqlalchemy import func, or_
from config import Config


class ProductService:
    @staticmethod
    def get_all_products(page=1, per_page=50, search=None, category_id=None):
        query = Product.query.filter_by(is_active=True)
        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                    Product.barcode.ilike(f"%{search}%"),
                )
            )
        if category_id:
            query = query.filter_by(category_id=category_id)
        return query.order_by(Product.name).paginate(page=page, per_page=per_page)

    @staticmethod
    def get_product_by_id(product_id):
        return Product.query.get(product_id)

    @staticmethod
    def get_product_by_barcode(barcode):
        return Product.query.filter_by(barcode=barcode, is_active=True).first()

    @staticmethod
    def get_product_by_sku(sku):
        return Product.query.filter_by(sku=sku, is_active=True).first()

    @staticmethod
    def create_product(data):
        product = Product(
            sku=data.get("sku"),
            barcode=data.get("barcode"),
            name=data.get("name"),
            description=data.get("description"),
            category_id=data.get("category_id"),
            supplier_id=data.get("supplier_id"),
            unit_price=float(data.get("unit_price", 0)),
            cost_price=float(data.get("cost_price", 0)),
            reorder_level=int(data.get("reorder_level", 10)),
            is_controlled=data.get("is_controlled", False),
            requires_prescription=data.get("requires_prescription", False),
        )
        db.session.add(product)
        db.session.commit()
        return product

    @staticmethod
    def update_product(product_id, data):
        product = Product.query.get(product_id)
        if not product:
            return None
        for key, value in data.items():
            if hasattr(product, key):
                setattr(product, key, value)
        db.session.commit()
        return product

    @staticmethod
    def delete_product(product_id):
        product = Product.query.get(product_id)
        if product:
            product.is_active = False
            db.session.commit()
            return True
        return False

    @staticmethod
    def get_low_stock_products():
        products = Product.query.filter_by(is_active=True).all()
        low_stock = []
        for p in products:
            if p.get_total_stock() <= p.reorder_level:
                low_stock.append(
                    {
                        "id": p.id,
                        "name": p.name,
                        "sku": p.sku,
                        "current_stock": p.get_total_stock(),
                        "reorder_level": p.reorder_level,
                    }
                )
        return low_stock

    @staticmethod
    def get_expiring_inventory(days=30):
        expiry_date = date.today() + timedelta(days=days)
        batches = InventoryBatch.query.filter(
            InventoryBatch.expiry_date <= expiry_date, InventoryBatch.quantity > 0
        ).all()
        return [
            {
                "id": b.id,
                "product_id": b.product_id,
                "product_name": b.product.name,
                "batch_number": b.batch_number,
                "quantity": b.quantity,
                "expiry_date": b.expiry_date,
            }
            for b in batches
        ]


class CategoryService:
    @staticmethod
    def get_all_categories():
        return Category.query.filter_by(parent_id=None).all()

    @staticmethod
    def create_category(data):
        category = Category(
            name=data.get("name"),
            parent_id=data.get("parent_id"),
            description=data.get("description"),
        )
        db.session.add(category)
        db.session.commit()
        return category


class SupplierService:
    @staticmethod
    def get_all_suppliers():
        return Supplier.query.all()

    @staticmethod
    def create_supplier(data):
        supplier = Supplier(
            name=data.get("name"),
            contact_name=data.get("contact_name"),
            phone=data.get("phone"),
            email=data.get("email"),
            address=data.get("address"),
        )
        db.session.add(supplier)
        db.session.commit()
        return supplier


class CustomerService:
    @staticmethod
    def get_all_customers(page=1, per_page=50, search=None):
        query = Customer.query
        if search:
            query = query.filter(
                or_(
                    Customer.name.ilike(f"%{search}%"),
                    Customer.phone.ilike(f"%{search}%"),
                    Customer.email.ilike(f"%{search}%"),
                )
            )
        return query.order_by(Customer.name).paginate(page=page, per_page=per_page)

    @staticmethod
    def get_customer_by_id(customer_id):
        return Customer.query.get(customer_id)

    @staticmethod
    def create_customer(data):
        customer = Customer(
            name=data.get("name"),
            email=data.get("email"),
            phone=data.get("phone"),
            dob=data.get("dob"),
            address=data.get("address"),
            insurance_provider=data.get("insurance_provider"),
            insurance_id=data.get("insurance_id"),
            allergy_notes=data.get("allergy_notes"),
            medical_conditions=data.get("medical_conditions"),
        )
        db.session.add(customer)
        db.session.commit()
        return customer

    @staticmethod
    def update_customer(customer_id, data):
        customer = Customer.query.get(customer_id)
        if not customer:
            return None
        for key, value in data.items():
            if hasattr(customer, key):
                setattr(customer, key, value)
        db.session.commit()
        return customer


class PrescriptionService:
    @staticmethod
    def get_all_prescriptions(page=1, per_page=50, status=None, customer_id=None):
        query = Prescription.query
        if status:
            query = query.filter_by(status=status)
        if customer_id:
            query = query.filter_by(customer_id=customer_id)
        return query.order_by(Prescription.created_at.desc()).paginate(
            page=page, per_page=per_page
        )

    @staticmethod
    def get_prescription_by_id(prescription_id):
        return Prescription.query.get(prescription_id)

    @staticmethod
    def create_prescription(data):
        prescription = Prescription(
            customer_id=data.get("customer_id"),
            prescriber_name=data.get("prescriber_name"),
            prescriber_license=data.get("prescriber_license"),
            drug_name=data.get("drug_name"),
            drug_ndc=data.get("drug_ndc"),
            quantity=data.get("quantity"),
            dosage=data.get("dosage"),
            instructions=data.get("instructions"),
            refills_allowed=int(data.get("refills_allowed", 0)),
            date_issued=data.get("date_issued"),
            expiry_date=data.get("expiry_date"),
        )
        db.session.add(prescription)
        db.session.commit()
        return prescription

    @staticmethod
    def update_prescription_status(prescription_id, status):
        prescription = Prescription.query.get(prescription_id)
        if not prescription:
            return None
        prescription.status = status
        if status == "picked_up":
            prescription.refills_used += 1
        db.session.commit()
        return prescription


class InventoryService:
    @staticmethod
    def add_stock(data):
        product = Product.query.get(data.get("product_id"))
        if not product:
            return None

        batch = InventoryBatch(
            product_id=product.id,
            batch_number=data.get("batch_number"),
            quantity=int(data.get("quantity", 0)),
            cost_per_unit=float(data.get("cost_per_unit", product.cost_price)),
            expiry_date=data.get("expiry_date"),
            location=data.get("location"),
        )
        db.session.add(batch)
        db.session.commit()
        return batch

    @staticmethod
    def adjust_stock(product_id, quantity, reason, batch_id=None):
        product = Product.query.get(product_id)
        if not product:
            return None

        batch = None
        if batch_id:
            batch = InventoryBatch.query.get(batch_id)
        else:
            batch = (
                InventoryBatch.query.filter_by(product_id=product_id)
                .order_by(InventoryBatch.expiry_date)
                .first()
            )

        if batch:
            batch.quantity += quantity
        else:
            batch = InventoryBatch(
                product_id=product_id,
                quantity=quantity,
                cost_per_unit=product.cost_price,
                expiry_date=date.today() + timedelta(days=365),
            )
            db.session.add(batch)
        db.session.commit()
        return batch

    @staticmethod
    def get_inventory_summary():
        products = Product.query.filter_by(is_active=True).all()
        total_items = len(products)
        total_value = 0
        total_units = 0

        for p in products:
            stock = p.get_total_stock()
            total_units += stock
            total_value += stock * p.cost_price

        return {
            "total_items": total_items,
            "total_units": total_units,
            "total_value": total_value,
        }


class POSService:
    @staticmethod
    def create_transaction(data):
        customer_id = data.get("customer_id")
        user_id = data.get("user_id")
        items = data.get("items", [])
        discount_amount = float(data.get("discount_amount", 0))
        discount_type = data.get("discount_type", "fixed")  # "fixed" or "percentage"
        payment_method = data.get("payment_method", "cash")
        amount_paid = float(data.get("amount_paid", 0))
        prescription_id = data.get("prescription_id")

        if not items:
            return None, "No items in cart"

        transaction_number = f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        subtotal = 0
        transaction_items = []

        for item_data in items:
            product = Product.query.get(item_data.get("product_id"))
            if not product:
                continue

            quantity = int(item_data.get("quantity", 1))
            unit_price = float(item_data.get("unit_price", product.unit_price))
            discount = float(item_data.get("discount", 0))
            line_total = (unit_price * quantity) - discount

            subtotal += line_total

            batch = (
                InventoryBatch.query.filter_by(product_id=product.id)
                .order_by(InventoryBatch.expiry_date)
                .first()
            )
            if batch and batch.quantity >= quantity:
                batch.quantity -= quantity

            transaction_items.append(
                {
                    "product_id": product.id,
                    "batch_id": batch.id if batch else None,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount": discount,
                    "line_total": line_total,
                }
            )

        # Calculate discount based on type
        if discount_type == "percentage":
            calculated_discount = subtotal * (discount_amount / 100)
        else:
            calculated_discount = min(
                discount_amount, subtotal
            )  # Don't allow discount > subtotal

        taxable_subtotal = subtotal - calculated_discount
        tax_rate = BillingService.get_default_tax_rate()
        tax_amount = taxable_subtotal * tax_rate
        total = taxable_subtotal + tax_amount
        change_given = max(0, amount_paid - total)

        transaction = Transaction(
            transaction_number=transaction_number,
            customer_id=customer_id,
            user_id=user_id,
            prescription_id=prescription_id,
            subtotal=subtotal,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            total=total,
            payment_method=payment_method,
            amount_paid=amount_paid,
            change_given=change_given,
        )
        db.session.add(transaction)
        db.session.flush()

        for item_data in transaction_items:
            ti = TransactionItem(
                transaction_id=transaction.id,
                product_id=item_data["product_id"],
                batch_id=item_data["batch_id"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                discount=item_data["discount"],
                line_total=item_data["line_total"],
            )
            db.session.add(ti)

        if customer_id:
            customer = Customer.query.get(customer_id)
            if customer:
                points = int(total)
                customer.loyalty_points += points

        db.session.commit()
        return transaction, None

    @staticmethod
    def get_today_sales():
        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())

        transactions = Transaction.query.filter(
            Transaction.created_at >= start_of_day,
            Transaction.created_at <= end_of_day,
            Transaction.status == "completed",
        ).all()

        total_revenue = sum(t.total for t in transactions)
        transaction_count = len(transactions)

        return {"total_revenue": total_revenue, "transaction_count": transaction_count}

    @staticmethod
    def get_transaction_history(page=1, per_page=50, start_date=None, end_date=None):
        query = Transaction.query
        if start_date:
            query = query.filter(Transaction.created_at >= start_date)
        if end_date:
            query = query.filter(Transaction.created_at <= end_date)
        return query.order_by(Transaction.created_at.desc()).paginate(
            page=page, per_page=per_page
        )


class AuthService:
    @staticmethod
    def authenticate(username, password):
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password) and user.is_active:
            return user
        return None

    @staticmethod
    def create_user(data):
        user = User(
            username=data.get("username"),
            name=data.get("name"),
            role=data.get("role", "cashier"),
        )
        user.set_password(data.get("password", "password"))
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def get_current_user(user_id):
        return User.query.get(user_id)


class ReportService:
    @staticmethod
    def get_daily_report(report_date=None):
        if not report_date:
            report_date = date.today()

        start_of_day = datetime.combine(report_date, datetime.min.time())
        end_of_day = datetime.combine(report_date, datetime.max.time())

        transactions = Transaction.query.filter(
            Transaction.created_at >= start_of_day,
            Transaction.created_at <= end_of_day,
            Transaction.status == "completed",
        ).all()

        items_sold = {}
        for t in transactions:
            for item in t.items:
                product_name = item.product.name
                if product_name in items_sold:
                    items_sold[product_name]["quantity"] += item.quantity
                    items_sold[product_name]["total"] += item.line_total
                else:
                    items_sold[product_name] = {
                        "quantity": item.quantity,
                        "total": item.line_total,
                    }

        payment_methods = {}
        for t in transactions:
            pm = t.payment_method
            if pm in payment_methods:
                payment_methods[pm] += t.total
            else:
                payment_methods[pm] = t.total

        return {
            "report_date": report_date,
            "total_sales": len(transactions),
            "total_revenue": sum(t.total for t in transactions),
            "total_tax": sum(t.tax_amount for t in transactions),
            "total_discount": sum(t.discount_amount for t in transactions),
            "items_sold": items_sold,
            "payment_methods": payment_methods,
        }

    @staticmethod
    def get_inventory_report():
        products = Product.query.filter_by(is_active=True).all()
        inventory = []

        for p in products:
            stock = p.get_total_stock()
            value = stock * p.cost_price
            inventory.append(
                {
                    "sku": p.sku,
                    "name": p.name,
                    "category": p.category.name if p.category else "Uncategorized",
                    "stock": stock,
                    "cost_price": p.cost_price,
                    "unit_price": p.unit_price,
                    "value": value,
                    "status": "Low Stock" if stock <= p.reorder_level else "In Stock",
                }
            )

        return inventory


class BillingService:
    @staticmethod
    def get_tax_rates():
        return TaxRate.query.filter_by(is_active=True).all()

    @staticmethod
    def get_default_tax_rate():
        from models import Settings

        # First check settings for tax_rate
        tax_rate_setting = Settings.query.filter_by(key="tax_rate").first()
        if tax_rate_setting and tax_rate_setting.value:
            try:
                return float(tax_rate_setting.value)
            except ValueError:
                pass

        # Fallback to TaxRate model
        default = TaxRate.query.filter_by(is_default=True, is_active=True).first()
        if not default:
            default = TaxRate.query.filter_by(is_active=True).first()
        return default.rate / 100 if default else Config.TAX_RATE

    @staticmethod
    def create_invoice_from_transaction(transaction_id, due_days=30):
        """Create an invoice from a completed transaction"""
        from datetime import timedelta

        transaction = Transaction.query.get(transaction_id)
        if not transaction or not transaction.customer:
            return None, "Transaction not found or no customer"

        invoice_number = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Calculate due date
        due_date = (datetime.now() + timedelta(days=due_days)).date()

        invoice = Invoice(
            invoice_number=invoice_number,
            customer_id=transaction.customer_id,
            transaction_id=transaction.id,
            user_id=transaction.user_id,
            subtotal=transaction.subtotal,
            discount_amount=transaction.discount_amount,
            tax_amount=transaction.tax_amount,
            total=transaction.total,
            due_date=due_date,
            terms=f"Net {due_days} days",
            status="unpaid" if transaction.total > 0 else "paid",
        )

        db.session.add(invoice)
        db.session.flush()

        # Create invoice items from transaction items
        for item in transaction.items:
            invoice_item = InvoiceItem(
                invoice_id=invoice.id,
                product_id=item.product_id,
                description=item.product.name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount=item.discount,
                tax_rate=Config.TAX_RATE,
                line_total=item.line_total,
            )
            db.session.add(invoice_item)

        # Update customer balance if they have credit terms
        if transaction.customer.payment_terms != "cash" and transaction.total > 0:
            transaction.customer.current_balance += transaction.total

        db.session.commit()
        return invoice, None

    @staticmethod
    def get_customer_invoices(customer_id, status=None, page=1, per_page=50):
        query = Invoice.query.filter_by(customer_id=customer_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(Invoice.created_at.desc()).paginate(
            page=page, per_page=per_page
        )

    @staticmethod
    def get_overdue_invoices():
        today = date.today()
        return Invoice.query.filter(
            Invoice.due_date < today, Invoice.status.in_(["unpaid", "partial"])
        ).all()

    @staticmethod
    def record_payment(data):
        customer = Customer.query.get(data.get("customer_id"))
        if not customer:
            return None, "Customer not found"

        payment_number = f"PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        payment = Payment(
            payment_number=payment_number,
            customer_id=customer.id,
            invoice_id=data.get("invoice_id"),
            user_id=data.get("user_id"),
            amount=float(data.get("amount", 0)),
            payment_method=data.get("payment_method", "cash"),
            reference_number=data.get("reference_number"),
            notes=data.get("notes"),
        )

        db.session.add(payment)

        # Apply payment to invoice if specified
        if payment.invoice_id:
            invoice = Invoice.query.get(payment.invoice_id)
            if invoice:
                applied_amount = payment.apply_to_invoice(invoice)
                if applied_amount > 0:
                    customer.current_balance -= applied_amount
        else:
            # General payment - reduce customer balance
            customer.current_balance -= payment.amount

        db.session.commit()
        return payment, None

    @staticmethod
    def get_customer_statement(customer_id, start_date=None, end_date=None):
        """Generate customer statement showing invoices and payments"""
        customer = Customer.query.get(customer_id)
        if not customer:
            return None

        query = Invoice.query.filter_by(customer_id=customer_id)
        if start_date:
            query = query.filter(Invoice.created_at >= start_date)
        if end_date:
            query = query.filter(Invoice.created_at <= end_date)

        invoices = query.order_by(Invoice.created_at).all()

        payments_query = Payment.query.filter_by(customer_id=customer_id)
        if start_date:
            payments_query = payments_query.filter(Payment.payment_date >= start_date)
        if end_date:
            payments_query = payments_query.filter(Payment.payment_date <= end_date)

        payments = payments_query.order_by(Payment.payment_date).all()

        # Calculate running balance
        balance = 0
        statement_items = []

        # Add opening balance if needed
        if customer.current_balance != 0:
            statement_items.append(
                {
                    "date": date.today(),
                    "type": "opening_balance",
                    "description": "Opening Balance",
                    "amount": customer.current_balance,
                    "balance": customer.current_balance,
                }
            )

        # Add invoices
        for invoice in invoices:
            balance += invoice.total
            statement_items.append(
                {
                    "date": invoice.created_at.date(),
                    "type": "invoice",
                    "reference": invoice.invoice_number,
                    "description": f"Invoice {invoice.invoice_number}",
                    "amount": invoice.total,
                    "balance": balance,
                }
            )

        # Add payments
        for payment in payments:
            balance -= payment.amount
            statement_items.append(
                {
                    "date": payment.payment_date.date(),
                    "type": "payment",
                    "reference": payment.payment_number,
                    "description": f"Payment - {payment.payment_method}",
                    "amount": -payment.amount,
                    "balance": balance,
                }
            )

        return {
            "customer": customer,
            "statement_items": statement_items,
            "current_balance": customer.current_balance,
        }

    @staticmethod
    def calculate_invoice_totals(items, tax_rate=None):
        """Calculate totals for invoice items"""
        if tax_rate is None:
            tax_rate = BillingService.get_default_tax_rate()

        subtotal = 0
        total_discount = 0
        total_tax = 0

        for item in items:
            line_subtotal = item["unit_price"] * item["quantity"]
            line_discount = item.get("discount", 0)
            line_total_before_tax = line_subtotal - line_discount
            line_tax = line_total_before_tax * tax_rate

            subtotal += line_subtotal
            total_discount += line_discount
            total_tax += line_tax

        total = subtotal - total_discount + total_tax

        return {
            "subtotal": subtotal,
            "discount_amount": total_discount,
            "tax_amount": total_tax,
            "total": total,
        }


class InvoiceService:
    @staticmethod
    def generate_invoice_pdf(invoice_id):
        """Generate PDF invoice (placeholder - would need reportlab integration)"""
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return None

        # This would generate a PDF using reportlab
        # For now, return invoice data that can be used for PDF generation
        return {
            "invoice": invoice,
            "customer": invoice.customer,
            "items": invoice.items,
            "payments": invoice.payments,
            "balance_due": invoice.get_balance_due(),
        }

    @staticmethod
    def send_invoice_email(invoice_id):
        """Send invoice via email (placeholder)"""
        # Implementation would integrate with email service
        pass


class PaymentGatewayService:
    """Service for managing payment gateways and processing payments"""

    @staticmethod
    def get_active_gateways():
        """Get all active payment gateways"""
        return PaymentGateway.query.filter_by(is_active=True).all()

    @staticmethod
    def get_gateway_by_name(name, require_active=True):
        """Get gateway by name"""
        query = PaymentGateway.query.filter_by(name=name)
        if require_active:
            query = query.filter_by(is_active=True)
        return query.first()

    @staticmethod
    def test_connection(gateway):
        """Test connection to payment gateway"""
        try:
            config = gateway.get_config()
            if gateway.name == "mpesa":
                # Test M-Pesa connection
                return (
                    len(config.get("consumer_key", "")) > 0
                    and len(config.get("consumer_secret", "")) > 0
                )
            elif gateway.name == "stripe":
                # Test Stripe connection (basic check)
                return len(config.get("secret_key", "")) > 0
            elif gateway.name == "paypal":
                # Test PayPal connection (basic check)
                return (
                    len(config.get("client_id", "")) > 0
                    and len(config.get("client_secret", "")) > 0
                )
            elif gateway.name == "bank_transfer":
                # Bank transfer is always "connected"
                return True
            return False
        except Exception as e:
            print(f"Connection test failed for {gateway.name}: {e}")
            return False

    @staticmethod
    def create_gateway_transaction(payment_id, gateway_name, amount, currency="USD"):
        """Create a gateway transaction record"""
        gateway = PaymentGatewayService.get_gateway_by_name(gateway_name)
        if not gateway:
            return None

        payment = Payment.query.get(payment_id)
        if not payment:
            return None

        transaction = PaymentGatewayTransaction(
            payment_id=payment_id,
            gateway_id=gateway.id,
            amount=amount,
            currency=currency,
            reference_number=f"{payment.payment_number}-{gateway_name}",
        )

        db.session.add(transaction)
        db.session.commit()
        return transaction

    @staticmethod
    def process_cash_payment(data):
        """Process cash payment with change calculation"""
        payment = Payment.query.get(data.get("payment_id"))
        if not payment:
            return None, "Payment not found"

        amount_paid = float(data.get("amount_paid", 0))
        change = payment.calculate_change(amount_paid)

        payment.status = "completed"
        payment.reference_number = data.get(
            "reference_number", f"Cash-{payment.payment_number}"
        )
        payment.processed_at = datetime.utcnow()

        # Apply to invoice if specified
        if payment.invoice_id:
            invoice = Invoice.query.get(payment.invoice_id)
            if invoice:
                payment.apply_to_invoice(invoice)

        # Update customer balance for credit payments
        if payment.customer.payment_terms != "cash":
            payment.customer.current_balance -= payment.amount

        db.session.commit()
        return payment, None


class MpesaService:
    """M-Pesa payment gateway integration"""

    @staticmethod
    def get_gateway_config():
        """Get M-Pesa gateway configuration"""
        gateway = PaymentGateway.query.filter_by(name="mpesa", is_active=True).first()
        return gateway.get_config() if gateway else {}

    @staticmethod
    def initiate_stk_push(
        phone_number, amount, account_reference, transaction_desc="Payment"
    ):
        """Initiate M-Pesa STK Push"""
        import requests
        import base64
        import json

        config = MpesaService.get_gateway_config()
        if not config:
            return {"error": "M-Pesa not configured"}

        # Get access token
        auth = base64.b64encode(
            f"{config['consumer_key']}:{config['consumer_secret']}".encode()
        ).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

        token_response = requests.get(
            f"{config['base_url']}/oauth/v1/generate?grant_type=client_credentials",
            headers=headers,
        )

        if token_response.status_code != 200:
            return {"error": "Failed to get access token"}

        access_token = token_response.json().get("access_token")

        # Initiate STK Push
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f"{config['shortcode']}{config['passkey']}{timestamp}".encode()
        ).decode()

        payload = {
            "BusinessShortCode": config["shortcode"],
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone_number,
            "PartyB": config["shortcode"],
            "PhoneNumber": phone_number,
            "CallBackURL": config.get("callback_url", ""),
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc,
        }

        response = requests.post(
            f"{config['base_url']}/mpesa/stkpush/v1/processrequest",
            json=payload,
            headers=headers,
        )

        return response.json()

    @staticmethod
    def process_callback(callback_data):
        """Process M-Pesa callback"""
        try:
            data = json.loads(callback_data)
            stk_callback = data["Body"]["stkCallback"]
            result_code = stk_callback["ResultCode"]
            checkout_request_id = stk_callback.get("CheckoutRequestID")

            if result_code == 0:
                # Successful payment
                callback_metadata = stk_callback["CallbackMetadata"]["Item"]

                receipt_number = None
                amount = None
                phone_number = None

                for item in callback_metadata:
                    if item["Name"] == "MpesaReceiptNumber":
                        receipt_number = item["Value"]
                    elif item["Name"] == "TransactionDate":
                        transaction_date = item["Value"]
                    elif item["Name"] == "PhoneNumber":
                        phone_number = item["Value"]
                    elif item["Name"] == "Amount":
                        amount = item["Value"]

                # Find transaction by CheckoutRequestID (initial transaction_id)
                gateway_txn = PaymentGatewayTransaction.query.filter_by(
                    transaction_id=checkout_request_id
                ).first()

                if gateway_txn:
                    # Update transaction with final details
                    original_txn_id = gateway_txn.transaction_id  # CheckoutRequestID
                    gateway_txn.transaction_id = (
                        receipt_number  # Update to receipt number
                    )
                    gateway_txn.update_status("completed", callback_data)
                    gateway_txn.callback_received_at = datetime.utcnow()
                    db.session.commit()

                    return {"status": "success", "transaction_id": receipt_number}

            return {"status": "failed", "result_code": result_code}

        except Exception as e:
            return {"status": "error", "message": str(e)}


class StripeService:
    """Stripe payment gateway integration"""

    @staticmethod
    def get_gateway_config():
        """Get Stripe gateway configuration"""
        gateway = PaymentGateway.query.filter_by(name="stripe", is_active=True).first()
        return gateway.get_config() if gateway else {}

    @staticmethod
    def create_payment_intent(amount, currency="usd", metadata=None):
        """Create Stripe payment intent"""
        import stripe

        config = StripeService.get_gateway_config()
        if not config:
            return {"error": "Stripe not configured"}

        stripe.api_key = config["secret_key"]

        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency,
                metadata=metadata or {},
                payment_method_types=["card"],
            )

            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "status": intent.status,
            }

        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def confirm_payment(payment_intent_id):
        """Confirm payment intent"""
        import stripe

        config = StripeService.get_gateway_config()
        if not config:
            return {"error": "Stripe not configured"}

        stripe.api_key = config["secret_key"]

        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if intent.status == "succeeded":
                # Find and update our transaction
                gateway_txn = PaymentGatewayTransaction.query.filter_by(
                    transaction_id=payment_intent_id
                ).first()

                if gateway_txn:
                    gateway_txn.update_status("completed", intent)
                    db.session.commit()

                return {"status": "success", "amount": intent.amount / 100}

            return {"status": intent.status}

        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def process_webhook(payload, signature):
        """Process Stripe webhook"""
        import stripe

        config = StripeService.get_gateway_config()
        if not config:
            return {"error": "Stripe not configured"}

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, config["webhook_secret"]
            )

            if event.type == "payment_intent.succeeded":
                payment_intent = event.data.object

                # Find and update transaction
                gateway_txn = PaymentGatewayTransaction.query.filter_by(
                    transaction_id=payment_intent.id
                ).first()

                if gateway_txn:
                    gateway_txn.update_status("completed", payment_intent)
                    gateway_txn.callback_received_at = datetime.utcnow()
                    db.session.commit()

                return {"status": "processed"}

            return {"status": "ignored"}

        except Exception as e:
            return {"error": str(e)}


class PayPalService:
    """PayPal payment gateway integration"""

    @staticmethod
    def get_gateway_config():
        """Get PayPal gateway configuration"""
        gateway = PaymentGateway.query.filter_by(name="paypal", is_active=True).first()
        return gateway.get_config() if gateway else {}

    @staticmethod
    def get_access_token():
        """Get PayPal access token"""
        import requests
        import base64

        config = PayPalService.get_gateway_config()
        if not config:
            return None

        auth = base64.b64encode(
            f"{config['client_id']}:{config['client_secret']}".encode()
        ).decode()

        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {"grant_type": "client_credentials"}

        response = requests.post(
            f"{config['base_url']}/v1/oauth2/token", data=data, headers=headers
        )

        if response.status_code == 200:
            return response.json().get("access_token")
        return None

    @staticmethod
    def create_order(amount, currency="USD", return_url=None, cancel_url=None):
        """Create PayPal order"""
        import requests

        access_token = PayPalService.get_access_token()
        if not access_token:
            return {"error": "Failed to get access token"}

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        order_data = {
            "intent": "CAPTURE",
            "purchase_units": [
                {"amount": {"currency_code": currency, "value": f"{amount:.2f}"}}
            ],
            "application_context": {"return_url": return_url, "cancel_url": cancel_url},
        }

        response = requests.post(
            f"{PayPalService.get_gateway_config()['base_url']}/v2/checkout/orders",
            json=order_data,
            headers=headers,
        )

        return response.json()

    @staticmethod
    def capture_order(order_id):
        """Capture PayPal order"""
        import requests

        access_token = PayPalService.get_access_token()
        if not access_token:
            return {"error": "Failed to get access token"}

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            f"{PayPalService.get_gateway_config()['base_url']}/v2/checkout/orders/{order_id}/capture",
            headers=headers,
        )

        result = response.json()

        if response.status_code == 201:
            # Find and update transaction
            gateway_txn = PaymentGatewayTransaction.query.filter_by(
                transaction_id=order_id
            ).first()

            if gateway_txn:
                gateway_txn.update_status("completed", result)
                db.session.commit()

        return result


class BankTransferService:
    """Bank transfer payment processing"""

    @staticmethod
    def generate_payment_instructions(amount, currency="USD", reference=None):
        """Generate bank transfer instructions"""
        config = BankTransferService.get_gateway_config()
        if not config:
            return None

        instructions = {
            "bank_name": config.get("bank_name", "PharmaSuite Bank"),
            "account_name": config.get("account_name", "PharmaSuite Pharmacy"),
            "account_number": config.get("account_number", "1234567890"),
            "routing_number": config.get("routing_number", "123456789"),
            "swift_code": config.get("swift_code", "PHARXXX"),
            "amount": amount,
            "currency": currency,
            "reference": reference
            or f"Payment-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "instructions": config.get(
                "instructions",
                "Please include the reference number in your transfer description.",
            ),
        }

        return instructions

    @staticmethod
    def get_gateway_config():
        """Get bank transfer configuration"""
        gateway = PaymentGateway.query.filter_by(
            name="bank_transfer", is_active=True
        ).first()
        return gateway.get_config() if gateway else {}

    @staticmethod
    def record_bank_transfer(payment_id, transaction_id, amount):
        """Record a completed bank transfer"""
        payment = Payment.query.get(payment_id)
        if not payment:
            return False

        payment.status = "completed"
        payment.gateway_transaction_id = transaction_id
        payment.reference_number = transaction_id
        payment.processed_at = datetime.utcnow()

        # Apply to invoice if specified
        if payment.invoice_id:
            invoice = Invoice.query.get(payment.invoice_id)
            if invoice:
                payment.apply_to_invoice(invoice)

        # Update customer balance
        if payment.customer.payment_terms != "cash":
            payment.customer.current_balance -= payment.amount

        db.session.commit()
        return True


class ReconciliationService:
    """Payment reconciliation service"""

    @staticmethod
    def reconcile_gateway_transactions(gateway_name, start_date, end_date):
        """Reconcile transactions for a specific gateway"""
        gateway = PaymentGatewayService.get_gateway_by_name(gateway_name)
        if not gateway:
            return None

        # Get transactions for the period
        transactions = PaymentGatewayTransaction.query.filter(
            PaymentGatewayTransaction.gateway_id == gateway.id,
            PaymentGatewayTransaction.initiated_at >= start_date,
            PaymentGatewayTransaction.initiated_at <= end_date,
        ).all()

        total_count = len(transactions)
        total_amount = sum(t.amount for t in transactions)
        reconciled_count = len([t for t in transactions if t.status == "completed"])
        reconciled_amount = sum(
            t.amount for t in transactions if t.status == "completed"
        )

        # Create reconciliation record
        reconciliation = PaymentReconciliation(
            reconciliation_date=date.today(),
            gateway_id=gateway.id,
            total_transactions=total_count,
            total_amount=total_amount,
            reconciled_transactions=reconciled_count,
            reconciled_amount=reconciled_amount,
            discrepancies_found=total_count - reconciled_count,
            discrepancy_amount=total_amount - reconciled_amount,
            status="completed",
        )

        db.session.add(reconciliation)
        db.session.commit()

        return reconciliation

    @staticmethod
    def get_reconciliation_report(reconciliation_id):
        """Get detailed reconciliation report"""
        reconciliation = PaymentReconciliation.query.get(reconciliation_id)
        if not reconciliation:
            return None

        transactions = (
            PaymentGatewayTransaction.query.filter_by(
                gateway_id=reconciliation.gateway_id
            )
            .filter(
                PaymentGatewayTransaction.initiated_at
                >= reconciliation.reconciliation_date,
                PaymentGatewayTransaction.initiated_at
                < reconciliation.reconciliation_date + timedelta(days=1),
            )
            .all()
        )

        return {
            "reconciliation": reconciliation,
            "transactions": transactions,
            "summary": {
                "total_count": reconciliation.total_transactions,
                "reconciled_count": reconciliation.reconciled_transactions,
                "pending_count": reconciliation.total_transactions
                - reconciliation.reconciled_transactions,
                "total_amount": reconciliation.total_amount,
                "reconciled_amount": reconciliation.reconciled_amount,
                "pending_amount": reconciliation.total_amount
                - reconciliation.reconciled_amount,
            },
        }
