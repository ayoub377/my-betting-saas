from dataclasses import dataclass
from datetime import datetime

from app.services.base import TransfermarktBase
from app.utils.regex import REGEX_BG_COLOR, REGEX_COUNTRY_ID, REGEX_MEMBERS_DATE
from app.utils.utils import clean_response, extract_from_url, remove_str, safe_regex, safe_split
from app.utils.xpath import Clubs, Staff


@dataclass
class TransfermarktClubAttendance(TransfermarktBase):
    """
    A class for retrieving and parsing the profile information of a football club from Transfermarkt.

    Args:
        club_id (str): The unique identifier of the football club.
        URL (str): The URL template for the club's profile page on Transfermarkt.
    """

    club_id: str = None
    URL: str = "https://www.transfermarkt.com/-/besucherzahlenentwicklung/verein/{club_id}"

    def __post_init__(self) -> None:
        """Initialize the TransfermarktClubProfile class."""
        self.URL = self.URL.format(club_id=self.club_id)
        self.page = self.request_url_page()
        # self.raise_exception_if_not_found(xpath=Clubs.Profile.URL)

    def get_club_staff(self) -> dict:
        """
        Retrieve and parse the profile information of the football club from Transfermarkt.

        This method extracts various attributes of the club's profile, such as name, official name, address, contact
        information, stadium details, and more.

        Returns:
            dict: A dictionary containing the club's profile information.
        """
        self.response["average_attendance"] = self.get_text_by_xpath(Staff.AVERAGE_ATTENDANCE)

        return clean_response(self.response)
