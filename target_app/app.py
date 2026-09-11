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

LOGIN_PAGE = """
<html>
<head><title>First Valley CU - Staff Portal</title></head>
<body bgcolor="#e8e8e8">
<center>
<br><br>
<form method="post" action="/login">
<table width="400" border="2" cellpadding="8" cellspacing="0" bgcolor="#ffffff">
<tr bgcolor="#003366"><td colspan="2" align="center">
<font color="white" size="4"><b>First Valley Credit Union</b></font><br>
<font color="#cccccc" size="2">Staff Back-Office Portal</font>
</td></tr>
{% if error %}
<tr><td colspan="2" bgcolor="#ffdddd" align="center">
<font color="red">{{ error }}</font>
</td></tr>
{% endif %}
<tr><td colspan="2">&nbsp;</td></tr>
<tr>
<td align="right"><b>Username:</b></td>
<td><input type="text" name="username" size="20"></td>
</tr>
<tr>
<td align="right"><b>Password:</b></td>
<td><input type="password" name="password" size="20"></td>
</tr>
<tr><td colspan="2">&nbsp;</td></tr>
<tr><td colspan="2" align="center">
<input type="submit" value="  Log In  ">
</td></tr>
<tr><td colspan="2">&nbsp;</td></tr>
</table>
</form>
</center>
</body>
</html>
"""

SEARCH_PAGE = """
<html>
<head><title>Member Search - First Valley CU</title></head>
<body bgcolor="#f0f0f0">
<table width="100%" border="0" cellpadding="4" bgcolor="#003366">
<tr>
<td><font color="white" size="3"><b>First Valley Credit Union — Staff Portal</b></font></td>
<td align="right"><font color="#aaaaff" size="2">Logged in as: {{ user }} &nbsp;|&nbsp; <a href="/logout" style="color:#aaaaff">Logout</a></font></td>
</tr>
</table>
<br>
<center>
<table width="600" border="1" cellpadding="6" cellspacing="0" bgcolor="#ffffff">
<tr bgcolor="#003366"><td colspan="2">
<font color="white" size="3"><b>Member Account Search</b></font>
</td></tr>
{% if error %}
<tr><td colspan="2" bgcolor="#fff0aa" align="center">
<font color="#aa6600">{{ error }}</font>
</td></tr>
{% endif %}
<tr><td colspan="2">&nbsp;</td></tr>
<tr>
<td colspan="2" align="center">
<form method="get" action="/search">
<b>Member ID:</b>&nbsp;
<input type="text" name="member_id" value="{{ member_id or '' }}" size="15">
&nbsp;&nbsp;
<input type="submit" value=" Search ">
</form>
</td>
</tr>
<tr><td colspan="2">&nbsp;</td></tr>
</table>
</center>
</body>
</html>
"""

DETAIL_PAGE = """
<html>
<head><title>Member Detail - First Valley CU</title></head>
<body bgcolor="#f0f0f0">
<table width="100%" border="0" cellpadding="4" bgcolor="#003366">
<tr>
<td><font color="white" size="3"><b>First Valley Credit Union — Staff Portal</b></font></td>
<td align="right"><font color="#aaaaff" size="2">Logged in as: {{ user }} &nbsp;|&nbsp; <a href="/logout" style="color:#aaaaff">Logout</a></font></td>
</tr>
</table>
<br>
<center>
<table width="600" border="1" cellpadding="6" cellspacing="0" bgcolor="#ffffff">
<tr bgcolor="#003366"><td colspan="2">
<font color="white" size="3"><b>Member Account Detail</b></font>
</td></tr>
<tr><td colspan="2">&nbsp;</td></tr>
<tr bgcolor="#e8e8ff">
<td width="200"><b>Member ID</b></td>
<td>{{ member.id }}</td>
</tr>
<tr>
<td><b>Full Name</b></td>
<td>{{ member.name }}</td>
</tr>
<tr bgcolor="#e8e8ff">
<td><b>Account Type</b></td>
<td>{{ member.type }}</td>
</tr>
<tr>
<td><b>Current Balance</b></td>
<td><b>{{ member.balance }}</b></td>
</tr>
<tr bgcolor="#e8e8ff">
<td><b>Account Status</b></td>
<td>{{ member.status }}</td>
</tr>
<tr>
<td><b>Branch</b></td>
<td>{{ member.branch }}</td>
</tr>
<tr><td colspan="2">&nbsp;</td></tr>
<tr><td colspan="2" align="center">
<a href="/search">[Back to Search]</a>
&nbsp;&nbsp;&nbsp;
<a href="/transfer/{{ member.id }}">[Initiate Transfer]</a>
</td></tr>
<tr><td colspan="2">&nbsp;</td></tr>
</table>
</center>
</body>
</html>
"""

