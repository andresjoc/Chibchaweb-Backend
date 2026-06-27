from fastapi import FastAPI, Depends
from api.routes import router
from api.DAO.database import engine, Base
from fastapi.middleware.cors import CORSMiddleware
from api.security import verificar_api_key


Base.metadata.create_all(bind=engine)
app = FastAPI()
app.include_router(router, dependencies=[Depends(verificar_api_key)])

origins = [
    "http://localhost:5173",
    "https://chibchaweb-hosting-platform-frontend-production.up.railway.app",
    "https://chibchaweb-front-production.up.railway.app",
    "https://www.chibchaweb.site",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)