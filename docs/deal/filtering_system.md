# Deal Filtering System

## Overview

The Deal Filtering System is a crucial component of the AI Agentic Deals platform that enables users to efficiently find deals matching their specific criteria. This document outlines the architecture, components, and functionality of the filtering system.

## System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│  Filter Inputs  │────►│ Filter Pipeline │────►│  Filter Results │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                             ▲      ▲
                             │      │
                  ┌──────────┘      └──────────┐
                  │                            │
        ┌─────────────────┐            ┌─────────────────┐
        │                 │            │                 │
        │  Database Layer │            │ User Preference │
        │                 │            │    System       │
        └─────────────────┘            └─────────────────┘
```

## Core Components

### 1. Filter Types

The system supports several filter types:

```python
from enum import Enum, auto

class FilterType(Enum):
    """Types of filters available in the system."""
    CATEGORY = auto()      # Product categories (Electronics, Fashion, etc.)
    PRICE_RANGE = auto()   # Min/max price boundaries
    DISCOUNT = auto()      # Minimum discount percentage
    RATING = auto()        # Minimum deal quality rating
    SOURCE = auto()        # Deal source (Amazon, eBay, etc.)
    KEYWORD = auto()       # Keyword search in title/description
    SELLER = auto()        # Specific seller filter
    RECENCY = auto()       # Time-based filtering
    CUSTOM = auto()        # User-defined complex filters
```

### 2. Filter Definition

Filters are defined using a standardized schema:

```python
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

class FilterDefinition(BaseModel):
    """Definition of a single filter."""
    filter_type: str
    operator: str
    value: Any
    negated: bool = False
    
    class Config:
        schema_extra = {
            "example": {
                "filter_type": "price_range",
                "operator": "between",
                "value": {"min": 10.0, "max": 50.0},
                "negated": False
            }
        }

class FilterGroup(BaseModel):
    """Group of filters with a logical operator."""
    operator: str = "AND"  # Can be "AND" or "OR"
    filters: List[Union[FilterDefinition, "FilterGroup"]]
    
    class Config:
        schema_extra = {
            "example": {
                "operator": "AND",
                "filters": [
                    {
                        "filter_type": "category",
                        "operator": "eq",
                        "value": "electronics"
                    },
                    {
                        "filter_type": "discount",
                        "operator": "gte",
                        "value": 20
                    }
                ]
            }
        }
```

### 3. Filter Manager

The Filter Manager orchestrates the filtering process:

```python
class FilterManager:
    """Manager for handling deal filters."""
    
    def __init__(self, db_session, user_preference_service=None):
        self.db_session = db_session
        self.user_preference_service = user_preference_service
        self.filter_processors = {
            "category": self._process_category_filter,
            "price_range": self._process_price_filter,
            "discount": self._process_discount_filter,
            "rating": self._process_rating_filter,
            "source": self._process_source_filter,
            "keyword": self._process_keyword_filter,
            "seller": self._process_seller_filter,
            "recency": self._process_recency_filter,
            "custom": self._process_custom_filter
        }
    
    async def apply_filters(
        self, 
        query, 
        filter_group: FilterGroup,
        user_id: Optional[UUID] = None
    ):
        """Apply filter group to the query."""
        if filter_group.operator.upper() == "AND":
            return await self._apply_and_group(query, filter_group, user_id)
        else:
            return await self._apply_or_group(query, filter_group, user_id)
    
    async def _apply_and_group(self, query, filter_group, user_id):
        """Apply AND group of filters."""
        for filter_item in filter_group.filters:
            if isinstance(filter_item, FilterGroup):
                query = await self.apply_filters(query, filter_item, user_id)
            else:
                query = await self._apply_single_filter(query, filter_item, user_id)
        return query
    
    async def _apply_or_group(self, query, filter_group, user_id):
        """Apply OR group of filters."""
        or_conditions = []
        for filter_item in filter_group.filters:
            if isinstance(filter_item, FilterGroup):
                subquery = query.session.query(Deal)
                subquery = await self.apply_filters(subquery, filter_item, user_id)
                or_conditions.append(subquery.exists())
            else:
                or_conditions.append(
                    await self._get_filter_condition(filter_item, user_id)
                )
        return query.filter(or_(*or_conditions))
    
    async def _apply_single_filter(self, query, filter_def, user_id):
        """Apply a single filter to the query."""
        condition = await self._get_filter_condition(filter_def, user_id)
        if filter_def.negated:
            condition = not_(condition)
        return query.filter(condition)
    
    async def _get_filter_condition(self, filter_def, user_id):
        """Get SQLAlchemy condition for a filter."""
        processor = self.filter_processors.get(filter_def.filter_type.lower())
        if not processor:
            raise ValueError(f"Unknown filter type: {filter_def.filter_type}")
        return await processor(filter_def, user_id)
    
    # Individual filter processors below
    async def _process_category_filter(self, filter_def, user_id):
        """Process category filter."""
        value = filter_def.value
        operator = filter_def.operator.lower()
        
        if operator == "eq":
            return Deal.category == value
        elif operator == "in":
            return Deal.category.in_(value)
        else:
            raise ValueError(f"Unsupported operator for category: {operator}")
    
    # Other filter processors would be implemented similarly...
