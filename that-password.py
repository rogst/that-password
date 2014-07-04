from flask import Flask, g, url_for, request, redirect, render_template, flash, abort
from pymongo import MongoClient
from datetime import datetime, timedelta
import time
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = "qwerty"

def get_db():
    db = getattr(g, 'mongodb', None)
    if db is None:
        db = g.mongodb = MongoClient('mongodb://localhost:27017/')
    return db.thatpassword

@app.teardown_appcontext
def close_db(error):
    db = getattr(g, 'mongodb', None)
    if db is not None:
        db.close()

def create_password_link(password, validity):
    db = get_db()
    collection = db.passwords
    link = str(uuid.uuid4())
    doc = {"link": link,
           "password": password, 
           "views": 0,
           "created": time.strftime("%Y/%m/%d %H:%M:%S")}
    if "views" in validity:
        doc["max_views"] = validity['views']
    if "days" in validity:
        doc["max_age"] = validity['days']
    if "ip" in validity:
        doc["valid_ip"] = validity['ip']
    collection.insert(doc)
    return link
       
def get_password(password_id):
    db = get_db()
    passwords = db.passwords
    doc = passwords.find_one({"link": password_id})
    if doc is None:
        abort(404)
    passwords.update({"link": password_id},
                     {"$inc": {"views": 1}})
    password = doc["password"]
    if "max_views" in doc:
        if int(doc["views"]) >= int(doc["max_views"]):
            passwords.remove({"link": password_id})
            abort(404)
    if "max_days" in doc:
        now = time.strftime("%Y/%m/%d %H:%M:%S")
        created_date = datetime(doc["created"], "%Y/%m/%d %H:%M:%S")
        end_date = created_date + timedelta(days=doc["max_days"])
        if now > end_date:
            passwords.remove({"link": password_id})
            abort(404)
    if "valid_ip" in doc:
        client_ip = None
        if not request.headers.getlist("X-Forwarded-For"):
           client_ip = request.remote_addr
        else:
           client_ip = request.headers.getlist("X-Forwarded-For")[0]
        if client_ip != doc["valid_ip"]:
            abort(404)
        
    return password

    
@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == "POST":
        password = request.form["password"]
        valid_type = request.form.getlist("valid_type")
        validity = {}
        if 'views' in valid_type:
            validity['views'] = request.form["valid_views"]
        if 'days' in valid_type:
            validity['days'] = request.form["valid_days"]
        if 'ip' in valid_type:
            validity['ip'] = request.form["valid_ip"]
        link = create_password_link(password, validity)
        flash(url_for('view_password', password_id=link, _external=True))
        return render_template('index.html')
    
    return render_template('index.html')


@app.route("/password/<password_id>")
def view_password(password_id):
    password = get_password(password_id)
    return render_template('password.html', password=password)

@app.errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html'), 404



if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
