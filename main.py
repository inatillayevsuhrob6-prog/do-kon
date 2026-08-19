import os, sqlite3, threading, io, time, re, hashlib, json, glob
from datetime import datetime
from flask import Flask, request, redirect, render_template_string, send_file, jsonify, g, session

BOT_TOKEN = "8863204152:AAF-VbLwrDrnSl832BZchmMA6HhJmbfQgjs"
APP_URL = "https://smartstore-web-dvse.onrender.com"

# Ma'lumotlar papkasi
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)
DB_REGISTRY_PATH = os.path.join(DATA_DIR, "db_registry.json")
DB_PATH = os.path.join(DATA_DIR, "default.db")

app = Flask(__name__)
app.secret_key = "smartstore-secret-key-2024-pro"
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

# ═══════════════════════════════════════
# 🗄️ DATABASE REGISTRY (JSON)
# ═══════════════════════════════════════
def load_registry():
    try:
        if os.path.exists(DB_REGISTRY_PATH):
            with open(DB_REGISTRY_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_registry(registry):
    try:
        with open(DB_REGISTRY_PATH, 'w', encoding='utf-8') as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("Registry save error:", e)

def get_user_id():
    tg_user = request.args.get('tg_user')
    if tg_user and tg_user.isdigit():
        uid = 'tg_' + tg_user
        session['session_id'] = uid
        session['tg_user'] = tg_user
        return uid
    if session.get('tg_user'):
        uid = 'tg_' + str(session['tg_user'])
        session['session_id'] = uid
        return uid
    if 'session_id' not in session:
        session['session_id'] = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
    return session['session_id']

def ensure_session_id():
    tg_user = request.args.get('tg_user')
    if tg_user and tg_user.isdigit():
        session['session_id'] = 'tg_' + tg_user
        session['tg_user'] = tg_user
        return session['session_id']
    if session.get('tg_user'):
        session['session_id'] = 'tg_' + str(session['tg_user'])
        return session['session_id']
    if 'session_id' not in session:
        session['session_id'] = hashlib.sha256(os.urandom(32)).hexdigest()[:32]
    return session['session_id']

def get_user_db_path():
    db_name = session.get('db_name')
    if not db_name or not re.match(r'^[a-zA-Z0-9_]+$', db_name):
        return DB_PATH
    registry = load_registry()
    if db_name not in registry:
        return DB_PATH
    entry = registry[db_name]
    current_session = get_user_id()
    if entry.get('owner_session') == current_session:
        return os.path.join(DATA_DIR, db_name + ".db")
    if current_session in entry.get('allowed_sessions', []):
        return os.path.join(DATA_DIR, db_name + ".db")
    session.pop('db_name', None)
    return DB_PATH

def get_db():
    if "db" not in g:
        db_path = get_user_db_path()
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.executescript("""
            CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, barcode TEXT UNIQUE NOT NULL, price REAL NOT NULL CHECK(price>=0), min_stock INTEGER DEFAULT 5, stock INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL NOT NULL, payment TEXT NOT NULL, customer_phone TEXT, customer_name TEXT DEFAULT '', debt REAL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS sale_items (id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL, product_id INTEGER NOT NULL, qty INTEGER NOT NULL, price REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS debts (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL, total REAL DEFAULT 0, paid REAL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        g.db.commit()
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()

def db_error(msg):
    return render_template_string("<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><style>" + CSS + "</style></head><body>" + NAV_HTML + "<div style='padding:24px;max-width:500px;margin:60px auto;'><div class='card' style='text-align:center;padding:40px;'><div style='font-size:56px;margin-bottom:16px;'>❌</div><h1 style='font-size:24px;margin-bottom:12px;color:var(--red);'>Xato</h1><p style='color:var(--dim);margin-bottom:24px;'>" + msg + "</p><a href='/db' class='btn btn-primary' style='padding:16px;'>← Orqaga</a></div></div></body></html>")

# ═══════════════════════════════════════
# 🎨 PREMIUM CSS
# ═══════════════════════════════════════
CSS = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');:root{--bg:#0a0e1a;--card:#111827;--border:#1e293b;--primary:#3b82f6;--pg:rgba(59,130,246,.3);--green:#10b981;--gg:rgba(16,185,129,.3);--red:#ef4444;--yellow:#f59e0b;--text:#f1f5f9;--dim:#94a3b8}*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;-webkit-font-smoothing:antialiased}.nav{background:rgba(17,24,39,.95);backdrop-filter:blur(20px);border-bottom:1px solid var(--border);padding:0 24px;height:64px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}.nav-brand{font-size:22px;font-weight:800;background:linear-gradient(135deg,#3b82f6,#10b981);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.nav-links{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.nav-links a{color:var(--dim);text-decoration:none;padding:10px 16px;border-radius:12px;font-size:14px;font-weight:600;transition:.2s}.nav-links a:hover{color:var(--text);background:rgba(255,255,255,.05)}.card{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:24px;transition:.3s}.btn{padding:14px 24px;border-radius:12px;border:none;font-weight:700;font-size:15px;cursor:pointer;transition:.2s;display:inline-flex;align-items:center;gap:8px;text-decoration:none;color:#fff}.btn:active{transform:scale(.97)}.btn-primary{background:linear-gradient(135deg,#3b82f6,#2563eb);box-shadow:0 4px 15px var(--pg)}.btn-green{background:linear-gradient(135deg,#10b981,#059669);box-shadow:0 4px 15px var(--gg)}.btn-red{background:linear-gradient(135deg,#ef4444,#dc2626)}.btn-gray{background:#334155}.btn-sm{padding:10px 16px;font-size:13px;border-radius:10px}.input{width:100%;padding:14px 16px;border-radius:12px;background:rgba(15,23,42,.8);color:var(--text);border:2px solid var(--border);font-size:15px;font-family:inherit;outline:none;transition:.2s}.input:focus{border-color:var(--primary)}.grid{display:grid;gap:16px}.g2{grid-template-columns:repeat(2,1fr)}.g3{grid-template-columns:repeat(3,1fr)}.g4{grid-template-columns:repeat(4,1fr)}.stat-card{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:20px;position:relative;overflow:hidden}.stat-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--primary),var(--green))}.stat-card.green::before{background:linear-gradient(90deg,#10b981,#34d399)}.stat-card.yellow::before{background:linear-gradient(90deg,#f59e0b,#fbbf24)}.stat-card.red::before{background:linear-gradient(90deg,#ef4444,#f87171)}.stat-label{font-size:13px;color:var(--dim);margin-bottom:8px;font-weight:600}.stat-value{font-size:30px;font-weight:900;letter-spacing:-1px}.table-wrap{overflow-x:auto;border-radius:20px;border:1px solid var(--border)}table{width:100%;border-collapse:collapse}th{background:rgba(15,23,42,.5);padding:14px 16px;text-align:left;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:var(--dim);font-weight:700}td{padding:14px 16px;border-top:1px solid var(--border);font-size:14px}tr:hover td{background:rgba(255,255,255,.02)}.badge{display:inline-block;padding:5px 12px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:.5px}.badge-green{background:rgba(16,185,129,.15);color:#34d399}.badge-red{background:rgba(239,68,68,.15);color:#f87171}.badge-blue{background:rgba(59,130,246,.15);color:#60a5fa}.badge-yellow{background:rgba(245,158,11,.15);color:#fbbf24}.cart-item{display:flex;justify-content:space-between;align-items:center;padding:14px 16px;background:rgba(15,23,42,.5);border:1px solid var(--border);border-radius:12px;margin-bottom:8px}.qty-btn{width:40px;height:40px;border-radius:10px;border:none;background:var(--primary);color:#fff;font-weight:700;font-size:18px;cursor:pointer}.total-bar{background:linear-gradient(135deg,rgba(16,185,129,.1),rgba(59,130,246,.1));border:1px solid rgba(16,185,129,.2);border-radius:20px;padding:20px 24px;margin-top:16px}.total-amount{font-size:36px;font-weight:900;color:var(--green);letter-spacing:-1px}.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(8px);z-index:200;align-items:center;justify-content:center}.modal-overlay.active{display:flex}.modal{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:32px;max-width:480px;width:90%}.mnav{display:none}.success-banner{padding:16px 20px;margin-bottom:20px;background:rgba(16,185,129,.1);border:2px solid var(--green);border-radius:14px;display:flex;align-items:center;gap:12px;animation:fadeIn .4s ease}.db-badge{display:inline-block;padding:4px 10px;border-radius:8px;font-size:11px;font-weight:700;background:rgba(59,130,246,.15);color:#60a5fa;margin-left:8px}@keyframes fadeIn{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:translateY(0)}}@media(max-width:768px){.g2,.g3,.g4{grid-template-columns:1fr}.nav{padding:0 16px;height:60px}.nav-brand{font-size:18px}.nav-links{display:none}body{padding-bottom:80px}.mnav{display:flex;position:fixed;bottom:0;left:0;right:0;background:rgba(17,24,39,.98);backdrop-filter:blur(20px);border-top:1px solid var(--border);z-index:100;padding:8px 4px calc(8px + env(safe-area-inset-bottom));justify-content:space-around}.mnav a{display:flex;flex-direction:column;align-items:center;gap:3px;color:var(--dim);text-decoration:none;font-size:22px;padding:6px 12px;border-radius:10px}.mnav a:active{background:rgba(59,130,246,.15);color:var(--primary)}.mnav span{font-size:10px;font-weight:700}}"

NAV_HTML = "<div class='nav'><div class='nav-brand'>🏪 SmartStore</div><div class='nav-links'><a href='/dashboard'>📊 Panel</a><a href='/pos'>🛒 Kassa</a><a href='/products'>📦 Mahsulot</a><a href='/sales'>🧾 Sotuv</a><a href='/debts'>💳 Qarzdor</a><a href='/reports'>📈 Hisobot</a><a href='/db' style='color:var(--primary);'>🗄️ Baza</a><button onclick=\"document.getElementById('db-popup').classList.add('active')\" style=\"background:rgba(59,130,246,.15);border:1px solid rgba(59,130,246,.3);color:var(--primary);font-size:20px;padding:8px 14px;border-radius:10px;cursor:pointer;font-weight:700;\">⋮</button></div></div><div id=\"db-popup\" class=\"modal-overlay\" onclick=\"if(event.target===this)this.classList.remove('active')\"><div class=\"modal\" style=\"max-width:360px;\"><h3 style=\"margin-bottom:16px;text-align:center;font-size:18px;\">🗄️ Database Menyusi</h3><a href=\"/db\" class=\"btn btn-primary\" style=\"width:100%;justify-content:center;margin-bottom:10px;padding:16px;\">🗄️ Bazani boshqarish</a><a href=\"/db/create\" class=\"btn btn-green\" style=\"width:100%;justify-content:center;margin-bottom:10px;padding:16px;\" onclick=\"event.preventDefault();window.location.href='/db'\">➕ Yangi baza</a><button onclick=\"document.getElementById('db-popup').classList.remove('active')\" class=\"btn btn-gray\" style=\"width:100%;justify-content:center;padding:16px;\">✕ Yopish</button></div></div>"

MOBILE_NAV = "<div class='mnav'><a href='/dashboard'>📊<span>Panel</span></a><a href='/pos'>🛒<span>Kassa</span></a><a href='/products'>📦<span>Mahsulot</span></a><a href='/sales'>🧾<span>Sotuv</span></a><a href='/debts'>💳<span>Qarzdor</span></a><a href='/db'>🗄️<span>Baza</span></a></div>"

TG_SCRIPT = "<script src='https://telegram.org/js/telegram-web-app.js'></script><script>if(window.Telegram&&Telegram.WebApp){Telegram.WebApp.ready();Telegram.WebApp.expand();}</script>"

def RP(tpl, **ctx):
    full = "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no'><title>SmartStore</title>" + TG_SCRIPT + "<style>" + CSS + "</style></head><body>" + NAV_HTML + tpl + MOBILE_NAV + "</body></html>"
    return render_template_string(full, **ctx)

# ═══════════════════════════════════════
# 🏠 ROUTES
# ═══════════════════════════════════════
@app.route("/")
def index():
    tg_user = request.args.get('tg_user')
    if tg_user and tg_user.isdigit():
        session['session_id'] = 'tg_' + tg_user
        session['tg_user'] = tg_user
    ensure_session_id()
    return redirect("/dashboard")

@app.route("/db")
def db_page():
    ensure_session_id()
    db_name = session.get('db_name')
    registry = load_registry()
    current_session = get_user_id()
    my_dbs = [{"name": name, "password": data.get("password", ""), "is_owner": True} for name, data in registry.items() if data.get('owner_session') == current_session]
    existing_dbs = list(registry.keys())
    
    return RP("""<div style="padding:24px;max-width:600px;margin:0 auto;">
    <h1 style="font-size:28px;font-weight:800;margin-bottom:24px;">🗄️ Database Boshqaruvi</h1>
    {%if db_name and db_name != 'default'%}
    <div class="card" style="margin-bottom:20px;border-color:rgba(16,185,129,.4);background:rgba(16,185,129,.05);">
        <div style="display:flex;align-items:center;gap:16px;">
            <div style="font-size:52px;">✅</div>
            <div style="flex:1;">
                <div style="font-size:13px;color:var(--dim);font-weight:600;">Faol database</div>
                <div style="font-size:24px;font-weight:800;color:var(--green);margin-top:4px;">{{db_name}}</div>
            </div>
        </div>
    </div>
    <div class="grid g2">
        <a href="/dashboard" class="btn btn-primary" style="padding:18px;justify-content:center;">📊 Panelga o'tish</a>
        <a href="/db/disconnect" class="btn btn-red" style="padding:18px;justify-content:center;">🔌 Uzish</a>
    </div>
    {%else%}
    <div class="card" style="margin-bottom:16px;border-color:rgba(59,130,246,.3);background:rgba(59,130,246,.05);">
        <div style="display:flex;align-items:center;gap:12px;"><div style="font-size:36px;">ℹ️</div>
        <div style="color:var(--dim);font-size:14px;">Hozir <strong style="color:var(--primary);">default baza</strong>da ishlaysiz. Alohida baza yaratib, ma'lumotlaringizni ajratishingiz mumkin.</div></div>
    </div>
    {%if my_dbs%}
    <div class="card" style="margin-bottom:16px;border-color:rgba(16,185,129,.3);">
        <h3 style="font-size:16px;margin-bottom:12px;color:var(--green);">📋 Sizning bazalaringiz ({{my_dbs|length}})</h3>
        {%for db in my_dbs%}
        <div style="padding:12px 0;border-bottom:1px solid var(--border);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <div>
                    <span style="font-weight:700;font-size:16px;">🗄️ {{db.name}}</span>
                    <span class="badge badge-green" style="margin-left:8px;">👑 Egasi</span>
                </div>
                <a href="/db/switch/{{db.name}}" class="btn btn-primary btn-sm">O'tish</a>
            </div>
            <div style="display:flex;align-items:center;gap:10px;padding:8px 12px;background:rgba(59,130,246,.1);border-radius:10px;">
                <span style="font-size:12px;color:var(--dim);">🔑 Parol:</span>
                <code style="font-family:monospace;font-size:14px;color:#60a5fa;font-weight:700;letter-spacing:1px;">{{db.password}}</code>
                <button onclick="navigator.clipboard.writeText('{{db.password}}');this.textContent='✅';setTimeout(()=>this.textContent='📋',1500)" style="background:none;border:none;color:var(--dim);cursor:pointer;font-size:14px;padding:4px 8px;" title="Nusxalash">📋</button>
            </div>
        </div>
        {%endfor%}
    </div>
    {%endif%}
    <div class="card" style="margin-bottom:20px;">
        <h2 style="font-size:20px;margin-bottom:16px;">➕ Yangi database yaratish</h2>
        <p style="color:var(--dim);font-size:14px;margin-bottom:16px;">Faqat sizga tegishli alohida baza</p>
        <form method="POST" action="/db/create">
            <label style="font-size:13px;color:var(--dim);margin-bottom:6px;display:block;">Database nomi</label>
            <input class="input" name="db_name" placeholder="masalan: myshop" required pattern="[a-zA-Z0-9_]+" title="Faqat harf, raqam, underscore">
            <label style="font-size:13px;color:var(--dim);margin-bottom:6px;display:block;margin-top:12px;">Parol</label>
            <input class="input" name="password" type="password" placeholder="Kamida 4 belgi" required minlength="4">
            <button class="btn btn-green" style="width:100%;padding:18px;margin-top:20px;justify-content:center;font-size:16px;">🚀 Yaratish</button>
        </form>
    </div>
    {%if existing_dbs%}
    <div class="card">
        <h2 style="margin-bottom:16px;">🔗 Mavjud bazaga ulanish</h2>
        <p style="color:var(--dim);font-size:14px;margin-bottom:16px;">Boshqa foydalanuvchining bazasiga parol bilan kiring</p>
        <form method="POST" action="/db/connect">
            <label style="font-size:13px;color:var(--dim);margin-bottom:6px;display:block;">Database nomi</label>
            <input class="input" name="db_name" placeholder="Baza nomi" required pattern="[a-zA-Z0-9_]+">
            <label style="font-size:13px;color:var(--dim);margin-bottom:6px;display:block;margin-top:12px;">Parol</label>
            <input class="input" name="password" type="password" placeholder="Parol" required>
            <button class="btn btn-primary" style="width:100%;padding:18px;margin-top:20px;justify-content:center;font-size:16px;">🔌 Ulanish</button>
        </form>
    </div>
    {%endif%}
    {%endif%}
    </div>""", db_name=db_name, my_dbs=my_dbs, existing_dbs=existing_dbs)

@app.route("/db/create", methods=["POST"])
def db_create():
    ensure_session_id()
    db_name = request.form.get("db_name", "").strip().lower()
    password = request.form.get("password", "")
    
    if not re.match(r'^[a-zA-Z0-9_]+$', db_name):
        return db_error("Noto'g'ri nom! Faqat harf, raqam, underscore.")
    if len(password) < 4:
        return db_error("Parol kamida 4 ta belgi bo'lsin!")
    
    db_path = os.path.join(DATA_DIR, db_name + ".db")
    registry = load_registry()
    
    if db_name in registry:
        return db_error("Bu nom allaqachon mavjud! Boshqa nom tanlang yoki ulaning.")
    
    current_session = get_user_id()
    registry[db_name] = {
        "password": password,
        "owner_session": current_session,
        "allowed_sessions": [current_session],
        "created_at": datetime.now().isoformat()
    }
    save_registry(registry)
    
    db = sqlite3.connect(db_path)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, barcode TEXT UNIQUE NOT NULL, price REAL NOT NULL CHECK(price>=0), min_stock INTEGER DEFAULT 5, stock INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL NOT NULL, payment TEXT NOT NULL, customer_phone TEXT, customer_name TEXT DEFAULT '', debt REAL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sale_items (id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL, product_id INTEGER NOT NULL, qty INTEGER NOT NULL, price REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS debts (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL, total REAL DEFAULT 0, paid REAL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    """)
    db.commit()
    db.close()
    
    session['db_name'] = db_name
    session['db_message'] = "✅ Database '" + db_name + "' yaratildi! 🔑 Parol: " + password
    return redirect("/dashboard")

@app.route("/db/connect", methods=["POST"])
def db_connect():
    ensure_session_id()
    db_name = request.form.get("db_name", "").strip().lower()
    password = request.form.get("password", "")
    
    if not re.match(r'^[a-zA-Z0-9_]+$', db_name):
        return db_error("Noto'g'ri nom!")
    
    registry = load_registry()
    
    if db_name not in registry:
        return db_error("Bu nomda database yo'q!")
    
    entry = registry[db_name]
    saved_password = entry.get("password", "")
    current_session = get_user_id()
    
    if entry.get('owner_session') == current_session:
        session['db_name'] = db_name
        session['db_message'] = "O'z bazangizga o'tdingiz: " + db_name
        return redirect("/dashboard")
    
    if password != saved_password:
        return db_error("Noto'g'ri parol!")
    
    if current_session not in entry.get('allowed_sessions', []):
        entry.setdefault('allowed_sessions', []).append(current_session)
        registry[db_name] = entry
        save_registry(registry)
    
    session['db_name'] = db_name
    session['db_message'] = "Database '" + db_name + "' ga parol bilan ulandi!"
    return redirect("/dashboard")

@app.route("/db/switch/<db_name>")
def db_switch(db_name):
    ensure_session_id()
    registry = load_registry()
    current_session = get_user_id()
    
    if db_name not in registry:
        return db_error("Baza topilmadi!")
    
    entry = registry[db_name]
    if entry.get('owner_session') != current_session and current_session not in entry.get('allowed_sessions', []):
        return db_error("Bu bazaga kirish huquqi yo'q!")
    
    session['db_name'] = db_name
    session['db_message'] = "Database '" + db_name + "' ga o'tildi!"
    return redirect("/dashboard")

@app.route("/db/disconnect")
def db_disconnect():
    current_uid = get_user_id()
    db_name = session.get('db_name')
    
    if db_name and db_name != 'default':
        registry = load_registry()
        if db_name in registry:
            entry = registry[db_name]
            owner = entry.get('owner_session', '')
            allowed = entry.get('allowed_sessions', [])
            
            if owner == current_uid:
                pass
            elif current_uid in allowed:
                allowed.remove(current_uid)
                entry['allowed_sessions'] = allowed
                registry[db_name] = entry
                save_registry(registry)
    
    session.pop('db_name', None)
    session.pop('db_message', None)
    return redirect("/dashboard")

@app.route("/dashboard")
def dashboard():
    ensure_session_id()
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    ts = db.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE date(created_at)=?", (today,)).fetchone()[0]
    tc = db.execute("SELECT COUNT(*) FROM sales WHERE date(created_at)=?", (today,)).fetchone()[0]
    tp = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    ls = db.execute("SELECT COUNT(*) FROM products WHERE stock<=min_stock").fetchone()[0]
    td = db.execute("SELECT COALESCE(SUM(total),0) FROM debts WHERE total>0").fetchone()[0]
    ws = db.execute("SELECT date(created_at) d,SUM(total) s FROM sales WHERE created_at>=date('now','-7 days') GROUP BY d ORDER BY d").fetchall()
    top = db.execute("SELECT p.name,SUM(si.qty) t FROM sale_items si JOIN products p ON p.id=si.product_id GROUP BY si.product_id ORDER BY t DESC LIMIT 5").fetchall()
    
    db_msg = session.pop('db_message', None)
    db_name = session.get('db_name', 'default')
    db_badge = '<span class="db-badge">🗄️ ' + db_name + '</span>' if db_name != 'default' else '<span class="db-badge" style="background:rgba(148,163,184,.15);color:var(--dim);">📁 Default</span>'
    banner = '<div class="success-banner"><span style="font-size:26px;">🗄️</span><span style="font-size:15px;font-weight:700;color:var(--green);">' + db_msg + '</span></div>' if db_msg else ''
    
    return RP(banner + """<div style="padding:24px;max-width:1400px;margin:0 auto;">
    <h1 style="font-size:28px;font-weight:800;margin-bottom:24px;">📊 Dashboard """ + db_badge + """</h1>
    <div class="grid g4" style="margin-bottom:24px;">
        <div class="stat-card"><div class="stat-label">💰 Bugungi savdo</div><div class="stat-value">{{"{:,.0f}".format(ts)}}</div></div>
        <div class="stat-card green"><div class="stat-label">🧾 Cheklar</div><div class="stat-value">{{tc}}</div></div>
        <div class="stat-card yellow"><div class="stat-label">📦 Mahsulotlar</div><div class="stat-value">{{tp}}</div></div>
        <div class="stat-card red"><div class="stat-label">⚠️ Kam qoldiq</div><div class="stat-value">{{ls}}</div></div></div>
    <div class="grid g2">
        <div class="card"><h2 style="margin-bottom:16px;font-size:18px;">🏆 Top 5</h2>{%for p in top%}<div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border);"><span>{{p.name}}</span><span class="badge badge-blue">{{p.t}} dona</span></div>{%else%}<p style="color:var(--dim);text-align:center;padding:20px;">Hali savdo yo'q</p>{%endfor%}</div>
        <div class="card"><h2 style="margin-bottom:16px;font-size:18px;">📈 7 kunlik</h2>{%for s in ws%}<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);"><span style="color:var(--dim);font-size:13px;">{{s.d}}</span><span style="color:var(--green);font-weight:700;">{{"{:,.0f}".format(s.s)}}</span></div>{%endfor%}</div></div>
    {%if td>0%}<div class="card" style="margin-top:24px;border-color:rgba(245,158,11,.3);"><div style="display:flex;justify-content:space-between;align-items:center;"><div><div style="font-size:14px;color:var(--dim);">💸 Jami qarz</div><div style="font-size:28px;font-weight:800;color:var(--yellow);margin-top:4px;">{{"{:,.0f}".format(td)}} so'm</div></div><a href="/debts" class="btn btn-primary">Qarzdorlar →</a></div></div>{%endif%}</div>""", ts=ts, tc=tc, tp=tp, ls=ls, td=td, ws=ws, top=top)

@app.route("/products")
def products_list():
    ensure_session_id()
    db = get_db()
    q = request.args.get("q", "")
    rows = db.execute("SELECT * FROM products WHERE name LIKE ? OR barcode LIKE ? ORDER BY id DESC", ("%"+q+"%", "%"+q+"%")).fetchall() if q else db.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    low = [r for r in rows if r["stock"] <= r["min_stock"]]
    return RP("""<div style="padding:24px;max-width:1200px;margin:0 auto;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:12px;"><h1 style="font-size:28px;font-weight:800;">📦 Mahsulotlar <span style="color:var(--dim);font-size:16px;">({{rows|length}})</span></h1><a href="/products/new" class="btn btn-green">➕ Yangi</a></div>
    <form method="GET" style="display:flex;gap:8px;margin-bottom:20px;"><input class="input" name="q" value="{{q}}" placeholder="🔍 Qidiruv..." style="margin:0;"><button class="btn btn-primary">Qidirish</button></form>
    {%if low%}<div class="card" style="margin-bottom:20px;border-color:rgba(239,68,68,.4);"><h3 style="color:var(--red);margin-bottom:10px;">⚠️ Kam qoldiq ({{low|length}})</h3>{%for p in low[:5]%}<div style="padding:4px 0;font-size:13px;">• {{p.name}} — {{p.stock}}/{{p.min_stock}}</div>{%endfor%}</div>{%endif%}
    <div class="table-wrap"><table><thead><tr><th>Nomi</th><th>Barcode</th><th>Narxi</th><th>Qoldiq</th><th>Holat</th><th>Amallar</th></tr></thead><tbody>
    {%for p in rows%}<tr><td><strong>{{p.name}}</strong></td><td style="font-family:monospace;color:var(--dim);">{{p.barcode}}</td><td style="font-weight:600;">{{"{:,.0f}".format(p.price)}}</td><td>{{p.stock}}</td>
    <td>{%if p.stock<=p.min_stock%}<span class="badge badge-red">KAM</span>{%else%}<span class="badge badge-green">OK</span>{%endif%}</td>
    <td><a href="/products/{{p.id}}/edit" class="btn btn-gray btn-sm">✏️</a><form method="POST" action="/products/{{p.id}}/delete" style="display:inline;" onsubmit="return confirm('Ochirilsinmi?')"><button class="btn btn-red btn-sm">🗑</button></form></td></tr>
    {%else%}<tr><td colspan="6" style="text-align:center;color:var(--dim);padding:50px;">Mahsulot yo'q</td></tr>{%endfor%}</tbody></table></div></div>""", rows=rows, q=q, low=low)

@app.route("/products/new", methods=["GET", "POST"])
def product_new():
    ensure_session_id()
    if request.method == "POST":
        db = get_db()
        try:
            db.execute("INSERT INTO products(name,barcode,price,min_stock,stock) VALUES(?,?,?,?,?)", (request.form["name"].strip(), request.form["barcode"].strip(), float(request.form["price"]), int(request.form.get("min_stock", 5)), int(request.form.get("stock", 0))))
            db.commit()
            return redirect("/products")
        except sqlite3.IntegrityError:
            return "❌ Barcode mavjud", 400
    bc = request.args.get("barcode", "")
    return RP("""<div style="padding:24px;max-width:600px;margin:0 auto;"><div class="card"><h1 style="margin-bottom:24px;font-size:22px;">➕ Yangi mahsulot</h1><form method="POST">
    <label style="font-size:13px;color:var(--dim);margin-bottom:6px;display:block;">Nomi *</label><input class="input" name="name" required placeholder="Coca-Cola 1.5L">
    <label style="font-size:13px;color:var(--dim);margin-bottom:6px;display:block;">Shtrix-kod *</label><input class="input" name="barcode" value="{{bc}}" required>
    <label style="font-size:13px;color:var(--dim);margin-bottom:6px;display:block;">Narxi *</label><input class="input" type="number" step="0.01" name="price" required>
    <div class="grid g2" style="margin-top:4px;"><div><label style="font-size:13px;color:var(--dim);margin-bottom:6px;display:block;">Min qoldiq</label><input class="input" type="number" name="min_stock" value="5"></div>
    <div><label style="font-size:13px;color:var(--dim);margin-bottom:6px;display:block;">Qoldiq</label><input class="input" type="number" name="stock" value="0"></div></div>
    <button class="btn btn-green" style="width:100%;margin-top:20px;justify-content:center;font-size:16px;padding:16px;">💾 Saqlash</button></form></div></div>""", bc=bc)

@app.route("/products/<int:pid>/edit", methods=["GET", "POST"])
def product_edit(pid):
    ensure_session_id()
    db = get_db()
    if request.method == "POST":
        db.execute("UPDATE products SET name=?,barcode=?,price=?,min_stock=?,stock=? WHERE id=?", (request.form["name"], request.form["barcode"], float(request.form["price"]), int(request.form["min_stock"]), int(request.form["stock"]), pid))
        db.commit()
        return redirect("/products")
    p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p:
        return "Yo'q", 404
    return RP("""<div style="padding:24px;max-width:600px;margin:0 auto;"><div class="card"><h1 style="margin-bottom:24px;font-size:22px;">✏️ Tahrirlash</h1><form method="POST">
    <input class="input" name="name" value="{{p.name}}" required><input class="input" name="barcode" value="{{p.barcode}}" required>
    <input class="input" type="number" step="0.01" name="price" value="{{p.price}}" required>
    <div class="grid g2"><input class="input" type="number" name="min_stock" value="{{p.min_stock}}"><input class="input" type="number" name="stock" value="{{p.stock}}"></div>
    <button class="btn btn-green" style="width:100%;margin-top:20px;justify-content:center;font-size:16px;padding:16px;">💾 Saqlash</button></form></div></div>""", p=p)

@app.route("/products/<int:pid>/delete", methods=["POST"])
def product_delete(pid):
    ensure_session_id()
    db = get_db()
    db.execute("DELETE FROM products WHERE id=?", (pid,))
    db.commit()
    return redirect("/products")

@app.route("/pos")
def pos():
    ensure_session_id()
    return RP("""<script src="https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js"></script>
    <div style="padding:24px;max-width:1100px;margin:0 auto;"><h1 style="font-size:28px;font-weight:800;margin-bottom:24px;">🛒 Kassa</h1>
    <div class="grid g2"><div class="card"><h2 style="margin-bottom:16px;font-size:18px;">📷 Professional Skaner</h2>
    <div style="display:flex;gap:8px;margin-bottom:16px;"><input id="mb" class="input" placeholder="Barcode kiriting..." style="margin:0;" autofocus><button class="btn btn-primary" onclick="ms()">🔍</button></div>
    <button class="btn btn-green" style="width:100%;margin-bottom:12px;justify-content:center;" onclick="ss()">📷 Kamera</button>
    <div id="sr" style="border-radius:12px;overflow:hidden;min-height:200px;background:#000;"></div>
    <button class="btn btn-red" style="width:100%;margin-top:12px;justify-content:center;display:none;" id="sb" onclick="xs()">⏹ Stop</button></div>
    <div class="card"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;"><h2 style="font-size:18px;">🧺 Savat</h2><button class="btn btn-red btn-sm" onclick="cc()">🗑</button></div>
    <div id="ct" style="min-height:200px;max-height:400px;overflow-y:auto;"></div>
    <div class="total-bar"><div style="font-size:13px;color:var(--dim);">JAMI</div><div class="total-amount" id="tt">0 so'm</div></div>
    <label style="display:flex;align-items:center;gap:10px;margin-top:16px;color:var(--dim);"><input type="checkbox" id="snd" checked> 🔊 Ovoz</label>
    <button class="btn btn-green" style="width:100%;margin-top:16px;justify-content:center;font-size:17px;padding:18px;" onclick="oc()">💳 To'lov</button></div></div></div>
    <div id="cm" class="modal-overlay"><div class="modal"><h2 style="margin-bottom:20px;font-size:20px;text-align:center;">💳 To'lov turi</h2>
    <div class="grid g2" style="margin-bottom:20px;"><button class="btn btn-green" style="justify-content:center;padding:16px;" onclick="doPay('cash')">💵 Naqd</button>
    <button class="btn btn-primary" style="justify-content:center;padding:16px;" onclick="doPay('card')">💳 Karta</button>
    <button class="btn btn-gray" style="justify-content:center;padding:16px;" onclick="openCredit()">📝 Nasiya</button>
    <button class="btn btn-gray" style="justify-content:center;padding:16px;" onclick="doPay('mixed')">🔀 Aralash</button></div>
    <button class="btn btn-red" style="width:100%;justify-content:center;" onclick="xc()">Bekor</button></div></div>
    <div id="crm" class="modal-overlay"><div class="modal"><h2 style="margin-bottom:20px;font-size:20px;text-align:center;">📝 Nasiya ma'lumotlari</h2>
    <input class="input" id="cf" placeholder="👤 Ism Familiya" style="margin-bottom:12px;">
    <input class="input" id="cp" placeholder="📱 Telefon" style="margin-bottom:16px;">
    <button class="btn btn-green" style="width:100%;justify-content:center;padding:16px;margin-bottom:8px;" onclick="doPay('credit')">✅ Saqlash</button>
    <button class="btn btn-gray" style="width:100%;justify-content:center;" onclick="backToPayment()">← Orqaga</button></div></div>
    <script>let C=[],sc=null,ls='';const F=n=>new Intl.NumberFormat('ru-RU').format(n);
    function rc(){const e=document.getElementById('ct');if(!C.length){e.innerHTML='<div style="text-align:center;color:var(--dim);padding:60px;">🛒 Savat bosh</div>';document.getElementById('tt').textContent='0 so\\'m';return}
    let h='',t=0;C.forEach((x,i)=>{const s=x.price*x.qty;t+=s;h+='<div class="cart-item"><div><div style="font-weight:600">'+x.name+'</div><div style="color:var(--dim);font-size:12px;">'+F(x.price)+' × '+x.qty+'</div></div><div style="display:flex;gap:6px;align-items:center"><button class="qty-btn" onclick="cq('+i+',-1)">−</button><span style="min-width:32px;text-align:center;font-weight:700">'+x.qty+'</span><button class="qty-btn" onclick="cq('+i+',1)">+</button></div></div>'});
    e.innerHTML=h;document.getElementById('tt').textContent=F(t)+" so'm"}
    function cq(i,d){C[i].qty=Math.max(1,C[i].qty+d);rc()}function cc(){C=[];rc()}
    async function ab(c){try{const r=await fetch('/api/product/by-barcode?code='+encodeURIComponent(c));if(!r.ok)throw 0;const p=await r.json();const x=C.find(y=>y.id===p.id);if(x)x.qty++;else C.push({...p,qty:1});if(document.getElementById('snd').checked)bp();rc()}catch{if(confirm('Topilmadi: '+c+'\\nYangi qo\\'shasizmi?'))location.href='/products/new?barcode='+encodeURIComponent(c)}}
    function bp(){try{const c=new(window.AudioContext||window.webkitAudioContext)(),o=c.createOscillator(),g=c.createGain();o.connect(g);g.connect(c.destination);o.frequency.value=880;g.gain.value=.1;o.start();o.stop(c.currentTime+.1)}catch{}}
    async function ss(){
if(sc) return;
var region = document.getElementById('sr');
region.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:200px;color:var(--dim)">📷 Kamera yuklanmoqda...</div>';
sc = new Html5Qrcode("sr");

var onOk = function(txt){
    if(txt && txt !== ls){
        ls = txt;
        ab(txt);
        if(navigator.vibrate) navigator.vibrate(80);
        setTimeout(function(){ ls=''; }, 700);
    }
};
var onErr = function(){};

var ok = false;

try {
    await sc.start({facingMode: "environment"}, {fps: 30, qrbox: {width: 250, height: 150}}, onOk, onErr);
    ok = true;
} catch(e){}

if(!ok){
    try {
        await sc.start(
            {facingMode: {ideal: "environment"}, width: {ideal: 1920}, height: {ideal: 1080}, frameRate: {ideal: 60}},
            {fps: 60, qrbox: {width: 260, height: 140}},
            onOk, onErr
        );
        ok = true;
    } catch(e){}
}

if(!ok){
    try {
        var cams = await Html5Qrcode.getCameras();
        var camId = null;
        if(cams.length){
            camId = cams[0].id;
            for(var i=0; i<cams.length; i++){
                if(/back|rear|environment/i.test(cams[i].label || '')){ camId = cams[i].id; break; }
            }
            await sc.start(camId, {fps: 30, qrbox: {width: 250, height: 150}}, onOk, onErr);
            ok = true;
        }
    } catch(e){}
}

if(!ok){
    try {
        await sc.start({facingMode: "user"}, {fps: 30, qrbox: {width: 250, height: 150}}, onOk, onErr);
        ok = true;
    } catch(e){}
}

if(!ok){
    sc = null;
    region.innerHTML = '<div style="padding:20px;text-align:center;color:var(--red)">❌ Kamera ochilmadi<br><small style="color:var(--dim)">Ruxsatni tekshiring</small></div>';
    return;
}

try {
    var video = document.querySelector('#sr video');
    if(video && video.srcObject){
        var track = video.srcObject.getTracks()[0];
        if(track && track.getCapabilities){
            var caps = track.getCapabilities();
            var adv = {};
            if(caps.torch){ adv.torch = true; }
            if(caps.focusMode && caps.focusMode.indexOf('continuous') !== -1){
                adv.focusMode = 'continuous';
            }
            if(Object.keys(adv).length > 0){
                await track.applyConstraints({advanced: [adv]});
            }
        }
    }
} catch(e){}

document.getElementById('sb').style.display = 'flex';
}

function xs(){if(sc){sc.stop().then(function(){sc.clear();sc=null});document.getElementById('sb').style.display='none'}}
function ms(){const v=document.getElementById('mb').value.trim();if(v){ab(v);document.getElementById('mb').value=''}}
document.getElementById('mb').addEventListener('keydown',function(e){if(e.key==='Enter')ms()});
function oc(){if(!C.length){alert('Savat bosh!');return}document.getElementById('cm').classList.add('active')}
function xc(){document.getElementById('cm').classList.remove('active')}
function openCredit(){document.getElementById('cm').classList.remove('active');document.getElementById('crm').classList.add('active')}
function backToPayment(){document.getElementById('crm').classList.remove('active');document.getElementById('cm').classList.add('active')}
async function doPay(t){let ph='',fn='';if(t==='credit'){fn=document.getElementById('cf').value.trim();ph=document.getElementById('cp').value.trim();if(!fn||!ph){alert('Ism va telefonni kiriting!');return}document.getElementById('crm').classList.remove('active')}const body={items:C.map(function(x){return{product_id:x.id,qty:x.qty}}),payment:t,customer_phone:ph,customer_name:fn};try{const r=await fetch('/api/checkout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw new Error(d.error||'Xato');alert('✅ Chek #'+d.sale_id+'\\nJami: '+F(d.total)+' so\\'m');C=[];rc();xc();document.getElementById('cp').value='';document.getElementById('cf').value='';window.open('/sales/'+d.sale_id+'/receipt','_blank')}catch(e){alert('❌ '+e.message)}}
rc()</script>""")

@app.route("/api/product/by-barcode")
def api_pbc():
    ensure_session_id()
    c = request.args.get("code", "").strip()
    if not c:
        return jsonify({"error": "code kerak"}), 400
    db = get_db()
    p = db.execute("SELECT * FROM products WHERE barcode=?", (c,)).fetchone()
    if not p:
        return jsonify({"error": "topilmadi"}), 404
    return jsonify(dict(p))

@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    ensure_session_id()
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "JSON yo'q"}), 400
        items = data.get("items", [])
        payment = data.get("payment", "cash")
        phone = data.get("customer_phone", "")
        cname = data.get("customer_name", "")
        if not items:
            return jsonify({"error": "Savat bo'sh"}), 400
        db = get_db()
        total = 0
        prepared = []
        for item in items:
            pid = item.get("product_id")
            qty = item.get("qty", 0)
            if not pid or qty <= 0:
                raise Exception("Noto'g'ri ma'lumot")
            p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            if not p:
                raise Exception("Mahsulot topilmadi")
            if p["stock"] < qty:
                raise Exception("{} yetarli emas!".format(p["name"]))
            prepared.append((p, qty))
            total += p["price"] * qty
        debt = total if payment == "credit" else 0
        cur = db.execute("INSERT INTO sales(total,payment,customer_phone,customer_name,debt) VALUES(?,?,?,?,?)", (total, payment, phone, cname, debt))
        sid = cur.lastrowid
        for p, q in prepared:
            db.execute("INSERT INTO sale_items(sale_id,product_id,qty,price) VALUES(?,?,?,?)", (sid, p["id"], q, p["price"]))
            db.execute("UPDATE products SET stock=stock-? WHERE id=?", (q, p["id"]))
        if payment == "credit" and phone:
            db.execute("INSERT INTO debts(phone,full_name,total,paid) VALUES(?,?,?,0) ON CONFLICT(phone) DO UPDATE SET full_name=?,total=total+?", (phone, cname or "Mijoz", debt, cname or "Mijoz", debt))
        db.commit()
        return jsonify({"sale_id": sid, "total": total})
    except Exception as e:
        try:
            db.rollback()
        except:
            pass
        return jsonify({"error": str(e)}), 400

