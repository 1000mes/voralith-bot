# Discord Giveaway Bot

A feature-rich Discord bot for hosting giveaways with slash commands, interactive buttons, and automatic winner selection. Designed for 24/7 hosting on Replit.

## 🎉 Features

- **Slash Commands**: Modern Discord slash command interface
- **Interactive Buttons**: Users can join giveaways with a single click
- **Flexible Duration**: Support for various time formats (1h, 30m, 2d, 1w)
- **Automatic Winners**: Random winner selection when giveaways end
- **Real-time Updates**: Participant count updates in real-time
- **Multiple Giveaways**: Support for multiple concurrent giveaways
- **24/7 Uptime**: Configured for continuous hosting on Replit
- **Error Handling**: Robust error handling for edge cases

## 🚀 Setup Instructions

### 1. Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and bot
3. Copy the bot token
4. Enable the following bot permissions:
   - Send Messages
   - Use Slash Commands
   - Embed Links
   - Read Message History
   - Add Reactions

### 2. Replit Configuration

1. Fork this Replit project
2. In the Secrets tab (🔒), add:
   - Key: `DISCORD_TOKEN`
   - Value: Your Discord bot token
3. The bot will automatically start when you run the project

### 3. Invite Bot to Server

Generate an invite link with these permissions:
- Applications Commands (for slash commands)
- Send Messages
- Embed Links
- Use External Emojis

## 📖 Commands

### `/giveaway`
Create a new giveaway with customizable prize and duration.

**Parameters:**
- `prize`: The prize description (e.g., "Nintendo Switch")
- `duration`: Time duration (e.g., "1h", "30m", "2d", "1w")

**Example:**
