from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    send_file,
    send_from_directory,
    flash,
)
from datetime import datetime, date, timedelta
from functools import wraps
from config import Config
from models import (
    db,
    User,
    Role,
    Permission,
    RolePermission,
    Category,
    Supplier,
    Product,
    Customer,
    Prescription,
    Transaction,
    Invoice,
    InvoiceItem,
    Payment,
    PaymentGateway,
    PaymentGatewayTransaction,
    PaymentReconciliation,
    TaxRate,
    Settings,
    ReceiptTemplate,
)
from services import (
    ProductService,
    CategoryService,
    SupplierService,
    CustomerService,
    PrescriptionService,
    InventoryService,
    POSService,
    AuthService,
    ReportService,
    BillingService,
    InvoiceService,
    PaymentGatewayService,
    MpesaService,
    StripeService,
    PayPalService,
    BankTransferService,
    ReconciliationService,
)
import os
from werkzeug.utils import secure_filename
from PIL import Image
import uuid

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Create uploads directory after app is initialized
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Ensure upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2MB max file size


# Context processor to make settings available in all templates
@app.context_processor
def inject_settings():
    settings_dict = {s.key: s.value for s in Settings.query.all()}
    return {"global_settings": settings_dict}


# Currency filter for templates
@app.template_filter("currency")
def currency_filter(amount, symbol=None):
    if symbol is None:
        symbol = getattr(Config, "CURRENCY_SYMBOL", "KSh")
    try:
        return f"{symbol} {float(amount):,.2f}"
    except (ValueError, TypeError):
        return f"{symbol} {amount}"


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def permission_required(permission_code):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            user = User.query.get(session["user_id"])
            if not user or not user.has_permission(permission_code):
                flash(
                    f"You don't have permission to access this feature: {permission_code}",
                    "error",
                )
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)

        return decorated_function

    return decorator


@app.context_processor
def utility_processor():
    def has_permission(permission_code):
        if "user_id" not in session:
            return False
        user = User.query.get(session["user_id"])
        return user and user.has_permission(permission_code)

    def has_any_permission(*permission_codes):
        if "user_id" not in session:
            return False
        user = User.query.get(session["user_id"])
        if not user:
            return False
        return any(user.has_permission(code) for code in permission_codes)

    return dict(has_permission=has_permission, has_any_permission=has_any_permission)


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        selected_role = request.form.get("role", "cashier")

        user = AuthService.authenticate(username, password)
        if user:
            # Validate role matches (optional - for additional security)
            if user.role.name != selected_role:
                return render_template(
                    "login.html",
                    error=f"Access denied. You are logged in as {user.role.display_name}, but selected {selected_role.title()} role.",
                    selected_role=selected_role,
                )

            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role.name
            session["is_admin"] = user.role.name == "admin"
            user.last_login = datetime.utcnow()
            db.session.commit()

            # Success message for role-based feedback
            success_msg = (
                f"Welcome back, {user.name}! Logged in as {user.role.display_name}."
            )
            return render_template("login.html", success=success_msg, redirect=True)
        else:
            return render_template(
                "login.html",
                error="Invalid username or password. Please check your credentials.",
                selected_role=selected_role,
            )

    return render_template("login.html")


@app.route("/login/success")
@login_required
def login_success():
    """Handle successful login redirect"""
    return redirect(url_for("dashboard"))


@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    """Handle forgot password requests"""
    username = request.form.get("username")
    email = request.form.get("email")

    if not username and not email:
        return jsonify(
            {"status": "error", "message": "Please provide username or email"}
        ), 400

    # Find user
    user = None
    if username:
        user = User.query.filter_by(username=username).first()
    elif email:
        user = User.query.filter_by(email=email).first()

    if user:
        # In a real application, send email
        # For demo, just return success
        return jsonify(
            {
                "status": "success",
                "message": f"Password reset instructions sent to {user.email}",
                "email": user.email,
            }
        )
    else:
        return jsonify({"status": "error", "message": "User not found"}), 404


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    sales = POSService.get_today_sales()
    low_stock = ProductService.get_low_stock_products()
    expiring = ProductService.get_expiring_inventory()
    pending_prescriptions = Prescription.query.filter_by(status="pending").count()

    return render_template(
        "dashboard.html",
        sales=sales,
        low_stock=low_stock[:10],
        expiring=expiring[:10],
        pending_prescriptions=pending_prescriptions,
    )


@app.route("/pos")
@login_required
def pos():
    products = Product.query.filter_by(is_active=True).limit(100).all()
    customers = Customer.query.limit(50).all()

    # Get current tax rate from settings
    settings_dict = {s.key: s.value for s in Settings.query.all()}
    tax_rate = float(settings_dict.get("tax_rate", Config.TAX_RATE))

    return render_template(
        "pos.html", products=products, customers=customers, tax_rate=tax_rate
    )


@app.route("/pos/add-item", methods=["POST"])
@login_required
def pos_add_item():
    data = request.get_json()
    product = ProductService.get_product_by_barcode(data.get("barcode"))
    if not product:
        product = ProductService.get_product_by_id(data.get("product_id"))
    if not product:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(
        {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "barcode": product.barcode,
            "price": product.unit_price,
            "stock": product.get_total_stock(),
            "requires_prescription": product.requires_prescription,
        }
    )


@app.route("/pos/process-sale", methods=["POST"])
@login_required
def pos_process_sale():
    data = request.get_json()
    data["user_id"] = session["user_id"]

    transaction, error = POSService.create_transaction(data)
    if error:
        return jsonify({"error": error}), 400

    return jsonify(
        {
            "id": transaction.id,
            "transaction_number": transaction.transaction_number,
            "total": transaction.total,
            "change_given": transaction.change_given,
        }
    )


@app.route("/products")
@login_required
def products():
    search = request.args.get("search", "")
    category_id = request.args.get("category_id")
    page = request.args.get("page", 1, type=int)

    pagination = ProductService.get_all_products(
        page=page, search=search, category_id=category_id
    )
    categories = CategoryService.get_all_categories()

    return render_template(
        "products.html",
        products=pagination.items,
        categories=categories,
        pagination=pagination,
        search=search,
    )


@app.route("/products/add", methods=["GET", "POST"])
@login_required
def products_add():
    categories = CategoryService.get_all_categories()
    suppliers = SupplierService.get_all_suppliers()

    if request.method == "POST":
        data = request.form.to_dict()
        product = ProductService.create_product(data)
        return redirect(url_for("products"))

    return render_template(
        "products_form.html", product=None, categories=categories, suppliers=suppliers
    )


@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
def products_edit(product_id):
    product = ProductService.get_product_by_id(product_id)
    if not product:
        return "Product not found", 404

    categories = CategoryService.get_all_categories()
    suppliers = SupplierService.get_all_suppliers()

    if request.method == "POST":
        data = request.form.to_dict()
        ProductService.update_product(product_id, data)
        return redirect(url_for("products"))

    return render_template(
        "products_form.html",
        product=product,
        categories=categories,
        suppliers=suppliers,
    )


@app.route("/inventory")
@login_required
def inventory():
    inventory_summary = InventoryService.get_inventory_summary()
    products = Product.query.filter_by(is_active=True).limit(50).all()
    return render_template(
        "inventory.html", summary=inventory_summary, products=products
    )


