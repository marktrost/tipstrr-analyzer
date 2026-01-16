import requests
import pandas as pd
from datetime import datetime
import time
import os
import json
from sqlalchemy.orm import Session
from models import Tipster, Bet
from database import SessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# КОНФИГУРАЦИЯ (вынести в config.py или переменные окружения)
LOGIN_URL = os.environ.get("LOGIN_URL", "https://www.tipstrr.com/login")
API_LIST_URL_TEMPLATE = "https://tipstrr.com/api/portfolio/{username}/tips/completed"
API_TIP_URL_TEMPLATE = "https://tipstrr.com/api/portfolio/{username}/tips/cached"
API_FIXTURE_URL = "https://tipstrr.com/api/fixture"

class TipstrrParser:
    def __init__(self):
        self.session = None
        self.username = os.environ.get("TIPSTRR_USERNAME")
        self.password = os.environ.get("TIPSTRR_PASSWORD")
        
        if not self.username or not self.password:
            logger.error("Не указаны учетные данные в переменных окружения!")
            raise ValueError("Укажите TIPSTRR_USERNAME и TIPSTRR_PASSWORD")
    
    def create_session(self):
        """Создает сессию с авторизацией"""
        self.session = requests.Session()
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        
        # Получаем начальные куки
        self.session.get("https://www.tipstrr.com")
        
        # Логинимся
        login_data = {
            "username": self.username,
            "password": self.password
        }
        
        login_headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://www.tipstrr.com',
            'Referer': 'https://www.tipstrr.com/login',
        }
        
        response = self.session.post(LOGIN_URL, data=login_data, headers=login_headers)
        
        if response.status_code != 200:
            logger.error(f"Ошибка авторизации: {response.status_code}")
            return False
        
        logger.info("Авторизация успешна")
        return True
    
    def parse_tipster(self, username, max_tips=None):
        """Парсит данные конкретного каппера"""
        if not self.session:
            if not self.create_session():
                return None
        
        db = SessionLocal()
        try:
            # Проверяем, есть ли каппер в БД
            tipster = db.query(Tipster).filter(Tipster.username == username).first()
            if not tipster:
                tipster = Tipster(
                    username=username,
                    name=username,
                    profile_url=f"https://tipstrr.com/tipster/{username}"
                )
                db.add(tipster)
                db.commit()
                db.refresh(tipster)
            
            # Получаем список прогнозов
            logger.info(f"Загружаю прогнозы для {username}...")
            api_url = API_LIST_URL_TEMPLATE.format(username=username)
            
            all_tips = []
            skip = 0
            
            while True:
                response = self.session.get(api_url, params={'skip': skip})
                
                if response.status_code != 200:
                    logger.error(f"Ошибка API: {response.status_code}")
                    break
                
                batch = response.json()
                if not batch:
                    break
                
                all_tips.extend(batch)
                
                # Если указано ограничение
                if max_tips and len(all_tips) >= max_tips:
                    all_tips = all_tips[:max_tips]
                    break
                
                # Если пришло меньше 10 - последняя страница
                if len(batch) < 10:
                    break
                
                skip += 10
                time.sleep(0.1)
            
            logger.info(f"Найдено {len(all_tips)} прогнозов")
            
            # Обрабатываем каждый прогноз
            new_bets = 0
            for tip in all_tips:
                reference = tip.get('reference')
                
                # Проверяем, есть ли уже в БД
                existing = db.query(Bet).filter(Bet.reference == reference).first()
                if existing:
                    continue
                
                # Парсим детали
                bet_data = self._parse_tip_details(reference)
                if bet_data:
                    # Преобразуем дату
                    try:
                        event_date = datetime.strptime(bet_data['event_date'], '%Y-%m-%d')
                    except:
                        event_date = None
                    
                    # Создаем запись ставки
                    bet = Bet(
                        tipster_id=tipster.id,
                        reference=reference,
                        event_date=event_date,
                        home_team=bet_data.get('home_team', ''),
                        away_team=bet_data.get('away_team', ''),
                        match=bet_data.get('match', ''),
                        sport=bet_data.get('sport', ''),
                        league=bet_data.get('league', ''),
                        market=bet_data.get('market', ''),
                        bet=bet_data.get('bet', ''),
                        odds=float(bet_data.get('odds', 0)) if bet_data.get('odds') else None,
                        result=bet_data.get('result', ''),
                        profit=float(bet_data.get('profit', 0)) if bet_data.get('profit') else 0,
                        raw_result_code=int(bet_data.get('raw_result_code', 0))
                    )
                    
                    db.add(bet)
                    new_bets += 1
            
            db.commit()
            logger.info(f"Добавлено {new_bets} новых ставок для {username}")
            
            return {
                "tipster": tipster.username,
                "total_bets": len(all_tips),
                "new_bets": new_bets
            }
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге: {e}")
            db.rollback()
            return None
        finally:
            db.close()
    
    def _parse_tip_details(self, reference):
        """Внутренний метод парсинга деталей ставки"""
        # ... (используй твой существующий код из parse_tip_details и extract_tip_data)
        # Вернуть словарь с данными или None
        pass

def parse_single_tipster(username="freguli", max_tips=50):
    """Функция для быстрого теста"""
    parser = TipstrrParser()
    return parser.parse_tipster(username, max_tips)

if __name__ == "__main__":
    # Тестовый запуск
    result = parse_single_tipster("freguli", 10)
    print(result)
