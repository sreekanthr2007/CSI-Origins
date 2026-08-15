"""FastAPI application entry point for Cross-Bank Mule Account Detection Network."""
import logging
import contextlib
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.config import settings
from backend.app.api.routes import router as api_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("mule-detection-core")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Auto-seeds graph with initial multi-bank transactions on server startup."""
    try:
        from backend.app.config import settings
        from backend.app.data_generator.motif_injector import generate_with_contamination
        from backend.app.privacy.hashing import generate_standing_hash
        from backend.app.api.routes import BANK_VAULTS, graph_engine

        if graph_engine.get_graph().node_count == 0:
            dataset = generate_with_contamination(
                num_banks=6,
                num_accounts_per_bank=25,
                num_edges=60,
                contamination_rate=0.20,
                seed=42
            )
            for acc in dataset.get("accounts", []):
                b_id = acc.get("bank_id")
                if b_id in BANK_VAULTS:
                    BANK_VAULTS[b_id].register_account(
                        account_number=acc.get("account_number"),
                        ifsc_code=acc.get("ifsc_code"),
                        customer_name=acc.get("customer_name", "Demo User"),
                        kyc_status=acc.get("kyc_status", "verified")
                    )
            standing_key = settings.get_standing_key()
            enriched_edges = []
            for e in dataset.get("edges", []):
                s_acc = e.get("sender_account", "")
                s_ifsc = e.get("sender_ifsc", "SBIN0001000")
                r_acc = e.get("receiver_account", "")
                r_ifsc = e.get("receiver_ifsc", "HDFC0001000")
                s_hash = e.get("sender_hash") or generate_standing_hash(s_acc, s_ifsc, standing_key)
                r_hash = e.get("receiver_hash") or generate_standing_hash(r_acc, r_ifsc, standing_key)
                e_copy = dict(e)
                e_copy["sender_hash"] = s_hash
                e_copy["receiver_hash"] = r_hash
                e_copy["bank_id"] = e.get("sender_bank_id") or e.get("bank_id", "UNKNOWN")
                enriched_edges.append(e_copy)

            graph_engine.get_graph().add_edges_batch(enriched_edges)
            logger.info(f"Auto-seeded graph with {len(enriched_edges)} initial transactions.")
    except Exception as e:
        logger.warning(f"Initial graph auto-seeding skipped: {e}")
    yield



app = FastAPI(
    title=settings.APP_NAME,
    description="Privacy-Preserving Federated Graph Intelligence for Multi-Bank Fraud Rings",
    version="1.0.0",
    lifespan=lifespan
)


# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to capture unhandled errors gracefully."""
    logger.error(f"Unhandled server error on {request.url.path}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"status": "error", "message": "Internal server error occurred.", "path": request.url.path}
    )


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}


# Register API routes under both /api and /api/v1
app.include_router(api_router, prefix="/api", tags=["Core API"])
app.include_router(api_router, prefix="/api/v1", tags=["v1 API"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
