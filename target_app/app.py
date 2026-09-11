from flask import Flask, request, session, redirect, url_for, render_template_string
import os

app = Flask(__name__)
app.secret_key = "dev-secret-key"

MEMBERS = {
    "10001": {
        "name": "James Harrington",
        "account_number": "ACC-0010-4821",
        "type": "Checking",
        "balance": "$4,821.50",
        "status": "Active",
        "branch": "Downtown",
    },
    "10002": {
        "name": "Patricia Nguyen",
        "account_number": "ACC-0010-1234",
        "type": "Savings",
        "balance": "$12,340.00",
        "status": "Active",
        "branch": "Eastside",
    },
    "10003": {
        "name": "Robert Chen",
        "account_number": "ACC-0010-9807",
        "type": "Savings",
        "balance": "$980.75",
        "status": "Frozen",
        "branch": "Westpark",
    },
}

BASE_STYLE = """
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Arial', sans-serif;
    background: #eef0f3;
    color: #1a1a2e;
    font-size: 14px;
  }

  .topbar {
    background: #1a1a2e;
    color: #ffffff;
    padding: 13px 28px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 3px solid #2e4a7a;
  }
  .topbar .brand {
    font-size: 15px;
    font-weight: bold;
    letter-spacing: 0.4px;
  }
  .topbar .user-info {
    font-size: 13px;
    color: #a0aec0;
  }
  .topbar a {
    color: #a0aec0;
    text-decoration: none;
    margin-left: 14px;
    border: 1px solid #3a4a6a;
    padding: 4px 10px;
    border-radius: 3px;
    font-size: 12px;
  }
  .topbar a:hover { color: #ffffff; border-color: #ffffff; }

  .container {
    max-width: 660px;
    margin: 36px auto;
    padding: 0 16px;
  }

  .card {
    background: #ffffff;
    border-radius: 5px;
    border: 1px solid #d8dde6;
    box-shadow: 0 2px 6px rgba(0,0,0,0.07);
    overflow: hidden;
  }

  .card-header {
    background: #1a1a2e;
    color: #ffffff;
    padding: 13px 22px;
    font-size: 14px;
    font-weight: bold;
    letter-spacing: 0.3px;
  }

  .card-header.warning-header {
    background: #92610a;
  }

  .card-header.success-header {
    background: #1a5c32;
  }

  .card-body { padding: 26px 28px; }

  .form-group { margin-bottom: 16px; }
  .form-group label {
    display: block;
    margin-bottom: 5px;
    font-weight: bold;
    font-size: 13px;
    color: #2d3748;
  }
  .form-group input[type=text],
  .form-group input[type=password] {
    width: 100%;
    padding: 8px 11px;
    border: 1px solid #c8d0dc;
    border-radius: 4px;
    font-size: 14px;
    outline: none;
    background: #fafbfc;
    color: #1a1a2e;
    transition: border-color 0.15s;
  }
  .form-group input:focus {
    border-color: #2e4a7a;
    background: #ffffff;
  }
  .form-group input:disabled {
    background: #f0f2f5;
    color: #666;
  }

  .btn {
    display: inline-block;
    padding: 8px 20px;
    border: none;
    border-radius: 4px;
    font-size: 13px;
    font-weight: bold;
    cursor: pointer;
    text-decoration: none;
    letter-spacing: 0.2px;
  }

  .btn-primary {
    background: #1a1a2e;
    color: #ffffff;
  }
  .btn-primary:hover { background: #2e4a7a; }

  .btn-outline {
    background: transparent;
    color: #1a1a2e;
    border: 1px solid #c8d0dc;
  }
  .btn-outline:hover { background: #f0f2f5; }

  .btn-destructive {
    background: #7a1a1a;
    color: #ffffff;
  }
  .btn-destructive:hover { background: #9b2020; }

  .alert {
    padding: 10px 14px;
    border-radius: 4px;
    margin-bottom: 16px;
    font-size: 13px;
    line-height: 1.5;
  }
  .alert-warning {
    background: #fffbeb;
    color: #78500a;
    border: 1px solid #f5c842;
  }
  .alert-error {
    background: #fff5f5;
    color: #7a1a1a;
    border: 1px solid #e8a0a0;
  }

  .detail-table { width: 100%; border-collapse: collapse; }
  .detail-table tr td {
    padding: 10px 14px;
    border-bottom: 1px solid #edf0f5;
    font-size: 14px;
  }
  .detail-table tr td:first-child {
    width: 180px;
    font-weight: bold;
    color: #4a5568;
    background: #f7f8fa;
    font-size: 13px;
  }
  .detail-table tr:last-child td { border-bottom: none; }

  .actions {
    margin-top: 22px;
    display: flex;
    gap: 10px;
  }

  .search-row {
    display: flex;
    gap: 10px;
    align-items: flex-end;
  }
  .search-row .form-group { flex: 1; margin-bottom: 0; }

  .success-box {
    background: #f0faf4;
    border: 1px solid #a3d9b1;
    border-radius: 4px;
    padding: 18px 20px;
    margin-bottom: 20px;
  }
  .success-box .success-label {
    font-size: 13px;
    font-weight: bold;
    color: #1a5c32;
    margin-bottom: 10px;
  }
  .success-box .success-row {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    padding: 5px 0;
    border-bottom: 1px solid #d0eeda;
    color: #2d3748;
  }
  .success-box .success-row:last-child { border-bottom: none; }
  .success-box .success-row span:last-child { font-weight: bold; }
</style>
"""

LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <title>First Valley CU - Staff Login</title>
  """ + BASE_STYLE + """
  <style>
    body {
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }
    .login-wrap { width: 100%; max-width: 360px; }
    .login-wrap .card-header {
      text-align: center;
      padding: 18px 22px 14px;
      font-size: 15px;
    }
    .login-wrap .subtitle {
      font-size: 11px;
      color: #a0aec0;
      font-weight: normal;
      margin-top: 3px;
      letter-spacing: 0.3px;
    }
    .login-wrap .card-body { padding: 26px 28px 28px; }
    .login-wrap .btn-primary {
      width: 100%;
      padding: 10px;
      margin-top: 4px;
      font-size: 14px;
    }
  </style>
</head>
<body>
  <div class="login-wrap">
    <div class="card">
      <div class="card-header">
        First Valley Credit Union
        <div class="subtitle">STAFF BACK-OFFICE PORTAL</div>
      </div>
      <div class="card-body">
        {% if error %}
        <div class="alert alert-error">{{ error }}</div>
        {% endif %}
        <form method="post" action="/login">
          <div class="form-group">
            <label for="username">Username</label>
            <input type="text" id="username" name="username"
                   placeholder="Enter your username" autofocus>
          </div>
          <div class="form-group">
            <label for="password">Password</label>
            <input type="password" id="password" name="password"
                   placeholder="Enter your password">
          </div>
          <button type="submit" class="btn btn-primary">Log In</button>
        </form>
      </div>
    </div>
  </div>
</body>
</html>
"""

SEARCH_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <title>Member Search - First Valley CU</title>
  """ + BASE_STYLE + """
</head>
<body>
  <div class="topbar">
    <div class="brand">First Valley Credit Union &mdash; Staff Portal</div>
    <div class="user-info">
      {{ user }}
      <a href="/logout">Logout</a>
    </div>
  </div>
  <div class="container">
    <div class="card">
      <div class="card-header">Member Account Search</div>
      <div class="card-body">
        {% if error %}
        <div class="alert alert-error">{{ error }}</div>
        {% endif %}
        <form method="get" action="/search">
          <div class="search-row">
            <div class="form-group">
              <label for="member_id">Member ID</label>
              <input type="text" id="member_id" name="member_id"
                     value="{{ member_id or '' }}"
                     placeholder="Enter member ID (e.g. 10001)" autofocus>
            </div>
            <button type="submit" class="btn btn-primary"
                    style="height: 37px; margin-bottom: 1px;">Search</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</body>
</html>
"""

DETAIL_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <title>Member Detail - First Valley CU</title>
  """ + BASE_STYLE + """
</head>
<body>
  <div class="topbar">
    <div class="brand">First Valley Credit Union &mdash; Staff Portal</div>
    <div class="user-info">
      {{ user }}
      <a href="/logout">Logout</a>
    </div>
  </div>
  <div class="container">
    <div class="card">
      <div class="card-header">Member Account Detail</div>
      <div class="card-body">
        <table class="detail-table">
          <tr><td>Member ID</td><td>{{ member.id }}</td></tr>
          <tr><td>Full Name</td><td>{{ member.name }}</td></tr>
          <tr><td>Account Number</td><td>{{ member.account_number }}</td></tr>
          <tr><td>Account Type</td><td>{{ member.type }}</td></tr>
          <tr><td>Current Balance</td><td><strong>{{ member.balance }}</strong></td></tr>
          <tr><td>Account Status</td><td>{{ member.status }}</td></tr>
          <tr><td>Branch</td><td>{{ member.branch }}</td></tr>
        </table>
        <div class="actions">
          <a href="/search" class="btn btn-outline">Back to Search</a>
          <a href="/transfer/{{ member.id }}" class="btn btn-destructive">Initiate Transfer</a>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""

TRANSFER_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <title>Transfer Funds - First Valley CU</title>
  """ + BASE_STYLE + """
