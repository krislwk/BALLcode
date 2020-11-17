from flask import Flask, redirect, url_for, render_template, request, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import requests
from lxml import html

def moodleLogin(user, passw):
    login_url = "https://bangkok.learn.nae.school/login/index.php"
    url = "https://bangkok.learn.nae.school/mod/canteen/view.php?id=59957&userid="
    session_requests = requests.session()

    result = session_requests.get(login_url)
    tree = html.fromstring(result.text)
    authenticity_token = list(set(tree.xpath("//input[@name='logintoken']/@value")))[0]

    payload = {
        "username" : user,
        "password" : passw,
        "logintoken" : authenticity_token
    }

    result = session_requests.post(login_url, data = payload, headers = dict(referer = login_url))
    result = session_requests.get(url)
    if "<title>Moodle @ St Andrews: Log in to the site</title>" in result.text:
        return False
    else:
        return True

app = Flask(__name__, template_folder="Templates")
app.secret_key = "mrAdamIsTheBest"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////home/ballcode/mysite/User.sqlite3'
app.config['SQLALCHEMY_BINDS'] = {'equipment' : 'sqlite:////home/ballcode/mysite/Equipment.sqlite3', 'blacklist' : 'sqlite:////home/ballcode/mysite/Blacklist.sqlite3'}

db = SQLAlchemy(app)
admin_list = ["Kris","Adam"]
admin_password = "mradamisthebest"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20))
    name = db.Column(db.String(20))
    year = db.Column(db.Integer)
    date = db.Column(db.String(10))
    time = db.Column(db.String(5))
    equipment = db.Column(db.String(20))
    eID = db.Column(db.String(6))

    def __init__(self, username, link):
        self.username = (username[:-3].lower() + username[-3:])
        self.name = username[:-3].lower()
        self.year = (13 - (int(username[-2:]) - 20))+1
        self.date = str(datetime.now())[:10]
        self.time = (str(datetime.now() + timedelta(hours=7)).split(" ")[1])[:8]
        self.equipment = link[6:]
        self.eID = link[:6]

class Equipment(db.Model):
    __bind_key__ = 'equipment'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    eID = db.Column(db.String(6))

    def __init__(self, n, id):
        self.name = n
        self.eID = id

class Blacklist(db.Model):
    __bind_key__ = 'blacklist'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20))

    def __init__(self, n):
        self.username = n

def createComparableUsername(username):
    name = username[:-3].lower()
    year = username[-3:]
    return name + year

@app.route("/returncode/", methods=["GET", "POST"])
def returncode():
    if request.method == "POST":
        if moodleLogin(request.form["username"], request.form["password"]):
            if User.query.filter_by(eID = session["equipmentID"]).first().username != request.form["username"]:
                return redirect(url_for("denyborrow"))
            db.session.delete(User.query.filter_by(eID = session["equipmentID"]).first())
            db.session.commit()
            return redirect(url_for("Return"))
        else:
            return render_template("login.html", error="Incorrect username and/or password.")
    else:
        return render_template("login.html", error="")

@app.route("/<equipment>", methods=["GET", "POST"])
def login(equipment):
    if User.query.filter_by(eID = equipment[:6]).first():
        session["equipmentID"] = equipment[:6]
        return redirect(url_for("returncode"))
    if Equipment.query.filter_by(eID = equipment[:6]).first() and Equipment.query.filter_by(eID = equipment[:6]).first().name == equipment[6:]:
        if not User.query.filter_by(eID = equipment[:6]).first():
            if request.method == "POST":
                if Blacklist.query.filter_by(username = createComparableUsername(request.form["username"])).first():
                    return redirect(url_for("deny"))
                if User.query.filter_by(username = createComparableUsername(request.form["username"])).first():
                    return redirect(url_for("deny"))
                if moodleLogin(request.form["username"], request.form["password"]):
                    db.session.add(User(request.form["username"], equipment))
                    db.session.commit()
                    session["gear"] = equipment
                    session["redirect"] = False
                    return redirect(url_for("borrow"))
                else:
                    return render_template("login.html", error="Incorrect username and/or password.")
            else:
                return render_template("login.html", error="")
        else:
            try:
                if session["redirect"] == False:
                    return redirect("error.html")
            except:
                db.session.delete(User.query.filter_by(eID = equipment[:6]).first())
                db.session.commit()
                return redirect(url_for("Return"))
    else:
        return render_template("error.html")

@app.route("/deniedborrowed/")
def denyborrow():
    return render_template("alrborrowed.html")

@app.route("/denied/")
def deny():
    return render_template("deny.html")

@app.route("/Return/")
def Return():
    return render_template("return.html")

@app.route("/borrow/")
def borrow():
    equipment = session["gear"]
    session.pop("gear", None)
    return render_template("borrow.html", gear=equipment[6:])

@app.route("/error/")
def error():
    return render_template("error.html")

@app.route("/create/", methods=["GET", "POST"])
def create():
    if "admin" in session:
        if request.method == "POST":
            if request.form["submit"] == "Delete":
                db.session.delete(Equipment.query.filter_by(eID = request.form["eID_for_delete"]).first())
                db.session.commit()
                return redirect(url_for("create"))
            if len(request.form["eID"]) != 6:
                return render_template("create.html", equipments=Equipment.query.all(), error="ID must be 6 characters.")
            if Equipment.query.filter_by(eID = request.form["eID"]).first():
                return render_template("create.html", equipments=Equipment.query.all(), error="ID must be unique.")
            db.session.add(Equipment(request.form["name"], request.form["eID"]))
            db.session.commit()
            return redirect(url_for("create"))
        else:
            return render_template("create.html", equipments=Equipment.query.all(), error="")
    else:
         session["next"] = "create"
         return redirect(url_for("adminLogin"))

@app.route("/admin/", methods=["GET", "POST"])
def admin():
    if "admin" in session:
        if request.method == "POST":
            if request.form["submit"] == "Logout":
                session.pop("admin", None)
                return redirect(url_for("adminLogin"))
            else:
                db.session.delete(User.query.filter_by(eID = request.form["eID"]).first())
                db.session.commit()
                return render_template("admin.html", users=User.query.all())
        return render_template("admin.html", users=User.query.all())
    else:
        session["next"] = "admin"
        return redirect(url_for("adminLogin"))

@app.route("/blacklist", methods=["GET", "POST"])
def blacklist():
    if "admin" in session:
        if request.method == "POST":
            if not Blacklist.query.filter_by(username=createComparableUsername(request.form["username"])).first():
                return render_template("blacklist.html", users=Blacklist.query.all())
            if request.form["submit"] == "Add":
                db.session.add(Blacklist(createComparableUsername(request.form["username"])))
                db.session.commit()
                return render_template("blacklist.html", users=Blacklist.query.all())
            if request.form["submit"] == "Delete":
                db.session.delete(Blacklist.query.filter_by(username=createComparableUsername(request.form["username"])).first())
                db.session.commit()
                return render_template("blacklist.html", users=Blacklist.query.all())
        else:
            return render_template("blacklist.html", users=Blacklist.query.all())
    else:
        session["next"] = "blacklist"
        return redirect(url_for("adminLogin"))

@app.route("/adminLogin", methods=["GET", "POST"])
def adminLogin():
    if request.method == "POST":
        if request.form["username"] in admin_list and request.form["password"] == admin_password:
            session["admin"] = True
            return redirect(session["next"])
    else:
        return render_template("adminlogin.html")

if __name__ == "__main__":
    app.run()
