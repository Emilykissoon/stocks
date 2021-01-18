import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL(os.getenv("DATABASE_URL"))

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows=db.execute("select symbol, sum(sell), sum(buy), sum(shares) from transactions where id=:id group by symbol order by symbol", id=session["user_id"])
    symbols = []
    names = []
    shares = []
    price = []
    total = []
    cash = []
    add=[]
    for r in rows:
        print(r)
    length=0
    for r in rows:
        if (r["symbol"]):
            s = r["symbol"]
            symbols.append(s)
            info = lookup(s)
            names.append(info["name"])
            price.append(info["price"])
            total.append(r["sum(shares)"]*info["price"])
            cash.append(r["sum(sell)"] + r["sum(buy)"])
            shares.append(r["sum(shares)"])
            length += 1

    add_cash=db.execute("select sell from transactions where (shares=0 and id=:id)", id=session["user_id"])
    add=0
    for a in add_cash:
        add += a['sell']
        print(a)

    print(total)

    tot=10000.00
    t = 0
    for c in cash:
        tot -= c
    tot += add
    for tl in total:
        t += tl
    t += tot
    db.execute("update users set cash=:tot where id=:id", tot=tot, id=session["user_id"])
    return render_template("index.html", length=length, symbols=symbols, names=names,
            shares= shares, price=price, total=total, tot=tot, t=t)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        symbol=lookup(request.form.get("symbol"))

        if not symbol:
            return render_template("apology.html", message="Please input valid symbol")

        shares=int(request.form.get("shares"))
        if shares < 1:
            return render_template("apology.html", message="Please enter positive integer")

        price=symbol["price"]*shares
        num=db.execute("select * from users where id=:id", id = session["user_id"])
        cash = num[0]["cash"]

        if (price > cash):
            return render_template("apology.html", message="You do not have enought cash")

        db.execute("insert into transactions (id, symbol, buy, shares) values (:id, :symbol, :buy, :shares)", id=session["user_id"],
                    symbol=symbol["symbol"], buy=price, shares=shares)

        return redirect("/")

    return render_template("buy.html")

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    if request.method=="POST":
        amount=int(request.form.get("cash"))
        if (amount < 1):
            return render_template("apology.html", message="Please enter positive integer")
        db.execute("insert into transactions (id, sell) values (:id, :amount)", id=session["user_id"], amount=amount)
        return redirect("/")
    return render_template("add.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows=db.execute("select * from transactions where id=:id order by time", id=session["user_id"])
    symbol=[]
    shares=[]
    price=[]
    transacted=[]
    for r in rows:
        symbol.append(r["symbol"])
        shares.append(r["shares"])
        price.append(r["buy"] + r["sell"])
        transacted.append(r["time"])

    return render_template("history.html", length=len(rows), symbol=symbol, shares=shares, price=price, transacted=transacted)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return render_template("apology.html", message="Must provide username")

        # Ensure password was submitted
        elif not request.form.get("password"):
            return render_template("apology.html", message="Must provide password")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return render_template("apology.html", message="Invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method=="POST":
        quote=request.form.get("quote")
        if not quote:
            return render_template("apology.html", message="Please provide symbol")
        s=lookup(quote)
        return render_template("symbol.html", name=s["name"], price=s["price"], symbol=s["symbol"])
    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()
    if request.method == "POST":

        exists = db.execute("select 1 from users where username=:username",
                    username=request.form.get("username"))
        # exists = 1

        if not request.form.get("username"):
            return render_template("apology.html", message="Must provide username")

        elif exists:
            return render_template("apology.html", message="Username already exists")

        elif not request.form.get("password1") or not request.form.get("password2"):
            return render_template("apology.html", message="Must provide password twice")

        elif request.form.get("password1") != request.form.get("password2"):
            return render_template("apology.html", message="Passwords do not match")

        else:
            db.execute("insert into users (username, hash) values (:username, :h)",
                        username=request.form.get("username"),
                        h = generate_password_hash(request.form.get("password1")))

            rows=db.execute("select * from users where username=:username", username=request.form.get("username"))

            # Remember which user has logged in
            session["user_id"] = rows[0]["id"]

            # Redirect user to home page
            return redirect("/")

    return render_template("/register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    rows=db.execute("select symbol, sum(buy), sum(shares) from transactions where id=:id group by symbol order by symbol", id=session["user_id"])
    symbols=[]
    shares=[]
    for r in rows:
        symbols.append(r["symbol"])
        shares.append(r["sum(shares)"])
        print(r)

    if request.method=="POST":
        sym=request.form.get("symbol")
        shares=int(request.form.get("shares"))
        user_shares=db.execute("select sum(shares) from transactions where id=:id and symbol=:symbol",
                id=session["user_id"], symbol=sym)
        print(user_shares)

        if (shares > user_shares[0]["sum(shares)"]):
            return render_template("apology.html", message="You do not own that many shares")
        stock=lookup(sym)
        price=stock["price"]*shares
        sym=stock["symbol"]
        db.execute("insert into transactions (id, symbol, sell, shares) values (:id, :symbol, :sell, :shares)",
                    id=session["user_id"], symbol=sym, sell=-price, shares=-shares)
        return redirect("/")

    return render_template("sell.html", length=len(rows), symbols=symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return render_template("apology.html", message="Internal Server Error")


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


if __name__ == "__main__":
    app.run()