@app.route("/inventory/add-stock", methods=["POST"])
@login_required
def inventory_add_stock():
    data = request.form.to_dict()
    if data.get("expiry_date"):
        data["expiry_date"] = datetime.strptime(data["expiry_date"], "%Y-%m-%d").date()
    InventoryService.add_stock(data)
    return redirect(url_for("inventory"))


@app.route("/customers")
@login_required
def customers():
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)

    pagination = CustomerService.get_all_customers(page=page, search=search)
    return render_template(
        "customers.html",
        customers=pagination.items,
        pagination=pagination,
        search=search,
    )


@app.route("/customers/add", methods=["GET", "POST"])
@login_required
def customers_add():
    if request.method == "POST":
        data = request.form.to_dict()
        if data.get("dob"):
            data["dob"] = datetime.strptime(data["dob"], "%Y-%m-%d").date()
        CustomerService.create_customer(data)
        return redirect(url_for("customers"))

    return render_template("customers_form.html", customer=None)


@app.route("/customers/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def customers_edit(customer_id):
    customer = CustomerService.get_customer_by_id(customer_id)
    if not customer:
        return "Customer not found", 404

    if request.method == "POST":
        data = request.form.to_dict()
        if data.get("dob"):
            data["dob"] = datetime.strptime(data["dob"], "%Y-%m-%d").date()
        CustomerService.update_customer(customer_id, data)
        return redirect(url_for("customers"))

    return render_template("customers_form.html", customer=customer)


@app.route("/customers/<int:customer_id>")
@login_required
def customers_view(customer_id):
    customer = CustomerService.get_customer_by_id(customer_id)
    if not customer:
        return "Customer not found", 404

    transactions = (
        Transaction.query.filter_by(customer_id=customer_id)
        .order_by(Transaction.created_at.desc())
        .limit(20)
        .all()
    )
    prescriptions = (
        Prescription.query.filter_by(customer_id=customer_id)
        .order_by(Prescription.created_at.desc())
        .all()
    )

    return render_template(
        "customers_view.html",
        customer=customer,
        transactions=transactions,
        prescriptions=prescriptions,
    )


@app.route("/prescriptions")
@login_required
def prescriptions():
    status = request.args.get("status")
    page = request.args.get("page", 1, type=int)

    pagination = PrescriptionService.get_all_prescriptions(page=page, status=status)
    return render_template(
        "prescriptions.html",
        prescriptions=pagination.items,
        pagination=pagination,
        current_status=status,
    )


@app.route("/prescriptions/add", methods=["GET", "POST"])
@login_required
def prescriptions_add():
    customers = Customer.query.all()

    if request.method == "POST":
        data = request.form.to_dict()
        if data.get("date_issued"):
            data["date_issued"] = datetime.strptime(
                data["date_issued"], "%Y-%m-%d"
            ).date()
        if data.get("expiry_date"):
            data["expiry_date"] = datetime.strptime(
                data["expiry_date"], "%Y-%m-%d"
            ).date()
        PrescriptionService.create_prescription(data)
        return redirect(url_for("prescriptions"))

    return render_template(
        "prescriptions_form.html", prescription=None, customers=customers
    )


@app.route("/prescriptions/<int:prescription_id>/update-status", methods=["POST"])
@login_required
def prescriptions_update_status(prescription_id):
    data = request.form.to_dict()
    status = data.get("status")
    PrescriptionService.update_prescription_status(prescription_id, status)
    return redirect(url_for("prescriptions"))


@app.route("/transactions")
@login_required
def transactions():
    page = request.args.get("page", 1, type=int)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if start_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
    if end_date:
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

    pagination = POSService.get_transaction_history(
        page=page, start_date=start_date, end_date=end_date
    )
    return render_template(
        "transactions.html", transactions=pagination.items, pagination=pagination
    )


@app.route("/transactions/<int:transaction_id>")
@login_required
def transactions_view(transaction_id):
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        return "Transaction not found", 404
    return render_template("transactions_view.html", transaction=transaction)


@app.route("/reports")
@login_required
def reports():
    report_date = request.args.get("date")
    if report_date:
        report_date = datetime.strptime(report_date, "%Y-%m-%d").date()
    else:
        report_date = date.today()

    daily_report = ReportService.get_daily_report(report_date)
    return render_template("reports.html", report=daily_report)


@app.route("/reports/inventory")
@login_required
def reports_inventory():
    inventory_report = ReportService.get_inventory_report()
    return render_template("reports_inventory.html", inventory=inventory_report)


@app.route("/suppliers")
@login_required
def suppliers():
    suppliers_list = SupplierService.get_all_suppliers()
    return render_template("suppliers.html", suppliers=suppliers_list)


@app.route("/suppliers/add", methods=["POST"])
@login_required
def suppliers_add():
    data = request.form.to_dict()
    SupplierService.create_supplier(data)
    return redirect(url_for("suppliers"))


@app.route("/categories")
@login_required
def categories():
    categories_list = CategoryService.get_all_categories()
    return render_template("categories.html", categories=categories_list)


@app.route("/categories/add", methods=["POST"])
@login_required
def categories_add():
    data = request.form.to_dict()
    CategoryService.create_category(data)
    return redirect(url_for("categories"))


@app.route("/users")
@login_required
def users():
    if not session.get("is_admin"):
        return "Access denied", 403
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("users.html", users=all_users)


@app.route("/users/add", methods=["GET", "POST"])
@login_required
def users_add():
    if not session.get("is_admin"):
        return "Access denied", 403
    if request.method == "POST":
        username = request.form.get("username")
        if User.query.filter_by(username=username).first():
            return render_template(
                "users_form.html", user=None, error="Username already exists"
            )
        role_name = request.form.get("role")
        role_obj = Role.query.filter_by(name=role_name).first()
        if not role_obj:
            return render_template(
                "users_form.html", user=None, error="Invalid role selected"
            )
        user = User(
            username=username,
            name=request.form.get("name"),
            email=request.form.get("email"),
            role=role_obj,
            is_active=request.form.get("is_active") == "on",
            created_by=session.get("user_id"),
        )
        user.set_password(request.form.get("password", "password"))
        db.session.add(user)
        db.session.commit()
        return redirect(url_for("users"))
    return render_template("users_form.html", user=None, error=None)


@app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def users_edit(user_id):
    if not session.get("is_admin"):
        return "Access denied", 403
    user = User.query.get(user_id)
    if not user:
        return "User not found", 404
    if request.method == "POST":
        role_name = request.form.get("role")
        role_obj = Role.query.filter_by(name=role_name).first()
        if not role_obj:
            return render_template(
                "users_form.html", user=user, error="Invalid role selected"
            )
        user.name = request.form.get("name")
        user.email = request.form.get("email")
        user.role = role_obj
        user.is_active = request.form.get("is_active") == "on"
        if request.form.get("password"):
            user.set_password(request.form.get("password"))
        db.session.commit()
        return redirect(url_for("users"))
    return render_template("users_form.html", user=user, error=None)


@app.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
def users_delete(user_id):
    if not session.get("is_admin"):
        return "Access denied", 403
    user = User.query.get(user_id)
    if user:
        user.is_active = False
        db.session.commit()
    return redirect(url_for("users"))


@app.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
def users_toggle(user_id):
    if not session.get("is_admin"):
        return "Access denied", 403
    user = User.query.get(user_id)
    if user:
        user.is_active = not user.is_active
        db.session.commit()
    return redirect(url_for("users"))


# Role and Permission Management Routes
@app.route("/roles")
@login_required
@permission_required("roles_view")
def roles():
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)

    query = Role.query
    if search:
        query = query.filter(
            Role.name.ilike(f"%{search}%") | Role.display_name.ilike(f"%{search}%")
        )

    pagination = query.order_by(Role.created_at.desc()).paginate(page=page, per_page=50)
    return render_template(
        "roles.html", roles=pagination.items, pagination=pagination, search=search
    )


