import requests
import polars as pl  # ← ИМЕННО ЭТО ИЗМЕНЕНИЕ
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
            
            # СОЗДАЕМ POLARS DATAFRAME ДЛЯ АНАЛИЗА (опционально)
            if all_tips:
                df = pl.DataFrame(all_tips)
                logger.info(f"Создан Polars DataFrame: {df.shape}")
            
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
            
            # ДОПОЛНИТЕЛЬНО: СОХРАНИМ В EXCEL ДЛЯ АНАЛИЗА (если нужно)
            self._save_to_excel(all_tips, username)
            
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
        try:
            # 1. Получаем детали прогноза (ставки)
            tip_url = f"https://tipstrr.com/api/portfolio/{self.username}/tips/cached/{reference}"
            response_tip = self.session.get(tip_url)

            if response_tip.status_code != 200:
                logger.error(f"Ошибка при запросе прогноза {reference}: {response_tip.status_code}")
                return None

            tip_data = response_tip.json()

            # 2. Получаем детали матча (фикстуры)
            fixture_data = None
            fixture_reference = None
            
            if tip_data.get('tipBetItem') and len(tip_data['tipBetItem']) > 0:
                fixture_reference = tip_data['tipBetItem'][0].get('fixtureReference')
            
            if fixture_reference:
                fixture_url = f"{API_FIXTURE_URL}/{fixture_reference}"
                response_fixture = self.session.get(fixture_url)

                if response_fixture.status_code == 200:
                    fixture_data = response_fixture.json()

            # Извлекаем данные
            title = tip_data.get('title', '')
            tip_date = tip_data.get('tipDate', '')
            result = tip_data.get('result', '')
            profit = tip_data.get('profit', '')

            # Обработка даты
            event_date = ''
            event_time = ''
            if tip_date:
                try:
                    dt = datetime.fromisoformat(tip_date.replace('Z', '+00:00'))
                    event_date = dt.strftime('%Y-%m-%d')
                    event_time = dt.strftime('%H:%M')
                except:
                    event_date = tip_date[:10] if len(tip_date) >= 10 else tip_date
                    event_time = ''

            # Данные о ставке
            odds = None
            market_text = ''
            bet_text = ''

            if tip_data.get('tipBet') and len(tip_data['tipBet']) > 0:
                odds = tip_data['tipBet'][0].get('odds', '')

            if tip_data.get('tipBetItem') and len(tip_data['tipBetItem']) > 0:
                market_text = tip_data['tipBetItem'][0].get('marketText', '')
                bet_text = tip_data['tipBetItem'][0].get('betText', '')

            # Данные о матче из фикстуры (если есть)
            home_team = ''
            away_team = ''
            sport = ''
            league = ''

            if fixture_data:
                home_team = fixture_data.get('homeTeam', {}).get('name', '')
                away_team = fixture_data.get('awayTeam', {}).get('name', '')
                sport = fixture_data.get('sport', {}).get('name', '')
                league = fixture_data.get('competition', {}).get('name', '')

            # Если нет данных из фикстуры, пробуем извлечь из title
            if not home_team and ' v ' in title:
                parts = title.split(' v ')
                if len(parts) == 2:
                    home_team = parts[0].strip()
                    away_team = parts[1].strip()

            # Расшифровка результата
            result_map = {1: 'Win', 2: 'Loss', 3: 'Void'}
            result_text = result_map.get(result, f'Unknown ({result})')

            return {
                'event_date': event_date,
                'event_time': event_time,
                'home_team': home_team,
                'away_team': away_team,
                'match': f"{home_team} vs {away_team}" if home_team and away_team else title,
                'sport': sport,
                'league': league,
                'market': market_text,
                'bet': bet_text,
                'odds': odds,
                'result': result_text,
                'profit': profit,
                'raw_result_code': result,
                'reference': reference
            }
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге деталей {reference}: {e}")
            return None
    
    def _save_to_excel(self, data, username):
        """Сохранение данных в Excel через polars"""
        if not data:
            return
        
        try:
            # Создаем DataFrame из данных
            df = pl.DataFrame(data)
            
            # Добавляем информацию о каппере
            df = df.with_columns([
                pl.lit(username).alias('tipster'),
                pl.lit(datetime.now().strftime('%Y-%m-%d %H:%M:%S')).alias('parsed_at')
            ])
            
            # Сохраняем в Excel
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{username}_bets_{timestamp}.xlsx"
            
            df.write_excel(
                workbook=filename,
                worksheet="bets",
                autofit=True,
                has_header=True
            )
            
            logger.info(f"Данные сохранены в Excel: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении в Excel: {e}")
            # Если не получилось в Excel, сохраняем в JSON
            return self._save_to_json(data, username)
    
    def _save_to_json(self, data, username):
        """Резервное сохранение в JSON"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{username}_bets_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Данные сохранены в JSON: {filename}")
        return filename


def parse_single_tipster(username="freguli", max_tips=50):
    """Функция для быстрого теста"""
    parser = TipstrrParser()
    return parser.parse_tipster(username, max_tips)


def main():
    """Функция для локального тестирования (как в твоем оригинальном коде)"""
    print("=== Парсер Tipstrr.com (Polars версия) ===")
    print("=" * 30)
    
    # Запрашиваем количество прогнозов
    while True:
        try:
            user_input = input(
                "\nСколько прогнозов парсить? (Enter = ВСЕ доступные, число = конкретное количество): ").strip()

            if user_input == "":
                max_tips = None  # ВСЕ доступные
                print("Будут загружены ВСЕ доступные прогнозы (пока не закончатся)")
                break
            else:
                max_tips = int(user_input)
                if max_tips > 0:
                    print(f"Будут загружены {max_tips} прогнозов")
                    break
                else:
                    print("Введите положительное число или Enter для ВСЕХ прогнозов")
        except ValueError:
            print("Пожалуйста, введите число или нажмите Enter для ВСЕХ прогнозов")
    
    # Запускаем парсер
    parser = TipstrrParser()
    result = parser.parse_tipster(parser.username, max_tips)
    
    if result:
        print(f"\n✓ Парсинг завершен!")
        print(f"Каппер: {result['tipster']}")
        print(f"Всего ставок: {result['total_bets']}")
        print(f"Новых добавлено: {result['new_bets']}")
    else:
        print("\n✗ Ошибка при парсинге")


if __name__ == "__main__":
    main()
