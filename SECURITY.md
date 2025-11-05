# Security and Privacy Guide

Comprehensive guide to Phase 8 security features: Credential Management, OAuth 2.0 Token Handling, and Secure Storage.

## Overview

Phase 8 implements enterprise-grade security features for the Clarify Data Bridge integration:

1. **Credential Management** - Secure storage and lifecycle management
2. **OAuth 2.0 Token Refresh** - Automatic token renewal and monitoring
3. **Secure Logging** - Automatic masking of sensitive data
4. **Credential Validation** - Multi-stage validation with detailed feedback

---

## Phase 8.1: Credential Management

### Secure Storage

All credentials are stored using Home Assistant's encrypted storage system with additional security layers:

- **Encrypted at rest**: Home Assistant's Storage API automatically encrypts data
- **In-memory protection**: Credentials are only loaded when needed
- **Automatic cleanup**: Credentials are removed on integration unload

### Credential Types Supported

| Type | Description | Use Case |
|------|-------------|----------|
| **OAuth 2.0 Client Credentials** | Modern OAuth 2.0 flow | Recommended for all new integrations |
| **API Key** (Legacy) | Simple API key authentication | Legacy support only |

### Credential Lifecycle

```python
from .credential_manager import CredentialManager, OAuth2Credentials

# 1. Initialize manager
credential_manager = CredentialManager(hass)
await credential_manager.async_load()

# 2. Create credentials
credentials = OAuth2Credentials(
    client_id="your-client-id",
    client_secret="your-client-secret",
    integration_id="your-integration-id",
)

# 3. Store securely
await credential_manager.async_store_credentials(entry_id, credentials)

# 4. Retrieve when needed
credentials = await credential_manager.async_get_credentials(entry_id)

# 5. Delete on unload
await credential_manager.async_delete_credentials(entry_id)
```

### Credential Validation

Multi-stage validation ensures credentials are valid before use:

#### Stage 1: Format Validation

Validates credential format without making API calls:

```python
is_valid, error_msg = credential_manager.validate_credential_format(
    client_id, client_secret, integration_id
)
```

**Format Requirements:**
- **Client ID**: Minimum 10 characters
- **Client Secret**: Minimum 20 characters
- **Integration ID**: Valid UUID format (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)

**Example Errors:**
```
"Client ID appears too short (minimum 10 characters)"
"Client secret is required"
"Integration ID must be a valid UUID format"
```

#### Stage 2: Connection Test

Tests actual API connection with credentials:

```python
result = await credential_manager.async_validate_credentials(credentials)

if result.is_valid:
    print(f"✅ {result.message}")
else:
    print(f"❌ {result.message}")
    print(f"Status: {result.status.value}")
    print(f"Details: {result.error_details}")
```

**Validation Results:**
- `VALID` - Credentials work correctly
- `INVALID` - Authentication failed (401)
- `REVOKED` - Credentials revoked or no permission (403)
- `EXPIRED` - Token expired (automatic refresh triggered)

#### Stage 3: Caching

Validation results are cached for 5 minutes to reduce API calls:

```python
# First call - validates against API
result1 = await credential_manager.async_validate_credentials(credentials)

# Second call within 5 minutes - uses cache
result2 = await credential_manager.async_validate_credentials(credentials)

# Force refresh
result3 = await credential_manager.async_validate_credentials(
    credentials, force_refresh=True
)
```

### Credential Rotation

Safely rotate credentials without downtime:

```python
success = await credential_manager.async_rotate_credentials(
    entry_id,
    new_client_id="new-client-id",
    new_client_secret="new-client-secret",
)

if success:
    print("✅ Credentials rotated successfully")
else:
    print("❌ Rotation failed - old credentials still active")
```

**Rotation Process:**
1. Validate new credential format
2. Test new credentials against API
3. If valid: Update stored credentials
4. If invalid: Rollback to old credentials
5. Return success/failure status

**Use Cases:**
- Security policy requires periodic rotation
- Credentials compromised
- Migrating to new Clarify integration

### Credential Status Monitoring

Get comprehensive credential status:

```python
status = credential_manager.get_credential_status(entry_id)

print(f"Exists: {status['exists']}")
print(f"Created: {status['created_at']}")
print(f"Last Validated: {status['last_validated']}")
print(f"Has Access Token: {status['has_access_token']}")
print(f"Token Expired: {status['token_expired']}")
print(f"Client ID: {status['client_id_prefix']}...")  # Masked
```

