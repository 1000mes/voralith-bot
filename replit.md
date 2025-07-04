# Voralith Bot - Architecture Overview

## Overview

Voralith is a comprehensive Discord bot built with Python using the discord.py library. The bot provides giveaway functionality, support systems, and professional announcement features. It includes slash commands for creating giveaways, interactive buttons for user participation, automatic winner selection, support ticket system, and announcement capabilities. It's designed for 24/7 hosting on Replit with a Flask-based keep-alive mechanism.

## System Architecture

### Backend Architecture
- **Framework**: Python with discord.py library for Discord API integration
- **Web Framework**: Flask for keep-alive HTTP endpoint
- **Database**: PostgreSQL with psycopg2 for persistent data storage
- **Concurrency**: asyncio for handling Discord events and tasks
- **Storage**: PostgreSQL database for persistent vouch tracking and statistics
- **Deployment**: Configured for Replit hosting with automatic uptime management

### Key Design Decisions
- **PostgreSQL storage**: Persistent database for vouch tracking and statistics
- **Dynamic counters**: Real-time vouch numbering system using database sequences
- **Flask keep-alive**: Implements HTTP endpoint to prevent Replit from sleeping the application
- **Discord UI Views**: Uses modern Discord interaction components (buttons) for better user experience
- **Slash commands**: Modern Discord command interface instead of traditional prefix commands
- **OAuth2 integration**: Proper Discord authorization for server joining and profile access

## Key Components

### Bot Core (`main.py`)
- Discord bot initialization with appropriate intents
- Command handling and event processing
- Giveaway management logic
- Support ticket system with interactive select menu
- Professional announcement and update log systems
- Error handling and logging

### Keep-Alive Service (`keep_alive.py`)
- Flask web server providing status page with Voralith branding
- Threading implementation to run alongside Discord bot
- Prevents application from sleeping on Replit

### Giveaway System
- `GiveawayView`: Discord UI View class for interactive buttons
- `active_giveaways`: In-memory dictionary storing giveaway data
- Automatic winner selection and announcement

### Support System
- `TicketView`: Discord UI View with select menu for support categories
- Interactive ticket creation with guidelines
- Professional support categories (Purchase, Technical, General, Refund, Report)

### Announcement System
- Professional announcement embeds with timestamps
- Update log system with changelog formatting
- Custom branding and author information

## Data Flow

1. **Giveaway Creation**: User executes slash command → Bot creates giveaway object → Stores in memory → Posts embed with join button
2. **User Participation**: User clicks join button → Bot validates participation → Updates participant list → Confirms participation
3. **Winner Selection**: Timer expires → Bot selects random winner → Announces results → Cleans up giveaway data

### Data Structure
```python
giveaway = {
    'id': int,
    'prize': str,
    'end_time': datetime,
    'participants': set,
    'channel_id': int,
    'message_id': int,
    'host_id': int
}
```

## External Dependencies

### Discord API
- **Purpose**: Core bot functionality and user interaction
- **Integration**: discord.py library handles API communication
- **Requirements**: Bot token, appropriate permissions, slash command registration

### Replit Platform
- **Purpose**: 24/7 hosting and deployment
- **Integration**: Keep-alive mechanism prevents application sleeping
- **Configuration**: Environment variables for bot token storage

## Deployment Strategy

### Replit Hosting
- **Environment**: Python runtime on Replit
- **Configuration**: Bot token stored in Replit Secrets
- **Uptime**: Flask server keeps application active
- **Auto-restart**: Replit handles application restarts

### Bot Permissions Required
- Send Messages
- Use Slash Commands  
- Embed Links
- Read Message History
- Add Reactions

## Limitations and Considerations

### Data Persistence
- **Current**: In-memory storage only
- **Impact**: Giveaway data lost on application restart
- **Future**: Could integrate database for persistence

### Scalability
- **Current**: Single-instance deployment
- **Limitations**: Memory-based storage limits concurrent giveaways
- **Considerations**: Works well for small to medium Discord servers

## User Preferences

Preferred communication style: Simple, everyday language.

