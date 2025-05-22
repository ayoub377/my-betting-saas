# import json
# import uuid
# from datetime import datetime
# import requests
# from app.models.database import SessionLocal
# from app.models.team import Team, Player
#
# import logging
# from sqlalchemy.orm import Session
#
import logging

from app.core.config import redis_client

# # Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
#
#


import httpx


async def fetch_club_id(club_name):
    cache_key = f"club_id:{club_name}"
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        print(f"Cache hit for {club_name}")
        return {"id": cached_data}

    base_url = "http://127.0.0.1:9000/clubs"
    try:
        async with httpx.AsyncClient(proxies=None) as client:
            response = await client.get(f"{base_url}/search/{club_name}")
            response.raise_for_status()
            club_results = response.json()
            logger.debug("Getting the ID for the club name")
            # Filter to find the exact match
            for club in club_results.get("results", []):
                if club_name.lower() in club["name"].lower():  # Case-insensitive match
                    await redis_client.set(cache_key,club["id"], ex=86400)
                    return {"id": club["id"]}
            # If no match is found, return the ID of the first team
            if club_results.get("results"):
                first_club_id = club_results["results"][0]["id"]
                await redis_client.set(cache_key, first_club_id, ex=86400)
                return {"id": first_club_id}

            print(f"No exact match found for club: {club_name}")
    except httpx.HTTPStatusError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except httpx.RequestError as req_err:
        print(f"Request error occurred: {req_err}")
    except ValueError as json_err:
        print(f"JSON decode error: {json_err}")

    return None  # Return None if there was an error or no exact match found

#
# # Function to fetch data from each endpoint
# def fetch_club_data(club_id):
#     base_url = "http://127.0.0.1:9000/clubs"  # Adjusted base URL to point to the actual endpoint
#
#     # Fetch data from the endpoints
#     try:
#         profile_response = requests.get(f"{base_url}/{club_id}/profile")
#         stadium_response = requests.get(f"{base_url}/{club_id}/stadium")
#         players_response = requests.get(f"{base_url}/{club_id}/players")
#         staffs_response = requests.get(f"{base_url}/{club_id}/staffs")
#
#         # Check if responses are successful
#         profile_response.raise_for_status()
#         stadium_response.raise_for_status()
#         players_response.raise_for_status()
#         staffs_response.raise_for_status()
#
#         # Parse the JSON responses
#         club_profile = profile_response.json()  # Ensure we call .json() on a successful response
#         club_stadium = stadium_response.json()
#         club_players = players_response.json()
#         club_staffs = staffs_response.json()
#
#         return {
#             "profile": club_profile,
#             "stadium": club_stadium,
#             "players": club_players,
#             "staffs": club_staffs,
#         }
#
#     except requests.exceptions.HTTPError as http_err:
#         print(f"HTTP error occurred: {http_err}")
#     except requests.exceptions.RequestException as req_err:
#         print(f"Request error occurred: {req_err}")
#     except ValueError as json_err:
#         print(f"JSON decode error: {json_err}")
#
#     return None  # Return None if there was an error
#
#

async def fetch_club_players_data(club_id):
    base_url = "http://127.0.0.1:9000/clubs"  # Adjusted base URL to point to the actual endpoint

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/{club_id}/players", timeout=15)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except httpx.RequestError as req_err:
        print(f"Request error occurred: {req_err}")
    except ValueError as json_err:
        print(f"JSON decode error: {json_err}")

    return None  # Return None if there was an error