@app.route("/roles/create", methods=["GET", "POST"])
@login_required
@permission_required("roles_manage")
def roles_create():

    if request.method == "POST":
        role_name = request.form.get("name").lower().replace(" ", "_")
        if Role.query.filter_by(name=role_name).first():
            return render_template(
                "roles_form.html", role=None, error="Role name already exists"
            )

        role = Role(
            name=role_name,
            display_name=request.form.get("display_name"),
            description=request.form.get("description"),
            is_system_role=False,
        )
        db.session.add(role)
        db.session.commit()

        # Assign permissions
        permission_ids = request.form.getlist("permissions")
        for perm_id in permission_ids:
            permission = Permission.query.get(int(perm_id))
            if permission:
                role_permission = RolePermission(
                    role_id=role.id,
                    permission_id=permission.id,
                    permission_code=permission.code,
                    granted_by=session["user_id"],
                )
                db.session.add(role_permission)
        db.session.commit()

        return redirect(url_for("roles"))

    permissions = Permission.query.order_by(Permission.category, Permission.name).all()
    return render_template(
        "roles_form.html", role=None, permissions=permissions, error=None
    )


@app.route("/roles/<int:role_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("roles_manage")
def roles_edit(role_id):
    role = Role.query.get(role_id)
    if not role:
        return "Role not found", 404

    if request.method == "POST":
        if not role.is_system_role:
            # Only allow editing display_name and description for non-system roles
            role.display_name = request.form.get("display_name")
            role.description = request.form.get("description")

        # Update permissions - remove all existing and add new ones
        RolePermission.query.filter_by(role_id=role.id).delete()

        permission_ids = request.form.getlist("permissions")
        for perm_id in permission_ids:
            permission = Permission.query.get(int(perm_id))
            if permission:
                role_permission = RolePermission(
                    role_id=role.id,
                    permission_id=permission.id,
                    permission_code=permission.code,
                    granted_by=session["user_id"],
                )
                db.session.add(role_permission)

        db.session.commit()

        # Update permissions - remove all existing and add new ones
        RolePermission.query.filter_by(role_id=role.id).delete()

        permission_ids = request.form.getlist("permissions")
        for perm_id in permission_ids:
            permission = Permission.query.get(int(perm_id))
            if permission:
                role_permission = RolePermission(
                    role_id=role.id,
                    permission_id=permission.id,
                    permission_code=permission.code,
                    granted_by=session["user_id"],
                )
                db.session.add(role_permission)
        db.session.commit()

        return redirect(url_for("roles"))

    permissions = Permission.query.order_by(Permission.category, Permission.name).all()
    return render_template(
        "roles_form.html",
        role=role,
        permissions=permissions,
    )


@app.route("/roles/<int:role_id>/delete", methods=["POST"])
@login_required
@permission_required("roles_manage")
def roles_delete(role_id):

    role = Role.query.get(role_id)
    if role and not role.is_system_role:
        # Check if role is in use
        if User.query.filter_by(role_id=role.id).first():
            return "Cannot delete role that is assigned to users", 400

        db.session.delete(role)
        db.session.commit()

    return redirect(url_for("roles"))


@app.route("/permissions")
@login_required
@permission_required("roles_view")
def permissions():
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)

    query = Permission.query
    if search:
        query = query.filter(
            Permission.name.ilike(f"%{search}%") | Permission.code.ilike(f"%{search}%")
        )

    pagination = query.order_by(Permission.category, Permission.name).paginate(
        page=page, per_page=50
    )
    return render_template(
        "permissions.html",
        permissions=pagination.items,
        pagination=pagination,
        search=search,
    )


@app.route("/permissions/create", methods=["GET", "POST"])
@login_required
@permission_required("roles_manage")
def permissions_create():

    if request.method == "POST":
        permission_code = request.form.get("code")
        if Permission.query.filter_by(code=permission_code).first():
            return render_template(
                "permissions_form.html",
                permission=None,
                error="Permission code already exists",
            )

        permission = Permission(
            code=permission_code,
            name=request.form.get("name"),
            description=request.form.get("description"),
            category=request.form.get("category", "general"),
            is_system_permission=False,
        )
        db.session.add(permission)
        db.session.commit()

        return redirect(url_for("permissions"))

    return render_template("permissions_form.html", permission=None, error=None)