TRANSFER_PAGE = """
<html>
<head><title>Transfer Funds - First Valley CU</title></head>
<body bgcolor="#f0f0f0">
<table width="100%" border="0" cellpadding="4" bgcolor="#003366">
<tr>
<td><font color="white" size="3"><b>First Valley Credit Union — Staff Portal</b></font></td>
<td align="right"><font color="#aaaaff" size="2">Logged in as: {{ user }} &nbsp;|&nbsp; <a href="/logout" style="color:#aaaaff">Logout</a></font></td>
</tr>
</table>
<br>
<center>
<table width="600" border="1" cellpadding="6" cellspacing="0" bgcolor="#ffffff">
<tr bgcolor="#aa0000"><td colspan="2">
<font color="white" size="3"><b>Initiate Fund Transfer</b></font>
</td></tr>
{% if error %}
<tr><td colspan="2" bgcolor="#ffdddd" align="center">
<font color="red">{{ error }}</font>
</td></tr>
{% endif %}
<tr bgcolor="#fff5cc"><td colspan="2">
<font color="#aa6600"><b>Warning:</b> This action is irreversible. Funds will be debited immediately.</font>
</td></tr>
<tr><td colspan="2">&nbsp;</td></tr>
<tr>
<td><b>From Member ID</b></td>
<td>{{ member_id }}</td>
</tr>
<tr><td colspan="2">&nbsp;</td></tr>
<tr>
<td colspan="2" align="center">
<form method="post" action="/transfer/{{ member_id }}">
<table border="0" cellpadding="4">
<tr>
<td align="right"><b>To Account No.:</b></td>
<td><input type="text" name="to_account" size="20"></td>
</tr>
<tr>
<td align="right"><b>Amount ($):</b></td>
<td><input type="text" name="amount" size="20"></td>
</tr>
<tr>
<td align="right"><b>Memo:</b></td>
<td><input type="text" name="memo" size="30"></td>
</tr>
<tr><td colspan="2" align="center">&nbsp;</td></tr>
<tr><td colspan="2" align="center">
<input type="submit" value=" Submit Transfer " style="background:#aa0000;color:white;font-weight:bold;">
&nbsp;&nbsp;
<a href="/member/{{ member_id }}">[Cancel]</a>
</td></tr>
</table>
</form>
</td></tr>
<tr><td colspan="2">&nbsp;</td></tr>
</table>
</center>
</body>
</html>
"""

TRANSFER_CONFIRM_PAGE = """
<html>
<head><title>Transfer Submitted - First Valley CU</title></head>
<body bgcolor="#f0f0f0">
<table width="100%" border="0" cellpadding="4" bgcolor="#003366">
<tr>
<td><font color="white" size="3"><b>First Valley Credit Union — Staff Portal</b></font></td>
</tr>
</table>
<br>
<center>
<table width="500" border="1" cellpadding="6" cellspacing="0" bgcolor="#ffffff">
<tr bgcolor="#006600"><td>
<font color="white" size="3"><b>Transfer Request Submitted</b></font>
</td></tr>
<tr><td>&nbsp;</td></tr>
<tr><td>Transfer of <b>{{ amount }}</b> from member <b>{{ from_id }}</b> to account <b>{{ to_account }}</b> has been queued.</td></tr>
<tr><td>&nbsp;</td></tr>
<tr><td align="center"><a href="/search">[Return to Search]</a></td></tr>
<tr><td>&nbsp;</td></tr>
</table>
</center>
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
    error = None
    if member_id and member_id not in MEMBERS:
        error = f"No member found with ID: {member_id}"
        return render_template_string(SEARCH_PAGE, user=session["user"], error=error, member_id=member_id)
    if member_id and member_id in MEMBERS:
        return redirect(url_for("member_detail", member_id=member_id))
    return render_template_string(SEARCH_PAGE, user=session["user"], error=None, member_id=None)


@app.route("/member/<member_id>")
def member_detail(member_id):
    if not session.get("user"):
        return redirect(url_for("login"))
    data = MEMBERS.get(member_id)
    if not data:
        return render_template_string(SEARCH_PAGE, user=session["user"], error=f"No member found with ID: {member_id}", member_id=member_id)
    member = dict(data)
    member["id"] = member_id
    return render_template_string(DETAIL_PAGE, user=session["user"], member=member)


@app.route("/transfer/<member_id>", methods=["GET", "POST"])
def transfer(member_id):
    if not session.get("user"):
        return redirect(url_for("login"))
    error = None
    if request.method == "POST":
        to_account = request.form.get("to_account", "").strip()
        amount = request.form.get("amount", "").strip()
        memo = request.form.get("memo", "").strip()
        if not to_account or not amount:
            error = "To Account and Amount are required."
            return render_template_string(TRANSFER_PAGE, user=session["user"], member_id=member_id, error=error)
        try:
            float(amount.replace(",", "").replace("$", ""))
        except ValueError:
            error = "Amount must be a valid number."
            return render_template_string(TRANSFER_PAGE, user=session["user"], member_id=member_id, error=error)
        return render_template_string(TRANSFER_CONFIRM_PAGE, amount=f"${amount}", from_id=member_id, to_account=to_account)
    return render_template_string(TRANSFER_PAGE, user=session["user"], member_id=member_id, error=None)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="127.0.0.1", port=port, debug=False)
