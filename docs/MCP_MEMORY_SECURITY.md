# MCP Memory Server Security Documentation

## 🔒 Security Vulnerability Fixed

**CRITICAL SECURITY ISSUE RESOLVED**: The MCP Memory Server previously had no authentication mechanism, allowing anyone with network access to read and write all user memories without authorization.

## 🛡️ Security Implementation

### Authentication System

The MCP Memory Server now implements a secure authentication system with the following features:

1. **Cryptographically Secure Token Generation**
   - Uses `secrets.token_urlsafe(32)` for secure random token generation
   - Each server instance generates a unique authentication token
   - Tokens are sufficiently long and random to prevent brute force attacks

2. **Bearer Token Authentication**
   - All API endpoints (except health check) require Bearer token authentication
   - Tokens are validated using constant-time comparison to prevent timing attacks
   - Proper 401 Unauthorized responses for invalid/missing tokens

3. **Secure Token Storage**
   - Tokens are stored in `.mcp_token` file with restrictive permissions (0o600)
   - Tokens are also available via `MCP_MEMORY_TOKEN` environment variable
   - Automatic cleanup of token files on server shutdown

4. **Backward Compatibility**
   - Graceful degradation when authentication is not available
   - Fallback to SQLite database when MCP server is unavailable
   - Maintains existing functionality while adding security

## 🔧 Implementation Details

### Server-Side Changes (`tools/mcp_memory_server.py`)

```python
class MCPMemoryServer:
    def __init__(self, port=None):
        # ... existing initialization ...
        self.auth_token = self._generate_auth_token()
        self.token_file = os.path.join(os.path.dirname(__file__), "..", ".mcp_token")
        self.setup_middleware()

    def _generate_auth_token(self) -> str:
        """Generate a cryptographically secure authentication token"""
        return secrets.token_urlsafe(32)

    @web.middleware
    async def auth_middleware(self, request, handler):
        """Authentication middleware to validate Bearer tokens"""
        # Allow health check without authentication
        if request.path == "/health":
            return await handler(request)
        
        # Extract and validate Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return web.json_response(
                {"error": "Missing or invalid Authorization header"}, 
                status=401
            )
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        if not self._validate_token(token):
            return web.json_response(
                {"error": "Invalid authentication token"}, 
                status=401
            )
        
        return await handler(request)
```

### Client-Side Changes (`tools/mcp_memory_client.py`)

```python
def get_mcp_auth_token():
    """Get the MCP authentication token from file or environment"""
    # First try environment variable
    token = os.environ.get("MCP_MEMORY_TOKEN")
    if token:
        return token
    
    # Then try token file
    token_file = os.path.join(os.path.dirname(__file__), '..', '.mcp_token')
    if os.path.exists(token_file):
        try:
            with open(token_file, 'r') as f:
                return f.read().strip()
        except Exception as e:
            logging.warning(f"Failed to read MCP token file: {e}")
    
    return None

class MCPMemoryClient:
    def __init__(self, server_url: Optional[str] = None, auth_token: Optional[str] = None):
        self.server_url = server_url or get_mcp_server_url()
        self.auth_token = auth_token or get_mcp_auth_token()
        # ... rest of initialization ...

    async def _make_request(self, endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated HTTP request to MCP memory server"""
        # Prepare headers with authentication
        headers = {}
        if self.auth_token and endpoint != "health":  # Don't send auth for health check
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        # Make request and handle 401 responses
        # ... request implementation ...
```

## 🚀 Usage

### Starting the Server

The MCP Memory Server automatically generates and manages authentication tokens:

```bash
python tools/mcp_memory_server.py
```

Output:
```
INFO: Starting MCP Memory Server on localhost:8501
INFO: Port 8501 saved to .mcp_port
INFO: Authentication token saved to .mcp_token
INFO: Authentication token: abc123def456... (keep this secret!)
INFO: MCP Memory Server started successfully with authentication enabled
```

### Client Configuration

The MCP Memory Client automatically discovers and uses authentication tokens:

