# Deal Export Functionality

## Overview

The AI Agentic Deals System offers robust export functionality that allows users to extract, download, and share deal data in various formats. This feature enables users to maintain records of deals, perform offline analysis, and integrate deal data with external tools and systems.

## Core Export Capabilities

### 1. Data Export Formats

The system supports exporting deal data in the following formats:

- **CSV**: Comma-separated values for spreadsheet applications
- **JSON**: Structured data for programmatic processing
- **PDF**: Formatted documents with deal details and visualizations
- **Excel**: Native Excel files with formatted data and multiple sheets

### 2. Export Scopes

Users can export data at different scopes depending on their needs:

- **Single Deal Export**: Detailed information about a specific deal
- **Multiple Deal Export**: Selected deals in a comparison or collection
- **Search Results Export**: All deals matching a search query
- **Dashboard Export**: Current dashboard view with visualizations
- **Analytics Export**: Reports and insights based on deal analysis

### 3. Customization Options

Export operations can be customized with various options:

- **Field Selection**: Choose which data fields to include in exports
- **Date Range Filtering**: Export deals from a specific time period
- **Format Customization**: Control headers, ordering, and data formatting
- **Metadata Inclusion**: Option to include or exclude system metadata
- **Template Selection**: Use predefined templates for PDF exports

## Implementation Details

### Data Model

```sql
-- Export templates
CREATE TABLE export_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    format VARCHAR(20) NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    configuration JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Export history
CREATE TABLE export_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    export_type VARCHAR(50) NOT NULL,
    format VARCHAR(20) NOT NULL,
    item_count INTEGER NOT NULL,
    configuration JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    file_size INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE
);
```

### Export Service

The primary implementation of export functionality is in the `ExportService` class:

```python
class ExportService:
    """Service for handling export operations."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.file_service = FileService()
    
    async def export_deals(
        self,
        user_id: UUID,
        deal_ids: List[UUID],
        format: str,
        options: ExportOptions
    ) -> ExportResult:
        """
        Export deals to the specified format.
        
        Args:
            user_id: User ID requesting the export
            deal_ids: List of deal IDs to export
            format: Export format (csv, json, pdf, excel)
            options: Export configuration options
            
        Returns:
            ExportResult with file details and download URL
        """
        # Validate permissions
        await self._validate_export_permissions(user_id, deal_ids)
        
        # Retrieve deal data
        deals = await self._get_deal_data(deal_ids, options)
        
        # Apply field selection and filtering
        filtered_data = self._apply_export_filters(deals, options)
        
        # Generate export in requested format
        file_data = await self._generate_export_file(filtered_data, format, options)
        
        # Store file and record export history
        file_id = await self.file_service.store_file(file_data, f"export.{format}")
        await self._record_export(user_id, "deals", format, len(deal_ids), options)
        
        # Generate download URL
        download_url = await self.file_service.get_download_url(file_id)
        
        return ExportResult(
            file_id=file_id,
            download_url=download_url,
            format=format,
            item_count=len(deal_ids)
        )
    
    async def export_search_results(
        self,
        user_id: UUID,
        search_params: dict,
        format: str,
        options: ExportOptions
    ) -> ExportResult:
        """Export search results to the specified format."""
        # Implementation details...
    
    async def export_dashboard(
        self,
        user_id: UUID,
        dashboard_id: UUID,
        format: str,
        options: ExportOptions
    ) -> ExportResult:
        """Export dashboard to the specified format."""
        # Implementation details...
    
    async def get_export_templates(
        self,
        user_id: UUID
    ) -> List[ExportTemplate]:
        """Get available export templates for user."""
        # Implementation details...
    
    # Private helper methods
    async def _validate_export_permissions(self, user_id: UUID, deal_ids: List[UUID]) -> None:
        """Validate user has permission to export the specified deals."""
        # Implementation details...
    
    async def _get_deal_data(self, deal_ids: List[UUID], options: ExportOptions) -> List[dict]:
        """Retrieve full deal data for export."""
        # Implementation details...
    
    def _apply_export_filters(self, deals: List[dict], options: ExportOptions) -> List[dict]:
        """Apply field selection and filtering based on options."""
        # Implementation details...
    
    async def _generate_export_file(self, data: List[dict], format: str, options: ExportOptions) -> bytes:
        """Generate file in the requested format."""
        if format == "csv":
            return self._generate_csv(data, options)
        elif format == "json":
            return self._generate_json(data, options)
        elif format == "pdf":
            return await self._generate_pdf(data, options)
        elif format == "excel":
            return self._generate_excel(data, options)
        else:
            raise UnsupportedFormatError(f"Format '{format}' is not supported")
    
    async def _record_export(self, user_id: UUID, export_type: str, format: str, item_count: int, options: ExportOptions) -> None:
        """Record export operation in history."""
        # Implementation details...
```

