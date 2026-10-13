import os
import sqlite3
import hashlib
import json
import secrets
from datetime import datetime, timezone
from functools import wraps
from io import BytesIO

import qrcode
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort, flash, send_file

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "instance", "honeychain.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("HONEYCHAIN_SECRET", secrets.token_hex(32))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db

def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    return f"{salt}${digest}"

def verify_password(password, stored):
    try:
        salt, digest = stored.split("$", 1)
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
        return secrets.compare_digest(check, digest)
    except Exception:
        return False

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'beekeeper',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS hives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hive_code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        location TEXT NOT NULL,
        bee_species TEXT NOT NULL,
        colony_strength TEXT NOT NULL,
        installation_date TEXT,
        temperature REAL DEFAULT 34,
        humidity REAL DEFAULT 60,
        activity_level TEXT DEFAULT 'High',
        status TEXT DEFAULT 'Healthy',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS inspections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        hive_id INTEGER NOT NULL,
        inspection_date TEXT NOT NULL,
        temperature REAL,
        humidity REAL,
        colony_strength TEXT,
        activity_level TEXT,
        notes TEXT,
        FOREIGN KEY(hive_id) REFERENCES hives(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id TEXT UNIQUE NOT NULL,
        hive_id INTEGER NOT NULL,
        honey_type TEXT NOT NULL,
        origin TEXT NOT NULL,
        harvest_date TEXT NOT NULL,
        quantity REAL NOT NULL,
        harvest_method TEXT,
        notes TEXT,
        status TEXT DEFAULT 'Harvested',
        created_at TEXT NOT NULL,
        FOREIGN KEY(hive_id) REFERENCES hives(id)
    );
    CREATE TABLE IF NOT EXISTS quality_tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        moisture REAL,
        ph REAL,
        purity_status TEXT,
        color TEXT,
        aroma TEXT,
        test_center TEXT,
        certificate_number TEXT,
        test_date TEXT,
        quality_status TEXT DEFAULT 'Pending',
        FOREIGN KEY(batch_id) REFERENCES batches(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS processing (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        stage TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        date TEXT,
        responsible_person TEXT,
        notes TEXT,
        UNIQUE(batch_id, stage),
        FOREIGN KEY(batch_id) REFERENCES batches(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        block_number INTEGER NOT NULL,
        batch_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        previous_hash TEXT NOT NULL,
        current_hash TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        notification_type TEXT DEFAULT 'info',
        is_read INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)
    # Seed users
    users = [
        ("Punitha Varshini", "punitha.varshini@honeychain.demo", "HoneyChain@2026", "beekeeper"),
        ("HoneyChain Admin", "admin@honeychain.demo", "Admin@2026", "admin"),
    ]
    for name, email, pw, role in users:
        if not db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                       (name, email, hash_password(pw), role, now_iso()))
    # Seed hives
    if db.execute("SELECT COUNT(*) c FROM hives").fetchone()["c"] == 0:
        demo_hives = [
            ("H001","Green Valley Hive","Madurai, Tamil Nadu","Apis mellifera","Strong", "2026-08-01",34,62,"High","Healthy"),
            ("H002","Golden Meadow Hive","Coimbatore, Tamil Nadu","Apis cerana","Medium","2026-08-05",38,76,"Medium","Warning"),
            ("H003","Western Ghats Hive","Kerala","Apis cerana","Strong","2026-07-22",33,68,"High","Healthy"),
            ("H004","Mysore Blossom Hive","Karnataka","Apis mellifera","Low","2026-08-10",41,82,"Low","Critical"),
            ("H005","Sahyadri Hive","Maharashtra","Apis mellifera","Strong","2026-07-30",35,61,"High","Healthy"),
        ]
        for h in demo_hives:
            db.execute("""INSERT INTO hives(hive_code,name,location,bee_species,colony_strength,
                installation_date,temperature,humidity,activity_level,status,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", h + (now_iso(),))
    # Seed batches
    if db.execute("SELECT COUNT(*) c FROM batches").fetchone()["c"] == 0:
        hives = db.execute("SELECT id,hive_code,location FROM hives ORDER BY id").fetchall()
        demo = [
            ("HC-2026-0001",hives[0]["id"],"Wildflower Honey",hives[0]["location"],"2026-09-05",25,"Manual","Demo verified batch","Verified"),
            ("HC-2026-0002",hives[1]["id"],"Forest Honey",hives[1]["location"],"2026-09-08",18,"Manual","Pending quality review","Pending"),
            ("HC-2026-0003",hives[2]["id"],"Floral Honey",hives[2]["location"],"2026-09-10",31,"Manual","Verified demo batch","Verified"),
            ("HC-2026-0004",hives[3]["id"],"Wildflower Honey",hives[3]["location"],"2026-09-12",14,"Manual","Rejected demo quality record","Rejected"),
            ("HC-2026-0005",hives[4]["id"],"Blossom Honey",hives[4]["location"],"2026-09-14",27,"Manual","Awaiting processing","Pending"),
        ]
        for b in demo:
            db.execute("""INSERT INTO batches(batch_id,hive_id,honey_type,origin,harvest_date,quantity,
                harvest_method,notes,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""", b + (now_iso(),))
    # Seed processing stages and quality
    stages = ["Harvested","Collected","Quality Tested","Processing","Packaging","Distribution"]
    batches = db.execute("SELECT * FROM batches ORDER BY id").fetchall()
    for b in batches:
        for i, stage in enumerate(stages):
            exists = db.execute("SELECT id FROM processing WHERE batch_id=? AND stage=?", (b["id"],stage)).fetchone()
            if not exists:
                status = "Completed" if (b["status"]=="Verified" and i < 6) else ("Completed" if i == 0 else "Pending")
                db.execute("""INSERT INTO processing(batch_id,stage,status,date,responsible_person,notes)
                              VALUES(?,?,?,?,?,?)""",
                           (b["id"],stage,status,now_iso() if status=="Completed" else None,"Punitha Varshini" if status=="Completed" else None,"Demo record"))
        if not db.execute("SELECT id FROM quality_tests WHERE batch_id=?", (b["id"],)).fetchone():
            qs = "Verified" if b["status"]=="Verified" else ("Rejected" if b["status"]=="Rejected" else "Pending")
            db.execute("""INSERT INTO quality_tests(batch_id,moisture,ph,purity_status,color,aroma,test_center,
                certificate_number,test_date,quality_status) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                       (b["id"],17.8,4.2,"Recorded","Golden Amber","Floral","Demo Lab",
                        f"CERT-{b['batch_id'][-4:]}", "2026-09-15", qs))
    # Seed blockchain if empty
    if db.execute("SELECT COUNT(*) c FROM blocks").fetchone()["c"] == 0:
        for b in batches:
            append_event_db(db, b["batch_id"], "BATCH_CREATED")
            if b["status"] == "Verified":
                append_event_db(db, b["batch_id"], "QUALITY_VERIFIED")
                append_event_db(db, b["batch_id"], "PROCESSING_COMPLETED")
                append_event_db(db, b["batch_id"], "PACKAGING_COMPLETED")
    # Seed notifications
    if db.execute("SELECT COUNT(*) c FROM notifications").fetchone()["c"] == 0:
        punitha = db.execute("SELECT id FROM users WHERE email=?", (users[0][1],)).fetchone()["id"]
        notices = [
            ("High temperature detected in Hive H004.","critical"),
            ("Batch HC-2026-0002 is waiting for quality verification.","warning"),
            ("Batch HC-2026-0001 blockchain record verified.","success"),
        ]
        for msg, typ in notices:
            db.execute("INSERT INTO notifications(user_id,title,message,notification_type,created_at) VALUES(?,?,?,?,?)",
                       (punitha,"HoneyChain Alert",msg,typ,now_iso()))
    db.commit()
    db.close()

def canonical_hash(block_number, batch_id, event_type, timestamp, previous_hash):
    payload = {"blockNumber": block_number, "batchId": batch_id, "eventType": event_type,
               "previousHash": previous_hash, "timestamp": timestamp}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()

def append_event_db(db, batch_id, event_type):
    previous = db.execute("SELECT * FROM blocks ORDER BY block_number DESC LIMIT 1").fetchone()
    number = (previous["block_number"] + 1) if previous else 1
    previous_hash = previous["current_hash"] if previous else "000000"
    ts = now_iso()
    current = canonical_hash(number, batch_id, event_type, ts, previous_hash)
    db.execute("""INSERT INTO blocks(block_number,batch_id,event_type,timestamp,previous_hash,current_hash)
                  VALUES(?,?,?,?,?,?)""", (number,batch_id,event_type,ts,previous_hash,current))
    return current

def verify_chain_db(db):
    blocks = db.execute("SELECT * FROM blocks ORDER BY block_number").fetchall()
    previous_hash = "000000"
    expected_number = 1
    for b in blocks:
        if b["block_number"] != expected_number:
            return False, f"Invalid block number at block {b['block_number']}"
        if b["previous_hash"] != previous_hash:
            return False, f"Previous hash mismatch at block {b['block_number']}"
        expected = canonical_hash(b["block_number"],b["batch_id"],b["event_type"],b["timestamp"],b["previous_hash"])
        if b["current_hash"] != expected:
            return False, f"Hash mismatch at block {b['block_number']}"
        previous_hash = b["current_hash"]
        expected_number += 1
    return True, "Blockchain integrity verified"

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

@app.context_processor
def inject_user():
    return {"current_user": session.get("user_name"), "current_role": session.get("role")}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if len(name) < 2 or "@" not in email or len(password) < 8:
            flash("Please check your details and try again.","error")
            return render_template("register.html")
        db=get_db()
        if db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            db.close(); flash("An account with this email already exists. Please sign in.","error")
            return redirect(url_for("login"))
        db.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES(?,?,?,?,?)",
                   (name,email,hash_password(password),"beekeeper",now_iso()))
        db.commit(); db.close()
        flash("Account created successfully. Please sign in.","success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        db=get_db(); user=db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone(); db.close()
        if user and verify_password(password,user["password_hash"]):
            session["user_id"]=user["id"]; session["user_name"]=user["name"]; session["role"]=user["role"]
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.","error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    db=get_db()
    stats = {
        "hives": db.execute("SELECT COUNT(*) c FROM hives").fetchone()["c"],
        "healthy": db.execute("SELECT COUNT(*) c FROM hives WHERE status='Healthy'").fetchone()["c"],
        "batches": db.execute("SELECT COUNT(*) c FROM batches").fetchone()["c"],
        "verified": db.execute("SELECT COUNT(*) c FROM batches WHERE status='Verified'").fetchone()["c"],
        "pending": db.execute("SELECT COUNT(*) c FROM batches WHERE status='Pending'").fetchone()["c"],
        "honey": db.execute("SELECT COALESCE(SUM(quantity),0) s FROM batches").fetchone()["s"],
        "blocks": db.execute("SELECT COUNT(*) c FROM blocks").fetchone()["c"],
        "alerts": db.execute("SELECT COUNT(*) c FROM notifications WHERE is_read=0 AND notification_type IN ('critical','warning')").fetchone()["c"],
    }
    recent=db.execute("""SELECT b.*,h.hive_code FROM batches b JOIN hives h ON h.id=b.hive_id ORDER BY b.id DESC LIMIT 5""").fetchall()
    db.close()
    return render_template("dashboard.html",stats=stats,recent=recent)

@app.route("/hives", methods=["GET","POST"])
@login_required
def hives():
    db=get_db()
    if request.method=="POST":
        try:
            code=request.form["hive_code"].strip()
            vals=(code,request.form["name"].strip(),request.form["location"].strip(),request.form["bee_species"].strip(),
                  request.form["colony_strength"],request.form.get("installation_date"),float(request.form.get("temperature",34)),
                  float(request.form.get("humidity",60)),request.form.get("activity_level","High"))
            status="Critical" if vals[6]>40 or vals[7]>85 else ("Warning" if vals[6]>37 or vals[7]>75 or vals[4]=="Low" else "Healthy")
            db.execute("""INSERT INTO hives(hive_code,name,location,bee_species,colony_strength,installation_date,
                       temperature,humidity,activity_level,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""", vals+(status,now_iso()))
            db.commit(); flash("Hive added successfully.","success")
        except sqlite3.IntegrityError:
            flash("Hive code already exists.","error")
        except Exception as e:
            flash(f"Could not add hive: {e}","error")
        return redirect(url_for("hives"))
    rows=db.execute("SELECT * FROM hives ORDER BY id").fetchall(); db.close()
    return render_template("hives.html",hives=rows)

@app.route("/hives/<int:hive_id>/simulate", methods=["POST"])
@login_required
def simulate_hive(hive_id):
    import random
    db=get_db()
    h=db.execute("SELECT * FROM hives WHERE id=?", (hive_id,)).fetchone()
    if not h: abort(404)
    temp=round(random.uniform(31,43),1); hum=round(random.uniform(55,88),1)
    strength=random.choice(["Strong","Medium","Low"]); activity=random.choice(["High","Medium","Low"])
    status="Critical" if temp>40 or hum>85 else ("Warning" if temp>37 or hum>75 or strength=="Low" else "Healthy")
    db.execute("""UPDATE hives SET temperature=?,humidity=?,colony_strength=?,activity_level=?,status=? WHERE id=?""",
               (temp,hum,strength,activity,status,hive_id))
    db.execute("""INSERT INTO inspections(hive_id,inspection_date,temperature,humidity,colony_strength,activity_level,notes)
                  VALUES(?,?,?,?,?,?,?)""",(hive_id,now_iso(),temp,hum,strength,activity,"Simulated sensor update"))
    if status != "Healthy":
        uid=session["user_id"]; db.execute("""INSERT INTO notifications(user_id,title,message,notification_type,created_at)
                    VALUES(?,?,?,?,?)""",(uid,"Hive Monitoring Alert",f"Hive {h['hive_code']} requires attention. Temperature {temp}°C, humidity {hum}%.","critical" if status=="Critical" else "warning",now_iso()))
    db.commit(); db.close()
    flash("Simulated hive sensor values updated.","success")
    return redirect(url_for("hives"))

@app.route("/batches", methods=["GET","POST"])
@login_required
def batches():
    db=get_db()
    if request.method=="POST":
        hives=db.execute("SELECT * FROM hives ORDER BY hive_code").fetchall()
        hive_id=int(request.form["hive_id"])
        last=db.execute("SELECT batch_id FROM batches ORDER BY id DESC LIMIT 1").fetchone()
        num=int(last["batch_id"].split("-")[-1])+1 if last else 1
        bid=f"HC-{datetime.now().year}-{num:04d}"
        db.execute("""INSERT INTO batches(batch_id,hive_id,honey_type,origin,harvest_date,quantity,harvest_method,notes,status,created_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?)""",
                   (bid,hive_id,request.form["honey_type"],request.form["origin"],request.form["harvest_date"],
                    float(request.form["quantity"]),request.form.get("harvest_method","Manual"),request.form.get("notes",""),"Pending",now_iso()))
        stages=["Harvested","Collected","Quality Tested","Processing","Packaging","Distribution"]
        batch_row=db.execute("SELECT id FROM batches WHERE batch_id=?", (bid,)).fetchone()
        for i,s in enumerate(stages):
            db.execute("INSERT INTO processing(batch_id,stage,status) VALUES(?,?,?)",(batch_row["id"],s,"Completed" if i==0 else "Pending"))
        append_event_db(db,bid,"BATCH_CREATED")
        db.commit(); db.close()
        flash(f"Batch {bid} created and recorded on the blockchain.","success")
        return redirect(url_for("batch_detail",batch_id=bid))
    rows=db.execute("""SELECT b.*,h.hive_code FROM batches b JOIN hives h ON h.id=b.hive_id ORDER BY b.id DESC""").fetchall()
    hives=db.execute("SELECT * FROM hives ORDER BY hive_code").fetchall()
    db.close()
    return render_template("batches.html",batches=rows,hives=hives)

@app.route("/batches/<batch_id>")
@login_required
def batch_detail(batch_id):
    db=get_db()
    b=db.execute("""SELECT b.*,h.hive_code,h.name hive_name,h.location hive_location FROM batches b
                   JOIN hives h ON h.id=b.hive_id WHERE b.batch_id=?""",(batch_id,)).fetchone()
    if not b: abort(404)
    q=db.execute("SELECT * FROM quality_tests WHERE batch_id=? ORDER BY id DESC LIMIT 1",(b["id"],)).fetchone()
    stages=db.execute("SELECT * FROM processing WHERE batch_id=? ORDER BY id",(b["id"],)).fetchall()
    blocks=db.execute("SELECT * FROM blocks WHERE batch_id=? ORDER BY block_number",(batch_id,)).fetchall()
    db.close()
    score=trace_score(b,q,stages,blocks)
    return render_template("batch_detail.html",batch=b,quality=q,stages=stages,blocks=blocks,score=score)

def trace_score(b,q,stages,blocks):
    score=20 # harvest/batch
    score += 20 if q and q["quality_status"]=="Verified" else (10 if q else 0)
    score += 20 if any(s["stage"]=="Processing" and s["status"]=="Completed" for s in stages) else 0
    score += 20 if any(s["stage"]=="Packaging" and s["status"]=="Completed" for s in stages) else 0
    score += 20 if blocks else 0
    return score

@app.route("/quality/<batch_id>", methods=["POST"])
@login_required
def quality(batch_id):
    db=get_db(); b=db.execute("SELECT * FROM batches WHERE batch_id=?",(batch_id,)).fetchone()
    if not b: abort(404)
    status=request.form.get("quality_status","Pending")
    db.execute("""INSERT INTO quality_tests(batch_id,moisture,ph,purity_status,color,aroma,test_center,certificate_number,test_date,quality_status)
                  VALUES(?,?,?,?,?,?,?,?,?,?)""",
               (b["id"],request.form.get("moisture"),request.form.get("ph"),request.form.get("purity_status"),
                request.form.get("color"),request.form.get("aroma"),request.form.get("test_center"),
                request.form.get("certificate_number"),request.form.get("test_date"),status))
    if status=="Verified":
        db.execute("UPDATE batches SET status='Verified' WHERE id=?",(b["id"],))
        append_event_db(db,batch_id,"QUALITY_VERIFIED")
    elif status=="Rejected":
        db.execute("UPDATE batches SET status='Rejected' WHERE id=?",(b["id"],))
    db.commit(); db.close(); flash("Quality record saved.","success")
    return redirect(url_for("batch_detail",batch_id=batch_id))

@app.route("/processing/<batch_id>/<int:processing_id>/complete", methods=["POST"])
@login_required
def complete_processing(batch_id,processing_id):
    db=get_db()
    row=db.execute("SELECT * FROM processing WHERE id=? AND batch_id=(SELECT id FROM batches WHERE batch_id=?)",(processing_id,batch_id)).fetchone()
    if not row: abort(404)
    db.execute("UPDATE processing SET status='Completed',date=?,responsible_person=?,notes=? WHERE id=?",
               (now_iso(),session.get("user_name"),request.form.get("notes","Completed"),processing_id))
    event_map={"Processing":"PROCESSING_COMPLETED","Packaging":"PACKAGING_COMPLETED","Distribution":"DISTRIBUTION_COMPLETED"}
    if row["stage"] in event_map:
        append_event_db(db,batch_id,event_map[row["stage"]])
    db.commit(); db.close(); flash(f"{row['stage']} completed.","success")
    return redirect(url_for("batch_detail",batch_id=batch_id))

@app.route("/blockchain")
@login_required
def blockchain():
    db=get_db(); blocks=db.execute("SELECT * FROM blocks ORDER BY block_number DESC").fetchall()
    db.close(); return render_template("blockchain.html",blocks=blocks)

@app.route("/blockchain/verify", methods=["POST"])
@login_required
def verify_blockchain():
    db=get_db(); valid,msg=verify_chain_db(db); db.close()
    return jsonify({"valid":valid,"message":msg})

@app.route("/verify/<batch_id>")
def public_verify(batch_id):
    db=get_db()
    b=db.execute("""SELECT b.*,h.hive_code,h.name hive_name FROM batches b JOIN hives h ON h.id=b.hive_id WHERE b.batch_id=?""",(batch_id,)).fetchone()
    if not b: return render_template("verify.html",not_found=True,batch_id=batch_id)
    q=db.execute("SELECT * FROM quality_tests WHERE batch_id=? ORDER BY id DESC LIMIT 1",(b["id"],)).fetchone()
    stages=db.execute("SELECT * FROM processing WHERE batch_id=? ORDER BY id",(b["id"],)).fetchall()
    blocks=db.execute("SELECT * FROM blocks WHERE batch_id=? ORDER BY block_number",(batch_id,)).fetchall()
    valid,_=verify_chain_db(db); db.close()
    score=trace_score(b,q,stages,blocks)
    return render_template("verify.html",batch=b,quality=q,stages=stages,blocks=blocks,valid=valid,score=score,not_found=False)

@app.route("/qr/<batch_id>.png")
def qr_code(batch_id):
    db=get_db(); exists=db.execute("SELECT batch_id FROM batches WHERE batch_id=?",(batch_id,)).fetchone(); db.close()
    if not exists: abort(404)
    target=url_for("public_verify",batch_id=batch_id,_external=True)
    img=qrcode.make(target)
    buf=BytesIO(); img.save(buf,"PNG"); buf.seek(0)
    return send_file(buf,mimetype="image/png",download_name=f"{batch_id}.png")

@app.route("/monitoring")
@login_required
def monitoring():
    db=get_db(); hives=db.execute("SELECT * FROM hives ORDER BY hive_code").fetchall(); db.close()
    return render_template("monitoring.html",hives=hives)

@app.route("/analytics")
@login_required
def analytics():
    db=get_db()
    locations=db.execute("SELECT origin,COALESCE(SUM(quantity),0) total FROM batches GROUP BY origin ORDER BY total DESC").fetchall()
    statuses=db.execute("SELECT status,COUNT(*) total FROM batches GROUP BY status").fetchall()
    db.close(); return render_template("analytics.html",locations=locations,statuses=statuses)

@app.route("/notifications")
@login_required
def notifications():
    db=get_db(); rows=db.execute("SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC",(session["user_id"],)).fetchall(); db.close()
    return render_template("notifications.html",notifications=rows)

@app.route("/notifications/<int:nid>/read",methods=["POST"])
@login_required
def notification_read(nid):
    db=get_db(); db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?",(nid,session["user_id"])); db.commit(); db.close()
    return redirect(url_for("notifications"))

@app.route("/admin")
@admin_required
def admin():
    db=get_db()
    users=db.execute("SELECT id,name,email,role,created_at FROM users ORDER BY id").fetchall()
    batches=db.execute("SELECT b.*,h.hive_code FROM batches b JOIN hives h ON h.id=b.hive_id ORDER BY b.id DESC").fetchall()
    db.close(); return render_template("admin.html",users=users,batches=batches)

@app.route("/api/dashboard")
@login_required
def api_dashboard():
    db=get_db()
    data={
        "hives":db.execute("SELECT COUNT(*) c FROM hives").fetchone()["c"],
        "batches":db.execute("SELECT COUNT(*) c FROM batches").fetchone()["c"],
        "verified":db.execute("SELECT COUNT(*) c FROM batches WHERE status='Verified'").fetchone()["c"],
        "blocks":db.execute("SELECT COUNT(*) c FROM blocks").fetchone()["c"],
    }
    db.close(); return jsonify(data)

@app.errorhandler(403)
def forbidden(_): return render_template("error.html",code=403,message="You do not have permission to access this page."),403

@app.errorhandler(404)
def not_found(_): return render_template("error.html",code=404,message="The requested page was not found."),404

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=True)
