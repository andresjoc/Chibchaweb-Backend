from fastapi import Header, HTTPException
import os

API_KEY = os.getenv("API_KEY")
API_KEY_NAME = os.getenv("API_KEY_NAME", "Chibcha-api-key")

def verificar_api_key(x_api_key: str = Header(..., alias=API_KEY_NAME)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="API Key inválida")
