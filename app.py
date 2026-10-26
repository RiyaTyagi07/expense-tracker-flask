from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import calendar

app = Flask(__name__)

app.secret_key = "expense_tracker_secret_key"

DATABASE = "database.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


# =========================================================
# CREATE DATABASE
# =========================================================

def create_database():

    connection = get_db_connection()

    # ---------------- USERS TABLE ----------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # ---------------- EXPENSES TABLE ----------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ---------------- BUDGETS TABLE ----------------

    connection.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            month TEXT NOT NULL,
            amount REAL NOT NULL,
            UNIQUE(user_id, month),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    connection.commit()
    connection.close()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not name or not email or not password:
            return "All fields are required."

        hashed_password = generate_password_hash(password)

        connection = get_db_connection()

        try:

            connection.execute(
                """
                INSERT INTO users (name, email, password)
                VALUES (?, ?, ?)
                """,
                (name, email, hashed_password)
            )

            connection.commit()

        except sqlite3.IntegrityError:

            connection.close()

            return "Email already registered."

        connection.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()
        password = request.form["password"]

        connection = get_db_connection()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        connection.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("dashboard"))

        return "Invalid email or password."

    return render_template("login.html")


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    user_id = session["user_id"]

    # =====================================================
    # ALL EXPENSES
    # =====================================================

    expenses = connection.execute(
        """
        SELECT *
        FROM expenses
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
        """,
        (user_id,)
    ).fetchall()

    # =====================================================
    # TOTAL SPENDING
    # =====================================================

    total_expenses = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()[0]

    # =====================================================
    # TRANSACTION COUNT
    # =====================================================

    expense_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM expenses
        WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()[0]

    # =====================================================
    # CURRENT MONTH
    # =====================================================

    current_month = datetime.now().strftime("%Y-%m")

    current_month_expenses = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE user_id = ?
        AND strftime('%Y-%m', date) = ?
        """,
        (
            user_id,
            current_month
        )
    ).fetchone()[0]

    monthly_expenses = current_month_expenses

    # =====================================================
    # LAST MONTH
    # =====================================================

    current_year = datetime.now().year
    current_month_number = datetime.now().month

    if current_month_number == 1:

        last_month_year = current_year - 1
        last_month_number = 12

    else:

        last_month_year = current_year
        last_month_number = current_month_number - 1

    last_month = (
        f"{last_month_year}-"
        f"{last_month_number:02d}"
    )

    last_month_expenses = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE user_id = ?
        AND strftime('%Y-%m', date) = ?
        """,
        (
            user_id,
            last_month
        )
    ).fetchone()[0]

    # =====================================================
    # MONTHLY CHANGE
    # =====================================================

    if last_month_expenses > 0:

        spending_change = (
            (
                current_month_expenses
                - last_month_expenses
            )
            / last_month_expenses
        ) * 100

    elif current_month_expenses > 0:

        spending_change = 100

    else:

        spending_change = 0

    # =====================================================
    # DAILY AVERAGE
    # =====================================================

    current_day = datetime.now().day

    if current_day > 0:

        daily_average = (
            current_month_expenses
            / current_day
        )

    else:

        daily_average = 0

    # =====================================================
    # CATEGORY-WISE SPENDING
    # =====================================================

    category_data = connection.execute(
        """
        SELECT category, SUM(amount) AS total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY total DESC
        """,
        (user_id,)
    ).fetchall()

    categories = []
    category_totals = []

    for row in category_data:

        categories.append(row["category"])
        category_totals.append(row["total"])

    # =====================================================
    # CURRENT MONTH CATEGORY DATA
    # =====================================================

    monthly_category_data = connection.execute(
        """
        SELECT category, SUM(amount) AS total
        FROM expenses
        WHERE user_id = ?
        AND strftime('%Y-%m', date) = ?
        GROUP BY category
        ORDER BY total DESC
        """,
        (
            user_id,
            current_month
        )
    ).fetchall()

    # =====================================================
    # HIGHEST SPENDING CATEGORY
    # =====================================================

    if monthly_category_data:

        highest_category = (
            monthly_category_data[0]["category"]
        )

        highest_category_amount = (
            monthly_category_data[0]["total"]
        )

    else:

        highest_category = "No data"

        highest_category_amount = 0

    # =====================================================
    # MONTHLY TREND - LAST 6 MONTHS
    # =====================================================

    trend_labels = []
    trend_totals = []

    current_date = datetime.now()

    for i in range(5, -1, -1):

        month_number = current_date.month - i
        year = current_date.year

        while month_number <= 0:

            month_number += 12
            year -= 1

        month_value = f"{year}-{month_number:02d}"

        month_name = calendar.month_abbr[
            month_number
        ]

        month_total = connection.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE user_id = ?
            AND strftime('%Y-%m', date) = ?
            """,
            (
                user_id,
                month_value
            )
        ).fetchone()[0]

        trend_labels.append(
            f"{month_name} {str(year)[-2:]}"
        )

        trend_totals.append(
            month_total
        )

    # =====================================================
    # MONTHLY BUDGET
    # =====================================================

    budget_row = connection.execute(
        """
        SELECT amount
        FROM budgets
        WHERE user_id = ?
        AND month = ?
        """,
        (
            user_id,
            current_month
        )
    ).fetchone()

    if budget_row:

        monthly_budget = budget_row["amount"]

    else:

        monthly_budget = 0

    # =====================================================
    # REMAINING BUDGET
    # =====================================================

    budget_remaining = (
        monthly_budget
        - monthly_expenses
    )

    # =====================================================
    # BUDGET PERCENTAGE
    # =====================================================

    if monthly_budget > 0:

        budget_percentage = (
            monthly_expenses
            / monthly_budget
        ) * 100

    else:

        budget_percentage = 0

    progress_percentage = min(
        budget_percentage,
        100
    )

    # =====================================================
    # BUDGET STATUS
    # =====================================================

    if monthly_budget == 0:

        budget_status = "not_set"

    elif monthly_expenses > monthly_budget:

        budget_status = "exceeded"

    elif budget_percentage >= 80:

        budget_status = "warning"

    else:

        budget_status = "safe"

    # =====================================================
    # AUTOMATIC SPENDING INSIGHTS
    # =====================================================

    insights = []

    # Spending comparison insight

    if last_month_expenses > 0:

        if current_month_expenses > last_month_expenses:

            insights.append(
                f"Your spending increased by "
                f"{abs(spending_change):.1f}% "
                f"compared to last month."
            )

        elif current_month_expenses < last_month_expenses:

            insights.append(
                f"Your spending decreased by "
                f"{abs(spending_change):.1f}% "
                f"compared to last month."
            )

        else:

            insights.append(
                "Your spending is the same "
                "as last month."
            )

    elif current_month_expenses > 0:

        insights.append(
            "This is your first month "
            "with recorded spending."
        )

    else:

        insights.append(
            "No expenses recorded "
            "for this month yet."
        )

    # Highest category insight

    if highest_category != "No data":

        insights.append(
            f"{highest_category} is your "
            f"highest spending category "
            f"this month with "
            f"₹{highest_category_amount:,.2f}."
        )

    # Daily average insight

    if current_month_expenses > 0:

        insights.append(
            f"Your average daily spending "
            f"this month is "
            f"₹{daily_average:,.2f}."
        )

    # Budget insight

    if monthly_budget > 0:

        if monthly_expenses > monthly_budget:

            insights.append(
                f"You are ₹"
                f"{abs(budget_remaining):,.2f} "
                f"over your monthly budget."
            )

        else:

            insights.append(
                f"You have ₹"
                f"{budget_remaining:,.2f} "
                f"remaining from your monthly budget."
            )

    # =====================================================
    # CLOSE DATABASE
    # =====================================================

    connection.close()

    # =====================================================
    # SEND DATA TO DASHBOARD
    # =====================================================

    return render_template(
        "dashboard.html",

        expenses=expenses,

        total_expenses=total_expenses,

        expense_count=expense_count,

        monthly_expenses=monthly_expenses,

        categories=categories,

        category_totals=category_totals,

        monthly_budget=monthly_budget,

        budget_remaining=budget_remaining,

        budget_percentage=budget_percentage,

        progress_percentage=progress_percentage,

        budget_status=budget_status,

        current_month=current_month,

        last_month_expenses=last_month_expenses,

        spending_change=spending_change,

        daily_average=daily_average,

        highest_category=highest_category,

        highest_category_amount=highest_category_amount,

        trend_labels=trend_labels,

        trend_totals=trend_totals,

        insights=insights
    )


# =========================================================
# SET / UPDATE MONTHLY BUDGET
# =========================================================

@app.route("/set-budget", methods=["POST"])
def set_budget():

    if "user_id" not in session:
        return redirect(url_for("login"))

    budget_amount = request.form.get(
        "budget",
        ""
    ).strip()

    if not budget_amount:
        return redirect(url_for("dashboard"))

    try:

        budget_amount = float(
            budget_amount
        )

    except ValueError:

        return redirect(url_for("dashboard"))

    if budget_amount <= 0:
        return redirect(url_for("dashboard"))

    current_month = datetime.now().strftime(
        "%Y-%m"
    )

    connection = get_db_connection()

    existing_budget = connection.execute(
        """
        SELECT id
        FROM budgets
        WHERE user_id = ?
        AND month = ?
        """,
        (
            session["user_id"],
            current_month
        )
    ).fetchone()

    if existing_budget:

        connection.execute(
            """
            UPDATE budgets
            SET amount = ?
            WHERE user_id = ?
            AND month = ?
            """,
            (
                budget_amount,
                session["user_id"],
                current_month
            )
        )

    else:

        connection.execute(
            """
            INSERT INTO budgets
            (user_id, month, amount)
            VALUES (?, ?, ?)
            """,
            (
                session["user_id"],
                current_month,
                budget_amount
            )
        )

    connection.commit()
    connection.close()

    return redirect(url_for("dashboard"))


# =========================================================
# ADD EXPENSE
# =========================================================

@app.route("/add-expense", methods=["GET", "POST"])
def add_expense():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        title = request.form["title"].strip()
        amount = request.form["amount"]
        category = request.form["category"]
        date = request.form["date"]

        if not title or not amount or not category or not date:
            return "All fields are required."

        connection = get_db_connection()

        connection.execute(
            """
            INSERT INTO expenses
            (user_id, title, amount, category, date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                title,
                float(amount),
                category,
                date
            )
        )

        connection.commit()
        connection.close()

        return redirect(url_for("dashboard"))

    return render_template(
        "add_expense.html"
    )


