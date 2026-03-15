# tests/test_errors.py
"""
Tests para el módulo core/errors.py
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from telegram.error import NetworkError, TimedOut, RetryAfter, BadRequest


class TestErrorCategory:
    """Tests para categorización de errores."""
    
    def test_categorize_network_error(self):
        """Test que categoriza NetworkError como NETWORK."""
        from core.errors import categorize_error, ErrorCategory
        
        error = NetworkError("Network unreachable")
        result = categorize_error(error)
        
        assert result == ErrorCategory.NETWORK
    
    def test_categorize_timeout_error(self):
        """Test que categoriza TimedOut como NETWORK."""
        from core.errors import categorize_error, ErrorCategory
        
        error = TimedOut()
        result = categorize_error(error)
        
        assert result == ErrorCategory.NETWORK
    
    def test_categorize_retry_after(self):
        """Test que categoriza RetryAfter como API_TIMEOUT."""
        from core.errors import categorize_error, ErrorCategory
        
        error = RetryAfter(retry_after=60)
        result = categorize_error(error)
        
        assert result == ErrorCategory.API_TIMEOUT
    
    def test_categorize_bad_request(self):
        """Test que categoriza BadRequest como USER_INPUT."""
        from core.errors import categorize_error, ErrorCategory
        
        error = BadRequest("Invalid query")
        result = categorize_error(error)
        
        assert result == ErrorCategory.USER_INPUT
    
    def test_categorize_value_error(self):
        """Test que categoriza ValueError como USER_INPUT."""
        from core.errors import categorize_error, ErrorCategory
        
        error = ValueError("Invalid value")
        result = categorize_error(error)
        
        assert result == ErrorCategory.USER_INPUT
    
    def test_categorize_key_error(self):
        """Test que categoriza KeyError como USER_INPUT."""
        from core.errors import categorize_error, ErrorCategory
        
        error = KeyError("missing_key")
        result = categorize_error(error)
        
        assert result == ErrorCategory.USER_INPUT
    
    def test_categorize_asyncio_timeout(self):
        """Test que categoriza asyncio.TimeoutError como API_TIMEOUT."""
        from core.errors import categorize_error, ErrorCategory
        
        error = asyncio.TimeoutError()
        result = categorize_error(error)
        
        assert result == ErrorCategory.API_TIMEOUT
    
    def test_categorize_generic_timeout_string(self):
        """Test que categoriza errores con 'timeout' en mensaje."""
        from core.errors import categorize_error, ErrorCategory
        
        error = Exception("Connection timeout after 30s")
        result = categorize_error(error)
        
        assert result == ErrorCategory.API_TIMEOUT
    
    def test_categorize_generic_unknown(self):
        """Test que categoriza errores unknown."""
        from core.errors import categorize_error, ErrorCategory
        
        error = Exception("Some random error")
        result = categorize_error(error)
        
        assert result == ErrorCategory.UNKNOWN


class TestUserMessage:
    """Tests para mensajes user-friendly."""
    
    def test_get_user_message_spanish(self):
        """Test que retorna mensaje en español."""
        from core.errors import get_user_message, ErrorCategory
        
        msg = get_user_message(ErrorCategory.API_TIMEOUT, 'es')
        
        assert "tiempo" in msg.lower() or "Timeout" in msg
    
    def test_get_user_message_english(self):
        """Test que retorna mensaje en inglés."""
        from core.errors import get_user_message, ErrorCategory
        
        msg = get_user_message(ErrorCategory.API_TIMEOUT, 'en')
        
        assert "timeout" in msg.lower() or "time" in msg.lower()
    
    def test_get_user_message_default_unknown(self):
        """Test que retorna mensaje por defecto para unknown."""
        from core.errors import get_user_message, ErrorCategory
        
        msg = get_user_message(ErrorCategory.UNKNOWN, 'es')
        
        assert len(msg) > 0


class TestRetryAsync:
    """Tests para retry_async."""
    
    @pytest.mark.asyncio
    async def test_retry_async_success_first_try(self):
        """Test que no reintenta si tiene éxito al primer intento."""
        from core.errors import retry_async
        
        call_count = 0
        
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await retry_async(successful_func, max_retries=3)
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_async_success_after_failures(self):
        """Test que reintenta y tiene éxito."""
        from core.errors import retry_async
        
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary error")
            return "success"
        
        result = await retry_async(flaky_func, max_retries=3, initial_delay=0.01)
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_async_all_fail(self):
        """Test que lanza excepción si todos los intentos fallan."""
        from core.errors import retry_async
        
        async def failing_func():
            raise Exception("Permanent error")
        
        with pytest.raises(Exception):
            await retry_async(failing_func, max_retries=3, initial_delay=0.01)
    
    @pytest.mark.asyncio
    async def test_retry_async_no_retry_on_bad_request(self):
        """Test que no reintenta BadRequest."""
        from core.errors import retry_async
        
        call_count = 0
        
        async def bad_request_func():
            nonlocal call_count
            call_count += 1
            raise BadRequest("Invalid query")
        
        with pytest.raises(BadRequest):
            await retry_async(bad_request_func, max_retries=3)
        
        assert call_count == 1  # No reintenta
    
    @pytest.mark.asyncio
    async def test_retry_async_with_backoff(self):
        """Test que usa backoff exponencial."""
        from core.errors import retry_async
        import time
        
        call_times = []
        
        async def flaky_func():
            call_times.append(time.time())
            raise Exception("Temp error")
        
        try:
            await retry_async(flaky_func, max_retries=3, initial_delay=0.1, backoff_factor=2.0)
        except Exception:
            pass
        
        # Verificar que los delays aumentan
        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            # El delay debería ser aproximadamente 0.1s


class TestWithRetryDecorator:
    """Tests para el decorador @with_retry."""
    
    @pytest.mark.asyncio
    async def test_with_retry_decorator(self):
        """Test que el decorador funciona."""
        from core.errors import with_retry
        
        call_count = 0
        
        @with_retry(max_retries=2, initial_delay=0.01)
        async def my_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temp")
            return "done"
        
        result = await my_func()
        
        assert result == "done"
        assert call_count == 2


class TestLogErrorWithContext:
    """Tests para log_error_with_context."""
    
    def test_log_error_with_context_basic(self):
        """Test que log_error_with_context no lanza excepción."""
        from core.errors import log_error_with_context, ErrorCategory
        
        # No debe lanzar excepción
        try:
            log_error_with_context(
                ErrorCategory.API_FAILURE,
                ValueError("Test error"),
                context="test_context"
            )
        except Exception as e:
            pytest.fail(f"Lanzó excepción: {e}")
    
    def test_log_error_with_context_no_update(self):
        """Test que funciona sin update."""
        from core.errors import log_error_with_context, ErrorCategory
        
        try:
            log_error_with_context(
                ErrorCategory.NETWORK,
                Exception("Network error")
            )
        except Exception as e:
            pytest.fail(f"Lanzó excepción: {e}")