</head>
<body>
  <div class="topbar">
    <div class="brand">First Valley Credit Union &mdash; Staff Portal</div>
    <div class="user-info">
      {{ user }}
      <a href="/logout">Logout</a>
    </div>
  </div>
  <div class="container">
    <div class="card">
      <div class="card-header warning-header">Initiate Fund Transfer</div>
      <div class="card-body">
        <div class="alert alert-warning">
          <strong>Warning:</strong> This action is irreversible.
          Funds will be debited immediately upon submission.
        </div>
        {% if error %}
        <div class="alert alert-error">{{ error }}</div>
        {% endif %}
        <form method="post" action="/transfer/{{ member_id }}">
          <div class="form-group">
            <label>From Member ID</label>
            <input type="text" value="{{ member_id }}" disabled>
          </div>
          <div class="form-group">
            <label for="to_account">To Account Number</label>
            <input type="text" id="to_account" name="to_account"
                   placeholder="Destination account number">
          </div>
          <div class="form-group">
            <label for="amount">Amount ($)</label>
            <input type="text" id="amount" name="amount" placeholder="0.00">
          </div>
          <div class="form-group">
            <label for="memo">Memo (optional)</label>
            <input type="text" id="memo" name="memo" placeholder="Transfer note">
          </div>
          <div class="actions">
            <a href="/member/{{ member_id }}" class="btn btn-outline">Cancel</a>
            <button type="submit" class="btn btn-destructive">Submit Transfer</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</body>
</html>
"""

TRANSFER_CONFIRM_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <title>Transfer Submitted - First Valley CU</title>
  """ + BASE_STYLE + """
</head>
<body>
  <div class="topbar">
    <div class="brand">First Valley Credit Union &mdash; Staff Portal</div>
  </div>
  <div class="container">
    <div class="card">
      <div class="card-header success-header">Transfer Request Submitted</div>
      <div class="card-body">
        <div class="success-box">
          <div class="success-label">Transaction Details</div>
          <div class="success-row">
            <span>From Member</span><span>{{ from_id }}</span>
          </div>
          <div class="success-row">
            <span>To Account</span><span>{{ to_account }}</span>
          </div>
          <div class="success-row">
            <span>Amount</span><span>{{ amount }}</span>
          </div>
          <div class="success-row">
            <span>Status</span><span>Queued for Processing</span>
          </div>
        </div>
        <a href="/search" class="btn btn-primary">Return to Search</a>
      </div>
    </div>
  </div>
</body>
</html>
"""


@app.route("/")
def index():
    if session.get("user"):
        return redirect(url_for("search"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username == "staff" and password == "demo1234":
            session["user"] = username
            return redirect(url_for("search"))
        error = "Invalid credentials. Please try again."
    return render_template_string(LOGIN_PAGE, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/search")
def search():
    if not session.get("user"):
        return redirect(url_for("login"))
    member_id = request.args.get("member_id", "").strip()
    if member_id and member_id in MEMBERS:
        return redirect(url_for("member_detail", member_id=member_id))
    error = None
    if member_id and member_id not in MEMBERS:
        error = f"No member found with ID: {member_id}"
    return render_template_string(SEARCH_PAGE, user=session["user"],
                                  error=error, member_id=member_id or None)


@app.route("/member/<member_id>")
def member_detail(member_id):
    if not session.get("user"):
        return redirect(url_for("login"))
    data = MEMBERS.get(member_id)
    if not data:
        return render_template_string(SEARCH_PAGE, user=session["user"],
                                      error=f"No member found with ID: {member_id}",
                                      member_id=member_id)
    member = dict(data)
    member["id"] = member_id
    return render_template_string(DETAIL_PAGE, user=session["user"], member=member)


@app.route("/transfer/<member_id>", methods=["GET", "POST"])
def transfer(member_id):
    if not session.get("user"):
        return redirect(url_for("login"))
    if request.method == "POST":
        to_account = request.form.get("to_account", "").strip()
        amount = request.form.get("amount", "").strip()
        if not to_account or not amount:
            return render_template_string(TRANSFER_PAGE, user=session["user"],
                                          member_id=member_id,
                                          error="To Account and Amount are required.")
        try:
            float(amount.replace(",", "").replace("$", ""))
        except ValueError:
            return render_template_string(TRANSFER_PAGE, user=session["user"],
                                          member_id=member_id,
                                          error="Amount must be a valid number.")
        return render_template_string(TRANSFER_CONFIRM_PAGE,
                                      amount=f"${amount}",
                                      from_id=member_id,
                                      to_account=to_account)
    return render_template_string(TRANSFER_PAGE, user=session["user"],
                                  member_id=member_id, error=None)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="127.0.0.1", port=port, debug=False)
