from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "message": "Tipstrr Analyzer работает!",
        "version": "1.0",
        "endpoints": {
            "/health": "Проверка работы",
            "/parse/<username>": "Парсинг каппера",
            "/api/tipsters": "Список капперов",
            "/api/bets/<username>": "Ставки каппера"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

@app.route('/parse/<username>')
def parse_tipster(username):
    try:
        # Временно заглушка
        return jsonify({
            "success": True,
            "message": f"Парсинг {username} - функция временно отключена",
            "tip": "Добавь импорт парсера когда БД заработает"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/tipsters')
def get_tipsters():
    return jsonify([])

@app.route('/api/bets/<username>')
def get_bets(username):
    return jsonify({"username": username, "bets": []})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