# =========================================================
# EDIT EXPENSE
# =========================================================

@app.route(
    "/edit-expense/<int:expense_id>",
    methods=["GET", "POST"]
)
def edit_expense(expense_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    expense = connection.execute(
        """
        SELECT *
        FROM expenses
        WHERE id = ?
        AND user_id = ?
        """,
        (
            expense_id,
            session["user_id"]
        )
    ).fetchone()

    if not expense:

        connection.close()

        return "Expense not found."

    if request.method == "POST":

        title = request.form["title"].strip()
        amount = request.form["amount"]
        category = request.form["category"]
        date = request.form["date"]

        connection.execute(
            """
            UPDATE expenses
            SET
                title = ?,
                amount = ?,
                category = ?,
                date = ?
            WHERE id = ?
            AND user_id = ?
            """,
            (
                title,
                float(amount),
                category,
                date,
                expense_id,
                session["user_id"]
            )
        )

        connection.commit()
        connection.close()

        return redirect(url_for("dashboard"))

    connection.close()

    return render_template(
        "edit_expense.html",
        expense=expense
    )


# =========================================================
# DELETE EXPENSE
# =========================================================

@app.route(
    "/delete-expense/<int:expense_id>"
)
def delete_expense(expense_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    connection.execute(
        """
        DELETE FROM expenses
        WHERE id = ?
        AND user_id = ?
        """,
        (
            expense_id,
            session["user_id"]
        )
    )

    connection.commit()
    connection.close()

    return redirect(url_for("dashboard"))


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    create_database()

    app.run(debug=True)