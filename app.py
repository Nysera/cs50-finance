import os

from flask import Flask, render_template, request, redirect, flash, session
from flask_session import Session
from cs50 import SQL
from helpers import login_required, lookup, usd, validate_username, user, validate_password, convert_to_int, pluralize_word
from werkzeug.security import generate_password_hash, check_password_hash

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    current_user = db.execute("SELECT * FROM users WHERE id = ?", session.get("user_id"))[0]
    stocks_query = db.execute("SELECT stock_symbol, price_per_stock, SUM(CASE WHEN transaction_type='buy' AND user_id = ? THEN stock_amount END) AS stock_brought, SUM(CASE WHEN transaction_type='sell' AND user_id = ? THEN stock_amount END) AS stock_sold FROM transactions GROUP BY stock_symbol", current_user.get("id"), current_user.get("id"))

    portfolio_stock_list = []
    portfolio_total_value = 0

    for stock in stocks_query:
        stock_dict = {}

        stock_symbol = stock.get("stock_symbol").upper()
        stock_lookup = lookup(stock_symbol)
        stock_name = stock_lookup.get("name")
        stocks_brought = stock.get("stock_brought")
        stocks_sold = stock.get("stock_sold")

        if stocks_brought == None:
            stocks_brought = 0

        if stocks_sold == None:
            stocks_sold = 0

        if stocks_sold == stocks_brought:
            continue

        stock_realtime_price = stock_lookup.get("price")
        stock_amount = stocks_brought - stocks_sold

        stock_dict.update({"stock_symbol": stock_symbol, "stock_name": stock_name, "stock_amount": stock_amount, "stock_realtime_price": stock_realtime_price})
        portfolio_stock_list.append(stock_dict)

        portfolio_total_value += stock_realtime_price * stock_amount

    user_account_balance = current_user.get("cash")

    return render_template("index.html", stocks = portfolio_stock_list, user_account_balance = user_account_balance, portfolio_total_value = portfolio_total_value, usd = usd)


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect("/")

    if request.method == "POST":
        username = request.form.get("username").lower()

        if not username or not validate_username(username):
            flash("Username must be at least 4 characters long.", "error")
            return redirect("/register")

        if user(db, username):
            flash("Username is already taken.", "error")
            return redirect("/register")

        password = request.form.get("password")
        confirm_password = request.form.get("confirmation")

        if not password or not validate_password(password):
            flash("Password doesn't meet the requirements.", "error")
            return redirect("/register")

        if confirm_password != password:
            flash("Confirm passwords doesn't match", "error")
            return redirect("/register")

        password_hash = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, password_hash)

        flash("Account has been created. Try logging in.", "success")
        return redirect("/login")

    else:
        return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect("/")

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = db.execute("SELECT * FROM users WHERE username = ?", username)

        if (user and check_password_hash(user[0].get("hash"), password)):
            session["user_id"] = user[0].get("id")
            return redirect("/")
        else:
            flash("Incorrect username or password.", "error")
            return redirect("/login")

    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        stock_symbol = request.form.get("stock-symbol")
        symbol_lookup = lookup(stock_symbol)

        if symbol_lookup == None:
            flash("Invalid stock symbol. Please try again.", "error")
            return redirect("/quote")

        name = symbol_lookup.get("name")
        price = symbol_lookup.get("price")
        symbol = symbol_lookup.get("symbol")

        return render_template("quote.html", name = name, price = price, symbol = symbol, stock_symbol = stock_symbol)

    else:
        return render_template("quote.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        current_user = db.execute("SELECT * FROM users WHERE id = ?", session.get("user_id"))[0]
        stock_symbol = request.form.get("stock-symbol").lower()

        if not stock_symbol or not lookup(stock_symbol):
            flash("Invalid stock symbol. Please try again.", "error")
            return redirect("/buy")

        stock_amount = convert_to_int(request.form.get("stock-amount"))

        if not stock_amount or stock_amount <= 0:
            flash("Invalid stock amount. Please try again.", "error")
            return render_template("buy.html", stock_symbol = stock_symbol)

        stock_price = lookup(stock_symbol).get("price")
        transaction_total = stock_price * stock_amount
        current_user_balance = current_user.get("cash")

        if transaction_total <= current_user_balance:
            db.execute("UPDATE users SET cash = ? WHERE id = ?", current_user_balance - transaction_total, current_user.get("id"))
            db.execute("INSERT INTO transactions (user_id, transaction_type, stock_amount, stock_symbol, price_per_stock) VALUES(?, ?, ?, ?, ?)", current_user.get("id"), "buy", stock_amount, stock_symbol, stock_price)

            message = f"{stock_amount} {pluralize_word(stock_amount, 'stock')} of {stock_symbol.upper()} has been added to your account."
            flash(message, "success")
            return redirect("/")

        else:
            flash("Your account balance is too low for this transaction.", "error")
            return redirect("/buy")

    else:
        return render_template("buy.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        current_user = db.execute("SELECT * FROM users WHERE id = ?", session.get("user_id"))[0]
        stock_symbol = request.form.get("stock-symbol").lower()

        user_stock_symbols_query = db.execute("SELECT DISTINCT stock_symbol FROM transactions WHERE transaction_type = 'buy' AND user_id = ?", current_user.get("id"))
        user_stock_symbols_list = []

        for symbol in user_stock_symbols_query:
            user_stock_symbols_list.append(symbol.get("stock_symbol"))

        if not stock_symbol or stock_symbol not in user_stock_symbols_list:
            flash("Stock symbol must be in your portfolio to sell.", "error")
            return redirect("/sell")

        stock_amount = convert_to_int(request.form.get("stock-amount"))
        current_user_stock_amount = db.execute("SELECT SUM(stock_amount) AS stock_amount FROM transactions WHERE transaction_type = 'buy' AND stock_symbol = ? AND user_id = ?", stock_symbol, current_user.get("id"))[0].get("stock_amount")

        if not stock_amount or stock_amount <= 0 or not stock_amount <= current_user_stock_amount:
            flash(f"Invalid stock amount. You have {current_user_stock_amount} {pluralize_word(stock_amount, 'stock')} of {stock_symbol.upper()} available to sell.", "error")
            return render_template("sell.html", stock_symbol = stock_symbol)


        current_stock_price = lookup(stock_symbol).get("price")
        db.execute("INSERT INTO transactions (user_id, transaction_type, stock_amount, stock_symbol, price_per_stock) VALUES(?, ?, ?, ?, ?)", current_user.get("id"), "sell", stock_amount, stock_symbol, current_stock_price)

        transaction_total = current_stock_price * stock_amount
        db.execute("UPDATE users SET cash = ? WHERE id = ?", current_user.get("cash") + transaction_total, current_user.get("id"))

        message = f"{stock_amount} {pluralize_word(stock_amount, 'stock')} of {stock_symbol.upper()} has been sold, {usd(transaction_total)} has been added to your account."
        flash(message, "success")
        return redirect("/")

    else:
        return render_template("sell.html")


@app.route("/history")
@login_required
def history():
    current_user = db.execute("SELECT * FROM users WHERE id = ?", session.get("user_id"))[0]
    transaction_query = db.execute("SELECT transaction_type, stock_amount, stock_symbol, price_per_stock, transaction_date FROM transactions WHERE user_id = ? GROUP BY transaction_date", current_user.get("id"))

    return render_template("history.html", transactions = transaction_query)