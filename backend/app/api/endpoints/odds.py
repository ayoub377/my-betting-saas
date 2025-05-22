import asyncio
import os
from typing import List, Optional

import shin
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
import requests
from datetime import datetime, timedelta

from app.core.auth import has_access
from app.core.config import redis_client, rate_limit_dependency
from app.models.odds import MatchData, Outcome, H2HMarket, Bookmaker
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()
league = ''
API_KEY = os.getenv("ODDS_API_KEY")

# Cache expiry time in seconds (30 minutes)
CACHE_EXPIRY = 30 * 60


# Fetch data from API
async def fetch_api_data(name):
    cache_key = f"odds_api:{name}"
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        # If cached data exists, return it
        return json.loads(cached_data)

    url = f"https://api.the-odds-api.com/v4/sports/{name}/odds?apiKey={API_KEY}&regions=eu&markets=h2h,spreads&oddsFormat=decimal"
    response = requests.get(url)
    data = response.json()
    if response.status_code == 200:
        # Store the data in the cache with an expiry time
        await redis_client.setex(cache_key, CACHE_EXPIRY, json.dumps(data))

        return data  # Parse JSON response and return list of matches
    else:
        raise HTTPException(status_code=500, detail="Failed to fetch data from the Odds API.")


# extract h2h data
# def extract_bookmaker_data(matches: List[dict], selected_bookmakers=None) -> List[MatchData]:
#     if selected_bookmakers is None:
#         selected_bookmakers = ["pinnacle"]
#     elif "pinnacle" not in selected_bookmakers:
#         selected_bookmakers.append("pinnacle")  # Ensure Pinnacle is included
#
#     match_data_list = []
#
#     for match in matches:
#         if "home_team" not in match or "away_team" not in match or "commence_time" not in match:
#             continue
#
#         bookmakers = []
#
#         for bookmaker in match.get("bookmakers", []):
#             if bookmaker["key"] in selected_bookmakers:
#                 h2h_markets = [
#                     H2HMarket(
#                         key=market["key"],
#                         outcomes=[
#                             Outcome(name=outcome["name"], price=outcome["price"])
#                             for outcome in market.get("outcomes", [])
#                         ],
#                     )
#                     for market in bookmaker.get("markets", [])
#                     if market["key"] == "h2h"
#                 ]
#
#                 if h2h_markets:
#                     bookmakers.append(Bookmaker(name=bookmaker["key"], markets=h2h_markets))
#
#         if bookmakers:
#             match_data_list.append(
#                 MatchData(
#                     home_team=match["home_team"],
#                     away_team=match["away_team"],
#                     commence_time=match["commence_time"],
#                     bookmakers=bookmakers,
#                 )
#             )
#
#     return match_data_list

# Filter matches by start time

def extract_bookmaker_data(matches: List[dict], selected_bookmakers: Optional[List[str]] = None) -> List[MatchData]:
    # Normalize bookmaker names (case insensitive) and ensure Pinnacle is included
    selected_bookmakers = set(bookmaker.lower() for bookmaker in (selected_bookmakers or ["Pinnacle"]))
    selected_bookmakers.add("pinnacle")  # Always ensure Pinnacle is included
    match_data_list = []

    for match in matches:
        # Ensure required match fields exist
        if not all(key in match for key in ["home_team", "away_team", "commence_time"]):
            continue

        bookmakers = []

        for bookmaker in match.get("bookmakers", []):
            if bookmaker["title"].lower() in selected_bookmakers:  # Match bookmaker keys (case insensitive)
                h2h_markets = [
                    H2HMarket(
                        key=market["key"],
                        outcomes=[
                            Outcome(name=outcome["name"], price=outcome["price"])
                            for outcome in market.get("outcomes", [])
                        ],
                    )
                    for market in bookmaker.get("markets", [])
                    if market["key"] == "h2h"
                ]

                if h2h_markets:
                    bookmakers.append(Bookmaker(name=bookmaker["key"], markets=h2h_markets))

        if bookmakers:
            match_data_list.append(
                MatchData(
                    home_team=match["home_team"],
                    away_team=match["away_team"],
                    commence_time=match["commence_time"],
                    bookmakers=bookmakers,
                )
            )

    return match_data_list


def filter_matches_by_hour(matches):
    current_time = datetime.utcnow() + timedelta(hours=1)  # UTC+1 time
    cutoff_time = current_time + timedelta(hours=1)

    filtered_matches = [
        match for match in matches if datetime.fromisoformat(match["commence_time"][:-1]) <= cutoff_time
    ]
    return filtered_matches


def filter_matches_by_day(matches):
    current_time = datetime.utcnow() + timedelta(hours=1)  # UTC+1 time
    start_of_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    filtered_matches = [
        match for match in matches if start_of_day <= datetime.fromisoformat(match["commence_time"][:-1]) < end_of_day
    ]
    return filtered_matches


