from flask import Flask, render_template_string, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
import psycopg2
import psycopg2.extras
import bcrypt
import uuid
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'güvenli-bir-anahtar-giriniz-123456'
socketio = SocketIO(app, cors_allowed_origins="*")

# ------------------- PostgreSQL Bağlantısı -------------------
DATABASE_URL = "postgresql://neondb_owner:npg_9eNwSgZnL6Mq@ep-broad-moon-anjzygzz-pooler.c-6.us-east-1.aws.neon.tech/neondb?sslmode=require"

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# Tabloları oluştur (eğer yoksa)
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            text TEXT,
            file_data TEXT,
            file_type TEXT,
            filename TEXT,
            timestamp TEXT,
            type TEXT
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ------------------- Yardımcı fonksiyonlar -------------------
def hash_password(pwd):
    return bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(pwd, hashed):
    return bcrypt.checkpw(pwd.encode('utf-8'), hashed.encode('utf-8'))

# ------------------- HTML Şablonu (Mavi-Siyah Tema) -------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gece Mavisi Sohbet</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0a0f1e;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        /* Giriş/Kayıt Kartı */
        .auth-container {
            background: #141e30;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.5);
            padding: 40px;
            width: 400px;
            text-align: center;
            border: 1px solid #2c3e66;
        }
        .auth-container h2 {
            color: #5dade2;
            margin-bottom: 25px;
        }
        .auth-container input {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            background: #1e2a3a;
            border: 1px solid #2c3e66;
            border-radius: 30px;
            color: white;
            font-size: 1rem;
            outline: none;
        }
        .auth-container button {
            width: 100%;
            padding: 12px;
            background: #1f6e8c;
            border: none;
            border-radius: 30px;
            color: white;
            font-weight: bold;
            cursor: pointer;
            transition: 0.2s;
        }
        .auth-container button:hover {
            background: #0e4d64;
        }
        .auth-container a {
            color: #5dade2;
            text-decoration: none;
            display: block;
            margin-top: 15px;
        }
        /* Sohbet Ana Alanı */
        .chat-container {
            width: 95%;
            max-width: 1400px;
            height: 90vh;
            background: #0f172a;
            border-radius: 20px;
            display: flex;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            border: 1px solid #1e2f4b;
        }
        .sidebar {
            width: 280px;
            background: #0a0f1e;
            border-right: 1px solid #1e2f4b;
            display: flex;
            flex-direction: column;
        }
        .user-info {
            padding: 20px;
            background: #111827;
            border-bottom: 1px solid #1e2f4b;
        }
        .user-info h3 {
            color: #5dade2;
        }
        .user-info p {
            color: #8ba3c7;
            font-size: 0.8rem;
        }
        .online-users {
            flex: 1;
            padding: 15px;
            overflow-y: auto;
        }
        .online-users h4 {
            color: #5dade2;
            margin-bottom: 15px;
        }
        .user-list {
            list-style: none;
        }
        .user-list li {
            padding: 10px;
            background: #111827;
            margin-bottom: 8px;
            border-radius: 12px;
            color: #cbd5e6;
            display: flex;
            justify-content: space-between;
            cursor: pointer;
            transition: 0.2s;
        }
        .user-list li:hover {
            background: #1e2a3a;
            transform: translateX(5px);
        }
        .main-chat {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        .chat-header {
            background: #111827;
            padding: 15px 20px;
            border-bottom: 1px solid #1e2f4b;
            color: #5dade2;
            font-weight: bold;
        }
        .chat-messages {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .message {
            display: flex;
            flex-direction: column;
            max-width: 70%;
            animation: fadeIn 0.2s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .message.own {
            align-self: flex-end;
        }
        .message.other {
            align-self: flex-start;
        }
        .message-header {
            font-size: 0.7rem;
            margin-bottom: 4px;
            padding: 0 8px;
            display: flex;
            gap: 8px;
        }
        .message-username {
            color: #5dade2;
            font-weight: bold;
        }
        .message-time {
            color: #6c86a3;
        }
        .message-bubble {
            background: #1e2a3a;
            padding: 8px 14px;
            border-radius: 18px;
            color: #e2e8f0;
            word-wrap: break-word;
        }
        .own .message-bubble {
            background: #1f6e8c;
            color: white;
        }
        .chat-input-area {
            display: flex;
            padding: 15px;
            background: #111827;
            border-top: 1px solid #1e2f4b;
            gap: 10px;
        }
        #messageInput {
            flex: 1;
            padding: 12px;
            background: #0f172a;
            border: 1px solid #2c3e66;
            border-radius: 30px;
            color: white;
            outline: none;
        }
        button {
            background: #1f6e8c;
            border: none;
            padding: 10px 18px;
            border-radius: 30px;
            color: white;
            cursor: pointer;
            transition: 0.2s;
        }
        button:hover {
            background: #0e4d64;
        }
        .logout-btn {
            background: #7f1a1a;
            margin-top: 15px;
        }
        .logout-btn:hover {
            background: #991b1b;
        }
        @media (max-width: 768px) {
            .sidebar { width: 200px; }
            .message { max-width: 85%; }
        }
    </style>
</head>
<body>
    {% if not session.username %}
    <!-- Giriş / Kayıt Ekranı -->
    <div class="auth-container">
        <h2>🌊 Gece Mavisi Sohbet</h2>
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for msg in messages %}
                    <p style="color: #f87171;">{{ msg }}</p>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="post" action="{{ url_for('login') }}">
            <input type="text" name="username" placeholder="Kullanıcı Adı" required>
            <input type="password" name="password" placeholder="Şifre" required>
            <button type="submit">Giriş Yap</button>
        </form>
        <a href="#" onclick="showRegister()">Hesap yok mu? Kayıt ol</a>
        <form id="registerForm" method="post" action="{{ url_for('register') }}" style="display:none; margin-top:15px;">
            <input type="text" name="username" placeholder="Kullanıcı Adı" required>
            <input type="password" name="password" placeholder="Şifre" required>
            <button type="submit">Kayıt Ol</button>
        </form>
    </div>
    <script>
        function showRegister() {
            document.getElementById('registerForm').style.display = 'block';
        }
    </script>
    {% else %}
    <!-- Sohbet Ana Ekranı -->
    <div class="chat-container">
        <div class="sidebar">
            <div class="user-info">
                <h3>👤 {{ session.username }}</h3>
                <p>✅ Çevrimiçi</p>
                <a href="{{ url_for('logout') }}" style="text-decoration:none;"><button class="logout-btn">🚪 Çıkış Yap</button></a>
            </div>
            <div class="online-users">
                <h4>📡 Çevrimiçi (<span id="userCount">0</span>)</h4>
                <ul class="user-list" id="userList"></ul>
            </div>
        </div>
        <div class="main-chat">
            <div class="chat-header">💬 Genel Sohbet</div>
            <div class="chat-messages" id="chatMessages"></div>
            <div class="chat-input-area">
                <input type="text" id="messageInput" placeholder="Mesajınızı yazın..." autocomplete="off">
                <button id="sendBtn">Gönder</button>
            </div>
        </div>
    </div>

    <script>
        var socket = io();
        var username = "{{ session.username }}";

        socket.emit('join', {username: username});

        function sendMessage() {
            let text = document.getElementById('messageInput').value.trim();
            if(text) {
                socket.emit('send_message', {text: text});
                document.getElementById('messageInput').value = '';
            }
        }

        document.getElementById('sendBtn').onclick = sendMessage;
        document.getElementById('messageInput').addEventListener('keypress', function(e) {
            if(e.key === 'Enter') sendMessage();
        });

        socket.on('message_history', function(history) {
            const container = document.getElementById('chatMessages');
            container.innerHTML = '';
            history.forEach(msg => {
                addMessage(msg, msg.username === username);
            });
        });

        socket.on('new_message', function(msg) {
            addMessage(msg, msg.username === username);
        });

        socket.on('user_list', function(users) {
            const list = document.getElementById('userList');
            const count = Object.keys(users).length;
            document.getElementById('userCount').innerText = count;
            list.innerHTML = '';
            for(let id in users) {
                let li = document.createElement('li');
                li.innerHTML = `<span>${escapeHtml(users[id])}</span>`;
                list.appendChild(li);
            }
        });

        function addMessage(msg, isOwn) {
            const container = document.getElementById('chatMessages');
            const div = document.createElement('div');
            div.className = `message ${isOwn ? 'own' : 'other'}`;
            div.innerHTML = `
                <div class="message-header">
                    <span class="message-username">${escapeHtml(msg.username)}</span>
                    <span class="message-time">${msg.timestamp}</span>
                </div>
                <div class="message-bubble">${escapeHtml(msg.text)}</div>
            `;
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
        }

        function escapeHtml(str) {
            if(!str) return '';
            return str.replace(/[&<>]/g, function(m) {
                if(m === '&') return '&amp;';
                if(m === '<') return '&lt;';
                if(m === '>') return '&gt;';
                return m;
            });
        }
    </script>
    {% endif %}
</body>
</html>
"""

@app.route('/')
def index():
    if 'username' in session:
        return render_template_string(HTML_TEMPLATE, session=session)
    else:
        return render_template_string(HTML_TEMPLATE, session={})

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if user and check_password(password, user['password']):
        session['username'] = username
    else:
        flash('Hatalı kullanıcı adı veya şifre')
    return redirect(url_for('index'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']
    hashed = hash_password(password)
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed))
        conn.commit()
        session['username'] = username
    except psycopg2.IntegrityError:
        conn.rollback()
        flash('Bu kullanıcı adı zaten alınmış.')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

# ------------------- Socket.IO Olayları -------------------
active_users = {}  # sid -> username

@socketio.on('join')
def handle_join(data):
    username = data['username']
    active_users[request.sid] = username
    emit('user_list', active_users, broadcast=True)
    
    # Son 50 mesajı veritabanından al
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT id, username, text, timestamp FROM messages ORDER BY timestamp DESC LIMIT 50")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    history = [{'id': r['id'], 'username': r['username'], 'text': r['text'], 'timestamp': r['timestamp']} for r in reversed(rows)]
    emit('message_history', history)

@socketio.on('send_message')
def handle_send_message(data):
    username = active_users.get(request.sid, 'Anonim')
    text = data['text']
    msg_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime('%H:%M')
    msg = {
        'id': msg_id,
        'username': username,
        'text': text,
        'timestamp': timestamp,
        'type': 'text'
    }
    # Veritabanına kaydet
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO messages (id, username, text, timestamp, type) VALUES (%s, %s, %s, %s, %s)",
                (msg_id, username, text, timestamp, 'text'))
    conn.commit()
    cur.close()
    conn.close()
    emit('new_message', msg, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in active_users:
        username = active_users.pop(request.sid)
        emit('user_list', active_users, broadcast=True)

# ------------------- Çalıştırma -------------------
if __name__ == '__main__':
    print("💙 Mavi-Siyah Sohbet Sistemi başlıyor...")
    print("🔐 Kayıt/Giriş sistemi aktif | Veritabanı: Neon PostgreSQL")
    print("📍 http://127.0.0.1:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
