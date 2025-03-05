# LLM and Auth Service Fixes

## Date: February 25, 2024

## Issues Fixed

1. **LLM Import Error in `core/utils/llm.py`**
   - **Problem**: The code was trying to import a non-existent `DeepSeek` class from `langchain_community.llms`. This was causing test failures across deal and goal services that depend on the LLM functionality.
   - **Fix**: Modified the LLM utility to use a fallback mechanism:
     - When DeepSeek is requested, the system now checks if OpenAI keys are available and uses ChatOpenAI as fallback
     - If no OpenAI keys are available, a MockLLM is used instead
     - Added appropriate logging when falling back to alternative models

2. **Missing `TokenErrorType` Enum in `core/models/auth_token.py`**
   - **Problem**: The auth service was referencing a `TokenErrorType` enum that wasn't defined anywhere, causing `NameError` during test execution.
   - **Fix**: Added the missing enum class to `auth_token.py`:
     ```python
     class TokenErrorType(str, enum.Enum):
         """Token error type enumeration."""
         INVALID = "invalid"
         EXPIRED = "expired"
         BLACKLISTED = "blacklisted"
         INVALID_TYPE = "invalid_type"
         MALFORMED = "malformed"
         MISSING = "missing"
         NOT_FOUND = "not_found"
         UNAUTHORIZED = "unauthorized"
     ```

3. **Missing `ExpiredSignatureError` import in `core/services/auth.py`**
   - **Problem**: The auth service was using `ExpiredSignatureError` but didn't import it from the jose library.
   - **Fix**: Added the missing import:
     ```python
     from jose import JWTError, jwt, ExpiredSignatureError
     ```
   - Also updated the import statement for `TokenErrorType` in auth.py

## Tests Affected

These fixes address multiple test failures:

1. LLM-related test failures in:
   - `backend_tests/services/test_deal_service.py`
   - `backend_tests/services/test_goal_service.py`

2. Auth service test failures in:
   - `backend_tests/services/test_auth_service.py`
   - `backend_tests/services/test_user/test_auth_service.py`

## Implementation Notes

1. The DeepSeek integration seems to be planned for the future but not currently available in langchain_community. The fixes maintain compatibility with the planned implementation while ensuring the system works with current dependencies.

2. The token-related fixes ensure proper exception handling in authentication flows, particularly when dealing with expired or invalid tokens.

## Related Configuration

The system appears to be designed with multiple LLM providers in mind:
- DeepSeek as the primary model (production)
- GPT-4 as a fallback option
- MockLLM for testing

The configuration-based approach makes it easy to switch between these options without code changes. 