**Example Output:**
```json
{
  "exists": true,
  "created_at": "2024-01-15T10:30:00Z",
  "last_validated": "2024-01-15T14:25:00Z",
  "has_access_token": true,
  "token_expired": false,
  "token_expires_at": "2024-01-15T15:30:00Z",
  "has_refresh_token": false,
  "integration_id": "12345678-1234-1234-1234-123456789abc",
  "client_id_prefix": "abcd****",
  "last_validation_result": {
    "status": "valid",
    "is_valid": true,
    "message": "Credentials validated successfully",
    "validated_at": "2024-01-15T14:25:00Z"
  }
}
```

---

## OAuth 2.0 Token Management

### Automatic Token Refresh

The integration automatically monitors and refreshes OAuth 2.0 tokens:

**Configuration:**
- **Refresh Buffer**: 5 minutes before expiration
- **Check Interval**: Every 5 minutes
- **Max Retries**: 3 attempts
- **Retry Delay**: 30 seconds between attempts

**How It Works:**

```
Token Lifetime: ──────────────────────────────────────────────
                |                                    |       |
                ├────────────────────────────────────┤───────┤
                Created                   Refresh    Expires
                                         (at -5min)

Timeline:
08:00 - Token obtained (expires at 09:00)
08:50 - Monitor detects expiration in 10 minutes
08:55 - Refresh triggered (5 minutes before expiration)
08:55 - New token obtained (expires at 09:55)
```

### Token Manager

```python
from .oauth2_handler import OAuth2TokenManager

# Initialize
token_manager = OAuth2TokenManager(hass, credential_manager)

# Register credentials for monitoring
await token_manager.async_register_credentials(entry_id, credentials)

# Start monitoring
await token_manager.async_start()

# Register callback for post-refresh actions
def on_token_refreshed():
    print("✅ Token refreshed - reconnecting services")

token_manager.register_refresh_callback(entry_id, on_token_refreshed)

# Force immediate refresh
success = await token_manager.async_force_refresh(entry_id)

# Get token status
status = token_manager.get_token_status(entry_id)
print(f"Time until expiry: {status['time_until_expiry_seconds']}s")
print(f"Expires soon: {status['expires_soon']}")
print(f"Refresh in progress: {status['refresh_in_progress']}")

# Stop monitoring
await token_manager.async_stop()
```

### Refresh Callbacks

Register callbacks to be notified when tokens are refreshed:

```python
async def reconnect_services():
    """Reconnect services after token refresh."""
    print("Token refreshed - updating connections")
    await coordinator.reconnect()

token_manager.register_refresh_callback(entry_id, reconnect_services)
```

**Use Cases:**
- Reconnect API clients after token refresh
- Update dependent services
- Log token refresh events
- Trigger health checks

### Token Refresh Failures

If token refresh fails after all retries:

```python
from .oauth2_handler import TokenRefreshError

try:
    await token_manager.async_force_refresh(entry_id)
except TokenRefreshError as err:
    print(f"❌ Token refresh failed: {err}")
    # Notify user
    # Trigger re-authentication flow
```

**Failure Scenarios:**
- Network connectivity issues
- Credentials revoked
- Clarify.io API downtime
- Rate limiting

**Recovery Actions:**
1. Log error with details
2. Fire `clarify_data_bridge_health_status_changed` event
3. Update health monitor status
4. Notify user via Home Assistant notification
5. Retry on next check interval

---

## Secure Logging

### Automatic Sensitive Data Masking

All logs automatically mask sensitive information:

```python
from .credential_manager import create_secure_logger

_LOGGER = create_secure_logger(__name__)

# These log messages are automatically masked
_LOGGER.info("Client ID: abc123secret")
# Output: Client ID: abc1****

_LOGGER.debug('{"client_secret": "supersecret123"}')
# Output: {"client_secret": "****"}

_LOGGER.error("Auth failed with access_token=Bearer abc123xyz")
# Output: Auth failed with access_token=Bearer ****
```

### Masked Patterns

The secure logger automatically masks:

| Pattern | Example | Masked Output |
|---------|---------|---------------|
| `client_id` | `client_id=abc123secret` | `client_id=****` |
| `client_secret` | `client_secret=xyz789` | `client_secret=****` |
| `access_token` | `access_token=Bearer abc` | `access_token=****` |
| `refresh_token` | `refresh_token=def456` | `refresh_token=****` |
| `Authorization` header | `Authorization: Bearer xyz` | `Authorization: Bearer ****` |
| JSON credentials | `{"client_id": "abc"}` | `{"client_id": "****"}` |

### Using Secure Logger

Replace standard logger with secure logger:

**Before:**
```python
import logging

_LOGGER = logging.getLogger(__name__)

_LOGGER.info(f"Credentials: {credentials}")
# ⚠️ Logs sensitive data!
```

