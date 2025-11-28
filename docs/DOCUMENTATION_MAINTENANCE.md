# Documentation Maintenance Guide

This guide provides a comprehensive workflow for maintaining Jakey's documentation to ensure it stays synchronized with the codebase and remains accurate, useful, and up-to-date.

## Overview

Jakey's documentation is a critical component of the project that requires regular maintenance to reflect changes in features, commands, and system architecture. This guide establishes processes and tools for keeping documentation current.

## Maintenance Workflow

### 1. Regular Documentation Audits

#### Monthly Reviews
- **Command Synchronization**: Verify all commands in `bot/commands.py` are documented
- **Feature Completeness**: Check for new features lacking documentation
- **Link Validation**: Ensure all cross-references and links work correctly
- **Version Consistency**: Update version numbers and dates across docs

#### Quarterly Deep Dives
- **Architecture Updates**: Review system architecture documentation
- **API Documentation**: Validate API endpoints and integration details
- **Configuration Documentation**: Ensure all environment variables are documented
- **Installation Instructions**: Test and update setup procedures

### 2. Code-Change Triggered Updates

#### When Adding New Commands
1. **Update COMMANDS.md**: Add command documentation with usage examples
2. **Update README.md**: Increment command count and add to feature list
3. **Update docs/README.md**: Add to appropriate category
4. **Test Documentation**: Verify examples work with actual implementation

#### When Adding New Features
1. **Create Feature Documentation**: New dedicated `.md` file in `docs/`
2. **Update Documentation Index**: Add to `docs/README.md`
3. **Cross-Reference**: Link from related documentation
4. **Update README.md**: Add to main feature list if significant

#### When Modifying Configuration
1. **Update config.py Documentation**: Document new environment variables
2. **Update .env.example**: Add new configuration options
3. **Update Setup Guides**: Include new configuration steps
4. **Test Configuration**: Verify documentation matches implementation

## Documentation Standards

### File Organization

```
docs/
├── README.md                    # Documentation index and overview
├── COMMANDS.md                  # Complete command reference
├── DOCUMENTATION_MAINTENANCE.md  # This file
├── FEATURE_SPECIFIC_DOCS/       # Feature documentation
│   ├── TIPCC_INTEGRATION.md
│   ├── ARTA_IMAGE_GENERATION.md
│   ├── AIRDROP_CLAIMING.md
│   └── ...
├── TECHNICAL_DOCS/              # Technical documentation
│   ├── POLLINATIONS_API.md
│   ├── MEMORY_SYSTEM.md
│   ├── LOGGING.md
│   └── ...
├── ROLE_MANAGEMENT_DOCS/        # Role system documentation
│   ├── REACTION_ROLES.md
│   ├── GENDER_ROLES.md
│   └── ...
└── DEVELOPMENT_DOCS/            # Development documentation
    ├── WELCOME_MESSAGES.md
    ├── TIP_THANK_YOU_FEATURE.md
    └── ...
```

### Writing Guidelines

#### Command Documentation Format
```markdown
### %command <parameters> (Permission Level)

Brief description of what the command does.

**Usage**: `%command <required> [optional]`

**Examples**:
- `%command example`
- `%command example with parameters`

**Response**: Description of what the command returns.

**Note**: Any special considerations or restrictions.
```

#### Feature Documentation Structure
1. **Overview**: High-level description and purpose
2. **Features**: Detailed feature list with explanations
3. **Configuration**: Setup and configuration instructions
4. **Usage**: How to use the feature with examples
5. **Troubleshooting**: Common issues and solutions
6. **Integration**: How it works with other features

### Cross-Reference Standards

#### Internal Links
- Use relative paths: `[Command Reference](COMMANDS.md)`
- Include anchor links for specific sections: `[Time Commands](COMMANDS.md#time-commands)`
- Validate links during documentation reviews

#### External References
- Use full URLs for external resources
- Include access notes if authentication is required
- Update or remove broken links promptly

## Automation Tools

### Documentation Validation Script

Create a script to automatically check documentation consistency:

```bash
#!/bin/bash
# docs_check.sh - Documentation validation script

echo "🔍 Checking documentation consistency..."

# Check command count consistency
COMMAND_COUNT=$(grep -c "@bot_instance.command" bot/commands.py)
DOC_COUNT=$(grep -o "commands.*[0-9]\+" docs/COMMANDS.md | grep -o "[0-9]\+")

if [ "$COMMAND_COUNT" -ne "$DOC_COUNT" ]; then
    echo "❌ Command count mismatch: Code has $COMMAND_COUNT, docs say $DOC_COUNT"
fi

# Check for missing command documentation
echo "📋 Checking for undocumented commands..."
# Add logic to compare commands in code vs documentation

# Check broken links
echo "🔗 Checking for broken links..."
# Add link validation logic

echo "✅ Documentation check complete"
```

### Command Extraction Utility

Create a utility to extract command information from code:

```python
# docs/extract_commands.py
import re
import ast

def extract_commands_from_file(file_path):
    """Extract command information from commands.py"""
    commands = []
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find all command decorators
    pattern = r'@bot_instance\.command\(name="([^"]+)"\)'
    matches = re.findall(pattern, content)
    
    for cmd_name in matches:
        commands.append({
            'name': cmd_name,
            'file': file_path,
            'documented': check_if_documented(cmd_name)
        })
    
    return commands

def check_if_documented(command_name):
    """Check if command is documented in COMMANDS.md"""
    with open('docs/COMMANDS.md', 'r') as f:
        content = f.read()
    return f"%{command_name}" in content

if __name__ == "__main__":
    commands = extract_commands_from_file('bot/commands.py')
    for cmd in commands:
        status = "✅" if cmd['documented'] else "❌"
        print(f"{status} %{cmd['name']}")
```

