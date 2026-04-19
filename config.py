import os


class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, "pharmacy.db")
    SECRET_KEY = os.environ.get("SECRET_KEY", "pharma-suite-2024-secret-key")

    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    TAX_RATE = 0.08
    CURRENCY = "KSH"
    CURRENCY_SYMBOL = "KSh"
    STORE_NAME = "PharmaSuite Pharmacy"
    STORE_ADDRESS = ""
    STORE_PHONE = ""

    LOW_STOCK_THRESHOLD = 10
    EXPIRY_WARNING_DAYS = 30

    ADMIN_USERNAME = "admin"
    ADMIN_PASSWORD = "admin123"
