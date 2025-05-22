import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
from fuzzywuzzy import fuzz, process
from app.utils.utils import extract_first_name


class FlashScoreScraper:
    TEAM_NAME_ABBREVIATIONS = {
        "atletico madrid": "atl. Madrid",
        "athletic bilbao": "ath bilbao",
        "borussia Monchengladbach": "B. Monchengladbach",
        "atletico tucuman": "atl. tucuman"

    }

    def __init__(self, match_id=None):
        """
        Initialize the scraper with the match ID and WebDriver path.
        :param match_id: The ID of the match to scrape.
        :param driver_path: Path to the Selenium WebDriver executable.
        """
        # self.match_id = match_id
        self.BASE_URL = f"https://www.flashscore.com/"
        self.options = Options()
        self.options.add_argument("--headless=new")  # Use "--headless=new" for
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument("--disable-images")
        self.options.add_argument("--blink-settings=imagesEnabled=false")
        self.driver = webdriver.Chrome(options=self.options)

    def normalize_team_name(self, team_name: str):
            """
            Normalize the team name to match the abbreviated or full version used in Flashscore,
            considering possible misspellings or partial input.
            :param team_name: The name of the team provided by the user.
            :return: The normalized team name.
            """
            # Convert user input to lowercase for case-insensitive matching
            team_name = team_name.lower()

            # Use fuzzy matching to find the closest match in the abbreviation dictionary
            best_match = process.extractOne(team_name, self.TEAM_NAME_ABBREVIATIONS.keys(), scorer=fuzz.partial_ratio)

            # If a good match is found (e.g., fuzz score > 80), return the corresponding abbreviation
            if best_match and best_match[1] > 80:
                return self.TEAM_NAME_ABBREVIATIONS[best_match[0]]

            # If no good match is found, return the original team name (in case of unknown teams)
            return team_name

    def scrape_lineups(self, match_id):

        """
        Scrape the lineups for the match and return a JSON object with home and away teams' players.
        :return: JSON object containing home and away players.
        """
        try:
            # get the lineups URL
            match_summary_url = f"{self.BASE_URL}match/{match_id}/#/match-summary/match-summary"
            # Load the page
            self.driver.get(match_summary_url)
            wait = WebDriverWait(self.driver, 10)

            # Wait for and click the Lineups button
            lineups_link = wait.until(
                EC.presence_of_element_located((By.XPATH, "//a[@href='#/match-summary/lineups']"))
            )

            # Scroll the element into view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", lineups_link)

            # Wait for the element to be clickable and click it

            # Click the element via JavaScript
            self.driver.execute_script("arguments[0].click();", lineups_link)
            # Wait for the lineup section to load
            lineups_section = wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "lf__lineUp"))
            )

            sections = lineups_section.find_elements(By.CLASS_NAME, "section")
            starting_lineup_section = None
            for section in sections:
                try:
                    # Check if the section contains the "Starting Lineups" title
                    title_div = section.find_element(By.XPATH,
                                                     ".//span[contains(@class, 'wcl-overline_rOFfd') and contains("
                                                     "@class, 'wcl-scores-overline-02_n9EXm')]")

                    if title_div.text == "STARTING LINEUPS":
                        starting_lineup_section = section
                        break
                except:
                    # If the title div is not found, skip this section
                    continue

            if starting_lineup_section is None:
                raise ValueError("Starting Lineups section not found.")

            # Find the sides container
            sides_box = starting_lineup_section.find_element(By.CLASS_NAME, "lf__sides")
            sides = sides_box.find_elements(By.CLASS_NAME, "lf__side")

            # Check if there are exactly two sides (home and away)
            if len(sides) != 2:
                raise Exception("Expected two sides for lineups (home and away).")

            # Extract player names for home and away teams
            team_data = {}
            for idx, side in enumerate(["home_team", "away_team"]):
                players_div = sides[idx].find_elements(By.CSS_SELECTOR,
                                                       ".lf__participantNew:not(.lf__participantNew--substituedPlayer)")
                players = {}
                for player_div in players_div:
                    strong_element = player_div.find_element(
                        By.XPATH,
                        ".//strong[@data-testid='wcl-scores-simpleText-01']"
                    )

                    full_name = strong_element.text
                    first_name = extract_first_name(full_name)
                    jersey_span = player_div.find_element(
                        By.CSS_SELECTOR,
                        ".wcl-simpleText_Asp-0.wcl-scores-simpleText-01_pV2Wk.wcl-number_7yjM9"
                    )
                    jersey_number = jersey_span.text

                    # Add to dictionary
                    players[jersey_number] = first_name
                team_data[side] = players

            # Return JSON
            return json.dumps(team_data, indent=4)

        except Exception as e:
            raise Exception(f"An error occurred: {str(e)}")

        finally:
            self.driver.quit()

    def get_team_id_by_name(self, home_team: str):
        """
        Search for a home team by name and extract its team_id from the parent <a> tag.
        :param home_team: The name of the home team to search for.
        :return: The extracted team_id or None if not found.
        """
        # Normalize the team name
        normalized_team_name = self.normalize_team_name(home_team)
        team_element_xpath = f"//span[contains(@class, 'wcl-simpleText_Asp-0') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), translate('{normalized_team_name}', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))] | //strong[contains(@class, 'wcl-simpleText_Asp-0') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), translate('{normalized_team_name}', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'))]"

        try:
            # Load the page
            self.driver.get(self.BASE_URL)
            wait = WebDriverWait(self.driver, 10)

            # Wait for the team name element to appear
            team_name_span = wait.until(
                EC.presence_of_element_located((
                    By.XPATH,
                    team_element_xpath)
                )
            )

            # Navigate to the parent <div> with the relevant match information
            grandparent_element = team_name_span.find_element(By.XPATH, "../..")
            # get the id
            grandparent_id = grandparent_element.get_attribute("id")

            # remove the substring and only leave relevant match_id
            match_id = re.sub(r'^g_1_', '', grandparent_id)
            return match_id

        except Exception as e:
            raise Exception(f"An error occurred while searching for the team: {str(e)}")


# Example Usage
if __name__ == "__main__":
    team_name = input("enter team name:")

    scraper = FlashScoreScraper()
    match_id = scraper.get_team_id_by_name(team_name)
    print(match_id)
    lineups = scraper.scrape_lineups(match_id=match_id)
    print(lineups)
