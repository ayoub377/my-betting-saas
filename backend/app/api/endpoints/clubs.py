import asyncio
import json
import os
from collections import defaultdict
from typing import Optional, Dict

import httpx
from fastapi import APIRouter, HTTPException, Depends
from dotenv import load_dotenv

from app.core import auth
from app.core.config import redis_client, rate_limit_dependency
from app.models.loader import fetch_club_id, fetch_club_players_data
from app.services.clubs.players import TransfermarktClubPlayers
from app.services.clubs.profile import TransfermarktClubProfile
from app.services.clubs.search import TransfermarktClubSearch
from app.services.clubs.attendance import TransfermarktClubAttendance
from app.services.clubs.staff import TransfermarktClubStaffs
from app.services.flashscore_scraper.flashscore_scraper import FlashScoreScraper
from app.utils.utils import parse_market_value


router = APIRouter()


# load_dotenv()  # Load environment variables from .env file


@router.get("/search/{club_name}")
def search_clubs(club_name: str, page_number: Optional[int] = 1) -> dict:
    tfmkt = TransfermarktClubSearch(query=club_name, page_number=page_number)
    found_clubs = tfmkt.search_clubs()
    return found_clubs


@router.get("/search/{club_name}/injured")
def get_club_injuries(club_name: str):
    # Fetch club IDs
    club1_id = fetch_club_id(club_name)

    if not club1_id:
        print("Could not fetch one or both club IDs.")
        return None

    # Fetch players data
    players_club1 = fetch_club_players_data(club1_id["id"])

    # The fultred players
    filtered_players = {
        club_name: [],

    }

    # Process players for the club
    if isinstance(players_club1, dict):
        # get the list in players key
        players_list = players_club1["players"]
        if isinstance(players_list, list):  # Ensure it's a list
            for player in players_list:
                # Ensure it is a dictionary
                if isinstance(player, dict) and 'status' in player:
                    # Check if the player's status is not "Team captain"
                    if player['status'] != "Team captain":
                        filtered_players[club_name].append(player)

    return filtered_players


# @router.get("/compare/{club_home_name}/{club_away_name}")
# async def compare_players(club_home_name: str, club_away_name: str):
#     async with httpx.AsyncClient() as client:
#         # Fetch team IDs concurrently
#         home_team_id_task = asyncio.create_task(fetch_club_id(club_home_name))
#         away_team_id_task = asyncio.create_task(fetch_club_id(club_away_name))
#
#         home_team_id = await home_team_id_task
#         away_team_id = await away_team_id_task
#         # Fetch player data concurrently
#         home_players_task = asyncio.create_task(fetch_club_players_data(home_team_id["id"]))
#         away_players_task = asyncio.create_task(fetch_club_players_data(away_team_id["id"]))
#
#         home_team_players_data = await home_players_task
#         away_team_players_data = await away_players_task
#
#         home_team_players = home_team_players_data.get("players", [])
#         away_team_players = away_team_players_data.get("players", [])
#
#     # Group players by position
#     home_team_positions = defaultdict(list)
#     away_team_positions = defaultdict(list)
#
#     for player in home_team_players:
#         home_team_positions[player["position"]].append(player)
#
#     for player in away_team_players:
#         away_team_positions[player["position"]].append(player)
#
#     comparison_results = []
#
#     # Concurrently parse market values and compare players
#     async def compare_position(position):
#         home_players = home_team_positions.get(position, [])
#         away_players = away_team_positions.get(position, [])
#
#         position_results = []
#
#         if home_players and away_players:
#             for home_player in home_players:
#                 for away_player in away_players:
#                     home_value = await parse_market_value(home_player.get("marketValue", ""))
#                     away_value = await parse_market_value(away_player.get("marketValue", ""))
#
#                     if home_value > away_value:
#                         result = (
#                             f"{club_home_name}'s {home_player['name']} ({position}) has a higher market value "
#                             f"({format_market_value(home_value)}) than {club_away_name}'s {away_player['name']} ({format_market_value(away_value)})."
#                         )
#                     elif away_value > home_value:
#                         result = (
#                             f"{club_away_name}'s {away_player['name']} ({position}) has a higher market value "
#                             f"({format_market_value(away_value)}) than {club_home_name}'s {home_player['name']} ({format_market_value(home_value)})."
#                         )
#                     else:
#                         result = (
#                             f"Both teams have players with equal market value ({format_market_value(home_value)}) at {position}: "
#                             f"{club_home_name}'s {home_player['name']} and {club_away_name}'s {away_player['name']}."
#                         )
#
#                     position_results.append(result)
#
#         elif home_players:
#             for home_player in home_players:
#                 result = f"{club_home_name} has {home_player['name']} at {position}, but {club_away_name} has no player for this position."
#                 position_results.append(result)
#
#         elif away_players:
#             for away_player in away_players:
#                 result = f"{club_away_name} has {away_player['name']} at {position}, but {club_home_name} has no player for this position."
#                 position_results.append(result)
#
#         else:
#             position_results.append(f"Neither team has a player for {position}.")
#
#         return position_results
#
#     all_positions = set(home_team_positions.keys()).union(set(away_team_positions.keys()))
#     tasks = [compare_position(position) for position in all_positions]
#
#     position_results = await asyncio.gather(*tasks)
#     comparison_results.extend([result for sublist in position_results for result in sublist])
#
#     return {"comparison": comparison_results}


