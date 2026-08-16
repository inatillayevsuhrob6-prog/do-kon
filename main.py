import os, sqlite3, threading, io, time, re, hashlib
from datetime import datetime
from flask import Flask, request, redirect, render_template_string, send_file, jsonify, g, session

BOT_TOKEN = "8863204152:AAF-VbLwrDrnSl832BZchmMA6HhJmbfQgjs"
APP_URL = "https://smartstore-web-dvse.onrender.com"
DATA_DIR = "/tmp" if os.environ.get("RENDER") else os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)
app.secret_key = "smartstore-2024"

def get_db_path():
    db_name = session.get('db_name')
    if not db_name or not re.match(r'^[a-zA-Z0-9_]+$', db_name):
        return None
    return os.path.join(DATA_DIR, f"{db_name}.db")

def get_pass_path(db_name):
    return os.path.join(DATA_DIR, f"{db_name}.pass")

def get_db():
    if "db" not in g:
        db_path = get_db_path()
        if not db_path:
            g.db = None
            return None
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db: db.close()

def init_user_db(db_path):
    db = sqlite3.connect(db_path)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, barcode TEXT UNIQUE NOT NULL, price REAL NOT NULL CHECK(price>=0), min_stock INTEGER DEFAULT 5, stock INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY AUTOINCREMENT, total REAL NOT NULL, payment TEXT NOT NULL, customer_phone TEXT, customer_name TEXT DEFAULT '', debt REAL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sale_items (id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL, product_id INTEGER NOT NULL, qty INTEGER NOT NULL, price REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS debts (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT UNIQUE NOT NULL, full_name TEXT NOT NULL, total REAL DEFAULT 0, paid REAL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    """)
    db.commit(); db.close()

CSS = "@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');:root{--bg:#0a0e1a;--card:#111827;--border:#1e293b;--primary:#3b82f6;--green:#10b981;--red:#ef4444;--yellow:#f59e0b;--text:#f1f5f9;--dim:#94a3b8}*{box-sizing:border-box;margin:0;padding:0}body{font-family:Inter,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}.nav{background:rgba(17,24,39,.95);border-bottom:1px solid var(--border);padding:0 24px;height:70px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100}.nav-brand{font-size:24px;font-weight:800;background:linear-gradient(135deg,#3b82f6,#10b981);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.nav-links{display:flex;gap:6px}.nav-links a{color:var(--dim);text-decoration:none;padding:10px 16px;border-radius:12px;font-size:15px;font-weight:600}.card{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:28px}.btn{padding:14px 28px;border-radius:14px;border:none;font-weight:700;font-size:16px;cursor:pointer;color:#fff}.btn-primary{background:linear-gradient(135deg,#3b82f6,#2563eb)}.btn-green{background:linear-gradient(135deg,#10b981,#059669)}.btn-red{background:linear-gradient(135deg,#ef4444,#dc2626)}.btn-gray{background:#334155}.btn-sm{padding:10px 16px;font-size:14px}.input{width:100%;padding:16px;border-radius:14px;background:rgba(15,23,42,.8);color:#fff;border:2px solid var(--border);font-size:16px}.grid{display:grid;gap:20px}.g2{grid-template-columns:repeat(2,1fr)}.g4{grid-template-columns:repeat(4,1fr)}.stat-card{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:24px}.stat-label{font-size:15px;color:var(--dim);margin-bottom:10px}.stat-value{font-size:36px;font-weight:900}.table-wrap{overflow-x:auto;border-radius:20px;border:1px solid var(--border)}table{width:100%;border-collapse:collapse}th{background:rgba(15,23,42,.5);padding:16px;text-align:left;font-size:13px;color:var(--dim)}td{padding:16px;border-top:1px solid var(--border);font-size:15px}.badge{padding:6px 12px;border-radius:999px;font-size:13px;font-weight:700}.badge-green{background:rgba(16,185,129,.15);color:#34d399}.badge-red{background:rgba(239,68,68,.15);color:#f87171}.badge-blue{background:rgba(59,130,246,.15);color:#60a5fa}.cart-item{display:flex;justify-content:space-between;padding:16px;background:rgba(15,23,42,.5);border:1px solid var(--border);border-radius:14px;margin-bottom:10px}.qty-btn{width:40px;height:40px;border-radius:12px;border:none;background:var(--primary);color:#fff;font-weight:700;font-size:18px;cursor:pointer}.total-bar{background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.2);border-radius:20px;padding:24px;margin-top:20px}.total-amount{font-size:40px;font-weight:900;color:var(--green)}.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:200;align-items:center;justify-content:center}.modal-overlay.active{display:flex}.modal{background:var(--card);border-radius:24px;padding:36px;max-width:500px;width:90%}.mnav{display:none}@media(max-width:768px){.g2,.g4{grid-template-columns:1fr}.nav-links{display:none}body{padding-bottom:90px}.mnav{display:flex;position:fixed;bottom:0;left:0;right:0;background:rgba(17,24,39,.98);border-top:1px solid var(--border);z-index:100;padding:8px;justify-content:space-around}.mnav a{display:flex;flex-direction:column;align-items:center;color:var(--dim);text-decoration:none;font-size:24px}.mnav span{font-size:11px}}"

NAV_HTML = "<div class='nav'><div class='nav-brand'>🏪 SmartStore</div><div class='nav-links'><a href='/dashboard'>📊 Panel</a><a href='/pos'>🛒 Kassa</a><a href='/products'>📦 Mahsulot</a><a href='/sales'>🧾 Sotuv</a><a href='/debts'>💳 Qarzdor</a><a href='/reports'>📈 Hisobot</a><a href='/db'>🗄️ Database</a></div></div>"

MOBILE_NAV = "<div class='mnav'><a href='/dashboard'>📊<span>Panel</span></a><a href='/pos'>🛒<span>Kassa</span></a><a href='/products'>📦<span>Mahsulot</span></a><a href='/sales'>🧾<span>Sotuv</span></a><a href='/debts'>💳<span>Qarzdor</span></a></div>"

TG_SCRIPT = "<script src='https://telegram.org/js/telegram-web-app.js'></script><script>if(window.Telegram&&Telegram.WebApp){Telegram.WebApp.ready();Telegram.WebApp.expand();}</script>"

def RP(tpl, **ctx):
    full = "<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>SmartStore</title>" + TG_SCRIPT + "<style>" + CSS + "</style></head><body>" + NAV_HTML + tpl + MOBILE_NAV + "</body></html>"
    return render_template_string(full, **ctx)

@app.route("/")
def index():
    if not session.get('db_name'):
        return redirect("/db")
    return redirect("/dashboard")

@app.route("/db")
def db_page():
    db_name = session.get('db_name')
    return RP("<div style='padding:24px;max-width:600px;margin:0 auto;'><h1 style='font-size:32px;margin-bottom:24px;'>🗄️ Database</h1>{%if db_name%}<div class='card' style='margin-bottom:20px;border-color:rgba(16,185,129,.4);'><div style='display:flex;align-items:center;gap:12px;'><div style='font-size:48px;'>✅</div><div><div style='font-size:14px;color:var(--dim);'>Ulangan database</div><div style='font-size:24px;font-weight:800;color:var(--green);'>{{db_name}}</div></div></div></div><div class='grid g2'><a href='/dashboard' class='btn btn-primary' style='padding:18px;justify-content:center;'>📊 Dashboard</a><a href='/db/disconnect' class='btn btn-red' style='padding:18px;justify-content:center;'>🔌 Uzish</a></div>{%else%}<div class='card' style='margin-bottom:20px;'><h2 style='margin-bottom:16px;'>➕ Yangi database yaratish</h2><form method='POST' action='/db/create'><input class='input' name='db_name' placeholder='Database nomi (masalan: myshop)' required pattern='[a-zA-Z0-9_]+' title='Faqat harf, raqam, underscore'><input class='input' name='password' type='password' placeholder='Parol (kamida 4 ta belgi)' required minlength='4' style='margin-top:12px;'><button class='btn btn-green' style='width:100%;padding:18px;margin-top:16px;'>🚀 Yaratish</button></form></div><div class='card'><h2 style='margin-bottom:16px;'>🔗 Mavjud database ga ulanish</h2><form method='POST' action='/db/connect'><input class='input' name='db_name' placeholder='Database nomi' required pattern='[a-zA-Z0-9_]+'><input class='input' name='password' type='password' placeholder='Parol' required style='margin-top:12px;'><button class='btn btn-primary' style='width:100%;padding:18px;margin-top:16px;'>🔌 Ulanish</button></form></div>{%endif%}</div>", db_name=db_name)

@app.route("/db/create", methods=["POST"])
def db_create():
    db_name = request.form.get("db_name", "").strip()
    password = request.form.get("password", "")
    if not re.match(r'^[a-zA-Z0-9_]+$', db_name):
        return "❌ Noto'g'ri nom! Faqat harf, raqam, underscore.", 400
    if len(password) < 4:
        return "❌ Parol kamida 4 ta belgi!", 400
    db_path = os.path.join(DATA_DIR, f"{db_name}.db")
    pass_path = get_pass_path(db_name)
    if os.path.exists(db_path):
        return "❌ Bu nom allaqachon mavjud!", 400
    pass_hash = hashlib.sha256(password.encode()).hexdigest()
    with open(pass_path, 'w') as f:
        f.write(pass_hash)
    init_user_db(db_path)
    session['db_name'] = db_name
    return redirect("/dashboard")

@app.route("/db/connect", methods=["POST"])
def db_connect():
    db_name = request.form.get("db_name", "").strip()
    password = request.form.get("password", "")
    if not re.match(r'^[a-zA-Z0-9_]+$', db_name):
        return "❌ Noto'g'ri nom!", 400
    db_path = os.path.join(DATA_DIR, f"{db_name}.db")
    pass_path = get_pass_path(db_name)
    if not os.path.exists(db_path):
        return "❌ Bu nomda database yo'q!", 400
    if not os.path.exists(pass_path):
        return "❌ Parol fayli topilmadi!", 400
    pass_hash = hashlib.sha256(password.encode()).hexdigest()
    with open(pass_path, 'r') as f:
        saved_hash = f.read().strip()
    if pass_hash != saved_hash:
        return "❌ Noto'g'ri parol!", 400
    session['db_name'] = db_name
    return redirect("/dashboard")

@app.route("/db/disconnect")
def db_disconnect():
    session.pop('db_name', None)
    return redirect("/db")

@app.route("/dashboard")
def dashboard():
    if not session.get('db_name'): return redirect("/db")
    db = get_db()
    if not db: return redirect("/db")
    today = datetime.now().strftime("%Y-%m-%d")
    ts = db.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE date(created_at)=?", (today,)).fetchone()[0]
    tc = db.execute("SELECT COUNT(*) FROM sales WHERE date(created_at)=?", (today,)).fetchone()[0]
    tp = db.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    ls = db.execute("SELECT COUNT(*) FROM products WHERE stock<=min_stock").fetchone()[0]
    td = db.execute("SELECT COALESCE(SUM(total),0) FROM debts WHERE total>0").fetchone()[0]
    ws = db.execute("SELECT date(created_at) d,SUM(total) s FROM sales WHERE created_at>=date('now','-7 days') GROUP BY d ORDER BY d").fetchall()
    top = db.execute("SELECT p.name,SUM(si.qty) t FROM sale_items si JOIN products p ON p.id=si.product_id GROUP BY si.product_id ORDER BY t DESC LIMIT 5").fetchall()
    return RP("<div style='padding:24px;max-width:1400px;margin:0 auto;'><h1 style='font-size:32px;margin-bottom:24px;'>📊 Dashboard</h1><div class='grid g4' style='margin-bottom:24px;'><div class='stat-card'><div class='stat-label'>💰 Bugungi savdo</div><div class='stat-value'>{{\"{:,.0f}\".format(ts)}}</div></div><div class='stat-card'><div class='stat-label'>🧾 Cheklar</div><div class='stat-value'>{{tc}}</div></div><div class='stat-card'><div class='stat-label'>📦 Mahsulotlar</div><div class='stat-value'>{{tp}}</div></div><div class='stat-card'><div class='stat-label'>⚠️ Kam qoldiq</div><div class='stat-value'>{{ls}}</div></div></div><div class='grid g2'><div class='card'><h2 style='margin-bottom:16px;'>🏆 Top 5</h2>{%for p in top%}<div style='display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--border);'><span>{{p.name}}</span><span class='badge badge-blue'>{{p.t}} dona</span></div>{%else%}<p style='color:var(--dim);text-align:center;'>Hali savdo yo'q</p>{%endfor%}</div><div class='card'><h2 style='margin-bottom:16px;'>📈 7 kunlik</h2>{%for s in ws%}<div style='display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border);'><span style='color:var(--dim);'>{{s.d}}</span><span style='color:var(--green);font-weight:700;'>{{\"{:,.0f}\".format(s.s)}}</span></div>{%endfor%}</div></div>{%if td>0%}<div class='card' style='margin-top:24px;'><div style='display:flex;justify-content:space-between;align-items:center;'><div><div style='color:var(--dim);'>💸 Jami qarz</div><div style='font-size:32px;font-weight:800;color:var(--yellow);'>{{\"{:,.0f}\".format(td)}} so'm</div></div><a href='/debts' class='btn btn-primary'>Qarzdorlar →</a></div></div>{%endif%}</div>", ts=ts, tc=tc, tp=tp, ls=ls, td=td, ws=ws, top=top)

@app.route("/products")
def products_list():
    if not session.get('db_name'): return redirect("/db")
    db = get_db(); q = request.args.get("q", "")
    rows = db.execute("SELECT * FROM products WHERE name LIKE ? OR barcode LIKE ? ORDER BY id DESC", ("%"+q+"%", "%"+q+"%")).fetchall() if q else db.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    low = [r for r in rows if r["stock"] <= r["min_stock"]]
    return RP("<div style='padding:24px;max-width:1200px;margin:0 auto;'><div style='display:flex;justify-content:space-between;margin-bottom:24px;'><h1 style='font-size:32px;'>📦 Mahsulotlar ({{rows|length}})</h1><a href='/products/new' class='btn btn-green'>➕ Yangi</a></div><form method='GET' style='display:flex;gap:8px;margin-bottom:20px;'><input class='input' name='q' value='{{q}}' placeholder='🔍 Qidiruv...' style='margin:0;'><button class='btn btn-primary'>Qidirish</button></form>{%if low%}<div class='card' style='margin-bottom:20px;border-color:rgba(239,68,68,.4);'><h3 style='color:var(--red);'>⚠️ Kam qoldiq ({{low|length}})</h3>{%for p in low[:5]%}<div style='padding:4px 0;'>• {{p.name}} — {{p.stock}}/{{p.min_stock}}</div>{%endfor%}</div>{%endif%}<div class='table-wrap'><table><thead><tr><th>Nomi</th><th>Barcode</th><th>Narxi</th><th>Qoldiq</th><th>Amallar</th></tr></thead><tbody>{%for p in rows%}<tr><td><strong>{{p.name}}</strong></td><td style='font-family:monospace;color:var(--dim);'>{{p.barcode}}</td><td>{{\"{:,.0f}\".format(p.price)}}</td><td>{%if p.stock<=p.min_stock%}<span class='badge badge-red'>{{p.stock}}</span>{%else%}{{p.stock}}{%endif%}</td><td><a href='/products/{{p.id}}/edit' class='btn btn-gray btn-sm'>✏️</a><form method='POST' action='/products/{{p.id}}/delete' style='display:inline;'><button class='btn btn-red btn-sm'>🗑</button></form></td></tr>{%else%}<tr><td colspan='5' style='text-align:center;color:var(--dim);padding:40px;'>Mahsulot yo'q</td></tr>{%endfor%}</tbody></table></div></div>", rows=rows, q=q, low=low)

@app.route("/products/new", methods=["GET", "POST"])
def product_new():
    if not session.get('db_name'): return redirect("/db")
    if request.method == "POST":
        db = get_db()
        try:
            db.execute("INSERT INTO products(name,barcode,price,min_stock,stock) VALUES(?,?,?,?,?)", (request.form["name"].strip(), request.form["barcode"].strip(), float(request.form["price"]), int(request.form.get("min_stock", 5)), int(request.form.get("stock", 0))))
            db.commit(); return redirect("/products")
        except: return "❌ Barcode mavjud", 400
    bc = request.args.get("barcode", "")
    return RP("<div style='padding:24px;max-width:600px;margin:0 auto;'><div class='card'><h1 style='margin-bottom:24px;'>➕ Yangi mahsulot</h1><form method='POST'><input class='input' name='name' placeholder='Nomi' required><input class='input' name='barcode' value='{{bc}}' placeholder='Shtrix-kod' required><input class='input' type='number' step='0.01' name='price' placeholder='Narxi' required><div class='grid g2'><input class='input' type='number' name='min_stock' value='5' placeholder='Min qoldiq'><input class='input' type='number' name='stock' value='0' placeholder='Qoldiq'></div><button class='btn btn-green' style='width:100%;padding:16px;'>💾 Saqlash</button></form></div></div>", bc=bc)

@app.route("/products/<int:pid>/edit", methods=["GET", "POST"])
def product_edit(pid):
    if not session.get('db_name'): return redirect("/db")
    db = get_db()
    if request.method == "POST":
        db.execute("UPDATE products SET name=?,barcode=?,price=?,min_stock=?,stock=? WHERE id=?", (request.form["name"], request.form["barcode"], float(request.form["price"]), int(request.form["min_stock"]), int(request.form["stock"]), pid))
        db.commit(); return redirect("/products")
    p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p: return "Yo'q", 404
    return RP("<div style='padding:24px;max-width:600px;margin:0 auto;'><div class='card'><h1 style='margin-bottom:24px;'>✏️ Tahrirlash</h1><form method='POST'><input class='input' name='name' value='{{p.name}}' required><input class='input' name='barcode' value='{{p.barcode}}' required><input class='input' type='number' step='0.01' name='price' value='{{p.price}}' required><div class='grid g2'><input class='input' type='number' name='min_stock' value='{{p.min_stock}}'><input class='input' type='number' name='stock' value='{{p.stock}}'></div><button class='btn btn-green' style='width:100%;padding:16px;'>💾 Saqlash</button></form></div></div>", p=p)

@app.route("/products/<int:pid>/delete", methods=["POST"])
def product_delete(pid):
    if not session.get('db_name'): return redirect("/db")
    db = get_db(); db.execute("DELETE FROM products WHERE id=?", (pid,)); db.commit(); return redirect("/products")

@app.route("/pos")
def pos():
    if not session.get('db_name'): return redirect("/db")
    return RP("<script src='https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js'></script><div style='padding:24px;max-width:1100px;margin:0 auto;'><h1 style='font-size:32px;margin-bottom:24px;'>🛒 Kassa</h1><div class='grid g2'><div class='card'><h2 style='margin-bottom:16px;'>📷 Professional Skaner</h2><div style='display:flex;gap:8px;margin-bottom:16px;'><input id='mb' class='input' placeholder='Barcode...' style='margin:0;'><button class='btn btn-primary' onclick='ms()'>🔍</button></div><button class='btn btn-green' style='width:100%;' onclick='ss()'>📷 Kamera</button><div id='sr' style='border-radius:12px;overflow:hidden;min-height:200px;background:#000;margin-top:12px;'></div><button class='btn btn-red' style='width:100%;margin-top:12px;display:none;' id='sb' onclick='xs()'>⏹ Stop</button></div><div class='card'><div style='display:flex;justify-content:space-between;margin-bottom:16px;'><h2>🧺 Savat</h2><button class='btn btn-red btn-sm' onclick='cc()'>🗑</button></div><div id='ct' style='min-height:200px;max-height:400px;overflow-y:auto;'></div><div class='total-bar'><div style='color:var(--dim);'>JAMI</div><div class='total-amount' id='tt'>0 so'm</div></div><label style='display:flex;align-items:center;gap:10px;margin-top:16px;'><input type='checkbox' id='snd' checked> 🔊 Ovoz</label><button class='btn btn-green' style='width:100%;padding:18px;margin-top:16px;' onclick='oc()'>💳 To'lov</button></div></div></div><div id='cm' class='modal-overlay'><div class='modal'><h2 style='margin-bottom:20px;text-align:center;'>💳 To'lov turi</h2><div class='grid g2'><button class='btn btn-green' style='padding:16px;' onclick=\"doPay('cash')\">💵 Naqd</button><button class='btn btn-primary' style='padding:16px;' onclick=\"doPay('card')\">💳 Karta</button><button class='btn btn-gray' style='padding:16px;' onclick='openCredit()'>📝 Nasiya</button><button class='btn btn-gray' style='padding:16px;' onclick=\"doPay('mixed')\">🔀 Aralash</button></div><button class='btn btn-red' style='width:100%;margin-top:12px;' onclick='xc()'>Bekor</button></div></div><div id='crm' class='modal-overlay'><div class='modal'><h2 style='margin-bottom:20px;text-align:center;'>📝 Nasiya ma'lumotlari</h2><input class='input' id='cf' placeholder='👤 Ism Familiya' style='margin-bottom:12px;'><input class='input' id='cp' placeholder='📱 Telefon' style='margin-bottom:16px;'><button class='btn btn-green' style='width:100%;padding:16px;margin-bottom:8px;' onclick=\"doPay('credit')\">✅ Saqlash</button><button class='btn btn-gray' style='width:100%;' onclick='backToPayment()'>← Orqaga</button></div></div><script>let C=[],sc=null,ls='';const F=n=>new Intl.NumberFormat('ru-RU').format(n);function rc(){const e=document.getElementById('ct');if(!C.length){e.innerHTML='<div style=\"text-align:center;color:var(--dim);padding:60px;\">🛒 Savat bo\\'sh</div>';document.getElementById('tt').textContent='0 so\\'m';return}let h='',t=0;C.forEach((x,i)=>{const s=x.price*x.qty;t+=s;h+='<div class=\"cart-item\"><div><div style=\"font-weight:600;\">'+x.name+'</div><div style=\"color:var(--dim);font-size:12px;\">'+F(x.price)+' × '+x.qty+'</div></div><div style=\"display:flex;gap:6px;align-items:center\"><button class=\"qty-btn\" onclick=\"cq('+i+',-1)\">−</button><span style=\"min-width:32px;text-align:center;font-weight:700\">'+x.qty+'</span><button class=\"qty-btn\" onclick=\"cq('+i+',1)\">+</button></div></div>'});e.innerHTML=h;document.getElementById('tt').textContent=F(t)+\" so'm\"}function cq(i,d){C[i].qty=Math.max(1,C[i].qty+d);rc()}function cc(){C=[];rc()}async function ab(c){try{const r=await fetch('/api/product/by-barcode?code='+encodeURIComponent(c));if(!r.ok)throw 0;const p=await r.json();const x=C.find(y=>y.id===p.id);if(x)x.qty++;else C.push({...p,qty:1});if(document.getElementById('snd').checked)bp();rc()}catch{if(confirm('Topilmadi: '+c+'\\nYangi qo\\'shasizmi?'))location.href='/products/new?barcode='+encodeURIComponent(c)}}function bp(){try{const c=new(window.AudioContext||window.webkitAudioContext)(),o=c.createOscillator(),g=c.createGain();o.connect(g);g.connect(c.destination);o.frequency.value=880;g.gain.value=.1;o.start();o.stop(c.currentTime+.1)}catch{}}async function ss(){if(sc)return;const region=document.getElementById('sr');region.innerHTML='<div style=\"display:flex;align-items:center;justify-content:center;height:200px;color:var(--dim)\">📷 Kamera yuklanmoqda...</div>';sc=new Html5Qrcode('sr');let cams=[];try{cams=await Html5Qrcode.getCameras();}catch(e){}let camId=null;if(cams.length){camId=cams[0].id;for(const c of cams){if(/back|rear|environment|orqa/i.test(c.label||'')){camId=c.id;break;}}}const onOk=function(txt){if(txt&&txt!==ls){ls=txt;ab(txt);if(navigator.vibrate)navigator.vibrate(80);setTimeout(function(){ls='';},700);}};const onErr=function(){};const hq={fps:60,qrbox:{width:260,height:140},videoConstraints:{facingMode:{ideal:'environment'},width:{ideal:1920},height:{ideal:1080},frameRate:{ideal:60},advanced:[{focusMode:'continuous'}]}};let ok=false;if(camId){try{await sc.start(camId,hq,onOk,onErr);ok=true;}catch(e){}}if(!ok){try{await sc.start({facingMode:{ideal:'environment'}},hq,onOk,onErr);ok=true;}catch(e){}}if(!ok){try{await sc.start({facingMode:'environment'},{fps:30,qrbox:{width:250,height:140}},onOk,onErr);ok=true;}catch(e){}}if(!ok&&cams.length){try{await sc.start(cams[0].id,{fps:30,qrbox:{width:250,height:140}},onOk,onErr);ok=true;}catch(e){}}if(!ok){sc=null;region.innerHTML='<div style=\"padding:20px;text-align:center;color:var(--red)\">❌ Kamera ruxsati kerak</div>';alert('Kamera ochilmadi');return;}try{await sc.applyVideoConstraints({advanced:[{torch:true,focusMode:'continuous'}]});}catch(e){}document.getElementById('sb').style.display='flex';}function xs(){if(sc){sc.stop().then(function(){sc.clear();sc=null});document.getElementById('sb').style.display='none'}}function ms(){const v=document.getElementById('mb').value.trim();if(v){ab(v);document.getElementById('mb').value=''}}document.getElementById('mb').addEventListener('keydown',function(e){if(e.key==='Enter')ms()});function oc(){if(!C.length){alert('Savat bo\\'sh!');return}document.getElementById('cm').classList.add('active')}function xc(){document.getElementById('cm').classList.remove('active')}function openCredit(){document.getElementById('cm').classList.remove('active');document.getElementById('crm').classList.add('active')}function backToPayment(){document.getElementById('crm').classList.remove('active');document.getElementById('cm').classList.add('active')}async function doPay(t){let ph='',fn='';if(t==='credit'){fn=document.getElementById('cf').value.trim();ph=document.getElementById('cp').value.trim();if(!fn||!ph){alert('Ism va telefonni kiriting!');return}document.getElementById('crm').classList.remove('active')}const body={items:C.map(function(x){return{product_id:x.id,qty:x.qty}}),payment:t,customer_phone:ph,customer_name:fn};try{const r=await fetch('/api/checkout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw new Error(d.error||'Xato');alert('✅ Chek #'+d.sale_id+'\\nJami: '+F(d.total)+' so\\'m');C=[];rc();xc();document.getElementById('cp').value='';document.getElementById('cf').value='';window.open('/sales/'+d.sale_id+'/receipt','_blank')}catch(e){alert('❌ '+e.message)}}rc()</script>")

@app.route("/api/product/by-barcode")
def api_pbc():
    if not session.get('db_name'): return jsonify({"error": "db yo'q"}), 400
    c = request.args.get("code", "").strip()
    if not c: return jsonify({"error": "code kerak"}), 400
    db = get_db(); p = db.execute("SELECT * FROM products WHERE barcode=?", (c,)).fetchone()
    if not p: return jsonify({"error": "topilmadi"}), 404
    return jsonify(dict(p))

@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    if not session.get('db_name'): return jsonify({"error": "db yo'q"}), 400
    try:
        data = request.get_json(force=True, silent=True)
        if not data: return jsonify({"error": "JSON yo'q"}), 400
        items = data.get("items", []); payment = data.get("payment", "cash"); phone = data.get("customer_phone", ""); cname = data.get("customer_name", "")
        if not items: return jsonify({"error": "Savat bo'sh"}), 400
        db = get_db(); total = 0; prepared = []
        for item in items:
            pid = item.get("product_id"); qty = item.get("qty", 0)
            if not pid or qty <= 0: raise Exception("Noto'g'ri ma'lumot")
            p = db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            if not p: raise Exception("Mahsulot topilmadi")
            if p["stock"] < qty: raise Exception(f"{p['name']} yetarli emas!")
            prepared.append((p, qty)); total += p["price"] * qty
        debt = total if payment == "credit" else 0
        cur = db.execute("INSERT INTO sales(total,payment,customer_phone,customer_name,debt) VALUES(?,?,?,?,?)", (total, payment, phone, cname, debt))
        sid = cur.lastrowid
        for p, q in prepared:
            db.execute("INSERT INTO sale_items(sale_id,product_id,qty,price) VALUES(?,?,?,?)", (sid, p["id"], q, p["price"]))
            db.execute("UPDATE products SET stock=stock-? WHERE id=?", (q, p["id"]))
        if payment == "credit" and phone:
            db.execute("INSERT INTO debts(phone,full_name,total,paid) VALUES(?,?,?,0) ON CONFLICT(phone) DO UPDATE SET full_name=?,total=total+?", (phone, cname or "Mijoz", debt, cname or "Mijoz", debt))
        db.commit(); return jsonify({"sale_id": sid, "total": total})
    except Exception as e:
        try: db.rollback()
        except: pass
        return jsonify({"error": str(e)}), 400

@app.route("/sales")
def sales_list():
    if not session.get('db_name'): return redirect("/db")
    db = get_db()
    rows = db.execute("SELECT s.*, GROUP_CONCAT(p.name || ' x' || si.qty, ', ') as products FROM sales s LEFT JOIN sale_items si ON si.sale_id=s.id LEFT JOIN products p ON p.id=si.product_id GROUP BY s.id ORDER BY s.id DESC LIMIT 100").fetchall()
    return RP("<div style='padding:24px;max-width:1200px;margin:0 auto;'><h1 style='font-size:32px;margin-bottom:24px;'>🧾 Sotuvlar</h1><div class='table-wrap'><table><thead><tr><th>#</th><th>Sana</th><th>Mahsulotlar</th><th>Summa</th><th>To'lov</th><th>Mijoz</th><th>Chek</th></tr></thead><tbody>{%for s in rows%}<tr><td>#{{s.id}}</td><td style='color:var(--dim);'>{{s.created_at[:16]}}</td><td style='font-size:12px;'>{{s.products or '-'}}</td><td style='color:var(--green);font-weight:700;'>{{\"{:,.0f}\".format(s.total)}}</td><td>{%if s.payment=='cash'%}<span class='badge badge-green'>NAQD</span>{%elif s.payment=='card'%}<span class='badge badge-blue'>KARTA</span>{%elif s.payment=='credit'%}<span class='badge badge-red'>NASIYA</span>{%else%}<span class='badge badge-yellow'>ARALASH</span>{%endif%}</td><td style='font-size:12px;'>{{s.customer_name or '-'}}{%if s.customer_phone%}<br>{{s.customer_phone}}{%endif%}</td><td><a href='/sales/{{s.id}}/receipt' target='_blank' class='btn btn-gray btn-sm'>📄</a></td></tr>{%endfor%}</tbody></table></div></div>", rows=rows)

@app.route("/sales/<int:sid>/receipt")
def receipt(sid):
    if not session.get('db_name'): return "Yo'q", 404
    ft = request.args.get("format", "html"); db = get_db()
    s = db.execute("SELECT * FROM sales WHERE id=?", (sid,)).fetchone()
    if not s: return "Yo'q", 404
    items = db.execute("SELECT si.*, p.name FROM sale_items si JOIN products p ON p.id=si.product_id WHERE si.sale_id=?", (sid,)).fetchall()
    if ft == "pdf":
        try:
            from reportlab.lib.pagesizes import A6; from reportlab.pdfgen import canvas as pc; from reportlab.lib.units import mm
            buf = io.BytesIO(); c = pc.Canvas(buf, pagesize=A6); w, h = A6
            c.setFont("Helvetica-Bold", 14); c.drawCentredString(w/2, h-20*mm, "SMARTSTORE")
            c.setFont("Helvetica", 9); c.drawCentredString(w/2, h-27*mm, "#"+str(sid)+" "+str(s["created_at"])[:19])
            c.setFont("Helvetica", 10); y = h-40*mm
            for it in items: c.drawString(10*mm, y, it["name"][:25]); c.drawRightString(w-10*mm, y, f"{it['qty']}x{int(it['price'])}={int(it['qty']*it['price'])}"); y -= 5*mm
            y -= 5*mm
            if s["customer_name"]: c.drawString(10*mm, y, "Mijoz: "+s["customer_name"]); y -= 4*mm
            if s["customer_phone"]: c.drawString(10*mm, y, "Tel: "+s["customer_phone"])
            c.setFont("Helvetica-Bold", 12); c.drawRightString(w-10*mm, 22*mm, f"JAMI:{int(s['total'])} so'm")
            c.setFont("Helvetica", 9); c.drawCentredString(w/2, 12*mm, s["payment"].upper()); c.save(); buf.seek(0)
            return send_file(buf, download_name=f"chek-{sid}.pdf", mimetype="application/pdf")
        except: return "PDF xatosi", 500
    return render_template_string("<!DOCTYPE html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Chek #{{s.id}}</title><style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');body{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;font-family:'Inter',sans-serif;padding:0;margin:0}.np{position:fixed;top:20px;left:0;right:0;text-align:center;z-index:10;display:flex;gap:8px;justify-content:center;flex-wrap:wrap;padding:0 16px}.np button,.np a{padding:12px 24px;border:none;border-radius:12px;cursor:pointer;font-size:14px;font-weight:600;text-decoration:none;color:#fff;box-shadow:0 4px 15px rgba(0,0,0,.2)}.rc{max-width:420px;margin:100px auto 40px;background:#fff;border-radius:24px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.3)}.header{background:linear-gradient(135deg,#3b82f6,#10b981);padding:32px 28px;color:#fff;text-align:center}.header h1{font-size:28px;font-weight:900;margin:0}.header .sub{font-size:12px;opacity:.9;margin-top:6px}.header .id{font-size:16px;font-weight:700;margin-top:12px;background:rgba(255,255,255,.2);display:inline-block;padding:6px 16px;border-radius:999px}.body{padding:28px}.items{margin-bottom:20px}.item{padding:14px 0;border-bottom:1px solid #f1f5f9}.item:last-child{border-bottom:none}.item-top{display:flex;justify-content:space-between;align-items:start;gap:12px}.item-name{font-weight:600;font-size:15px;color:#0f172a;flex:1}.item-subtotal{font-weight:700;color:#10b981;font-size:15px}.item-detail{font-size:12px;color:#64748b}.total-section{background:#f8fafc;margin:0 -28px;padding:24px 28px;border-top:2px dashed #e2e8f0}.total-row{display:flex;justify-content:space-between;padding:4px 0;font-size:14px;color:#64748b}.total-row.grand{font-size:24px;font-weight:900;color:#0f172a;padding:12px 0 0;margin-top:8px;border-top:1px solid #e2e8f0}.total-row.grand .amount{color:#10b981}.info{margin-top:20px;padding:16px;background:#f1f5f9;border-radius:12px}.info-row{display:flex;justify-content:space-between;padding:6px 0;font-size:13px}.info-row .label{color:#64748b}.info-row .value{font-weight:600;color:#0f172a}.debt-box{margin-top:16px;padding:14px;background:linear-gradient(135deg,#fef3c7,#fde68a);border-radius:12px;text-align:center;border:2px solid #f59e0b}.debt-box .label{font-size:12px;color:#92400e;font-weight:600;text-transform:uppercase}.debt-box .amount{font-size:24px;font-weight:900;color:#b45309;margin-top:4px}.footer{text-align:center;padding:24px;background:#0f172a;color:#94a3b8;font-size:12px}.footer .emoji{font-size:32px;display:block;margin-bottom:8px}.payment-badge{display:inline-block;padding:4px 12px;border-radius:999px;font-size:11px;font-weight:700;text-transform:uppercase}.payment-badge.cash{background:#d1fae5;color:#065f46}.payment-badge.card{background:#dbeafe;color:#1e40af}.payment-badge.credit{background:#fee2e2;color:#991b1b}.payment-badge.mixed{background:#fef3c7;color:#92400e}@media print{body{background:#fff;padding:0}.np{display:none!important}.rc{margin:0;box-shadow:none;border-radius:0;max-width:100%}.header{border-radius:0}}@media(max-width:500px){.rc{margin:80px 12px 20px}.np{top:10px}.np button,.np a{padding:10px 16px;font-size:13px}}</style></head><body><div class='np'><button onclick='window.print()' style='background:linear-gradient(135deg,#3b82f6,#2563eb)'>🖨 Chop etish</button><a href='/sales/{{s.id}}/receipt?format=pdf' style='background:linear-gradient(135deg,#10b981,#059669)'>📥 PDF yuklash</a><button onclick='window.close()' style='background:linear-gradient(135deg,#ef4444,#dc2626)'>✖ Yopish</button></div><div class='rc'><div class='header'><h1>🏪 SMARTSTORE</h1><div class='sub'>Chek • {{s.created_at[:19]}}</div><div class='id'>#{{ '{:06d}'.format(s.id) }}</div></div><div class='body'><div class='items'>{%for it in items%}<div class='item'><div class='item-top'><span class='item-name'>{{it.name}}</span><span class='item-subtotal'>{{'{:,.0f}'.format(it.qty*it.price)}} so'm</span></div><div class='item-detail'>{{it.qty}} × {{'{:,.0f}'.format(it.price)}} so'm</div></div>{%endfor%}</div><div class='total-section'><div class='total-row'><span>Mahsulotlar soni</span><span>{{items|length}} ta</span></div><div class='total-row grand'><span>JAMI:</span><span class='amount'>{{'{:,.0f}'.format(s.total)}} so'm</span></div></div><div class='info'><div class='info-row'><span class='label'>To'lov turi</span><span class='value'>{%if s.payment=='cash'%}<span class='payment-badge cash'>💵 NAQD</span>{%elif s.payment=='card'%}<span class='payment-badge card'>💳 KARTA</span>{%elif s.payment=='credit'%}<span class='payment-badge credit'>📝 NASIYA</span>{%else%}<span class='payment-badge mixed'>🔀 ARALASH</span>{%endif%}</span></div>{%if s.customer_name%}<div class='info-row'><span class='label'>Mijoz</span><span class='value'>{{s.customer_name}}</span></div>{%endif%}{%if s.customer_phone%}<div class='info-row'><span class='label'>📱 Telefon</span><span class='value'>{{s.customer_phone}}</span></div>{%endif%}<div class='info-row'><span class='label'>Chek raqami</span><span class='value'>#{{ '{:06d}'.format(s.id) }}</span></div></div>{%if s.debt>0%}<div class='debt-box'><div class='label'>⚠️ QARZ</div><div class='amount'>{{'{:,.0f}'.format(s.debt)}} so'm</div></div>{%endif%}</div><div class='footer'><span class='emoji'>🙏</span><div>Xaridingiz uchun rahmat!</div><div style='margin-top:8px;opacity:.7;'>SmartStore POS © 2026</div></div></div></body></html>", s=s, items=items)

@app.route("/debts")
def debts_page():
    if not session.get('db_name'): return redirect("/db")
    db = get_db()
    rows = db.execute("SELECT * FROM debts WHERE total>0 ORDER BY total DESC").fetchall()
    td = sum(r["total"] for r in rows); tp = sum(r["paid"] for r in rows) if rows else 0
    return RP("<div style='padding:24px;max-width:1000px;margin:0 auto;'><h1 style='font-size:32px;margin-bottom:24px;'>💳 Qarzdorlar</h1><div class='grid g3' style='margin-bottom:20px;'><div class='stat-card'><div class='stat-label'>💸 Jami qarz</div><div class='stat-value' style='color:var(--red);'>{{\"{:,.0f}\".format(td)}}</div></div><div class='stat-card'><div class='stat-label'>✅ To'langan</div><div class='stat-value' style='color:var(--green);'>{{\"{:,.0f}\".format(tp)}}</div></div><div class='stat-card'><div class='stat-label'>👥 Qarzdorlar</div><div class='stat-value'>{{rows|length}}</div></div></div><div class='table-wrap'><table><thead><tr><th>Ism Familiya</th><th>Telefon</th><th>Qarz</th><th>To'lov</th></tr></thead><tbody>{%for d in rows%}<tr><td><strong>{{d.full_name}}</strong></td><td style='font-family:monospace;'>{{d.phone}}</td><td style='color:var(--red);font-weight:700;'>{{\"{:,.0f}\".format(d.total)}}</td><td><form method='POST' action='/debts/{{d.id}}/pay' style='display:flex;gap:6px;'><input type='number' name='amount' placeholder='Summa' required style='width:120px;padding:8px;background:var(--bg);color:#fff;border:1px solid var(--border);border-radius:8px;'><button class='btn btn-green btn-sm'>💰</button></form></td></tr>{%else%}<tr><td colspan='4' style='text-align:center;color:var(--dim);padding:40px;'>✅ Qarzdor yo'q</td></tr>{%endfor%}</tbody></table></div></div>", rows=rows, td=td, tp=tp)

@app.route("/debts/<int:did>/pay", methods=["POST"])
def debt_pay(did):
    if not session.get('db_name'): return redirect("/db")
    amt = float(request.form["amount"]); db = get_db()
    db.execute("UPDATE debts SET total=MAX(0,total-?), paid=COALESCE(paid,0)+? WHERE id=?", (amt, amt, did))
    db.commit(); return redirect("/debts")

@app.route("/reports")
def reports_page():
    if not session.get('db_name'): return redirect("/db")
    db = get_db(); p = request.args.get("period", "day")
    w = {"day": "date(created_at)=date('now')", "week": "created_at>=date('now','-7 days')", "month": "created_at>=date('now','-30 days')"}.get(p, "date(created_at)=date('now')")
    st = db.execute("SELECT COUNT(*) c,COALESCE(SUM(total),0) s FROM sales WHERE "+w).fetchone()
    bp = db.execute("SELECT payment,SUM(total) s FROM sales WHERE "+w+" GROUP BY payment").fetchall()
    tp = db.execute("SELECT p.name,SUM(si.qty) q,SUM(si.qty*si.price) s FROM sale_items si JOIN products p ON p.id=si.product_id JOIN sales sl ON sl.id=si.sale_id WHERE "+w+" GROUP BY si.product_id ORDER BY s DESC LIMIT 5").fetchall()
    dc_ = db.execute("SELECT COUNT(*) c FROM debts WHERE total>0").fetchone()[0]
    given = db.execute("SELECT COALESCE(SUM(total+paid),0) FROM debts").fetchone()[0]
    paid_ = db.execute("SELECT COALESCE(SUM(paid),0) FROM debts").fetchone()[0]
    rest = db.execute("SELECT COALESCE(SUM(total),0) FROM debts").fetchone()[0]
    ac = (st["s"]/st["c"]) if st["c"] > 0 else 0
    return RP("<div style='padding:16px;max-width:900px;margin:0 auto;'><h1 style='font-size:28px;margin-bottom:16px;'>📈 Hisobotlar</h1><div style='display:flex;gap:8px;margin-bottom:16px;'><a href='?period=day' class='btn {%if period==\"day\"%}btn-primary{%else%}btn-gray{%endif%}' style='flex:1;'>📅 Kun</a><a href='?period=week' class='btn {%if period==\"week\"%}btn-primary{%else%}btn-gray{%endif%}' style='flex:1;'>Hafta</a><a href='?period=month' class='btn {%if period==\"month\"%}btn-primary{%else%}btn-gray{%endif%}' style='flex:1;'>Oy</a></div><button class='btn' onclick='window.print()' style='width:100%;padding:16px;margin-bottom:16px;background:linear-gradient(135deg,#3b82f6,#8b5cf6);'>📄 Hisobot yaratish</button><div class='grid g2' style='margin-bottom:12px;'><div class='stat-card'><div class='stat-label'>💰 Jami savdo</div><div class='stat-value' style='color:var(--green);'>{{\"{:,.0f}\".format(st.s)}} so'm</div></div><div class='stat-card'><div class='stat-label'>🧾 Cheklar</div><div class='stat-value'>{{st.c}}</div></div><div class='stat-card'><div class='stat-label'>📊 O'rtacha</div><div class='stat-value'>{{\"{:,.0f}\".format(ac)}}</div></div><div class='stat-card'><div class='stat-label'>👥 Qarzdorlar</div><div class='stat-value'>{{dc_}}</div></div></div><div class='card' style='margin-bottom:12px;'><h2 style='margin-bottom:12px;'>💸 Qarz holati</h2><div class='grid g2'><div style='background:rgba(59,130,246,.1);border-radius:12px;padding:14px;'><div class='stat-label'>Jami berilgan</div><div style='font-size:20px;font-weight:800;'>{{\"{:,.0f}\".format(given)}} so'm</div></div><div style='background:rgba(16,185,129,.1);border-radius:12px;padding:14px;'><div class='stat-label'>To'langan</div><div style='font-size:20px;font-weight:800;color:var(--green);'>{{\"{:,.0f}\".format(paid_)}} so'm</div></div><div style='background:rgba(239,68,68,.1);border-radius:12px;padding:14px;grid-column:span 2;'><div class='stat-label'>Qolgan qarz</div><div style='font-size:20px;font-weight:800;color:var(--red);'>{{\"{:,.0f}\".format(rest)}} so'm</div></div></div></div><div class='grid g2'><div class='card'><h2 style='margin-bottom:12px;'>💳 To'lov turlari</h2>{%for x in bp%}<div style='display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);'><span>{{x.payment|upper}}</span><span style='color:var(--green);font-weight:700;'>{{\"{:,.0f}\".format(x.s)}}</span></div>{%else%}<p style='color:var(--dim);text-align:center;'>Ma'lumot yo'q</p>{%endfor%}</div><div class='card'><h2 style='margin-bottom:12px;'>🏆 Top 5</h2>{%for x in tp%}<div style='display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);'><div><div style='font-weight:600;'>{{x.name}}</div><div style='font-size:11px;color:var(--dim);'>{{x.q}} dona</div></div><span style='color:var(--green);font-weight:700;'>{{\"{:,.0f}\".format(x.s)}}</span></div>{%else%}<p style='color:var(--dim);text-align:center;'>Hali savdo yo'q</p>{%endfor%}</div></div></div>", period=p, st=st, bp=bp, tp=tp, dc_=dc_, given=given, paid_=paid_, rest=rest, ac=ac)

def start_bot_thread():
    if not BOT_TOKEN: print("⚠️ BOT_TOKEN yo'q"); return
    try:
        import asyncio
        from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
        from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
        
        async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_user
            app_url_with_user = APP_URL
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Ilovani ochish", web_app=WebAppInfo(url=app_url_with_user))], [InlineKeyboardButton("ℹ️ Yordam", callback_data="help")]])
            await update.message.reply_html("👋 <b>{}</b>\n\n🏪 SmartStore POS\n\n👇 Ilovaga o'ting:\n\n1️⃣ Database yarating yoki ulaning\n2️⃣ Mahsulot qo'shing\n3️⃪ Sotuv qiling".format(user.full_name), reply_markup=kb)
        
        async def cb_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
            query = update.callback_query; await query.answer()
            await query.edit_message_text("ℹ️ Ilovani oching → Database → Mahsulot → Sotuv")
        
        async def run_bot():
            app_bot = Application.builder().token(BOT_TOKEN).build()
            app_bot.add_handler(CommandHandler("start", cmd_start))
            app_bot.add_handler(CallbackQueryHandler(cb_help, pattern="^help$"))
            print("🤖 Telegram bot ishga tushdi!")
            async with app_bot:
                await app_bot.start()
                await app_bot.updater.start_polling(drop_pending_updates=True)
                await asyncio.Event().wait()
        
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        loop.run_until_complete(run_bot())
    except Exception as e: print("❌ Bot xatosi:", e)

if __name__ == "__main__":
    print("🤖 Bot ishga tushmoqda...")
    threading.Thread(target=start_bot_thread, daemon=True).start()
    print("="*50); print("🏪 SmartStore POS (Database System)"); print("="*50)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
