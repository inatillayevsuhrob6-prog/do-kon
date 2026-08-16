from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
import sqlite3
import datetime
import json
import os
import base64
from io import BytesIO
from PIL import Image
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import threading
import time

app = Flask(__name__)
app.secret_key = "dukon_boshqaruvi_secret_key_2024"

# ==================== DATABASE ====================
def get_db():
    conn = sqlite3.connect("shop.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Ma'lumotlar bazasini yaratish"""
    conn = get_db()
    c = conn.cursor()
    
    # Mahsulotlar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        barcode TEXT UNIQUE NOT NULL,
        price REAL NOT NULL,
        quantity INTEGER DEFAULT 0,
        category TEXT
    )''')
    
    # Sotuvlar jadvali
    c.execute('''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        quantity INTEGER,
        total REAL,
        date TEXT,
        FOREIGN KEY (product_id) REFERENCES products (id)
    )''')
    
    # Test ma'lumotlar
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        sample_products = [
            ("Non", "123456789", 5000, 20, "Oziq-ovqat"),
            ("Sut", "987654321", 12000, 15, "Sut mahsulotlari"),
            ("Tuxum", "555555555", 2000, 30, "Oziq-ovqat"),
            ("Yog'", "444444444", 25000, 5, "Sut mahsulotlari"),
            ("Un", "333333333", 8000, 3, "Oziq-ovqat"),
            ("Pepsi", "111111111", 10000, 10, "Ichimliklar"),
            ("Coca-cola", "222222222", 12000, 8, "Ichimliklar")
        ]
        for p in sample_products:
            c.execute("INSERT INTO products (name, barcode, price, quantity, category) VALUES (?,?,?,?,?)", p)
    
    conn.commit()
    conn.close()
    print("✅ Ma'lumotlar bazasi tayyor!")

# ==================== HTML TEMPLATES ====================
# Barcha HTML kodlari string sifatida
HTML_DASHBOARD = '''
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - Do'kon boshqaruvi</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .navbar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .card { border: none; border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); transition: transform 0.3s; cursor: pointer; }
        .card:hover { transform: translateY(-5px); }
        .stat-card { background: white; border-radius: 15px; padding: 20px; margin-bottom: 20px; }
        .stat-icon { font-size: 40px; opacity: 0.3; position: absolute; right: 20px; top: 20px; }
        .low-stock-item { border-left: 4px solid #dc3545; margin-bottom: 10px; }
        .toast-container { position: fixed; top: 20px; right: 20px; z-index: 9999; }
        .product-card { background: white; border-radius: 10px; padding: 10px; margin: 10px; display: inline-block; width: 200px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="fas fa-store"></i> Do'kon boshqaruvi</a>
            <div>
                <a href="/" class="btn btn-outline-light"><i class="fas fa-chart-line"></i> Dashboard</a>
                <a href="/products" class="btn btn-outline-light"><i class="fas fa-boxes"></i> Mahsulotlar</a>
                <a href="/scan" class="btn btn-outline-light"><i class="fas fa-qrcode"></i> Skaner</a>
                <a href="/warehouse" class="btn btn-outline-light"><i class="fas fa-warehouse"></i> Ombor</a>
            </div>
        </div>
    </nav>

    <div class="toast-container" id="toastContainer"></div>

    <div class="container mt-4">
        <h2 class="text-white mb-4"><i class="fas fa-chart-line"></i> Dashboard</h2>
        
        <div class="row">
            <div class="col-md-3" onclick="window.location.href='/products'">
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-box"></i></div>
                    <h6>Jami mahsulotlar</h6>
                    <h2>{{ total_products }}</h2>
                    <small>ta mahsulot</small>
                </div>
            </div>
            <div class="col-md-3" onclick="window.location.href='/warehouse'">
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-cubes"></i></div>
                    <h6>Ombor zaxirasi</h6>
                    <h2>{{ total_stock }}</h2>
                    <small>dona</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-money-bill"></i></div>
                    <h6>Jami qiymat</h6>
                    <h2>{{ "{:,.0f}".format(total_value) }} so'm</h2>
                    <small>ombordagi</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-chart-simple"></i></div>
                    <h6>Bugungi sotuv</h6>
                    <h2>{{ "{:,.0f}".format(today_sales) }} so'm</h2>
                    <small>so'm</small>
                </div>
            </div>
        </div>

        <div class="row mt-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header bg-danger text-white">
                        <i class="fas fa-exclamation-triangle"></i> Kamayib borayotgan mahsulotlar
                    </div>
                    <div class="card-body">
                        {% if low_stock %}
                            {% for product in low_stock %}
                            <div class="low-stock-item d-flex justify-content-between align-items-center p-2">
                                <div>
                                    <strong>{{ product['name'] }}</strong><br>
                                    <small>Shtrix: {{ product['barcode'] }}</small>
                                </div>
                                <span class="badge bg-danger rounded-pill">{{ product['quantity'] }} dona qoldi</span>
                            </div>
                            {% endfor %}
                        {% else %}
                            <p class="text-center text-success"><i class="fas fa-check-circle"></i> Barcha mahsulotlar yetarli!</p>
                        {% endif %}
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header bg-success text-white">
                        <i class="fas fa-fire"></i> Eng ko'p sotilganlar
                    </div>
                    <div class="card-body">
                        {% if top_products %}
                            {% for product in top_products %}
                            <div class="d-flex justify-content-between align-items-center p-2 border-bottom">
                                <span><i class="fas fa-tag"></i> {{ product['name'] }}</span>
                                <span class="badge bg-success rounded-pill">{{ product['total_sold'] }} dona</span>
                            </div>
                            {% endfor %}
                        {% else %}
                            <p class="text-center">Hozircha sotuvlar mavjud emas</p>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function showToast(message, type = 'success') {
            const toastContainer = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `toast align-items-center text-white bg-${type} border-0 show`;
            toast.setAttribute('role', 'alert');
            toast.innerHTML = `
                <div class="d-flex">
                    <div class="toast-body">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            `;
            toastContainer.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        }
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

HTML_PRODUCTS = '''
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <title>Mahsulotlar boshqaruvi</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .card { border-radius: 15px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        .table-container { background: white; border-radius: 15px; padding: 20px; }
        .btn-add { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; }
        .search-box { border-radius: 25px; padding: 10px 20px; border: 2px solid #e0e0e0; width: 300px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="fas fa-store"></i> Do'kon boshqaruvi</a>
            <div>
                <a href="/" class="btn btn-outline-light"><i class="fas fa-chart-line"></i> Dashboard</a>
                <a href="/products" class="btn btn-outline-light"><i class="fas fa-boxes"></i> Mahsulotlar</a>
                <a href="/scan" class="btn btn-outline-light"><i class="fas fa-qrcode"></i> Skaner</a>
                <a href="/warehouse" class="btn btn-outline-light"><i class="fas fa-warehouse"></i> Ombor</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="table-container">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h2><i class="fas fa-boxes"></i> Mahsulotlar ro'yxati</h2>
                <div>
                    <input type="text" id="searchInput" class="search-box me-2" placeholder="🔍 Qidirish..." onkeyup="searchProducts()">
                    <button class="btn btn-add" data-bs-toggle="modal" data-bs-target="#addModal">
                        <i class="fas fa-plus"></i> Yangi mahsulot
                    </button>
                </div>
            </div>
            
            <div class="table-responsive">
                <table class="table table-hover" id="productsTable">
                    <thead class="table-dark">
                        <tr>
                            <th>ID</th><th>Nomi</th><th>Shtrix kod</th><th>Narxi</th><th>Soni</th><th>Kategoriya</th><th>Harakat</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for p in products %}
                        <tr class="product-row">
                            <td>{{ p['id'] }}</td>
                            <td><strong>{{ p['name'] }}</strong></td>
                            <td><code>{{ p['barcode'] }}</code></td>
                            <td>{{ "{:,.0f}".format(p['price']) }} so'm</td>
                            <td class="{% if p['quantity'] < 5 %}text-danger fw-bold{% endif %}">
                                {{ p['quantity'] }} dona
                                {% if p['quantity'] < 5 %}
                                    <i class="fas fa-exclamation-circle text-danger"></i>
                                {% endif %}
                            </td>
                            <td><span class="badge bg-info">{{ p['category'] }}</span></td>
                            <td>
                                <button class="btn btn-sm btn-warning" onclick="editProduct({{ p['id'] }})">
                                    <i class="fas fa-edit"></i>
                                </button>
                                <button class="btn btn-sm btn-danger" onclick="deleteProduct({{ p['id'] }})">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Add Modal -->
    <div class="modal fade" id="addModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header bg-primary text-white">
                    <h5 class="modal-title"><i class="fas fa-plus"></i> Yangi mahsulot qo'shish</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <form id="addProductForm">
                    <div class="modal-body">
                        <div class="mb-3">
                            <label>Mahsulot nomi</label>
                            <input type="text" name="name" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label>Shtrix kod</label>
                            <input type="text" name="barcode" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label>Narxi (so'm)</label>
                            <input type="number" name="price" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label>Soni</label>
                            <input type="number" name="quantity" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label>Kategoriya</label>
                            <input type="text" name="category" class="form-control">
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="submit" class="btn btn-primary">Saqlash</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script>
        function searchProducts() {
            let input = document.getElementById('searchInput');
            let filter = input.value.toLowerCase();
            let rows = document.getElementsByClassName('product-row');
            
            for(let row of rows) {
                let text = row.innerText.toLowerCase();
                row.style.display = text.includes(filter) ? '' : 'none';
            }
        }
        
        document.getElementById('addProductForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            let formData = new FormData(e.target);
            let response = await fetch('/api/products', { method: 'POST', body: formData });
            if(response.ok) {
                location.reload();
            } else {
                alert('Xatolik yuz berdi!');
            }
        });
        
        async function editProduct(id) {
            let newName = prompt('Yangi nomini kiriting:');
            if(newName) {
                await fetch(`/api/products/${id}`, { method: 'PUT', body: JSON.stringify({name: newName}), headers: {'Content-Type': 'application/json'} });
                location.reload();
            }
        }
        
        async function deleteProduct(id) {
            if(confirm('Haqiqatan ham bu mahsulotni o\'chirmoqchimisiz?')) {
                await fetch(`/api/products/${id}`, { method: 'DELETE' });
                location.reload();
            }
        }
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

HTML_SCAN = '''
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <title>Shtrix kod skaner</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .scanner-container { max-width: 600px; margin: 50px auto; }
        .scan-card { background: white; border-radius: 20px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
        .barcode-input { font-size: 24px; text-align: center; letter-spacing: 2px; font-family: monospace; }
        .result-card { margin-top: 20px; border-radius: 15px; animation: fadeIn 0.5s; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
        .camera-preview { border-radius: 15px; overflow: hidden; margin-top: 20px; background: #000; }
        #video { width: 100%; height: auto; }
        .btn-scan { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; font-size: 18px; padding: 12px; }
        .sound-toggle { position: fixed; bottom: 20px; right: 20px; z-index: 1000; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="fas fa-store"></i> Do'kon boshqaruvi</a>
            <div>
                <a href="/" class="btn btn-outline-light"><i class="fas fa-chart-line"></i> Dashboard</a>
                <a href="/products" class="btn btn-outline-light"><i class="fas fa-boxes"></i> Mahsulotlar</a>
                <a href="/scan" class="btn btn-outline-light"><i class="fas fa-qrcode"></i> Skaner</a>
                <a href="/warehouse" class="btn btn-outline-light"><i class="fas fa-warehouse"></i> Ombor</a>
            </div>
        </div>
    </nav>

    <div class="scanner-container">
        <div class="scan-card">
            <h3 class="text-center mb-4"><i class="fas fa-qrcode"></i> Shtrix kod skaner</h3>
            
            <div class="mb-3">
                <label>Shtrix kodni kiriting yoki skanerlang:</label>
                <input type="text" id="barcodeInput" class="form-control barcode-input" placeholder="123456789" autofocus>
            </div>
            
            <button class="btn btn-scan w-100" onclick="scanBarcode()">
                <i class="fas fa-camera"></i> Sotish
            </button>
            
            <div class="mt-3">
                <button class="btn btn-outline-primary w-100" onclick="toggleCamera()">
                    <i class="fas fa-video"></i> Kamerani yoqish
                </button>
            </div>
            
            <div id="cameraContainer" class="camera-preview" style="display: none;">
                <video id="video" autoplay></video>
                <canvas id="canvas" style="display: none;"></canvas>
            </div>
            
            <div id="result"></div>
        </div>
    </div>

    <div class="sound-toggle">
        <button class="btn btn-dark" onclick="toggleSound()">
            <i id="soundIcon" class="fas fa-volume-up"></i>
        </button>
    </div>

    <script>
        let soundEnabled = true;
        let cameraActive = false;
        let video = null;
        let stream = null;
        
        const barcodeInput = document.getElementById('barcodeInput');
        barcodeInput.focus();
        
        barcodeInput.addEventListener('keypress', function(e) {
            if(e.key === 'Enter') scanBarcode();
        });
        
        async function scanBarcode() {
            const barcode = barcodeInput.value;
            if(!barcode) return;
            
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin"></i> Jarayon...</div>';
            
            try {
                const response = await fetch('/api/scan', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({barcode: barcode})
                });
                const data = await response.json();
                
                if(data.status === 'success') {
                    resultDiv.innerHTML = `
                        <div class="result-card alert alert-success">
                            <i class="fas fa-check-circle"></i>
                            <strong>${data.name}</strong> sotildi!<br>
                            Narxi: ${data.price.toLocaleString()} so'm<br>
                            Qolgan: ${data.remaining} dona
                        </div>
                    `;
                    if(soundEnabled) playBeep(true);
                    barcodeInput.value = '';
                    barcodeInput.focus();
                    updateStats();
                } else if(data.status === 'out_of_stock') {
                    resultDiv.innerHTML = `
                        <div class="result-card alert alert-danger">
                            <i class="fas fa-exclamation-triangle"></i>
                            <strong>${data.name}</strong> tugagan!<br>
                    Iltimos, omborni to'ldiring!
                        </div>
                    `;
                    if(soundEnabled) playBeep(false);
                } else {
                    resultDiv.innerHTML = `
                        <div class="result-card alert alert-warning">
                            <i class="fas fa-search"></i>
                            Shtrix kod topilmadi: ${data.barcode}
                        </div>
                    `;
                }
            } catch(error) {
                resultDiv.innerHTML = '<div class="alert alert-danger">Xatolik yuz berdi!</div>';
            }
        }
        
        function playBeep(success) {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.value = success ? 800 : 400;
            gainNode.gain.value = 0.3;
            
            oscillator.start();
            setTimeout(() => {
                oscillator.stop();
                audioContext.close();
            }, 300);
        }
        
        async function toggleCamera() {
            if(!cameraActive) {
                try {
                    stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: "environment"}});
                    video = document.getElementById('video');
                    video.srcObject = stream;
                    document.getElementById('cameraContainer').style.display = 'block';
                    cameraActive = true;
                    startBarcodeDetection();
                } catch(err) {
                    alert('Kamera ishga tushmadi: ' + err.message);
                }
            } else {
                if(stream) stream.getTracks().forEach(track => track.stop());
                document.getElementById('cameraContainer').style.display = 'none';
                cameraActive = false;
            }
        }
        
        function startBarcodeDetection() {
            const video = document.getElementById('video');
            const canvas = document.getElementById('canvas');
            const context = canvas.getContext('2d');
            
            setInterval(() => {
                if(video.readyState === video.HAVE_ENOUGH_DATA) {
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    context.drawImage(video, 0, 0, canvas.width, canvas.height);
                    const imageData = canvas.toDataURL('image/png');
                    
                    fetch('/api/detect_barcode', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({image: imageData})
                    })
                    .then(res => res.json())
                    .then(data => {
                        if(data.barcode) {
                            barcodeInput.value = data.barcode;
                            scanBarcode();
                        }
                    });
                }
            }, 500);
        }
        
        function toggleSound() {
            soundEnabled = !soundEnabled;
            document.getElementById('soundIcon').className = soundEnabled ? 'fas fa-volume-up' : 'fas fa-volume-mute';
        }
        
        function updateStats() {
            // Yangilash uchun dashboardga so'rov yuborish
            fetch('/api/stats').then(res => res.json());
        }
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

HTML_WAREHOUSE = '''
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <title>Omborxona boshqaruvi</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .warehouse-card { background: white; border-radius: 15px; padding: 20px; margin-bottom: 20px; }
        .stock-badge { font-size: 14px; padding: 5px 10px; border-radius: 20px; }
        .stock-low { background: #dc3545; color: white; }
        .stock-medium { background: #ffc107; color: black; }
        .stock-high { background: #28a745; color: white; }
        .progress-bar-custom { height: 10px; border-radius: 5px; transition: width 0.3s; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="fas fa-store"></i> Do'kon boshqaruvi</a>
            <div>
                <a href="/" class="btn btn-outline-light"><i class="fas fa-chart-line"></i> Dashboard</a>
                <a href="/products" class="btn btn-outline-light"><i class="fas fa-boxes"></i> Mahsulotlar</a>
                <a href="/scan" class="btn btn-outline-light"><i class="fas fa-qrcode"></i> Skaner</a>
                <a href="/warehouse" class="btn btn-outline-light"><i class="fas fa-warehouse"></i> Ombor</a>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        <div class="warehouse-card">
            <h2><i class="fas fa-warehouse"></i> Omborxona hisobi</h2>
            <p class="text-muted">Mahsulotlar sonini yangilash va nazorat qilish</p>
        </div>
        
        <div class="row">
            <div class="col-md-4">
                <div class="warehouse-card">
                    <h5><i class="fas fa-chart-pie"></i> Statistika</h5>
                    <div class="mt-3">
                        <p>Jami mahsulotlar: <strong>{{ total_products }}</strong></p>
                        <p>Jami zaxira: <strong>{{ total_stock }}</strong> dona</p>
                        <p>Kam zaxira: <strong class="text-danger">{{ low_count }}</strong> ta</p>
                    </div>
                </div>
            </div>
            <div class="col-md-8">
                <div class="warehouse-card">
                    <h5><i class="fas fa-search"></i> Qidirish</h5>
                    <input type="text" id="searchWarehouse" class="form-control" placeholder="Mahsulot nomi yoki shtrix kod..." onkeyup="filterWarehouse()">
                </div>
            </div>
        </div>
        
        <div class="warehouse-card">
            <div class="table-responsive">
                <table class="table" id="warehouseTable">
                    <thead class="table-dark">
                        <tr>
                            <th>Mahsulot</th><th>Shtrix kod</th><th>Hozirgi soni</th><th>Holat</th><th>Yangilash</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for p in products %}
                        <tr class="warehouse-row">
                            <td>
                                <strong>{{ p['name'] }}</strong><br>
                                <small class="text-muted">{{ p['category'] }}</small>
                            </td>
                            <td><code>{{ p['barcode'] }}</code></td>
                            <td>
                                <span id="qty-{{ p['id'] }}">{{ p['quantity'] }}</span> dona
                                <div class="progress-bar-custom mt-1" style="width: {{ (p['quantity'] / 50 * 100) if p['quantity'] < 50 else 100 }}%; background: {% if p['quantity'] < 5 %}#dc3545{% elif p['quantity'] < 20 %}#ffc107{% else %}#28a745{% endif %};"></div>
                            </td>
                            <td>
                                {% if p['quantity'] < 5 %}
                                    <span class="stock-badge stock-low"><i class="fas fa-exclamation-circle"></i> Tez orada tugaydi</span>
                                {% elif p['quantity'] < 20 %}
                                    <span class="stock-badge stock-medium"><i class="fas fa-chart-line"></i> O'rtacha</span>
                                {% else %}
                                    <span class="stock-badge stock-high"><i class="fas fa-check-circle"></i> Yetarli</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="input-group">
                                    <input type="number" id="input-{{ p['id'] }}" value="{{ p['quantity'] }}" class="form-control" style="width: 100px;">
                                    <button class="btn btn-primary" onclick="updateQuantity({{ p['id'] }})">
                                        <i class="fas fa-save"></i> Yangilash
                                    </button>
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        async function updateQuantity(productId) {
            const newQuantity = document.getElementById(`input-${productId}`).value;
            const response = await fetch('/api/update_quantity', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({product_id: productId, quantity: newQuantity})
            });
            
            if(response.ok) {
                document.getElementById(`qty-${productId}`).innerText = newQuantity;
                showNotification('✅ Yangilandi!', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                showNotification('❌ Xatolik!', 'danger');
            }
        }
        
        function filterWarehouse() {
            let input = document.getElementById('searchWarehouse');
            let filter = input.value.toLowerCase();
            let rows = document.getElementsByClassName('warehouse-row');
            
            for(let row of rows) {
                let text = row.innerText.toLowerCase();
                row.style.display = text.includes(filter) ? '' : 'none';
            }
        }
        
        function showNotification(msg, type) {
            const notif = document.createElement('div');
            notif.className = `alert alert-${type} position-fixed top-0 end-0 m-3`;
            notif.style.zIndex = '9999';
            notif.innerHTML = msg;
            document.body.appendChild(notif);
            setTimeout(() => notif.remove(), 2000);
        }
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

# ==================== ROUTES ====================
@app.route('/')
def dashboard():
    conn = get_db()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) as total, SUM(quantity) as stock, SUM(price*quantity) as value FROM products")
    stats = c.fetchone()
    
    today = datetime.date.today().strftime("%Y-%m-%d")
    c.execute("SELECT SUM(total) as today_sales FROM sales WHERE date LIKE ?", (f"{today}%",))
    today_sales = c.fetchone()[0] or 0
    
    c.execute("SELECT name, quantity, barcode FROM products WHERE quantity < 5 ORDER BY quantity ASC")
    low_stock = c.fetchall()
    
    c.execute('''SELECT p.name, SUM(s.quantity) as total_sold 
                 FROM sales s JOIN products p ON s.product_id = p.id 
                 GROUP BY p.id ORDER BY total_sold DESC LIMIT 5''')
    top_products = c.fetchall()
    
    conn.close()
    
    return render_template_string(HTML_DASHBOARD, 
                                 total_products=stats['total'] or 0,
                                 total_stock=stats['stock'] or 0,
                                 total_value=stats['value'] or 0,
                                 today_sales=today_sales,
                                 low_stock=low_stock,
                                 top_products=top_products)

@app.route('/products')
def products():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM products ORDER BY id")
    products = c.fetchall()
    conn.close()
    return render_template_string(HTML_PRODUCTS, products=products)

@app.route('/scan')
def scan():
    return render_template_string(HTML_SCAN)

@app.route('/warehouse')
def warehouse():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM products ORDER BY quantity ASC")
    products = c.fetchall()
    
    c.execute("SELECT COUNT(*) FROM products WHERE quantity < 5")
    low_count = c.fetchone()[0]
    
    c.execute("SELECT SUM(quantity) FROM products")
    total_stock = c.fetchone()[0] or 0
    
    conn.close()
    
    return render_template_string(HTML_WAREHOUSE, 
                                 products=products,
                                 low_count=low_count,
                                 total_products=len(products),
                                 total_stock=total_stock)

# ==================== API ENDPOINTS ====================
@app.route('/api/products', methods=['POST'])
def add_product():
    name = request.form['name']
    barcode = request.form['barcode']
    price = float(request.form['price'])
    quantity = int(request.form['quantity'])
    category = request.form.get('category', '')
    
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO products (name, barcode, price, quantity, category) VALUES (?,?,?,?,?)",
                 (name, barcode, price, quantity, category))
        conn.commit()
        return jsonify({"status": "success"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Bunday shtrix kod mavjud"}), 400
    finally:
        conn.close()

@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE products SET name = ? WHERE id = ?", (data.get('name'), product_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/products/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/scan', methods=['POST'])
def scan_barcode():
    data = request.get_json()
    barcode = data.get('barcode')
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE barcode = ?", (barcode,))
    product = c.fetchone()
    
    if product:
        if product['quantity'] > 0:
            c.execute("UPDATE products SET quantity = quantity - 1 WHERE id = ?", (product['id'],))
            c.execute("INSERT INTO sales (product_id, quantity, total, date) VALUES (?, 1, ?, datetime('now'))",
                     (product['id'], product['price']))
            conn.commit()
            result = {
                "status": "success",
                "name": product['name'],
                "price": product['price'],
                "remaining": product['quantity'] - 1
            }
        else:
            result = {"status": "out_of_stock", "name": product['name']}
    else:
        result = {"status": "not_found", "barcode": barcode}
    
    conn.close()
    return jsonify(result)

@app.route('/api/update_quantity', methods=['POST'])
def update_quantity():
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = int(data.get('quantity'))
    
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE products SET quantity = ? WHERE id = ?", (quantity, product_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/api/detect_barcode', methods=['POST'])
def detect_barcode():
    data = request.get_json()
    image_data = data.get('image')
    
    if image_data:
        # Base64 dan rasmni o'qish
        image_data = image_data.split(',')[1]
        image_bytes = base64.b64decode(image_data)
        image = Image.open(BytesIO(image_bytes))
        image_np = np.array(image)
        
        # Shtrix kodni aniqlash
        barcodes = decode(image_np)
        if barcodes:
            return jsonify({"barcode": barcodes[0].data.decode('utf-8')})
    
    return jsonify({"barcode": None})

@app.route('/api/stats')
def get_stats():
    return jsonify({"status": "ok"})

# ==================== MAIN ====================
if __name__ == '__main__':
    init_database()
    
    # Ovoz fayllarni tekshirish
    if not os.path.exists('sounds'):
        os.makedirs('sounds')
    
    print("=" * 50)
    print("🏪 DO'KON BOSHQARUV TIZIMI")
    print("=" * 50)
    print("✅ Ma'lumotlar bazasi: shop.db")
    print("📱 Dashboard: http://127.0.0.1:5000")
    print("🔍 Skaner: http://127.0.0.1:5000/scan")
    print("📦 Mahsulotlar: http://127.0.0.1:5000/products")
    print("🏚️ Ombor: http://127.0.0.1:5000/warehouse")
    print("=" * 50)
    print("🎯 Test shtrix kodlar:")
    print("   123456789 - Non (5000 so'm)")
    print("   987654321 - Sut (12000 so'm)")
    print("   555555555 - Tuxum (2000 so'm)")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
