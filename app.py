from flask import Flask, jsonify
import os
import sys

app = Flask(__name__)

# Проверяем БД
DB_AVAILABLE = False
DB_ERROR = ""

try:
    # Пробуем подключиться к БД
    import psycopg2
    DATABASE_URL = os.environ.get('DATABASE_URL', '')
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    if DATABASE_URL:
        # Простая проверка подключения
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        conn.close()
        DB_AVAILABLE = True
    else:
        DB_ERROR = "DATABASE_URL not set"
except Exception as e:
    DB_ERROR = str(e)
    DB_AVAILABLE = False

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "message": "Tipstrr Analyzer работает!",
        "database": "available" if DB_AVAILABLE else f"not_available: {DB_ERROR}",
        "version": "1.2",
        "endpoints": {
            "/health": "Проверка работы",
            "/status": "Детальный статус",
            "/test-db": "Тест БД",
            "/parse/<username>": "Парсинг каппера"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/status')
def status():
    return jsonify({
        "python_version": sys.version,
        "database_available": DB_AVAILABLE,
        "database_error": DB_ERROR if not DB_AVAILABLE else None,
        "environment_variables": {
            "TIPSTRR_USERNAME": bool(os.environ.get("TIPSTRR_USERNAME")),
            "DATABASE_URL": bool(os.environ.get("DATABASE_URL"))
        }
    })

@app.route('/test-db')
def test_db():
    try:
        import psycopg2
        DATABASE_URL = os.environ.get('DATABASE_URL', '')
        if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "database": "connected",
            "postgres_version": db_version[0]
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })

@app.route('/parse/<username>')
def parse_tipster(username):
    # Простой парсер без БД
    try:
        import requests
        
        return jsonify({
            "success": True,
            "message": f"Парсер для {username} готов",
            "next": "Добавить логику когда БД заработает"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
