"""
Base SQLAlchemy model configuration.
"""
from sqlalchemy import Column, DateTime, Integer, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declared_attr


class BaseModel:
    """Base model class with common fields"""
    
    @declared_attr
    def __tablename__(cls):
        """Generate table name from class name"""
        # Convert CamelCase to snake_case
        name = cls.__name__
        result = name[0].lower()
        for char in name[1:]:
            if char.isupper():
                result += '_' + char.lower()
            else:
                result += char
        return result + 's'  # Pluralize
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"


# Create the declarative base
Base = declarative_base(cls=BaseModel)