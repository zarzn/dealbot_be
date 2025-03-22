"""Fix for sharing service to handle special types in JSON serialization."""

import re
import json
from datetime import datetime
from uuid import UUID

def fix_sharing_file():
    """Fix the sharing.py file to handle special types in JSON serialization."""
    target_file = '/app/core/services/sharing.py'
    
    # Read the original file
    with open(target_file, 'r') as f:
        content = f.read()
    
    # Update the DateTimeEncoder class to handle HttpUrl and other types
    datetime_encoder_pattern = re.compile(r'class DateTimeEncoder.*?def default\(self, obj\):.*?return super\(\)\.default\(obj\)', re.DOTALL)
    
    datetime_encoder_replacement = """class DateTimeEncoder(json.JSONEncoder):
    \"\"\"Custom JSON encoder that can handle datetime objects and other special types.\"\"\"
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, UUID):
            return str(obj)
        # Handle pydantic HttpUrl
        elif hasattr(obj, '__str__') and (hasattr(obj, 'host') or hasattr(obj, 'scheme')):
            return str(obj)
        # Handle any other objects with __dict__
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        return super().default(obj)"""
    
    # Replace the DateTimeEncoder class
    modified_content = re.sub(datetime_encoder_pattern, datetime_encoder_replacement, content)
    
    # Fix the deal serialization
    deal_pattern = re.compile(r'# Create content data including the deal snapshot\s+content_data = \{.*?"personal_notes": share_request\.personal_notes if share_request\.include_personal_notes else None\s+\}', re.DOTALL)
    
    deal_replacement = """# Create content data including the deal snapshot
            try:
                # First convert to dictionary
                deal_dict = deal_data.model_dump()
                # Ensure all values are JSON serializable
                content_data = {
                    "deal": deal_dict,
                    "personal_notes": share_request.personal_notes if share_request.include_personal_notes else None
                }
            except Exception as e:
                logger.error(f"Error creating content data: {str(e)}")
                raise ShareException(f"Failed to create shareable content: {str(e)}")"""
    
    # Replace the deal serialization code
    modified_content = re.sub(deal_pattern, deal_replacement, modified_content)
    
    # Fix the serialization before creating the SharedContent record
    serialize_pattern = re.compile(r'# Create the shared content record\s+try:\s+# Serialize content_data with the custom encoder that handles datetime objects\s+serialized_content_data = json\.loads\(json\.dumps\(content_data, cls=DateTimeEncoder\)\)')
    
    serialize_replacement = """# Create the shared content record
        try:
            # Serialize content_data with the custom encoder that handles datetime and HttpUrl objects
            try:
                serialized_content = json.dumps(content_data, cls=DateTimeEncoder)
                serialized_content_data = json.loads(serialized_content)
            except Exception as e:
                logger.error(f"Error serializing content data: {str(e)}")
                # Fallback - try stringifying problematic values
                sanitized_data = sanitize_for_json(content_data)
                serialized_content = json.dumps(sanitized_data)
                serialized_content_data = json.loads(serialized_content)"""
    
    # Replace the serialization code
    modified_content = re.sub(serialize_pattern, serialize_replacement, modified_content)
    
    # Add a helper function for sanitizing data
    if "def sanitize_for_json(" not in modified_content:
        sanitize_function = """
def sanitize_for_json(data):
    \"\"\"Recursively sanitize data to ensure it's JSON serializable.\"\"\"
    if isinstance(data, dict):
        return {k: sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_json(item) for item in data]
    elif isinstance(data, (datetime, UUID)):
        return str(data)
    elif hasattr(data, '__str__') and (hasattr(data, 'host') or hasattr(data, 'scheme')):
        return str(data)
    elif not isinstance(data, (str, int, float, bool, type(None))):
        return str(data)
    return data
"""
        # Insert the sanitize function before the SharingService class
        sharing_service_index = modified_content.find("class SharingService:")
        modified_content = modified_content[:sharing_service_index] + sanitize_function + modified_content[sharing_service_index:]
    
    # Write the modified content back to the file
    with open(target_file, 'w') as f:
        f.write(modified_content)
    
    print(f"Updated {target_file}")

if __name__ == "__main__":
    fix_sharing_file() 