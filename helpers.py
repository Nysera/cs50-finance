import os
import re
import requests
import urllib.parse

from flask import session, redirect
from functools import wraps


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Contact API
    try:
        api_key = os.environ.get("API_KEY")
        url = f"https://cloud.iexapis.com/stable/stock/{urllib.parse.quote_plus(symbol)}/quote?token={api_key}"
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException:
        return None

    # Parse response
    try:
        quote = response.json()
        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError):
        return None


def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


def validate_username(username):
    pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9-_.]{3,15}$")

    if re.match(pattern, username):
        return True
    else:
        return False


def user(db, username):
    user_query = db.execute("SELECT username FROM users WHERE username = ?", username.lower())

    if user_query:
        return True
    else:
        return False


def validate_password(password):
    pattern = re.compile(r"^(?=.*?[A-Z])(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&*-]).{8,}$")

    if re.match(pattern, password):
        return True
    else:
        return False


def convert_to_int(value):
    if value:
        return int(value)
    else:
        return ""


def pluralize_word(value, word):
    if value > 1:
        return f"{word}s"
    else:
        return word