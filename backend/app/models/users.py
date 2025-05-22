from pydantic import BaseModel

class WaitlistEmail(BaseModel):
    email: str