```python
from tools.mcp_memory_client import MCPMemoryClient

# Client will automatically find and use authentication token
async with MCPMemoryClient() as client:
    if await client.check_connection():
        result = await client.remember_user_info("user123", "preferences", "likes crypto")
```

### Manual Token Management

For custom implementations, you can manually specify the authentication token:

```python
# Using environment variable
export MCP_MEMORY_TOKEN="your_generated_token"

# Using explicit token
client = MCPMemoryClient(auth_token="your_generated_token")
```

## 🔍 Security Testing

Comprehensive security tests are included in `tests/test_mcp_memory_security.py`:

```bash
python -m tests.test_mcp_memory_security
```

Tests cover:
- ✅ Authentication token generation
- ✅ Token file creation with proper permissions
- ✅ Environment variable token retrieval
- ✅ File-based token retrieval
- ✅ Client initialization with authentication
- ✅ Authentication error handling
- ✅ Token validation
- ✅ Graceful degradation without authentication
- ✅ Backward compatibility

## 🛡️ Security Best Practices

1. **Token Security**
   - Never commit authentication tokens to version control
   - Use restrictive file permissions (0o600) for token files
   - Rotate tokens periodically for long-running servers
   - Monitor logs for authentication failures

2. **Network Security**
   - Run MCP server on localhost only (default behavior)
   - Use firewall rules to restrict access if binding to external interfaces
   - Consider using reverse proxy with additional authentication layers

3. **Monitoring**
   - Monitor authentication failure logs
   - Set up alerts for suspicious authentication patterns
   - Regular security audits of token storage and usage

## 🔙 Backward Compatibility

The authentication system maintains full backward compatibility:

- **Existing functionality preserved**: All existing MCP memory operations work unchanged
- **Graceful degradation**: System falls back to SQLite when MCP is unavailable
- **Automatic token discovery**: No manual configuration required for standard usage
- **Fallback mechanisms**: Multiple token discovery methods (environment, file)

## 🚨 Security Considerations

### Threats Mitigated

1. **Unauthorized Access**: Authentication prevents unauthorized read/write access to memories
2. **Data Tampering**: Token-based authentication prevents malicious memory modification
3. **Information Disclosure**: Secure token storage prevents token leakage
4. **Timing Attacks**: Constant-time token comparison prevents timing-based attacks

### Remaining Considerations

1. **Network Eavesdropping**: Use HTTPS for production deployments over networks
2. **Token Rotation**: Implement token rotation for long-running production servers
3. **Rate Limiting**: Consider implementing rate limiting for authentication attempts
4. **Audit Logging**: Implement comprehensive audit logging for security events

## 📋 Migration Guide

### For Existing Users

1. **No action required** - Authentication is automatically handled
2. **Update startup scripts** - New authentication logs will appear
3. **Monitor logs** - Watch for authentication-related messages
4. **Test functionality** - Run existing tests to ensure compatibility

### For New Deployments

1. **Standard deployment** - Authentication works automatically
2. **Custom configurations** - Use environment variables or explicit tokens
3. **Security hardening** - Review security best practices above
4. **Monitoring setup** - Implement security monitoring and alerting

## 🔧 Troubleshooting

### Common Issues

1. **Authentication Failed Errors**
   - Check that server and client are using the same token
   - Verify token file permissions and accessibility
   - Ensure token file exists and contains valid token

2. **Token File Issues**
   - Check file permissions (should be 0o600)
   - Verify file path accessibility
   - Ensure token file is not corrupted

3. **Connection Issues**
   - Verify MCP server is running and accessible
   - Check port file contains correct port number
   - Ensure no firewall blocking connections

### Debug Steps

1. Check server logs for authentication messages
2. Verify token file creation and contents
3. Test with explicit token configuration
4. Monitor client connection and authentication attempts

## 📞 Support

For security-related issues or questions:

1. Review this documentation thoroughly
2. Check security test results
3. Examine server and client logs
4. Verify token generation and storage
5. Test authentication flow step by step

**Security is a shared responsibility - keep your authentication tokens secure and monitor for suspicious activity.**