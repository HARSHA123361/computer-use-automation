from flask import Flask, request, session, redirect, url_for, render_template_string
import os

app = Flask(__name__)
app.secret_key = "dev-secret-key"

MEMBERS = {
    "10001": {
        "name": "James Harrington",
        "type": "Checking",
        "balance": "$4,821.50",
        "status": "Active",
        "branch": "Downtown",
    },
    "10002": {
        "name": "Patricia Nguyen",
        "type": "Savings",
        "balance": "$12,340.00",
        "status": "Active",
        "branch": "Eastside",
    },
    "10003": {
        "name": "Robert Chen",
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
  body { font-family: Arial, sans-serif; background: #f0f2f5; color: #222; font-size: 14px; }
  .topbar {
    background: #003366; color: white; padding: 12px 24px;
    display: flex; justify-content: space-between; align-items: center;
  }
  .topbar .brand { font-size: 16px; font-weight: bold; letter-spacing: 0.3px; }
  .topbar .user-info { font-size: 13px; color: #aac4e8; }
  .topbar a { color: #aac4e8; text-decoration: none; margin-left: 12px; }
  .topbar a:hover { color: white; }
  .container { max-width: 680px; margin: 40px auto; padding: 0 16px; }
  .card {
    background: white; border-radius: 6px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.12); overflow: hidden;
  }
  .card-header {
    background: #003366; color: white;
    padding: 14px 20px; font-size: 15px; font-weight: bold;
  }
  .card-body { padding: 24px 28px; }
  .form-group { margin-bottom: 18px; }
  .form-group label { display: block; margin-bottom: 6px; font-weight: bold; color: #333; }
  .form-group input[type=text],
  .form-group input[type=password] {
    width: 100%; padding: 9px 12px; border: 1px solid #ccc;
    border-radius: 4px; font-size: 14px; outline: none;
    transition: border-color 0.2s;
  }
  .form-group input:focus { border-color: #003366; }
  .btn {
    display: inline-block; padding: 9px 22px; border: none;
    border-radius: 4px; font-size: 14px; cursor: pointer;
    text-decoration: none; font-weight: bold;
  }
  .btn-primary { background: #003366; color: white; }
  .btn-primary:hover { background: #004a99; }
  .btn-danger { background: #c0392b; color: white; }
  .btn-danger:hover { background: #a93226; }
  .btn-secondary { background: #6c757d; color: white; }
  .btn-secondary:hover { background: #5a6268; }
  .alert { padding: 10px 14px; border-radius: 4px; margin-bottom: 16px; font-size: 13px; }
  .alert-error { background: #fde8e8; color: #c0392b; border: 1px solid #f5c6cb; }
  .alert-warning { background: #fff8e1; color: #856404; border: 1px solid #ffeeba; }
  .detail-table { width: 100%; border-collapse: collapse; }
  .detail-table tr td { padding: 10px 14px; border-bottom: 1px solid #eee; }
  .detail-table tr td:first-child { width: 200px; font-weight: bold; color: #444; background: #f8f9fa; }
  .detail-table tr:last-child td { border-bottom: none; }
  .actions { margin-top: 20px; display: flex; gap: 10px; }
  .search-row { display: flex; gap: 10px; align-items: flex-end; }
  .search-row .form-group { flex: 1; margin-bottom: 0; }
</style>
"""

LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
  <title>First Valley CU - Staff Login</title>
  """ + BASE_STYLE + """
  <style>
    body { display: flex; align-items: center; justify-content: center; min-height: 100vh; }
    .login-wrap { width: 100%; max-width: 380px; }
    .login-wrap .card-header { text-align: center; font-size: 16px; }
    .login-wrap .subtitle { text-align: center; font-size: 12px; color: #aac4e8; margin-top: 3px; }
    .login-wrap .card-body { padding: 28px 32px; }
    .login-wrap .btn-primary { width: 100%; padding: 10px; margin-top: 6px; }
  </style>
</head>
<body>
  <div class="login-wrap">
    <div class="card">
      <div class="card-header">
        First Valley Credit Union
        <div class="subtitle">Staff Back-Office Portal</div>
      </div>
      <div class="card-body">
        {% if error %}
        <div class="alert alert-error">{{ error }}</div>
        {% endif %}
        <form method="post" action="/login">
          <div class="form-group">
            <label for="username">Username</label>
            <input type="text" id="username" name="username" placeholder="Enter username" autofocus>
          </div>
          <div class="form-group">
            <label for="password">Password</label>
            <input type="password" id="password" name="password" placeholder="Enter password">
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
      Logged in as: {{ user }}
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
                     value="{{ member_id or '' }}" placeholder="e.g. 10001" autofocus>
            </div>
            <button type="submit" class="btn btn-primary" style="height:38px;">Search</button>
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
      Logged in as: {{ user }}
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
          <tr><td>Account Type</td><td>{{ member.type }}</td></tr>
          <tr><td>Current Balance</td><td><strong>{{ member.balance }}</strong></td></tr>
          <tr><td>Account Status</td><td>{{ member.status }}</td></tr>
          <tr><td>Branch</td><td>{{ member.branch }}</td></tr>
        </table>
        <div class="actions">
          <a href="/search" class="btn btn-secondary">Back to Search</a>
          <a href="/transfer/{{ member.id }}" class="btn btn-danger">Initiate Transfer</a>
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
      Logged in as: {{ user }}
      <a href="/logout">Logout</a>
    </div>
  </div>
  <div class="container">
    <div class="card">
      <div class="card-header" style="background:#c0392b;">Initiate Fund Transfer</div>
      <div class="card-body">
        <div class="alert alert-warning">
          <strong>Warning:</strong> This action is irreversible. Funds will be debited immediately upon submission.
        </div>
        {% if error %}
        <div class="alert alert-error">{{ error }}</div>
        {% endif %}
        <form method="post" action="/transfer/{{ member_id }}">
          <div class="form-group">
            <label>From Member ID</label>
            <input type="text" value="{{ member_id }}" disabled style="background:#f4f4f4;">
          </div>
          <div class="form-group">
            <label for="to_account">To Account Number</label>
            <input type="text" id="to_account" name="to_account" placeholder="Destination account">
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
            <a href="/member/{{ member_id }}" class="btn btn-secondary">Cancel</a>
            <button type="submit" class="btn btn-danger">Submit Transfer</button>
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
      <div class="card-header" style="background:#1a7a3c;">Transfer Request Submitted</div>
      <div class="card-body">
        <p style="margin-bottom:16px;">
          Transfer of <strong>{{ amount }}</strong> from member
          <strong>{{ from_id }}</strong> to account
          <strong>{{ to_account }}</strong> has been queued for processing.
        </p>
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
    return render_template_string(SEARCH_PAGE, user=session["user"], error=error, member_id=member_id or None)


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