@app.route("/sales")
def sales_list():
    ensure_session_id()
    db = get_db()
    rows = db.execute("SELECT s.*, GROUP_CONCAT(p.name || ' x' || si.qty, ', ') as products FROM sales s LEFT JOIN sale_items si ON si.sale_id=s.id LEFT JOIN products p ON p.id=si.product_id GROUP BY s.id ORDER BY s.id DESC LIMIT 100").fetchall()
    return RP("""<div style="padding:24px;max-width:1200px;margin:0 auto;"><h1 style="font-size:28px;font-weight:800;margin-bottom:24px;">🧾 Sotuvlar</h1>
    <div class="table-wrap"><table><thead><tr><th>#</th><th>Sana</th><th>Mahsulotlar</th><th>Summa</th><th>To'lov</th><th>Mijoz</th><th>Chek</th></tr></thead><tbody>
    {%for s in rows%}<tr><td><strong>#{{s.id}}</strong></td><td style="font-size:13px;color:var(--dim);">{{s.created_at[:16]}}</td>
    <td style="font-size:12px;">{{s.products or '-'}}</td>
    <td style="color:var(--green);font-weight:700;">{{"{:,.0f}".format(s.total)}}</td>
    <td>{%if s.payment=='cash'%}<span class="badge badge-green">NAQD</span>{%elif s.payment=='card'%}<span class="badge badge-blue">KARTA</span>{%elif s.payment=='credit'%}<span class="badge badge-red">NASIYA</span>{%else%}<span class="badge badge-yellow">ARALASH</span>{%endif%}</td>
    <td style="font-size:12px;">{{s.customer_name or '-'}}{%if s.customer_phone%}<br>{{s.customer_phone}}{%endif%}</td>
    <td><a href="/sales/{{s.id}}/receipt" target="_blank" class="btn btn-gray btn-sm">📄</a></td></tr>{%endfor%}</tbody></table></div></div>""", rows=rows)

