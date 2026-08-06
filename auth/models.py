from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    employee_id = Column(String(20), unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)

    role = Column(
        String(30),
        nullable=False,
        default="officer",
    )
    # officer | reviewer | translator | admin

    department = Column(
        String(100),
        nullable=True,
    )

    preferred_language = Column(
        String(10),
        nullable=False,
        default="en",
    )
    # en | mr | hi

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    last_login = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    blacklisted_tokens = relationship(
        "BlacklistedTokens",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class BlacklistedTokens(Base):
    __tablename__ = "blacklisted_tokens"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        index=True,
    )

    token = Column(
        Text,
        nullable=False,
    )

    blacklisted_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    reason = Column(
        String(255),
        nullable=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    user = relationship(
        "User",
        back_populates="blacklisted_tokens",
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=True, default="New Conversation")
    
    # Useful for future dashboard KPI visualizations
    department_context = Column(String(100), nullable=True) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", backref="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    role = Column(String(20), nullable=False) # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    
    # Store the extracted sources as JSON to display in the UI history
    citations_json = Column(Text, nullable=True) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("ChatSession", back_populates="messages")

class MessageFeedback(Base):
    __tablename__ = "message_feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=True)
    
    answered = Column(String(10), nullable=True)          # 'yes' | 'no'
    accuracy = Column(Integer, nullable=True)              # 1 - 5 stars
    citations_relevant = Column(String(20), nullable=True) # 'yes' | 'partially' | 'no'
    comments = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)