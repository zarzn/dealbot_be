# Token Wallet System

## Overview

The Token Wallet System is a critical component of the AI Agentic Deals System that manages user token balances, transactions, and wallet connections. This document provides comprehensive details about the wallet architecture, data models, API endpoints, and integration patterns.

## Architecture

The Token Wallet System consists of the following components:

1. **Wallet Models**: Database models for storing wallet information and transactions
2. **Wallet Service**: Business logic for wallet operations
3. **Wallet API**: REST endpoints for wallet management
4. **Wallet Integration**: Connection to blockchain networks
5. **Transaction Processing**: Handling token transfers and balance updates
6. **Security Layer**: Protecting wallet operations and sensitive data

### System Flow

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  User/API   │─────▶│    Wallet   │─────▶│   Service   │─────▶│  Database   │
│   Request   │      │  Controller │      │    Layer    │      │    Models   │
└─────────────┘      └─────────────┘      └─────────────┘      └─────────────┘
                           │                     │                     ▲
                           │                     ▼                     │
                           │               ┌─────────────┐             │
                           └──────────────▶│ Blockchain  │─────────────┘
                                           │ Integration │
                                           └─────────────┘
```

The system follows a layered approach where API requests go through controllers, service layer, and models, with blockchain integration for external wallet connections.

## Data Models

### TokenWallet Model

The `TokenWallet` model represents a user's wallet in the system:

```python
class TokenWallet(SQLModelBase):
    __tablename__ = "token_wallets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    address: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    network: Mapped[str] = mapped_column(String(50), default="solana")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="wallets")
    transactions: Mapped[List["WalletTransaction"]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan"
    )
```

### WalletTransaction Model

The `WalletTransaction` model tracks all token movements:

```python
class WalletTransaction(SQLModelBase):
    __tablename__ = "wallet_transactions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    wallet_id: Mapped[UUID] = mapped_column(ForeignKey("token_wallets.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(
        SQLAlchemyEnum(
            TransactionType, values_callable=lambda x: [e.value.lower() for e in x]
        )
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=6))
    status: Mapped[str] = mapped_column(
        SQLAlchemyEnum(
            TransactionStatus, values_callable=lambda x: [e.value.lower() for e in x]
        ),
        default=TransactionStatus.PENDING.value,
    )
    tx_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, onupdate=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Relationships
    wallet: Mapped["TokenWallet"] = relationship(back_populates="transactions")
    user: Mapped["User"] = relationship(back_populates="transactions")
```

### Schema Models

In addition to the database models, the system uses Pydantic schemas:

```python
class TokenWalletCreate(BaseModel):
    user_id: UUID
    address: Optional[str] = None
    network: str = "solana"

class TokenWalletUpdate(BaseModel):
    address: Optional[str] = None
    is_active: Optional[bool] = None
    network: Optional[str] = None
    data: Optional[dict] = None

class TokenWalletResponse(BaseModel):
    id: UUID
    user_id: UUID
    address: Optional[str]
    balance: Decimal
    is_active: bool
    network: str
    created_at: datetime
    last_used: Optional[datetime]
