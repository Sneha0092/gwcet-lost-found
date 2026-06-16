from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3, json, urllib.request, os

app = Flask(__name__, static_folder='public')
CORS(app)
import os as _os; DB = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'db', 'lostfound.db')

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS lost_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT,
            roll_number TEXT,
            item_type TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            lost_time TEXT,
            contact_email TEXT,
            contact_phone TEXT,
            status TEXT DEFAULT "open",
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS found_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            found_time TEXT,
            reported_by TEXT DEFAULT "College Staff",
            storage_location TEXT,
            status TEXT DEFAULT "available",
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lost_id INTEGER,
            found_id INTEGER,
            score INTEGER,
            reasons TEXT,
            status TEXT DEFAULT "pending",
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(lost_id) REFERENCES lost_reports(id),
            FOREIGN KEY(found_id) REFERENCES found_items(id)
        );
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            lost_id INTEGER,
            found_id INTEGER,
            contact_email TEXT,
            status TEXT DEFAULT "submitted",
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    count = conn.execute('SELECT COUNT(*) FROM found_items').fetchone()[0]
    if count == 0:
        seeds = [
            ('bag', 'Black Wildcraft backpack with red zipper, water bottle side pocket, laptop compartment', 'CSE Department Lab 3', '2024-01-15 11:30', 'Lab Assistant', 'Admin Office'),
            ('electronics', 'Samsung Galaxy S23, black colour, cracked screen protector, college ID sticker on back', 'College Canteen', '2024-01-15 13:10', 'Canteen Staff', 'Admin Office'),
            ('stationery', 'Scientific calculator Casio FX-991ES Plus, black cover with name label scratched off', 'Exam Hall B', '2024-01-15 10:00', 'Invigilator', 'HOD Office'),
            ('id_card', 'College ID card — name partially visible, CSE department, 2022 batch', 'Library Reading Room', '2024-01-15 09:45', 'Library Staff', 'Admin Office'),
            ('electronics', 'boAt Airdopes earbuds, white, with charging case, found near power socket', 'Seminar Hall 1', '2024-01-14 15:20', 'Peon', 'Admin Office'),
            ('keys', 'Bike keys with Hero keychain, 2 keys on ring, small torch attached', 'Parking Lot B', '2024-01-15 08:55', 'Security Guard', 'Security Cabin'),
            ('wallet', 'Brown leather wallet, some cash and ATM cards inside', 'Boys Hostel Common Room', '2024-01-15 20:10', 'Hostel Warden', 'Hostel Office'),
            ('clothing', 'Black Nike jacket, size M, left on bench', 'Sports Ground', '2024-01-15 17:30', 'PT Teacher', 'Sports Room'),
        ]
        conn.executemany(
            'INSERT INTO found_items (item_type, description, location, found_time, reported_by, storage_location) VALUES (?,?,?,?,?,?)',
            seeds
        )
        conn.commit()
    conn.close()

def call_gemini(prompt):
    api_key = os.environ.get('GEMINI_API_KEY', '')
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}'
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1000}
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    return data['candidates'][0]['content']['parts'][0]['text']

def ai_match(lost, found_items):
    items_text = '\n'.join([
        f"ID {f['id']}: [{f['item_type']}] {f['description']} — found at {f['location']}"
        for f in found_items
    ])
    prompt = f"""You are an AI for a Lost & Found portal at a college campus. A student lost an item. Match it against found items.

LOST ITEM:
Type: {lost['item_type']}
Description: {lost['description']}
Location lost: {lost['location']}
Time lost: {lost['lost_time'] or 'unknown'}

FOUND ITEMS:
{items_text}

For each found item, give a match score 0-100 and 2-4 short reasons why it matches or not.
Return ONLY valid JSON array, no markdown:
[{{"found_id": <id>, "score": <0-100>, "reasons": ["reason1", "reason2", ...]}}]
Only include items with score > 25. Sort by score descending."""
    try:
        text = call_gemini(prompt).strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        print(f"AI error: {e}")
        return []

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/api/report-lost', methods=['POST'])
def report_lost():
    data = request.json
    if not all(data.get(f) for f in ['item_type', 'description', 'location']):
        return jsonify({'error': 'item_type, description, location are required'}), 400
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO lost_reports (student_name, roll_number, item_type, description, location, lost_time, contact_email, contact_phone) VALUES (?,?,?,?,?,?,?,?)',
        (data.get('student_name'), data.get('roll_number'), data['item_type'],
         data['description'], data['location'], data.get('lost_time'),
         data.get('contact_email'), data.get('contact_phone'))
    )
    lost_id = cur.lastrowid
    conn.commit()
    found_rows = conn.execute('SELECT * FROM found_items WHERE status="available"').fetchall()
    found_items = [dict(r) for r in found_rows]
    conn.close()
    matches = ai_match(data, found_items) if found_items else []
    if matches:
        conn = get_db()
        for m in matches:
            conn.execute(
                'INSERT OR REPLACE INTO matches (lost_id, found_id, score, reasons) VALUES (?,?,?,?)',
                (lost_id, m['found_id'], m['score'], json.dumps(m['reasons']))
            )
        conn.commit()
        conn.close()
    return jsonify({'lost_id': lost_id, 'matches': matches}), 201