@app.route("/sales/<int:sid>/receipt")
def receipt(sid):
    ft = request.args.get("format", "html")
    
    # Barcha bazalardan sale ni qidirish
    import glob
    s = None
    items = []
    db = None
    
    for db_file in glob.glob(os.path.join(DATA_DIR, "*.db")):
        try:
            temp_db = sqlite3.connect(db_file)
            temp_db.row_factory = sqlite3.Row
            s = temp_db.execute("SELECT * FROM sales WHERE id=?", (sid,)).fetchone()
            if s:
                items = temp_db.execute("SELECT si.*, p.name FROM sale_items si JOIN products p ON p.id=si.product_id WHERE si.sale_id=?", (sid,)).fetchall()
                db = temp_db
                break
            temp_db.close()
        except Exception as e:
            print(f"DB search error: {e}")
            continue
    
    if not s:
        return render_template_string("<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><style>body{font-family:sans-serif;background:#f5f5f5;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}.box{background:#fff;padding:40px;border-radius:20px;text-align:center;box-shadow:0 10px 40px rgba(0,0,0,.1)}.icon{font-size:64px;margin-bottom:20px}h1{color:#ef4444;margin-bottom:10px}p{color:#666}</style></head><body><div class='box'><div class='icon'>❌</div><h1>Chek topilmadi</h1><p>Bu chek mavjud emas yoki o'chirilgan</p><a href='/dashboard' style='display:inline-block;margin-top:20px;padding:12px 24px;background:#3b82f6;color:#fff;text-decoration:none;border-radius:10px;'>← Panelga qaytish</a></div></body></html>")
    
    # PDF format
    if ft == "pdf":
        try:
            from reportlab.lib.pagesizes import A6
            from reportlab.pdfgen import canvas as pc
            from reportlab.lib.units import mm
            buf = io.BytesIO()
            c = pc.Canvas(buf, pagesize=A6)
            w, h = A6
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(w/2, h-20*mm, "SMARTSTORE")
            c.setFont("Helvetica", 10)
            c.drawCentredString(w/2, h-28*mm, f"Chek #{sid} - {str(s['created_at'])[:19]}")
            c.line(10*mm, h-32*mm, w-10*mm, h-32*mm)
            y = h - 40*mm
            c.setFont("Helvetica-Bold", 11)
            for it in items:
                name = it["name"][:20]
                qty_price = f"{it['qty']} x {int(it['price'])}"
                total = f"{int(it['qty'] * it['price'])}"
                c.drawString(10*mm, y, name)
                c.drawCentredString(w/2, y, qty_price)
                c.drawRightString(w-10*mm, y, total)
                y -= 6*mm
            c.line(10*mm, y-2*mm, w-10*mm, y-2*mm)
            y -= 10*mm
            c.setFont("Helvetica-Bold", 14)
            c.drawRightString(w-10*mm, y, f"JAMI: {int(s['total'])} so'm")
            y -= 8*mm
            c.setFont("Helvetica", 10)
            c.drawString(10*mm, y, f"To'lov: {s['payment'].upper()}")
            if s["customer_name"]:
                y -= 5*mm
                c.drawString(10*mm, y, f"Mijoz: {s['customer_name']}")
            if s["customer_phone"]:
                y -= 5*mm
                c.drawString(10*mm, y, f"Tel: {s['customer_phone']}")
            if s["debt"] > 0:
                y -= 5*mm
                c.setFillColorRGB(0.8, 0, 0)
                c.drawString(10*mm, y, f"QARZ: {int(s['debt'])} so'm")
            c.save()
            buf.seek(0)
            if db:
                db.close()
            return send_file(buf, download_name=f"chek-{sid}.pdf", mimetype="application/pdf")
        except Exception as e:
            print(f"PDF error: {e}")
            if db:
                db.close()
            return "PDF xatosi", 500
    
    # HTML format - Professional dizayn
    html_template = """<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Chek #{{ '{:06d}'.format(s.id) }} • SmartStore</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&family=JetBrains+Mono:wght@600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:'Inter',sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;padding:20px 16px}
.toolbar{position:fixed;top:16px;left:0;right:0;display:flex;gap:10px;justify-content:center;z-index:100;flex-wrap:wrap;padding:0 16px}
.toolbar button,.toolbar a{padding:12px 20px;border:none;border-radius:12px;font-size:14px;font-weight:700;cursor:pointer;text-decoration:none;color:#fff;box-shadow:0 4px 15px rgba(0,0,0,.2);transition:.2s;font-family:inherit}
.toolbar button:hover{transform:translateY(-2px)}
.btn-print{background:linear-gradient(135deg,#3b82f6,#2563eb)}
.btn-pdf{background:linear-gradient(135deg,#10b981,#059669)}
.btn-close{background:linear-gradient(135deg,#ef4444,#dc2626)}
.receipt{max-width:420px;margin:80px auto 40px;background:#fff;border-radius:24px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.3)}
.header{background:linear-gradient(135deg,#1e293b,#0f172a);padding:32px 28px;color:#fff;text-align:center}
.logo{font-size:40px;margin-bottom:8px}
.brand{font-size:24px;font-weight:900;background:linear-gradient(135deg,#60a5fa,#34d399);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.tagline{font-size:10px;color:#94a3b8;letter-spacing:2px;text-transform:uppercase;margin-top:4px}
.divider{height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.2),transparent);margin:16px 0}
.cheque-id{display:inline-block;background:rgba(59,130,246,.2);border:1px solid rgba(59,130,246,.4);padding:6px 16px;border-radius:20px;font-family:'JetBrains Mono',monospace;font-size:14px;font-weight:700;color:#60a5fa}
.date{font-size:11px;color:#cbd5e1;margin-top:8px}
.body{padding:24px 28px}
.section-title{font-size:10px;font-weight:700;color:#94a3b8;letter-spacing:2px;text-transform:uppercase;margin-bottom:12px}
.item{padding:12px 0;border-bottom:1px dashed #e2e8f0}
.item:last-of-type{border-bottom:none}
.item-row{display:flex;justify-content:space-between;align-items:start;gap:10px}
.item-name{font-weight:600;font-size:14px;color:#0f172a;flex:1}
.item-total{font-family:'JetBrains Mono',monospace;font-weight:700;font-size:14px;color:#10b981}
.item-detail{font-size:11px;color:#64748b;font-family:'JetBrains Mono',monospace;margin-top:3px}
.summary{background:#f8fafc;margin:20px -28px 0;padding:20px 28px;border-top:2px dashed #cbd5e1;border-bottom:2px dashed #cbd5e1}
.row{display:flex;justify-content:space-between;padding:5px 0;font-size:13px;color:#64748b}
.row .val{font-weight:600;color:#0f172a;font-family:'JetBrains Mono',monospace}
.grand{display:flex;justify-content:space-between;align-items:center;padding:16px 0 0;margin-top:10px;border-top:2px solid #0f172a}
.grand-label{font-size:12px;font-weight:700;color:#0f172a;letter-spacing:2px}
.grand-amount{font-family:'JetBrains Mono',monospace;font-size:28px;font-weight:900;color:#10b981}
.info{margin-top:20px}
.info-row{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;background:#f8fafc;border-radius:10px;margin-bottom:8px}
.info-label{font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase}
.info-value{font-size:13px;font-weight:700;color:#0f172a}
.badge{display:inline-block;padding:5px 12px;border-radius:20px;font-size:11px;font-weight:800}
.badge-cash{background:#d1fae5;color:#065f46}
.badge-card{background:#dbeafe;color:#1e40af}
.badge-credit{background:#fee2e2;color:#991b1b}
.badge-mixed{background:#fef3c7;color:#92400e}
.debt-box{margin-top:16px;padding:16px;background:linear-gradient(135deg,#fef3c7,#fde68a);border:2px solid #f59e0b;border-radius:12px;text-align:center}
.debt-label{font-size:10px;font-weight:800;color:#92400e;letter-spacing:2px}
.debt-amount{font-family:'JetBrains Mono',monospace;font-size:24px;font-weight:900;color:#b45309;margin-top:4px}
.footer{background:#0f172a;padding:24px 28px;text-align:center;color:#94a3b8}
.thanks{font-size:32px;margin-bottom:6px}
.thanks-text{font-size:14px;font-weight:600;color:#f1f5f9}
.thanks-sub{font-size:10px;color:#64748b;letter-spacing:2px;margin-top:4px}
@media(max-width:500px){body{padding:12px 8px}.receipt{margin:70px 0 20px;border-radius:20px}.header{padding:24px 20px}.body{padding:20px}.summary{margin:16px -20px 0;padding:16px 20px}.toolbar{top:8px;gap:6px}.toolbar button,.toolbar a{padding:10px 16px;font-size:13px}}
@media print{body{background:#fff;padding:0}.toolbar{display:none!important}.receipt{margin:0;box-shadow:none;border-radius:0;max-width:100%}@page{margin:0}}
</style>
</head>
<body>
<div class="toolbar">
<button class="btn-print" onclick="window.print()">🖨️ Chop</button>
<a class="btn-pdf" href="/sales/{{s.id}}/receipt?format=pdf">📥 PDF</a>
<button class="btn-close" onclick="window.close()">✕ Yopish</button>
</div>
<div class="receipt">
<div class="header">
<div class="logo">🏪</div>
<div class="brand">SMARTSTORE</div>
<div class="tagline">Professional POS</div>
<div class="divider"></div>
<div class="cheque-id"># {{ '{:06d}'.format(s.id) }}</div>
<div class="date">📅 {{ s.created_at[:19] }}</div>
</div>
<div class="body">
<div class="section-title">Mahsulotlar</div>
{% for it in items %}
<div class="item">
<div class="item-row">
<span class="item-name">{{ it.name }}</span>
<span class="item-total">{{ '{:,.0f}'.format(it.qty * it.price) }}</span>
</div>
<div class="item-detail">{{ it.qty }} × {{ '{:,.0f}'.format(it.price) }} so'm</div>
</div>
{% endfor %}
<div class="summary">
<div class="row"><span>Mahsulotlar</span><span class="val">{{ items|length }} ta</span></div>
<div class="row"><span>Jami dona</span><span class="val">{% set ns = namespace(q=0) %}{% for it in items %}{% set ns.q = ns.q + it.qty %}{% endfor %}{{ ns.q }}</span></div>
<div class="grand">
<span class="grand-label">JAMI</span>
<span class="grand-amount">{{ '{:,.0f}'.format(s.total) }}</span>
</div>
<div style="text-align:right;font-size:10px;color:#64748b;margin-top:2px;font-weight:600">SO'M</div>
</div>
<div class="info">
<div class="info-row">
<span class="info-label">To'lov</span>
{% if s.payment == 'cash' %}<span class="badge badge-cash">💵 NAQD</span>
{% elif s.payment == 'card' %}<span class="badge badge-card">💳 KARTA</span>
{% elif s.payment == 'credit' %}<span class="badge badge-credit">📝 NASIYA</span>
{% else %}<span class="badge badge-mixed">🔀 ARALASH</span>{% endif %}
</div>
{% if s.customer_name %}
<div class="info-row">
<span class="info-label">👤 Mijoz</span>
<span class="info-value">{{ s.customer_name }}</span>
</div>
{% endif %}
{% if s.customer_phone %}
<div class="info-row">
<span class="info-label">📱 Telefon</span>
<span class="info-value" style="font-family:'JetBrains Mono',monospace">{{ s.customer_phone }}</span>
</div>
{% endif %}
</div>
{% if s.debt > 0 %}
<div class="debt-box">
<div class="debt-label">⚠️ QARZ SUMMASI</div>
<div class="debt-amount">{{ '{:,.0f}'.format(s.debt) }} so'm</div>
</div>
{% endif %}
</div>
<div class="footer">
<div class="thanks">🙏</div>
<div class="thanks-text">Xaridingiz uchun rahmat!</div>
<div class="thanks-sub">SmartStore POS • 2026</div>
</div>
</div>
</body>
</html>"""
    
    result = render_template_string(html_template, s=s, items=items)
    if db:
        db.close()
    return result


