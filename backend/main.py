# =============================================
#  台股 AI 網站 — 後端主程式 (FastAPI)
# =============================================

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import uvicorn

from auth import router as auth_router
from stocks import router as stocks_router
from portfolio import router as portfolio_router
from analysis import router as analysis_router
from database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="台股 AI 分析平台",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 部署後改成你的前端網址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,      prefix="/api/auth",      tags=["認證"])
app.include_router(stocks_router,    prefix="/api/stocks",    tags=["股票"])
app.include_router(portfolio_router, prefix="/api/portfolio", tags=["持倉"])
app.include_router(analysis_router,  prefix="/api/analysis",  tags=["AI分析"])

@app.get("/")
def root():
    return {"status": "ok", "message": "台股 AI 平台運行中"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