**After:**
```python
from .credential_manager import create_secure_logger

_LOGGER = create_secure_logger(__name__)

_LOGGER.info(f"Credentials: {credentials}")
# ✅ Automatically masked
```

### Manual Masking

For explicit masking:

```python
from .credential_manager import CredentialManager

# Mask string
masked = CredentialManager._mask_string("supersecret123", visible_chars=4)
print(masked)  # Output: "supe****"

# Mask entry ID
masked_id = CredentialManager._mask_entry_id("12345678abcdefgh")
print(masked_id)  # Output: "12345678****"
```

---

## Integration with Home Assistant

### Setup Flow

When users configure the integration:

```
1. User enters credentials
     ↓
2. Format validation
     ├─ Invalid → Show error message
     └─ Valid → Continue
     ↓
3. Connection test
     ├─ Failed → Show specific error
     └─ Success → Continue
     ↓
4. Store credentials securely
     ↓
5. Initialize token manager
     ↓
6. Start monitoring
```

### Configuration Flow Enhancement

The configuration flow now provides detailed validation feedback:

**Format Errors:**
```
❌ Client ID appears too short (minimum 10 characters)
```

**Connection Errors:**
```
❌ Authentication failed - please verify your credentials
❌ Integration ID not found - check your Clarify.io dashboard
❌ Network connection failed - check internet connectivity
```

**Success:**
```
✅ Successfully connected to Clarify.io
```

### Entry Management

Credentials are automatically managed throughout the entry lifecycle:

```python
# Setup
async def async_setup_entry(hass, entry):
    # 1. Load credential manager
    credential_manager = CredentialManager(hass)
    await credential_manager.async_load()

    # 2. Store credentials
    credentials = OAuth2Credentials(...)
    await credential_manager.async_store_credentials(entry.entry_id, credentials)

    # 3. Start token monitoring
    token_manager = OAuth2TokenManager(hass, credential_manager)
    await token_manager.async_start()

    return True

# Unload
async def async_unload_entry(hass, entry):
    # 1. Stop token manager
    await token_manager.async_stop()

    # 2. Delete credentials
    await credential_manager.async_delete_credentials(entry.entry_id)

    return True
```

---

## Best Practices

### 1. Credential Storage

**✅ DO:**
- Use OAuth 2.0 Client Credentials (not API keys)
- Store credentials via CredentialManager
- Delete credentials on integration unload
- Rotate credentials periodically

**❌ DON'T:**
- Store credentials in plain text
- Log full credentials
- Share credentials between integrations
- Hardcode credentials

### 2. Token Management

**✅ DO:**
- Let the token manager handle refresh automatically
- Register refresh callbacks for dependent services
- Monitor token expiration status
- Handle TokenRefreshError gracefully

**❌ DON'T:**
- Implement custom token refresh logic
- Disable automatic token monitoring
- Ignore token expiration
- Make API calls with expired tokens

### 3. Logging

**✅ DO:**
- Use `create_secure_logger()` for all modules
- Log validation failures with masked details
- Include request IDs (not credentials) for debugging
- Log token refresh events (not token values)

**❌ DON'T:**
- Use standard `logging.getLogger()`
- Log full credential objects
- Include tokens in error messages
- Log API request/response bodies with credentials

### 4. Error Handling

**✅ DO:**
- Catch specific exceptions (InvalidAuth, CannotConnect)
- Provide user-friendly error messages
- Log technical details (masked) for debugging
- Implement retry logic with exponential backoff

**❌ DON'T:**
- Catch generic `Exception` without re-raising
- Show technical error messages to users
- Retry infinitely without backoff
- Log full exception stack traces with credentials

### 5. Validation

**✅ DO:**
- Validate format before API calls
- Cache validation results (5 minutes)
- Force refresh after credential rotation
- Provide specific format error messages

**❌ DON'T:**
- Skip format validation
- Validate on every API call
- Assume credentials are valid indefinitely
- Show generic "invalid credentials" errors

---

## Security Checklist

Use this checklist when implementing or auditing security:

### Credential Management
- [ ] Credentials stored using CredentialManager
- [ ] Credentials deleted on integration unload
- [ ] Format validation before connection test
- [ ] Connection test with detailed error handling
- [ ] Credential rotation supported
- [ ] Status monitoring implemented

### Token Management
- [ ] OAuth2TokenManager initialized and started
- [ ] Token expiration monitored (5-minute buffer)
- [ ] Automatic refresh enabled
- [ ] Refresh callbacks registered for dependent services
- [ ] TokenRefreshError handled gracefully
- [ ] Token manager stopped on unload