@app.route("/permissions/<int:permission_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required("roles_manage")
def permissions_edit(permission_id):

    permission = Permission.query.get(permission_id)
    if not permission:
        return "Permission not found", 404

    if permission.is_system_permission:
        return "Cannot edit system permissions", 403

    if request.method == "POST":
        permission.name = request.form.get("name")
        permission.description = request.form.get("description")
        permission.category = request.form.get("category", "general")
        db.session.commit()

        return redirect(url_for("permissions"))

    return render_template("permissions_form.html", permission=permission)


@app.route("/permissions/<int:permission_id>/delete", methods=["POST"])
@login_required
@permission_required("roles_manage")
def permissions_delete(permission_id):

    permission = Permission.query.get(permission_id)
    if permission and not permission.is_system_permission:
        # Check if permission is in use
        if RolePermission.query.filter_by(permission_id=permission.id).first():
            return "Cannot delete permission that is assigned to roles", 400

        db.session.delete(permission)
        db.session.commit()

    return redirect(url_for("permissions"))


def initialize_default_permissions():
    """Initialize default permissions and roles"""
    with app.app_context():
        # Create default permissions
        default_permissions = [
            # POS & Sales
            {
                "code": "pos_access",
                "name": "Point of Sale Access",
                "category": "sales",
                "system": True,
            },
            {
                "code": "pos_create_sale",
                "name": "Create Sales",
                "category": "sales",
                "system": True,
            },
            {
                "code": "pos_apply_discount",
                "name": "Apply Discounts",
                "category": "sales",
                "system": True,
            },
            {
                "code": "pos_void_sale",
                "name": "Void Sales",
                "category": "sales",
                "system": False,
            },
            # Products & Inventory
            {
                "code": "products_view",
                "name": "View Products",
                "category": "inventory",
                "system": True,
            },
            {
                "code": "products_create",
                "name": "Create Products",
                "category": "inventory",
                "system": True,
            },
            {
                "code": "products_edit",
                "name": "Edit Products",
                "category": "inventory",
                "system": True,
            },
            {
                "code": "products_delete",
                "name": "Delete Products",
                "category": "inventory",
                "system": False,
            },
            {
                "code": "inventory_view",
                "name": "View Inventory",
                "category": "inventory",
                "system": True,
            },
            {
                "code": "inventory_adjust",
                "name": "Adjust Inventory",
                "category": "inventory",
                "system": True,
            },
            {
                "code": "inventory_receive",
                "name": "Receive Stock",
                "category": "inventory",
                "system": True,
            },
            # Customers
            {
                "code": "customers_view",
                "name": "View Customers",
                "category": "customers",
                "system": True,
            },
            {
                "code": "customers_create",
                "name": "Create Customers",
                "category": "customers",
                "system": True,
            },
            {
                "code": "customers_edit",
                "name": "Edit Customers",
                "category": "customers",
                "system": True,
            },
            {
                "code": "customers_delete",
                "name": "Delete Customers",
                "category": "customers",
                "system": False,
            },
            # Prescriptions
            {
                "code": "prescriptions_view",
                "name": "View Prescriptions",
                "category": "prescriptions",
                "system": True,
            },
            {
                "code": "prescriptions_create",
                "name": "Create Prescriptions",
                "category": "prescriptions",
                "system": True,
            },
            {
                "code": "prescriptions_edit",
                "name": "Edit Prescriptions",
                "category": "prescriptions",
                "system": True,
            },
            {
                "code": "prescriptions_fill",
                "name": "Fill Prescriptions",
                "category": "prescriptions",
                "system": True,
            },
            {
                "code": "prescriptions_verify",
                "name": "Verify Prescriptions",
                "category": "prescriptions",
                "system": True,
            },
            # Transactions & Billing
            {
                "code": "transactions_view",
                "name": "View Transactions",
                "category": "billing",
                "system": True,
            },
            {
                "code": "transactions_refund",
                "name": "Process Refunds",
                "category": "billing",
                "system": False,
            },
            {
                "code": "billing_view",
                "name": "View Billing",
                "category": "billing",
                "system": True,
            },
            {
                "code": "billing_create_invoice",
                "name": "Create Invoices",
                "category": "billing",
                "system": True,
            },
            {
                "code": "billing_manage_payments",
                "name": "Manage Payments",
                "category": "billing",
                "system": True,
            },
            # Reports
            {
                "code": "reports_view",
                "name": "View Reports",
                "category": "reports",
                "system": True,
            },
            {
                "code": "reports_sales",
                "name": "Sales Reports",
                "category": "reports",
                "system": True,
            },
            {
                "code": "reports_inventory",
                "name": "Inventory Reports",
                "category": "reports",
                "system": True,
            },
            {
                "code": "reports_financial",
                "name": "Financial Reports",
                "category": "reports",
                "system": False,
            },
            # Suppliers
            {
                "code": "suppliers_view",
                "name": "View Suppliers",
                "category": "suppliers",
                "system": True,
            },
            {
                "code": "suppliers_manage",
                "name": "Manage Suppliers",
                "category": "suppliers",
                "system": True,
            },
            # Settings & Configuration
            {
                "code": "settings_view",
                "name": "View Settings",
                "category": "administration",
                "system": True,
            },
            {
                "code": "settings_edit",
                "name": "Edit Settings",
                "category": "administration",
                "system": False,
            },
            # User Management
            {
                "code": "users_view",
                "name": "View Users",
                "category": "administration",
                "system": True,
            },
            {
                "code": "users_manage",
                "name": "Manage Users",
                "category": "administration",
                "system": False,
            },
            {
                "code": "roles_view",
                "name": "View Roles",
                "category": "administration",
                "system": True,
            },
            {
                "code": "roles_manage",
                "name": "Manage Roles",
                "category": "administration",
                "system": False,
            },
            # Payment Gateway Management
            {
                "code": "payments_view",
                "name": "View Payment Gateways",
                "category": "administration",
                "system": True,
            },
            {
                "code": "payments_manage",
                "name": "Manage Payment Gateways",
                "category": "administration",
                "system": False,
            },
        ]

        for perm_data in default_permissions:
            if not Permission.query.filter_by(code=perm_data["code"]).first():
                permission = Permission(
                    code=perm_data["code"],
                    name=perm_data["name"],
                    description=f"Permission to {perm_data['name'].lower()}",
                    category=perm_data["category"],
                    is_system_permission=perm_data["system"],
                )
                db.session.add(permission)

        # Create default roles
        default_roles = [
            {
                "name": "admin",
                "display_name": "Administrator",
                "description": "Full system access with all permissions",
                "system": True,
                "permissions": ["all"],  # Special case for admin
            },
            {
                "name": "pharmacist",
                "display_name": "Pharmacist",
                "description": "Clinical pharmacy operations and prescription management",
                "system": True,
                "permissions": [
                    "pos_access",
                    "pos_create_sale",
                    "pos_apply_discount",
                    "products_view",
                    "inventory_view",
                    "customers_view",
                    "customers_create",
                    "customers_edit",
                    "prescriptions_view",
                    "prescriptions_create",
                    "prescriptions_edit",
                    "prescriptions_fill",
                    "prescriptions_verify",
                    "transactions_view",
                    "billing_view",
                    "reports_view",
                    "reports_sales",
                ],
            },
            {
                "name": "cashier",
                "display_name": "Cashier",
                "description": "Point of sale operations and basic customer service",
                "system": True,
                "permissions": [
                    "pos_access",
                    "pos_create_sale",
                    "customers_view",
                    "customers_create",
                    "transactions_view",
                ],
            },
            {
                "name": "store_keeper",
                "display_name": "Store Keeper",
                "description": "Inventory management and stock control",
                "system": True,
                "permissions": [
                    "products_view",
                    "products_create",
                    "products_edit",
                    "inventory_view",
                    "inventory_adjust",
                    "inventory_receive",
                    "suppliers_view",
                    "suppliers_manage",
                    "reports_view",
                    "reports_inventory",
                ],
            },
        ]

        for role_data in default_roles:
            if not Role.query.filter_by(name=role_data["name"]).first():
                role = Role(
                    name=role_data["name"],
                    display_name=role_data["display_name"],
                    description=role_data["description"],
                    is_system_role=role_data["system"],
                )
                db.session.add(role)
                db.session.flush()  # Get role ID

                # Assign permissions
                if role_data["permissions"] == ["all"]:
                    # Admin gets all permissions
                    permissions = Permission.query.all()
                    for perm in permissions:
                        role_permission = RolePermission(
                            role_id=role.id,
                            permission_id=perm.id,
                            permission_code=perm.code,
                        )
                        db.session.add(role_permission)
                else:
                    for perm_code in role_data["permissions"]:
                        permission = Permission.query.filter_by(code=perm_code).first()
                        if permission:
                            role_permission = RolePermission(
                                role_id=role.id,
                                permission_id=permission.id,
                                permission_code=permission.code,
                            )
                            db.session.add(role_permission)

        db.session.commit()


with app.app_context():
    db.drop_all()
    db.create_all()
    initialize_default_permissions()
    if not User.query.filter_by(username="admin").first():
        # Get roles
        admin_role = Role.query.filter_by(name="admin").first()
        pharmacist_role = Role.query.filter_by(name="pharmacist").first()
        cashier_role = Role.query.filter_by(name="cashier").first()
        store_keeper_role = Role.query.filter_by(name="store_keeper").first()

        # Admin user
        admin = User(
            username="admin",
            name="Administrator",
            role=admin_role,
            email="admin@pharmacare.com",
        )
        admin.set_password("admin123")
        db.session.add(admin)

        # Pharmacist user
        pharmacist = User(
            username="pharmacist",
            name="Dr. Sarah Johnson",
            role=pharmacist_role,
            email="sarah@pharmacare.com",
        )
        pharmacist.set_password("password")
        db.session.add(pharmacist)

        # Cashier user
        cashier = User(
            username="cashier",
            name="John Smith",
            role=cashier_role,
            email="john@pharmacare.com",
        )
        cashier.set_password("password")
        db.session.add(cashier)

        # Store keeper user
        store_keeper = User(
            username="store_keeper",
            name="Mike Davis",
            role=store_keeper_role,
            email="mike@pharmacare.com",
        )
        store_keeper.set_password("password")
        db.session.add(store_keeper)

        db.session.commit()

        # Initialize default payment gateways
        if not PaymentGateway.query.first():
            gateways = [
                {
                    "name": "mpesa",
                    "display_name": "M-Pesa",
                    "gateway_type": "mobile_money",
                    "config": {
                        "consumer_key": "",
                        "consumer_secret": "",
                        "shortcode": "",
                        "passkey": "",
                        "base_url": "https://sandbox.safaricom.co.ke",
                        "callback_url": "",
                    },
                    "is_active": False,
                    "is_test_mode": True,
                    "processing_fee_fixed": 0,
                    "processing_fee_percentage": 0,
                },
                {
                    "name": "stripe",
                    "display_name": "Stripe",
                    "gateway_type": "credit_card",
                    "config": {
                        "publishable_key": "",
                        "secret_key": "",
                        "webhook_secret": "",
                    },
                    "is_active": False,
                    "is_test_mode": True,
                    "processing_fee_fixed": 0.30,
                    "processing_fee_percentage": 2.9,
                },
                {
                    "name": "paypal",
                    "display_name": "PayPal",
                    "gateway_type": "digital_wallet",
                    "config": {
                        "client_id": "",
                        "client_secret": "",
                        "base_url": "https://api-m.sandbox.paypal.com",
                    },
                    "is_active": False,
                    "is_test_mode": True,
                    "processing_fee_fixed": 0.49,
                    "processing_fee_percentage": 2.9,
                },
                {
                    "name": "bank_transfer",
                    "display_name": "Bank Transfer",
                    "gateway_type": "bank_transfer",
                    "config": {
                        "bank_name": "",
                        "account_name": "",
                        "account_number": "",
                        "routing_number": "",
                        "swift_code": "",
                        "currency": "USD",
                        "instructions": "Please transfer the amount to the account details provided and include your invoice number as reference.",
                    },
                    "is_active": False,
                    "is_test_mode": False,
                    "processing_fee_fixed": 0,
                    "processing_fee_percentage": 0,
                },
            ]

            for gateway_data in gateways:
                gateway = PaymentGateway(
                    name=gateway_data["name"],
                    display_name=gateway_data["display_name"],
                    gateway_type=gateway_data["gateway_type"],
                    config=str(gateway_data["config"]),
                    is_active=gateway_data["is_active"],
                    is_test_mode=gateway_data["is_test_mode"],
                    processing_fee_fixed=gateway_data["processing_fee_fixed"],
                    processing_fee_percentage=gateway_data["processing_fee_percentage"],
                )
                db.session.add(gateway)

            db.session.commit()


@app.route("/invoices")
@login_required
def invoices():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status")
    customer_id = request.args.get("customer_id")

    query = Invoice.query
    if status:
        query = query.filter_by(status=status)
    if customer_id:
        query = query.filter_by(customer_id=customer_id)

    pagination = query.order_by(Invoice.created_at.desc()).paginate(
        page=page, per_page=50
    )
    customers = Customer.query.filter(Customer.credit_limit > 0).all()

    return render_template(
        "invoices.html",
        invoices=pagination.items,
        pagination=pagination,
        customers=customers,
        current_status=status,
    )


@app.route("/invoices/create", methods=["GET", "POST"])
@login_required
def invoices_create():
    if request.method == "POST":
        transaction_id = request.form.get("transaction_id")
        customer_id = request.form.get("customer_id")
        due_days = int(request.form.get("due_days", 30))

        if transaction_id:
            invoice, error = BillingService.create_invoice_from_transaction(
                transaction_id, due_days
            )
            if error:
                return render_template("invoices_form.html", error=error)
            return redirect(url_for("invoices_view", invoice_id=invoice.id))

        # Manual invoice creation
        items = []
        item_count = int(request.form.get("item_count", 0))
        for i in range(item_count):
            if request.form.get(f"description_{i}"):
                items.append(
                    {
                        "description": request.form.get(f"description_{i}"),
                        "quantity": int(request.form.get(f"quantity_{i}", 1)),
                        "unit_price": float(request.form.get(f"unit_price_{i}", 0)),
                        "discount": float(request.form.get(f"discount_{i}", 0)),
                    }
                )

        totals = BillingService.calculate_invoice_totals(items)

        invoice_number = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        due_date = (datetime.now() + timedelta(days=due_days)).date()

        invoice = Invoice(
            invoice_number=invoice_number,
            customer_id=customer_id,
            user_id=session["user_id"],
            subtotal=totals["subtotal"],
            discount_amount=totals["discount_amount"],
            tax_amount=totals["tax_amount"],
            total=totals["total"],
            due_date=due_date,
            terms=f"Net {due_days} days",
            status="unpaid",
        )

        db.session.add(invoice)
        db.session.flush()

        for item in items:
            invoice_item = InvoiceItem(
                invoice_id=invoice.id,
                description=item["description"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                discount=item["discount"],
                line_total=(item["unit_price"] * item["quantity"]) - item["discount"],
            )
            db.session.add(invoice_item)

        db.session.commit()
        return redirect(url_for("invoices_view", invoice_id=invoice.id))

    transactions = (
        Transaction.query.filter(
            Transaction.customer_id.isnot(None), Transaction.status == "completed"
        )
        .order_by(Transaction.created_at.desc())
        .limit(50)
        .all()
    )

    customers = Customer.query.filter(Customer.credit_limit > 0).all()
    return render_template(
        "invoices_form.html", transactions=transactions, customers=customers
    )


@app.route("/invoices/<int:invoice_id>")
@login_required
def invoices_view(invoice_id):
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return "Invoice not found", 404

    return render_template("invoices_view.html", invoice=invoice)


@app.route("/invoices/<int:invoice_id>/pdf")
@login_required
def invoices_pdf(invoice_id):
    invoice_data = InvoiceService.generate_invoice_pdf(invoice_id)
    if not invoice_data:
        return "Invoice not found", 404

    # For now, return HTML view - would implement PDF generation
    return render_template("invoices_pdf.html", **invoice_data)


@app.route("/invoices/<int:invoice_id>/payment", methods=["POST"])
@login_required
def invoices_payment(invoice_id):
    invoice = Invoice.query.get(invoice_id)
    if not invoice:
        return "Invoice not found", 404

    data = request.form.to_dict()
    data["invoice_id"] = invoice_id
    data["customer_id"] = invoice.customer_id
    data["user_id"] = session["user_id"]

    payment, error = BillingService.record_payment(data)
    if error:
        return render_template("invoices_view.html", invoice=invoice, error=error)

    return redirect(url_for("invoices_view", invoice_id=invoice_id))


@app.route("/payments")
@login_required
def payments():
    page = request.args.get("page", 1, type=int)
    customer_id = request.args.get("customer_id")

    query = Payment.query
    if customer_id:
        query = query.filter_by(customer_id=customer_id)

    pagination = query.order_by(Payment.payment_date.desc()).paginate(
        page=page, per_page=50
    )
    customers = Customer.query.filter(Customer.credit_limit > 0).all()

    return render_template(
        "payments.html",
        payments=pagination.items,
        pagination=pagination,
        customers=customers,
    )


@app.route("/payments/record", methods=["GET", "POST"])
@login_required
def payments_record():
    if request.method == "POST":
        data = request.form.to_dict()
        data["user_id"] = session["user_id"]

        payment, error = BillingService.record_payment(data)
        if error:
            customers = Customer.query.filter(Customer.credit_limit > 0).all()
            invoices = Invoice.query.filter(
                Invoice.status.in_(["unpaid", "partial"])
            ).all()
            return render_template(
                "payments_form.html",
                customers=customers,
                invoices=invoices,
                error=error,
            )

        return redirect(url_for("payments"))

    customers = Customer.query.filter(Customer.credit_limit > 0).all()
    invoices = Invoice.query.filter(Invoice.status.in_(["unpaid", "partial"])).all()
    return render_template("payments_form.html", customers=customers, invoices=invoices)


@app.route("/customers/<int:customer_id>/statement")
@login_required
def customer_statement(customer_id):
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    if start_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
    if end_date:
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

    statement = BillingService.get_customer_statement(customer_id, start_date, end_date)
    if not statement:
        return "Customer not found", 404

    return render_template("customer_statement.html", **statement)


@app.route("/billing/dashboard")
@login_required
def billing_dashboard():
    overdue_invoices = BillingService.get_overdue_invoices()
    total_outstanding = sum(inv.get_balance_due() for inv in overdue_invoices)

    # Recent invoices
    recent_invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(10).all()

    # Recent payments
    recent_payments = (
        Payment.query.order_by(Payment.payment_date.desc()).limit(10).all()
    )

    # Customers with credit
    credit_customers = Customer.query.filter(Customer.credit_limit > 0).all()
    total_credit_used = sum(c.current_balance for c in credit_customers)

    return render_template(
        "billing_dashboard.html",
        overdue_invoices=overdue_invoices,
        total_outstanding=total_outstanding,
        recent_invoices=recent_invoices,
        recent_payments=recent_payments,
        credit_customers=credit_customers,
        total_credit_used=total_credit_used,
    )


@app.route("/tax-rates")
@login_required
def tax_rates():
    tax_rates_list = BillingService.get_tax_rates()
    return render_template("tax_rates.html", tax_rates=tax_rates_list)


@app.route("/tax-rates/add", methods=["POST"])
@login_required
def tax_rates_add():
    data = request.form.to_dict()
    tax_rate = TaxRate(
        name=data.get("name"),
        rate=float(data.get("rate", 0)),
        description=data.get("description"),
        is_default=data.get("is_default") == "on",
    )

    # If this is default, unset others
    if tax_rate.is_default:
        TaxRate.query.filter_by(is_default=True).update({"is_default": False})

    db.session.add(tax_rate)
    db.session.commit()
    return redirect(url_for("tax_rates"))


# Payment Gateway Routes
@app.route("/payment-gateways")
@login_required
@permission_required("payments_view")
def payment_gateways():
    gateways = PaymentGatewayService.get_active_gateways()
    return render_template("payment_gateways.html", gateways=gateways)


@app.route("/payment-gateways/configure/<gateway_name>", methods=["GET", "POST"])
@login_required
@permission_required("payments_manage")
def payment_gateways_configure(gateway_name):
    gateway = PaymentGatewayService.get_gateway_by_name(
        gateway_name, require_active=False
    )
    if not gateway:
        return "Gateway not found", 404

    if request.method == "POST":
        config = gateway.get_config()
        for key, value in request.form.items():
            if key.startswith("config_"):
                config_key = key[7:]  # Remove 'config_' prefix
                config[config_key] = value

        gateway.set_config(config)
        gateway.is_active = request.form.get("is_active") == "on"
        gateway.is_test_mode = request.form.get("is_test_mode") == "on"

        db.session.commit()
        return redirect(url_for("payment_gateways"))

    return render_template("payment_gateway_config.html", gateway=gateway)


@app.route("/payments/process/<gateway_name>", methods=["POST"])
@login_required
def payments_process_gateway(gateway_name):
    data = request.get_json()

    if gateway_name == "mpesa":
        phone_number = data.get("phone_number")
        amount = data.get("amount")
        account_ref = data.get("account_reference", "PharmaSuite")

        result = MpesaService.initiate_stk_push(phone_number, amount, account_ref)

        if "error" not in result:
            # Create payment and gateway transaction
            payment_data = {
                "customer_id": data.get("customer_id"),
                "amount": amount,
                "payment_method": "mpesa",
                "user_id": session["user_id"],
            }
            payment, error = BillingService.record_payment(payment_data)

            if payment:
                gateway_txn = PaymentGatewayService.create_gateway_transaction(
                    payment.id, "mpesa", amount
                )
                if gateway_txn:
                    gateway_txn.transaction_id = result.get("CheckoutRequestID")
                    db.session.commit()

                return jsonify(
                    {
                        "status": "success",
                        "payment_id": payment.id,
                        "gateway_response": result,
                    }
                )

        return jsonify(
            {
                "status": "error",
                "message": result.get("error", "Failed to initiate payment"),
            }
        )

    elif gateway_name == "stripe":
        amount = data.get("amount")
        metadata = data.get("metadata", {})

        result = StripeService.create_payment_intent(amount, metadata=metadata)

        if "error" not in result:
            # Create payment record
            payment_data = {
                "customer_id": data.get("customer_id"),
                "amount": amount,
                "payment_method": "stripe",
                "user_id": session["user_id"],
            }
            payment, error = BillingService.record_payment(payment_data)

            if payment:
                gateway_txn = PaymentGatewayService.create_gateway_transaction(
                    payment.id, "stripe", amount
                )
                if gateway_txn:
                    gateway_txn.transaction_id = result.get("payment_intent_id")
                    db.session.commit()

            return jsonify(
                {
                    "status": "success",
                    "client_secret": result["client_secret"],
                    "payment_id": payment.id if payment else None,
                }
            )

        return jsonify({"status": "error", "message": result["error"]})

    elif gateway_name == "paypal":
        amount = data.get("amount")
        return_url = data.get("return_url")
        cancel_url = data.get("cancel_url")

        result = PayPalService.create_order(
            amount, return_url=return_url, cancel_url=cancel_url
        )

        if "error" not in result:
            # Create payment record
            payment_data = {
                "customer_id": data.get("customer_id"),
                "amount": amount,
                "payment_method": "paypal",
                "user_id": session["user_id"],
            }
            payment, error = BillingService.record_payment(payment_data)

            if payment:
                gateway_txn = PaymentGatewayService.create_gateway_transaction(
                    payment.id, "paypal", amount
                )
                if gateway_txn:
                    gateway_txn.transaction_id = result["id"]
                    db.session.commit()

            return jsonify(
                {
                    "status": "success",
                    "order_id": result["id"],
                    "payment_id": payment.id if payment else None,
                    "approve_url": next(
                        link["href"]
                        for link in result["links"]
                        if link["rel"] == "approve"
                    ),
                }
            )

        return jsonify({"status": "error", "message": result["error"]})

    elif gateway_name == "bank_transfer":
        payment_data = {
            "customer_id": data.get("customer_id"),
            "amount": data.get("amount"),
            "payment_method": "bank_transfer",
            "user_id": session["user_id"],
            "status": "pending",
        }
        payment, error = BillingService.record_payment(payment_data)

        if payment:
            instructions = BankTransferService.generate_payment_instructions(
                data.get("amount"), reference=payment.payment_number
            )
            return jsonify(
                {
                    "status": "success",
                    "payment_id": payment.id,
                    "instructions": instructions,
                }
            )

        return jsonify({"status": "error", "message": error})

    return jsonify({"status": "error", "message": "Unsupported gateway"})


@app.route("/payments/cash", methods=["POST"])
@login_required
def payments_cash():
    data = request.get_json()

    # Create payment record first
    payment_data = {
        "customer_id": data.get("customer_id"),
        "amount": data.get("amount"),
        "payment_method": "cash",
        "user_id": session["user_id"],
    }
    payment, error = BillingService.record_payment(payment_data)

    if not payment:
        return jsonify({"status": "error", "message": error})

    # Process cash payment with change calculation
    cash_data = {
        "payment_id": payment.id,
        "amount_paid": data.get("amount_paid", payment.amount),
        "reference_number": data.get("reference_number"),
    }

    payment, error = PaymentGatewayService.process_cash_payment(cash_data)

    if payment:
        return jsonify(
            {
                "status": "success",
                "payment_id": payment.id,
                "change_given": payment.change_given,
                "transaction_number": payment.payment_number,
            }
        )

    return jsonify({"status": "error", "message": error})


# Webhook endpoints for payment gateways
@app.route("/webhooks/mpesa", methods=["POST"])
def webhook_mpesa():
    callback_data = request.get_data(as_text=True)
    result = MpesaService.process_callback(callback_data)

    if result.get("status") == "success":
        return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})
    else:
        return jsonify({"ResultCode": 1, "ResultDesc": "Failed"}), 400


