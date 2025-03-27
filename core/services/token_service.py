"""Token service for managing token operations.

This module provides functionality for managing token balances, transactions,
and interactions with the Solana blockchain.
"""

import asyncio
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, List, Optional, Any
from decimal import Decimal
import base58
from uuid import uuid4

# Try to import Solana-related packages, but don't fail if they're not available
try:
    from solana.rpc.async_api import AsyncClient
    from solana.transaction import Transaction
    from solders.pubkey import Pubkey
    from solders.system_program import TransferParams, transfer
    from solders.keypair import Keypair
    from solders.rpc.responses import GetLatestBlockhashResp
    SOLANA_AVAILABLE = True
except ImportError:
    # Create placeholder classes for type hints
    class AsyncClient: pass
    class Pubkey: 
        @staticmethod
        def from_string(s): return None
    class Keypair: pass
    class GetLatestBlockhashResp: pass
    SOLANA_AVAILABLE = False
    logging.getLogger(__name__).warning("Solana packages not available. Blockchain operations will be disabled.")

from core.config import settings
from core.models.user import User
from core.models.token_transaction import TokenTransaction
from core.models.token_balance import TokenBalance
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from core.database import get_session, AsyncSessionLocal
from core.exceptions import ResourceNotFoundError, TokenError

logger = logging.getLogger(__name__)