## API Endpoints

### Export Deals

**Endpoint:** `POST /api/v1/exports/deals`

**Request:**
```json
{
  "deal_ids": ["550e8400-e29b-41d4-a716-446655440000", "550e8400-e29b-41d4-a716-446655440001"],
  "format": "csv",
  "options": {
    "fields": ["title", "description", "current_price", "original_price", "discount_percent", "url", "expires_at"],
    "include_metadata": false,
    "filename": "my_deals_export",
    "template_id": null
  }
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "file_id": "550e8400-e29b-41d4-a716-446655440002",
    "download_url": "https://example.com/download/550e8400-e29b-41d4-a716-446655440002",
    "format": "csv",
    "item_count": 2,
    "expires_at": "2023-12-31T23:59:59Z"
  }
}
```

### Export Search Results

**Endpoint:** `POST /api/v1/exports/search`

**Request:**
```json
{
  "search_params": {
    "query": "gaming laptop",
    "price_range": [500, 1200],
    "categories": ["electronics", "computers"],
    "min_discount": 20
  },
  "format": "excel",
  "options": {
    "include_images": true,
    "max_items": 100,
    "sheet_name": "Gaming Laptops"
  }
}
```

**Response:** Similar to the deals export response

### Get Export Templates

**Endpoint:** `GET /api/v1/exports/templates`

**Response:**
```json
{
  "status": "success",
  "data": {
    "templates": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440003",
        "name": "Detailed Deal Report",
        "description": "Comprehensive deal report with all details and price history",
        "format": "pdf",
        "is_public": true,
        "created_at": "2023-11-01T10:00:00Z"
      },
      {
        "id": "550e8400-e29b-41d4-a716-446655440004",
        "name": "Price Comparison Sheet",
        "description": "Simple price comparison with basic details",
        "format": "excel",
        "is_public": false,
        "created_at": "2023-11-15T14:30:00Z"
      }
    ]
  }
}
```

## Frontend Components

### Export Button Component

