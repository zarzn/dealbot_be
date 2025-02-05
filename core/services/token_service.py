"""Token service for managing token operations.

This module provides functionality for managing token balances, transactions,
and interactions with the Solana blockchain.
"""

import asyncio
from datetime import datetime
import json
import logging
from typing import Dict, List, Optional, Any
from decimal import Decimal
import base58
from solana.rpc.async_api import AsyncClient
from solana.transaction import Transaction
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.keypair import Keypair
from solders.rpc.responses import GetLatestBlockhashResp

""" from core.exceptions import (
    SolanaError,
    SolanaTransactionError,
    SolanaConnectionError,
    InsufficientTokensError,
    TokenValidationError,
    TokenError,
    TokenTransactionError,
    TokenBalanceError,
    DatabaseError,
    ValidationError,
    NetworkError,
    CacheOperationError,
    APIError,
    APIServiceUnavailableError
) 
DO NOT DELETE THIS COMMENT
"""
from core.config import settings
from core.models.user import User
from core.models.token_transaction import TokenTransaction
from core.models.token_balance import TokenBalance
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)

class TokenService:
    """Service for managing token operations."""
    
    def __init__(
        self,
        rpc_url: str = settings.SOL_NETWORK_RPC,
        token_address: str = settings.TOKEN_CONTRACT_ADDRESS,
        required_balance: Decimal = settings.TOKEN_REQUIRED_BALANCE,
        search_cost: Decimal = settings.TOKEN_SEARCH_COST
    ):
        """Initialize the token service.
        
        Args:
            rpc_url: Solana RPC endpoint URL
            token_address: Token contract address
            required_balance: Minimum required token balance
            search_cost: Token cost per search
        """
        self.rpc_url = rpc_url
        self.token_address = Pubkey.from_string(token_address)
        self.required_balance = Decimal(str(required_balance))
        self.search_cost = Decimal(str(search_cost))
        self.client: Optional[AsyncClient] = None

    async def __aenter__(self):
        """Create Solana client on context manager enter."""
        if not self.client:
            try:
                self.client = AsyncClient(self.rpc_url)
                # Test connection
                await self.client.is_connected()
            except Exception as e:
                raise Exception(
                    f"Failed to connect to Solana network: {str(e)}"
                )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close Solana client on context manager exit."""
        if self.client:
            await self.client.close()
            self.client = None

    async def get_balance(self, wallet_address: str) -> Decimal:
        """Get token balance for a wallet address.
        
        Args:
            wallet_address: Solana wallet address
            
        Returns:
            Token balance as Decimal
            
        Raises:
            Exception: If connection fails or wallet is invalid
        """
        if not self.client:
            raise RuntimeError("TokenService must be used as a context manager")

        try:
            pubkey = Pubkey.from_string(wallet_address)
            response = await self.client.get_token_account_balance(pubkey)
            
            if "result" not in response or "value" not in response["result"]:
                raise Exception(
                    f"Invalid response from Solana network for wallet {wallet_address}"
                )
                
            amount = response["result"]["value"]["amount"]
            decimals = response["result"]["value"]["decimals"]
            
            return Decimal(amount) / Decimal(10 ** decimals)

        except ValueError:
            raise Exception(f"Invalid wallet address: {wallet_address}")
        except Exception as e:
            raise Exception(
                f"Failed to get token balance for wallet {wallet_address}: {str(e)}"
            )

    async def validate_balance(self, wallet_address: str) -> bool:
        """Validate if wallet has required token balance.
        
        Args:
            wallet_address: Solana wallet address
            
        Returns:
            True if balance is sufficient, False otherwise
        """
        balance = await self.get_balance(wallet_address)
        return balance >= self.required_balance

    async def check_search_cost(self, wallet_address: str) -> None:
        """Check if wallet has sufficient balance for search operation.
        
        Args:
            wallet_address: Solana wallet address
            
        Raises:
            Exception: If balance is insufficient for search
        """
        balance = await self.get_balance(wallet_address)
        if balance < self.search_cost:
            raise Exception(
                f"Insufficient balance for search. Required: {self.search_cost}, Available: {balance}"
            )

    async def process_transaction(
        self,
        db: AsyncSession,
        user_id: str,
        amount: Decimal,
        transaction_type: str,
        details: Optional[Dict[str, Any]] = None
    ) -> TokenTransaction:
        """Process a token transaction.
        
        Args:
            db: Database session
            user_id: User ID
            amount: Transaction amount
            transaction_type: Transaction type (payment, refund, etc.)
            details: Additional transaction details
            
        Returns:
            Created TokenTransaction instance
            
        Raises:
            Exception: If transaction processing fails
        """
        try:
            # Get user's current balance
            balance_query = select(TokenBalance).where(
                TokenBalance.user_id == user_id
            )
            result = await db.execute(balance_query)
            balance = result.scalar_one_or_none()
            
            if not balance:
                # Create initial balance record
                balance = TokenBalance(
                    user_id=user_id,
                    balance=Decimal('0')
                )
                db.add(balance)
            
            # Create transaction record
            transaction = TokenTransaction(
                user_id=user_id,
                amount=amount,
                type=transaction_type,
                balance_before=balance.balance,
                balance_after=balance.balance + amount,
                details=details or {}
            )
            db.add(transaction)
            
            # Update balance
            balance.balance += amount
            
            await db.commit()
            return transaction

        except Exception as e:
            await db.rollback()
            raise Exception(
                f"Failed to process token transaction: {str(e)}"
            )

    async def deduct_search_cost(
        self,
        db: AsyncSession,
        user_id: str,
        search_params: Dict[str, Any]
    ) -> TokenTransaction:
        """Deduct tokens for search operation.
        
        Args:
            db: Database session
            user_id: User ID
            search_params: Search operation parameters
            
        Returns:
            Created TokenTransaction instance
        """
        return await self.process_transaction(
            db=db,
            user_id=user_id,
            amount=-self.search_cost,
            transaction_type="search_cost",
            details={"search_params": search_params}
        )

    async def refund_search_cost(
        self,
        db: AsyncSession,
        user_id: str,
        transaction_id: str,
        reason: str
    ) -> TokenTransaction:
        """Refund tokens for failed search operation.
        
        Args:
            db: Database session
            user_id: User ID
            transaction_id: Original transaction ID
            reason: Refund reason
            
        Returns:
            Created TokenTransaction instance
        """
        return await self.process_transaction(
            db=db,
            user_id=user_id,
            amount=self.search_cost,
            transaction_type="search_refund",
            details={
                "original_transaction": transaction_id,
                "reason": reason
            }
        )

    async def get_transaction_history(
        self,
        db: AsyncSession,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[TokenTransaction]:
        """Get user's token transaction history.
        
        Args:
            db: Database session
            user_id: User ID
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip
            
        Returns:
            List of TokenTransaction instances
        """
        query = (
            select(TokenTransaction)
            .where(TokenTransaction.user_id == user_id)
            .order_by(TokenTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        
        result = await db.execute(query)
        return result.scalars().all()

    async def transfer_tokens(
        self,
        from_wallet: str,
        to_wallet: str,
        amount: Decimal,
        private_key: bytes
    ) -> str:
        """Transfer tokens between wallets.
        
        Args:
            from_wallet: Sender's wallet address
            to_wallet: Recipient's wallet address
            amount: Amount to transfer
            private_key: Sender's private key
            
        Returns:
            Transaction signature
            
        Raises:
            Exception: If transfer fails
        """
        if not self.client:
            raise RuntimeError("TokenService must be used as a context manager")

        try:
            # Convert addresses to Pubkey
            from_pubkey = Pubkey.from_string(from_wallet)
            to_pubkey = Pubkey.from_string(to_wallet)
            
            # Create keypair from private key
            keypair = Keypair.from_bytes(private_key)
            
            # Get recent blockhash
            recent_blockhash: GetLatestBlockhashResp = await self.client.get_latest_blockhash()
            
            # Create transfer instruction
            lamports = int(amount * Decimal(10 ** 9))  # Convert to lamports
            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=from_pubkey,
                    to_pubkey=to_pubkey,
                    lamports=lamports
                )
            )
            
            # Create and sign transaction
            transaction = Transaction().add(transfer_ix)
            transaction.recent_blockhash = recent_blockhash.value.blockhash
            transaction.sign(keypair)
            
            # Send transaction
            result = await self.client.send_transaction(
                transaction,
                keypair,
                opts={"skip_preflight": True}
            )
            
            if "result" not in result:
                raise Exception("Failed to get transaction result")
                
            return result["result"]

        except Exception as e:
            raise Exception(f"Failed to transfer tokens: {str(e)}") 
