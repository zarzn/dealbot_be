"""Tests for the chat model."""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select

from core.models.chat import Chat, ChatMessage, ChatStatus, MessageRole, MessageStatus
from core.models.user import User
from core.models.deal import Deal
from core.models.enums import DealStatus, MarketType

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_creation(db_session):
    """Test creating a chat in the database."""
    # Create a user
    user = User(
        email="chat_test@example.com",
        username="chatuser",
        full_name="Chat Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Chat Test Deal",
        description="A deal for testing chat model",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create a chat
    chat = Chat(
        title="Test Chat",
        status=ChatStatus.ACTIVE.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        metadata={
            "context": "deal discussion",
            "importance": "high"
        }
    )
    
    # Add to session and commit
    db_session.add(chat)
    await db_session.commit()
    await db_session.refresh(chat)
    
    # Verify the chat was created with an ID
    assert chat.id is not None
    assert isinstance(chat.id, uuid.UUID)
    assert chat.title == "Test Chat"
    assert chat.status == ChatStatus.ACTIVE.value.lower()
    assert chat.user_id == user.id
    assert chat.deal_id == deal.id
    
    # Verify metadata
    assert chat.metadata["context"] == "deal discussion"
    assert chat.metadata["importance"] == "high"
    
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
        email="chat_test@example.com",
        username="chatuser",
        full_name="Chat Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a conversation ID
    conversation_id = uuid.uuid4()
    
    # Create a chat message
    message = ChatMessage(
        user_id=user.id,
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content="Hello, this is a test message",
        status=MessageStatus.PENDING,
        context={"source": "web_interface"},
        chat_metadata={"client_id": "test_client"}
    )
    
    # Add to session and commit
    db_session.add(message)
    await db_session.commit()
    await db_session.refresh(message)
    
    # Verify the message was created with an ID
    assert message.id is not None
    assert isinstance(message.id, uuid.UUID)
    assert message.user_id == user.id
    assert message.conversation_id == conversation_id
    assert message.role == MessageRole.USER
    assert message.content == "Hello, this is a test message"
    assert message.status == MessageStatus.PENDING
    
    # Verify context and metadata
    assert message.context["source"] == "web_interface"
    assert message.chat_metadata["client_id"] == "test_client"
    
    # Verify created_at was set
    assert message.created_at is not None
    assert isinstance(message.created_at, datetime)

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_message_mark_completed(db_session):
    """Test marking a chat message as completed."""
    # Create a user
    user = User(
        email="chat_complete@example.com",
        username="chatcompleteuser",
        full_name="Chat Complete Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a conversation ID
    conversation_id = uuid.uuid4()
    
    # Create a chat message
    message = ChatMessage(
        user_id=user.id,
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content="I'm processing your request",
        status=MessageStatus.PROCESSING
    )
    db_session.add(message)
    await db_session.commit()
    
    # Mark the message as completed
    await message.mark_completed(tokens_used=150)
    await db_session.commit()
    await db_session.refresh(message)
    
    # Verify the message was marked as completed
    assert message.status == MessageStatus.COMPLETED
    assert message.tokens_used == 150

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_message_mark_failed(db_session):
    """Test marking a chat message as failed."""
    # Create a user
    user = User(
        email="chat_fail@example.com",
        username="chatfailuser",
        full_name="Chat Fail Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a conversation ID
    conversation_id = uuid.uuid4()
    
    # Create a chat message
    message = ChatMessage(
        user_id=user.id,
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content="I'm processing your request",
        status=MessageStatus.PROCESSING
    )
    db_session.add(message)
    await db_session.commit()
    
    # Mark the message as failed
    error_message = "Failed to generate response: model error"
    await message.mark_failed(error=error_message)
    await db_session.commit()
    await db_session.refresh(message)
    
    # Verify the message was marked as failed
    assert message.status == MessageStatus.FAILED
    assert message.error == error_message

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_message_different_roles(db_session):
    """Test creating chat messages with different roles."""
    # Create a user
    user = User(
        email="chat_roles@example.com",
        username="chatrolesuser",
        full_name="Chat Roles Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a conversation ID
    conversation_id = uuid.uuid4()
    
    # Create messages with different roles
    user_message = ChatMessage(
        user_id=user.id,
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content="What's the weather like today?",
        status=MessageStatus.COMPLETED,
        tokens_used=10
    )
    
    assistant_message = ChatMessage(
        user_id=user.id,
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content="The weather is sunny with a high of 75°F.",
        status=MessageStatus.COMPLETED,
        tokens_used=15
    )
    
    system_message = ChatMessage(
        user_id=user.id,
        conversation_id=conversation_id,
        role=MessageRole.SYSTEM,
        content="You are a helpful assistant that provides weather information.",
        status=MessageStatus.COMPLETED,
        tokens_used=20
    )
    
    db_session.add_all([user_message, assistant_message, system_message])
    await db_session.commit()
    
    # Query messages by role
    stmt = select(ChatMessage).where(
        ChatMessage.conversation_id == conversation_id,
        ChatMessage.role == MessageRole.USER
    )
    result = await db_session.execute(stmt)
    user_messages = result.scalars().all()
    
    stmt = select(ChatMessage).where(
        ChatMessage.conversation_id == conversation_id,
        ChatMessage.role == MessageRole.ASSISTANT
    )
    result = await db_session.execute(stmt)
    assistant_messages = result.scalars().all()
    
    stmt = select(ChatMessage).where(
        ChatMessage.conversation_id == conversation_id,
        ChatMessage.role == MessageRole.SYSTEM
    )
    result = await db_session.execute(stmt)
    system_messages = result.scalars().all()
    
    # Verify messages by role
    assert len(user_messages) == 1
    assert len(assistant_messages) == 1
    assert len(system_messages) == 1
    
    assert user_messages[0].content == "What's the weather like today?"
    assert assistant_messages[0].content == "The weather is sunny with a high of 75°F."
    assert system_messages[0].content == "You are a helpful assistant that provides weather information."

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_message_conversation_query(db_session):
    """Test querying chat messages by conversation."""
    # Create a user
    user = User(
        email="chat_convo@example.com",
        username="chatconvouser",
        full_name="Chat Conversation Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create two conversation IDs
    conversation1_id = uuid.uuid4()
    conversation2_id = uuid.uuid4()
    
    # Create messages for conversation 1
    messages_convo1 = [
        ChatMessage(
            user_id=user.id,
            conversation_id=conversation1_id,
            role=MessageRole.USER,
            content=f"User message {i} in conversation 1",
            status=MessageStatus.COMPLETED,
            tokens_used=10 + i
        )
        for i in range(3)
    ]
    
    # Create messages for conversation 2
    messages_convo2 = [
        ChatMessage(
            user_id=user.id,
            conversation_id=conversation2_id,
            role=MessageRole.USER,
            content=f"User message {i} in conversation 2",
            status=MessageStatus.COMPLETED,
            tokens_used=20 + i
        )
        for i in range(2)
    ]
    
    db_session.add_all(messages_convo1 + messages_convo2)
    await db_session.commit()
    
    # Query messages by conversation
    stmt = select(ChatMessage).where(
        ChatMessage.conversation_id == conversation1_id
    ).order_by(ChatMessage.created_at)
    result = await db_session.execute(stmt)
    convo1_messages = result.scalars().all()
    
    stmt = select(ChatMessage).where(
        ChatMessage.conversation_id == conversation2_id
    ).order_by(ChatMessage.created_at)
    result = await db_session.execute(stmt)
    convo2_messages = result.scalars().all()
    
    # Verify messages by conversation
    assert len(convo1_messages) == 3
    assert len(convo2_messages) == 2
    
    for i, msg in enumerate(convo1_messages):
        assert msg.content == f"User message {i} in conversation 1"
        assert msg.tokens_used == 10 + i
    
    for i, msg in enumerate(convo2_messages):
        assert msg.content == f"User message {i} in conversation 2"
        assert msg.tokens_used == 20 + i

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_message_user_relationship(db_session):
    """Test the relationship between chat messages and users."""
    # Create a user
    user = User(
        email="chat_rel@example.com",
        username="chatreluser",
        full_name="Chat Relationship Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a conversation ID
    conversation_id = uuid.uuid4()
    
    # Create a chat message
    message = ChatMessage(
        user_id=user.id,
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content="Test message for relationship",
        status=MessageStatus.COMPLETED,
        tokens_used=25
    )
    db_session.add(message)
    await db_session.commit()
    
    # Query the message with user relationship
    stmt = select(ChatMessage).where(ChatMessage.id == message.id)
    result = await db_session.execute(stmt)
    loaded_message = result.scalar_one()
    
    # Verify the relationship
    assert loaded_message.user_id == user.id
    assert loaded_message.user.email == "chat_rel@example.com"
    assert loaded_message.user.username == "chatreluser"

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_relationships(db_session):
    """Test chat relationships with user, deal, and messages."""
    # Create a user
    user = User(
        email="chat_rel_test@example.com",
        username="chatreluser",
        full_name="Chat Relationship Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Chat Relationship Test Deal",
        description="A deal for testing chat relationships",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create a chat
    chat = Chat(
        title="Relationship Test Chat",
        status=ChatStatus.ACTIVE.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        metadata={"test": True}
    )
    db_session.add(chat)
    await db_session.commit()
    
    # Create chat messages
    message1 = ChatMessage(
        content="First test message",
        role=MessageRole.USER.value.lower(),
        chat_id=chat.id,
        user_id=user.id
    )
    
    message2 = ChatMessage(
        content="Second test message",
        role=MessageRole.ASSISTANT.value.lower(),
        chat_id=chat.id,
        user_id=user.id
    )
    
    db_session.add_all([message1, message2])
    await db_session.commit()
    
    # Query the chat with relationships
    stmt = select(Chat).where(Chat.id == chat.id)
    result = await db_session.execute(stmt)
    loaded_chat = result.scalar_one()
    
    # Verify relationships
    assert loaded_chat.id == chat.id
    assert loaded_chat.user_id == user.id
    assert loaded_chat.deal_id == deal.id
    
    # Query messages for the chat
    stmt = select(ChatMessage).where(ChatMessage.chat_id == chat.id).order_by(ChatMessage.created_at)
    result = await db_session.execute(stmt)
    messages = result.scalars().all()
    
    # Verify messages
    assert len(messages) == 2
    assert messages[0].content == "First test message"
    assert messages[0].role == MessageRole.USER.value.lower()
    assert messages[1].content == "Second test message"
    assert messages[1].role == MessageRole.ASSISTANT.value.lower()

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_creation(async_session):
    """Test creating a chat in the database."""
    # Create a test user first
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    await async_session.commit()
    
    # Create chat
    chat = Chat(user_id=user_id, title="Test Chat")
    async_session.add(chat)
    await async_session.commit()
    
    # Retrieve the chat
    query = select(Chat).where(Chat.user_id == user_id)
    result = await async_session.execute(query)
    fetched_chat = result.scalar_one()
    
    # Assertions
    assert fetched_chat is not None
    assert fetched_chat.id is not None
    assert fetched_chat.user_id == user_id
    assert fetched_chat.title == "Test Chat"
    assert fetched_chat.status == ChatStatus.ACTIVE
    assert isinstance(fetched_chat.created_at, datetime)
    assert isinstance(fetched_chat.updated_at, datetime)
    assert fetched_chat.chat_metadata is None


@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_message_creation(async_session):
    """Test creating a chat message in the database."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create chat
    chat = Chat(user_id=user_id, title="Test Chat")
    async_session.add(chat)
    await async_session.commit()
    
    # Create message
    message = ChatMessage(
        user_id=user_id,
        conversation_id=chat.id,
        role=MessageRole.USER,
        content="Hello, AI!",
        status=MessageStatus.COMPLETED,
        tokens_used=10
    )
    async_session.add(message)
    await async_session.commit()
    
    # Retrieve the message
    query = select(ChatMessage).where(ChatMessage.conversation_id == chat.id)
    result = await async_session.execute(query)
    fetched_message = result.scalar_one()
    
    # Assertions
    assert fetched_message is not None
    assert fetched_message.id is not None
    assert fetched_message.user_id == user_id
    assert fetched_message.conversation_id == chat.id
    assert fetched_message.role == MessageRole.USER
    assert fetched_message.content == "Hello, AI!"
    assert fetched_message.status == MessageStatus.COMPLETED
    assert fetched_message.tokens_used == 10
    assert fetched_message.context is None
    assert fetched_message.chat_metadata is None
    assert fetched_message.error is None


@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_relationships(async_session):
    """Test the relationships between chat, messages, and user."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create chat
    chat = Chat(user_id=user_id, title="Test Chat")
    async_session.add(chat)
    await async_session.commit()
    
    # Create multiple messages
    message1 = ChatMessage(
        user_id=user_id,
        conversation_id=chat.id,
        role=MessageRole.USER,
        content="What can you help me with?",
        status=MessageStatus.COMPLETED
    )
    
    message2 = ChatMessage(
        user_id=user_id,
        conversation_id=chat.id,
        role=MessageRole.ASSISTANT,
        content="I can help you find investment opportunities and analyze deals.",
        status=MessageStatus.COMPLETED
    )
    
    async_session.add_all([message1, message2])
    await async_session.commit()
    
    # Test chat -> messages relationship
    query = select(Chat).where(Chat.id == chat.id)
    result = await async_session.execute(query)
    fetched_chat = result.scalar_one()
    
    assert fetched_chat.user is not None
    assert fetched_chat.user.id == user_id
    assert len(fetched_chat.messages) == 2
    
    # Test message -> chat relationship
    query = select(ChatMessage).where(ChatMessage.id == message1.id)
    result = await async_session.execute(query)
    fetched_message = result.scalar_one()
    
    assert fetched_message.chat is not None
    assert fetched_message.chat.id == chat.id
    assert fetched_message.user is not None
    assert fetched_message.user.id == user_id
    
    # Test user -> chats relationship
    query = select(User).where(User.id == user_id)
    result = await async_session.execute(query)
    fetched_user = result.scalar_one()
    
    assert len(fetched_user.chats) == 1
    assert fetched_user.chats[0].id == chat.id
    assert len(fetched_user.chat_messages) == 2


@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_status_update(async_session):
    """Test updating a chat's status."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create chat
    chat = Chat(user_id=user_id, title="Test Chat")
    async_session.add(chat)
    await async_session.commit()
    
    # Update status
    chat.status = ChatStatus.ARCHIVED
    await async_session.commit()
    
    # Verify status update
    query = select(Chat).where(Chat.id == chat.id)
    result = await async_session.execute(query)
    updated_chat = result.scalar_one()
    
    assert updated_chat.status == ChatStatus.ARCHIVED
    
    # Update status again
    updated_chat.status = ChatStatus.DELETED
    await async_session.commit()
    
    # Verify second update
    query = select(Chat).where(Chat.id == chat.id)
    result = await async_session.execute(query)
    deleted_chat = result.scalar_one()
    
    assert deleted_chat.status == ChatStatus.DELETED


@pytest.mark.asyncio
@pytest.mark.core
async def test_message_status_methods(async_session):
    """Test the message status update methods."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create chat
    chat = Chat(user_id=user_id, title="Test Chat")
    async_session.add(chat)
    await async_session.commit()
    
    # Create message
    message = ChatMessage(
        user_id=user_id,
        conversation_id=chat.id,
        role=MessageRole.USER,
        content="Process this message",
        status=MessageStatus.PENDING
    )
    async_session.add(message)
    await async_session.commit()
    
    # Test mark_completed
    await message.mark_completed(tokens_used=15)
    await async_session.commit()
    
    query = select(ChatMessage).where(ChatMessage.id == message.id)
    result = await async_session.execute(query)
    completed_message = result.scalar_one()
    
    assert completed_message.status == MessageStatus.COMPLETED
    assert completed_message.tokens_used == 15
    
    # Create another message for testing mark_failed
    error_message = ChatMessage(
        user_id=user_id,
        conversation_id=chat.id,
        role=MessageRole.ASSISTANT,
        content="This will fail",
        status=MessageStatus.PROCESSING
    )
    async_session.add(error_message)
    await async_session.commit()
    
    # Test mark_failed
    await error_message.mark_failed(error="Service unavailable")
    await async_session.commit()
    
    query = select(ChatMessage).where(ChatMessage.id == error_message.id)
    result = await async_session.execute(query)
    failed_message = result.scalar_one()
    
    assert failed_message.status == MessageStatus.FAILED
    assert failed_message.error == "Service unavailable"


@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_cascade_delete(async_session):
    """Test that deleting a chat deletes its messages via cascade."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create chat
    chat = Chat(user_id=user_id, title="Test Chat for Deletion")
    async_session.add(chat)
    await async_session.commit()
    
    # Create messages
    message1 = ChatMessage(
        user_id=user_id,
        conversation_id=chat.id,
        role=MessageRole.USER,
        content="Message 1",
        status=MessageStatus.COMPLETED
    )
    
    message2 = ChatMessage(
        user_id=user_id,
        conversation_id=chat.id,
        role=MessageRole.ASSISTANT,
        content="Response to message 1",
        status=MessageStatus.COMPLETED
    )
    
    async_session.add_all([message1, message2])
    await async_session.commit()
    
    # Get message IDs for later verification
    message1_id = message1.id
    message2_id = message2.id
    
    # Delete the chat
    await async_session.delete(chat)
    await async_session.commit()
    
    # Verify chat is deleted
    query = select(Chat).where(Chat.id == chat.id)
    result = await async_session.execute(query)
    deleted_chat = result.scalar_one_or_none()
    assert deleted_chat is None
    
    # Verify cascade delete of messages
    query = select(ChatMessage).where(
        ChatMessage.id.in_([message1_id, message2_id])
    )
    result = await async_session.execute(query)
    deleted_messages = result.scalars().all()
    assert len(deleted_messages) == 0


@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_metadata(async_session):
    """Test chat and message metadata storage."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    await async_session.commit()
    
    # Create chat with metadata
    chat = Chat(
        user_id=user_id, 
        title="Metadata Test Chat",
        chat_metadata={"category": "investment", "priority": "high"}
    )
    async_session.add(chat)
    await async_session.commit()
    
    # Create message with context and metadata
    message = ChatMessage(
        user_id=user_id,
        conversation_id=chat.id,
            role=MessageRole.USER,
        content="Analyze this investment",
            status=MessageStatus.COMPLETED,
        context={"investment_type": "crypto", "risk_level": "medium"},
        chat_metadata={"source": "web", "device": "desktop"}
    )
    async_session.add(message)
    await async_session.commit()
    
    # Verify chat metadata
    query = select(Chat).where(Chat.id == chat.id)
    result = await async_session.execute(query)
    fetched_chat = result.scalar_one()
    
    assert fetched_chat.chat_metadata == {"category": "investment", "priority": "high"}
    
    # Verify message context and metadata
    query = select(ChatMessage).where(ChatMessage.id == message.id)
    result = await async_session.execute(query)
    fetched_message = result.scalar_one()
    
    assert fetched_message.context == {"investment_type": "crypto", "risk_level": "medium"}
    assert fetched_message.chat_metadata == {"source": "web", "device": "desktop"}
    
    # Update metadata
    fetched_chat.chat_metadata = {
        **fetched_chat.chat_metadata, 
        "status": "active"
    }
    await async_session.commit()
    
    # Verify updated metadata
    query = select(Chat).where(Chat.id == chat.id)
    result = await async_session.execute(query)
    updated_chat = result.scalar_one()
    
    assert updated_chat.chat_metadata == {
        "category": "investment", 
        "priority": "high",
        "status": "active"
    }


@pytest.mark.asyncio
@pytest.mark.core
async def test_pydantic_models(async_session):
    """Test the Pydantic models associated with Chat."""
    # Test ChatMessageCreate
    message_create = ChatMessageCreate(
        content="Hello from Pydantic",
        role="user",
        context={"source": "api_test"}
    )
    
    assert message_create.content == "Hello from Pydantic"
    assert message_create.role == "user"
    assert message_create.context == {"source": "api_test"}
    
    # Test with invalid role
    with pytest.raises(ValueError, match="Invalid role"):
        ChatMessageCreate(
            content="Invalid role",
            role="invalid_role"
        )
    
    # Create chat and message in the database
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    chat = Chat(user_id=user_id, title="Pydantic Test Chat")
    async_session.add(chat)
    await async_session.commit()
    
    message = ChatMessage(
        user_id=user_id,
        conversation_id=chat.id,
        role=MessageRole.USER,
        content=message_create.content,
        status=MessageStatus.COMPLETED,
        tokens_used=12,
        context=message_create.context
    )
    async_session.add(message)
    await async_session.commit()
    
    # Test ChatMessageResponse
    message_response = ChatMessageResponse.model_validate(message)
    
    assert message_response.id == message.id
    assert message_response.user_id == user_id
    assert message_response.content == "Hello from Pydantic"
    assert message_response.role == "user"
    assert message_response.context == {"source": "api_test"}
    assert message_response.tokens_used == 12
    
    # Test ChatResponse
    chat_response = ChatResponse(
        id=chat.id,
        user_id=user_id,
        message="Response from assistant",
        role="assistant",
        context={"response_type": "text"},
        tokens_used=15
    )
    
    assert chat_response.id == chat.id
    assert chat_response.user_id == user_id
    assert chat_response.message == "Response from assistant"
    assert chat_response.role == "assistant"
    assert chat_response.context == {"response_type": "text"}
    assert chat_response.tokens_used == 15
    assert isinstance(chat_response.created_at, datetime)

@pytest.mark.asyncio
@pytest.mark.core
async def test_chat_message_user_relationship(async_session):
    """Test the relationship between chat messages and users."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    await async_session.commit()
    
    # Create chat
    chat = Chat(user_id=user_id, title="Test Chat")
    async_session.add(chat)
    await async_session.commit()
    
    # Create message
    message = ChatMessage(
        user_id=user_id,
        conversation_id=chat.id,
        role=MessageRole.USER,
        content="Hello, AI!",
        status=MessageStatus.COMPLETED,
        tokens_used=10
    )
    async_session.add(message)
    await async_session.commit()
    
    # Retrieve the message with user relationship
    query = select(ChatMessage).where(ChatMessage.id == message.id)
    result = await async_session.execute(query)
    loaded_message = result.scalar_one()
    
    # Verify the relationship
    assert loaded_message.user_id == user_id
    assert loaded_message.user.email == "test@example.com"
    assert loaded_message.user.username == "testuser"