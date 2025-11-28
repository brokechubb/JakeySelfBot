# Reaction Role System

Jakey includes a comprehensive reaction role system that allows users to self-assign roles by reacting to specific messages with emojis. This feature is commonly used for role assignment in Discord servers.

## Overview

The reaction role system enables server administrators to create automated role assignments based on user reactions to specific messages. When a user adds the configured emoji reaction to the designated message, Jakey automatically assigns the corresponding role.

## Commands

### %add_reaction_role <message_id> <emoji> <role> (Admin Only)

Add a new reaction role configuration to a message.

**Usage**: `%add_reaction_role <message_id> <emoji> <role>`

**Parameters**:
- `message_id`: The Discord message ID to attach the reaction role to
- `emoji`: The emoji that triggers the role assignment
- `role`: The role name or mention to be assigned

**Examples**:
```
%add_reaction_role 123456789012345678 🎮 Gamer
%add_reaction_role 987654321098765432 🎵 Music Lover
%add_reaction_role 555555555555555555 🎨 Artist
```

**Response**: Confirms the reaction role has been added successfully.

### %remove_reaction_role <message_id> <emoji> (Admin Only)

Remove an existing reaction role configuration.

**Usage**: `%remove_reaction_role <message_id> <emoji>`

**Parameters**:
- `message_id`: The Discord message ID with the reaction role
- `emoji`: The emoji to remove from the reaction role configuration

**Examples**:
```
%remove_reaction_role 123456789012345678 🎮
%remove_reaction_role 987654321098765432 🎵
```

**Response**: Confirms the reaction role has been removed successfully.

### %list_reaction_roles (Admin Only)

Display all currently configured reaction roles.

**Usage**: `%list_reaction_roles`

**Response**: Shows a formatted list of all reaction role configurations including:
- Message IDs
- Trigger emojis
- Assigned roles
- Configuration status

## Setup Guide

### 1. Create Role Assignment Message

First, create a message in your server where users can react to get roles. This could be in a dedicated #roles channel or any appropriate channel.

Example message:
```
🎮 React with 🎮 for the Gamer role
🎵 React with 🎵 for the Music Lover role
🎨 React with 🎨 for the Artist role
```

### 2. Get Message ID

To get the message ID:
1. Enable Developer Mode in Discord (User Settings > Advanced > Developer Mode)
2. Right-click on the message and select "Copy Message ID"

### 3. Configure Reaction Roles

Use the `%add_reaction_role` command to set up each reaction role:

```
%add_reaction_role MESSAGE_ID_HERE 🎮 Gamer
%add_reaction_role MESSAGE_ID_HERE 🎵 "Music Lover"
%add_reaction_role MESSAGE_ID_HERE 🎨 Artist
```

### 4. Verify Configuration

Use `%list_reaction_roles` to verify all reaction roles are configured correctly.

## Features

### Automatic Role Assignment

- When a user adds the configured emoji to the message, Jakey automatically assigns the corresponding role
- The system handles both role additions and removals when users remove their reactions

### Role Management

- Only roles that Jakey has permission to manage can be used
- The bot must have the "Manage Roles" permission in the server
- Jakey cannot assign roles higher than its own highest role in the server hierarchy

### Error Handling

- Invalid message IDs are detected and reported
- Missing permissions are handled gracefully with informative error messages
- Duplicate configurations are prevented

### Security

- Only admin users can configure reaction roles
- Role assignments are logged for audit purposes
- The system validates role existence before configuration

## Best Practices

### Role Organization

1. **Create a dedicated roles channel** for reaction role messages
2. **Use clear, descriptive role names** that users will understand
3. **Group related roles** together in the same message
4. **Use appropriate emojis** that relate to the role purpose

### Message Design

1. **Use clear formatting** with bullet points or numbered lists
2. **Include role descriptions** so users know what each role is for
3. **Keep messages organized** and easy to read
4. **Consider using embeds** for better visual presentation

### Permission Management

1. **Ensure Jakey has proper permissions**:
   - Manage Roles permission
   - Read Messages/View Channels
   - Add Reactions
2. **Position Jakey's role appropriately** in the server role hierarchy
3. **Test configurations** before making them public

## Troubleshooting

### Common Issues

**"I don't have permission to manage that role"**
- Ensure Jakey's role is higher than the target role in the server role hierarchy
- Check that Jakey has the "Manage Roles" permission

**"Message not found"**
- Verify the message ID is correct
- Ensure the message is in a channel Jakey can access
- Check that the message hasn't been deleted

**"Emoji not working"**
- Ensure the emoji is available in the server
- Try using a different emoji
- Check for emoji formatting issues

### Debugging Commands

1. **List all reaction roles**: `%list_reaction_roles`
2. **Check bot permissions**: Ensure Jakey has required permissions
3. **Verify message accessibility**: Make sure the message exists and is accessible

## Integration with Other Features

The reaction role system integrates seamlessly with Jakey's other features:

- **Gender Role Detection**: Can work alongside automatic gender role detection
- **Admin Commands**: All reaction role commands respect admin permission settings
- **Logging**: All role assignments are logged for server administration
- **Error Handling**: Uses Jakey's comprehensive error handling system

## Security Considerations

- **Admin-only configuration**: Only authorized users can set up reaction roles
- **Role hierarchy respect**: System respects Discord's role hierarchy rules
- **Permission validation**: Validates permissions before attempting role assignments
- **Audit trail**: All configuration changes are logged

## Advanced Usage

### Multiple Messages

You can set up reaction roles across multiple messages in different channels, allowing for complex role assignment systems.

### Conditional Roles

Combine reaction roles with other server features like:
- Welcome messages that mention available roles
- Automated role assignment based on user activity
- Integration with server verification systems

### Role Categories

Organize roles into categories using multiple messages:
- Gaming roles
- Notification roles
- Identity roles
- Interest-based roles

This system provides a flexible and secure way to manage server roles through user interactions.