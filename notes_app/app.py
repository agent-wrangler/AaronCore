from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'notes.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT,
            category TEXT DEFAULT 'general',
            tags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # 创建全文搜索虚拟表
    try:
        c.execute('CREATE VIRTUAL TABLE notes_fts USING fts5(title, content, tags, content=notes, content_rowid=id)')
    except:
        pass
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/notes', methods=['GET'])
def get_notes():
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if search:
        if category:
            c.execute('''
                SELECT * FROM notes 
                WHERE (title LIKE ? OR content LIKE ? OR tags LIKE ?) AND category = ?
                ORDER BY updated_at DESC
            ''', (f'%{search}%', f'%{search}%', f'%{search}%', category))
        else:
            c.execute('''
                SELECT * FROM notes 
                WHERE title LIKE ? OR content LIKE ? OR tags LIKE ?
                ORDER BY updated_at DESC
            ''', (f'%{search}%', f'%{search}%', f'%{search}%'))
    elif category:
        c.execute('SELECT * FROM notes WHERE category = ? ORDER BY updated_at DESC', (category,))
    else:
        c.execute('SELECT * FROM notes ORDER BY updated_at DESC')
    
    notes = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(notes)

@app.route('/api/notes', methods=['POST'])
def create_note():
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO notes (title, content, category, tags)
        VALUES (?, ?, ?, ?)
    ''', (data.get('title', ''), data.get('content', ''), 
          data.get('category', 'general'), data.get('tags', '')))
    note_id = c.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'id': note_id, 'message': 'created'})

@app.route('/api/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE notes 
        SET title = ?, content = ?, category = ?, tags = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (data.get('title', ''), data.get('content', ''),
          data.get('category', 'general'), data.get('tags', ''), note_id))
    conn.commit()
    conn.close()
    return jsonify({'message': 'updated'})

@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'deleted'})

if __name__ == '__main__':
    print('🚀 Nova 开发者笔记启动！')
    print('📝 访问 http://localhost:5005')
    app.run(debug=True, port=5005)
