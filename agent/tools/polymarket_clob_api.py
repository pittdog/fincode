"""Polymarket CLOB API client for detailed market data and trade execution."""
import os
import logging
from typing import List, Dict, Any, Optional
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, TradeParams
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CLOBOrderBook:
    """Detailed order book from CLOB."""
    market_id: str
    bids: List[Dict[str, Any]]
    asks: List[Dict[str, Any]]
    best_bid: float
    best_ask: float
    mid_price: float
    spread: float
    market_question: Optional[str] = None

class PolymarketCLOBClient:
    """Level 2 client for interacting with Polymarket CLOB."""

    def __init__(
        self, 
        host: str = "https://clob.polymarket.com",
        key: Optional[str] = None,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        chain_id: int = 137
    ):
        """Initialize CLOB client.
        
        Args:
            host: CLOB host URL
            key: Wallet private key for authentication
            api_key: Polymarket API Key
            secret: Polymarket API Secret
            passphrase: Polymarket API Passphrase
            chain_id: Polygon chain ID (137)
        """
        self.host = host
        self.key = key or os.getenv("POLYMARKET_PRIVATE_KEY")
        self.api_key = api_key or os.getenv("POLYMARKET_API_KEY")
        self.secret = secret or os.getenv("POLYMARKET_SECRET")
        self.passphrase = passphrase or os.getenv("POLYMARKET_PASSPHRASE")
        self.chain_id = chain_id
        
        creds = None
        if self.api_key and self.secret and self.passphrase:
             creds = ApiCreds(
                 api_key=self.api_key,
                 api_secret=self.secret,
                 api_passphrase=self.passphrase
             )
        
        self.client = ClobClient(
            host=self.host,
            key=self.key,
            creds=creds,
            chain_id=self.chain_id
        )

    async def get_markets(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch all markets from CLOB."""
        try:
            # Note: py-clob-client is mostly synchronous in its current version
            # or uses it internal session. We wrap it for consistency.
            data = self.client.get_markets()
            return data[:limit] if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Error fetching CLOB markets: {e}")
            return []

    async def get_order_book(self, token_id: str, question: Optional[str] = None) -> Optional[CLOBOrderBook]:
        """Fetch detailed order book from CLOB.
        
        Args:
            token_id: The token/market asset ID
            question: Optional market question/name
        """
        try:
            data = self.client.get_order_book(token_id)
            
            bids = data.bids if hasattr(data, 'bids') else data.get("bids", [])
            asks = data.asks if hasattr(data, 'asks') else data.get("asks", [])
            
            best_bid = float(bids[0].price) if bids else 0.0
            best_ask = float(asks[0].price) if asks else 1.0
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            
            return CLOBOrderBook(
                market_id=token_id,
                bids=[{"price": float(b.price), "size": float(b.size)} for b in bids],
                asks=[{"price": float(a.price), "size": float(a.size)} for a in asks],
                best_bid=best_bid,
                best_ask=best_ask,
                mid_price=mid_price,
                spread=spread,
                market_question=question
            )
        except Exception as e:
            logger.error(f"Error fetching CLOB order book for {token_id}: {e}")
            return None

    async def get_trades(self, token_id: str) -> List[Dict[str, Any]]:
        """Fetch recent trades for a market."""
        try:
            return self.client.get_trades(token_id)
        except Exception as e:
            logger.error(f"Error fetching CLOB trades for {token_id}: {e}")
            return []

    async def get_historical_trades(self, token_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch historical trades for a market using CLOB API."""
        try:
            # The token_id from Gamma clobTokenIds is usually the asset_id
            params = TradeParams(asset_id=token_id)
            return self.client.get_trades(params)
        except Exception as e:
            logger.error(f"Error fetching historical trades for {token_id}: {e}")
            return []

    def derive_api_creds(self):
        """Derive or create API credentials."""
        return self.client.create_or_derive_api_creds()
