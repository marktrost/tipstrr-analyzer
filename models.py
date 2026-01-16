from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Tipster(Base):
    __tablename__ = "tipsters"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    name = Column(String)
    sport = Column(String)
    is_paid = Column(Boolean, default=False)
    profile_url = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Связь со ставками
    bets = relationship("Bet", back_populates="tipster")

class Bet(Base):
    __tablename__ = "bets"
    
    id = Column(Integer, primary_key=True, index=True)
    tipster_id = Column(Integer, ForeignKey("tipsters.id"))
    reference = Column(String, unique=True, index=True)
    event_date = Column(DateTime)
    home_team = Column(String)
    away_team = Column(String)
    match = Column(String)
    sport = Column(String)
    league = Column(String)
    market = Column(String)
    bet = Column(String)
    odds = Column(Float)
    result = Column(String)  # Win/Loss/Void
    profit = Column(Float)
    raw_result_code = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Связь с каппером
    tipster = relationship("Tipster", back_populates="bets")