@app.route("/debts")
def debts_page():
    ensure_session_id()
    db = get_db()
    rows = db.execute("SELECT * FROM debts WHERE total>0 ORDER BY total DESC").fetchall()
    td = sum(r["total"] for r in rows)
    tp = sum(r["paid"] for r in rows) if rows else 0
    return RP("""<div style="padding:24px;max-width:1000px;margin:0 auto;"><h1 style="font-size:28px;font-weight:800;margin-bottom:24px;">💳 Qarzdorlar</h1>
    <div class="grid g3" style="margin-bottom:20px;"><div class="stat-card red"><div class="stat-label">💸 Jami qarz</div><div class="stat-value">{{"{:,.0f}".format(td)}}</div></div>
    <div class="stat-card green"><div class="stat-label">✅ To'langan</div><div class="stat-value">{{"{:,.0f}".format(tp)}}</div></div>
    <div class="stat-card"><div class="stat-label">👥 Qarzdorlar</div><div class="stat-value">{{rows|length}}</div></div></div>
    <div class="table-wrap"><table><thead><tr><th>Ism Familiya</th><th>Telefon</th><th>Qarz</th><th>To'lov</th></tr></thead><tbody>
    {%for d in rows%}<tr><td><strong>{{d.full_name}}</strong></td><td style="font-family:monospace;">{{d.phone}}</td><td style="color:var(--red);font-weight:700;font-size:16px;">{{"{:,.0f}".format(d.total)}}</td>
    <td><form method="POST" action="/debts/{{d.id}}/pay" style="display:flex;gap:6px;"><input type="number" name="amount" placeholder="Summa" required style="width:120px;padding:8px;background:var(--bg);color:#fff;border:1px solid var(--border);border-radius:8px;"><button class="btn btn-green btn-sm">💰</button></form></td></tr>
    {%else%}<tr><td colspan="4" style="text-align:center;color:var(--dim);padding:50px;">✅ Qarzdor yo'q</td></tr>{%endfor%}</tbody></table></div></div>""", rows=rows, td=td, tp=tp)

