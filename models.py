from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"))
    role = db.relationship("Role", backref="users")
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def has_permission(self, permission):
        """Check if user has a specific permission"""
        # First check if user has admin role (full access)
        if self.role and self.role.name == "admin":
            return True

        if not self.role:
            return False

        # Check if role has the permission
        for perm in self.role.permissions:
            if perm.code == permission:
                return True

        return False

    def get_all_permissions(self):
        """Get all permissions for this user"""
        if self.role and self.role.name == "admin":
            return [p.code for p in Permission.query.all()]

        if not self.role:
            return []

        return [perm.code for perm in self.role.permissions]


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_system_role = db.Column(db.Boolean, default=False)  # Cannot be deleted
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    permissions = db.relationship(
        "Permission", secondary="role_permissions", overlaps="roles"
    )


class Permission(db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(
        db.String(50), default="general"
    )  # Group permissions by category
    is_system_permission = db.Column(db.Boolean, default=False)  # Cannot be deleted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    roles = db.relationship(
        "RolePermission", backref="permission", lazy=True, overlaps="permissions"
    )


class RolePermission(db.Model):
    __tablename__ = "role_permissions"

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    permission_id = db.Column(
        db.Integer, db.ForeignKey("permissions.id"), nullable=False
    )
    permission_code = db.Column(
        db.String(100), nullable=False
    )  # Denormalized for performance
    granted_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("role_id", "permission_id", name="unique_role_permission"),
    )

    user = db.relationship("User", backref="granted_permissions")


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    description = db.Column(db.String(200))

    products = db.relationship("Product", backref="category", lazy=True)
    children = db.relationship(
        "Category", backref=db.backref("parent", remote_side=[id])
    )


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship("Product", backref="supplier", lazy=True)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True)
    barcode = db.Column(db.String(50), unique=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"))
    unit_price = db.Column(db.Float, default=0)
    cost_price = db.Column(db.Float, default=0)
    reorder_level = db.Column(db.Integer, default=10)
    is_controlled = db.Column(db.Boolean, default=False)
    requires_prescription = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    inventory_items = db.relationship("InventoryBatch", backref="product", lazy=True)
    transaction_items = db.relationship("TransactionItem", backref="product", lazy=True)

    def get_total_stock(self):
        return sum(b.quantity for b in self.inventory_items if b.quantity > 0)


class InventoryBatch(db.Model):
    __tablename__ = "inventory_batch"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    batch_number = db.Column(db.String(50))
    quantity = db.Column(db.Integer, default=0)
    cost_per_unit = db.Column(db.Float)
    expiry_date = db.Column(db.Date)
    location = db.Column(db.String(50))
    received_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    dob = db.Column(db.Date)
    address = db.Column(db.Text)
    insurance_provider = db.Column(db.String(100))
    insurance_id = db.Column(db.String(50))
    allergy_notes = db.Column(db.Text)
    medical_conditions = db.Column(db.Text)
    loyalty_points = db.Column(db.Integer, default=0)
    credit_limit = db.Column(db.Float, default=0)
    current_balance = db.Column(db.Float, default=0)
    payment_terms = db.Column(
        db.String(50), default="cash"
    )  # cash, net_30, net_60, etc.
    billing_address = db.Column(db.Text)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    transactions = db.relationship("Transaction", backref="customer", lazy=True)
    prescriptions = db.relationship("Prescription", backref="customer", lazy=True)
    invoices = db.relationship("Invoice", backref="customer", lazy=True)
    payments = db.relationship("Payment", backref="customer", lazy=True)


class Prescription(db.Model):
    __tablename__ = "prescriptions"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    prescriber_name = db.Column(db.String(100))
    prescriber_license = db.Column(db.String(50))
    drug_name = db.Column(db.String(200), nullable=False)
    drug_ndc = db.Column(db.String(50))
    quantity = db.Column(db.Integer)
    dosage = db.Column(db.String(100))
    instructions = db.Column(db.Text)
    refills_allowed = db.Column(db.Integer, default=0)
    refills_used = db.Column(db.Integer, default=0)
    date_issued = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    transactions = db.relationship("Transaction", backref="prescription", lazy=True)


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    transaction_number = db.Column(db.String(50), unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"))
    prescription_id = db.Column(db.Integer, db.ForeignKey("prescriptions.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    subtotal = db.Column(db.Float, default=0)
    discount_amount = db.Column(db.Float, default=0)
    tax_amount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    payment_method = db.Column(db.String(20))
    amount_paid = db.Column(db.Float, default=0)
    change_given = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default="completed")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", backref="transactions")
    items = db.relationship(
        "TransactionItem",
        backref="transaction",
        lazy=True,
        cascade="all, delete-orphan",
    )


class TransactionItem(db.Model):
    __tablename__ = "transaction_items"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(
        db.Integer, db.ForeignKey("transactions.id"), nullable=False
    )
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey("inventory_batch.id"))
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    line_total = db.Column(db.Float, nullable=False)

    batch = db.relationship("InventoryBatch", backref="transaction_items")


class Invoice(db.Model):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    subtotal = db.Column(db.Float, default=0)
    discount_amount = db.Column(db.Float, default=0)
    tax_amount = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)

    status = db.Column(
        db.String(20), default="unpaid"
    )  # unpaid, paid, overdue, cancelled
    due_date = db.Column(db.Date)
    paid_date = db.Column(db.Date)

    notes = db.Column(db.Text)
    terms = db.Column(db.String(100))  # payment terms
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", backref="invoices")
    transaction = db.relationship("Transaction", backref="invoice")
    items = db.relationship(
        "InvoiceItem", backref="invoice", lazy=True, cascade="all, delete-orphan"
    )
    payments = db.relationship("Payment", backref="invoice", lazy=True)

    def get_balance_due(self):
        paid_amount = sum(p.amount for p in self.payments if p.status == "completed")
        return self.total - paid_amount

    def is_overdue(self):
        if self.status == "paid" or not self.due_date:
            return False
        return date.today() > self.due_date


class InvoiceItem(db.Model):
    __tablename__ = "invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))
    description = db.Column(db.String(200))
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    tax_rate = db.Column(db.Float, default=0)
    line_total = db.Column(db.Float, default=0)

    product = db.relationship("Product", backref="invoice_items")


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    payment_number = db.Column(db.String(50), unique=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(
        db.String(20)
    )  # cash, card, check, bank_transfer, credit, mpesa, stripe, paypal
    reference_number = db.Column(db.String(100))  # check number, transaction ID, etc.
    status = db.Column(
        db.String(20), default="pending"
    )  # pending, processing, completed, failed, refunded, cancelled

    gateway_transaction_id = db.Column(
        db.String(100)
    )  # Gateway-specific transaction ID
    gateway_name = db.Column(db.String(20))  # mpesa, stripe, paypal, bank_transfer
    gateway_response = db.Column(db.Text)  # Raw gateway response data

    change_given = db.Column(db.Float, default=0)  # For cash payments
    currency = db.Column(db.String(3), default="USD")

    notes = db.Column(db.Text)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", backref="payments")
    gateway_transactions = db.relationship(
        "PaymentGatewayTransaction", backref="payment", lazy=True
    )

    def apply_to_invoice(self, invoice):
        """Apply this payment to an invoice"""
        if self.status == "completed" and invoice:
            remaining_balance = invoice.get_balance_due()
            applied_amount = min(self.amount, remaining_balance)

            # Mark invoice as paid if fully paid
            if applied_amount >= remaining_balance:
                invoice.status = "paid"
                invoice.paid_date = self.payment_date.date()
            elif applied_amount > 0:
                invoice.status = "partial"

            db.session.commit()
            return applied_amount
        return 0

    def calculate_change(self, amount_paid):
        """Calculate change for cash payments"""
        if self.payment_method == "cash":
            self.change_given = max(0, amount_paid - self.amount)
            return self.change_given
        return 0


class PaymentGateway(db.Model):
    __tablename__ = "payment_gateways"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(
        db.String(50), unique=True, nullable=False
    )  # mpesa, stripe, paypal
    display_name = db.Column(db.String(100), nullable=False)
    gateway_type = db.Column(
        db.String(20), nullable=False
    )  # mobile_money, card, digital_wallet

    is_active = db.Column(db.Boolean, default=True)
    is_test_mode = db.Column(db.Boolean, default=True)

    # Gateway-specific configuration (stored as JSON)
    config = db.Column(db.Text)  # JSON string with API keys, endpoints, etc.

    # Fee structure
    processing_fee_fixed = db.Column(db.Float, default=0)
    processing_fee_percentage = db.Column(db.Float, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    transactions = db.relationship(
        "PaymentGatewayTransaction", backref="gateway", lazy=True
    )

    def get_config(self):
        """Get configuration as dictionary"""
        import json

        try:
            return json.loads(self.config or "{}")
        except:
            return {}

    def set_config(self, config_dict):
        """Set configuration from dictionary"""
        import json

        self.config = json.dumps(config_dict)


class PaymentGatewayTransaction(db.Model):
    __tablename__ = "payment_gateway_transactions"

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=False)
    gateway_id = db.Column(
        db.Integer, db.ForeignKey("payment_gateways.id"), nullable=False
    )

    transaction_id = db.Column(db.String(100), unique=True)  # Gateway transaction ID
    reference_number = db.Column(db.String(100))  # Our reference

    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default="USD")
    status = db.Column(
        db.String(20), default="pending"
    )  # pending, processing, completed, failed, cancelled, refunded

    gateway_response = db.Column(db.Text)  # Raw response from gateway
    gateway_request = db.Column(db.Text)  # Request sent to gateway

    callback_data = db.Column(db.Text)  # Webhook/callback data
    callback_received_at = db.Column(db.DateTime)

    processing_fee = db.Column(db.Float, default=0)
    exchange_rate = db.Column(db.Float, default=1.0)  # For currency conversion

    initiated_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def update_status(self, new_status, gateway_response=None):
        """Update transaction status and related payment"""
        self.status = new_status
        self.updated_at = datetime.utcnow()

        if gateway_response:
            self.gateway_response = str(gateway_response)

        if new_status == "completed" and not self.completed_at:
            self.completed_at = datetime.utcnow()
            # Update payment status
            if self.payment:
                self.payment.status = "completed"
                self.payment.processed_at = self.completed_at
                self.payment.gateway_transaction_id = self.transaction_id

        elif new_status == "failed":
            if self.payment:
                self.payment.status = "failed"

        db.session.commit()


class PaymentReconciliation(db.Model):
    __tablename__ = "payment_reconciliations"

    id = db.Column(db.Integer, primary_key=True)
    reconciliation_date = db.Column(db.Date, nullable=False)
    gateway_id = db.Column(db.Integer, db.ForeignKey("payment_gateways.id"))

    total_transactions = db.Column(db.Integer, default=0)
    total_amount = db.Column(db.Float, default=0)
    reconciled_transactions = db.Column(db.Integer, default=0)
    reconciled_amount = db.Column(db.Float, default=0)

    discrepancies_found = db.Column(db.Integer, default=0)
    discrepancy_amount = db.Column(db.Float, default=0)

    status = db.Column(
        db.String(20), default="pending"
    )  # pending, in_progress, completed, failed
    notes = db.Column(db.Text)

    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    gateway = db.relationship("PaymentGateway", backref="reconciliations")
    user = db.relationship("User", backref="reconciliations")


class TaxRate(db.Model):
    __tablename__ = "tax_rates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    rate = db.Column(db.Float, default=0)  # percentage (e.g., 8.5 for 8.5%)
    description = db.Column(db.String(200))
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Settings(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ReceiptTemplate(db.Model):
    __tablename__ = "receipt_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    template_type = db.Column(
        db.String(20), default="digital"
    )  # digital, thermal, email
    header_text = db.Column(db.Text)
    footer_text = db.Column(db.Text)
    show_logo = db.Column(db.Boolean, default=True)
    show_store_info = db.Column(db.Boolean, default=True)
    show_terms = db.Column(db.Boolean, default=True)
    custom_css = db.Column(db.Text)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="audit_logs")
