"""Tests for the chat model."""

import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select

from core.models.chat import Chat, ChatMessage, MessageRole, ChatStatus, MessageStatus
from core.models.user import User
from core.models.deal import Deal
from core.models.market import Market
from core.models.enums import MarketType, DealStatus, MarketCategory, MarketStatus

# Skip all tests in this module since the chats table doesn't exist
# pytestmark = pytest.mark.skip(reason="The chats table doesn't exist in the test database")

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_creation(db_session):
    """Test creating a chat in the database."""
    # Create a user
    user = User(
        email="chat_test@example.com",
        name="Chat Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a market
    market = Market(
        name="Chat Test Market",
        type=MarketType.TEST.value.lower(),
        status=MarketStatus.ACTIVE.value.lower()
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Chat Test Deal",
        description="A deal for testing chat",
        url="https://example.com/chat-test-deal",
        price=10.99,
        currency="USD",
        status=DealStatus.ACTIVE.value.lower(),
        category=MarketCategory.ELECTRONICS.value,
        user_id=user.id,
        market_id=market.id
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create a chat
    chat = Chat(
        user_id=user.id,
        title="Test Chat",
        status="active",
        chat_metadata={
            "context": "deal discussion",
            "importance": "high",
            "deal_id": str(deal.id)  # Store deal_id in metadata instead
        }
    )
    db_session.add(chat)
    await db_session.commit()
    await db_session.refresh(chat)
    
    # Verify the chat was created with an ID
    assert chat.id is not None
    assert isinstance(chat.id, uuid.UUID)
    assert chat.title == "Test Chat"
    assert chat.status == "active"
    assert chat.user_id == user.id
    
    # Verify metadata
    assert chat.chat_metadata["context"] == "deal discussion"
    assert chat.chat_metadata["importance"] == "high"
    assert chat.chat_metadata["deal_id"] == str(deal.id)
    
    # Verify created_at and updated_at were set
    assert chat.created_at is not None
    assert chat.updated_at is not None
    assert isinstance(chat.created_at, datetime)
    assert isinstance(chat.updated_at, datetime)

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_message_creation(db_session):
    """Test creating a chat message in the database."""
    # Create a user
    user = User(
        email="chat_message_test@example.com",
        name="Chat Message Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a chat
    chat = Chat(
        user_id=user.id,
        title="Test Chat for Messages",
        status="active",
        chat_metadata={"context": "message testing"}
    )
    db_session.add(chat)
    await db_session.commit()
    
    # Create a chat message
    message = ChatMessage(
        user_id=user.id,
        conversation_id=chat.id,
        role="user",
        content="Hello, this is a test message",
        status="completed",
        tokens_used=10,
        chat_metadata={"test": True}
    )
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message)
    
    # Verify the message was created with an ID
    assert message.id is not None
    assert isinstance(message.id, uuid.UUID)
    assert message.role == "user"
    assert message.content == "Hello, this is a test message"
    assert message.status == "completed"
    assert message.tokens_used == 10
    assert message.chat_metadata["test"] is True
    
    # Verify relationships
    assert message.user_id == user.id
    assert message.conversation_id == chat.id

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_message_mark_completed(db_session):
    """Test marking a chat message as completed."""
    # Create a user
    user = User(
        email="chat_complete@example.com",
        name="Chat Complete Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a chat first
    chat = Chat(
        user_id=user.id,
        title="Mark Completed Test Chat",
        status="active",
        chat_metadata={"context": "mark completed testing"}
    )
    db_session.add(chat)
    await db_session.commit()
    
    # Create a chat message
    message = ChatMessage(
        user_id=user.id,
        conversation_id=chat.id,
        role=MessageRole.ASSISTANT.value.lower(),
        content="I'm processing your request",
        status=MessageStatus.PROCESSING
    )
    db_session.add(message)
    await db_session.commit()
    
    # Mark as completed
    await message.mark_completed(tokens_used=42)
    await db_session.commit()
    await db_session.refresh(message)
    
    # Verify status and tokens
    assert message.status == MessageStatus.COMPLETED
    assert message.tokens_used == 42

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_message_mark_failed(db_session):
    """Test marking a chat message as failed."""
    # Create a user
    user = User(
        email="chat_failed@example.com",
        name="Chat Failed Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a chat first
    chat = Chat(
        user_id=user.id,
        title="Mark Failed Test Chat",
        status="active",
        chat_metadata={"context": "mark failed testing"}
    )
    db_session.add(chat)
    await db_session.commit()
    
    # Create a chat message
    message = ChatMessage(
        user_id=user.id,
        conversation_id=chat.id,
        role=MessageRole.ASSISTANT.value.lower(),
        content="I'm processing your request",
        status=MessageStatus.PROCESSING
    )
    db_session.add(message)
    await db_session.commit()
    
    # Mark as failed
    error_message = "API rate limit exceeded"
    await message.mark_failed(error=error_message)
    await db_session.commit()
    await db_session.refresh(message)
    
    # Verify status and error
    assert message.status == MessageStatus.FAILED
    assert message.error == error_message

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_message_different_roles(db_session):
    """Test creating chat messages with different roles."""
    # Create a user
    user = User(
        email="chat_roles@example.com",
        name="Chat Roles Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a chat first
    chat = Chat(
        user_id=user.id,
        title="Different Roles Test Chat",
        status="active",
        chat_metadata={"context": "roles testing"}
    )
    db_session.add(chat)
    await db_session.commit()
    
    # Create messages with different roles
    user_message = ChatMessage(
        user_id=user.id,
        conversation_id=chat.id,
        role=MessageRole.USER.value.lower(),
        content="Can you help me find a good deal?",
        status=MessageStatus.COMPLETED
    )
    
    assistant_message = ChatMessage(
        user_id=user.id,
        conversation_id=chat.id,
        role=MessageRole.ASSISTANT.value.lower(),
        content="I'll search for deals matching your preferences.",
        status=MessageStatus.COMPLETED
    )
    
    system_message = ChatMessage(
        user_id=user.id,
        conversation_id=chat.id,
        role=MessageRole.SYSTEM.value.lower(),
        content="Initialize deal search agent.",
        status=MessageStatus.COMPLETED
    )
    
    db_session.add_all([user_message, assistant_message, system_message])
    await db_session.commit()
    
    # Query messages
    stmt = select(ChatMessage).where(ChatMessage.conversation_id == chat.id)
    result = await db_session.execute(stmt)
    messages = result.scalars().all()
    
    # Verify all messages were created
    assert len(messages) == 3
    
    # Verify roles
    roles = [m.role for m in messages]
    assert MessageRole.USER.value.lower() in roles
    assert MessageRole.ASSISTANT.value.lower() in roles
    assert MessageRole.SYSTEM.value.lower() in roles

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_message_conversation_query(db_session):
    """Test querying messages for a specific conversation."""
    # Create a user
    user = User(
        email="chat_conversation@example.com",
        name="Chat Conversation Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create two chats
    chat1 = Chat(
        user_id=user.id,
        title="First Conversation",
        status="active",
        chat_metadata={"context": "conversation testing 1"}
    )
    
    chat2 = Chat(
        user_id=user.id,
        title="Second Conversation",
        status="active",
        chat_metadata={"context": "conversation testing 2"}
    )
    
    db_session.add_all([chat1, chat2])
    await db_session.commit()
    
    # Create messages for the first conversation
    message1 = ChatMessage(
        user_id=user.id,
        conversation_id=chat1.id,
        role="user",
        content="First conversation message 1",
        status="completed"
    )
    
    message2 = ChatMessage(
        user_id=user.id,
        conversation_id=chat1.id,
        role="assistant",
        content="First conversation message 2",
        status="completed"
    )
    
    # Create message for the second conversation
    message3 = ChatMessage(
        user_id=user.id,
        conversation_id=chat2.id,
        role="user",
        content="Second conversation message",
        status="completed"
    )
    
    db_session.add_all([message1, message2, message3])
    await db_session.commit()
    
    # Query messages for the first conversation
    stmt = select(ChatMessage).where(ChatMessage.conversation_id == chat1.id)
    result = await db_session.execute(stmt)
    conversation1_messages = result.scalars().all()
    
    # Verify the number of messages
    assert len(conversation1_messages) == 2
    
    # Verify the content of messages
    contents = [m.content for m in conversation1_messages]
    assert "First conversation message 1" in contents
    assert "First conversation message 2" in contents
    
    # Query messages for the second conversation
    stmt = select(ChatMessage).where(ChatMessage.conversation_id == chat2.id)
    result = await db_session.execute(stmt)
    conversation2_messages = result.scalars().all()
    
    # Verify the number of messages
    assert len(conversation2_messages) == 1
    
    # Verify the content of messages
    assert conversation2_messages[0].content == "Second conversation message"

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_message_user_relationship(db_session):
    """Test relationships between chat message and user."""
    # Create a user
    user = User(
        email="chat_relationship@example.com",
        name="Chat Relationship Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a chat first
    chat = Chat(
        user_id=user.id,
        title="Relationship Test Chat",
        status="active",
        chat_metadata={"context": "relationship testing"}
    )
    db_session.add(chat)
    await db_session.commit()
    
    # Create a chat message
    message = ChatMessage(
        user_id=user.id,
        conversation_id=chat.id,  # Use the actual chat id
        role="user",
        content="Test message for relationship",
        status="completed",
        tokens_used=25
    )
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message)
    await db_session.refresh(user)
    
    # Verify the user relationship
    stmt = select(User).where(User.id == user.id)
    result = await db_session.execute(stmt)
    loaded_user = result.scalar_one()
    
    # Explicitly refresh the user to load relationships
    await db_session.refresh(loaded_user, ['chat_messages'])
    
    # Verify the user has the message in its relationship
    assert loaded_user.chat_messages[0].id == message.id
    assert loaded_user.chat_messages[0].content == "Test message for relationship"
    
    # Verify the message has the correct user
    assert message.user_id == user.id

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_relationships(db_session):
    """Test relationships between chat and other models."""
    # Create a user
    user = User(
        email="chat_rels@example.com",
        name="Chat Relationships Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a market
    market = Market(
        name="Chat Relationships Test Market",
        type=MarketType.TEST.value.lower(),
        status=MarketStatus.ACTIVE.value.lower()
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a chat
    chat = Chat(
        user_id=user.id,
        title="Relationship Test Chat",
        status="active",
        chat_metadata={"context": "relationship testing"}
    )
    db_session.add(chat)
    await db_session.commit()
    
    # Verify the chat user relationship
    stmt = select(User).where(User.id == user.id)
    result = await db_session.execute(stmt)
    loaded_user = result.scalar_one()
    
    # Explicitly refresh the user to load relationships
    await db_session.refresh(loaded_user, ['chats'])
    
    # Verify the user has the chat in its relationship
    assert loaded_user.chats[0].id == chat.id
    assert loaded_user.chats[0].title == "Relationship Test Chat"
    
    # Verify the chat has the correct user
    assert chat.user_id == user.id