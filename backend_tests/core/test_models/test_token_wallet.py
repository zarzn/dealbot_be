"""Tests for the token wallet model."""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select
from decimal import Decimal

from core.models.token_wallet import TokenWallet, TokenTransaction, TransactionType
from core.models.user import User
from core.models.token_balance import TokenBalance
from core.models.token import Token
from core.models.enums import TokenStatus, TransactionStatus

@pytest.mark.asyncio
@pytest.mark.core
async def test_token_wallet_creation(db_session):
    """Test creating a token wallet in the database."""
    # Create a user
    user = User(
        email="wallet_test@example.com",
        username="walletuser",
        full_name="Wallet Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a token wallet
    wallet = TokenWallet(
        user_id=user.id,
        address="AjAq5XWVhZuGQZun9nYwjhErBWYjeGj6ZdPgxzJwrLCH",
        network="mainnet-beta",
        data={"test": True}
    )
    db_session.add(wallet)
    await db_session.commit()
    
    # Verify wallet was created
    result = await db_session.execute(select(TokenWallet).where(TokenWallet.user_id == user.id))
    fetched_wallet = result.scalars().first()
    
    assert fetched_wallet is not None
    assert fetched_wallet.address == "AjAq5XWVhZuGQZun9nYwjhErBWYjeGj6ZdPgxzJwrLCH"
    assert fetched_wallet.user_id == user.id
    assert fetched_wallet.network == "mainnet-beta"
    assert fetched_wallet.is_active is True
    assert fetched_wallet.data == {"test": True}

@pytest.mark.asyncio
@pytest.mark.core
async def test_token_wallet_relationships(db_session):
    """Test token wallet relationships."""
    # Create a user
    user = User(
        email="wallet_rel_test@example.com",
        username="walletreluser",
        full_name="Wallet Relation Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a token wallet
    wallet = TokenWallet(
        user_id=user.id,
        address="BjAq5XWVhZuGQZun9nYwjhErBWYjeGj6ZdPgxzJwrLCX",
        network="mainnet-beta"
    )
    db_session.add(wallet)
    await db_session.commit()
    
    # Create a transaction
    transaction = TokenTransaction(
        wallet_id=wallet.id,
        user_id=user.id,
        type=TransactionType.DEPOSIT.value.lower(),
        amount=100.5,
        status=TransactionStatus.COMPLETED.value.lower(),
        tx_hash="tx123456789",
        transaction_metadata={"source": "test"}
    )
    db_session.add(transaction)
    await db_session.commit()
    
    # Get wallet with transaction
    result = await db_session.execute(
        select(TokenWallet)
        .where(TokenWallet.id == wallet.id)
    )
    fetched_wallet = result.scalars().first()
    
    # Verify relationships
    assert fetched_wallet is not None
    assert fetched_wallet.user.id == user.id
    assert len(fetched_wallet.transactions) == 1
    assert fetched_wallet.transactions[0].type == TransactionType.DEPOSIT.value.lower()
    assert float(fetched_wallet.transactions[0].amount) == 100.5
    assert fetched_wallet.transactions[0].user_id == user.id

@pytest.mark.asyncio
@pytest.mark.core
async def test_token_wallet_update(db_session):
    """Test updating a token wallet."""
    # Create a user
    user = User(
        email="wallet_update@example.com",
        username="walletupdateuser",
        full_name="Wallet Update Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a token wallet
    wallet = TokenWallet(
        user_id=user.id,
        address="CjAq5XWVhZuGQZun9nYwjhErBWYjeGj6ZdPgxzJwrLCC",
        network="mainnet-beta",
        is_active=True
    )
    db_session.add(wallet)
    await db_session.commit()
    
    # Update wallet
    wallet.is_active = False
    wallet.network = "devnet"
    wallet.data = {"updated": True}
    await db_session.commit()
    
    # Verify update
    result = await db_session.execute(select(TokenWallet).where(TokenWallet.id == wallet.id))
    updated_wallet = result.scalars().first()
    
    assert updated_wallet is not None
    assert updated_wallet.is_active is False
    assert updated_wallet.network == "devnet"
    assert updated_wallet.data == {"updated": True}

@pytest.mark.asyncio
@pytest.mark.core
async def test_token_wallet_deletion(db_session):
    """Test deleting a token wallet."""
    # Create a user
    user = User(
        email="wallet_delete@example.com",
        username="walletdeleteuser",
        full_name="Wallet Delete Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a token wallet
    wallet = TokenWallet(
        user_id=user.id,
        address="DjAq5XWVhZuGQZun9nYwjhErBWYjeGj6ZdPgxzJwrLDD",
        network="mainnet-beta"
    )
    db_session.add(wallet)
    await db_session.commit()
    
    # Add a transaction
    transaction = TokenTransaction(
        wallet_id=wallet.id,
        user_id=user.id,
        type=TransactionType.TRANSFER.value.lower(),
        amount=50.25,
        status=TransactionStatus.COMPLETED.value.lower()
    )
    db_session.add(transaction)
    await db_session.commit()
    
    # Get the wallet ID for later verification
    wallet_id = wallet.id
    
    # Delete the wallet
    await db_session.delete(wallet)
    await db_session.commit()
    
    # Verify wallet is deleted
    result = await db_session.execute(select(TokenWallet).where(TokenWallet.id == wallet_id))
    deleted_wallet = result.scalars().first()
    assert deleted_wallet is None
    
    # Verify cascade delete of transaction
    result = await db_session.execute(select(TokenTransaction).where(TokenTransaction.wallet_id == wallet_id))
    deleted_transaction = result.scalars().first()
    assert deleted_transaction is None

@pytest.mark.asyncio
@pytest.mark.core
async def test_multiple_wallets_per_user(db_session):
    """Test that a user can have multiple wallets."""
    # Create a user
    user = User(
        email="multi_wallet@example.com",
        username="multiwalletuser",
        full_name="Multi Wallet Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create multiple wallets
    wallet1 = TokenWallet(
        user_id=user.id,
        address="EjAq5XWVhZuGQZun9nYwjhErBWYjeGj6ZdPgxzJwrLEE",
        network="mainnet-beta"
    )
    wallet2 = TokenWallet(
        user_id=user.id,
        address="FjAq5XWVhZuGQZun9nYwjhErBWYjeGj6ZdPgxzJwrLFF",
        network="devnet"
    )
    db_session.add(wallet1)
    db_session.add(wallet2)
    await db_session.commit()
    
    # Verify user has multiple wallets
    result = await db_session.execute(
        select(User)
        .where(User.id == user.id)
    )
    fetched_user = result.scalars().first()
    
    assert fetched_user is not None
    assert len(fetched_user.token_wallets) == 2
    assert any(wallet.network == "mainnet-beta" for wallet in fetched_user.token_wallets)
    assert any(wallet.network == "devnet" for wallet in fetched_user.token_wallets)

@pytest.mark.asyncio
@pytest.mark.core
async def test_wallet_transaction_status_update(db_session):
    """Test updating transaction status."""
    # Create a user
    user = User(
        email="tx_status@example.com",
        username="txstatususer",
        full_name="Transaction Status Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a token wallet
    wallet = TokenWallet(
        user_id=user.id,
        address="GjAq5XWVhZuGQZun9nYwjhErBWYjeGj6ZdPgxzJwrLGG",
        network="mainnet-beta"
    )
    db_session.add(wallet)
    await db_session.commit()
    
    # Create a transaction with pending status
    transaction = TokenTransaction(
        wallet_id=wallet.id,
        user_id=user.id,
        type=TransactionType.WITHDRAWAL.value.lower(),
        amount=75.0,
        status=TransactionStatus.PENDING.value.lower()
    )
    db_session.add(transaction)
    await db_session.commit()
    
    # Update transaction status
    transaction.status = TransactionStatus.COMPLETED.value.lower()
    transaction.tx_hash = "tx_completed_hash"
    transaction.completed_at = datetime.utcnow()
    await db_session.commit()
    
    # Verify status update
    result = await db_session.execute(select(TokenTransaction).where(TokenTransaction.id == transaction.id))
    updated_tx = result.scalars().first()
    
    assert updated_tx is not None
    assert updated_tx.status == TransactionStatus.COMPLETED.value.lower()
    assert updated_tx.tx_hash == "tx_completed_hash"
    assert updated_tx.completed_at is not None 
    assert devnet_wallets[0].address == "So1ana5555555555555555555555555555555555555" 