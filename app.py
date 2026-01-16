from flask import Flask, jsonify
import os
import sys

# Пробуем импортировать БД
try:
    from database import engine, SessionLocal
    from models import Base
    Base.metadata.create_all(bind=engine)
    DB_AVAILABLE = True
except Exception as e:
    print(f"БД не доступна: {e}")
    DB_AVAILABLE = False

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "message": "Tipstrr Analyzer работает!",
        "database": "available" if DB_AVAILABLE else "not_available",
        "version": "1.1",
        "endpoints": {
            "/health": "Проверка работы",
            "/status": "Детальный статус",
            "/parse/<username>": "Парсинг каппера",
            "/api/tipsters": "Список капперов",
            "/api/bets/<username>": "Ставки каппера"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/status')
def status():
    return jsonify({
        "python_version": sys.version,
        "database": DB_AVAILABLE,
        "environment_variables": {
            "TIPSTRR_USERNAME": bool(os.environ.get("TIPSTRR_USERNAME")),
            "DATABASE_URL": bool(os.environ.get("DATABASE_URL"))
        }
    })

# Остальные эндпоинты пока оставляем как заглушки
@app.route('/parse/<username>')
def parse_tipster(username):
    return jsonify({
        "success": True,
        "message": "Парсер готов к работе",
        "next_step": "Добавить логику парсера"
    })

@app.route('/api/tipsters')
def get_tipsters():
    if not DB_AVAILABLE:
        return jsonify({"error": "Database not available", "tipsters": []})
    
    try:
        db = SessionLocal()
        from models import Tipster
        tipsters = db.query(Tipster).all()
        result = [{"username": t.username, "name": t.name} for t in tipsters]
        db.close()
        return jsonify({"tipsters": result})
    except Exception as e:
        return jsonify({"error": str(e), "tipsters": []})

@app.route('/api/bets/<username>')
def get_bets(username):
    return jsonify({"username": username, "bets": [], "message": "В разработке"})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
