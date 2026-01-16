from flask import Flask, render_template, jsonify
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html', message="Анализатор Tipstrr запущен!")

@app.route('/api/status')
def status():
    return jsonify({
        "status": "online",
        "message": "Сервер работает"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
