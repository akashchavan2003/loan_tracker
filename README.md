# Loan EMI Tracker

A premium, staff-facing Loan EMI Tracker and management system.
Admin users can log in, add members, disburse loans, automatically generate reducing-balance EMI schedules, track outstanding principal, and view/export reports.

## Live Deployment on Render

🚀 **Live App URL:** [https://loan-emi-tracker.onrender.com](https://loan-emi-tracker.onrender.com)
- **Demo Credentials:** 
  - **Username:** `admin`
  - **Password:** `admin123`

---

## Quick Start (Local Setup)

Follow these steps to run the application locally using Python 3:

```bash
# 1. Clone the repository
git clone https://github.com/akashchavan2003/loan_tracker.git
cd loan_tracker

# 2. Install dependencies
pip3 install -r requirements.txt

# 3. Apply database migrations (runs against the configured NeonDB)
python3 manage.py migrate

# 4. Load demo seed data (creates admin user, members, and active loans)
python3 manage.py seed_data

# 5. Start the local development server
python3 manage.py runserver

# 6. Open in your browser:
# http://localhost:8000
# Login with: admin / admin123
```

---

## Tech Stack & Architecture

| Layer | Technology | Rationale |
|---|---|---|
| **Backend** | Django 5.1 | Out-of-the-box secure authentication, powerful ORM, built-in admin dashboard, and rapid form validation. |
| **Frontend** | Django Templates + HTML5 + CSS3 + Vanilla JS | Monolithic architecture for rapid deployment, zero CORS issues, fast page loads, and simplified asset serving. |
| **Styling** | Vanilla CSS (Dark Theme, Glassmorphism) | Premium, highly responsive dark mode interface styled completely from scratch (no bloated UI frameworks). |
| **Database** | NeonDB (PostgreSQL) | Fully serverless, production-grade cloud database with connection pooling and SSL forced. |
| **Hosting** | Render | Automated deployments tied directly to GitHub using Gunicorn and Whitenoise. |

---

## Key Features

### 1. Core Requirements
*   **Django Authentication:** Secured views requiring login; credentials validated using PBKDF2 hash checking.
*   **Member Management:** Register members with Name, Employee ID, and Monthly Salary, with full server-side validation.
*   **Loan Creation:** Auto-calculates monthly EMI using the reducing-balance annuity formula and generates the full schedule.
*   **EMI Schedule Table:** Renders EMI number, due date, EMI amount, principal component, interest component, and the remaining outstanding principal.
*   **Interactive Payment Tracking:** Mark individual EMIs as paid, which immediately subtracts the principal component from the loan's outstanding balance.
*   **Member-wise Outstanding Report:** A risk-reporting view showing the total outstanding debt per member.
*   **CSV Export:** Streamed CSV downloads directly from the database query.
*   **Indian Rupee Formatting:** Custom filter formatting currency as `₹1,23,456` with Indian comma grouping.

### 2. Bonus Features Completed
*   **Early Foreclosure:** Instantly close active loans by calculating a one-time settlement amount: `Outstanding Principal + Current Month Interest`. All future interest is waived.
*   **Top-Up Gating:** Prevents member loans from being topped up or replaced until at least **33%** of the active loan's principal has been successfully repaid.
*   **Dynamic Search & Filtering:** Live filter pills on loans (All, Active, Closed, Foreclosed) and text-search on members.
*   **Live EMI Preview:** An interactive JavaScript calculator on the creation form showing real-time monthly EMI, total interest, and progress before submitting.

---

## The EMI Math & Reducing Balance

The app uses the standard amortization formula for a fixed-rate reducing-balance loan:

$$\text{EMI} = \frac{P \times r \times (1 + r)^n}{(1 + r)^n - 1}$$

Where:
*   $P$ = Principal loan amount
*   $r$ = Monthly interest rate ($\text{Annual Rate} \div 12 \div 100$)
*   $n$ = Tenure in months

### Reducing-Balance Concept
In a reducing-balance loan, interest is calculated each month only on the **remaining outstanding principal** rather than the original loan amount.
*   **Month 1:** Interest is high because the outstanding balance is high.
*   **Month 12:** Interest is low because prior repayments have cleared most of the principal.
*   Because the total monthly EMI remains constant, the principal component increases each month as the interest component shrinks.

### Precision and Rounding
To prevent floating-point rounding errors (e.g. `0.1 + 0.2 = 0.30000000000000004`), all mathematical operations use Python's **`Decimal`** module. On the final month's instalment, any accumulated rounding cents/paise are automatically absorbed into the final principal component, ensuring the loan outstanding hits exactly **`₹0`**.

---

## Running Unit Tests

A comprehensive suite of 15 unit tests validates the mathematical engine under `tracker/tests.py`.

To run tests:
```bash
python3 manage.py test tracker.tests -v 2
```

Tested scenarios:
1.  EMI formula mathematical correctness.
2.  Ensuring total principal components sum to the original principal.
3.  Verification that outstanding balance reduces to exactly ₹0 on completion.
4.  Verification of decreasing interest components and increasing principal components over time.
5.  Foreclosure calculation accuracy.
6.  1-month edge-case handling.

---

## AI Usage Disclosure

*   **AI (Gemini/Antigravity) was used for:** 
    - The entire Frontend layer (designing the CSS layout system, creating the dark theme/glassmorphism UI, writing the template structures, and the live JavaScript EMI calculator).
    - Initial boilerplate setup.
*   **Human Developer reviewed and wrote:**
    - The mathematical backend services (`services.py`).
    - The database schema, state transitions, and form validation (top-up gating logic).
    - The 15 unit tests verifying financial correctness.