## Changelog

Changelog:
- July 01, 2025. Initial setup with basic giveaway functionality
- July 01, 2025. Added comprehensive support system with ticket management
- July 01, 2025. Added professional announcement and update log features
- July 01, 2025. Implemented custom branding as "Voralith" with purple logo
- July 01, 2025. Added purchase information display with payment options
- July 01, 2025. Updated keep-alive page with all new features
- July 01, 2025. Added complete verification system with anti-bot protection
- July 01, 2025. Implemented automatic "| Voralith | Verified" role assignment
- July 01, 2025. Added /end_giveaway command for manual giveaway termination
- July 01, 2025. Added new member welcome DM system with verification instructions
- July 01, 2025. Added admin commands: /setup_verification and /verify_stats
- July 01, 2025. Implemented OAuth2 authorization system for server reconnection
- July 01, 2025. Added Flask OAuth callback route for Discord authorization
- July 01, 2025. Enhanced verification with real Discord "join servers" permission
- July 03, 2025. Added /vouch command with star rating dropdown (1-5 stars)
- July 03, 2025. Created VouchView class with interactive star selection menu
- July 03, 2025. Added image support for vouch reviews with validation
- July 03, 2025. Added role restriction: /vouch only usable by "| Voralith | Customer" role
- July 03, 2025. Updated vouch embed format to match professional "Vouch Format" style
- July 03, 2025. Changed bot activity to "free boosting in tickets"
- July 03, 2025. Enhanced verification system to require OAuth2 authorization immediately
- July 03, 2025. Made Discord authorization mandatory for verification completion
- July 03, 2025. Simplified verification flow: "Verify Identity" → OAuth2 link → "Complete Verification"
- July 03, 2025. Converted all verification and vouch text to English only
- July 03, 2025. Fixed OAuth2 URL encoding with urllib.parse for proper authorization links
- July 03, 2025. Updated vouch dropdown menu and creation text to English
- July 03, 2025. Enhanced verification embed with clear step-by-step instructions
- July 03, 2025. Implemented PostgreSQL database for persistent vouch tracking
- July 03, 2025. Added dynamic vouch counter system replacing fixed "195" number
- July 03, 2025. Created vouch_counter and vouches tables for data persistence
- July 03, 2025. Updated OAuth2 permissions to "identify guilds.join" for proper server joining
- July 03, 2025. Enhanced vouch system with automatic database saves and real-time numbering
- July 03, 2025. Implemented automatic role assignment system via OAuth2 callback
- July 03, 2025. Added DISCORD_CLIENT_SECRET for OAuth2 token exchange functionality
- July 03, 2025. Created PermanentVerificationView for channel embed verification
- July 03, 2025. Enhanced /setup-verification to create persistent verification buttons
- July 03, 2025. Simplified verification process: one-click authorization with automatic role assignment
- July 03, 2025. Added comprehensive logging for OAuth2 callback debugging
- July 03, 2025. Removed /verify command completely as per user request
- July 03, 2025. Restored OAuth2 system for "identify" and "guilds.join" permissions
- July 03, 2025. OAuth2 system now provides account protection and server reconnection features
- July 03, 2025. Replaced complex OAuth2 system with simplified anti-bot protection and reconnection tracking
- July 03, 2025. Enhanced verification system with user data storage and protection ID system
- July 03, 2025. Added admin-only restrictions to all commands except /vouch
- July 03, 2025. Implemented strict DM permissions (admin ID 1156246022104825916 only)
- July 03, 2025. Updated command descriptions to indicate admin-only status
- July 03, 2025. Changed bot color theme from green (#00ff88) to purple (#5B2C6F) throughout all embeds
- July 03, 2025. Created /setup-reviews command for permanent review format embed with purple branding
- July 03, 2025. Added exact "Vouch Format" embed matching user-provided design specifications
- July 03, 2025. Fixed command duplication issue with complete command cache clearing and re-synchronization
- July 03, 2025. Updated /setup-reviews: changed footer to "Voralith Support", new example "/vouch manta is the best <3 Stars 5/5 Picture"
- July 03, 2025. Replaced pinning system with advanced "sticky message" functionality for /setup-reviews
- July 03, 2025. Added automatic message detection and re-posting to keep review format always at bottom
- July 03, 2025. Created /remove-sticky command to disable sticky system from channels
- July 03, 2025. Implemented sticky_channels tracking system for real-time message management
- July 03, 2025. Bot accidentally linked to external "restorecord" service, overwriting custom commands
- July 03, 2025. Successfully restored all 17 custom Voralith commands after RestoRecord incident
- July 03, 2025. All custom features restored: sticky system, purple branding, admin restrictions, PostgreSQL integration
- July 03, 2025. Bot re-invited to server after RestoRecord incident, all 17 commands now fully operational
- July 03, 2025. Sticky review system confirmed working perfectly in live environment
- July 03, 2025. Ticket system enhanced: removed "refund request" option, added automatic ticket channel creation
- July 03, 2025. Implemented ticket close button system - users, admins, and support can close tickets with confirmation
- July 03, 2025. Tickets now auto-detect existing categories and create private channels with proper permissions
- July 03, 2025. Added comprehensive media permissions for users in tickets (images, files, attachments)
- July 03, 2025. Disabled slash commands for regular users in tickets, preserved for admins and support
- July 03, 2025. Implemented automatic transcript system - saves all conversations to #transcript channel on closure
- July 03, 2025. Upgraded transcript system to generate professional HTML files with elegant Discord-style design
- July 03, 2025. HTML transcripts include chronological messages, timestamps, user avatars, and embedded images
- July 03, 2025. Added comprehensive anti-spam moderation system with smart rate limiting and timeouts
- July 03, 2025. Anti-spam: 5 messages max per 10 seconds, 3 warnings before 5-minute timeout, excludes tickets and admins
- July 03, 2025. Added manual moderation commands: /mute and /unmute for administrators
- July 03, 2025. /mute supports custom duration (1-86400 seconds) and reason tracking with detailed embeds
- July 03, 2025. /unmute provides immediate timeout removal with reason logging and verification checks
- July 03, 2025. Updated preview page with modern purple design and complete feature overview
- July 03, 2025. Implemented forced command synchronization system to resolve Discord API propagation delays
- July 03, 2025. Renamed /ticket command to /setup-tickets for better clarity and consistency
- July 03, 2025. Added /setup-rules command with professional server rules embed and consequences system
- July 03, 2025. Updated rule 9 in /setup-rules to link directly to specific ticket channel (#1388934457725292615)
- July 03, 2025. Added /setup-customorders command with interactive button system for custom order tickets
- July 03, 2025. Updated custom orders embed to be completely general instead of targeting specific services
- July 03, 2025. Fixed custom order ticket permissions - users can now close their own tickets
- July 03, 2025. Comprehensive system check-up completed: fixed hardcoded channel references, removed broken logo URLs, standardized all text to English, improved anti-spam to cover all ticket types, enhanced error logging with proper logger usage, cleaned up legacy OAuth2 variables, and ensured consistent permissions across all ticket systems
- July 03, 2025. Added advanced connection monitoring system with dual heartbeat mechanisms (internal Flask monitoring + Discord heartbeat) to solve UptimeRobot functionality loss issues - bot now maintains persistent Discord connection even during extended inactive periods
- July 03, 2025. Created /clear command with optional message count parameter - admins can clear specific number of messages or all messages with confirmation system and safety limits
- July 03, 2025. Fixed "échec de l'intéraction" error after disconnections by implementing persistent Discord UI views with custom_id parameters - ticket systems, verification, and custom orders now remain functional after bot restarts
- July 04, 2025. Resolved Discord interaction persistence issues - all new buttons/menus created after bot restart will work permanently, but old interactions require recreation
- July 04, 2025. Confirmed UptimeRobot monitoring URL: https://c3326c1f-4b25-4a12-8be3-cc3ca73147ba-00-2s50mbwyv8sk3.spock.replit.dev/ for 24/7 bot uptime