@app.route("/webhooks/stripe", methods=["POST"])
def webhook_stripe():
    payload = request.get_data(as_text=True)
    signature = request.headers.get("stripe-signature")

    result = StripeService.process_webhook(payload, signature)

    if result.get("status") == "processed":
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": result.get("error")}), 400


@app.route("/api/payment-gateways/test", methods=["POST"])
@login_required
@permission_required("payments_view")
def payment_gateways_test():
    """Test connection to all active payment gateways"""
    results = {}
    gateways = PaymentGatewayService.get_active_gateways()

    for gateway in gateways:
        results[gateway.name] = PaymentGatewayService.test_connection(gateway)

    return jsonify(results)


@app.route("/api/payment-gateways/<gateway_name>/toggle", methods=["POST"])
@login_required
@permission_required("payments_manage")
def payment_gateways_toggle(gateway_name):
    """Toggle gateway active status"""
    gateway = PaymentGatewayService.get_gateway_by_name(gateway_name)
    if not gateway:
        return jsonify({"success": False, "message": "Gateway not found"}), 404

    gateway.is_active = not gateway.is_active
    db.session.commit()

    return jsonify(
        {
            "success": True,
            "message": f"Gateway {'activated' if gateway.is_active else 'deactivated'} successfully",
        }
    )


