# Deal Comparison Feature

## Overview

The Deal Comparison feature allows users to compare multiple deals side-by-side, analyzing various attributes such as price, features, value proposition, and availability. This powerful tool helps users make informed purchasing decisions by visualizing differences between similar products or services. This document outlines the architecture, implementation details, and API endpoints for the deal comparison functionality.

## Architecture

The deal comparison system is designed around several key components:

### Data Model

```sql
CREATE TABLE comparison_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    is_public BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE comparison_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comparison_id UUID NOT NULL REFERENCES comparison_sets(id) ON DELETE CASCADE,
    deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    highlight_color VARCHAR(20),
    user_rating INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(comparison_id, deal_id)
);

CREATE TABLE comparison_attributes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comparison_id UUID NOT NULL REFERENCES comparison_sets(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    importance INTEGER NOT NULL DEFAULT 5,
    attribute_type VARCHAR(50) NOT NULL DEFAULT 'text',
    position INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(comparison_id, name)
);

CREATE TABLE comparison_values (
    attribute_id UUID NOT NULL REFERENCES comparison_attributes(id) ON DELETE CASCADE,
    item_id UUID NOT NULL REFERENCES comparison_items(id) ON DELETE CASCADE,
    value TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (attribute_id, item_id)
);

CREATE INDEX ix_comparison_sets_user_id ON comparison_sets(user_id);
CREATE INDEX ix_comparison_items_comparison_id ON comparison_items(comparison_id);
CREATE INDEX ix_comparison_items_deal_id ON comparison_items(deal_id);
CREATE INDEX ix_comparison_attributes_comparison_id ON comparison_attributes(comparison_id);
```

### Key Features

1. **Flexible Comparison Structure**
   - Support for user-defined comparison categories
   - Customizable attributes and importance ratings
   - Both structured and unstructured comparison data
   - Multi-deal comparison (up to 10 items simultaneously)

2. **Intelligent Attribute Extraction**
   - Automatic identification of common attributes
   - Smart value extraction from deal descriptions
   - Normalization of differing units and formats
   - AI-assisted attribute completion for missing data

3. **Visual Comparison Tools**
   - Side-by-side comparison tables
   - Attribute-based heat maps
   - Value scoring and highlighting
   - Exportable comparison reports

## Implementation Details

### Attribute Extraction Process

The system extracts comparable attributes from deals using a combination of predefined templates and AI processing:

```python
from core.services.ai_service import AIService
from core.models.deals import Deal
from core.models.enums import DealCategory

async def extract_comparable_attributes(deal_ids: List[UUID], category: Optional[str] = None) -> Dict[str, List[Dict]]:
    """
    Extract comparable attributes from a set of deals.
    
    Args:
        deal_ids: List of deal IDs to compare
        category: Optional category to help with attribute extraction
        
    Returns:
        Dictionary of attribute names with extracted values for each deal
    """
    # Load deals
    deals = await Deal.filter(id__in=deal_ids).all()
    
    # Determine category if not provided
    if not category and deals:
        # Use most common category among deals
        categories = [deal.category for deal in deals if deal.category]
        if categories:
            from collections import Counter
            category = Counter(categories).most_common(1)[0][0]
    
    # Get attribute template for category
    attribute_template = await get_category_attribute_template(category)
    
    # Extract values using AI service for complex attributes
    ai_service = AIService()
    extracted_attributes = {}
    
    for attribute in attribute_template:
        attr_name = attribute["name"]
        extracted_attributes[attr_name] = []
        
        for deal in deals:
            # Try direct extraction from deal properties first
            if attr_name in deal.metadata:
                value = deal.metadata[attr_name]
            else:
                # Use AI to extract from description
                extraction_prompt = f"Extract the {attr_name} from this product description: {deal.description}"
                value = await ai_service.extract_attribute(extraction_prompt, attr_name)
            
            extracted_attributes[attr_name].append({
                "deal_id": str(deal.id),
                "value": value,
                "confidence": 0.9 if attr_name in deal.metadata else 0.7
            })
    
    return extracted_attributes
```

