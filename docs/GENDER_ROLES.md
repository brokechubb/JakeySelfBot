# Gender Role Recognition System

Jakey includes an intelligent gender role recognition system that automatically detects users' genders based on their Discord roles and uses appropriate pronouns when interacting with them. This feature enhances personalization and user experience.

## Overview

The gender role system allows Jakey to:
- Automatically detect user gender based on assigned Discord roles
- Use appropriate pronouns (he/him, she/her, they/them) in conversations
- Provide personalized responses that respect user identity
- Support non-binary and gender-neutral preferences

## Configuration

### Environment Variable Setup

Set the `GENDER_ROLE_MAPPINGS` environment variable in your `.env` file:

```
GENDER_ROLE_MAPPINGS=male:123456789,female:987654321,neutral:111222333
```

### Guild Restriction (Optional)

To restrict gender role detection to a specific guild only, set the `GENDER_ROLES_GUILD_ID` environment variable:

```
GENDER_ROLES_GUILD_ID=123456789012345678
```

When this variable is set, Jakey will only use gender roles in the specified guild. In all other guilds, neutral pronouns (they/them/their) will be used regardless of user roles.

**Format**: `gender:role_id,gender:role_id,...`

**Supported Gender Categories**:
- `male`: Uses he/him/his pronouns
- `female`: Uses she/her/hers pronouns  
- `neutral`: Uses they/them/their pronouns (default fallback)

### Getting Role IDs

To find Discord role IDs:
1. Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
2. Right-click on a role in Server Settings > Roles
3. Select "Copy Role ID"

## Commands

### %set_gender_roles <gender:role_id,...> (Admin Only)

Set or update gender role mappings dynamically.

**Usage**: `%set_gender_roles <gender:role_id,...>`

**Examples**:
```
%set_gender_roles male:123456789,female:987654321,neutral:111222333
%set_gender_roles male:555555555555555555,female:666666666666666666
```

**Response**: Confirms the gender role mappings have been updated.

### %show_gender_roles (Admin Only)

Display current gender role configuration.

**Usage**: `%show_gender_roles`

**Response**: Shows:
- Currently configured gender role mappings
- Role names and IDs
- Detection status for each gender category

## Detection Logic

### Role Priority System

Jakey follows a specific priority when detecting gender roles:

1. **Male Roles**: Checks if user has any configured male role
2. **Female Roles**: Checks if user has any configured female role  
3. **Neutral Roles**: Falls back to neutral if no specific gender roles found
4. **Default**: Uses they/them pronouns if no gender roles detected

### Multiple Role Handling

- **Multiple Gender Roles**: If a user has roles from multiple gender categories, Jakey uses the first match in priority order (male → female → neutral)
- **No Gender Roles**: Users without any configured gender roles receive neutral pronouns by default
- **Role Changes**: Jakey automatically detects role changes and updates pronoun usage accordingly

## Pronoun Usage

### Male Pronouns
- Subject: he
- Object: him
- Possessive: his
- Examples: "He is playing", "Give him the chips", "That's his lucky streak"

### Female Pronouns  
- Subject: she
- Object: her
- Possessive: her/hers
- Examples: "She is winning", "Give her the cards", "That's her victory"

### Neutral Pronouns
- Subject: they
- Object: them
- Possessive: their/theirs
- Examples: "They are playing", "Give them the dice", "That's their win"

## Implementation Details

### Automatic Detection

The gender detection system works automatically in the background:

1. **Role Monitoring**: Jakey monitors user role assignments
2. **Real-time Updates**: Pronoun usage updates immediately when roles change
3. **Context Integration**: Gender detection integrates with all conversation contexts
4. **Memory Integration**: Gender preferences are stored in user memory for consistency

### Integration with Features

Gender role recognition integrates with:

- **AI Conversations**: Personalized responses with appropriate pronouns
- **Welcome Messages**: Gender-aware greeting generation
- **Memory System**: Stores gender preferences for user profiles
- **Tool Usage**: Gender-aware context in all tool interactions