# Store data
def store_data(bookmaker_data):
    with open("odds_data.json", "w") as file:
        json.dump(bookmaker_data, file, indent=4)


# calculate no vig pinnacle odds
import json


def remove_vig(bookmaker_data):
    bookmaker_data = [json.loads(match) for match in bookmaker_data]

    for match in bookmaker_data:
        pinnacle_markets = next(
            (bookmaker["markets"] for bookmaker in match["bookmakers"] if bookmaker["name"] == "pinnacle"),
            None
        )

        if pinnacle_markets:
            for market in pinnacle_markets:
                if market.get("outcomes"):
                    outcomes = market["outcomes"]

                    odds = [outcome["price"] for outcome in outcomes]
                    implied_probs = shin.calculate_implied_probabilities(odds)

                    for outcome, prob in zip(outcomes, implied_probs):
                        outcome["no_vig_price"] = round(1 / prob, 2)

    return bookmaker_data

# calculate EV
def calculate_ev(odds: float, fair_odds: float) -> float:
    if fair_odds <= 0:
        return 0
    implied_prob = 1 / fair_odds
    stake = 100  # Assume a default stake for EV calculation
    payout = stake * odds
    ev = (implied_prob * payout) - ((1 - implied_prob) * stake)
    return ev

# Main function
async def main(name, all_matches, bookmakers):
    matches = await fetch_api_data(name)

    if all_matches is False:
        filtered_matches = filter_matches_by_hour(matches)
        h2h_filtered_matches = extract_bookmaker_data(filtered_matches, bookmakers)
        serialized_filtered_matches = [match.model_dump_json() for match in h2h_filtered_matches]
        store_data(serialized_filtered_matches)
        no_vig_data = remove_vig(serialized_filtered_matches)
        return no_vig_data
    else:
        filtered_matches = filter_matches_by_day(matches)
        h2h_filtered_matches = extract_bookmaker_data(filtered_matches, bookmakers)
        print(h2h_filtered_matches)
        serialized_filtered_matches = [match.model_dump_json() for match in h2h_filtered_matches]
        store_data(serialized_filtered_matches)
        no_vig_data = remove_vig(serialized_filtered_matches)

        return no_vig_data


async def fetch_odds_for_match(competition_name, match_id):
    # Fetch new odds data
    matches = await fetch_api_data(competition_name)
    match = next((m for m in matches if m["id"] == match_id), None)
    if match:
        h2h_filtered_match = extract_bookmaker_data([match])
        no_vig_data = remove_vig([h2h_filtered_match[0].model_dump_json()])
        return no_vig_data
    return {}


# FastAPI route
# @router.get("/{competition_name}/{all_matches}",dependencies=[Depends(has_access), Depends(rate_limit_dependency)]) recover it later
@router.get("/odds/{leagues}", dependencies=[Depends(has_access),])
async def get_odds(
        leagues: str,  # Path parameter (required)
        bookmakers: Optional[str] = Query("pinnacle"),  # Query parameter
        allMatches: bool = Query(False)  # Query parameter
):
    try:

        # Convert comma-separated bookmakers to a list
        bookmakers_list = [b.strip() for b in bookmakers.split(",")] if bookmakers else []

        # Ensure Pinnacle is always included
        if "Pinnacle" not in bookmakers_list:
            bookmakers_list.append("Pinnacle")

        # Call your function to fetch data
        data = await main(leagues, allMatches, bookmakers_list)
        print(data)
        return data
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# @router.post("odds/calculate-ev/",dependencies=[Depends(has_access)])
# async def calculate_ev_for_user(
#     match_data: [dict],
#     premium_user: bool = Depends(lambda: True),  # Replace with actual auth check
# ):
#     if not premium_user:
#         raise HTTPException(status_code=403, detail="Upgrade to premium to access EV Finder.")
#
#     profitable_bets = []
#     for match in match_data:
#         for bookmaker in match["bookmakers"]:
#             if bookmaker["name"] != "pinnacle":
#                 for market in bookmaker["markets"]:
#                     for outcome in market["outcomes"]:
#                         fair_odds = outcome.get("no_vig_price")
#                         if fair_odds:
#                             ev = calculate_ev(outcome["price"], fair_odds)
#                             if ev > 5:  # Only return profitable bets
#                                 profitable_bets.append({
#                                     "match": f"{match['home_team']} vs {match['away_team']}",
#                                     "bookmaker": bookmaker["name"],
#                                     "market": market["key"],
#                                     "outcome": outcome["name"],
#                                     "odds": outcome["price"],
#                                     "fair_odds": fair_odds,
#                                     "ev": round(ev, 2)
#                                 })
#
#     return profitable_bets if profitable_bets else {"message": "No profitable EV bets found"}