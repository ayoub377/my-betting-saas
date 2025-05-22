from pydantic import BaseModel
from typing import List, Optional


class Outcome(BaseModel):
    name: str
    price: float


class H2HMarket(BaseModel):
    outcomes: List[Outcome]


class Bookmaker(BaseModel):
    name: str  # Bookmaker name (e.g., "pinnacle")
    markets: List[H2HMarket]  # List of markets like h2h, spreads, etc.


class MatchData(BaseModel):
    home_team: str
    away_team: str
    commence_time: str
    bookmakers: Optional[List[Bookmaker]] = None  # Include bookmakers
