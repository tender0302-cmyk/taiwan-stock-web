from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from auth       import router as auth_router
from stocks     import router as stocks_router
from portfolio  import router as portfolio_router
from analysis   import router as analysis_router
from simulation import router as sim_router
from database   import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from stocks import start_warmup
    start_warmup()
    yield

app = FastAPI(title="台股 AI 分析平台", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,      prefix="/api/auth",       tags=["認證"])
app.include_router(stocks_router,    prefix="/api/stocks",     tags=["股票"])
app.include_router(portfolio_router, prefix="/api/portfolio",  tags=["持倉"])
app.include_router(analysis_router,  prefix="/api/analysis",   tags=["AI分析"])
app.include_router(sim_router,       prefix="/api/simulation", tags=["模擬下單"])

@app.get("/")
def root():
    return {"status": "ok", "message": "台股 AI 平台運行中"}
