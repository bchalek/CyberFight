#!/usr/bin/env python3

"""
FutureBankTech Internal DNS Server
"""

import socket
import struct
import threading
import time
import json
import os
import subprocess
from flask import Flask, request, jsonify, render_template_string
import pymysql
import logging
from logging.handlers import RotatingFileHandler
from decimal import Decimal

app = Flask(__name__)
app.secret_key = 'dns_secret_key_123'
DNS_PORT = 9154
MANAGEMENT_PORT = 8154
ADMIN_PASSWORD = "dns_admin_2023"

log_dir = '/var/log/shared'
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [DNS-Server]: %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(log_dir, 'dns-server.log'),
            maxBytes=10240000,
            backupCount=10
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def log(message, level='INFO'):
    if level.upper() == 'ERROR':
        logger.error(message)
    elif level.upper() == 'WARNING':
        logger.warning(message)
    elif level.upper() == 'DEBUG':
        logger.debug(message)
    else:
        logger.info(message)

DB_CONFIG = {
    'host': 'db',
    'user': 'wpuser',
    'password': 'wppass',
    'database': 'wordpress',
    'charset': 'utf8mb4',
    'autocommit': True
}

class DNSRecord:
    def __init__(self, name, record_type, value, ttl=300):
        self.name = name.lower()
        self.type = record_type
        self.value = value
        self.ttl = ttl