### Comparison Creation Process

1. User selects deals to compare
2. System identifies the common category
3. System suggests appropriate comparison attributes
4. User customizes attributes and importance weights
5. System extracts attribute values from deals
6. User can manually adjust extracted values
7. System calculates overall scores based on importance weights
8. Comparison is displayed and can be saved for future reference

### Value Normalization

To ensure fair comparisons, the system normalizes values across different formats and units:

```python
async def normalize_attribute_values(attribute_name: str, values: List[str]) -> List[Dict]:
    """Normalize attribute values to enable fair comparison."""
    normalized_values = []
    
    # Detect value type and units
    value_type, unit = detect_value_type_and_unit(values)
    
    for value in values:
        try:
            # Convert to standard format based on type
            if value_type == "price":
                # Extract numeric value and convert to float
                numeric_value = extract_numeric_value(value)
                normalized_values.append({
                    "original": value,
                    "normalized": float(numeric_value),
                    "unit": unit or "$",
                    "type": "price"
                })
            elif value_type == "dimension":
                # Convert dimensions to standard unit (mm)
                normalized = convert_dimension_to_mm(value)
                normalized_values.append({
                    "original": value,
                    "normalized": normalized,
                    "unit": "mm",
                    "type": "dimension"
                })
            # Handle other value types...
            else:
                # For text values, just use original
                normalized_values.append({
                    "original": value,
                    "normalized": value,
                    "unit": None,
                    "type": "text"
                })
        except Exception as e:
            # If normalization fails, keep original value
            normalized_values.append({
                "original": value,
                "normalized": value,
                "unit": None,
                "type": "text",
                "error": str(e)
            })
    
    return normalized_values
```

## API Endpoints

### Create Comparison

**Endpoint:** `POST /api/v1/comparisons`

**Request:**
```json
{
  "title": "Gaming Laptops Under $1500",
  "description": "Comparing mid-range gaming laptops with good battery life",
  "category": "laptops",
  "deal_ids": [
    "550e8400-e29b-41d4-a716-446655440000",
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002"
  ],
  "custom_attributes": [
    {
      "name": "Battery Life",
      "description": "Hours of battery life under normal usage",
      "importance": 7
    }
  ]
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "comparison_id": "650e8400-e29b-41d4-a716-446655440000",
    "title": "Gaming Laptops Under $1500",
    "items": [
      {
        "item_id": "750e8400-e29b-41d4-a716-446655440000",
        "deal_id": "550e8400-e29b-41d4-a716-446655440000",
        "deal_title": "Alienware m15 R6 Gaming Laptop",
        "position": 0
      },
      {
        "item_id": "750e8400-e29b-41d4-a716-446655440001",
        "deal_id": "550e8400-e29b-41d4-a716-446655440001",
        "deal_title": "ASUS ROG Strix G15 Gaming Laptop",
        "position": 1
      },
      {
        "item_id": "750e8400-e29b-41d4-a716-446655440002",
        "deal_id": "550e8400-e29b-41d4-a716-446655440002",
        "deal_title": "MSI Katana GF66 Gaming Laptop",
        "position": 2
      }
    ],
    "attributes": [
      {
        "attribute_id": "850e8400-e29b-41d4-a716-446655440000",
        "name": "Processor",
        "importance": 8,
        "position": 0
      },
      {
        "attribute_id": "850e8400-e29b-41d4-a716-446655440001",
        "name": "Graphics Card",
        "importance": 9,
        "position": 1
      },
      {
        "attribute_id": "850e8400-e29b-41d4-a716-446655440002",
        "name": "RAM",
        "importance": 7,
        "position": 2
      },
      {
        "attribute_id": "850e8400-e29b-41d4-a716-446655440003",
        "name": "Storage",
        "importance": 6,
        "position": 3
      },
      {
        "attribute_id": "850e8400-e29b-41d4-a716-446655440004",
        "name": "Battery Life",
        "importance": 7,
        "position": 4
      }
    ],
    "values": {
      "Processor": [
        {
          "item_id": "750e8400-e29b-41d4-a716-446655440000",
          "value": "Intel Core i7-11800H"
        },
        {
          "item_id": "750e8400-e29b-41d4-a716-446655440001",
          "value": "AMD Ryzen 9 5900HX"
        },
        {
          "item_id": "750e8400-e29b-41d4-a716-446655440002",
          "value": "Intel Core i7-11800H"
        }
      ],
      "Graphics Card": [
        {
          "item_id": "750e8400-e29b-41d4-a716-446655440000",
          "value": "NVIDIA GeForce RTX 3060"
        },
        {
          "item_id": "750e8400-e29b-41d4-a716-446655440001",
          "value": "NVIDIA GeForce RTX 3070"
        },
        {
          "item_id": "750e8400-e29b-41d4-a716-446655440002",
          "value": "NVIDIA GeForce RTX 3060"
        }
      ],
      // Other attributes...
    }
  }
}
```