## Review Process

### Pre-Commit Documentation Review

Before committing code changes:

1. **Check for New Commands**: Run command extraction utility
2. **Validate Examples**: Test all command examples
3. **Update Counts**: Update command counts in all documentation
4. **Link Check**: Verify new links work correctly
5. **Spell Check**: Run spell check on new documentation

### Pull Request Documentation Requirements

Require documentation updates for:

- **New Commands**: Must be documented in COMMANDS.md
- **New Features**: Must have dedicated documentation
- **Configuration Changes**: Must update configuration documentation
- **Breaking Changes**: Must update relevant setup guides

### Release Documentation Updates

For each release:

1. **Update Version Numbers**: Across all documentation files
2. **Update Changelog**: Document new features and changes
3. **Review Migration Guides**: Update if breaking changes exist
4. **Update Installation**: Test and update setup instructions
5. **Archive Old Documentation**: Move outdated docs to archive folder

## Quality Assurance

### Documentation Testing

#### Example Validation
- Test all command examples in a development environment
- Verify configuration examples work correctly
- Check code snippets for syntax errors

#### User Experience Testing
- Follow documentation instructions from scratch
- Test with different user skill levels
- Verify clarity and completeness of instructions

### Accessibility Standards

#### Readability
- Use clear, simple language
- Avoid jargon where possible
- Define technical terms when used
- Use consistent terminology

#### Structure
- Use proper heading hierarchy
- Include table of contents for long documents
- Use bullet points and numbered lists appropriately
- Include code blocks for technical content

## Maintenance Schedule

### Daily Tasks
- **Monitor for Documentation Issues**: Check GitHub issues for documentation problems
- **Quick Updates**: Address minor documentation issues as they arise

### Weekly Tasks
- **Link Validation**: Check for broken links in documentation
- **Example Testing**: Test a subset of command examples
- **Review New Contributions**: Check documentation quality of new PRs

### Monthly Tasks
- **Full Command Audit**: Verify all commands are documented
- **Feature Review**: Check for undocumented features
- **Cross-Reference Update**: Ensure all links are current
- **User Feedback Review**: Address documentation feedback from users

### Quarterly Tasks
- **Architecture Documentation Review**: Update system architecture docs
- **API Documentation Validation**: Verify API documentation accuracy
- **Installation Guide Testing**: Test setup instructions from scratch
- **Documentation Restructuring**: Review and improve organization

## Tools and Resources

### Recommended Tools

#### Documentation Editors
- **Markdown Editors**: Typora, Mark Text, VS Code with Markdown extensions
- **Grammar Checkers**: Grammarly, LanguageTool
- **Link Checkers**: markdown-link-check, lychee

#### Automation Tools
- **CI/CD Integration**: GitHub Actions for documentation validation
- **Static Site Generators**: MkDocs, GitBook for advanced documentation
- **Documentation Linters**: markdownlint, write-good

### Templates

#### Command Documentation Template
```markdown
### %command <parameters> (Permission Level)

Brief one-sentence description.

**Usage**: `%command <required> [optional]`

**Parameters**:
- `required`: Description of required parameter
- `optional`: Description of optional parameter (default: value)

**Examples**:
- `%command example`
- `%command example with --flag`

**Response**: Description of expected output.

**Notes**:
- Any important considerations
- Restrictions or limitations
- Related commands or features
```

#### Feature Documentation Template
```markdown
# Feature Name

Brief overview of the feature and its purpose.

## Overview
Detailed description of what the feature does and why it exists.

## Features
- Feature 1: Description
- Feature 2: Description
- Feature 3: Description

## Configuration
Step-by-step configuration instructions with examples.

## Usage
How to use the feature with practical examples.

## Troubleshooting
Common issues and their solutions.

## Integration
How this feature works with other Jakey features.

## Advanced Usage
Advanced configurations and use cases.
```

## Contributing to Documentation

### Documentation Contributions

When contributing documentation:

1. **Follow Standards**: Use established templates and guidelines
2. **Test Examples**: Ensure all examples work correctly
3. **Check Links**: Verify all links are functional
4. **Spell Check**: Run spell check before submitting
5. **Get Review**: Have documentation reviewed by team members

### Documentation Issues

When reporting documentation issues:

1. **Be Specific**: Clearly describe what's wrong or missing
2. **Provide Examples**: Show what should be documented
3. **Suggest Improvements**: Offer specific suggestions for fixes
4. **Include Context**: Explain how the issue affects users

## Emergency Documentation Updates

### Critical Issues

For critical documentation issues (security vulnerabilities, broken installation, etc.):

1. **Immediate Update**: Fix documentation immediately
2. **Announcement**: Notify users of critical documentation updates
3. **Patch Release**: Consider patch release for critical fixes
4. **Review**: Conduct post-mortem to prevent future issues

### Rollback Procedures

If documentation updates cause problems:

1. **Identify Issue**: Determine what went wrong
2. **Rollback**: Revert to previous working version
3. **Communicate**: Notify users of the rollback
4. **Fix and Test**: Fix the issue and test thoroughly
5. **Redeploy**: Deploy corrected documentation

This maintenance guide ensures Jakey's documentation remains accurate, comprehensive, and useful throughout the project's lifecycle.