@app.route("/debts/<int:did>/pay", methods=["POST"])
def debt_pay(did):
    ensure_session_id()
    amt = float(request.form["amount"])
    db = get_db()
    db.execute("UPDATE debts SET total=MAX(0,total-?), paid=COALESCE(paid,0)+? WHERE id=?", (amt, amt, did))
    db.commit()
    return redirect("/debts")

@app.route("/reports")
def reports_page():
    ensure_session_id()
    db = get_db()
    if not db:
        return redirect("/dashboard")
    
    period = request.args.get("period", "day")
    today = datetime.now().strftime("%Y-%m-%d")
    
    if period == "week":
        date_filter = "created_at>=date('now','-7 days')"
        period_label = "Haftalik"
    elif period == "month":
        date_filter = "created_at>=date('now','-30 days')"
        period_label = "Oylik"
    else:
        date_filter = "date(created_at)='{}'".format(today)
        period_label = "Bugungi"
    
    st = db.execute("SELECT COUNT(*) c, COALESCE(SUM(total),0) s FROM sales WHERE {}".format(date_filter)).fetchone()
    total_sales = st["s"] if st else 0
    total_count = st["c"] if st else 0
    avg_check = total_sales / total_count if total_count > 0 else 0
    
    payments = db.execute("SELECT payment, COUNT(*) c, SUM(total) s FROM sales WHERE {} GROUP BY payment".format(date_filter)).fetchall()
    
    top_products = db.execute("SELECT p.name, SUM(si.qty) as qty, SUM(si.qty*si.price) as revenue FROM sale_items si JOIN products p ON p.id=si.product_id JOIN sales s ON s.id=si.sale_id WHERE {} GROUP BY si.product_id ORDER BY revenue DESC LIMIT 5".format(date_filter)).fetchall()
    
    debt_stats = db.execute("SELECT COUNT(*) c, COALESCE(SUM(total),0) t, COALESCE(SUM(paid),0) p FROM debts WHERE total>0").fetchone()
    debt_count = debt_stats["c"] if debt_stats else 0
    debt_total = debt_stats["t"] if debt_stats else 0
    debt_paid = debt_stats["p"] if debt_stats else 0
    debt_remaining = debt_total - debt_paid
    
    return RP("""<div style="padding:24px;max-width:1200px;margin:0 auto;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;flex-wrap:wrap;gap:12px;">
        <h1 style="font-size:28px;font-weight:800;">📈 Hisobotlar</h1>
        <button onclick="window.print()" class="btn btn-primary">🖨️ Chop etish</button>
    </div>
    <div class="grid g3" style="margin-bottom:24px;">
        <a href="?period=day" class="btn {%if period=='day'%}btn-primary{%else%}btn-gray{%endif%}" style="justify-content:center;padding:16px;">📅 Bugun</a>
        <a href="?period=week" class="btn {%if period=='week'%}btn-primary{%else%}btn-gray{%endif%}" style="justify-content:center;padding:16px;">📆 Hafta</a>
        <a href="?period=month" class="btn {%if period=='month'%}btn-primary{%else%}btn-gray{%endif%}" style="justify-content:center;padding:16px;">🗓️ Oy</a>
    </div>
    <div style="text-align:center;margin-bottom:24px;padding:12px;background:rgba(59,130,246,.1);border-radius:12px;">
        <span style="color:var(--primary);font-weight:700;font-size:16px;">{{period_label}} hisobot</span>
    </div>
    <div class="grid g4" style="margin-bottom:24px;">
        <div class="stat-card">
            <div class="stat-label">💰 Jami savdo</div>
            <div class="stat-value" style="color:var(--green);">{{"{:,.0f}".format(total_sales)}} so'm</div>
        </div>
        <div class="stat-card green">
            <div class="stat-label">🧾 Cheklar soni</div>
            <div class="stat-value">{{total_count}}</div>
        </div>
        <div class="stat-card yellow">
            <div class="stat-label">📊 O'rtacha chek</div>
            <div class="stat-value">{{"{:,.0f}".format(avg_check)}} so'm</div>
        </div>
        <div class="stat-card red">
            <div class="stat-label">💸 Qarzdorlar</div>
            <div class="stat-value">{{debt_count}}</div>
        </div>
    </div>
    <div class="grid g2">
        <div class="card">
            <h2 style="margin-bottom:16px;font-size:18px;">💳 To'lov turlari</h2>
            {%for p in payments%}
            <div style="display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--border);">
                <div>
                    {%if p.payment=='cash'%}<span class="badge badge-green">NAQD</span>
                    {%elif p.payment=='card'%}<span class="badge badge-blue">KARTA</span>
                    {%elif p.payment=='credit'%}<span class="badge badge-red">NASIYA</span>
                    {%else%}<span class="badge badge-yellow">ARALASH</span>{%endif%}
                </div>
                <div style="text-align:right;">
                    <div style="font-weight:700;color:var(--green);">{{"{:,.0f}".format(p.s)}} so'm</div>
                    <div style="font-size:12px;color:var(--dim);">{{p.c}} ta chek</div>
                </div>
            </div>
            {%else%}
            <p style="color:var(--dim);text-align:center;padding:20px;">Bu davrda savdo yo'q</p>
            {%endfor%}
        </div>
        <div class="card">
            <h2 style="margin-bottom:16px;font-size:18px;">🏆 Top 5 mahsulot</h2>
            {%for p in top_products%}
            <div style="display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--border);">
                <div>
                    <div style="font-weight:600;">{{p.name}}</div>
                    <div style="font-size:12px;color:var(--dim);">{{p.qty}} dona sotilgan</div>
                </div>
                <div style="font-weight:700;color:var(--green);">{{"{:,.0f}".format(p.revenue)}} so'm</div>
            </div>
            {%else%}
            <p style="color:var(--dim);text-align:center;padding:20px;">Bu davrda savdo yo'q</p>
            {%endfor%}
        </div>
    </div>
    {%if debt_count > 0%}
    <div class="card" style="margin-top:24px;border-color:rgba(245,158,11,.3);">
        <h2 style="margin-bottom:16px;font-size:18px;">💸 Qarz holati</h2>
        <div class="grid g3">
            <div style="background:rgba(59,130,246,.1);border-radius:12px;padding:16px;text-align:center;">
                <div class="stat-label">Jami berilgan</div>
                <div style="font-size:22px;font-weight:800;color:var(--primary);">{{"{:,.0f}".format(debt_total)}} so'm</div>
            </div>
            <div style="background:rgba(16,185,129,.1);border-radius:12px;padding:16px;text-align:center;">
                <div class="stat-label">To'langan</div>
                <div style="font-size:22px;font-weight:800;color:var(--green);">{{"{:,.0f}".format(debt_paid)}} so'm</div>
            </div>
            <div style="background:rgba(239,68,68,.1);border-radius:12px;padding:16px;text-align:center;">
                <div class="stat-label">Qolgan qarz</div>
                <div style="font-size:22px;font-weight:800;color:var(--red);">{{"{:,.0f}".format(debt_remaining)}} so'm</div>
            </div>
        </div>
    </div>
    {%endif%}
    </div>""", period=period, period_label=period_label, today=today, total_sales=total_sales, total_count=total_count, avg_check=avg_check, payments=payments, top_products=top_products, debt_count=debt_count, debt_total=debt_total, debt_paid=debt_paid, debt_remaining=debt_remaining)