```

### 4. Search Integration

The filtering system integrates with the search functionality:

```python
from fastapi import APIRouter, Depends, Query
from typing import List, Optional

from core.models.schemas import DealResponse, FilterRequest
from core.services.deal_service import DealService

router = APIRouter()

@router.post("/search", response_model=List[DealResponse])
async def search_deals(
    filter_request: FilterRequest,
    limit: int = Query(20, gt=0, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    user = Depends(get_current_user),
    deal_service: DealService = Depends()
):
    """
    Search for deals using filters.
    
    This endpoint allows searching for deals using various filters and sorting options.
    """
    deals = await deal_service.search_deals(
        filter_group=filter_request.filter_group,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
        user_id=user.id if user else None
    )
    
    return [DealResponse.from_orm(deal) for deal in deals]
```

## Filter Types in Detail

### 1. Category Filters

Category filters allow users to filter deals by product category. The system supports hierarchical categories:

```
Electronics
  └─ Computers
     ├─ Laptops
     ├─ Desktops
     └─ Accessories
  └─ Smartphones
     ├─ Android
     └─ iPhone
```

Implementation example:
```python
async def _process_category_filter(self, filter_def, user_id):
    value = filter_def.value
    operator = filter_def.operator.lower()
    
    if operator == "eq":
        return Deal.category == value
    elif operator == "in":
        return Deal.category.in_(value)
    elif operator == "child_of":
        # Get all subcategories
        categories = await self._get_subcategories(value)
        return Deal.category.in_(categories)
    else:
        raise ValueError(f"Unsupported operator for category: {operator}")

async def _get_subcategories(self, parent_category):
    """Get all subcategories of a parent category."""
    categories = [parent_category]
    
    # Find immediate children
    children = await Category.filter(parent_id=parent_category).values_list('id', flat=True)
    
    # Recursively find all descendants
    for child in children:
        subcats = await self._get_subcategories(child)
        categories.extend(subcats)
    
    return categories
```

### 2. Price Range Filters

Price filters allow filtering by price ranges:

```python
async def _process_price_filter(self, filter_def, user_id):
    value = filter_def.value
    operator = filter_def.operator.lower()
    
    if operator == "between":
        min_price = value.get("min")
        max_price = value.get("max")
        
        conditions = []
        if min_price is not None:
            conditions.append(Deal.price_current >= min_price)
        if max_price is not None:
            conditions.append(Deal.price_current <= max_price)
            
        return and_(*conditions)
    elif operator == "lt":
        return Deal.price_current < value
    elif operator == "lte":
        return Deal.price_current <= value
    elif operator == "gt":
        return Deal.price_current > value
    elif operator == "gte":
        return Deal.price_current >= value
    elif operator == "eq":
        return Deal.price_current == value
    else:
        raise ValueError(f"Unsupported operator for price_range: {operator}")
```

### 3. Discount Filters

Discount filters target the percentage discount on deals:

```python
async def _process_discount_filter(self, filter_def, user_id):
    value = filter_def.value
    operator = filter_def.operator.lower()
    
    if operator == "gte":
        return Deal.discount_percentage >= value
    elif operator == "gt":
        return Deal.discount_percentage > value
    elif operator == "lt":
        return Deal.discount_percentage < value
    elif operator == "lte":
        return Deal.discount_percentage <= value
    elif operator == "eq":
        return Deal.discount_percentage == value
    elif operator == "between":
        min_discount = value.get("min")
        max_discount = value.get("max")
        
        conditions = []
        if min_discount is not None:
            conditions.append(Deal.discount_percentage >= min_discount)
        if max_discount is not None:
            conditions.append(Deal.discount_percentage <= max_discount)
            
        return and_(*conditions)
    else:
        raise ValueError(f"Unsupported operator for discount: {operator}")
```

### 4. Rating Filters

Rating filters use the AI analysis quality rating:

```python
async def _process_rating_filter(self, filter_def, user_id):
    value = filter_def.value
    operator = filter_def.operator.lower()
    
    if operator == "gte":
        return Deal.analysis_quality >= value
    elif operator == "gt":
        return Deal.analysis_quality > value
    elif operator == "lt":
        return Deal.analysis_quality < value
    elif operator == "lte":
        return Deal.analysis_quality <= value
    elif operator == "eq":
        return Deal.analysis_quality == value
    else:
        raise ValueError(f"Unsupported operator for rating: {operator}")
```

### 5. Keyword Filters

Keyword filters search within deal titles and descriptions:

```python
async def _process_keyword_filter(self, filter_def, user_id):
    value = filter_def.value
    operator = filter_def.operator.lower()
    
    if operator == "contains":
        return or_(
            Deal.title.ilike(f"%{value}%"),
            Deal.description.ilike(f"%{value}%")
        )
    elif operator == "exact":
        return or_(
            Deal.title == value,
            Deal.description == value
        )
    else:
        raise ValueError(f"Unsupported operator for keyword: {operator}")
```

## User Preference Integration

The filtering system integrates with user preferences to provide personalized results:

```python
class UserPreferenceFilter:
    """Filter deals based on user preferences."""
    
    def __init__(self, preference_service):
        self.preference_service = preference_service
    
    async def apply_preference_filters(self, query, user_id):
        """Apply user preference-based filters to query."""
        if not user_id:
            return query
            
        # Get user preferences
        preferences = await self.preference_service.get_user_preferences(user_id)
        
        if not preferences:
            return query
            
        # Apply category preferences (if user has preferred categories)
        preferred_categories = preferences.get('preferred_categories', [])
        if preferred_categories:
            # We use a weight column to prioritize preferred categories
            # but still show other results
            query = query.order_by(
                case(
                    [(Deal.category.in_(preferred_categories), 1)],
                    else_=0
                ).desc()
            )
        
        # Apply price sensitivity preferences
        price_sensitivity = preferences.get('price_sensitivity')
        if price_sensitivity:
            if price_sensitivity == 'high':
                # Prioritize higher discounts for price-sensitive users
                query = query.order_by(Deal.discount_percentage.desc())
            elif price_sensitivity == 'low':
                # Prioritize quality over discount for less price-sensitive users
                query = query.order_by(Deal.analysis_quality.desc())
        
        # Apply brand preferences to boost preferred brands
        preferred_brands = preferences.get('preferred_brands', [])
        if preferred_brands:
            query = query.order_by(
                case(
                    [(Deal.brand.in_(preferred_brands), 1)],
                    else_=0
                ).desc()
            )
            
        return query
```

## Saved Filters

Users can save complex filter configurations for reuse:

```python
class SavedFilter(Base):
    """Model for user-saved filters."""
    __tablename__ = "saved_filters"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(UUID, ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    filter_definition: Mapped[Dict] = mapped_column(JSONB)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="saved_filters")


class SavedFilterService:
    """Service for managing saved filters."""
    
    def __init__(self, db_session):
        self.db_session = db_session
    
    async def create_saved_filter(
        self, 
        user_id: UUID, 
        name: str, 
        filter_definition: Dict,
        is_default: bool = False
    ) -> SavedFilter:
        """Create a new saved filter."""
        # If this is set as default, unset any existing default
        if is_default:
            await self._unset_default_filters(user_id)
            
        saved_filter = SavedFilter(
            user_id=user_id,
            name=name,
            filter_definition=filter_definition,
            is_default=is_default
        )
        
        self.db_session.add(saved_filter)
        await self.db_session.commit()
        await self.db_session.refresh(saved_filter)
        
        return saved_filter
    
    async def get_user_filters(self, user_id: UUID) -> List[SavedFilter]:
        """Get all saved filters for a user."""
        query = select(SavedFilter).where(SavedFilter.user_id == user_id)
        result = await self.db_session.execute(query)
        return result.scalars().all()
    
    async def get_filter_by_id(self, filter_id: UUID, user_id: UUID) -> Optional[SavedFilter]:
        """Get a saved filter by ID."""
        query = select(SavedFilter).where(
            SavedFilter.id == filter_id,
            SavedFilter.user_id == user_id
        )
        result = await self.db_session.execute(query)
        return result.scalars().first()
    
    async def delete_filter(self, filter_id: UUID, user_id: UUID) -> bool:
        """Delete a saved filter."""
        query = delete(SavedFilter).where(
            SavedFilter.id == filter_id,
            SavedFilter.user_id == user_id
        )
        result = await self.db_session.execute(query)
        await self.db_session.commit()
        
        return result.rowcount > 0
    
    async def _unset_default_filters(self, user_id: UUID) -> None:
        """Unset default flag for all user filters."""
        query = update(SavedFilter).where(
            SavedFilter.user_id == user_id,
            SavedFilter.is_default == True
        ).values(is_default=False)
        
        await self.db_session.execute(query)
```

## API Endpoints

The complete set of API endpoints for the filtering system:

```python
@router.post("/filters/saved", response_model=SavedFilterResponse)
async def create_saved_filter(
    filter_data: SavedFilterCreate,
    user = Depends(get_current_user),
    filter_service: SavedFilterService = Depends()
):
    """Create a new saved filter for the user."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    saved_filter = await filter_service.create_saved_filter(
        user_id=user.id,
        name=filter_data.name,
        filter_definition=filter_data.filter_definition.dict(),
        is_default=filter_data.is_default
    )
    
    return SavedFilterResponse.from_orm(saved_filter)

@router.get("/filters/saved", response_model=List[SavedFilterResponse])
async def get_saved_filters(
    user = Depends(get_current_user),
    filter_service: SavedFilterService = Depends()
):
    """Get all saved filters for the user."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    filters = await filter_service.get_user_filters(user.id)
    return [SavedFilterResponse.from_orm(f) for f in filters]

@router.get("/filters/saved/{filter_id}", response_model=SavedFilterResponse)
async def get_saved_filter(
    filter_id: UUID,
    user = Depends(get_current_user),
    filter_service: SavedFilterService = Depends()
):
    """Get a specific saved filter."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    saved_filter = await filter_service.get_filter_by_id(filter_id, user.id)
    if not saved_filter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved filter not found"
        )
    
    return SavedFilterResponse.from_orm(saved_filter)

@router.delete("/filters/saved/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_filter(
    filter_id: UUID,
    user = Depends(get_current_user),
    filter_service: SavedFilterService = Depends()
):
    """Delete a saved filter."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    deleted = await filter_service.delete_filter(filter_id, user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved filter not found"
        )
