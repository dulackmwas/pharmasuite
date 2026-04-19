# Pharmacy Management System - Specification Document

## 1. Project Overview

**Project Name:** PharmaSuite - Pharmacy Management System  
**Project Type:** Healthcare/Retail Desktop Application  
**Core Feature Summary:** A comprehensive pharmacy management system integrating point of sale, inventory control, prescription management, billing, and payment processing for retail pharmacies.  
**Target Users:** Pharmacy owners, pharmacists, pharmacy technicians, and cashiers.

---

## 2. UI/UX Specification

### 2.1 Layout Structure

**Multi-Window Model:**
- Main Window: Primary application interface with sidebar navigation
- Dialog Windows: Modal dialogs for confirmations, customer lookup, prescription details
- Floating Windows: Calculator, quick customer search (accessible from any screen)

**OS-Native Style Adaptation:**
- Use standard Windows window frame with native title bar controls
- System-aware theme integration (respects Windows dark/light mode)

**Major Layout Areas:**
```
┌─────────────────────────────────────────────────────────────┐
│  Header Bar: Logo | Module Title | Search | User Info       │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                  │
│  Sidebar │              Main Content Area                  │
│  Nav     │                                                  │
│          │                                                  │
│          ├──────────────────────────────────────────────────┤
│          │  Footer: Status Bar | Quick Actions             │
└──────────┴──────────────────────────────────────────────────┘
```

### 2.2 Visual Design

**Color Palette:**
- Primary: `#1E3A5F` (Deep Medical Blue)
- Secondary: `#2E7D32` (Pharmacy Green)
- Accent: `#FF6F00` (Alert Orange)
- Background: `#F5F7FA` (Light Gray)
- Surface: `#FFFFFF` (White)
- Text Primary: `#1A1A2E` (Near Black)
- Text Secondary: `#5C6B7A` (Gray)
- Success: `#4CAF50` (Green)
- Warning: `#FFC107` (Amber)
- Error: `#F44336` (Red)
- Info: `#2196F3` (Blue)

**Typography:**
- Font Family: "Segoe UI", system-ui, sans-serif
- Heading 1: 24px, SemiBold (600)
- Heading 2: 20px, SemiBold (600)
- Heading 3: 16px, Medium (500)
- Body: 14px, Regular (400)
- Small: 12px, Regular (400)
- Monospace (codes/numbers): "Consolas", monospace

**Spacing System:**
- Base Unit: 4px
- XS: 4px, SM: 8px, MD: 16px, LG: 24px, XL: 32px
- Component padding: 12px horizontal, 8px vertical
- Card padding: 16px
- Section spacing: 24px

**Visual Effects:**
- Card shadows: `0 2px 4px rgba(0,0,0,0.08)`
- Elevated shadows: `0 4px 12px rgba(0,0,0,0.12)`
- Border radius: 4px (buttons), 8px (cards), 12px (modals)
- Transitions: 150ms ease-in-out

### 2.3 Components

**Navigation Sidebar:**
- Width: 220px (collapsed: 60px)
- Items: Icon + Label, active state highlighted
- States: Default, Hover (`#E8EDF2`), Active (`#1E3A5F` with white text)

**Buttons:**
- Primary: `#1E3A5F` background, white text
- Secondary: White background, `#1E3A5F` border and text
- Danger: `#F44336` background, white text
- States: Default, Hover (darken 10%), Active (darken 15%), Disabled (50% opacity)

**Data Tables:**
- Striped rows: Alternating `#FFFFFF` / `#F8FAFC`
- Header: `#E8EDF2` background, bold text
- Hover row: `#E3F2FD`
- Selected row: `#BBDEFB`

**Form Inputs:**
- Height: 36px
- Border: 1px solid `#C5CAD3`
- Focus: 2px solid `#1E3A5F`
- Error: 1px solid `#F44336`

**Cards:**
- Background: White
- Border: 1px solid `#E8EDF2`
- Shadow: `0 2px 4px rgba(0,0,0,0.08)`
- Padding: 16px

**Badges/Tags:**
- Small rounded pills
- Status colors: Success (green), Warning (amber), Error (red), Info (blue)

---

## 3. Functional Specification

### 3.1 Core Features

#### 3.1.1 Dashboard
- Daily sales overview (count, revenue)
- Low stock alerts (items below reorder level)
- Pending prescriptions count
- Expiring medications (within 30 days)
- Quick action buttons: New Sale, Find Customer, Add Prescription

#### 3.1.2 Point of Sale (POS)
- Barcode/SKU input for quick item lookup
- Manual item search and addition
- Customer selection (optional for cash sales)
- Prescription linking for controlled substances
- Multiple payment methods (Cash, Card, Insurance, Mix)
- Automatic discount application (member discounts, promotions)
- Digital receipt generation (print/PDF)
- Sale suspension and recall
- Quick price override with manager approval

#### 3.1.3 Inventory Management
- Product catalog with drug database
- Batch and expiry tracking
- Stock levels with reorder alerts
- Supplier management
- Purchase orders generation
- Stock received logging
- Stock adjustment (with reason codes)
- Barcode/SKU management
- Category and location organization
- Drug interaction warnings database

