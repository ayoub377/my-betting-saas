from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import credentials, auth
from firebase_admin.exceptions import FirebaseError
import os
from dotenv import load_dotenv

load_dotenv()

security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        # Verify the Firebase token and extract the user's UID
        decoded_token = auth.verify_id_token(credentials.credentials)
        uid = decoded_token['uid']
        return uid
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")


def verify_firebase_token(token: str) -> dict:
    """
    Verify the provided Firebase JWT using Firebase Admin SDK.

    Args:
        token (str): The JWT to verify.

    Returns:
        dict: Decoded token payload if verification succeeds.

    Raises:
        HTTPException: If token verification fails.
    """
    try:
        # Verify the token using Firebase Admin SDK
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except FirebaseError as e:
        # Handle invalid token errors
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


async def has_access(credentials_: HTTPAuthorizationCredentials = Depends(security)):
    """
    Middleware function to validate the Firebase JWT.

    Args:
        credentials_ (HTTPAuthorizationCredentials): Token extracted from Authorization header.

    Raises:
        HTTPException: If the token is invalid.
    """
    token = credentials_.credentials  # Extract token from Authorization header
    decoded_token = verify_firebase_token(token)
    return decoded_token