```

## Service Layer

The `WalletService` handles business logic for wallet operations:

```python
class WalletService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.blockchain_client = BlockchainClient()

    async def get_wallet(self, user_id: UUID) -> Optional[TokenWallet]:
        """Get user's active wallet."""
        stmt = select(TokenWallet).where(
            TokenWallet.user_id == user_id,
            TokenWallet.is_active == True
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_wallet(self, wallet_data: TokenWalletCreate) -> TokenWallet:
        """Create a new wallet for user."""
        wallet = TokenWallet(**wallet_data.dict())
        self.db.add(wallet)
        await self.db.commit()
        await self.db.refresh(wallet)
        return wallet

    async def connect_external_wallet(
        self,
        user_id: UUID,
        wallet_address: str,
        signature: str
    ) -> bool:
        """Connect external blockchain wallet."""
        # Verify signature
        is_valid = await self.blockchain_client.verify_wallet_signature(
            wallet_address, signature
        )
        if not is_valid:
            raise InvalidSignatureError()
        
        # Check if wallet is already connected
        existing = await self.get_wallet_by_address(wallet_address)
        if existing:
            raise WalletAlreadyConnectedError()
        
        # Create wallet connection
        wallet_data = TokenWalletCreate(
            user_id=user_id,
            address=wallet_address,
            network="solana"
        )
        await self.create_wallet(wallet_data)
        return True

    async def get_balance(self, user_id: UUID) -> Decimal:
        """Get user's token balance."""
        wallet = await self.get_wallet(user_id)
        if not wallet:
            return Decimal('0')
        
        # Get on-chain balance if external wallet
        if wallet.address:
            return await self.blockchain_client.get_token_balance(wallet.address)
        
        # Get internal balance
        stmt = select(func.sum(WalletTransaction.amount)).where(
            WalletTransaction.user_id == user_id,
            WalletTransaction.status == TransactionStatus.COMPLETED.value
        )
        result = await self.db.execute(stmt)
        balance = result.scalar_one_or_none() or Decimal('0')
        return balance

    async def record_transaction(
        self,
        user_id: UUID,
        transaction_type: TransactionType,
        amount: Decimal,
        tx_hash: Optional[str] = None
    ) -> WalletTransaction:
        """Record a wallet transaction."""
        wallet = await self.get_wallet(user_id)
        if not wallet:
            raise WalletNotFoundError()
        
        transaction = WalletTransaction(
            wallet_id=wallet.id,
            user_id=user_id,
            type=transaction_type.value,
            amount=amount,
            status=TransactionStatus.PENDING.value,
            tx_hash=tx_hash
        )
        self.db.add(transaction)
        await self.db.commit()
        
        # Process transaction
        await self.process_transaction(transaction.id)
        
        return transaction
```

## API Endpoints

The wallet system exposes the following REST endpoints:

### Get User Wallet

```
GET /api/wallet
```

Returns the user's current wallet information, including balance and transaction history.

**Response Example:**
```json
{
  "wallet": {
    "id": "f8c3de3d-1fea-4d7c-a8b0-29f63c4c3454",
    "balance": "240.50",
    "address": "sol:9iD1Z5aU5MBzuuJALVgP1vzL3oLjZog5zaSNLNHPeGP1",
    "is_connected": true,
    "network": "solana",
    "created_at": "2024-01-15T10:30:45Z"
  },
  "transaction_history": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "type": "deposit",
      "amount": "100.00",
      "status": "completed",
      "timestamp": "2024-01-20T14:22:33Z"
    },
    {
      "id": "b2c3d4e5-f6g7-8901-bcde-fg2345678901",
      "type": "service_fee",
      "amount": "-10.50",
      "status": "completed",
      "timestamp": "2024-01-25T09:11:22Z"
    }
  ]
}
```

### Connect External Wallet

```
POST /api/wallet/connect
```

Connects an external blockchain wallet to the user's account.

**Request Body:**
```json
{
  "wallet_address": "sol:9iD1Z5aU5MBzuuJALVgP1vzL3oLjZog5zaSNLNHPeGP1",
  "signature": "base64_encoded_signature_data"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Wallet connected successfully",
  "wallet_id": "f8c3de3d-1fea-4d7c-a8b0-29f63c4c3454"
}
```

### Disconnect Wallet

```
POST /api/wallet/disconnect
```

Disconnects an external wallet from the user's account.

**Request Body:**
```json
{
  "wallet_id": "f8c3de3d-1fea-4d7c-a8b0-29f63c4c3454"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Wallet disconnected successfully"
}
```

### Transfer Tokens

```
POST /api/wallet/transfer
```

Transfers tokens from the user's wallet to another user or service.

**Request Body:**
```json
{
  "recipient_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "amount": "25.75",
  "note": "Payment for shared deal"
}
```

**Response:**
```json
{
  "success": true,
  "transaction_id": "c3d4e5f6-g7h8-9012-cdef-gh3456789012",
  "status": "completed",
  "balance_after": "214.75"
}
```

## Frontend Integration

The wallet system integrates with the frontend through the following components:

### User Wallet Page

The wallet page in the frontend displays:
- Current token balance
- Transaction history
- External wallet connection status
- Token earn/spend history

### Wallet Connection Flow

1. User initiates connection from wallet page
2. System generates connection request with challenge
3. User signs challenge with external wallet
4. Backend verifies signature and creates connection
5. Frontend updates to show connected status

### Transaction Notifications

The system provides real-time notifications for:
- Token transfers
- Fee deductions
- Reward distributions
- Low balance alerts

## Security Considerations

The wallet system implements several security measures:

1. **Signature Verification**: All external wallet connections require cryptographic proof of ownership
2. **Transaction Validation**: Multi-step validation process for all token transfers
3. **Rate Limiting**: Protection against brute force attempts and DoS attacks
4. **Encryption**: Sensitive wallet data is encrypted at rest
5. **Audit Logging**: All wallet operations are logged for security auditing
6. **Fraud Detection**: Anomaly detection for suspicious transaction patterns

## Error Handling

The wallet system defines the following error types:

```python
class WalletError(Exception):
    """Base class for wallet errors."""
    pass

class WalletNotFoundError(WalletError):
    """Raised when wallet is not found."""
    pass

class InsufficientBalanceError(WalletError):
    """Raised when user has insufficient balance."""
    pass

class WalletAlreadyConnectedError(WalletError):
    """Raised when wallet is already connected."""
    pass

class InvalidSignatureError(WalletError):
    """Raised when wallet signature is invalid."""
    pass

class TransactionFailedError(WalletError):
    """Raised when transaction fails."""
    pass
```

Each error type has a corresponding error handler that:
1. Logs the error with appropriate context
2. Returns a user-friendly error message
3. Performs any necessary cleanup or recovery actions

## Testing

The wallet system includes comprehensive tests:

### Unit Tests
- Wallet creation and retrieval
- Balance calculation
- Transaction recording
- Error handling

### Integration Tests
- External wallet connection
- Transaction processing
- API endpoint validation
- Frontend-backend interaction

### Security Tests
- Signature verification
- Rate limiting effectiveness
- Access control validation

## Monitoring and Metrics

The wallet system tracks the following metrics:

- Average wallet balance
- Transaction volume by type
- Error rates
- Processing time
- External wallet connections/disconnections

These metrics are exported to Prometheus and visualized in Grafana dashboards.

## Best Practices

### 1. Transaction Safety
- Always verify balances before transfers
- Use database transactions for atomic operations
- Implement proper error handling and rollbacks
- Maintain comprehensive audit logs

### 2. Performance Optimization
- Cache frequently accessed wallet data
- Use optimized queries for balance calculations
- Implement background processing for non-critical operations
- Monitor and optimize database performance

### 3. User Experience
- Provide clear error messages for wallet operations
- Display real-time balance updates
- Send notifications for significant transactions
- Offer detailed transaction history with filtering options

## Future Improvements

Planned enhancements to the wallet system:

1. **Multi-chain Support**: Extend wallet connections to additional blockchain networks
2. **Enhanced Analytics**: Provide users with spending/earning patterns and insights
3. **Smart Contract Integration**: Direct integration with token-based smart contracts
4. **Mobile Wallet Integration**: Support for mobile wallet connections via deep links
5. **Advanced Security Features**: Multi-factor authentication for high-value transactions 