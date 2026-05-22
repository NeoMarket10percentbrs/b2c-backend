import os
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from starlette.exceptions import HTTPException as StarletteHTTPException
import httpx
from core.database import engine, Base
from core.config import settings
from routers import routes
from services.b2b import close_b2b_client, init_b2b_client

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENV in ("development", "production"):
        async with engine.begin() as conn:
            print("ok")

    try:
        init_b2b_client()
    except Exception as e:
        print(f"Failed to initialize B2B client: {e}")
        if settings.ENV == "production":
            raise

    print("Application started successfully")

    yield

    await close_b2b_client()
    await engine.dispose()


app = FastAPI(
	title="NeoMarket Order Service",
	lifespan=lifespan,
	debug=settings.DEBUG,
)


def _error_payload(code: str, message: str) -> dict:
    return {"code": code, "message": message}


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload("HTTP_ERROR", str(exc.detail)),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    message = "Validation error"
    if errors:
        first = errors[0]
        field = first.get("loc", [])
        msg = first.get("msg", "")
        if field:
            message = f"Field '{'.'.join(map(str, field))}' {msg}"
        elif msg:
            message = msg
    return JSONResponse(
        status_code=422,
        content=_error_payload("VALIDATION_ERROR", message),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=_error_payload("INTERNAL_ERROR", "Internal server error"),
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:5173'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


for router in routes:
	app.include_router(router, prefix="/api/v1")

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