```tsx
interface ExportButtonProps {
  dealIds?: string[];
  searchParams?: Record<string, any>;
  dashboardId?: string;
  onExportComplete?: (result: ExportResult) => void;
}

const ExportButton: React.FC<ExportButtonProps> = ({
  dealIds,
  searchParams,
  dashboardId,
  onExportComplete
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState<string>("csv");
  const [options, setOptions] = useState<ExportOptions>({
    fields: ["title", "current_price", "original_price", "discount_percent", "url"],
    include_metadata: false
  });
  
  const handleExport = async () => {
    setIsLoading(true);
    try {
      let result;
      
      if (dealIds && dealIds.length > 0) {
        result = await api.post("/api/v1/exports/deals", {
          deal_ids: dealIds,
          format: selectedFormat,
          options
        });
      } else if (searchParams) {
        result = await api.post("/api/v1/exports/search", {
          search_params: searchParams,
          format: selectedFormat,
          options
        });
      } else if (dashboardId) {
        result = await api.post(`/api/v1/exports/dashboard/${dashboardId}`, {
          format: selectedFormat,
          options
        });
      }
      
      if (result && result.data.status === "success") {
        // Trigger download
        window.location.href = result.data.data.download_url;
        
        if (onExportComplete) {
          onExportComplete(result.data.data);
        }
        
        setIsOpen(false);
      }
    } catch (error) {
      console.error("Export failed", error);
      // Show error notification
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <>
      <Button 
        onClick={() => setIsOpen(true)}
        icon="download"
        variant="outline"
      >
        Export
      </Button>
      
      <Modal 
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Export Data"
      >
        <div className="export-options">
          <div className="format-selector">
            <Label>Export Format</Label>
            <RadioGroup
              value={selectedFormat}
              onChange={(value) => setSelectedFormat(value)}
              options={[
                { value: "csv", label: "CSV" },
                { value: "json", label: "JSON" },
                { value: "pdf", label: "PDF" },
                { value: "excel", label: "Excel" }
              ]}
            />
          </div>
          
          <div className="field-selector">
            <Label>Fields to Include</Label>
            <CheckboxGroup
              values={options.fields}
              onChange={(values) => setOptions({...options, fields: values})}
              options={[
                { value: "title", label: "Title" },
                { value: "description", label: "Description" },
                { value: "current_price", label: "Current Price" },
                { value: "original_price", label: "Original Price" },
                { value: "discount_percent", label: "Discount %" },
                { value: "url", label: "URL" },
                { value: "expires_at", label: "Expiration Date" }
                // Additional fields...
              ]}
            />
          </div>
          
          <div className="additional-options">
            <Switch
              label="Include Metadata"
              checked={options.include_metadata}
              onChange={(checked) => setOptions({...options, include_metadata: checked})}
            />
            
            {selectedFormat === "pdf" && (
              <TemplateSelector
                onChange={(templateId) => setOptions({...options, template_id: templateId})}
              />
            )}
          </div>
          
          <div className="actions">
            <Button 
              onClick={() => setIsOpen(false)}
              variant="outline"
            >
              Cancel
            </Button>
            <Button 
              onClick={handleExport}
              variant="primary"
              isLoading={isLoading}
            >
              Export
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};
```

## Security Considerations

### 1. Access Control
- Validate that users can only export deals they have access to
- Implement rate limiting for export operations
- Add throttling for large exports

### 2. File Security
- Generate temporary, expiring download URLs
- Encrypt sensitive data in exports
- Validate and sanitize all user inputs

### 3. Data Protection
- Allow users to control what data is included in exports
- Anonymize personal information when appropriate
- Maintain audit logs of all export operations

## Performance Considerations

### 1. Asynchronous Processing
- Process large exports asynchronously using background jobs
- Notify users when large exports are complete
- Implement pagination for large data sets

### 2. Resource Management
- Limit maximum export size based on user tier
- Add timeouts for export generation
- Apply appropriate caching for frequent exports

### 3. File Generation Optimization
- Stream large file generation to avoid memory issues
- Use efficient libraries for file format generation
- Compress large exports automatically

## Analytics and Metrics

The system tracks the following export-related metrics:

1. **Usage Metrics**
   - Exports by format
   - Average export size
   - Most frequently exported data

2. **Performance Metrics**
   - Export generation time
   - Download completion rate
   - Error rate by format

## Testing Requirements

### Functional Testing
- Verify all export formats generate valid files
- Test with various data selections and options
- Ensure proper error handling for invalid inputs

### Performance Testing
- Test with large datasets
- Measure response times for different export sizes
- Verify memory usage during large exports

### Security Testing
- Validate access control mechanisms
- Test encryption and URL security
- Verify rate limiting effectiveness

## Future Enhancements

1. **Additional Export Formats**
   - XML for enterprise integration
   - Google Sheets direct export
   - Markdown for text-based documentation

2. **Enhanced Visualization**
   - Interactive charts in PDF exports
   - Custom branding for exports
   - Rich text formatting options

3. **Integration Capabilities**
   - Direct export to cloud storage (Dropbox, Google Drive)
   - Scheduled automatic exports
   - Webhook notifications for completed exports 