import asyncio
import logging
import os
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Set
import httpx
from blockchain import Blockchain, Transaction, Block
from models import TransactionModel, BlockModel, NodeRegisterModel

app = FastAPI(title="P2P Blockchain Node", description="A peer-to-peer blockchain network node.")
templates = Jinja2Templates(directory="templates")

# Blockchain instance (singleton per node)
blockchain = Blockchain()

# WebSocket manager for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

ws_manager = ConnectionManager()

# CORS for cross-node communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("blockchain-node")

# --- FastAPI Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "chain": blockchain.chain, "peers": list(blockchain.nodes), "mempool": blockchain.mempool})

@app.get("/chain")
async def get_chain():
    return blockchain.to_dict()

@app.post("/transactions/new")
async def new_transaction(tx: TransactionModel):
    transaction = Transaction(**tx.dict())
    if not blockchain.add_transaction(transaction):
        raise HTTPException(status_code=400, detail="Invalid transaction (insufficient balance or invalid data)")
    await ws_manager.broadcast({"event": "new_transaction", "transaction": transaction.to_dict()})
    return {"message": "Transaction will be added to the next block."}

@app.get("/mine")
async def mine_block():
    miner_address = os.getenv("NODE_ADDRESS", "miner")
    block = blockchain.mine_block(miner_address)
    if not block:
        raise HTTPException(status_code=400, detail="No transactions to mine.")
    await broadcast_block(block)
    await ws_manager.broadcast({"event": "new_block", "block": block.to_dict()})
    return {"message": "Block mined", "block": block.to_dict()}

@app.post("/nodes/register")
async def register_nodes(data: NodeRegisterModel):
    new_nodes = set(data.nodes)
    if not new_nodes:
        raise HTTPException(status_code=400, detail="No nodes provided.")
    for node in new_nodes:
        blockchain.register_node(node)
    return {"message": "New nodes have been added", "total_nodes": list(blockchain.nodes)}

@app.get("/nodes/resolve")
async def consensus():
    replaced = await resolve_conflicts()
    return {"message": "Chain replaced" if replaced else "Chain is authoritative", "chain": blockchain.to_dict()}

@app.get("/nodes")
async def get_nodes():
    return {"nodes": list(blockchain.nodes)}

@app.get("/mempool")
async def get_mempool():
    return {"mempool": [tx.to_dict() for tx in blockchain.mempool]}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

# --- Peer Discovery, Consensus, and Broadcast ---

async def broadcast_block(block: Block):
    for node in blockchain.nodes:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"http://{node}/blocks/new", json=block.to_dict(), timeout=5)
        except Exception as e:
            logger.warning(f"Failed to broadcast block to {node}: {e}")

@app.post("/blocks/new")
async def receive_block(block_data: BlockModel):
    block = Block.from_dict(block_data.dict())
    last_block = blockchain.get_last_block()
    if block.previous_hash == last_block.hash and block.hash == block.calculate_hash():
        blockchain.chain.append(block)
        blockchain.recalculate_balances()
        blockchain.mempool.clear()
        await ws_manager.broadcast({"event": "new_block", "block": block.to_dict()})
        return {"message": "Block added"}
    else:
        raise HTTPException(status_code=400, detail="Invalid block")

async def resolve_conflicts() -> bool:
    new_chain = None
    max_length = len(blockchain.chain)
    for node in blockchain.nodes:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://{node}/chain", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    length = data["length"]
                    chain = [Block.from_dict(b) for b in data["chain"]]
                    if length > max_length and blockchain.validate_chain(chain):
                        max_length = length
                        new_chain = chain
        except Exception as e:
            logger.warning(f"Failed to fetch chain from {node}: {e}")
    if new_chain:
        blockchain.replace_chain(new_chain)
        await ws_manager.broadcast({"event": "chain_replaced", "chain": blockchain.to_dict()})
        return True
    return False

# --- Background Tasks ---
@app.on_event("startup")
async def startup_event():
    # Optionally, auto-register with known peers or perform initial sync
    pass

# --- Exception Handlers ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": str(exc)}) 