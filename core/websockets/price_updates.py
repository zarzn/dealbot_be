"""WebSocket handler for real-time price updates."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import asyncio
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.base import Base
from core.models.price_tracking import PricePoint, PriceTracker
from core.models.price_prediction import PricePrediction
from core.services.price_tracking import PriceTrackingService
from core.services.price_prediction import PricePredictionService
from core.utils.logger import get_logger
from core.database import get_async_db_context

logger = get_logger(__name__)

class PriceUpdateManager:
    """Manager for WebSocket connections and price updates."""
    
    def __init__(self):
        self.active_connections: Dict[UUID, List[WebSocket]] = {}
        self.user_subscriptions: Dict[WebSocket, List[UUID]] = {}
        self.background_tasks: List[asyncio.Task] = []

    async def connect(
        self,
        websocket: WebSocket,
        user_id: UUID
    ) -> None:
        """Connect a new WebSocket client."""
        await websocket.accept()
        
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        self.user_subscriptions[websocket] = []
        
        logger.info(f"WebSocket connected for user {user_id}")

    async def disconnect(
        self,
        websocket: WebSocket,
        user_id: UUID
    ) -> None:
        """Disconnect a WebSocket client."""
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                
        if websocket in self.user_subscriptions:
            del self.user_subscriptions[websocket]
            
        logger.info(f"WebSocket disconnected for user {user_id}")

    async def subscribe_to_deal(
        self,
        websocket: WebSocket,
        deal_id: UUID
    ) -> None:
        """Subscribe to price updates for a deal."""
        if websocket in self.user_subscriptions:
            if deal_id not in self.user_subscriptions[websocket]:
                self.user_subscriptions[websocket].append(deal_id)
                await self.send_initial_data(websocket, deal_id)
                
        logger.info(f"Subscribed to deal {deal_id}")

    async def unsubscribe_from_deal(
        self,
        websocket: WebSocket,
        deal_id: UUID
    ) -> None:
        """Unsubscribe from price updates for a deal."""
        if websocket in self.user_subscriptions:
            if deal_id in self.user_subscriptions[websocket]:
                self.user_subscriptions[websocket].remove(deal_id)
                
        logger.info(f"Unsubscribed from deal {deal_id}")

    async def send_initial_data(
        self,
        websocket: WebSocket,
        deal_id: UUID
    ) -> None:
        """Send initial price and prediction data for a deal."""
        try:
            # Use the new context manager for proper connection management
            async with get_async_db_context() as session:
                # Get recent price history
                tracking_service = PriceTrackingService(session)
                price_history = await tracking_service.get_price_history(deal_id)
                
                # Get latest prediction
                prediction_service = PricePredictionService(session)
                predictions = await prediction_service.get_predictions(deal_id)
                
                # Send initial data
                await websocket.send_json({
                    'type': 'initial_data',
                    'deal_id': str(deal_id),
                    'price_history': [p.model_dump() for p in price_history],
                    'predictions': [p.model_dump() for p in predictions],
                    'timestamp': datetime.utcnow().isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error sending initial data: {str(e)}")

    async def broadcast_price_update(
        self,
        deal_id: UUID,
        price_data: Dict[str, Any]
    ) -> None:
        """Broadcast price update to all subscribed clients."""
        message = {
            'type': 'price_update',
            'deal_id': str(deal_id),
            'data': price_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        for user_id, connections in self.active_connections.items():
            for websocket in connections:
                if deal_id in self.user_subscriptions[websocket]:
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.error(f"Error sending price update: {str(e)}")
                        await self.handle_disconnection(websocket, user_id)

    async def broadcast_prediction_update(
        self,
        deal_id: UUID,
        prediction_data: Dict[str, Any]
    ) -> None:
        """Broadcast prediction update to all subscribed clients."""
        message = {
            'type': 'prediction_update',
            'deal_id': str(deal_id),
            'data': prediction_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        for user_id, connections in self.active_connections.items():
            for websocket in connections:
                if deal_id in self.user_subscriptions[websocket]:
                    try:
                        await websocket.send_json(message)
                    except Exception as e:
                        logger.error(f"Error sending prediction update: {str(e)}")
                        await self.handle_disconnection(websocket, user_id)

    async def handle_disconnection(
        self,
        websocket: WebSocket,
        user_id: UUID
    ) -> None:
        """Handle client disconnection."""
        try:
            await websocket.close()
        except Exception:
            pass
            
        await self.disconnect(websocket, user_id)

    async def start_background_tasks(self) -> None:
        """Start background tasks for monitoring and updates."""
        self.background_tasks.append(
            asyncio.create_task(self.monitor_price_updates())
        )
        self.background_tasks.append(
            asyncio.create_task(self.monitor_prediction_updates())
        )

    async def stop_background_tasks(self) -> None:
        """Stop all background tasks."""
        for task in self.background_tasks:
            task.cancel()
            
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        self.background_tasks.clear()

    async def monitor_price_updates(self) -> None:
        """Monitor for price updates in background."""
        while True:
            try:
                # Use the new context manager for proper connection management
                async with get_async_db_context() as session:
                    tracking_service = PriceTrackingService(session)
                    for user_id, connections in self.active_connections.items():
                        for websocket in connections:
                            for deal_id in self.user_subscriptions[websocket]:
                                price_history = await tracking_service.get_price_history(deal_id)
                                if price_history:
                                    latest_price = price_history[0]
                                    await self.broadcast_price_update(
                                        deal_id,
                                        latest_price.model_dump()
                                    )
                        
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring price updates: {str(e)}")
                await asyncio.sleep(5)

    async def monitor_prediction_updates(self) -> None:
        """Monitor for prediction updates in background."""
        while True:
            try:
                # Use the new context manager for proper connection management
                async with get_async_db_context() as session:
                    prediction_service = PricePredictionService(session)
                    for user_id, connections in self.active_connections.items():
                        for websocket in connections:
                            for deal_id in self.user_subscriptions[websocket]:
                                predictions = await prediction_service.get_predictions(deal_id)
                                if predictions:
                                    latest_prediction = predictions[0]
                                    await self.broadcast_prediction_update(
                                        deal_id,
                                        latest_prediction.model_dump()
                                    )
                        
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring prediction updates: {str(e)}")
                await asyncio.sleep(60)

# Global WebSocket manager instance
price_update_manager = PriceUpdateManager()

async def handle_websocket(
    websocket: WebSocket,
    user_id: UUID
) -> None:
    """Handle WebSocket connection and messages."""
    try:
        await price_update_manager.connect(websocket, user_id)
        websocket.user_id = user_id  # Store user_id for later use
        
        while True:
            try:
                data = await websocket.receive_json()
                
                if data.get('type') == 'subscribe':
                    deal_id = UUID(data.get('deal_id'))
                    await price_update_manager.subscribe_to_deal(websocket, deal_id)
                    
                elif data.get('type') == 'unsubscribe':
                    deal_id = UUID(data.get('deal_id'))
                    await price_update_manager.unsubscribe_from_deal(websocket, deal_id)
                    
                elif data.get('type') == 'ping':
                    await websocket.send_json({
                        'type': 'pong',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
                else:
                    await websocket.send_json({
                        'type': 'error',
                        'message': 'Unknown message type',
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    'type': 'error',
                    'message': 'Invalid JSON',
                    'timestamp': datetime.utcnow().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                await websocket.send_json({
                    'type': 'error',
                    'message': str(e),
                    'timestamp': datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        await price_update_manager.disconnect(websocket, user_id)
        
    except Exception as e:
        logger.error(f"Error handling WebSocket: {str(e)}")
        try:
            await websocket.close()
        except Exception:
            pass 