# TODO: add a way to get number of players that has high market value of each team and compare the actual difference of each position with other team


@router.get("/compare_with_lineup")
async def compare_players_with_lineup(club_home_name: str, club_away_name: str, lineups: Dict):
    """
    Compare players' market value for a match using starting lineup data based on jersey numbers.
    :param club_home_name: Home team name.
    :param club_away_name: Away team name.
    :param lineups: JSON with home and away team starting lineups (jersey numbers as keys, names as values).
    :return: JSON comparison results.
    """
    async with httpx.AsyncClient() as client:
        # Fetch team IDs concurrently
        home_team_id, away_team_id = await asyncio.gather(
            fetch_club_id(club_home_name),
            fetch_club_id(club_away_name)
        )

        # Validate team IDs
        if not home_team_id or not away_team_id:
            missing_teams = []
            if not home_team_id:
                missing_teams.append(f"home team '{club_home_name}'")
            if not away_team_id:
                missing_teams.append(f"away team '{club_away_name}'")
            raise HTTPException(
                status_code=400,
                detail=f"Unrecognized team(s): {', '.join(missing_teams)}. Please provide valid team names."
            )

        # Fetch player data
        home_team_players_data, away_team_players_data = await asyncio.gather(
            fetch_club_players_data(home_team_id["id"]),
            fetch_club_players_data(away_team_id["id"])
        )

    # Ensure player data is available
    if not home_team_players_data or not away_team_players_data:
        raise ValueError("Failed to fetch player data for one or both teams.")

    home_team_players = home_team_players_data.get("players", [])
    away_team_players = away_team_players_data.get("players", [])

    # Filter players based on starting lineup jersey numbers
    starting_home_players = {
        player["jersey_number"]: player
        for player in home_team_players if player.get("jersey_number") in lineups["home_team"]
    }
    starting_away_players = {
        player["jersey_number"]: player
        for player in away_team_players if player.get("jersey_number") in lineups["away_team"]
    }

    # Organize players by positions
    home_team_positions = defaultdict(list)
    away_team_positions = defaultdict(list)

    for player in starting_home_players.values():
        home_team_positions[player["position"]].append(player)

    for player in starting_away_players.values():
        away_team_positions[player["position"]].append(player)

    # Helper function: Compare players at a position
    async def compare_position(position):
        home_players = home_team_positions.get(position, [])
        away_players = away_team_positions.get(position, [])

        comparisons = []
        if home_players and away_players:
            for home_player in home_players:
                for away_player in away_players:
                    home_value = await parse_market_value(home_player.get("marketValue", "0"))
                    away_value = await parse_market_value(away_player.get("marketValue", "0"))

                    comparison = {
                        "position": position,
                        "home_player": {
                            "name": home_player["name"],
                            "jersey_number": home_player["jersey_number"],
                            "market_value": home_value
                        },
                        "away_player": {
                            "name": away_player["name"],
                            "jersey_number": away_player["jersey_number"],
                            "market_value": away_value
                        },
                        "result": "home_higher" if home_value > away_value else
                        "away_higher" if away_value > home_value else "equal"
                    }
                    comparisons.append(comparison)

        elif home_players:
            for home_player in home_players:
                comparisons.append({
                    "position": position,
                    "home_player": {
                        "name": home_player["name"],
                        "jersey_number": home_player["jersey_number"],
                        "market_value": await parse_market_value(home_player.get("marketValue", "0"))
                    },
                    "away_player": None,
                    "result": "home_only"
                })

        elif away_players:
            for away_player in away_players:
                comparisons.append({
                    "position": position,
                    "home_player": None,
                    "away_player": {
                        "name": away_player["name"],
                        "jersey_number": away_player["jersey_number"],
                        "market_value": await parse_market_value(away_player.get("marketValue", "0"))
                    },
                    "result": "away_only"
                })

        else:
            comparisons.append({
                "position": position,
                "home_player": None,
                "away_player": None,
                "result": "no_players"
            })

        return comparisons

    # Fetch cached data if available
    cache_key = f"team_comparison:{club_home_name}:{club_away_name}"
    cached_results = await redis_client.get(cache_key)
    if cached_results:
        return json.loads(cached_results)

    # Compare all positions
    all_positions = set(home_team_positions.keys()).union(away_team_positions.keys())
    tasks = [compare_position(position) for position in all_positions]
    position_results = await asyncio.gather(*tasks)

    # Flatten results
    comparison_results = [result for sublist in position_results for result in sublist]

    # Cache the results
    cache_expiry = 7200
    await redis_client.setex(cache_key, cache_expiry, json.dumps(comparison_results))

    return {
        "home_team": club_home_name,
        "away_team": club_away_name,
        "comparison": comparison_results
    }