### Get Comparison

**Endpoint:** `GET /api/v1/comparisons/{comparison_id}`

**Response:** Similar to creation response but includes any updated values.

### Update Comparison

**Endpoint:** `PATCH /api/v1/comparisons/{comparison_id}`

**Request:**
```json
{
  "title": "Updated Gaming Laptop Comparison",
  "add_items": [
    "550e8400-e29b-41d4-a716-446655440003"
  ],
  "remove_items": [
    "750e8400-e29b-41d4-a716-446655440002"
  ],
  "update_attributes": [
    {
      "attribute_id": "850e8400-e29b-41d4-a716-446655440001",
      "importance": 10
    }
  ],
  "add_attributes": [
    {
      "name": "Display",
      "importance": 8
    }
  ]
}
```

**Response:** Updated comparison details.

### List User Comparisons

**Endpoint:** `GET /api/v1/comparisons`

**Response:**
```json
{
  "status": "success",
  "data": {
    "items": [
      {
        "comparison_id": "650e8400-e29b-41d4-a716-446655440000",
        "title": "Gaming Laptops Under $1500",
        "description": "Comparing mid-range gaming laptops with good battery life",
        "category": "laptops",
        "item_count": 3,
        "created_at": "2023-11-20T14:30:00Z",
        "updated_at": "2023-11-21T10:15:00Z"
      },
      // More comparisons...
    ],
    "total": 5,
    "page": 1,
    "size": 20,
    "pages": 1
  }
}
```

### Delete Comparison

**Endpoint:** `DELETE /api/v1/comparisons/{comparison_id}`

**Response:**
```json
{
  "status": "success",
  "message": "Comparison has been deleted successfully"
}
```

## Frontend Implementation

### Comparison Component