@app.route("/payments/paypal/capture/<order_id>", methods=["POST"])
@login_required
def payments_paypal_capture(order_id):
    result = PayPalService.capture_order(order_id)

    if "error" not in result:
        return jsonify(
            {
                "status": "success",
                "order_id": order_id,
                "capture_id": result["purchase_units"][0]["payments"]["captures"][0][
                    "id"
                ],
            }
        )

    return jsonify({"status": "error", "message": result["error"]})


@app.route("/reconciliation")
@login_required
def reconciliation():
    page = request.args.get("page", 1, type=int)
    reconciliations = PaymentReconciliation.query.order_by(
        PaymentReconciliation.created_at.desc()
    ).paginate(page=page, per_page=50)

    return render_template(
        "reconciliation.html",
        reconciliations=reconciliations.items,
        pagination=reconciliations,
    )


@app.route("/reconciliation/run", methods=["POST"])
@login_required
def reconciliation_run():
    gateway_name = request.form.get("gateway_name")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")

    if not all([gateway_name, start_date, end_date]):
        return "Missing required parameters", 400

    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    reconciliation = ReconciliationService.reconcile_gateway_transactions(
        gateway_name, start_date, end_date
    )

    if reconciliation:
        return redirect(url_for("reconciliation"))
    else:
        return "Reconciliation failed", 400