```

## Performance Considerations

The filtering system implements several optimizations:

1. **Database Indexing**
   - Indexes on commonly filtered fields
   - Composite indexes for frequent filter combinations
   - Partial indexes for common filter values

2. **Query Optimization**
   - Eager loading of related objects
   - Limit database round trips
   - Use windowing functions for efficient pagination

3. **Caching Strategy**
   - Cache common filter results
   - Cache user preference queries
   - Implement cache invalidation on data updates

4. **Limit Optimization**
   - Apply LIMIT and OFFSET at the database level
   - Implement cursor-based pagination for large result sets

## Security Considerations

1. **Input Validation**
   - Validate all filter parameters
   - Sanitize user input for SQL injection prevention
   - Implement rate limiting for filter API endpoints

2. **Authorization**
   - Check user permissions for accessing filter functionality
   - Validate user ownership of saved filters
   - Prevent access to other users' saved filters

3. **Data Protection**
   - Ensure filter definitions don't contain sensitive information
   - Apply appropriate access controls to filter storage

## Testing

The filtering system includes comprehensive tests:

```python
@pytest.mark.asyncio
async def test_category_filter():
    """Test filtering by category."""
    # Create test data
    await create_test_deals([
        {"title": "Test Deal 1", "category": "electronics"},
        {"title": "Test Deal 2", "category": "fashion"},
        {"title": "Test Deal 3", "category": "electronics"}
    ])
    
    # Create category filter
    filter_def = FilterDefinition(
        filter_type="category",
        operator="eq",
        value="electronics"
    )
    
    filter_group = FilterGroup(
        operator="AND",
        filters=[filter_def]
    )
    
    # Apply filter
    deals = await deal_service.search_deals(filter_group=filter_group)
    
    # Validate results
    assert len(deals) == 2
    assert all(deal.category == "electronics" for deal in deals)

