"""Secure credential management for Clarify Data Bridge integration.

This module provides secure storage, validation, and management of Clarify.io
API credentials with support for OAuth 2.0 client credentials flow.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, TYPE_CHECKING

from homeassistant.helpers.storage import Store

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Storage version for credential data
CREDENTIAL_STORAGE_VERSION = 1
CREDENTIAL_STORAGE_KEY = "clarify_credentials"


class CredentialType(Enum):
    """Supported credential types."""

    OAUTH2_CLIENT_CREDENTIALS = "oauth2_client_credentials"
    API_KEY = "api_key"  # Legacy support


class CredentialStatus(Enum):
    """Status of credentials."""

    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"
    REVOKED = "revoked"
    PENDING_VALIDATION = "pending_validation"


@dataclass
class CredentialValidationResult:
    """Result of credential validation."""

    status: CredentialStatus
    is_valid: bool
    message: str
    validated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    error_details: str | None = None


@dataclass
class OAuth2Credentials:
    """OAuth 2.0 client credentials.

    Attributes:
        client_id: OAuth 2.0 client ID
        client_secret: OAuth 2.0 client secret
        integration_id: Clarify integration ID
        access_token: Current access token (if obtained)
        token_expires_at: Token expiration time
        refresh_token: Refresh token (if available)
        token_type: Token type (usually "Bearer")
        scope: OAuth scopes granted
    """

    client_id: str
    client_secret: str
    integration_id: str
    access_token: str | None = None
    token_expires_at: datetime | None = None
    refresh_token: str | None = None
    token_type: str = "Bearer"
    scope: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_validated: datetime | None = None

    def is_token_expired(self) -> bool:
        """Check if access token is expired."""
        if not self.access_token or not self.token_expires_at:
            return True
        # Add 5-minute buffer before expiration
        return datetime.utcnow() >= (self.token_expires_at - timedelta(minutes=5))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "integration_id": self.integration_id,
            "access_token": self.access_token,
            "token_expires_at": (
                self.token_expires_at.isoformat() if self.token_expires_at else None
            ),
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "scope": self.scope,
            "created_at": self.created_at.isoformat(),
            "last_validated": (
                self.last_validated.isoformat() if self.last_validated else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OAuth2Credentials:
        """Create from dictionary."""
        return cls(
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            integration_id=data["integration_id"],
            access_token=data.get("access_token"),
            token_expires_at=(
                datetime.fromisoformat(data["token_expires_at"])
                if data.get("token_expires_at")
                else None
            ),
            refresh_token=data.get("refresh_token"),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope"),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_validated=(
                datetime.fromisoformat(data["last_validated"])
                if data.get("last_validated")
                else None
            ),
        )


class CredentialManager:
    """Secure credential management for Clarify integration.

    Handles storage, validation, and lifecycle management of API credentials
    with support for OAuth 2.0 and token refresh.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize credential manager.

        Args:
            hass: Home Assistant instance
        """
        self.hass = hass
        self._store = Store(
            hass,
            CREDENTIAL_STORAGE_VERSION,
            CREDENTIAL_STORAGE_KEY,
        )
        self._credentials: dict[str, OAuth2Credentials] = {}
        self._validation_cache: dict[str, CredentialValidationResult] = {}

        _LOGGER.info("Credential manager initialized")

    async def async_load(self) -> None:
        """Load credentials from secure storage."""
        try:
            data = await self._store.async_load()
            if data:
                for entry_id, cred_data in data.get("credentials", {}).items():
                    try:
                        self._credentials[entry_id] = OAuth2Credentials.from_dict(
                            cred_data
                        )
                        _LOGGER.debug(
                            "Loaded credentials for entry: %s",
                            self._mask_entry_id(entry_id),
                        )
                    except Exception as err:
                        _LOGGER.error(
                            "Failed to load credentials for entry %s: %s",
                            self._mask_entry_id(entry_id),
                            err,
                        )
                _LOGGER.info(
                    "Loaded %d credential set(s) from secure storage",
                    len(self._credentials),
                )
        except Exception as err:
            _LOGGER.error("Failed to load credentials from storage: %s", err)

    async def async_save(self) -> None:
        """Save credentials to secure storage."""
        try:
            data = {
                "credentials": {
                    entry_id: creds.to_dict()
                    for entry_id, creds in self._credentials.items()
                }
            }
            await self._store.async_save(data)
            _LOGGER.debug("Credentials saved to secure storage")
        except Exception as err:
            _LOGGER.error("Failed to save credentials: %s", err)
            raise

    async def async_store_credentials(
        self, entry_id: str, credentials: OAuth2Credentials
    ) -> None:
        """Store credentials for a config entry.

        Args:
            entry_id: Config entry ID
            credentials: Credentials to store
        """
        self._credentials[entry_id] = credentials
        await self.async_save()
        _LOGGER.info(
            "Stored credentials for entry: %s", self._mask_entry_id(entry_id)
        )

    async def async_get_credentials(
        self, entry_id: str
    ) -> OAuth2Credentials | None:
        """Retrieve credentials for a config entry.

        Args:
            entry_id: Config entry ID

        Returns:
            Credentials if found, None otherwise
        """
        return self._credentials.get(entry_id)

    async def async_delete_credentials(self, entry_id: str) -> None:
        """Delete credentials for a config entry.

        Args:
            entry_id: Config entry ID
        """
        if entry_id in self._credentials:
            del self._credentials[entry_id]
            await self.async_save()
            _LOGGER.info(
                "Deleted credentials for entry: %s", self._mask_entry_id(entry_id)
            )

    async def async_validate_credentials(
        self,
        credentials: OAuth2Credentials,
        api_url: str | None = None,
        force_refresh: bool = False,
    ) -> CredentialValidationResult:
        """Validate credentials by testing API connection.

        Args:
            credentials: Credentials to validate
            api_url: Optional API URL to use for validation
            force_refresh: Force validation even if cached result exists

        Returns:
            Validation result
        """
        # Generate cache key
        cache_key = self._generate_credential_hash(credentials)

        # Check cache
        if not force_refresh and cache_key in self._validation_cache:
            cached = self._validation_cache[cache_key]
            # Cache for 5 minutes
            if (datetime.utcnow() - cached.validated_at) < timedelta(minutes=5):
                _LOGGER.debug("Using cached validation result")
                return cached

        _LOGGER.info("Validating credentials...")

        try:
            # Import here to avoid circular dependency
            from .clarify_client import ClarifyClient

            # Create temporary client for validation
            client = ClarifyClient(
                hass=self.hass,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                integration_id=credentials.integration_id,
                api_url=api_url or "https://api.clarify.cloud/v1/",
            )

            # Attempt connection
            await client.async_connect()
            await client.async_verify_connection()

            # Validation successful
            result = CredentialValidationResult(
                status=CredentialStatus.VALID,
                is_valid=True,
                message="Credentials validated successfully",
                validated_at=datetime.utcnow(),
            )

            # Update last validated time
            credentials.last_validated = datetime.utcnow()

            # Cache result
            self._validation_cache[cache_key] = result

            _LOGGER.info("Credential validation successful")
            return result

        except Exception as err:
            error_msg = str(err).lower()

            # Determine status based on error
            if "401" in error_msg or "unauthorized" in error_msg:
                status = CredentialStatus.INVALID
                message = "Invalid credentials - authentication failed"
            elif "403" in error_msg or "forbidden" in error_msg:
                status = CredentialStatus.REVOKED
                message = "Credentials revoked or insufficient permissions"
            else:
                status = CredentialStatus.INVALID
                message = f"Validation failed: {str(err)}"

            result = CredentialValidationResult(
                status=status,
                is_valid=False,
                message=message,
                error_details=str(err),
            )

            _LOGGER.warning("Credential validation failed: %s", message)
            return result

    def validate_credential_format(
        self, client_id: str, client_secret: str, integration_id: str
    ) -> tuple[bool, str]:
        """Validate credential format before attempting connection.

        Args:
            client_id: Client ID to validate
            client_secret: Client secret to validate
            integration_id: Integration ID to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        errors = []

        # Client ID validation
        if not client_id or len(client_id.strip()) == 0:
            errors.append("Client ID is required")
        elif len(client_id) < 10:
            errors.append("Client ID appears too short (minimum 10 characters)")

        # Client secret validation
        if not client_secret or len(client_secret.strip()) == 0:
            errors.append("Client secret is required")
        elif len(client_secret) < 20:
            errors.append("Client secret appears too short (minimum 20 characters)")

        # Integration ID validation
        if not integration_id or len(integration_id.strip()) == 0:
            errors.append("Integration ID is required")
        # Check for valid Clarify integration ID format (alphanumeric, 20-36 chars)
        elif not re.match(
            r"^[0-9a-zA-Z]{20,36}$",
            integration_id.strip(),
        ):
            errors.append(
                "Integration ID must be a valid Clarify integration ID "
                "(20-36 alphanumeric characters)"
            )

        if errors:
            return False, "; ".join(errors)

        return True, "Credential format is valid"

    async def async_update_token(
        self,
        entry_id: str,
        access_token: str,
        expires_in: int,
        refresh_token: str | None = None,
    ) -> None:
        """Update OAuth 2.0 access token.

        Args:
            entry_id: Config entry ID
            access_token: New access token
            expires_in: Token lifetime in seconds
            refresh_token: Optional refresh token
        """
        credentials = self._credentials.get(entry_id)
        if not credentials:
            _LOGGER.error(
                "Cannot update token - credentials not found for entry: %s",
                self._mask_entry_id(entry_id),
            )
            return

        credentials.access_token = access_token
        credentials.token_expires_at = datetime.utcnow() + timedelta(
            seconds=expires_in
        )
        if refresh_token:
            credentials.refresh_token = refresh_token

        await self.async_save()

        _LOGGER.info(
            "Updated access token for entry %s (expires in %d seconds)",
            self._mask_entry_id(entry_id),
            expires_in,
        )

    async def async_rotate_credentials(
        self,
        entry_id: str,
        new_client_id: str,
        new_client_secret: str,
    ) -> bool:
        """Rotate credentials for a config entry.

        Args:
            entry_id: Config entry ID
            new_client_id: New client ID
            new_client_secret: New client secret

        Returns:
            True if rotation successful
        """
        credentials = self._credentials.get(entry_id)
        if not credentials:
            _LOGGER.error(
                "Cannot rotate credentials - not found for entry: %s",
                self._mask_entry_id(entry_id),
            )
            return False

        # Validate new credentials format
        is_valid, error_msg = self.validate_credential_format(
            new_client_id, new_client_secret, credentials.integration_id
        )
        if not is_valid:
            _LOGGER.error("New credentials validation failed: %s", error_msg)
            return False

        # Store old credentials temporarily for rollback
        old_client_id = credentials.client_id
        old_client_secret = credentials.client_secret

        try:
            # Update credentials
            credentials.client_id = new_client_id
            credentials.client_secret = new_client_secret
            credentials.access_token = None
            credentials.token_expires_at = None

            # Validate new credentials
            result = await self.async_validate_credentials(credentials, force_refresh=True)

            if result.is_valid:
                await self.async_save()
                _LOGGER.info(
                    "Credentials rotated successfully for entry: %s",
                    self._mask_entry_id(entry_id),
                )
                return True
            else:
                # Rollback on validation failure
                credentials.client_id = old_client_id
                credentials.client_secret = old_client_secret
                _LOGGER.error("New credentials validation failed - rolled back")
                return False

        except Exception as err:
            # Rollback on error
            credentials.client_id = old_client_id
            credentials.client_secret = old_client_secret
            _LOGGER.error("Credential rotation failed: %s - rolled back", err)
            return False

    def get_credential_status(self, entry_id: str) -> dict[str, Any]:
        """Get comprehensive status of credentials.

        Args:
            entry_id: Config entry ID

        Returns:
            Status dictionary
        """
        credentials = self._credentials.get(entry_id)
        if not credentials:
            return {
                "exists": False,
                "message": "Credentials not found",
            }

        status = {
            "exists": True,
            "created_at": credentials.created_at.isoformat(),
            "last_validated": (
                credentials.last_validated.isoformat()
                if credentials.last_validated
                else None
            ),
            "has_access_token": credentials.access_token is not None,
            "token_expired": credentials.is_token_expired(),
            "token_expires_at": (
                credentials.token_expires_at.isoformat()
                if credentials.token_expires_at
                else None
            ),
            "has_refresh_token": credentials.refresh_token is not None,
            "integration_id": credentials.integration_id,
            "client_id_prefix": self._mask_string(credentials.client_id),
        }

        # Check validation cache
        cache_key = self._generate_credential_hash(credentials)
        if cache_key in self._validation_cache:
            cached = self._validation_cache[cache_key]
            status["last_validation_result"] = {
                "status": cached.status.value,
                "is_valid": cached.is_valid,
                "message": cached.message,
                "validated_at": cached.validated_at.isoformat(),
            }

        return status

    @staticmethod
    def _generate_credential_hash(credentials: OAuth2Credentials) -> str:
        """Generate hash of credentials for caching.

        Args:
            credentials: Credentials to hash

        Returns:
            Hash string
        """
        data = f"{credentials.client_id}:{credentials.client_secret}:{credentials.integration_id}"
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def _mask_string(value: str, visible_chars: int = 4) -> str:
        """Mask sensitive string for logging.

        Args:
            value: String to mask
            visible_chars: Number of characters to show at start

        Returns:
            Masked string
        """
        if not value:
            return "***"
        if len(value) <= visible_chars:
            return "*" * len(value)
        return f"{value[:visible_chars]}{'*' * (len(value) - visible_chars)}"

    @staticmethod
    def _mask_entry_id(entry_id: str) -> str:
        """Mask config entry ID for logging.

        Args:
            entry_id: Entry ID to mask

        Returns:
            Masked entry ID
        """
        return CredentialManager._mask_string(entry_id, 8)