class TokenServiceV2:
    """Token service using only database operations."""
    
    def __init__(self):
        """Initialize TokenServiceV2."""
        self.search_cost = Decimal(str(settings.TOKEN_SEARCH_COST))
        self.required_balance = Decimal(str(settings.TOKEN_REQUIRED_BALANCE))
        self._session = None
        
    async def __aenter__(self):
        """Create session on context manager enter."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session on context manager exit."""
        pass
        
    async def get_balance(self, user_id: str) -> Decimal:
        """Get token balance for a user ID from the database.
        
        Args:
            user_id: User ID
            
        Returns:
            Token balance as Decimal
            
        Raises:
            TokenError: If user balance cannot be retrieved
        """
        try:
            # Create a new session for this operation
            async with AsyncSessionLocal() as session:
                # Try to get the balance from the database
                result = await session.execute(
                    select(TokenBalance).where(TokenBalance.user_id == user_id)
                )
                balance_record = result.scalar_one_or_none()
                
                if balance_record:
                    logger.info(f"Found balance for user {user_id} in database: {balance_record.balance}")
                    return balance_record.balance
                    
                # If no balance record exists, check if this is a valid user ID and create a record
                user_result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user:
                    # User exists but has no balance record, create one with zero balance
                    logger.info(f"Creating new balance record for user {user_id}")
                    balance_record = TokenBalance(user_id=user_id, balance=Decimal('0'))
                    session.add(balance_record)
                    await session.commit()
                    return Decimal('0')
                else:
                    # User does not exist
                    logger.error(f"User {user_id} not found")
                    raise ResourceNotFoundError(message=f"User {user_id} not found")
                    
        except ResourceNotFoundError:
            # Re-raise resource not found errors
            raise
        except Exception as e:
            logger.error(f"Failed to get balance for user {user_id}: {str(e)}")
            raise TokenError(message=f"Failed to get token balance: {str(e)}")
    
    async def validate_balance(self, user_id: str) -> bool:
        """Validate if user has required token balance.
        
        Args:
            user_id: User ID
            
        Returns:
            True if balance is sufficient, False otherwise
        """
        balance = await self.get_balance(user_id)
        return balance >= self.required_balance

    async def check_search_cost(self, user_id: str) -> None:
        """Check if user has sufficient balance for search operation.
        
        Args:
            user_id: User ID
            
        Raises:
            TokenError: If balance is insufficient for search
        """
        balance = await self.get_balance(user_id)
        if balance < self.search_cost:
            raise TokenError(
                message=f"Insufficient balance for search. Required: {self.search_cost}, Available: {balance}"
            )

    async def process_transaction(
        self,
        user_id: str,
        amount: Decimal,
        transaction_type: str,
        details: Optional[Dict[str, Any]] = None
    ) -> TokenTransaction:
        """Process a token transaction.
        
        Args:
            user_id: User ID
            amount: Transaction amount
            transaction_type: Transaction type (payment, refund, etc.)
            details: Additional transaction details
            
        Returns:
            Created TokenTransaction instance
            
        Raises:
            TokenError: If transaction processing fails
        """
        async with AsyncSessionLocal() as session:
            try:
                # Get user's current balance
                balance_query = select(TokenBalance).where(
                    TokenBalance.user_id == user_id
                )
                result = await session.execute(balance_query)
                balance = result.scalar_one_or_none()
                
                if not balance:
                    # Create initial balance record
                    balance = TokenBalance(
                        user_id=user_id,
                        balance=Decimal('0')
                    )
                    session.add(balance)
                
                # Create transaction record
                transaction = TokenTransaction(
                    user_id=user_id,
                    amount=amount,
                    type=transaction_type,
                    balance_before=balance.balance,
                    balance_after=balance.balance + amount,
                    details=details or {}
                )
                session.add(transaction)
                
                # Update balance
                balance.balance += amount
                
                await session.commit()
                return transaction

            except Exception as e:
                await session.rollback()
                raise TokenError(
                    message=f"Failed to process token transaction: {str(e)}"
                )

    async def deduct_search_cost(
        self,
        user_id: str,
        search_params: Dict[str, Any]
    ) -> TokenTransaction:
        """Deduct tokens for search operation.
        
        Args:
            user_id: User ID
            search_params: Search operation parameters
            
        Returns:
            Created TokenTransaction instance
        """
        return await self.process_transaction(
            user_id=user_id,
            amount=-self.search_cost,
            transaction_type="search_cost",
            details={"search_params": search_params}
        )

    async def refund_search_cost(
        self,
        user_id: str,
        transaction_id: str,
        reason: str
    ) -> TokenTransaction:
        """Refund tokens for failed search operation.
        
        Args:
            user_id: User ID
            transaction_id: Original transaction ID
            reason: Refund reason
            
        Returns:
            Created TokenTransaction instance
        """
        return await self.process_transaction(
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
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[TokenTransaction]:
        """Get user's token transaction history.
        
        Args:
            user_id: User ID
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip
            
        Returns:
            List of TokenTransaction instances
        """
        async with AsyncSessionLocal() as session:
            query = (
                select(TokenTransaction)
                .where(TokenTransaction.user_id == user_id)
                .order_by(TokenTransaction.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            result = await session.execute(query)
            return result.scalars().all()
    
    async def get_pricing_info(self, service_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get token pricing information.
        
        Args:
            service_type: Optional service type to filter pricing
            
        Returns:
            List of pricing information
        """
        # Mock pricing data - in a real implementation, this would come from a database
        pricing = [
            {
                "service_type": "search",
                "price": float(self.search_cost),
                "description": "Cost per search operation",
                "discounts": []
            },
            {
                "service_type": "goal",
                "price": 5.0,
                "description": "Cost to create a new goal",
                "discounts": []
            },
            {
                "service_type": "premium",
                "price": 100.0,
                "description": "Monthly premium subscription",
                "discounts": [
                    {"amount": 20, "description": "Annual subscription discount"}
                ]
            }
        ]
        
        if service_type:
            return [p for p in pricing if p["service_type"] == service_type]
        return pricing
    
    async def get_rewards(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        reward_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> List[Dict[str, Any]]:
        """Get token rewards for a user.
        
        Args:
            user_id: User ID
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            reward_type: Optional reward type for filtering
            page: Page number for pagination
            page_size: Items per page
            
        Returns:
            List of token rewards
        """
        async with AsyncSessionLocal() as session:
            # Build query to get reward transactions
            query = (
                select(TokenTransaction)
                .where(
                    TokenTransaction.user_id == user_id,
                    TokenTransaction.amount > 0,  # Rewards are positive amounts
                    TokenTransaction.type.in_(["reward", "referral", "achievement"])
                )
                .order_by(TokenTransaction.created_at.desc())
            )
            
            # Apply date filters if provided
            if start_date:
                query = query.where(TokenTransaction.created_at >= start_date)
            if end_date:
                query = query.where(TokenTransaction.created_at <= end_date)
            
            # Apply reward type filter if provided
            if reward_type:
                query = query.where(TokenTransaction.type == reward_type)
                
            # Apply pagination
            offset = (page - 1) * page_size
            query = query.limit(page_size).offset(offset)
            
            # Execute query
            result = await session.execute(query)
            transactions = result.scalars().all()
            
            # Convert to rewards format
            rewards = []
            for tx in transactions:
                rewards.append({
                    "id": str(tx.id),
                    "user_id": tx.user_id,
                    "amount": float(tx.amount),
                    "type": tx.type,
                    "description": tx.details.get("description", ""),
                    "awarded_at": tx.created_at,
                    "details": tx.details
                })
                
            return rewards
    
    async def burn_tokens(
        self,
        user_id: str,
        amount: Decimal,
        reason: str
    ) -> Dict[str, Any]:
        """Burn tokens from a user's balance.
        
        Args:
            user_id: User ID
            amount: Amount to burn
            reason: Reason for burning tokens
            
        Returns:
            Transaction details
        """
        # Check if user has sufficient balance
        balance = await self.get_balance(user_id)
        if balance < amount:
            raise TokenError(
                message=f"Insufficient balance for burn. Required: {amount}, Available: {balance}"
            )
            
        # Process burn transaction
        tx = await self.process_transaction(
            user_id=user_id,
            amount=-amount,  # Negative amount for burning
            transaction_type="burn",
            details={"reason": reason}
        )
        
        return {
            "status": "success",
            "transaction_id": str(tx.id),
            "amount": float(amount),
            "new_balance": float(balance - amount)
        }
    
    async def stake_tokens(
        self,
        user_id: str,
        amount: Decimal,
        duration: int
    ) -> Dict[str, Any]:
        """Stake tokens for rewards.
        
        Args:
            user_id: User ID
            amount: Amount to stake
            duration: Duration in days
            
        Returns:
            Stake details
        """
        # Check if user has sufficient balance
        balance = await self.get_balance(user_id)
        if balance < amount:
            raise TokenError(
                message=f"Insufficient balance for staking. Required: {amount}, Available: {balance}"
            )
            
        # Calculate end date
        stake_start = datetime.utcnow()
        stake_end = stake_start + timedelta(days=duration)
        
        # Calculate reward rate based on duration
        reward_rate = 0.05  # Default 5%
        if duration > 30:
            reward_rate = 0.08  # 8% for 30+ days
        if duration > 90:
            reward_rate = 0.12  # 12% for 90+ days
            
        # Process stake transaction
        tx = await self.process_transaction(
            user_id=user_id,
            amount=-amount,  # Deduct tokens for staking
            transaction_type="stake",
            details={
                "stake_id": str(uuid4()),
                "duration": duration,
                "stake_start": stake_start.isoformat(),
                "stake_end": stake_end.isoformat(),
                "reward_rate": reward_rate,
                "status": "active"
            }
        )
        
        return {
            "stake_id": tx.details["stake_id"],
            "amount": float(amount),
            "duration": duration,
            "stake_start": stake_start.isoformat(),
            "stake_end": stake_end.isoformat(),
            "reward_rate": reward_rate,
            "estimated_reward": float(amount * reward_rate),
            "transaction_id": str(tx.id)
        }
    
    async def get_stake_info(self, user_id: str) -> Dict[str, Any]:
        """Get staking information for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Staking information
        """
        async with AsyncSessionLocal() as session:
            # Query for active stake transactions
            query = (
                select(TokenTransaction)
                .where(
                    TokenTransaction.user_id == user_id,
                    TokenTransaction.type == "stake"
                )
                .order_by(TokenTransaction.created_at.desc())
            )
            
            result = await session.execute(query)
            transactions = result.scalars().all()
            
            # Filter for active stakes and format response
            active_stakes = []
            completed_stakes = []
            
            for tx in transactions:
                stake_data = tx.details.copy()
                stake_data["transaction_id"] = str(tx.id)
                stake_data["amount"] = abs(float(tx.amount))
                
                if stake_data.get("status") == "active":
                    active_stakes.append(stake_data)
                else:
                    completed_stakes.append(stake_data)
            
            return {
                "user_id": user_id,
                "active_stakes": active_stakes,
                "completed_stakes": completed_stakes,
                "total_staked": sum(stake["amount"] for stake in active_stakes),
                "total_rewards_earned": sum(stake.get("reward_paid", 0) for stake in completed_stakes)
            }
    
    async def unstake_tokens(
        self,
        user_id: str,
        stake_id: str
    ) -> Dict[str, Any]:
        """Unstake tokens and claim rewards.
        
        Args:
            user_id: User ID
            stake_id: Stake ID
            
        Returns:
            Unstake details
        """
        # Find the stake transaction
        async with AsyncSessionLocal() as session:
            stake_query = (
                select(TokenTransaction)
                .where(
                    TokenTransaction.user_id == user_id,
                    TokenTransaction.type == "stake",
                    TokenTransaction.meta_data.contains({"stake_id": stake_id})
                )
            )
            
            result = await session.execute(stake_query)
            stake_tx = result.scalar_one_or_none()
            
            if not stake_tx:
                raise TokenError(message=f"Stake not found: {stake_id}")
                
            # Check if stake is active
            if stake_tx.details.get("status") != "active":
                raise TokenError(message=f"Stake is not active: {stake_id}")
                
            # Calculate reward
            stake_amount = abs(stake_tx.amount)
            reward_rate = stake_tx.details.get("reward_rate", 0.05)
            reward_amount = stake_amount * Decimal(str(reward_rate))
            
            # Update stake transaction to mark as completed
            stake_details = stake_tx.details.copy()
            stake_details["status"] = "completed"
            stake_details["unstake_date"] = datetime.utcnow().isoformat()
            stake_details["reward_paid"] = float(reward_amount)
            
            stake_tx.details = stake_details
            
            # Process refund of staked tokens
            refund_tx = TokenTransaction(
                user_id=user_id,
                amount=stake_amount,
                type="unstake",
                details={
                    "stake_id": stake_id,
                    "original_transaction_id": str(stake_tx.id)
                }
            )
            session.add(refund_tx)
            
            # Process reward payment
            reward_tx = TokenTransaction(
                user_id=user_id,
                amount=reward_amount,
                type="stake_reward",
                details={
                    "stake_id": stake_id,
                    "original_transaction_id": str(stake_tx.id),
                    "reward_rate": reward_rate
                }
            )
            session.add(reward_tx)
            
            # Update user balance
            balance_query = select(TokenBalance).where(TokenBalance.user_id == user_id)
            balance_result = await session.execute(balance_query)
            balance = balance_result.scalar_one_or_none()
            
            if balance:
                # Update with both the refund and reward
                balance.balance += (stake_amount + reward_amount)
                
            await session.commit()
            
            return {
                "status": "success",
                "stake_id": stake_id,
                "unstaked_amount": float(stake_amount),
                "reward_amount": float(reward_amount),
                "total_amount": float(stake_amount + reward_amount),
                "unstake_transaction_id": str(refund_tx.id),
                "reward_transaction_id": str(reward_tx.id)
            }


class TokenService:
    """Legacy token service with blockchain support.
    
    This class is maintained for backward compatibility.
    New code should use TokenServiceV2.
    """
    
    def __init__(
        self,
        db: AsyncSession = None,
        rpc_url: str = settings.SOL_NETWORK_RPC,
        token_address: str = settings.TOKEN_CONTRACT_ADDRESS,
        required_balance: Decimal = settings.TOKEN_REQUIRED_BALANCE,
        search_cost: Decimal = settings.TOKEN_SEARCH_COST
    ):
        """Initialize the token service.
        
        Args:
            db: Database session
            rpc_url: Solana RPC endpoint URL
            token_address: Token contract address
            required_balance: Minimum required token balance
            search_cost: Token cost per search
        """
        self.db = db
        self.rpc_url = rpc_url
        self.token_address = token_address
        self.required_balance = Decimal(str(required_balance))
        self.search_cost = Decimal(str(search_cost))
        self.client: Optional[AsyncClient] = None

    async def __aenter__(self):
        """Create Solana client on context manager enter."""
        # No longer create Solana client, just return self
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close Solana client on context manager exit."""
        # No need to close anything
        pass

    async def get_balance(self, wallet_address_or_user_id: str) -> Decimal:
        """Get token balance for a wallet address or user ID.
        
        Args:
            wallet_address_or_user_id: User ID or wallet address
            
        Returns:
            Token balance as Decimal
            
        Raises:
            Exception: If connection fails or wallet/user is invalid
        """
        # Always use database first
        try:
            # Use the appropriate session handling approach
            _temp_session = False  # Initialize to prevent potential reference error
            if self.db:
                session = self.db
            else:
                # Create a new temporary session
                _temp_session = True
                session = AsyncSessionLocal()
                
            try:
                # Try to get the balance from the database
                result = await session.execute(
                    select(TokenBalance).where(TokenBalance.user_id == wallet_address_or_user_id)
                )
                balance_record = result.scalar_one_or_none()
                
                if balance_record:
                    logger.info(f"Found balance for user {wallet_address_or_user_id} in database: {balance_record.balance}")
                    return balance_record.balance
                    
                # If no balance record exists, check if this is a valid user ID and create a record
                user_result = await session.execute(
                    select(User).where(User.id == wallet_address_or_user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user:
                    # User exists but has no balance record, create one with zero balance
                    logger.info(f"Creating new balance record for user {wallet_address_or_user_id}")
                    balance_record = TokenBalance(user_id=wallet_address_or_user_id, balance=Decimal('0'))
                    session.add(balance_record)
                    await session.commit()
                    return Decimal('0')
            finally:
                # Close temporary session if we created one
                if not self.db and _temp_session:
                    await session.close()
                    
        except Exception as e:
            logger.warning(f"Failed to get balance from database: {str(e)}")
            # We no longer fall back to blockchain checks
            raise TokenError(message=f"Failed to get token balance: {str(e)}")

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
