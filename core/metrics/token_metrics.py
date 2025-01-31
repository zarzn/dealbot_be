from typing import Dict, Any
from prometheus_client import Counter, Gauge, Histogram
from datetime import datetime

# Transaction metrics
transaction_counter = Counter(
    'token_transactions_total',
    'Total number of token transactions',
    ['type', 'status']
)

transaction_amount_total = Counter(
    'token_transaction_amount_total',
    'Total amount of tokens transacted',
    ['type']
)

transaction_processing_time = Histogram(
    'token_transaction_processing_seconds',
    'Time spent processing token transactions',
    ['type'],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float('inf'))
)

failed_transactions = Counter(
    'token_failed_transactions_total',
    'Total number of failed token transactions',
    ['type', 'error_type']
)

# Balance metrics
user_balance = Gauge(
    'token_user_balance',
    'Current token balance for users',
    ['user_id']
)

total_token_supply = Gauge(
    'token_total_supply',
    'Total token supply in circulation'
)

# Wallet metrics
active_wallets = Gauge(
    'token_active_wallets',
    'Number of active token wallets'
)

wallet_connections = Counter(
    'token_wallet_connections_total',
    'Total number of wallet connections',
    ['status']
)

# Price metrics
token_price = Gauge(
    'token_current_price',
    'Current token price',
    ['source']
)

price_update_time = Gauge(
    'token_price_last_update',
    'Timestamp of last token price update',
    ['source']
)

# Smart contract metrics
contract_calls = Counter(
    'token_contract_calls_total',
    'Total number of smart contract calls',
    ['operation', 'status']
)

contract_gas_used = Counter(
    'token_contract_gas_total',
    'Total gas used for smart contract calls',
    ['operation']
)

class TokenMetrics:
    """Handler for token-related metrics"""
    
    @staticmethod
    def record_transaction(
        transaction_type: str,
        amount: float,
        status: str,
        processing_time: float
    ) -> None:
        """Record transaction metrics"""
        transaction_counter.labels(
            type=transaction_type,
            status=status
        ).inc()
        
        transaction_amount_total.labels(
            type=transaction_type
        ).inc(amount)
        
        transaction_processing_time.labels(
            type=transaction_type
        ).observe(processing_time)

    @staticmethod
    def record_failed_transaction(
        transaction_type: str,
        error_type: str
    ) -> None:
        """Record failed transaction metrics"""
        failed_transactions.labels(
            type=transaction_type,
            error_type=error_type
        ).inc()

    @staticmethod
    def update_user_balance(
        user_id: str,
        balance: float
    ) -> None:
        """Update user balance metric"""
        user_balance.labels(
            user_id=user_id
        ).set(balance)

    @staticmethod
    def update_total_supply(
        supply: float
    ) -> None:
        """Update total token supply metric"""
        total_token_supply.set(supply)

    @staticmethod
    def update_active_wallets(
        count: int
    ) -> None:
        """Update active wallets count"""
        active_wallets.set(count)

    @staticmethod
    def record_wallet_connection(
        status: str
    ) -> None:
        """Record wallet connection attempt"""
        wallet_connections.labels(
            status=status
        ).inc()

    @staticmethod
    def update_token_price(
        price: float,
        source: str
    ) -> None:
        """Update token price metrics"""
        token_price.labels(
            source=source
        ).set(price)
        
        price_update_time.labels(
            source=source
        ).set(datetime.utcnow().timestamp())

    @staticmethod
    def record_contract_call(
        operation: str,
        status: str,
        gas_used: float
    ) -> None:
        """Record smart contract call metrics"""
        contract_calls.labels(
            operation=operation,
            status=status
        ).inc()
        
        contract_gas_used.labels(
            operation=operation
        ).inc(gas_used)

    @staticmethod
    def get_metrics_summary() -> Dict[str, Any]:
        """Get summary of token metrics"""
        return {
            "transactions": {
                "total": transaction_counter._value.sum(),
                "failed": failed_transactions._value.sum(),
                "amount_total": transaction_amount_total._value.sum()
            },
            "wallets": {
                "active": active_wallets._value.get(),
                "connections": wallet_connections._value.sum()
            },
            "contract": {
                "calls": contract_calls._value.sum(),
                "gas_used": contract_gas_used._value.sum()
            }
        } 