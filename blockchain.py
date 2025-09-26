import hashlib
import json
import time
import threading
from typing import List, Optional, Dict, Set

# --- Transaction Class ---
class Transaction:
    """
    Represents a transaction in the blockchain.
    """
    def __init__(self, sender: str, recipient: str, amount: float, timestamp: Optional[float] = None, txid: Optional[str] = None):
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.timestamp = timestamp or time.time()
        self.txid = txid or self.calculate_txid()

    def calculate_txid(self) -> str:
        tx_string = f"{self.sender}{self.recipient}{self.amount}{self.timestamp}"
        return hashlib.sha256(tx_string.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "timestamp": self.timestamp,
            "txid": self.txid
        }

    @staticmethod
    def from_dict(data: dict) -> 'Transaction':
        return Transaction(
            sender=data["sender"],
            recipient=data["recipient"],
            amount=data["amount"],
            timestamp=data.get("timestamp"),
            txid=data.get("txid")
        )

# --- Block Class ---
class Block:
    """
    Represents a block in the blockchain.
    """
    def __init__(self, index: int, timestamp: float, transactions: List[Transaction], previous_hash: str, nonce: int = 0, hash_: Optional[str] = None):
        self.index = index
        self.timestamp = timestamp
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = hash_ or self.calculate_hash()

    def calculate_hash(self) -> str:
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash
        }

    @staticmethod
    def from_dict(data: dict) -> 'Block':
        transactions = [Transaction.from_dict(tx) for tx in data["transactions"]]
        return Block(
            index=data["index"],
            timestamp=data["timestamp"],
            transactions=transactions,
            previous_hash=data["previous_hash"],
            nonce=data["nonce"],
            hash_=data["hash"]
        )

# --- Blockchain Class ---
class Blockchain:
    """
    Manages the chain, mining, validation, and consensus.
    """
    def __init__(self, difficulty: int = 4, mining_reward: float = 10.0):
        self.chain: List[Block] = []
        self.difficulty = difficulty
        self.mining_reward = mining_reward
        self.mempool: List[Transaction] = []
        self.nodes: Set[str] = set()
        self.lock = threading.Lock()
        self.create_genesis_block()
        self.balances: Dict[str, float] = {}

    def create_genesis_block(self):
        genesis_block = Block(
            index=0,
            timestamp=time.time(),
            transactions=[],
            previous_hash="0"
        )
        self.chain.append(genesis_block)

    def get_last_block(self) -> Block:
        return self.chain[-1]

    def add_transaction(self, transaction: Transaction) -> bool:
        # Validate transaction (e.g., sufficient balance, valid signature)
        if transaction.sender != "MINING":
            sender_balance = self.balances.get(transaction.sender, 0)
            if sender_balance < transaction.amount:
                return False
        self.mempool.append(transaction)
        return True

    def mine_block(self, miner_address: str) -> Optional[Block]:
        with self.lock:
            # Always allow mining, even if mempool is empty
            transactions = self.mempool[:]
            # Reward transaction
            reward_tx = Transaction(sender="MINING", recipient=miner_address, amount=self.mining_reward)
            transactions.append(reward_tx)
            last_block = self.get_last_block()
            new_block = Block(
                index=last_block.index + 1,
                timestamp=time.time(),
                transactions=transactions,
                previous_hash=last_block.hash
            )
            # Proof of Work
            while not new_block.hash.startswith("0" * self.difficulty):
                new_block.nonce += 1
                new_block.hash = new_block.calculate_hash()
            # Add block
            self.chain.append(new_block)
            # Update balances
            for tx in transactions:
                if tx.sender != "MINING":
                    self.balances[tx.sender] = self.balances.get(tx.sender, 0) - tx.amount
                self.balances[tx.recipient] = self.balances.get(tx.recipient, 0) + tx.amount
            self.mempool.clear()
            return new_block

    def validate_chain(self, chain: Optional[List[Block]] = None) -> bool:
        chain = chain or self.chain
        for i in range(1, len(chain)):
            current = chain[i]
            previous = chain[i - 1]
            if current.previous_hash != previous.hash:
                return False
            if current.hash != current.calculate_hash():
                return False
            # Optional: validate transactions, balances, etc.
        return True

    def replace_chain(self, new_chain: List[Block]) -> bool:
        with self.lock:
            if len(new_chain) > len(self.chain) and self.validate_chain(new_chain):
                self.chain = new_chain
                self.recalculate_balances()
                self.mempool.clear()
                return True
            return False

    def recalculate_balances(self):
        self.balances = {}
        for block in self.chain:
            for tx in block.transactions:
                if tx.sender != "MINING":
                    self.balances[tx.sender] = self.balances.get(tx.sender, 0) - tx.amount
                self.balances[tx.recipient] = self.balances.get(tx.recipient, 0) + tx.amount

    def register_node(self, address: str):
        self.nodes.add(address)

    def to_dict(self) -> dict:
        return {
            "chain": [block.to_dict() for block in self.chain],
            "length": len(self.chain),
            "difficulty": self.difficulty,
            "nodes": list(self.nodes)
        }

    @staticmethod
    def from_dict(data: dict) -> 'Blockchain':
        blockchain = Blockchain(difficulty=data.get("difficulty", 4))
        blockchain.chain = [Block.from_dict(b) for b in data["chain"]]
        blockchain.nodes = set(data.get("nodes", []))
        blockchain.recalculate_balances()
        return blockchain 