#
#
# def populate_team(session: Session, team_data: dict, stadium_data: dict, staff_data: dict) -> Team:
#     try:
#         new_team = Team(
#             id=team_data['id'],
#             name=team_data['name'],
#             total_value=parse_market_value(team_data['currentMarketValue']),
#             average_attendance=int(stadium_data['average_attendance'].replace(',', '')),
#             stadium_seats=int(team_data["stadiumSeats"]),
#             coach_name=staff_data.get('name', None),
#             assigned_date=datetime.strptime(staff_data.get('appointed', None), '%b %d, %Y') if staff_data.get(
#                 'appointed') else None,
#             end_contract=datetime.strptime(staff_data.get('contract_expires', None), '%d.%m.%Y') if staff_data.get(
#                 'contract_expires') else None,
#         )
#
#         session.add(new_team)
#         session.commit()
#         return new_team
#
#     except Exception as e:
#         logger.error(f"Error adding team {team_data['name']}: {e}")
#         session.rollback()
#
#
# # def populate_players(session: Session, players_data: list, team_id: int):
# #     for player in players_data:
# #         # Create a new Player instance
# #         new_player = Player(
# #             PlayerId=player['id'],
# #             name=player['name'],
# #             position=player['position'],
# #             marketvalue=parse_market_value(player.get('marketValue', 0)),
# #             status=player.get("status", "No Status"),
# #             age=int(player['age']),
# #             teamid=team_id  # Foreign key reference to Team
# #         )
# #
# #         # Add the new player instance to the session
# #         session.add(new_player)
# #
# #     # Commit the players to the database
# #     session.commit()
# #
# #
# # def populate_team_and_players(json_data: dict):
# #     session = SessionLocal()
# #
# #     try:
# #         # Extract data from JSON
# #         team_data = json_data['profile']
# #         stadium_data = json_data['stadium']
# #         staff_data = json_data['staffs']
# #         players_data = json_data['players']['players']
# #         new_team = populate_team(session, team_data, stadium_data, staff_data)
# #
# #         # Populate players
# #         if isinstance(players_data, list):
# #             populate_players(session, players_data, new_team.id)
# #         else:
# #             logger.error(f"Invalid players data format: {players_data}")
# #
# #     except Exception as e:
# #         session.rollback()  # Rollback in case of error
# #         logger.error(f"Error populating data: {e}")
# #     finally:
# #         session.close()  # Ensure session is closed after operation
# #
# #
# # # # Read club names from the text file and process each one
# # # with open('./clubs', 'r', encoding='utf-8') as file:
# # #     for line in file:
# # #         club_name = line.strip()  # Remove any leading/trailing whitespace
# # #
# # #         if not club_name:  # Skip empty lines if any exist in the file
# # #             continue
# # #
# # #         print(f"Processing {club_name}...")
# # #
# # #         club_search = fetch_club_id(club_name)
# # #
# # #         if club_search is not None:
# # #             id__ = club_search.get('id')
# # #             data = fetch_club_data(id__)
# # #
# # #             if data is not None:
# # #                 populate_team_and_players(data)
# # #             else:
# # #                 print(f"No data found for {club_name}.")
# #
# #
# # def get_players_from_clubs(club_name1, club_name2):
# #     # Fetch club IDs
# #     club1_id = fetch_club_id(club_name1)
# #     club2_id = fetch_club_id(club_name2)
# #
# #     if not club1_id or not club2_id:
# #         print("Could not fetch one or both club IDs.")
# #         return None
# #
# #     # Fetch players data
# #     players_club1 = fetch_club_players_data(club1_id["id"])
# #     players_club2 = fetch_club_players_data(club2_id["id"])
# #
# #     filtered_players = {
# #         club_name1: [],
# #         club_name2: []
# #     }
# #
# #     # Process players for club 1
# #     if isinstance(players_club1, dict):
# #         players_list = players_club1["players"]
# #         if isinstance(players_list, dict):  # Ensure it's a list
# #             players_list = players_list.get('players')
# #             print(len(players_list))
# #             for player in players_list:
# #                 if isinstance(player, dict) and 'status' in player:
# #                     filtered_players[club_name1].append(player)
# #         else:
# #             print(f"Expected 'players' to be a list for {club_name1}: {players_list}")
# #
# #     # Process players for club 2
# #     if isinstance(players_club2, dict):
# #         players_list = players_club2["players"]
# #         if isinstance(players_list, dict):  # Ensure it's a list
# #             players_list = players_list.get('players')
# #             for player in players_list:
# #                 if isinstance(player, dict) and 'status' in player:
# #                     filtered_players[club_name2].append(player)
# #
# #         else:
# #             print(f"Expected 'players' to be a list for {club_name2}: {players_list}")
# #
# #     return filtered_players
# #
#
# # Example usage
#
#
# data = get_players_from_clubs('pohang', 'vissel')
#
# print(data)