class SecureLogger:
    """Logger wrapper that automatically masks sensitive data."""

    def __init__(self, logger: logging.Logger) -> None:
        """Initialize secure logger.

        Args:
            logger: Underlying logger instance
        """
        self._logger = logger
        # Patterns to detect and mask sensitive data
        self._sensitive_patterns = [
            (re.compile(r'"client_id"\s*:\s*"([^"]+)"'), r'"client_id": "****"'),
            (
                re.compile(r'"client_secret"\s*:\s*"([^"]+)"'),
                r'"client_secret": "****"',
            ),
            (re.compile(r'"access_token"\s*:\s*"([^"]+)"'), r'"access_token": "****"'),
            (
                re.compile(r'"refresh_token"\s*:\s*"([^"]+)"'),
                r'"refresh_token": "****"',
            ),
            (re.compile(r"client_id=([^\s,]+)"), r"client_id=****"),
            (re.compile(r"client_secret=([^\s,]+)"), r"client_secret=****"),
            (re.compile(r"access_token=([^\s,]+)"), r"access_token=****"),
            (re.compile(r"Authorization:\s*Bearer\s+([^\s]+)"), r"Authorization: Bearer ****"),
        ]

    def _mask_message(self, message: str) -> str:
        """Mask sensitive data in message.

        Args:
            message: Message to mask

        Returns:
            Masked message
        """
        for pattern, replacement in self._sensitive_patterns:
            message = pattern.sub(replacement, message)
        return message

    def debug(self, message: str, *args, **kwargs) -> None:
        """Log debug message with masking."""
        self._logger.debug(self._mask_message(message), *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        """Log info message with masking."""
        self._logger.info(self._mask_message(message), *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        """Log warning message with masking."""
        self._logger.warning(self._mask_message(message), *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        """Log error message with masking."""
        self._logger.error(self._mask_message(message), *args, **kwargs)


def create_secure_logger(name: str) -> SecureLogger:
    """Create a secure logger that masks sensitive data.

    Args:
        name: Logger name

    Returns:
        Secure logger instance
    """
    return SecureLogger(logging.getLogger(name))
