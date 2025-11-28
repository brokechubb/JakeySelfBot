# Security Policy

## Supported Versions

Only the latest version of JakeySelfBot is supported. If you discover a security vulnerability in an older version, please upgrade to the latest version to see if the issue has already been addressed.

## Reporting a Vulnerability

If you discover a security vulnerability, please report it privately through one of these channels:

- Open an issue in the GitHub repository with a detailed description
- Contact the maintainers directly through GitHub

Please do not create a public GitHub issue for security vulnerabilities.

## Security Best Practices

When using JakeySelfBot, please follow these security best practices:

### For End Users

- Never commit your `.env` file with API keys to a public repository
- Store your Discord token securely and do not share it
- Review and understand all configuration options before running the bot
- Only grant admin privileges to trusted users
- Regularly update your API keys
- Keep your hosting environment secure

### Environment Variables

The application properly handles sensitive configuration through environment variables:

- All API keys and tokens should be stored in the `.env` file
- The `.gitignore` file is configured to exclude the `.env` file from version control
- Configuration options are validated during startup

### Data Protection

- No sensitive user data is collected or stored unnecessarily
- The local database only stores information required for bot functionality
- User messages and conversations are only stored locally
- Webhook URLs and tokens are stored encrypted when possible

## Known Security Considerations

- This is a self-bot, which violates Discord's Terms of Service - use at your own risk
- Always run the bot with API keys that have appropriate access restrictions
- Regular tokens should be used rather than owner-only tokens when possible
- Enable 2FA on accounts that interact with cryptocurrency features

## Data Privacy

JakeySelfBot stores data locally for functionality:
- Conversation history is stored locally for context
- User preferences are stored to personalize interactions
- No data is transmitted to external servers beyond configured API endpoints
- Users can clear any stored data through commands

## Code Security

The application follows these security practices:
- Input validation and sanitization
- Proper error handling without exposing sensitive information
- Secure API key handling
- No hardcoded credentials

## Audit

The codebase is designed to be auditable:
- All external API calls are logged in the code
- Configuration is centralized and reviewable
- Security-related changes are documented