@app.route("/reconciliation/<int:reconciliation_id>")
@login_required
def reconciliation_view(reconciliation_id):
    report = ReconciliationService.get_reconciliation_report(reconciliation_id)
    if not report:
        return "Reconciliation not found", 404

    return render_template("reconciliation_report.html", **report)


# Receipt Management Routes
@app.route("/receipts")
@login_required
def receipts():
    templates = ReceiptTemplate.query.order_by(ReceiptTemplate.created_at.desc()).all()
    return render_template("receipts.html", templates=templates)


@app.route("/receipts/create", methods=["GET", "POST"])
@login_required
def receipts_create():
    if request.method == "POST":
        template = ReceiptTemplate(
            name=request.form.get("name"),
            template_type=request.form.get("template_type", "digital"),
            header_text=request.form.get("header_text", ""),
            footer_text=request.form.get("footer_text", ""),
            show_logo=request.form.get("show_logo") == "on",
            show_store_info=request.form.get("show_store_info") == "on",
            show_terms=request.form.get("show_terms") == "on",
            custom_css=request.form.get("custom_css", ""),
        )

        # Set as default if requested or if no default exists
        if (
            request.form.get("is_default") == "on"
            or not ReceiptTemplate.query.filter_by(is_default=True).first()
        ):
            ReceiptTemplate.query.filter_by(is_default=True).update(
                {"is_default": False}
            )
            template.is_default = True

        db.session.add(template)
        db.session.commit()

        return redirect(url_for("receipts"))

    return render_template("receipts_form.html", template=None)