class DNSServer:
    def __init__(self):
        """init"""
        self.records = {}
        self._db_initialized = False
        self.load_default_records()
        self._db_initialized = self.init_db()

    def wait_for_database(self, max_retries=30, delay=2):
        '''Wait for database'''
        for attempt in range(max_retries):
            try:
                conn = pymysql.connect(**DB_CONFIG)
                conn.close()
                print(f"Database connection successful after {attempt + 1} attempts")
                return True
            except Exception as e:
                print(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(delay)
        return False

    def table_exists(self, cursor, table_name):
        """Check if the table exist in the database"""
        try:
            cursor.execute("SHOW TABLES LIKE %s", (table_name,))
            return cursor.fetchone() is not None
        except Exception as e:
            print(f'Error checking if table {table_name} exists: {e}')
            return False

    def init_db(self):
        print("Initializing DNS database...")

        if not self.wait_for_database():
            print("ERROR: Could not connect to database after maximum retries")
            return False

        try:
            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor()

            if not self.table_exists(cursor, 'dns_records'):
                print("Creating dns_records table...")
                cursor.execute('''CREATE TABLE dns_records (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    type VARCHAR(10) NOT NULL,
                    value VARCHAR(255) NOT NULL,
                    ttl INT DEFAULT 300,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX(name, type)
                )''')
                print("dns_records table created successfully")
            else:
                print("dns_records table already exists")

            if not self.table_exists(cursor, 'dns_queries'):
                print("Creating dns_queries table...")
                cursor.execute('''CREATE TABLE dns_queries (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    client_ip VARCHAR(45),
                    query_name VARCHAR(255),
                    query_type VARCHAR(10),
                    response VARCHAR(255),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
                print("dns_queries table created successfully")
            else:
                print("dns_queries table already exists")

            cursor.execute('SELECT COUNT(*) FROM dns_records')
            record_count = cursor.fetchone()[0]

            if record_count == 0:
                print("Inserting default DNS records...")
                default_records = [
                    ('internal.futurebank.local', 'A', '192.168.1.100'),
                    ('payment.futurebank.local', 'A', '192.168.1.101'),
                    ('admin.futurebank.local', 'A', '192.168.1.102'),
                    ('api.futurebank.local', 'A', '192.168.1.103'),
                    ('futurebank.local', 'SOA', 'ns1.futurebank.local admin.futurebank.local 1 3600 1800 1209600 86400'),
                    ('futurebank.local', 'NS', 'ns1.futurebank.local'),
                    ('ns1.futurebank.local', 'A', '192.168.1.1'),
                    ('backup.futurebank.local', 'A', '10.0.0.50'),
                    ('staging.futurebank.local', 'CNAME', 'payment.futurebank.local')
                ]

                for name, rtype, value in default_records:
                    try:
                        cursor.execute('INSERT INTO dns_records (name, type, value) VALUES (%s, %s, %s)',
                                     (name, rtype, value))
                    except Exception as e:
                        print(f"Error inserting record {name}: {e}")

                print(f"Inserted {len(default_records)} default DNS records")
            else:
                print(f"DNS records table already contains {record_count} records")

            conn.close()
            print("Database initialization completed successfully")
            return True

        except Exception as e:
            print(f"Database initialization error: {e}")
            return False

    def load_default_records(self):
        '''Load default DNS records into memory'''
        self.records = {
            'localhost': [DNSRecord('localhost', 'A', '127.0.0.1')],
            'payment-app': [DNSRecord('payment-app', 'A', '172.18.0.3')],
            'wordpress': [DNSRecord('wordpress', 'A', '172.18.0.4')],
            'db': [DNSRecord('db', 'A', '172.18.0.2')],
            'futurebank.local': [
                DNSRecord('futurebank.local', 'A', '192.168.1.100'),
                DNSRecord('futurebank.local', 'MX', '10 mail.futurebank.local')
            ]
        }

    def get_records_from_db(self, name, record_type=None):
        """Get DNS records from database"""
        if not self._db_initialized:
            return []

        try:
            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor()

            if record_type:
                cursor.execute('SELECT name, type, value, ttl FROM dns_records WHERE name = %s AND type = %s',
                             (name.lower(), record_type))
            else:
                cursor.execute('SELECT name, type, value, ttl FROM dns_records WHERE name = %s',
                             (name.lower(),))

            records = []
            for row in cursor.fetchall():
                records.append(DNSRecord(row[0], row[1], row[2], row[3]))

            conn.close()
            return records

        except Exception as e:
            print(f"Database query error: {e}")
            return []

    def log_query(self, client_ip, query_name, query_type, response):
        """Log DNS query to database"""
        if not self._db_initialized:
            return

        try:
            conn = pymysql.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute(f'''INSERT INTO dns_queries (client_ip, query_name, query_type, response)
                            VALUES ('{client_ip}', '{query_name}', '{query_type}', '{response}')''')
            conn.close()
        except Exception as e:
            print(f"Query logging error: {e}")

    def resolve(self, name, record_type='A', client_ip='unknown'):
        '''Resolve DNS query'''
        name = name.lower().rstrip('.')

        db_records = self.get_records_from_db(name, record_type)
        if db_records:
            response = db_records[0].value
            self.log_query(client_ip, name, record_type, response)
            return db_records[0]

        if name in self.records:
            for record in self.records[name]:
                if record.type == record_type:
                    self.log_query(client_ip, name, record_type, record.value)
                    return record

        self.log_query(client_ip, name, record_type, 'NXDOMAIN')
        return None

def parse_dns_query(data):
    '''Parse DNS query packet'''
    if len(data) < 12:
        return None

    header = struct.unpack('!6H', data[:12])
    transaction_id = header[0]
    flags = header[1]
    questions = header[2]

    if questions != 1:
        return None

    offset = 12
    name_parts = []

    while offset < len(data):
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if length > 63:
            break

        name_parts.append(data[offset+1:offset+1+length].decode('utf-8'))
        offset += 1 + length

    if offset + 4 > len(data):
        return None

    query_type, query_class = struct.unpack('!HH', data[offset:offset+4])

    return {
        'transaction_id': transaction_id,
        'name': '.'.join(name_parts),
        'type': query_type,
        'class': query_class
    }

def create_dns_response(query, record):
    """Create DNS response pocket"""
    response = bytearray()

    response.extend(struct.pack('!H', query['transaction_id']))  # transaction ID
    response.extend(struct.pack('!H', 0x8180))  # Flags (todo: add recursion available)
    response.extend(struct.pack('!H', 1))  # questions
    response.extend(struct.pack('!H', 1 if record else 0))  # ansewers
    response.extend(struct.pack('!H', 0))  # Authority RRs
    response.extend(struct.pack('!H', 0))  # additional Rrs

    for part in query['name'].split('.'):
        response.append(len(part))
        response.extend(part.encode('utf-8'))
    response.append(0)
    response.extend(struct.pack('!HH', query['type'], query['class']))

    if record:
        response.extend(struct.pack('!H', 0xc00c))

        type_num = 1 if record.type == 'A' else 16 if record.type == 'TXT' else 1
        response.extend(struct.pack('!HH', type_num, 1))

        response.extend(struct.pack('!I', record.ttl))

        if record.type == 'A':
            ip_parts = record.value.split('.')
            ip_bytes = bytes([int(part) for part in ip_parts])
            response.extend(struct.pack('!H', 4))  # Data length
            response.extend(ip_bytes)
        elif record.type == 'TXT':
            txt_data = record.value.encode('utf-8')
            response.extend(struct.pack('!H', len(txt_data) + 1))
            response.append(len(txt_data))
            response.extend(txt_data)

    return bytes(response)

def handle_dns_request(data, addr, sock, dns_server):
    """Handle incoming DNS request"""
    try:
        query = parse_dns_query(data)
        if not query:
            return

        query_type_name = 'A' if query['type'] == 1 else 'TXT' if query['type'] == 16 else 'UNKNOWN'
        client_ip = addr[0]

        print(f"DNS Query from {client_ip}: {query['name']} ({query_type_name})")

        record = dns_server.resolve(query['name'], query_type_name, client_ip)
        response = create_dns_response(query, record)

        sock.sendto(response, addr)

    except Exception as e:
        print(f"DNS request handling error: {e}")

def start_dns_server():
    """Start the DNS server"""
    print(f"Starting DNS server on port {DNS_PORT}...")
    dns_server = DNSServer()

    if not dns_server._db_initialized:
        print("WARNING: DNS server starting without database - some features may not work properly")
    else:
        print("DNS database initialization successful")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', DNS_PORT))

    print(f"DNS Server listening on port {DNS_PORT}")

    while True:
        try:
            data, addr = sock.recvfrom(512)

            thread = threading.Thread(target=handle_dns_request, args=(data, addr, sock, dns_server))
            thread.daemon = True
            thread.start()
        except Exception as e:
            print(f"DNS server error: {e}")

dns_server_instance = DNSServer()

@app.route('/')
def index():
    """DNS Management Interface"""
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>FutureBankTech DNS Management</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
            h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
            .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
            .btn { background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            .btn:hover { background: #2980b9; }
            input, select { padding: 8px; margin: 5px; border: 1px solid #ddd; border-radius: 4px; }
            table { width: 100%; border-collapse: collapse; margin: 10px 0; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background: #f2f2f2; }
            .danger { color: #e74c3c; }
            .success { color: #27ae60; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1> FutureBankTech DNS Management Portal</h1>

            <div class="section">
                <h3>Quick Actions</h3>
                <a href="/records" class="btn">View All Records</a>
                <a href="/queries" class="btn">Query Logs</a>
                <a href="/zone_transfer" class="btn">Zone Transfer</a>
                <a href="/admin" class="btn">Admin Panel</a>
            </div>

            <div class="section">
                <h3>Add DNS Record (Payment Required)</h3>
                <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; margin: 10px 0; border-radius: 4px;">
                    <strong>Pricing:</strong> A: $10 | AAAA: $12 | CNAME: $8 | MX: $15 | TXT: $5 | NS: $20
                </div>
                <form action="/add_record" method="POST">
                    <input type="text" name="name" placeholder="Domain name" required>
                    <select name="type" id="recordType" onchange="updatePrice()">
                        <option value="A">A ($10.00)</option>
                        <option value="AAAA">AAAA ($12.00)</option>
                        <option value="CNAME">CNAME ($8.00)</option>
                        <option value="MX">MX ($15.00)</option>
                        <option value="TXT">TXT ($5.00)</option>
                        <option value="NS">NS ($20.00)</option>
                    </select>
                    <input type="text" name="value" placeholder="Record value" required>
                    <input type="number" name="ttl" value="300" placeholder="TTL">
                    <br><br>
                    <strong>Payment Portal Credentials:</strong><br>
                    <input type="text" name="username" placeholder="Username" required>
                    <input type="password" name="password" placeholder="Password" required>
                    <br><br>
                    <button type="submit" class="btn">Pay & Add Record</button>
                </form>
            </div>

            <div class="section">
                <h3>DNS Lookup</h3>
                <form action="/lookup" method="GET">
                    <input type="text" name="domain" placeholder="Domain to lookup" required>
                    <select name="type">
                        <option value="A">A</option>
                        <option value="TXT">TXT</option>
                        <option value="MX">MX</option>
                        <option value="NS">NS</option>
                    </select>
                    <button type="submit" class="btn">Lookup</button>
                </form>
            </div>

            <div class="section">
                <h3>System Status</h3>
                <p><strong>DNS Server:</strong> <span class="success">Running on port 53</span></p>
                <p><strong>Management Interface:</strong> <span class="success">Running on port 8053</span></p>
                <p><strong>Database:</strong> <span class="success">Connected</span></p>
                <p><strong>Records in DB:</strong> <span id="record-count">Loading...</span></p>
            </div>
        </div>

        <script>
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('record-count').textContent = data.record_count;
                });
        </script>
    </body>
    </html>
    ''')

@app.route('/records')
def view_records():
    """View all DNS records"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT name, type, value, ttl FROM dns_records ORDER BY name')
        records = cursor.fetchall()
        conn.close()

        html = '''
        <h2>DNS Records</h2>
        <table>
            <tr><th>Name</th><th>Type</th><th>Value</th><th>TTL</th></tr>
        '''

        for record in records:
            html += f'<tr><td>{record[0]}</td><td>{record[1]}</td><td>{record[2]}</td><td>{record[3]}</td></tr>'

        html += '</table><br><a href="/">Back to Main</a>'
        return html

    except Exception as e:
        return f'Error: {str(e)}'

@app.route('/queries')
def view_queries():
    """View DNS query logs"""
    try:
        html = '<h1>DNS Query Viewer</h1>'
        additional_params = request.args.get('query_params')
        if additional_params:
            html += '<h2>Query params</h2>'
            try:
                with open(additional_params, 'r') as f:
                    content = f.read()
                html += f'<h3>Saved DNS query: {additional_params}</h3><pre>{content}</pre><hr>'
            except Exception as e:
                pass
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT client_ip, query_name, query_type, response, timestamp FROM dns_queries ORDER BY timestamp DESC LIMIT 100')
        queries = cursor.fetchall()
        conn.close()

        html += '''
        <h2>Recent DNS Queries</h2>
        <table border="1" cellpadding="5" cellspacing="0">
            <tr><th>Client IP</th><th>Query</th><th>Type</th><th>Response</th><th>Timestamp</th></tr>
        '''

        for query in queries:
            html += f'<tr><td>{query[0]}</td><td>{query[1]}</td><td>{query[2]}</td><td>{query[3]}</td><td>{query[4]}</td></tr>'

        html += '</table>'

    except Exception as e:
        html += f'<p style="color: red;">Error loading DNS queries: {str(e)}</p>'

    html += '<br><a href="/">Back to Main</a>'

    return html

@app.route('/zone_transfer')
def zone_transfer():
    """Zone transfer functionality"""
    domain = request.args.get('domain', 'futurebank.local')

    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT name, type, value, ttl FROM dns_records WHERE name LIKE %s OR name = %s',
                      (f'%.{domain}', domain))
        records = cursor.fetchall()
        conn.close()

        html = f'''
        <h2>Zone Transfer for {domain}</h2>
        <p><strong>Warning:</strong> Zone transfers expose all DNS records for a domain!</p>
        <form method="GET">
            <input type="text" name="domain" value="{domain}" placeholder="Domain">
            <button type="submit">Transfer Zone</button>
        </form>
        <table>
            <tr><th>Name</th><th>Type</th><th>Value</th><th>TTL</th></tr>
        '''

        for record in records:
            html += f'<tr><td>{record[0]}</td><td>{record[1]}</td><td>{record[2]}</td><td>{record[3]}</td></tr>'

        html += '</table><br><a href="/">Back to Main</a>'
        return html

    except Exception as e:
        return f'Error: {str(e)}'

@app.route('/admin')
def admin_panel():
    """Admin panel"""
    password = request.args.get('password', '')

    if password != ADMIN_PASSWORD:
        return '''
        <h2>DNS Admin Panel</h2>
        <form method="GET">
            <input type="password" name="password" placeholder="Admin password" required>
            <button type="submit">Login</button>
        </form>
        '''

    return '''
    <h2>DNS Admin Panel - Authenticated</h2>
    <div style="border: 2px solid red; padding: 10px; margin: 10px; background: #ffe6e6;">
        <h3> Administrative Functions</h3>
        <p><strong>System Diagnostics:</strong></p>
        <form action="/admin/ping" method="POST">
            <input type="hidden" name="password" value="asdf">
            <input type="text" name="host" placeholder="Host to ping" value="localhost">
            <button type="submit">Ping Host</button>
        </form>

        <p><strong>DNS Flush Cache:</strong></p>
        <form action="/admin/flush" method="POST">
            <input type="hidden" name="password" value="asdf">
            <button type="submit">Flush DNS Cache</button>
        </form>

        <p><strong>Server Information:</strong></p>
        <form action="/admin/info" method="POST">
            <input type="hidden" name="password" value="asdf">
            <input type="text" name="command" placeholder="System command" value="uname -a">
            <input type="text" name="config" placeholder="Additional config (JSON)" value="">
            <button type="submit">Execute Command</button>
        </form>
    </div>
    <a href="/">Back to Main</a>
    '''

@app.route('/admin/ping', methods=['POST'])
def admin_ping():
    password = request.form.get('password', '')
    if password != ADMIN_PASSWORD:
        return 'Unauthorized'

    host = request.form.get('host', 'localhost')

    try:
        result = subprocess.check_output(f'ping -c 3 {host}', shell=True, text=True, timeout=10)
        return f'<pre>{result}</pre><br><a href="/admin?password={ADMIN_PASSWORD}">Back to Admin</a>'
    except Exception as e:
        return f'<pre>Error: {str(e)}</pre><br><a href="/admin?password={ADMIN_PASSWORD}">Back to Admin</a>'

@app.route('/admin/info', methods=['POST'])
def admin_info():
    """Basics infomation about system status"""
    password = request.form.get('password', '')
    if password != ADMIN_PASSWORD:
        return 'Unauthorized'

    command = request.form.get('command', 'uptime')
    config = request.form.get('config', '')

    if config:
        try:
            import pickle
            config_data = pickle.loads(config.encode())
            if isinstance(config_data, dict):
                for key, value in config_data.items():
                    if key == 'command':
                        command = value
                    elif key == 'timeout':
                        subprocess.check_output(command, shell=True, text=True, timeout=float(value))
                        return f'<pre>Command executed with timeout {value}s</pre><br><a href="/admin?password={ADMIN_PASSWORD}">Back to Admin</a>'
        except:
            pass

    try:
        result = subprocess.check_output(command, shell=True, text=True, timeout=10)
        return f'<pre>{result}</pre><br><a href="/admin?password={ADMIN_PASSWORD}">Back to Admin</a>'
    except Exception as e:
        return f'<pre>Error: {str(e)}</pre><br><a href="/admin?password={ADMIN_PASSWORD}">Back to Admin</a>'

def check_user_balance(username, password, required_amount):
    """Check if user has sufficient balance in payment-portal"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()


        cursor.execute('SELECT id, balance FROM portal_users WHERE username = %s AND password = %s',
                      (username, password))
        user_data = cursor.fetchone()

        if not user_data:
            conn.close()
            return False, "Invalid credentials"

        user_id, balance = user_data
        balance_decimal = Decimal(str(balance))
        required_decimal = Decimal(str(required_amount))

        if balance_decimal < required_decimal:
            conn.close()
            return False, f"Insufficient funds. Required: ${required_amount}, Available: ${float(balance_decimal)}"

        conn.close()
        return True, user_id

    except Exception as e:
        return False, f"Database error: {str(e)}"

def charge_user(user_id, amount, description):
    """Charge user for DNS record creation"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()


        cursor.execute('SELECT balance FROM portal_users WHERE id = %s', (user_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False, "User not found"

        current_balance = Decimal(str(result[0]))

        amount_decimal = Decimal(str(amount))
        new_balance = current_balance - amount_decimal


        cursor.execute('UPDATE portal_users SET balance = %s WHERE id = %s',
                      (new_balance, user_id))


        cursor.execute('''INSERT INTO portal_transactions
                         (user_id, amount, recipient, description, status)
                         VALUES (%s, %s, %s, %s, %s)''',
                      (user_id, -amount_decimal, 'DNS Service', description, 'completed'))

        conn.close()
        return True, float(new_balance)

    except Exception as e:
        return False, f"Payment error: {str(e)}"

@app.route('/add_record', methods=['POST'])
def add_record():
    """Add DNS record - requires payment"""
    try:
        name = request.form['name'].lower()
        record_type = request.form['type']
        value = request.form['value']
        ttl = int(request.form.get('ttl', 300))
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        record_prices = {
            'A': 10.00,
            'AAAA': 12.00,
            'CNAME': 8.00,
            'MX': 15.00,
            'TXT': 5.00,
            'NS': 20.00
        }

        required_amount = record_prices.get(record_type, 10.00)

        if not username or not password:
            return '''
            <div style="color: red; padding: 10px; border: 1px solid red;">
                <h3>Authentication Required</h3>
                <p>You must provide valid payment portal credentials to add DNS records.</p>
                <form method="POST">
                    <input type="hidden" name="name" value="{}">
                    <input type="hidden" name="type" value="{}">
                    <input type="hidden" name="value" value="{}">
                    <input type="hidden" name="ttl" value="{}">
                    <p><strong>Username:</strong> <input type="text" name="username" required></p>
                    <p><strong>Password:</strong> <input type="password" name="password" required></p>
                    <p><strong>Cost:</strong> ${:.2f}</p>
                    <button type="submit">Pay and Add Record</button>
                </form>
                <a href="/">Cancel</a>
            </div>
            '''.format(name, record_type, value, ttl, required_amount)

        balance_check, result = check_user_balance(username, password, required_amount)
        if not balance_check:
            return f'''
            <div style="color: red; padding: 10px; border: 1px solid red;">
                <h3>Payment Failed</h3>
                <p>{result}</p>
                <a href="/">Back to Main</a>
            </div>
            '''

        user_id = result

        payment_success, payment_result = charge_user(user_id, required_amount,
                                                    f"DNS Record Creation: {name} ({record_type})")
        if not payment_success:
            return f'''
            <div style="color: red; padding: 10px; border: 1px solid red;">
                <h3>Payment Processing Failed</h3>
                <p>{payment_result}</p>
                <a href="/">Back to Main</a>
            </div>
            '''


        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO dns_records (name, type, value, ttl) VALUES (%s, %s, %s, %s)',
                      (name, record_type, value, ttl))
        conn.close()

        return f'''
        <div style="color: green; padding: 10px; border: 1px solid green;">
            <h3>Record Added Successfully!</h3>
            <p><strong>Domain:</strong> {name}</p>
            <p><strong>Type:</strong> {record_type}</p>
            <p><strong>Value:</strong> {value}</p>
            <p><strong>TTL:</strong> {ttl}</p>
            <p><strong>Cost:</strong> ${required_amount:.2f}</p>
            <p><strong>New Balance:</strong> ${payment_result:.2f}</p>
        </div>
        <a href="/">Back to Main</a>
        '''

    except Exception as e:
        return f'Error: {str(e)}'

@app.route('/lookup')
def lookup():
    '''DNS lookup'''
    domain = request.args.get('domain', '')
    record_type = request.args.get('type', 'A')

    if not domain:
        return 'Domain required'

    record = dns_server_instance.resolve(domain, record_type, request.remote_addr)

    if record:
        return f'''
        <h2>DNS Lookup Result</h2>
        <p><strong>Domain:</strong> {domain}</p>
        <p><strong>Type:</strong> {record_type}</p>
        <p><strong>Value:</strong> {record.value}</p>
        <p><strong>TTL:</strong> {record.ttl}</p>
        <br><a href="/">Back to Main</a>
        '''
    else:
        return f'''
        <h2>DNS Lookup Result</h2>
        <p><strong>Domain:</strong> {domain}</p>
        <p><strong>Result:</strong> NXDOMAIN (Not Found)</p>
        <br><a href="/">Back to Main</a>
        '''

@app.route('/api/stats')
def api_stats():
    """API endpoint for statistics"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM dns_records')
        record_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM dns_queries')
        query_count = cursor.fetchone()[0]
        conn.close()

        return jsonify({
            'record_count': record_count,
            'query_count': query_count,
            'server_status': 'running'
        })

    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/check_balance', methods=['POST'])
def api_check_balance():
    """API endpoint to check user balance"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400

        username = data.get('username', '')
        password = data.get('password', '')

        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400

        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, balance FROM portal_users WHERE username = %s AND password = %s',
                      (username, password))
        user_data = cursor.fetchone()
        conn.close()

        if not user_data:
            return jsonify({'error': 'Invalid credentials'}), 401

        user_id, username, balance = user_data

        return jsonify({
            'user_id': user_id,
            'username': username,
            'balance': float(balance),
            'dns_pricing': {
                'A': 10.00,
                'AAAA': 12.00,
                'CNAME': 8.00,
                'MX': 15.00,
                'TXT': 5.00,
                'NS': 20.00
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/add_record', methods=['POST'])
def api_add_record():
    """API endpoint to add DNS record with payment"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON data required'}), 400

        name = data.get('name', '').lower()
        record_type = data.get('type', '')
        value = data.get('value', '')
        ttl = int(data.get('ttl', 300))
        username = data.get('username', '')
        password = data.get('password', '')

        if not all([name, record_type, value, username, password]):
            return jsonify({'error': 'All fields required: name, type, value, username, password'}), 400

        record_prices = {
            'A': 10.00,
            'AAAA': 12.00,
            'CNAME': 8.00,
            'MX': 15.00,
            'TXT': 5.00,
            'NS': 20.00
        }

        required_amount = record_prices.get(record_type, 10.00)

        balance_check, result = check_user_balance(username, password, required_amount)
        if not balance_check:
            return jsonify({'error': result}), 402

        user_id = result

        payment_success, payment_result = charge_user(user_id, required_amount,
                                                    f"DNS Record Creation: {name} ({record_type})")
        if not payment_success:
            return jsonify({'error': f'Payment failed: {payment_result}'}), 500

        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO dns_records (name, type, value, ttl) VALUES (%s, %s, %s, %s)',
                      (name, record_type, value, ttl))
        record_id = cursor.lastrowid
        conn.close()

        log(f'DNS record added: {name} ({record_type}) by user {username}, charged ${required_amount}')

        return jsonify({
            'message': 'DNS record added successfully',
            'record': {
                'id': record_id,
                'name': name,
                'type': record_type,
                'value': value,
                'ttl': ttl
            },
            'payment': {
                'amount_charged': required_amount,
                'new_balance': payment_result
            }
        }), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Start DNS server in a separate thread
    dns_thread = threading.Thread(target=start_dns_server)
    dns_thread.daemon = True
    dns_thread.start()

    # Wait for DNS server to initialize
    time.sleep(2)  # Give DNS server time to bind to port

    # Configure Flask for production
    app.config['JSON_SORT_KEYS'] = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False
    app.config['JSONIFY_MIMETYPE'] = 'application/json'

    # Run Flask with production settings
    app.run(
        host='0.0.0.0',
        port=MANAGEMENT_PORT,
        debug=False,
        threaded=True,
        use_reloader=False
    )