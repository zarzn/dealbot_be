# Market Service Parameter Handling Fix

## Problem

The `MarketService.create_market` and `update_market` methods were passing all provided parameters directly to the `Market` model constructor via the repository's methods, resulting in errors when parameters like `timeout`, `retry_count`, and `retry_delay` were included - as they are not valid fields in the `Market` model.

## Root Cause

The service methods were not filtering parameters before passing them to the repository's methods, which directly use the parameters to instantiate or update a `Market` model. The `Market` model raises a `TypeError` when it receives parameters that don't correspond to its fields.

The tests were expecting the service to handle parameters like `timeout`, `retry_count`, and `retry_delay`, which should be stored in the `config` field of the `Market` model rather than as top-level fields.

## Implementation

The solution involved:

1. Added a filtering mechanism in both `MarketService.create_market` and `update_market` methods to identify valid model parameters and exclude others.
2. Implemented logic to move non-model parameters like `timeout`, `retry_count`, and `retry_delay` into the `config` dictionary as part of a `connection` sub-dictionary.
3. For `update_market`, added logic to preserve and merge with existing config values.
4. Updated the test to verify that:
   - Basic model fields are set correctly
   - Original config elements are preserved
   - Non-model parameters are stored in the `config.connection` section

## Code Changes

### MarketService Create Method Update

```python
# MarketService.create_market method
async def create_market(self, **kwargs) -> Market:
    try:
        # ... existing validation code ...
        
        # Filter out non-model parameters
        valid_model_params = {
            'id', 'name', 'type', 'description', 'api_endpoint', 'api_key', 'status',
            'config', 'rate_limit', 'is_active', 'error_count', 'requests_today',
            'total_requests', 'success_rate', 'avg_response_time', 'last_error',
            'last_error_at', 'last_successful_request', 'last_reset_at', 'created_at',
            'updated_at'
        }
        
        # Add non-model parameters to config if they exist
        config = kwargs.get('config', {}).copy() if kwargs.get('config') else {}
            
        # Store timeout, retry_count, retry_delay in config
        for param in ['timeout', 'retry_count', 'retry_delay']:
            if param in kwargs:
                config.setdefault('connection', {})
                config['connection'][param] = kwargs[param]
        
        # Update config in kwargs
        if config:
            kwargs['config'] = config
        
        # Filter kwargs to only include valid model parameters
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_model_params}

        # Create the market using filtered kwargs
        return await self.market_repository.create(filtered_kwargs)
    except Exception as e:
        raise ValidationError(f"Failed to create market: {str(e)}")
```

### MarketService Update Method Update

```python
# MarketService.update_market method
async def update_market(self, market_id: UUID, **kwargs) -> Market:
    try:
        market = await self.get_market(market_id)

        # Validate API credentials if provided
        api_credentials = kwargs.get('api_credentials')
        if api_credentials and market.type:
            self._validate_api_credentials(market.type, api_credentials)

        # Filter out non-model parameters
        valid_model_params = {
            'id', 'name', 'type', 'description', 'api_endpoint', 'api_key', 'status',
            'config', 'rate_limit', 'is_active', 'error_count', 'requests_today',
            'total_requests', 'success_rate', 'avg_response_time', 'last_error',
            'last_error_at', 'last_successful_request', 'last_reset_at', 'created_at',
            'updated_at'
        }
        
        # Handle config updates - merge with existing config if present
        if 'config' in kwargs:
            config = market.config.copy() if market.config else {}
            if isinstance(kwargs['config'], dict):
                # Update with new config values
                config.update(kwargs['config'])
                kwargs['config'] = config
        else:
            config = market.config.copy() if market.config else {}
            
        # Store timeout, retry_count, retry_delay in config
        connection_updated = False
        for param in ['timeout', 'retry_count', 'retry_delay']:
            if param in kwargs:
                config.setdefault('connection', {})
                config['connection'][param] = kwargs[param]
                connection_updated = True
        
        # Update config in kwargs if connection parameters were updated
        if connection_updated:
            kwargs['config'] = config
        
        # Filter kwargs to only include valid model parameters
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_model_params}

        # Update the market
        return await self.market_repository.update(market_id, **filtered_kwargs)
    except MarketNotFoundError:
        raise
    except Exception as e:
        raise ValidationError(f"Failed to update market: {str(e)}")
```

### Test Update

```python
# Updated test assertion section
assert market.name == market_data["name"]
assert market.type == market_data["type"]
assert market.status == market_data["status"]
assert market.rate_limit == market_data["rate_limit"]

# Check that the original config elements are present in the returned config
for key, value in market_data["config"].items():
    assert key in market.config
    assert market.config[key] == value

# Check that connection config contains the expected timeout, retry_count, and retry_delay
assert "connection" in market.config
assert market.config["connection"]["timeout"] == market_data["timeout"]
assert market.config["connection"]["retry_count"] == market_data["retry_count"]
assert market.config["connection"]["retry_delay"] == market_data["retry_delay"]
```

## Impact

- Tests now pass successfully
- Both `create_market` and `update_market` methods correctly handle non-model parameters 
- Connection-related parameters are stored in a standardized location in the config
- This provides a consistent interface for setting and retrieving connection parameters
- For updates, existing config values are preserved and merged with new values

## Next Steps

- Apply similar parameter filtering to other service methods that might need it
- Review other service classes for similar parameter handling issues
- Consider adding documentation about which parameters are stored as model fields vs. config fields
- Add a utility method to the service to standardize the parameter filtering logic 