```typescript
interface ComparisonProps {
  comparisonId?: string;
  initialDeals?: string[];
  onComparisonCreated?: (comparisonId: string) => void;
}

const DealComparison: React.FC<ComparisonProps> = ({ 
  comparisonId,
  initialDeals,
  onComparisonCreated 
}) => {
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Load or create comparison on mount
  useEffect(() => {
    const loadComparison = async () => {
      try {
        setLoading(true);
        
        if (comparisonId) {
          // Load existing comparison
          const data = await api.get(`/comparisons/${comparisonId}`);
          setComparison(data.data.data);
        } else if (initialDeals && initialDeals.length > 1) {
          // Create new comparison
          const data = await api.post('/comparisons', {
            title: "My Comparison",
            deal_ids: initialDeals
          });
          setComparison(data.data.data);
          onComparisonCreated?.(data.data.data.comparison_id);
        } else {
          setError("At least two deals are required for comparison");
        }
      } catch (err) {
        setError(`Error loading comparison: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };
    
    loadComparison();
  }, [comparisonId, initialDeals]);
  
  // Render comparison table
  const renderComparisonTable = () => {
    if (!comparison) return null;
    
    return (
      <div className="comparison-table">
        <div className="comparison-header">
          <div className="attribute-column">
            <h3>Attributes</h3>
          </div>
          {comparison.items.map(item => (
            <div key={item.item_id} className="item-column">
              <h3>{item.deal_title}</h3>
            </div>
          ))}
        </div>
        
        <div className="comparison-body">
          {comparison.attributes.map(attribute => (
            <div key={attribute.attribute_id} className="attribute-row">
              <div className="attribute-name">
                <span>{attribute.name}</span>
                <span className="importance">
                  {Array(attribute.importance).fill('•').join('')}
                </span>
              </div>
              
              {comparison.items.map(item => (
                <div key={item.item_id} className="attribute-value">
                  {findAttributeValue(attribute.name, item.item_id)}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  };
  
  // Helper to find attribute value for a specific item
  const findAttributeValue = (attributeName: string, itemId: string): string => {
    if (!comparison || !comparison.values[attributeName]) return 'N/A';
    
    const valueObj = comparison.values[attributeName]
      .find(v => v.item_id === itemId);
      
    return valueObj ? valueObj.value : 'N/A';
  };
  
  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message={error} />;
  
  return (
    <div className="deal-comparison">
      <h2>{comparison?.title || 'Deal Comparison'}</h2>
      {renderComparisonTable()}
      <ComparisonControls 
        comparison={comparison} 
        onUpdate={setComparison} 
      />
    </div>
  );
};
```

### Comparison Controls Component

```typescript
interface ComparisonControlsProps {
  comparison: Comparison | null;
  onUpdate: (updated: Comparison) => void;
}

const ComparisonControls: React.FC<ComparisonControlsProps> = ({
  comparison,
  onUpdate
}) => {
  if (!comparison) return null;
  
  const handleAddDeal = async () => {
    // Implementation to search and add deals
  };
  
  const handleRemoveDeal = async (itemId: string) => {
    try {
      await api.patch(`/comparisons/${comparison.comparison_id}`, {
        remove_items: [itemId]
      });
      
      // Reload comparison
      const data = await api.get(`/comparisons/${comparison.comparison_id}`);
      onUpdate(data.data.data);
    } catch (err) {
      // Handle error
    }
  };
  
  const handleAddAttribute = async () => {
    // Implementation to add custom attributes
  };
  
  const handleExportComparison = () => {
    // Implementation to export comparison as PDF/CSV
  };
  
  return (
    <div className="comparison-controls">
      <Button onClick={handleAddDeal}>Add Deal</Button>
      <Button onClick={handleAddAttribute}>Add Attribute</Button>
      <Button onClick={handleExportComparison}>Export</Button>
    </div>
  );
};
```

## Analytics

The comparison feature includes analytics to track:

1. **Comparison Creation Metrics**
   - Number of comparisons created
   - Average deals per comparison
   - Most commonly compared categories

2. **Usage Metrics**
   - Time spent viewing comparisons
   - Attribute customization frequency
   - Export and sharing actions

3. **Outcome Metrics**
   - Deals purchased after comparison
   - Comparison abandonment rate
   - Most influential attributes

## Testing

The comparison feature includes comprehensive tests:

1. **Unit Tests**
   - Attribute extraction accuracy
   - Value normalization
   - Scoring algorithms

2. **Integration Tests**
   - API endpoint functionality
   - Database operations
   - AI attribute extraction

3. **End-to-End Tests**
   - Complete comparison creation flow
   - UI rendering and interactions
   - Export functionality

## Future Enhancements

Planned enhancements to the comparison feature:

1. **Enhanced Visualization**
   - Interactive charts and graphs
   - Star ratings for quick visual scanning
   - Color-coded attribute importance

2. **AI-Powered Recommendations**
   - Intelligent deal recommendations
   - Personalized attribute importance based on user preferences
   - Automated "best value" identification

3. **Collaborative Comparisons**
   - Shared editing of comparison sets
   - Public comparison templates
   - Social voting on attribute importance

4. **Dynamic Market Updates**
   - Real-time price and availability tracking
   - Automatic price history incorporation
   - Alert when better deals become available

5. **Advanced Filtering**
   - Filter comparison items by specific attribute values
   - Hide/show attributes dynamically
   - Custom weighting systems 