@app.route("/receipts/<int:template_id>/edit", methods=["GET", "POST"])
@login_required
def receipts_edit(template_id):
    template = ReceiptTemplate.query.get(template_id)
    if not template:
        return "Template not found", 404

    if request.method == "POST":
        template.name = request.form.get("name")
        template.template_type = request.form.get("template_type", "digital")
        template.header_text = request.form.get("header_text", "")
        template.footer_text = request.form.get("footer_text", "")
        template.show_logo = request.form.get("show_logo") == "on"
        template.show_store_info = request.form.get("show_store_info") == "on"
        template.show_terms = request.form.get("show_terms") == "on"
        template.custom_css = request.form.get("custom_css", "")

        # Handle default setting
        if request.form.get("is_default") == "on" and not template.is_default:
            ReceiptTemplate.query.filter_by(is_default=True).update(
                {"is_default": False}
            )
            template.is_default = True
        elif request.form.get("is_default") != "on" and template.is_default:
            template.is_default = False
            # Ensure at least one template is default
            if not ReceiptTemplate.query.filter(
                ReceiptTemplate.id != template_id, ReceiptTemplate.is_default == True
            ).first():
                # Set the first template as default
                first_template = ReceiptTemplate.query.filter(
                    ReceiptTemplate.id != template_id
                ).first()
                if first_template:
                    first_template.is_default = True

        db.session.commit()
        return redirect(url_for("receipts"))

    return render_template("receipts_form.html", template=template)


@app.route("/receipts/<int:template_id>/preview")
@login_required
def receipts_preview(template_id):
    template = ReceiptTemplate.query.get(template_id)
    if not template:
        return "Template not found", 404

    # Generate sample receipt content
    sample_receipt = generate_sample_receipt(template)
    return sample_receipt


@app.route("/receipts/<int:template_id>/test-print")
@login_required
def receipts_test_print(template_id):
    template = ReceiptTemplate.query.get(template_id)
    if not template:
        return "Template not found", 404

    sample_receipt = generate_sample_receipt(template)
    return render_template(
        "receipt_print.html", receipt_content=sample_receipt, template=template
    )


@app.route("/receipts/<int:template_id>/set-default", methods=["POST"])
@login_required
def receipts_set_default(template_id):
    template = ReceiptTemplate.query.get(template_id)
    if not template:
        return jsonify({"success": False, "message": "Template not found"}), 404

    # Remove default from all templates
    ReceiptTemplate.query.filter_by(is_default=True).update({"is_default": False})

    # Set this template as default
    template.is_default = True
    db.session.commit()

    return jsonify({"success": True, "message": "Template set as default"})


@app.route("/thermal-printer/setup")
@login_required
def thermal_printer_setup():
    return render_template("thermal_printer_setup.html")


@app.route("/email/settings")
@login_required
def email_settings():
    return render_template("email_settings.html")


@app.route("/receipt/settings")
@login_required
def receipt_settings():
    return render_template("receipt_settings.html")


def generate_sample_receipt(template):
    """Generate a sample receipt for preview"""
    # Get settings from database since global_settings is not available here
    settings_dict = {s.key: s.value for s in Settings.query.all()}
    store_name = settings_dict.get("store_name", "PharmaSuite Pharmacy")
    store_address = settings_dict.get("store_address", "123 Main Street, City")
    store_phone = settings_dict.get("store_phone", "+254 700 000 000")
    receipt_terms = settings_dict.get("receipt_terms", "Thank you for your business!")
    tax_rate = float(settings_dict.get("tax_rate", Config.TAX_RATE))
    tax_percentage = int(tax_rate * 100)

    receipt_html = f"""
    <div style="font-family: monospace; font-size: 12px; max-width: 300px; margin: 0 auto;">
        <div style="text-align: center; margin-bottom: 10px;">
            {f'<img src="/static/uploads/{global_settings.get("store_logo")}" style="max-width: 100px; height: auto; margin-bottom: 5px;" alt="Logo"><br>' if template.show_logo and global_settings.get("store_logo") else ""}
            <strong>{store_name}</strong><br>
            {f"{store_address}<br>" if template.show_store_info else ""}
            {f"Phone: {store_phone}<br>" if template.show_store_info else ""}
            {"-" * 30}
        </div>

        {f'<div style="text-align: center; margin-bottom: 10px;">{template.header_text}</div>' if template.header_text else ""}

        <div style="margin-bottom: 10px;">
            <div>Transaction: TXN-20241201001</div>
            <div>Date: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
            <div>Cashier: Sample User</div>
        </div>

        <div style="border-top: 1px dashed #000; border-bottom: 1px dashed #000; padding: 5px 0; margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                <span>Paracetamol 500mg</span>
                <span>KSh 25.00</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                <span>Qty: 2</span>
                <span>KSh 50.00</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
                <span>Ibuprofen 200mg</span>
                <span>KSh 15.00</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span>Qty: 1</span>
                <span>KSh 15.00</span>
            </div>
        </div>

        <div style="margin-bottom: 10px;">
            <div style="display: flex; justify-content: space-between;">
                <span>Subtotal:</span>
                <span>KSh 65.00</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span>Tax ({tax_percentage}%):</span>
                <span>KSh {(65.00 * tax_rate):.2f}</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-weight: bold; border-top: 1px solid #000; padding-top: 3px;">
                <span>TOTAL:</span>
                <span>KSh {(65.00 + (65.00 * tax_rate)):.2f}</span>
            </div>
        </div>

        <div style="text-align: center; margin-bottom: 10px;">
            <div>Payment Method: Cash</div>
            <div>Amount Paid: KSh 100.00</div>
            <div>Change: KSh 29.80</div>
        </div>

        {f'<div style="text-align: center; margin-bottom: 10px; font-size: 10px;">{template.footer_text}</div>' if template.footer_text else ""}

        {f'<div style="text-align: center; margin-bottom: 10px; font-size: 10px; border-top: 1px dashed #000; padding-top: 5px;">{receipt_terms}</div>' if template.show_terms else ""}

        <div style="text-align: center; margin-top: 10px;">
            {"=" * 30}<br>
            END OF RECEIPT
        </div>
    </div>
    """

    return receipt_html


@app.route("/settings", methods=["GET", "POST"])
@login_required
@permission_required("settings_view")
def settings():
    if request.method == "POST":
        # Handle logo upload
        if "store_logo" in request.files:
            file = request.files["store_logo"]
            if file and file.filename != "" and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # Generate unique filename
                ext = filename.rsplit(".", 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{ext}"
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)

                # Resize and save image
                image = Image.open(file)
                # Resize to 200x200 maintaining aspect ratio
                image.thumbnail((200, 200), Image.Resampling.LANCZOS)
                image.save(file_path, quality=90)

                # Save logo filename to settings
                logo_setting = Settings.query.filter_by(key="store_logo").first()
                if logo_setting:
                    # Remove old logo file if exists
                    if logo_setting.value:
                        old_file_path = os.path.join(
                            app.config["UPLOAD_FOLDER"], logo_setting.value
                        )
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                    logo_setting.value = unique_filename
                else:
                    logo_setting = Settings(key="store_logo", value=unique_filename)
                    db.session.add(logo_setting)

        # Handle other form fields
        for key, value in request.form.items():
            if key != "store_logo":  # Skip file field
                setting = Settings.query.filter_by(key=key).first()
                if setting:
                    setting.value = value
                else:
                    setting = Settings(key=key, value=value)
                    db.session.add(setting)

        db.session.commit()
        return redirect(url_for("settings"))

    all_settings = {s.key: s.value for s in Settings.query.all()}
    return render_template("settings.html", settings=all_settings)


@app.route("/static/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
