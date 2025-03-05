"""Tests for the token wallet model."""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select
from decimal import Decimal

from core.models.token_wallet import TokenWallet, WalletTransaction
from core.models.user import User
from core.models.token_balance import TokenBalance
from core.models.token import Token
from core.models.enums import TokenStatus, TransactionStatus, TransactionType

@pytest.mark.asyncio
@pytest.mark.core
async def test_token_wallet_creation(db_session):
    """Test creating a token wallet in the database."""
    # Create a user
    user = User(
        email="wallet_test@example.com",
        name="Wallet Test User",
        password="hashed_password_value",
        status="active"
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
        name="Wallet Relation Test User",
        password="hashed_password_value",
        status="active"
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
    transaction = WalletTransaction(
        wallet_id=wallet.id,
        user_id=user.id,
        type=TransactionType.REWARD.value.lower(),
        amount=100.5,
        status=TransactionStatus.COMPLETED.value.lower(),
        tx_hash="tx123456789",
        transaction_metadata={"source": "test"}
    )
    db_session.add(transaction)
    await db_session.commit()
    
    # Get wallet with transaction
    result = await db_session.execute(
        select(TokenWallet).where(TokenWallet.id == wallet.id)
    )
    fetched_wallet = result.scalar_one()
    
    # Get transactions separately to avoid async issues
    result = await db_session.execute(
        select(WalletTransaction).where(WalletTransaction.wallet_id == wallet.id)
    )
    transactions = result.scalars().all()
    
    # Verify relationships
    assert fetched_wallet is not None
    assert len(transactions) == 1
    assert transactions[0].wallet_id == wallet.id
    assert transactions[0].user_id == user.id
    assert transactions[0].type == TransactionType.REWARD.value.lower()
    assert transactions[0].amount == 100.5
    
    # Get user and verify relationship
    result = await db_session.execute(
        select(User).where(User.id == user.id)
    )
    fetched_user = result.scalar_one()
    
    # Get user's wallets separately
    result = await db_session.execute(
        select(TokenWallet).where(TokenWallet.user_id == user.id)
    )
    user_wallets = result.scalars().all()
    
    assert len(user_wallets) == 1
    assert user_wallets[0].id == wallet.id

@pytest.mark.asyncio
@pytest.mark.core
async def test_token_wallet_update(db_session):
    """Test updating a token wallet."""
    # Create a user
    user = User(
        email="wallet_update@example.com",
        name="Wallet Update Test User",
        password="hashed_password_value",
        status="active"
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a token wallet
    wallet = TokenWallet(
        user_id=user.id,
        address="CjAq5XWVhZuGQZun9nYwjhErBWYjeGj6ZdPgxzJwrLCY",
        network="mainnet-beta"
    )
    db_session.add(wallet)
    await db_session.commit()
    
    # Update the wallet
    wallet.address = "UpdatedAddress"
    wallet.is_active = False
    wallet.data = {"updated": True}
    await db_session.commit()
    
    # Verify updated wallet
    result = await db_session.execute(select(TokenWallet).where(TokenWallet.id == wallet.id))
    fetched_wallet = result.scalars().first()
    
    assert fetched_wallet is not None
    assert fetched_wallet.address == "UpdatedAddress"
    assert fetched_wallet.is_active is False
    assert fetched_wallet.data == {"updated": True}

@pytest.mark.asyncio
@pytest.mark.core
async def test_token_wallet_deletion(db_session):
    """Test deleting a token wallet."""
    # Create a user
    user = User(
        email="wallet_delete@example.com",
        name="Wallet Delete Test User",
        password="hashed_password_value",
        status="active"
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a token wallet
    wallet = TokenWallet(
        user_id=user.id,
        address="DjAq5XWVhZuGQZun9nYwjhErBWYjeGj6ZdPgxzJwrLCZ",
        network="mainnet-beta"
    )
    db_session.add(wallet)
    await db_session.commit()
    
    # Delete the wallet
    await db_session.delete(wallet)
    await db_session.commit()
    
    # Verify wallet is deleted
    result = await db_session.execute(select(TokenWallet).where(TokenWallet.id == wallet.id))
    deleted_wallet = result.scalars().first()
    
    assert deleted_wallet is None

@pytest.mark.asyncio
@pytest.mark.core
async def test_multiple_wallets_per_user(db_session):
    """Test creating multiple wallets for a single user."""
    # Create a user
    user = User(
        email="multi_wallet@example.com",
        name="Multi Wallet Test User",
        password="hashed_password_value",
        status="active"
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create wallet 1
    wallet1 = TokenWallet(
        user_id=user.id,
        address="Wallet1Address",
        network="mainnet-beta"
    )
    
    # Create wallet 2
    wallet2 = TokenWallet(
        user_id=user.id,
        address="Wallet2Address",
        network="testnet"
    )
    
    db_session.add_all([wallet1, wallet2])
    await db_session.commit()
    
    # Verify user has multiple wallets
    result = await db_session.execute(select(TokenWallet).where(TokenWallet.user_id == user.id))
    wallets = result.scalars().all()
    
    assert len(wallets) == 2
    addresses = [w.address for w in wallets]
    assert "Wallet1Address" in addresses
    assert "Wallet2Address" in addresses

@pytest.mark.asyncio
@pytest.mark.core
async def test_wallet_transaction_status_update(db_session):
    """Test updating transaction status."""
    # Create a user
    user = User(
        email="tx_status@example.com",
        name="Transaction Status Test User",
        password="hashed_password_value",
        status="active"
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a token wallet
    wallet = TokenWallet(
        user_id=user.id,
        address="TxStatusWalletAddress",
        network="mainnet-beta"
    )
    db_session.add(wallet)
    await db_session.commit()
    
    # Create a transaction with pending status
    transaction = WalletTransaction(
        wallet_id=wallet.id,
        user_id=user.id,
        type=TransactionType.DEDUCTION.value.lower(),
        amount=50.0,
        status=TransactionStatus.PENDING.value.lower(),
        tx_hash="tx_status_test"
    )
    db_session.add(transaction)
    await db_session.commit()
    
    # Update transaction status to completed
    transaction.status = TransactionStatus.COMPLETED.value.lower()
    transaction.updated_at = datetime.now()
    await db_session.commit()
    
    # Verify status was updated
    result = await db_session.execute(select(WalletTransaction).where(WalletTransaction.id == transaction.id))
    updated_tx = result.scalars().first()
    
    assert updated_tx is not None
    assert updated_tx.status == TransactionStatus.COMPLETED.value.lower() 