#### 3.1.4 Customer/Patient Management
- Patient profile (name, contact, DOB, allergies, conditions)
- Prescription history
- Purchase history
- Insurance information
- Loyalty points tracking
- Notes and alerts

#### 3.1.5 Prescription Management
- New prescription entry
- Prescription validation (prescriber, drug, quantity)
- Refill tracking
- Controlled substance handling (DEA compliance)
- Prescription status (Pending, Ready, Picked Up, Cancelled)
- Expiry monitoring

#### 3.1.6 Billing & Invoicing
- Customer billing/invoicing
- Insurance claim preparation
- Itemized receipts
- Tax calculation
- Multi-currency support
- Payment tracking

#### 3.1.7 Payment Processing
- Cash handling (change calculation)
- Credit/Debit card processing
- Insurance billing
- Split payments
- Refund processing
- End-of-day reconciliation
- Payment reports

#### 3.1.8 Reports & Analytics
- Sales reports (daily, weekly, monthly)
- Inventory reports
- Profit margin analysis
- Top selling items
- Customer analytics
- Financial reports

#### 3.1.9 Settings & Administration
- Store configuration
- User management (roles: Admin, Pharmacist, Cashier)
- Tax rates
- Payment methods configuration
- Receipt templates
- Backup/Restore
- Audit logs

### 3.2 User Interactions and Flows

**New Sale Flow:**
1. Cashier logs in
2. Scan/enter items (or search)
3. Add customer (optional)
4. Apply discounts
5. Select payment method
6. Process payment
7. Print/email receipt
8. Record sale in system

**Prescription Fill Flow:**
1. Customer drops prescription
2. Enter/lookup patient
3. Enter prescription details
4. Verify prescriber and drug
5. Check inventory
6. Mark prescription as "Processing"
7. Fill and verify quantity
8. Notify customer
9. Record pickup

**Stock Receive Flow:**
1. Create/select purchase order
2. Scan received items
3. Verify quantities and batches
4. Confirm acceptance
5. Update inventory levels

### 3.3 Data Flow & Key Modules

**Database Schema (SQLite):**
- `products`: id, sku, barcode, name, description, category_id, unit_price, cost_price, reorder_level, supplier_id, is_controlled
- `categories`: id, name, parent_id
- `customers`: id, name, email, phone, dob, insurance_id, allergy_notes, loyalty_points, created_at
- `prescriptions`: id, customer_id, drug_name, prescriber, quantity, refills_allowed, refills_used, date_issued, expiry_date, status
- `transactions`: id, customer_id, user_id, total, discount, tax, payment_method, status, created_at
- `transaction_items`: id, transaction_id, product_id, quantity, unit_price, discount
- `inventory_batch`: id, product_id, batch_number, quantity, expiry_date, cost_per_unit
- `users`: id, username, password_hash, role, name, is_active
- `settings`: key, value

**Key Classes/Modules:**
- `Database`: Connection management, migrations
- `ProductService`: Product CRUD, search, inventory operations
- `CustomerService`: Customer management, lookup
- `POSService`: Sale processing, calculations
- `PrescriptionService`: Prescription workflow
- `PaymentService`: Payment processing
- `InventoryService`: Stock management, alerts
- `ReportService`: Report generation
- `AuthService`: User authentication

### 3.4 Edge Cases

- Network disconnected (offline mode for critical operations)
- Concurrent inventory updates
- Partial payments
- Returned prescriptions
- Expired prescription handling
- Insurance claim rejections
- System crash recovery (auto-save drafts)
- Duplicate barcode scans
- Negative inventory (blocked)
- Price override exceeding limit

---

## 4. Acceptance Criteria

### 4.1 Success Conditions

1. **POS Module:**
   - Can add items via barcode scan or manual entry
   - Calculate totals correctly with tax and discounts
   - Process cash and card payments
   - Generate digital receipts

2. **Inventory Module:**
   - Can add, edit, and view products
   - Track stock levels accurately
   - Alert on low stock
   - Track batch and expiry dates

3. **Customer Module:**
   - Can create and search customer records
   - View purchase history
   - Update customer information

4. **Prescription Module:**
   - Can enter new prescriptions
   - Track refill counts
   - Update prescription status

5. **Billing Module:**
   - Generate itemized invoices
   - Handle insurance billing preparation
   - Track payment status

6. **Reports Module:**
   - Generate daily sales report
   - Generate inventory report
   - Export to common formats

### 4.2 Visual Checkpoints

1. Dashboard displays all required summary cards
2. Sidebar navigation highlights active section
3. Data tables are sortable and filterable
4. Forms show validation errors clearly
5. Loading states are indicated
6. Confirmation dialogs appear for destructive actions
7. Print preview shows receipt correctly
8. Low stock alerts are visible on dashboard

---

## 5. Technical Stack

- **Backend:** Python 3.x with Flask
- **Database:** SQLite (development), PostgreSQL (production-ready)
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla)
- **PDF Generation:** ReportLab
- **Project Type:** Desktop application with web technologies (Electron-ready structure)