from fastapi import Header, HTTPException, Request
import os

API_KEY = os.getenv("API_KEY")
API_KEY_NAME = os.getenv("API_KEY_NAME", "Chibcha-api-key")

def verificar_api_key(request: Request, x_api_key: str = Header(None, alias=API_KEY_NAME)):
    if request.method == "OPTIONS":
        return
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="API Key inválida")