# @router.get("/compare/{home_team}/{away_team}", dependencies=[Depends(auth.has_access),Depends(rate_limit_dependency)]) recover it later
@router.get("/compare/{home_team}/{away_team}", dependencies=[Depends(auth.has_access), Depends(rate_limit_dependency)])
async def get_comparaison_result(home_team: str, away_team: str):
    # Generate a unique cache key for this request
    cache_key = f"lineups:{home_team}:{away_team}"

    try:
        # Check if the lineups are already cached
        cached_lineups = await redis_client.get(cache_key)
        if cached_lineups:
            print("Retrieving lineups from cache")
            intermediate = json.loads(cached_lineups)
            # Second deserialization: Convert the JSON string to a dictionary
            lineups = json.loads(intermediate)
        else:
            scraper = FlashScoreScraper()
            match_id = scraper.get_team_id_by_name(home_team)
            if not match_id:
                raise HTTPException(status_code=404, detail=f"Match ID for {home_team} not found.")
            lineups = scraper.scrape_lineups(match_id=match_id)

            # Cache the scraped lineups for future requests
            await redis_client.set(cache_key, json.dumps(lineups), ex=3600)  # Cache for 1 hour
        # Process the lineups
        response_comparison = await compare_players_with_lineup(home_team, away_team, lineups)
        return response_comparison

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{club_id}/profile")
def get_club_profile(club_id: str) -> dict:
    tfmkt = TransfermarktClubProfile(club_id=club_id)
    club_profile = tfmkt.get_club_profile()
    return club_profile


@router.get("/{club_id}/stadium")
def get_club_stadium(club_id: str) -> dict:
    tfmkt = TransfermarktClubAttendance(club_id=club_id)
    club_staff = tfmkt.get_club_staff()
    return club_staff


@router.get("/{club_id}/players")
def get_club_players(club_id: str, season_id: Optional[str] = None) -> dict:
    tfmkt = TransfermarktClubPlayers(club_id=club_id, season_id=season_id)
    club_players = tfmkt.get_club_players()
    return club_players


@router.get("/{club_id}/staffs")
def get_club_staffs(club_id: str) -> dict:
    tfmkt = TransfermarktClubStaffs(club_id=club_id)
    club_staffs = tfmkt.get_club_staffs()
    return club_staffs
