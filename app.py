from flask import Flask, render_template, jsonify, request
from parser import parse_single_tipster
from models import Tipster, Bet
from database import SessionLocal, engine
from sqlalchemy.orm import Session
import os

# Создаем таблицы в БД
from models import Base
Base.metadata.create_all(bind=engine)

app = Flask(__name__)

@app.route('/')
def index():
    db = SessionLocal()
    try:
        tipsters = db.query(Tipster).all()
        stats = []
        for tipster in tipsters:
            bet_count = db.query(Bet).filter(Bet.tipster_id == tipster.id).count()
            stats.append({
                'name': tipster.name,
                'username': tipster.username,
                'bet_count': bet_count,
                'last_updated': tipster.created_at
            })
        return render_template('index.html', 
                             message="Анализатор Tipstrr запущен!",
                             stats=stats)
    finally:
        db.close()

@app.route('/parse/<username>')
def parse_tipster(username):
    max_tips = request.args.get('max', default=50, type=int)
    
    result = parse_single_tipster(username, max_tips)
    
    if result:
        return jsonify({
            "success": True,
            "message": f"Парсинг завершен для {username}",
            "data": result
        })
    else:
        return jsonify({
            "success": False,
            "message": "Ошибка при парсинге"
        }), 500

@app.route('/api/tipsters')
def get_tipsters():
    db = SessionLocal()
    try:
        tipsters = db.query(Tipster).all()
        return jsonify([{
            'id': t.id,
            'username': t.username,
            'name': t.name,
            'bet_count': db.query(Bet).filter(Bet.tipster_id == t.id).count()
        } for t in tipsters])
    finally:
        db.close()

@app.route('/api/bets/<username>')
def get_bets(username):
    db = SessionLocal()
    try:
        tipster = db.query(Tipster).filter(Tipster.username == username).first()
        if not tipster:
            return jsonify({"error": "Tipster not found"}), 404
        
        bets = db.query(Bet).filter(Bet.tipster_id == tipster.id).order_by(Bet.event_date.desc()).limit(100).all()
        
        return jsonify([{
            'id': b.id,
            'match': b.match,
            'bet': b.bet,
            'odds': b.odds,
            'result': b.result,
            'profit': b.profit,
            'date': b.event_date.isoformat() if b.event_date else None
        } for b in bets])
    finally:
        db.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