@pytest.mark.asyncio
async def test_complex_filter():
    """Test complex filtering with multiple conditions."""
    # Create test data
    await create_test_deals([
        {"title": "Electronics Deal", "category": "electronics", "price_current": 100, "discount_percentage": 20},
        {"title": "Fashion Deal", "category": "fashion", "price_current": 50, "discount_percentage": 30},
        {"title": "Budget Electronics", "category": "electronics", "price_current": 30, "discount_percentage": 15},
        {"title": "Premium Fashion", "category": "fashion", "price_current": 200, "discount_percentage": 10}
    ])
    
    # Create complex filter: (category=electronics AND discount>=20) OR (price<=50)
    electronics_filter = FilterDefinition(
        filter_type="category",
        operator="eq",
        value="electronics"
    )
    
    discount_filter = FilterDefinition(
        filter_type="discount",
        operator="gte",
        value=20
    )
    
    price_filter = FilterDefinition(
        filter_type="price_range",
        operator="lte",
        value=50
    )
    
    # Group 1: category=electronics AND discount>=20
    group1 = FilterGroup(
        operator="AND",
        filters=[electronics_filter, discount_filter]
    )
    
    # Main group: group1 OR price<=50
    main_group = FilterGroup(
        operator="OR",
        filters=[group1, price_filter]
    )
    
    # Apply filter
    deals = await deal_service.search_deals(filter_group=main_group)
    
    # Validate results
    assert len(deals) == 3  # Should match 3 deals
    
    # Check each deal matches at least one condition
    for deal in deals:
        # Either (electronics AND discount>=20) OR (price<=50)
        assert (deal.category == "electronics" and deal.discount_percentage >= 20) or deal.price_current <= 50
```

## Future Enhancements

1. **AI-Powered Filter Suggestions**
   - Suggest filters based on user browsing history
   - Recommend filter combinations based on similar users
   - Automatically adjust filters based on result quality

2. **Natural Language Filtering**
   - Allow users to specify filters in natural language
   - Convert natural language queries to structured filters
   - Provide conversational filtering interface

3. **Visual Filter Builder**
   - Drag-and-drop filter builder interface
   - Filter templates for common use cases
   - Filter preview with result counts

4. **Advanced Filtering Capabilities**
   - Semantic similarity filtering
   - Time-based dynamic filters
   - Geo-location based filtering

5. **Collaborative Filtering**
   - Allow sharing of filter configurations
   - Implement community-contributed filter templates
   - Enable filter ratings and reviews 