## Setup Guide

### 1. Create Gender Roles

First, create the necessary roles in your Discord server:

```
Male
Female  
Non-Binary
```

### 2. Configure Role Mappings

Use either environment variables or commands:

**Environment Variable**:
```
GENDER_ROLE_MAPPINGS=male:ROLE_ID_MALE,female:ROLE_ID_FEMALE,neutral:ROLE_ID_NEUTRAL
```

**Command Configuration**:
```
%set_gender_roles male:ROLE_ID_MALE,female:ROLE_ID_FEMALE,neutral:ROLE_ID_NEUTRAL
```

### 3. Assign Roles to Users

Assign the appropriate roles to users who want gender-specific pronouns.

### 4. Verify Configuration

Use `%show_gender_roles` to verify the setup is correct.

## Best Practices

### Role Management

1. **Clear Role Names**: Use descriptive role names that users understand
2. **Optional Participation**: Make gender roles opt-in rather than required
3. **Privacy Considerations**: Be respectful of users' privacy preferences
4. **Role Hierarchy**: Position gender roles appropriately in your server structure

### User Communication

1. **Explain the System**: Let users know how gender detection works
2. **Provide Options**: Ensure users can opt out or choose neutral pronouns
3. **Respect Identity**: Honor users' gender identity and preferences
4. **Clear Documentation**: Provide information about available gender roles

### Server Configuration

1. **Test Thoroughly**: Test the system with different role combinations
2. **Monitor Usage**: Keep track of how the system is being used
3. **Update Regularly**: Keep role mappings current as your server evolves
4. **Backup Configuration**: Document your gender role setup for reference

## Troubleshooting

### Common Issues

**"Pronouns not updating after role change"**
- Wait a few minutes for the system to detect changes
- Check that the role ID is correctly configured
- Verify the user actually has the assigned role

**"Wrong pronouns being used"**
- Check role priority order (male → female → neutral)
- Verify role mappings are correct
- Ensure user doesn't have conflicting gender roles

**"Gender roles not working"**
- Confirm Jakey has permission to view roles
- Check that role IDs are correct
- Verify the environment variable is set properly

### Debugging Commands

1. **Check configuration**: `%show_gender_roles`
2. **Verify role IDs**: Use Discord Developer Mode to copy role IDs
3. **Test with specific users**: Observe pronoun usage in conversations

## Advanced Features

### Custom Gender Categories

While the system supports male, female, and neutral categories by default, you can extend it for additional gender identities by using the neutral category as a flexible fallback.

### Integration with Other Systems

The gender role system can integrate with:
- **Welcome bots**: Gender-aware welcome messages
- **Role assignment bots**: Automated gender role assignment
- **Moderation tools**: Gender-aware moderation responses
- **Statistics tracking**: Gender demographics for server analytics

### Memory Enhancement

Gender preferences are stored in Jakey's memory system, allowing for:
- Persistent gender recognition across sessions
- Historical tracking of gender preferences
- Integration with user profile systems
- Backup and restoration of gender configurations

## Privacy and Ethics

### User Privacy

- **Opt-in System**: Gender detection is based on voluntarily assigned roles
- **Data Minimization**: Only necessary gender information is stored
- **User Control**: Users can change their assigned roles at any time
- **Transparency**: The system's operation is clearly documented

### Ethical Considerations

- **Respect Identity**: Honor users' stated gender identity
- **Inclusive Design**: Support for non-binary and gender-neutral options
- **Avoid Assumptions**: Don't make assumptions about gender based on behavior
- **Cultural Sensitivity**: Be aware of different cultural approaches to gender

## Security Considerations

- **Admin-only Configuration**: Only authorized users can configure gender roles
- **Role Validation**: System validates role existence before configuration
- **Permission Checks**: Ensures Jakey has necessary permissions to read roles
- **Audit Trail**: Configuration changes are logged for accountability

This gender role recognition system provides a respectful and inclusive way to personalize user interactions while maintaining privacy and user control over their gender identity presentation.