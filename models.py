"""
Pydantic models for the P2P Blockchain Network
Provides data validation and serialization for API requests/responses
"""

from pydantic import BaseModel, Field
from typing import List, Optional

class TransactionModel(BaseModel):
    sender: str
    recipient: str
    amount: float
    timestamp: Optional[float] = None
    txid: Optional[str] = None

class BlockModel(BaseModel):
    index: int
    timestamp: float
    transactions: List[TransactionModel]
    previous_hash: str
    nonce: int
    hash: str

class NodeRegisterModel(BaseModel):
    nodes: List[str] = Field(..., description="List of peer node addresses (ip:port)")