# ═══════════════════════════════════════
# 🤖 TELEGRAM BOT
# ═══════════════════════════════════════
def start_bot_thread():
    if not BOT_TOKEN:
        print("⚠️ BOT_TOKEN yo'q")
        return
    try:
        import asyncio
        from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
        from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
        
        async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_user
            app_url_with_user = APP_URL + "?tg_user=" + str(user.id)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Ilovani ochish", web_app=WebAppInfo(url=app_url_with_user))], [InlineKeyboardButton("ℹ️ Yordam", callback_data="help")]])
            info = """🏪 <b>SmartStore POS</b> - Professional do'kon boshqaruvi

✨ <b>Imkoniyatlar:</b>

📦 <b>Mahsulotlar</b> — Shtrix-kod bilan qo'shish, qoldiqni kuzatish

🛒 <b>Kassa</b> — Professional kamera (60 FPS), tezkor skaner

🧾 <b>Sotuvlar</b> — Cheklar tarixi, PDF formatda

💳 <b>Qarzdorlar</b> — Ism, telefon, to'lov qabul qilish

🗄️ <b>Database</b> — Har kim o'z bazasini yaratadi, parol bilan himoyalangan

━━━━━━━━━━━━━━━━━━━━

👋 <b>{}</b>, xush kelibsiz!

👇 Ilovani oching:""".format(user.full_name)
            await update.message.reply_html(info, reply_markup=kb)
        
        async def cb_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
            query = update.callback_query
            await query.answer()
            await query.edit_message_text("ℹ️ Ilovani oching → Mahsulot qo'shing → Sotuv qiling\n\n🗄️ Baza sahifasida o'z bazangizni yarating!")
        
        async def run_bot():
            while True:
                try:
                    app_bot = Application.builder().token(BOT_TOKEN).build()
                    app_bot.add_handler(CommandHandler("start", cmd_start))
                    app_bot.add_handler(CallbackQueryHandler(cb_help, pattern="^help$"))
                    print("🤖 Telegram bot ishga tushdi!")
                    async with app_bot:
                        await app_bot.start()
                        await app_bot.updater.start_polling(drop_pending_updates=True)
                        while True:
                            await asyncio.sleep(10)
                            if not app_bot.updater.running:
                                raise Exception("Polling to'xtadi")
                except Exception as e:
                    print("⚠️ Bot xatosi:", e, "- 10 soniyadan keyin qayta urinaman")
                    await asyncio.sleep(10)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_bot())
    except Exception as e:
        print("❌ Bot xatosi:", e)

if __name__ == "__main__":
    print("🤖 Bot ishga tushmoqda...")
    threading.Thread(target=start_bot_thread, daemon=True).start()
    print("=" * 50)
    print("🏪 SmartStore POS (Professional)")
    print("=" * 50)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
