import os
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import httpx
from core.database import engine, Base
from core.config import settings
from routers import routes

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
	if settings.ENV == "development" or settings.ENV == "production":
		async with engine.begin() as conn:
			await conn.run_sync(Base.metadata.create_all)
		print("Database tables created")

	app.state.http_client = httpx.AsyncClient(
		base_url=settings.SELLER_SERVICE_URL,
		timeout=5.0,
	)

	try:
		None
	except Exception as e:
		print(f"Failed to initialize database: {e}")
		if settings.ENV == "production":
			raise

	print("Application started successfully")

	yield

	await app.state.http_client.aclose()
	await engine.dispose()


app = FastAPI(
	title="NeoMarket Order Service",
	lifespan=lifespan,
	debug=settings.DEBUG,
)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_methods=["*"],
	allow_headers=["*"],
)


for router in routes:
	app.include_router(router, prefix="/api")

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

if __name__ == "__main__":
	uvicorn.run(
		"main:app",
		host=settings.APP_HOST,
		port=settings.APP_PORT,
		reload=settings.APP_RELOAD,
		log_level=settings.APP_LOG_LEVEL.lower(),
	)