### Logging
- [ ] All modules use `create_secure_logger()`
- [ ] No credentials in log messages
- [ ] No tokens in error messages
- [ ] Entry IDs masked in logs
- [ ] API request/response bodies sanitized

### Configuration Flow
- [ ] Multi-stage validation in config flow
- [ ] User-friendly error messages
- [ ] Technical details logged (masked)
- [ ] Validation cache implemented
- [ ] Secure credential entry (password fields)

### Integration Lifecycle
- [ ] Credentials loaded on setup
- [ ] Token monitoring started on setup
- [ ] Dependent services updated on token refresh
- [ ] Token monitoring stopped on unload
- [ ] Credentials deleted on unload

---

## Troubleshooting

### Problem: "Client ID appears too short"

**Cause**: Client ID format validation failed

**Solution:**
1. Check Client ID from Clarify.io dashboard
2. Ensure you're copying the full ID (no trailing spaces)
3. Client ID should be at least 10 characters

---

### Problem: "Authentication failed - verify credentials"

**Cause**: API rejected credentials (401)

**Solution:**
1. Verify Client ID and Client Secret from Clarify.io
2. Check Integration ID is correct
3. Ensure credentials haven't been revoked
4. Try generating new credentials in Clarify.io

---

### Problem: "Token refresh failed after 3 attempts"

**Cause**: Token refresh unsuccessful

**Solutions:**
1. Check network connectivity
2. Verify credentials haven't been revoked:
   ```python
   status = credential_manager.get_credential_status(entry_id)
   if status['last_validation_result']['status'] == 'revoked':
       # Credentials revoked - need to reconfigure
   ```
3. Check Clarify.io API status
4. Force refresh manually:
   ```python
   await token_manager.async_force_refresh(entry_id)
   ```
5. If all fails, reconfigure integration with new credentials

---

### Problem: Credentials visible in logs

**Cause**: Not using secure logger

**Solution:**
Replace logger:
```python
# Before
import logging
_LOGGER = logging.getLogger(__name__)

# After
from .credential_manager import create_secure_logger
_LOGGER = create_secure_logger(__name__)
```

---

### Problem: "Integration ID must be a valid UUID format"

**Cause**: Integration ID format invalid

**Solution:**
1. Get Integration ID from Clarify.io dashboard
2. Format should be: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
3. Example: `12345678-1234-1234-1234-123456789abc`
4. Copy exactly as shown (including hyphens)

---

## Advanced Topics

### Custom Credential Validation

Implement custom validation logic:

```python
from .credential_manager import CredentialValidationResult, CredentialStatus

class CustomValidator:
    async def async_validate(self, credentials):
        # Custom validation logic
        if not self._check_custom_rule(credentials):
            return CredentialValidationResult(
                status=CredentialStatus.INVALID,
                is_valid=False,
                message="Custom validation failed",
                error_details="Specific error details",
            )

        # Continue with standard validation
        return await credential_manager.async_validate_credentials(credentials)
```

### Multiple Integrations

Manage credentials for multiple Clarify integrations:

```python
# Store credentials for multiple entries
for entry_id, creds in multiple_credentials.items():
    await credential_manager.async_store_credentials(entry_id, creds)
    await token_manager.async_register_credentials(entry_id, creds)

# Monitor all tokens
await token_manager.async_start()
```

### Credential Import/Export

**⚠️ WARNING**: Only use for migration or backup

```python
# Export (encrypted)
credentials = await credential_manager.async_get_credentials(entry_id)
encrypted_backup = encrypt_credentials(credentials)

# Import (from encrypted backup)
credentials = decrypt_credentials(encrypted_backup)
await credential_manager.async_store_credentials(new_entry_id, credentials)
```

---

## Summary

Phase 8 Security and Privacy provides:

✅ **Credential Management**:
- Secure encrypted storage
- Multi-stage validation (format + connection)
- Credential rotation without downtime
- Comprehensive status monitoring

✅ **OAuth 2.0 Token Management**:
- Automatic token refresh (5-minute buffer)
- Monitoring every 5 minutes
- Retry logic with exponential backoff
- Refresh callbacks for dependent services

✅ **Secure Logging**:
- Automatic masking of sensitive data
- 8 patterns for credential detection
- Easy integration (`create_secure_logger()`)
- Manual masking utilities

✅ **Best Practices**:
- Security checklist for auditing
- Comprehensive troubleshooting guide
- Advanced topics for customization
- Integration lifecycle management

For more information:
- Configuration: [CONFIG.md](CONFIG.md)
- Advanced Features: [ADVANCED_FEATURES.md](ADVANCED_FEATURES.md)
- Performance: [PERFORMANCE_TUNING.md](PERFORMANCE_TUNING.md)