@app.route('/api/found-items', methods=['GET'])
def get_found_items():
    category = request.args.get('category')
    conn = get_db()
    if category and category != 'all':
        rows = conn.execute('SELECT * FROM found_items WHERE item_type=? AND status="available" ORDER BY created_at DESC', (category,)).fetchall()
    else:
        rows = conn.execute('SELECT * FROM found_items WHERE status="available" ORDER BY created_at DESC').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/matches/<int:lost_id>', methods=['GET'])
def get_matches(lost_id):
    conn = get_db()
    rows = conn.execute('''
        SELECT m.id, m.score, m.reasons, m.status,
               f.id as found_id, f.item_type, f.description as found_desc,
               f.location as found_location, f.found_time, f.storage_location,
               l.description as lost_desc, l.location as lost_location
        FROM matches m
        JOIN found_items f ON m.found_id = f.id
        JOIN lost_reports l ON m.lost_id = l.id
        WHERE m.lost_id = ? ORDER BY m.score DESC
    ''', (lost_id,)).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['reasons'] = json.loads(d['reasons'])
        result.append(d)
    return jsonify(result)

@app.route('/api/log-found', methods=['POST'])
def log_found():
    data = request.json
    if not all(data.get(f) for f in ['item_type', 'description', 'location']):
        return jsonify({'error': 'item_type, description, location required'}), 400
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO found_items (item_type, description, location, found_time, reported_by, storage_location) VALUES (?,?,?,?,?,?)',
        (data['item_type'], data['description'], data['location'],
         data.get('found_time'), data.get('reported_by', 'College Staff'),
         data.get('storage_location', 'Admin Office'))
    )
    conn.commit()
    conn.close()
    return jsonify({'found_id': cur.lastrowid, 'message': 'Found item logged'}), 201

@app.route('/api/claim', methods=['POST'])
def submit_claim():
    data = request.json
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO claims (match_id, lost_id, found_id, contact_email) VALUES (?,?,?,?)',
        (data.get('match_id'), data.get('lost_id'), data.get('found_id'), data.get('contact_email'))
    )
    conn.execute('UPDATE found_items SET status="claimed" WHERE id=?', (data.get('found_id'),))
    conn.commit()
    conn.close()
    return jsonify({'claim_id': cur.lastrowid, 'message': 'Claim submitted. Visit Admin Office with your college ID.'}), 201

@app.route('/api/stats', methods=['GET'])
def stats():
    conn = get_db()
    total_lost = conn.execute('SELECT COUNT(*) FROM lost_reports').fetchone()[0]
    total_found = conn.execute('SELECT COUNT(*) FROM found_items').fetchone()[0]
    total_matched = conn.execute('SELECT COUNT(*) FROM matches WHERE score >= 70').fetchone()[0]
    total_claimed = conn.execute('SELECT COUNT(*) FROM claims').fetchone()[0]
    conn.close()
    return jsonify({'total_lost': total_lost, 'total_found': total_found,
                    'total_matched': total_matched, 'total_claimed': total_claimed})

if __name__ == '__main__':
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    init_db()
    print("Server running on http://localhost:5050")
    app.run(host='0.0.0.0', port=5050, debug=False)