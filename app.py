import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import calendar

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this")
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

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

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
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in all required fields.", "error")
            return render_template("register.html")

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
            flash("This email is already registered.", "error")
            return render_template("register.html")

        connection.close()
        flash("Account created successfully. Please sign in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "error")
            return render_template("login.html", email=email)

        connection = get_db_connection()

        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        connection.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            flash("You have logged in successfully.", "success")
            return redirect(url_for("dashboard"))

        flash(
            "Invalid email or password. Please check your details and try again.",
            "error"
        )
        return render_template("login.html", email=email)

    return render_template("login.html")


# =========================================================
# FORGOT PASSWORD
# LOCAL DEMO ONLY - NOT SAFE FOR PUBLIC DEPLOYMENT
# =========================================================

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not email or not new_password or not confirm_password:
            flash("Please fill in all fields.", "error")
            return render_template(
                "forgot_password.html",
                email=email
            )

        if len(new_password) < 8:
            flash(
                "Your new password must contain at least 8 characters.",
                "error"
            )
            return render_template(
                "forgot_password.html",
                email=email
            )

        if new_password != confirm_password:
            flash("The passwords do not match.", "error")
            return render_template(
                "forgot_password.html",
                email=email
            )

        connection = get_db_connection()

        user = connection.execute(
            "SELECT id FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if not user:
            connection.close()
            flash(
                "No account was found with that email address.",
                "error"
            )
            return render_template(
                "forgot_password.html",
                email=email
            )

        hashed_password = generate_password_hash(new_password)

        connection.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed_password, user["id"])
        )

        connection.commit()
        connection.close()

        flash(
            "Password updated successfully. Please sign in.",
            "success"
        )
        return redirect(url_for("login"))

    return render_template("forgot_password.html")


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    connection = get_db_connection()

    expenses = connection.execute(
        """
        SELECT * FROM expenses
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
        """,
        (user_id,)
    ).fetchall()

    total_expenses = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses WHERE user_id = ?
        """,
        (user_id,)
    ).fetchone()[0]

    expense_count = connection.execute(
        "SELECT COUNT(*) FROM expenses WHERE user_id = ?",
        (user_id,)
    ).fetchone()[0]

    current_date = datetime.now()
    current_month = current_date.strftime("%Y-%m")

    monthly_expenses = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE user_id = ?
        AND strftime('%Y-%m', date) = ?
        """,
        (user_id, current_month)
    ).fetchone()[0]

    if current_date.month == 1:
        last_month_year = current_date.year - 1
        last_month_number = 12
    else:
        last_month_year = current_date.year
        last_month_number = current_date.month - 1

    last_month = f"{last_month_year}-{last_month_number:02d}"

    last_month_expenses = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE user_id = ?
        AND strftime('%Y-%m', date) = ?
        """,
        (user_id, last_month)
    ).fetchone()[0]

    if last_month_expenses > 0:
        spending_change = (
            (monthly_expenses - last_month_expenses)
            / last_month_expenses
        ) * 100
    elif monthly_expenses > 0:
        spending_change = 100
    else:
        spending_change = 0

    daily_average = monthly_expenses / current_date.day

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

    categories = [row["category"] for row in category_data]
    category_totals = [row["total"] for row in category_data]

    monthly_category_data = connection.execute(
        """
        SELECT category, SUM(amount) AS total
        FROM expenses
        WHERE user_id = ?
        AND strftime('%Y-%m', date) = ?
        GROUP BY category
        ORDER BY total DESC
        """,
        (user_id, current_month)
    ).fetchall()

    if monthly_category_data:
        highest_category = monthly_category_data[0]["category"]
        highest_category_amount = monthly_category_data[0]["total"]
    else:
        highest_category = "No data"
        highest_category_amount = 0

    trend_labels = []
    trend_totals = []

    for i in range(5, -1, -1):
        month_number = current_date.month - i
        year = current_date.year

        while month_number <= 0:
            month_number += 12
            year -= 1

        month_value = f"{year}-{month_number:02d}"
        month_name = calendar.month_abbr[month_number]

        month_total = connection.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM expenses
            WHERE user_id = ?
            AND strftime('%Y-%m', date) = ?
            """,
            (user_id, month_value)
        ).fetchone()[0]

        trend_labels.append(f"{month_name} {str(year)[-2:]}")
        trend_totals.append(month_total)

    budget_row = connection.execute(
        """
        SELECT amount FROM budgets
        WHERE user_id = ? AND month = ?
        """,
        (user_id, current_month)
    ).fetchone()

    monthly_budget = budget_row["amount"] if budget_row else 0
    budget_remaining = monthly_budget - monthly_expenses

    if monthly_budget > 0:
        budget_percentage = (monthly_expenses / monthly_budget) * 100
    else:
        budget_percentage = 0

    progress_percentage = min(budget_percentage, 100)

    if monthly_budget == 0:
        budget_status = "not_set"
    elif monthly_expenses > monthly_budget:
        budget_status = "exceeded"
    elif budget_percentage >= 80:
        budget_status = "warning"
    else:
        budget_status = "safe"

    insights = []

    if last_month_expenses > 0:
        if monthly_expenses > last_month_expenses:
            insights.append(
                f"Your spending increased by {abs(spending_change):.1f}% "
                "compared to last month."
            )
        elif monthly_expenses < last_month_expenses:
            insights.append(
                f"Your spending decreased by {abs(spending_change):.1f}% "
                "compared to last month."
            )
        else:
            insights.append("Your spending is the same as last month.")
    elif monthly_expenses > 0:
        insights.append("This is your first month with recorded spending.")
    else:
        insights.append("No expenses recorded for this month yet.")

    if highest_category != "No data":
        insights.append(
            f"{highest_category} is your highest spending category "
            f"this month with ₹{highest_category_amount:,.2f}."
        )

    if monthly_expenses > 0:
        insights.append(
            f"Your average daily spending this month is ₹{daily_average:,.2f}."
        )

    if monthly_budget > 0:
        if monthly_expenses > monthly_budget:
            insights.append(
                f"You are ₹{abs(budget_remaining):,.2f} "
                "over your monthly budget."
            )
        else:
            insights.append(
                f"You have ₹{budget_remaining:,.2f} "
                "remaining from your monthly budget."
            )

    connection.close()

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

    budget_value = request.form.get("budget", "").strip()

    try:
        budget_amount = float(budget_value)
    except (ValueError, TypeError):
        flash("Please enter a valid budget amount.", "error")
        return redirect(url_for("dashboard"))

    if budget_amount <= 0:
        flash("Budget must be greater than zero.", "error")
        return redirect(url_for("dashboard"))

    current_month = datetime.now().strftime("%Y-%m")
    connection = get_db_connection()

    connection.execute(
        """
        INSERT INTO budgets (user_id, month, amount)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, month)
        DO UPDATE SET amount = excluded.amount
        """,
        (session["user_id"], current_month, budget_amount)
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
        title = request.form.get("title", "").strip()
        amount_value = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()

        if not title or not amount_value or not category or not date:
            flash("Please fill in all expense fields.", "error")
            return redirect(url_for("add_expense"))

        try:
            amount = float(amount_value)
            datetime.strptime(date, "%Y-%m-%d")
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("Enter a valid amount and date.", "error")
            return redirect(url_for("add_expense"))

        connection = get_db_connection()
        connection.execute(
            """
            INSERT INTO expenses (user_id, title, amount, category, date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session["user_id"], title, amount, category, date)
        )
        connection.commit()
        connection.close()

        return redirect(url_for("dashboard"))

    return render_template("add_expense.html")


# =========================================================
# EDIT EXPENSE
# =========================================================

@app.route("/edit-expense/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    expense = connection.execute(
        """
        SELECT * FROM expenses
        WHERE id = ? AND user_id = ?
        """,
        (expense_id, session["user_id"])
    ).fetchone()

    if not expense:
        connection.close()
        return "Expense not found.", 404

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        amount_value = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()

        try:
            amount = float(amount_value)
            datetime.strptime(date, "%Y-%m-%d")
            if not title or not category or amount <= 0:
                raise ValueError
        except (ValueError, TypeError):
            connection.close()
            flash("Please enter valid expense details.", "error")
            return redirect(url_for("edit_expense", expense_id=expense_id))

        connection.execute(
            """
            UPDATE expenses
            SET title = ?, amount = ?, category = ?, date = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                title, amount, category, date,
                expense_id, session["user_id"]
            )
        )

        connection.commit()
        connection.close()
        return redirect(url_for("dashboard"))

    connection.close()
    return render_template("edit_expense.html", expense=expense)


# =========================================================
# DELETE EXPENSE
# =========================================================

@app.route("/delete-expense/<int:expense_id>", methods=["GET", "POST"])
def delete_expense(expense_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    connection.execute(
        """
        DELETE FROM expenses
        WHERE id = ? AND user_id = ?
        """,
        (expense_id, session["user_id"])
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

create_database()

if __name__ == "__main__":
    app.run(debug=True)