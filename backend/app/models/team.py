from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Team(Base):
    __tablename__ = 'teams'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    total_value = Column(Float)
    stadium_seats = Column(Integer)
    average_attendance = Column(Integer)
    coach_name = Column(String)
    assigned_date = Column(Date)
    end_contract = Column(Date)

    # Relationship to access Players data from Team
    players = relationship("Player", back_populates="team")


# Players Table
class Player(Base):
    __tablename__ = 'players'

    PlayerId = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    position = Column(String)
    marketvalue = Column(Float)
    age = Column(Integer)
    teamid = Column(Integer, ForeignKey('teams.id'))  # Define foreign key referencing Team table
    status = Column(String,nullable=True)
    # Relationship to access Team data from Player
    team = relationship("Team", back_populates="players")

