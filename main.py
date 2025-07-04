import discord
from discord.ext import commands, tasks
import asyncio
import random
import datetime
import os
import logging
import secrets
import urllib.parse
import psycopg2
from psycopg2.extras import RealDictCursor
from keep_alive import keep_alive
from collections import defaultdict, deque
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Admin user ID (only this user can use commands in DM)
ADMIN_USER_ID = 1156246022104825916  # Your user ID based on logs

# Anti-spam moderation system
user_message_times = defaultdict(deque)  # Track message timestamps per user
user_warnings = defaultdict(int)  # Track warnings per user

# Moderation settings - raisonnable limits
SPAM_LIMIT = 5  # Maximum messages
SPAM_WINDOW = 10  # In 10 seconds
WARNING_THRESHOLD = 3  # 3 warnings before timeout
TIMEOUT_DURATION = 300  # 5 minutes timeout

# Dictionary to store active giveaways
active_giveaways = {}

# Dictionary to store sticky channels (channel_id -> message_id)
sticky_channels = {}

def check_dm_permissions(interaction: discord.Interaction) -> bool:
    """Check if user can use commands in DM"""
    if interaction.guild is None:  # DM context
        return interaction.user.id == ADMIN_USER_ID
    return True  # All users can use commands in servers

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """Get a database connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def init_database():
    """Initialize the database tables"""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                # Create vouch counter table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vouch_counter (
                        guild_id BIGINT PRIMARY KEY,
                        total_vouches INTEGER DEFAULT 0
                    )
                """)
                
                # Create vouches table to store individual vouches
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS vouches (
                        id SERIAL PRIMARY KEY,
                        guild_id BIGINT,
                        user_id BIGINT,
                        username VARCHAR(100),
                        message TEXT,
                        stars INTEGER,
                        image_url TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
        finally:
            conn.close()

def get_next_vouch_number(guild_id):
    """Get the next vouch number for a guild"""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                # Get or create counter for this guild
                cursor.execute("""
                    INSERT INTO vouch_counter (guild_id, total_vouches)
                    VALUES (%s, 1)
                    ON CONFLICT (guild_id)
                    DO UPDATE SET total_vouches = vouch_counter.total_vouches + 1
                    RETURNING total_vouches
                """, (guild_id,))
                
                result = cursor.fetchone()
                conn.commit()
                return result[0] if result else 1
        except Exception as e:
            logger.error(f"Error getting vouch number: {e}")
            return 1
        finally:
            conn.close()
    return 1

def save_vouch(guild_id, user_id, username, message, stars, image_url=None):
    """Save a vouch to the database"""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO vouches (guild_id, user_id, username, message, stars, image_url)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (guild_id, user_id, username, message, stars, image_url))
                conn.commit()
                logger.info(f"Vouch saved for user {username} in guild {guild_id}")
        except Exception as e:
            logger.error(f"Error saving vouch: {e}")
        finally:
            conn.close()

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent for on_message
intents.guilds = True
intents.members = True  # Needed for role management and verification

bot = commands.Bot(command_prefix='!', intents=intents)

# In-memory storage for giveaways and verification
active_giveaways = {}
giveaway_counter = 0
verification_pending = {}  # Store users pending verification
verified_users = set()  # Store verified user IDs
oauth_states = {}  # Store OAuth2 states for security
sticky_channels = {}  # Store channels with sticky review messages {channel_id: message_id}

async def create_sticky_review_embed():
    """Create the sticky review format embed"""
    embed = discord.Embed(
        title="Vouch Format",
        description="When sending a review, ensure to abide by the following example, otherwise your vouch will be **deleted** and result in a **mute**",
        color=0x5B2C6F
    )
    
    embed.add_field(
        name="Example:",
        value="/vouch manta is the best <3 Stars 5/5 Picture",
        inline=False
    )
    
    embed.set_footer(text="Voralith Support", icon_url="https://cdn.discordapp.com/attachments/1156246022104825920/1321844863446892574/voralith-logo.png")
    
    return embed

async def update_sticky_message(channel):
    """Update the sticky message in a channel"""
    try:
        if channel.id in sticky_channels:
            # Delete the old sticky message
            try:
                old_message = await channel.fetch_message(sticky_channels[channel.id])
                await old_message.delete()
            except:
                pass  # Message might already be deleted
        
        # Send new sticky message
        embed = await create_sticky_review_embed()
        new_message = await channel.send(embed=embed)
        sticky_channels[channel.id] = new_message.id
        
        logger.info(f"Updated sticky message in {channel.name}")
        
    except Exception as e:
        logger.error(f"Error updating sticky message in {channel.name}: {e}")

# Anti-spam moderation functions
async def check_spam(message):
    """Check if user is spamming and take action"""
    user_id = message.author.id
    current_time = time.time()
    
    # Skip bots
    if message.author.bot:
        return False
        
    # Skip admins - check if they have admin permissions in the guild
    if message.guild and isinstance(message.author, discord.Member):
        if message.author.guild_permissions.administrator:
            logger.info(f"Skipping admin user {message.author.name} from anti-spam")
            return False
    
    # Skip in all ticket channels (regular tickets and custom orders)
    if message.channel and hasattr(message.channel, 'name'):
        if message.channel.name and (message.channel.name.startswith("ticket-") or "custom-order" in message.channel.name.lower()):
            return False
    
    # Add current message timestamp
    user_message_times[user_id].append(current_time)
    
    # Remove old timestamps outside the window
    while user_message_times[user_id] and user_message_times[user_id][0] < current_time - SPAM_WINDOW:
        user_message_times[user_id].popleft()
    
    # Debug: Log message count for this user
    message_count = len(user_message_times[user_id])
    logger.info(f"User {message.author.name} has {message_count}/{SPAM_LIMIT} messages in {SPAM_WINDOW}s window")
    
    # Check if user exceeded spam limit
    if message_count >= SPAM_LIMIT:
        logger.info(f"SPAM DETECTED: User {message.author.name} exceeded limit with {message_count} messages")
        await handle_spam_violation(message)
        return True
    
    return False

async def handle_spam_violation(message):
    """Handle spam violation with warnings and timeouts"""
    user = message.author
    user_id = user.id
    
    try:
        # Delete the spam message
        await message.delete()
        
        # Increment warning count
        user_warnings[user_id] += 1
        
        if user_warnings[user_id] >= WARNING_THRESHOLD:
            # Timeout user for 5 minutes
            try:
                timeout_until = discord.utils.utcnow() + datetime.timedelta(seconds=TIMEOUT_DURATION)
                await user.timeout(timeout_until, reason="Automatic spam detection")
                
                # Reset warnings after timeout
                user_warnings[user_id] = 0
                user_message_times[user_id].clear()
                
                # Send timeout notification
                embed = discord.Embed(
                    title="🔇 User Timed Out",
                    description=f"{user.mention} has been timed out for **{TIMEOUT_DURATION//60} minutes** for spamming.",
                    color=0xff4444
                )
                embed.set_footer(text="Voralith Automatic Moderation")
                await message.channel.send(embed=embed, delete_after=10)
                
                logger.info(f"User {user.name} timed out for spam")
                
            except discord.Forbidden:
                # If can't timeout, just send warning
                embed = discord.Embed(
                    title="⚠️ Spam Warning",
                    description=f"{user.mention} you have been detected for spamming. Please slow down your messages!",
                    color=0xff9900
                )
                embed.set_footer(text="Voralith Automatic Moderation")
                await message.channel.send(embed=embed, delete_after=5)
        else:
            # Send warning
            warnings_left = WARNING_THRESHOLD - user_warnings[user_id]
            embed = discord.Embed(
                title="⚠️ Anti-Spam Warning",
                description=f"{user.mention} please slow down your messages! **{warnings_left} warning(s)** remaining before timeout.",
                color=0xff9900
            )
            embed.add_field(
                name="📋 Limits",
                value=f"Maximum **{SPAM_LIMIT} messages** in **{SPAM_WINDOW} seconds**",
                inline=False
            )
            embed.set_footer(text="Voralith Automatic Moderation")
            await message.channel.send(embed=embed, delete_after=8)
            
            logger.info(f"Spam warning {user_warnings[user_id]}/{WARNING_THRESHOLD} for {user.name}")
            
    except Exception as e:
        logger.error(f"Error handling spam violation: {e}")

# Bot configuration for OAuth2 (legacy - kept for compatibility)
CLIENT_ID = os.getenv('DISCORD_CLIENT_ID') or '1388879919412543659'
REDIRECT_URI = 'https://voralith.mantallo.repl.co/oauth/callback'

class GiveawayView(discord.ui.View):
    def __init__(self, giveaway_id):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
    
    @discord.ui.button(label='🎉 Join Giveaway', style=discord.ButtonStyle.primary, custom_id='join_giveaway')
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        giveaway_id = self.giveaway_id
        
        if giveaway_id not in active_giveaways:
            await interaction.response.send_message("❌ This giveaway no longer exists!", ephemeral=True)
            return
        
        giveaway = active_giveaways[giveaway_id]
        
        if datetime.datetime.utcnow() > giveaway['end_time']:
            await interaction.response.send_message("❌ This giveaway has already ended!", ephemeral=True)
            return
        
        user_id = interaction.user.id
        
        if user_id in giveaway['participants']:
            await interaction.response.send_message("❌ You're already participating in this giveaway!", ephemeral=True)
            return
        
        giveaway['participants'].append(user_id)
        await interaction.response.send_message("✅ You've joined the giveaway! Good luck! 🎉", ephemeral=True)
        
        logger.info(f"User {interaction.user.name} joined giveaway {giveaway_id}")

# Legacy views to handle old buttons without custom_id
class LegacyTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(LegacyTicketSelectMenu())

class LegacyTicketSelectMenu(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="💰 Purchase Support",
                emoji="💰",
                value="purchase",
                description="Questions about purchases"
            ),
            discord.SelectOption(
                label="🛠️ Technical Support",
                emoji="🛠️",
                value="technical",
                description="Technical issues or help"
            ),
            discord.SelectOption(
                label="❓ General Question",
                emoji="❓",
                value="general",
                description="General questions"
            ),
            discord.SelectOption(
                label="🚨 Report Issue",
                emoji="🚨",
                value="report",
                description="Report a user or issue"
            )
        ]
        super().__init__(placeholder="Select a support category...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        # Same logic as TicketSelectMenu
        category_info = {
            "purchase": {
                "name": "Purchase Support",
                "emoji": "💰",
                "description": "Questions about purchases, payments, or billing"
            },
            "technical": {
                "name": "Technical Support", 
                "emoji": "🛠️",
                "description": "Technical issues, bugs, or help needed"
            },
            "general": {
                "name": "General Question",
                "emoji": "❓", 
                "description": "General questions or information"
            },
            "report": {
                "name": "Report Issue",
                "emoji": "🚨",
                "description": "Report a user, abuse, or other issue"
            }
        }
        
        selected = self.values[0]
        category = category_info[selected]
        
        guild = interaction.guild
        user = interaction.user
        
        # Find or create Support category
        support_category = None
        for cat in guild.categories:
            if "support" in cat.name.lower() or "ticket" in cat.name.lower():
                support_category = cat
                break
        
        if not support_category:
            support_category = await guild.create_category("Support")
        
        # Create ticket channel
        channel_name = f"ticket-{user.name.lower().replace(' ', '')}-{selected}"
        
        # Set up permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                embed_links=True,
                add_reactions=True,
                use_external_emojis=True,
                read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_messages=True,
                attach_files=True,
                embed_links=True
            )
        }
        
        # Add admin permissions
        for member in guild.members:
            if member.guild_permissions.administrator:
                overwrites[member] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    attach_files=True,
                    embed_links=True,
                    manage_channels=True
                )
        
        # Add support role permissions
        for role in guild.roles:
            if "support" in role.name.lower():
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    attach_files=True,
                    embed_links=True,
                    manage_channels=True
                )
        
        # Create the channel
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=support_category,
            overwrites=overwrites
        )
        
        # Create welcome embed
        embed = discord.Embed(
            title=f"{category['emoji']} {category['name']}",
            description=f"Welcome {user.mention}! This ticket has been created for: **{category['description']}**",
            color=0x5B2C6F
        )
        
        embed.add_field(
            name="📋 Guidelines",
            value="• Please describe your issue clearly\n• Provide relevant details or screenshots\n• Be patient while we assist you\n• Use the close button when resolved",
            inline=False
        )
        
        embed.set_footer(text="Voralith Support • A staff member will assist you shortly")
        embed.timestamp = datetime.datetime.now()
        
        # Add close button
        close_view = TicketCloseView()
        await ticket_channel.send(embed=embed, view=close_view)
        
        # Confirm to user
        await interaction.response.send_message(
            f"✅ Your {category['name'].lower()} ticket has been created: {ticket_channel.mention}",
            ephemeral=True
        )

class LegacyVerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='🔒 Verify Identity', style=discord.ButtonStyle.primary, emoji='🔒')
    async def legacy_verify_identity(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Same logic as PermanentVerificationView
        user_id = interaction.user.id
        guild_id = interaction.guild.id if interaction.guild else None
        
        if user_id in verified_users:
            await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
            return
        
        # Generate secure state for OAuth2
        state = secrets.token_urlsafe(32)
        oauth_states[user_id] = {
            'state': state,
            'guild_id': guild_id,
            'timestamp': datetime.datetime.utcnow()
        }
        
        # Create OAuth2 URL with proper permissions
        oauth_url = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions=0&scope=identify%20guilds.join&response_type=code&redirect_uri={urllib.parse.quote(REDIRECT_URI)}&state={state}"
        
        embed = discord.Embed(
            title="🔒 Identity Verification Required",
            description="To complete verification and receive your verified role, please follow these steps:",
            color=0x5B2C6F
        )
        
        embed.add_field(
            name="Step 1: Authorize",
            value=f"[Click here to authorize with Discord]({oauth_url})",
            inline=False
        )
        
        embed.add_field(
            name="Step 2: Complete",
            value="After authorization, click the 'Complete Verification' button that will appear.",
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Security Notice",
            value="This process only accesses your basic Discord profile and allows the bot to assign your verified role. No sensitive data is collected.",
            inline=False
        )
        
        embed.set_footer(text="Voralith Verification System")
        
        # Create completion view
        complete_view = CompleteVerificationView(user_id, state)
        
        await interaction.response.send_message(embed=embed, view=complete_view, ephemeral=True)
        
        logger.info(f"User {interaction.user.name} ({user_id}) started legacy verification process")

class LegacyCustomOrderView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="📝 Create Custom Order Ticket", style=discord.ButtonStyle.primary, emoji="🎨")
    async def legacy_create_custom_order_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Same logic as CustomOrderView
        try:
            guild = interaction.guild
            user = interaction.user
            
            # Find or create Support category
            support_category = None
            for category in guild.categories:
                if "support" in category.name.lower() or "ticket" in category.name.lower():
                    support_category = category
                    break
            
            if not support_category:
                support_category = await guild.create_category("Support")
            
            # Create ticket channel name
            channel_name = f"custom-order-{user.name.lower().replace(' ', '')}"
            
            # Set up permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    add_reactions=True,
                    use_external_emojis=True,
                    read_message_history=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    attach_files=True,
                    embed_links=True
                )
            }
            
            # Add permissions for admin and support roles
            for member in guild.members:
                if member.guild_permissions.administrator:
                    overwrites[member] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        manage_messages=True,
                        attach_files=True,
                        embed_links=True,
                        manage_channels=True
                    )
            
            for role in guild.roles:
                if "support" in role.name.lower():
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        manage_messages=True,
                        attach_files=True,
                        embed_links=True,
                        manage_channels=True
                    )
            
            # Create the ticket channel
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=support_category,
                overwrites=overwrites
            )
            
            # Create custom order ticket embed (same as CustomOrderView)
            embed = discord.Embed(
                title="🎨 Custom Order Ticket",
                description=f"Welcome {user.mention}! This ticket has been created for your custom order request.",
                color=0x5B2C6F
            )
            
            embed.add_field(
                name="📋 What to Include",
                value="Please provide the following information:",
                inline=False
            )
            
            embed.add_field(
                name="🎯 Order Details",
                value="• **What you want**: Detailed description of your custom order\n• **Purpose**: What will this be used for?\n• **Style preferences**: Colors, themes, design elements",
                inline=False
            )
            
            embed.add_field(
                name="📐 Specifications",
                value="• **Size/dimensions**: If applicable\n• **Format**: File type needed (PNG, JPG, MP4, etc.)\n• **Resolution**: Quality requirements",
                inline=False
            )
            
            embed.add_field(
                name="⏰ Timeline",
                value="• **Deadline**: When do you need this completed?\n• **Urgency level**: Rush order or standard timing?",
                inline=False
            )
            
            embed.add_field(
                name="💰 Budget",
                value="• **Budget range**: What's your expected price range?\n• **Payment method**: Preferred payment option",
                inline=False
            )
            
            embed.add_field(
                name="📎 References",
                value="• **Examples**: Share any reference images or links\n• **Inspiration**: Similar work you've seen and liked",
                inline=False
            )
            
            embed.set_footer(
                text="Voralith • Custom Orders • A staff member will assist you shortly"
            )
            embed.timestamp = datetime.datetime.now()
            
            # Create close button view
            close_view = TicketCloseView()
            
            # Send the embed with close button
            await ticket_channel.send(embed=embed, view=close_view)
            
            # Send confirmation to user
            success_embed = discord.Embed(
                title="✅ Custom Order Ticket Created",
                description=f"Your custom order ticket has been created: {ticket_channel.mention}",
                color=0x5B2C6F
            )
            success_embed.add_field(
                name="Next Steps",
                value="Please fill out the information requested in your ticket. A staff member will review your request and provide a quote.",
                inline=False
            )
            
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error creating legacy custom order ticket: {e}")
            await interaction.response.send_message("❌ An error occurred while creating your custom order ticket. Please try again.", ephemeral=True)

async def heartbeat_system():
    """Heartbeat system to maintain Discord connection"""
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        try:
            if bot.is_ready():
                logger.info(f"Heartbeat: Bot active in {len(bot.guilds)} guilds")
                
                # Perform a light activity to maintain connection
                if bot.guilds:
                    guild = bot.guilds[0]
                    # Update presence to show activity
                    await bot.change_presence(activity=discord.Game(name="free boosting in tickets"))
                    logger.info(f"Heartbeat: Active in {guild.name}")
            else:
                logger.warning("Heartbeat: Bot not ready!")
                
            # Wait 5 minutes before next heartbeat
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"Heartbeat error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error

@bot.event
async def on_ready():
    logger.info(f"{bot.user.name} has connected to Discord!")
    logger.info(f"Bot is in {len(bot.guilds)} guilds")
    
    # Initialize database
    init_database()
    
    # Add persistent views for ticket systems and other interactions
    bot.add_view(TicketView())
    bot.add_view(PermanentVerificationView())
    bot.add_view(CustomOrderView())
    bot.add_view(TicketCloseView())
    bot.add_view(TicketCloseConfirmView())
    
    # Log persistent view registration
    logger.info("Registered persistent views: TicketView, PermanentVerificationView, CustomOrderView, TicketCloseView, TicketCloseConfirmView")
    
    # Set bot activity
    await bot.change_presence(activity=discord.Game(name="free boosting in tickets"))
    
    # Start the giveaway checker
    if not check_giveaways.is_running():
        check_giveaways.start()
    
    # Start heartbeat system to maintain connection
    bot.loop.create_task(heartbeat_system())
    
    # Simple command synchronization
    logger.info("Starting command synchronization...")
    try:
        # Wait a moment for Discord API stability
        await asyncio.sleep(2)
        
        # Log all currently defined commands
        commands_list = [cmd.name for cmd in bot.tree.walk_commands()]
        logger.info(f"Commands defined in bot: {len(commands_list)}")
        for cmd in bot.tree.walk_commands():
            logger.info(f"  - {cmd.name}: {cmd.description}")
        
        # Direct sync without clearing
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s) successfully")
        for cmd in synced:
            logger.info(f"  ✓ Synced: {cmd.name}")
                
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")

@bot.tree.command(name="giveaway", description="Create a new giveaway (Admin only)")
async def giveaway_command(interaction: discord.Interaction, prize: str, duration: str):
    """
    Create a new giveaway
    
    Parameters:
    prize: The prize for the giveaway
    duration: Duration in format like '1h', '30m', '2d', '1w'
    """
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    # Parse duration
    duration_seconds = parse_duration(duration)
    if duration_seconds is None:
        await interaction.response.send_message("❌ Invalid duration format! Use formats like: 1h, 30m, 2d, 1w", ephemeral=True)
        return
    
    global giveaway_counter
    giveaway_counter += 1
    giveaway_id = giveaway_counter
    
    end_time = datetime.datetime.utcnow() + datetime.timedelta(seconds=duration_seconds)
    
    # Create giveaway data
    giveaway = {
        'id': giveaway_id,
        'prize': prize,
        'end_time': end_time,
        'participants': [],
        'channel_id': interaction.channel.id,
        'message_id': None,
        'host_id': interaction.user.id
    }
    
    # Create embed
    embed = discord.Embed(
        title="🎉 GIVEAWAY 🎉",
        description=f"**Prize:** {prize}\n**Ends:** <t:{int(end_time.timestamp())}:R>\n**Hosted by:** {interaction.user.mention}",
        color=0x5B2C6F
    )
    embed.add_field(name="How to join:", value="Click the button below to join!", inline=False)
    embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
    
    # Create view with button
    view = GiveawayView(giveaway_id)
    
    # Send the giveaway message
    await interaction.response.send_message(embed=embed, view=view)
    
    # Get the message to store its ID
    message = await interaction.original_response()
    giveaway['message_id'] = message.id
    
    # Store the giveaway
    active_giveaways[giveaway_id] = giveaway
    
    logger.info(f"Created giveaway {giveaway_id} for {prize} ending at {end_time}")

def parse_duration(duration_str):
    """Parse duration string into seconds"""
    duration_str = duration_str.lower().strip()
    
    # Extract number and unit
    if duration_str[-1] in ['s', 'm', 'h', 'd', 'w']:
        try:
            number = int(duration_str[:-1])
            unit = duration_str[-1]
            
            multipliers = {
                's': 1,
                'm': 60,
                'h': 3600,
                'd': 86400,
                'w': 604800
            }
            
            return number * multipliers[unit]
        except ValueError:
            return None
    
    return None

@tasks.loop(seconds=60)
async def check_giveaways():
    """Check for ended giveaways and announce winners"""
    current_time = datetime.datetime.utcnow()
    ended_giveaways = []
    
    for giveaway_id, giveaway in active_giveaways.items():
        if current_time >= giveaway['end_time']:
            ended_giveaways.append(giveaway_id)
    
    for giveaway_id in ended_giveaways:
        await end_giveaway(giveaway_id)

async def end_giveaway(giveaway_id):
    """End a giveaway and announce the winner"""
    if giveaway_id not in active_giveaways:
        return
    
    giveaway = active_giveaways[giveaway_id]
    
    try:
        channel = bot.get_channel(giveaway['channel_id'])
        if not channel:
            logger.error(f"Could not find channel for giveaway {giveaway_id}")
            return
        
        participants = giveaway['participants']
        
        if not participants:
            # No winner
            embed = discord.Embed(
                title="🎉 Giveaway Ended 🎉",
                description=f"**Prize:** {giveaway['prize']}\n**Winner:** No one participated! 😢",
                color=0x5B2C6F
            )
            embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
            await channel.send(embed=embed)
        else:
            # Select winner
            winner_id = random.choice(participants)
            winner = bot.get_user(winner_id)
            
            embed = discord.Embed(
                title="🎉 Giveaway Ended 🎉",
                description=f"**Prize:** {giveaway['prize']}\n**Winner:** {winner.mention if winner else 'Unknown User'}\n**Participants:** {len(participants)}",
                color=0x5B2C6F
            )
            embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
            await channel.send(f"🎉 Congratulations {winner.mention if winner else 'Unknown User'}! You won **{giveaway['prize']}**!", embed=embed)
            
            logger.info(f"Giveaway {giveaway_id} ended. Winner: {winner.name if winner else 'Unknown'}")
        
        # Remove from active giveaways
        del active_giveaways[giveaway_id]
        
    except Exception as e:
        logger.error(f"Error ending giveaway {giveaway_id}: {e}")

@bot.tree.command(name="giveaway_info", description="Display information about active giveaways in this server (Admin only)")
async def giveaway_info(interaction: discord.Interaction):
    """Display information about active giveaways in this server"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    # Get active giveaways for this server
    server_giveaways = [g for g in active_giveaways.values() if g['channel_id'] in [c.id for c in interaction.guild.channels]]
    
    if not server_giveaways:
        embed = discord.Embed(
            title="📊 Active Giveaways",
            description="No active giveaways in this server.",
            color=0x5B2C6F
        )
    else:
        embed = discord.Embed(
            title="📊 Active Giveaways",
            description=f"Found {len(server_giveaways)} active giveaway(s):",
            color=0x5B2C6F
        )
        
        for giveaway in server_giveaways:
            embed.add_field(
                name=f"🎁 {giveaway['prize']}",
                value=f"**ID:** {giveaway['id']}\n**Ends:** <t:{int(giveaway['end_time'].timestamp())}:R>\n**Participants:** {len(giveaway['participants'])}",
                inline=True
            )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="purchase_info", description="Display purchase information with payment options (Admin only)")
async def purchase_info(interaction: discord.Interaction):
    """Display purchase information with payment options"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="💳 Purchase Information",
        description="Available payment methods and purchase options:",
        color=0x5B2C6F
    )
    
    embed.add_field(
        name="💰 Payment Methods",
        value="• PayPal\n• Crypto (Bitcoin, Ethereum)\n• Bank Transfer\n• Gift Cards",
        inline=True
    )
    
    embed.add_field(
        name="🛍️ Available Services",
        value="• Discord Server Boosts\n• Custom Bot Development\n• Server Setup & Management\n• Premium Features",
        inline=True
    )
    
    embed.add_field(
        name="📞 Contact",
        value="Open a support ticket using `/ticket` for pricing and custom orders.",
        inline=False
    )
    
    embed.set_footer(text="Voralith Services", icon_url="https://cdn.discordapp.com/attachments/1156246022104825920/1321844863446892574/voralith-logo.png")
    
    await interaction.response.send_message(embed=embed)

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the ticket channel"""
        try:
            # Check if user has permission to close the ticket
            channel = interaction.channel
            user = interaction.user
            
            # Allow ticket creator, admins, or support staff to close
            can_close = False
            
            # Check if user is admin
            if user.guild_permissions.administrator:
                can_close = True
            
            # Check if user is the ticket creator (channel name contains their name)
            if channel.name.startswith(f"ticket-{user.name.lower()}"):
                can_close = True
            
            # Check if user has specific support role (you can modify this)
            for role in user.roles:
                if "support" in role.name.lower() or "staff" in role.name.lower():
                    can_close = True
                    break
            
            if not can_close:
                await interaction.response.send_message("❌ You don't have permission to close this ticket.", ephemeral=True)
                return
            
            # Create confirmation embed
            embed = discord.Embed(
                title="🔒 Close Ticket",
                description=f"Are you sure you want to close this ticket?\n\n**Closed by:** {user.mention}\n**Channel:** {channel.mention}",
                color=0xff4444
            )
            embed.add_field(
                name="⚠️ Warning",
                value="This action cannot be undone. The channel will be permanently deleted.",
                inline=False
            )
            
            # Create confirmation view
            confirm_view = TicketCloseConfirmView()
            
            await interaction.response.send_message(embed=embed, view=confirm_view)
            
        except Exception as e:
            print(f"Error in close ticket: {e}")
            await interaction.response.send_message("❌ An error occurred while trying to close the ticket.", ephemeral=True)

class TicketCloseConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✅ Confirm Close", style=discord.ButtonStyle.danger, custom_id="confirm_close_button")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm ticket closure"""
        try:
            channel = interaction.channel
            user = interaction.user
            guild = interaction.guild
            
            # Create transcript before closing
            await self.create_transcript(channel, user, guild)
            
            # Send final message
            embed = discord.Embed(
                title="🔒 Ticket Closed",
                description=f"This ticket has been closed by {user.mention}.\n\n📄 Transcript saved to #transcript\nChannel will be deleted in 5 seconds...",
                color=0xff4444
            )
            embed.set_footer(text="Thank you for using Voralith Support!")
            
            await interaction.response.send_message(embed=embed)
            
            # Wait 5 seconds then delete
            await asyncio.sleep(5)
            await channel.delete(reason=f"Ticket closed by {user.name}")
            
        except Exception as e:
            print(f"Error confirming ticket close: {e}")
            await interaction.response.send_message("❌ An error occurred while closing the ticket.", ephemeral=True)
    
    async def create_transcript(self, channel, closed_by, guild):
        """Create a beautiful HTML transcript of the ticket conversation"""
        try:
            # Find transcript channel
            transcript_channel = None
            for ch in guild.text_channels:
                if ch.name.lower() == "transcript":
                    transcript_channel = ch
                    break
            
            if not transcript_channel:
                print("No #transcript channel found")
                return
            
            # Get all messages from the ticket
            messages = []
            async for message in channel.history(limit=None, oldest_first=True):
                messages.append(message)
            
            # Create HTML transcript
            html_content = await self.generate_html_transcript(channel, closed_by, messages)
            
            # Save HTML to a file
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html_content)
                html_file_path = f.name
            
            # Send transcript to transcript channel
            embed = discord.Embed(
                title="🎫 New Ticket Transcript",
                description=f"**Ticket:** {channel.name}\n**Closed by:** {closed_by.mention}\n**Date:** <t:{int(discord.utils.utcnow().timestamp())}:F>\n**Messages:** {len(messages)}",
                color=0x5B2C6F
            )
            embed.set_footer(text="Voralith Support System")
            
            # Send the HTML file
            with open(html_file_path, 'rb') as f:
                discord_file = discord.File(f, filename=f"transcript-{channel.name}.html")
                await transcript_channel.send(embed=embed, file=discord_file)
            
            # Clean up the temporary file
            os.unlink(html_file_path)
            
            print(f"HTML transcript created for {channel.name} in #transcript")
            
        except Exception as e:
            print(f"Error creating transcript: {e}")
    
    async def generate_html_transcript(self, channel, closed_by, messages):
        """Generate beautiful HTML transcript"""
        
        # Filter out system messages but keep user content
        filtered_messages = []
        for message in messages:
            # Skip empty bot embeds but keep bot text messages
            if message.author.bot and not message.content and message.embeds:
                continue
            filtered_messages.append(message)
        
        html_template = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transcript - {channel.name}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #2c2f33 0%, #23272a 100%);
            color: #dcddde;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            background: linear-gradient(135deg, #5B2C6F 0%, #7c3aed 100%);
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        
        .header h1 {{
            color: white;
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }}
        
        .header-info {{
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            margin-top: 20px;
        }}
        
        .header-info p {{
            margin: 5px 0;
            font-size: 1.1rem;
        }}
        
        .messages {{
            background: #36393f;
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.2);
        }}
        
        .message {{
            margin-bottom: 20px;
            padding: 15px;
            background: #40444b;
            border-radius: 10px;
            border-left: 4px solid #5B2C6F;
            transition: transform 0.2s ease;
        }}
        
        .message:hover {{
            transform: translateX(5px);
        }}
        
        .message-header {{
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }}
        
        .avatar {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: linear-gradient(45deg, #5B2C6F, #7c3aed);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 15px;
            font-weight: bold;
            color: white;
            text-transform: uppercase;
        }}
        
        .message-info {{
            flex: 1;
        }}
        
        .username {{
            font-weight: bold;
            color: #ffffff;
            font-size: 1.1rem;
        }}
        
        .timestamp {{
            color: #72767d;
            font-size: 0.9rem;
            margin-left: 10px;
        }}
        
        .message-content {{
            margin-left: 55px;
            line-height: 1.6;
            word-wrap: break-word;
        }}
        
        .attachment {{
            background: #2f3136;
            border: 1px solid #5B2C6F;
            border-radius: 8px;
            padding: 10px;
            margin: 10px 0;
            display: inline-block;
        }}
        
        .attachment a {{
            color: #7c3aed;
            text-decoration: none;
            font-weight: bold;
        }}
        
        .attachment a:hover {{
            text-decoration: underline;
        }}
        
        .image-preview {{
            max-width: 400px;
            max-height: 300px;
            border-radius: 8px;
            margin: 10px 0;
        }}
        
        .bot-message {{
            border-left-color: #7289da;
        }}
        
        .bot-message .avatar {{
            background: linear-gradient(45deg, #7289da, #5865f2);
        }}
        
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding: 20px;
            color: #72767d;
            font-size: 0.9rem;
        }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        
        .stat {{
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }}
        
        .stat-number {{
            font-size: 2rem;
            font-weight: bold;
            color: #7c3aed;
        }}
        
        .stat-label {{
            color: #dcddde;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎫 Transcript Voralith</h1>
            <div class="header-info">
                <p><strong>Salon:</strong> {channel.name}</p>
                <p><strong>Fermé par:</strong> {closed_by.display_name}</p>
                <p><strong>Date:</strong> {discord.utils.utcnow().strftime('%d/%m/%Y à %H:%M')}</p>
            </div>
            <div class="stats">
                <div class="stat">
                    <div class="stat-number">{len(filtered_messages)}</div>
                    <div class="stat-label">Messages</div>
                </div>
                <div class="stat">
                    <div class="stat-number">{len(set(msg.author.id for msg in filtered_messages))}</div>
                    <div class="stat-label">Participants</div>
                </div>
            </div>
        </div>
        
        <div class="messages">
"""

        # Add messages
        for message in filtered_messages:
            # Get first letter for avatar
            avatar_letter = message.author.display_name[0] if message.author.display_name else "?"
            
            # Format timestamp
            timestamp = message.created_at.strftime('%d/%m/%Y %H:%M:%S')
            
            # Bot or user styling
            message_class = "message bot-message" if message.author.bot else "message"
            
            # Format content
            content = message.content if message.content else "<em>Aucun contenu texte</em>"
            content = content.replace('\n', '<br>')
            
            html_template += f"""
            <div class="{message_class}">
                <div class="message-header">
                    <div class="avatar">{avatar_letter}</div>
                    <div class="message-info">
                        <span class="username">{message.author.display_name}</span>
                        <span class="timestamp">{timestamp}</span>
                    </div>
                </div>
                <div class="message-content">
                    {content}
"""
            
            # Add attachments
            if message.attachments:
                for attachment in message.attachments:
                    # Check if it's an image
                    if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                        html_template += f"""
                    <div class="attachment">
                        <p>📷 <strong>Image:</strong> {attachment.filename}</p>
                        <img src="{attachment.url}" alt="{attachment.filename}" class="image-preview">
                    </div>
"""
                    else:
                        html_template += f"""
                    <div class="attachment">
                        📎 <strong>Fichier:</strong> <a href="{attachment.url}" target="_blank">{attachment.filename}</a>
                    </div>
"""
            
            html_template += """
                </div>
            </div>
"""

        # Close HTML
        html_template += """
        </div>
        
        <div class="footer">
            <p>Transcript généré automatiquement par <strong>Voralith Support System</strong></p>
            <p>© 2025 Voralith - Système de support professionnel</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html_template
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary, custom_id="cancel_close_button")
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel ticket closure"""
        embed = discord.Embed(
            title="✅ Ticket Closure Cancelled",
            description="The ticket will remain open.",
            color=0x5B2C6F
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Remove the confirmation message
        await interaction.message.delete()

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelectMenu())

class TicketSelectMenu(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="💰 Purchase Support",
                value="purchase",
                description="Questions about buying services or products"
            ),
            discord.SelectOption(
                label="🔧 Technical Support",
                value="technical",
                description="Technical issues or bugs"
            ),
            discord.SelectOption(
                label="❓ General Support",
                value="general",
                description="General questions and assistance"
            ),
            discord.SelectOption(
                label="🚨 Report Issue",
                value="report",
                description="Report a user or issue"
            )
        ]
        super().__init__(placeholder="Select a support category...", options=options, custom_id="ticket_select_menu")

    async def callback(self, interaction: discord.Interaction):
        category_info = {
            "purchase": {
                "title": "💰 Purchase Support",
                "description": "Thank you for your interest in our services! Please provide details about what you'd like to purchase.",
                "guidelines": "• Include your budget range\n• Specify the service you need\n• Mention any special requirements\n• Include your preferred payment method"
            },
            "technical": {
                "title": "🔧 Technical Support",
                "description": "We're here to help with technical issues. Please describe your problem in detail.",
                "guidelines": "• Describe the issue clearly\n• Include error messages if any\n• Mention what you were trying to do\n• Include screenshots if helpful"
            },
            "general": {
                "title": "❓ General Support",
                "description": "Ask us anything! We're happy to help with general questions.",
                "guidelines": "• Be clear and specific\n• Include relevant context\n• Ask one question at a time\n• Be patient for our response"
            },
            "report": {
                "title": "🚨 Report Issue",
                "description": "Thank you for reporting this issue. Please provide as much detail as possible.",
                "guidelines": "• Include user ID if reporting a user\n• Describe what happened\n• Provide evidence if available\n• Include date and time of incident"
            }
        }
        
        selected = category_info[self.values[0]]
        
        # Create the actual ticket channel
        try:
            guild = interaction.guild
            user = interaction.user
            
            # Look for existing ticket categories
            ticket_category = None
            for category in guild.categories:
                if any(word in category.name.lower() for word in ['ticket', 'support', 'aide']):
                    ticket_category = category
                    break
            
            # If no ticket category found, create one
            if not ticket_category:
                ticket_category = await guild.create_category("🎫 Tickets")
            
            # Create ticket channel name
            ticket_name = f"ticket-{user.name}".replace(" ", "-").lower()
            
            # Check if user already has a ticket open
            existing_ticket = None
            for channel in ticket_category.channels:
                if channel.name == ticket_name:
                    existing_ticket = channel
                    break
            
            if existing_ticket:
                await interaction.response.send_message(f"❌ You already have a ticket open: {existing_ticket.mention}", ephemeral=True)
                return
            
            # Set permissions for the ticket channel
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                user: discord.PermissionOverwrite(
                    read_messages=True, 
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    use_external_emojis=True,
                    add_reactions=True,
                    use_application_commands=False  # Disable slash commands
                ),
                guild.me: discord.PermissionOverwrite(
                    read_messages=True, 
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    manage_messages=True,
                    use_application_commands=True  # Bot can use commands
                )
            }
            
            # Add admin permissions
            for member in guild.members:
                if member.guild_permissions.administrator:
                    overwrites[member] = discord.PermissionOverwrite(
                        read_messages=True, 
                        send_messages=True,
                        attach_files=True,
                        embed_links=True,
                        manage_messages=True,
                        use_application_commands=True  # Admins can use commands
                    )
            
            # Add support/staff role permissions
            for role in guild.roles:
                if "support" in role.name.lower() or "staff" in role.name.lower():
                    overwrites[role] = discord.PermissionOverwrite(
                        read_messages=True, 
                        send_messages=True,
                        attach_files=True,
                        embed_links=True,
                        manage_messages=True,
                        use_application_commands=True  # Support can use commands
                    )
            
            # Create the ticket channel
            ticket_channel = await guild.create_text_channel(
                name=ticket_name,
                category=ticket_category,
                overwrites=overwrites
            )
            
            # Create initial ticket embed
            embed = discord.Embed(
                title=selected["title"],
                description=f"Hello {user.mention}! Thank you for opening a ticket.\n\n{selected['description']}",
                color=0x5B2C6F
            )
            embed.add_field(
                name="📝 Guidelines",
                value=selected["guidelines"],
                inline=False
            )
            embed.add_field(
                name="⚠️ Important",
                value="• Please be patient while waiting for a response\n• Only staff members can see this channel\n• Use the button below to close this ticket when resolved",
                inline=False
            )
            embed.set_footer(text="Voralith Support Team", icon_url="https://cdn.discordapp.com/attachments/1156246022104825920/1321844863446892574/voralith-logo.png")
            
            # Create close button view
            close_view = TicketCloseView()
            
            await ticket_channel.send(f"{user.mention}", embed=embed, view=close_view)
            
            # Respond to the user
            await interaction.response.send_message(f"✅ Your ticket has been created: {ticket_channel.mention}", ephemeral=True)
            
        except Exception as e:
            print(f"Error creating ticket: {e}")
            await interaction.response.send_message("❌ An error occurred while creating your ticket. Please try again.", ephemeral=True)

@bot.tree.command(name="setup-tickets", description="Create a support ticket system (Admin only)")
async def setup_tickets_command(interaction: discord.Interaction):
    """Create a support ticket system"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🎫 Support Ticket System",
        description="Select a category below to open a support ticket. Our team will assist you as soon as possible.",
        color=0x5B2C6F
    )
    
    embed.add_field(
        name="Available Categories:",
        value="• **Purchase Support** - Questions about services\n• **Technical Support** - Bug reports and technical issues\n• **General Support** - General questions and help\n• **Report Issue** - Report users or problems",
        inline=False
    )
    
    embed.set_footer(text="Voralith Support Team", icon_url="https://cdn.discordapp.com/attachments/1156246022104825920/1321844863446892574/voralith-logo.png")
    
    view = TicketView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="announcement", description="Create a professional announcement embed (Admin only)")
async def announcement(interaction: discord.Interaction, title: str, description: str, image_url: str = ""):
    """Create a professional announcement embed"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"📢 {title}",
        description=description,
        color=0x5B2C6F,
        timestamp=datetime.datetime.utcnow()
    )
    
    if image_url:
        embed.set_image(url=image_url)
    
    embed.set_author(name="Voralith Announcement", icon_url="https://cdn.discordapp.com/attachments/1156246022104825920/1321844863446892574/voralith-logo.png")
    embed.set_footer(text="Voralith Team")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="update_log", description="Create an update log with changelog (Admin only)")
async def update_log(interaction: discord.Interaction, version: str, updates: str, download_link: str = "", image_url: str = ""):
    """Create an update log with changelog"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title=f"🔄 Update {version}",
        description="New update available!",
        color=0x5B2C6F,
        timestamp=datetime.datetime.utcnow()
    )
    
    # Format updates - split by lines and add bullet points
    formatted_updates = "\n".join([f"• {line.strip()}" for line in updates.split('\n') if line.strip()])
    
    embed.add_field(
        name="📝 Changelog",
        value=formatted_updates,
        inline=False
    )
    
    if download_link:
        embed.add_field(
            name="⬇️ Download",
            value=f"[Click here to download]({download_link})",
            inline=False
        )
    
    if image_url:
        embed.set_image(url=image_url)
    
    embed.set_author(name="Voralith Updates", icon_url="https://cdn.discordapp.com/attachments/1156246022104825920/1321844863446892574/voralith-logo.png")
    embed.set_footer(text="Voralith Development Team")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="reconnect", description="Reconnect verified members to the server (Admin only)")
async def reconnect_command(interaction: discord.Interaction):
    """Allow admins to use the reconnection system to bring back verified members"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🔄 Member Reconnection System",
        description="This system helps reconnect verified members who may have left the server.",
        color=0x5B2C6F
    )
    
    embed.add_field(
        name="📊 Statistics",
        value=f"• **Verified Members:** {len(verified_users)}\n• **Pending Verifications:** {len(verification_pending)}\n• **Total Processed:** {len(verified_users) + len(verification_pending)}",
        inline=False
    )
    
    embed.add_field(
        name="🔧 How it works",
        value="The system automatically tracks verified members and can help them rejoin with their verified status intact.",
        inline=False
    )
    
    embed.set_footer(text="Voralith Reconnection System", icon_url="https://cdn.discordapp.com/attachments/1156246022104825920/1321844863446892574/voralith-logo.png")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

class PermanentVerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='🔒 Verify Identity', style=discord.ButtonStyle.primary, custom_id='permanent_verify_identity')
    async def permanent_verify_identity(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle permanent verification button click with automatic role assignment"""
        
        user_id = interaction.user.id
        guild_id = interaction.guild.id if interaction.guild else None
        
        if user_id in verified_users:
            await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
            return
        
        # Generate secure state for OAuth2
        state = secrets.token_urlsafe(32)
        oauth_states[user_id] = {
            'state': state,
            'guild_id': guild_id,
            'timestamp': datetime.datetime.utcnow()
        }
        
        # Create OAuth2 URL with proper permissions
        oauth_url = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&permissions=0&scope=identify%20guilds.join&response_type=code&redirect_uri={urllib.parse.quote(REDIRECT_URI)}&state={state}"
        
        embed = discord.Embed(
            title="🔒 Identity Verification Required",
            description="To complete verification and receive your verified role, please follow these steps:",
            color=0x5B2C6F
        )
        
        embed.add_field(
            name="Step 1: Authorize",
            value=f"[Click here to authorize with Discord]({oauth_url})",
            inline=False
        )
        
        embed.add_field(
            name="Step 2: Complete",
            value="After authorization, click the 'Complete Verification' button that will appear.",
            inline=False
        )
        
        embed.add_field(
            name="🛡️ Security Notice",
            value="This process only accesses your basic Discord profile and allows the bot to assign your verified role. No sensitive data is collected.",
            inline=False
        )
        
        embed.set_footer(text="Voralith Verification System", icon_url="https://cdn.discordapp.com/attachments/1156246022104825920/1321844863446892574/voralith-logo.png")
        
        # Create completion view
        complete_view = CompleteVerificationView(user_id, state)
        
        await interaction.response.send_message(embed=embed, view=complete_view, ephemeral=True)
        
        logger.info(f"User {interaction.user.name} ({user_id}) started permanent verification process")

class VerificationConfirmView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id
    
    @discord.ui.button(label='✅ Complete Verification', style=discord.ButtonStyle.success, custom_id='complete_verification')
    async def complete_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This verification is not for you.", ephemeral=True)
            return
        
        # Add to verified users
        verified_users.add(self.user_id)
        
        # Remove from pending if exists
        if self.user_id in verification_pending:
            del verification_pending[self.user_id]
        
        # Try to assign role if in guild
        if interaction.guild:
            try:
                # Check if verified role exists, create if not
                verified_role = discord.utils.get(interaction.guild.roles, name="| Voralith | Verified")
                if not verified_role:
                    verified_role = await interaction.guild.create_role(
                        name="| Voralith | Verified",
                        color=discord.Color.purple(),
                        reason="Voralith verification system"
                    )
                
                # Add role to user
                member = interaction.guild.get_member(self.user_id)
                if member and verified_role not in member.roles:
                    await member.add_roles(verified_role, reason="Completed Voralith verification")
                    
                    logger.info(f"Successfully assigned verified role to {member.name}")
                    
                    await interaction.response.send_message(f"✅ **Verification Complete!**\n\nYou have been successfully verified and assigned the {verified_role.mention} role!\n\n🎉 Welcome to the verified community!", ephemeral=True)
                else:
                    await interaction.response.send_message("✅ **Verification Complete!**\n\nYou are now verified! (Role assignment may take a moment)", ephemeral=True)
                    
            except Exception as e:
                logger.error(f"Error assigning verified role: {e}")
                await interaction.response.send_message("✅ **Verification Complete!**\n\nYou are now verified! (There was an issue with role assignment - please contact an admin)", ephemeral=True)
        else:
            await interaction.response.send_message("✅ **Verification Complete!**\n\nYou are now verified across all servers using Voralith!", ephemeral=True)
        
        logger.info(f"User {interaction.user.name} ({self.user_id}) completed verification")

class CompleteVerificationView(discord.ui.View):
    def __init__(self, user_id, oauth_state):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.oauth_state = oauth_state
    
    @discord.ui.button(label='✅ Complete Verification', style=discord.ButtonStyle.success, custom_id='complete_verification_oauth')
    async def complete_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This verification is not for you.", ephemeral=True)
            return
        
        # Check if user completed OAuth2 (simplified check)
        if self.user_id not in oauth_states:
            await interaction.response.send_message("❌ Please complete the Discord authorization first by clicking the link above.", ephemeral=True)
            return
        
        # Add to verified users
        verified_users.add(self.user_id)
        
        # Remove from pending and oauth states
        if self.user_id in verification_pending:
            del verification_pending[self.user_id]
        if self.user_id in oauth_states:
            del oauth_states[self.user_id]
        
        # Try to assign role if in guild
        if interaction.guild:
            try:
                # Check if verified role exists, create if not
                verified_role = discord.utils.get(interaction.guild.roles, name="| Voralith | Verified")
                if not verified_role:
                    verified_role = await interaction.guild.create_role(
                        name="| Voralith | Verified",
                        color=discord.Color.purple(),
                        reason="Voralith verification system"
                    )
                
                # Add role to user
                member = interaction.guild.get_member(self.user_id)
                if member and verified_role not in member.roles:
                    await member.add_roles(verified_role, reason="Completed Voralith verification")
                    
                    logger.info(f"Successfully assigned verified role to {member.name}")
                    
                    await interaction.response.send_message(f"✅ **Verification Complete!**\n\nYou have been successfully verified and assigned the {verified_role.mention} role!\n\n🎉 Welcome to the verified community!", ephemeral=True)
                else:
                    await interaction.response.send_message("✅ **Verification Complete!**\n\nYou are now verified! (Role assignment may take a moment)", ephemeral=True)
                    
            except Exception as e:
                logger.error(f"Error assigning verified role: {e}")
                await interaction.response.send_message("✅ **Verification Complete!**\n\nYou are now verified! (There was an issue with role assignment - please contact an admin)", ephemeral=True)
        else:
            await interaction.response.send_message("✅ **Verification Complete!**\n\nYou are now verified across all servers using Voralith!", ephemeral=True)
        
        logger.info(f"User {interaction.user.name} ({self.user_id}) completed OAuth2 verification")
    
    @discord.ui.button(label='❌ Cancel', style=discord.ButtonStyle.danger, custom_id='cancel_verification')
    async def cancel_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This verification is not for you.", ephemeral=True)
            return
        
        # Clean up OAuth state
        if self.user_id in oauth_states:
            del oauth_states[self.user_id]
        
        await interaction.response.send_message("❌ Verification cancelled.", ephemeral=True)
        logger.info(f"User {interaction.user.name} ({self.user_id}) cancelled verification")

@bot.tree.command(name="setup_verification", description="Setup verification channel (Admin only)")
async def setup_verification(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Setup the verification system in a channel"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    target_channel = channel or interaction.channel
    
    embed = discord.Embed(
        title="🔒 Identity Verification System",
        description="Welcome to our verification system! Click the button below to verify your identity and gain access to exclusive features.",
        color=0x5B2C6F
    )
    
    embed.add_field(
        name="🛡️ Why Verify?",
        value="• Access to exclusive channels\n• Participate in giveaways\n• Enhanced server permissions\n• Anti-bot protection",
        inline=False
    )
    
    embed.add_field(
        name="📋 Verification Process",
        value="1. Click the 'Verify Identity' button\n2. Complete Discord authorization\n3. Receive your verified role automatically\n4. Enjoy full server access!",
        inline=False
    )
    
    embed.add_field(
        name="🔐 Security & Privacy",
        value="Your verification is secure and private. We only access basic Discord information needed for verification.",
        inline=False
    )
    
    embed.set_footer(text="Voralith Verification System", icon_url="https://cdn.discordapp.com/attachments/1156246022104825920/1321844863446892574/voralith-logo.png")
    
    view = PermanentVerificationView()
    await target_channel.send(embed=embed, view=view)
    
    await interaction.response.send_message(f"✅ Verification system setup in {target_channel.mention}!", ephemeral=True)

@bot.tree.command(name="verify_stats", description="View verification statistics (Admin only)")
async def verify_stats(interaction: discord.Interaction):
    """View verification statistics"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="📊 Verification Statistics",
        description="Current verification system statistics:",
        color=0x5B2C6F
    )
    
    embed.add_field(
        name="✅ Verified Users",
        value=str(len(verified_users)),
        inline=True
    )
    
    embed.add_field(
        name="⏳ Pending Verifications",
        value=str(len(verification_pending)),
        inline=True
    )
    
    embed.add_field(
        name="🔄 OAuth Sessions",
        value=str(len(oauth_states)),
        inline=True
    )
    
    # Calculate verification rate
    total_interactions = len(verified_users) + len(verification_pending)
    verification_rate = (len(verified_users) / total_interactions * 100) if total_interactions > 0 else 0
    
    embed.add_field(
        name="📈 Verification Rate",
        value=f"{verification_rate:.1f}%",
        inline=True
    )
    
    embed.set_footer(text="Voralith Verification System", icon_url="https://cdn.discordapp.com/attachments/1156246022104825920/1321844863446892574/voralith-logo.png")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

class VouchView(discord.ui.View):
    def __init__(self, message: str, user: discord.User | discord.Member, image: discord.Attachment | None = None):
        super().__init__(timeout=300)
        self.message = message
        self.user = user
        self.image = image
        self.stars = None
        
        # Add star selection dropdown
        self.add_item(VouchStarSelect())
    
    async def create_vouch_embed(self, stars: int):
        """Create the vouch embed with selected stars"""
        # Get the next vouch number
        guild_id = self.user.guild.id if hasattr(self.user, 'guild') and self.user.guild else 0
        vouch_number = get_next_vouch_number(guild_id)
        
        embed = discord.Embed(
            title=f"Vouch #{vouch_number}",
            description=self.message,
            color=0x5B2C6F,
            timestamp=datetime.datetime.utcnow()
        )
        
        # Add star rating
        star_display = "⭐" * stars + "☆" * (5 - stars)
        embed.add_field(
            name="Rating",
            value=f"{star_display} ({stars}/5)",
            inline=True
        )
        
        # Add user info
        embed.set_author(
            name=f"{self.user.display_name}",
            icon_url=self.user.display_avatar.url
        )
        
        # Add image if provided
        if self.image:
            embed.set_image(url=self.image.url)
        
        embed.set_footer(text="Voralith Reviews", icon_url="https://cdn.discordapp.com/attachments/1156246022104825920/1321844863446892574/voralith-logo.png")
        
        return embed, vouch_number
    
    async def save_vouch_to_db(self, stars: int, vouch_number: int):
        """Save the vouch to database"""
        guild_id = self.user.guild.id if hasattr(self.user, 'guild') and self.user.guild else 0
        image_url = self.image.url if self.image else None
        
        save_vouch(
            guild_id=guild_id,
            user_id=self.user.id,
            username=self.user.display_name,
            message=self.message,
            stars=stars,
            image_url=image_url
        )

class VouchStarSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="⭐ 1 Star", value="1", description="Poor"),
            discord.SelectOption(label="⭐⭐ 2 Stars", value="2", description="Fair"),
            discord.SelectOption(label="⭐⭐⭐ 3 Stars", value="3", description="Good"),
            discord.SelectOption(label="⭐⭐⭐⭐ 4 Stars", value="4", description="Very Good"),
            discord.SelectOption(label="⭐⭐⭐⭐⭐ 5 Stars", value="5", description="Excellent"),
        ]
        super().__init__(placeholder="Select a star rating...", options=options)

    async def callback(self, interaction: discord.Interaction):
        stars = int(self.values[0])
        view = self.view
        
        # Create and send the vouch embed
        embed, vouch_number = await view.create_vouch_embed(stars)
        
        # Save to database
        await view.save_vouch_to_db(stars, vouch_number)
        
        # Send the public vouch
        await interaction.response.send_message(embed=embed)
        
        logger.info(f"Vouch created by {view.user.display_name} with {stars} stars")

@bot.tree.command(name="vouch", description="Leave a vouch/review with star rating")
async def vouch_command(interaction: discord.Interaction, message: str, image: discord.Attachment | None = None):
    """Create a vouch/review with star rating"""
    
    # Check if user has the Customer role
    if interaction.guild:
        customer_role = discord.utils.get(interaction.guild.roles, name="| Voralith | Customer")
        if not customer_role or customer_role not in interaction.user.roles:
            await interaction.response.send_message("❌ You need the **| Voralith | Customer** role to use this command.", ephemeral=True)
            return
    
    # Validate image if provided
    if image:
        if not image.content_type.startswith('image/'):
            await interaction.response.send_message("❌ Please upload a valid image file.", ephemeral=True)
            return
        
        # Check file size (10MB limit)
        if image.size > 10 * 1024 * 1024:
            await interaction.response.send_message("❌ Image file too large. Please upload an image smaller than 10MB.", ephemeral=True)
            return
    
    # Create the vouch view with star selection
    view = VouchView(message, interaction.user, image)
    
    embed = discord.Embed(
        title="⭐ Select Your Rating",
        description=f"Please select a star rating for your review:\n\n**Your message:** {message}",
        color=0x5B2C6F
    )
    
    if image:
        embed.set_image(url=image.url)
    
    embed.set_footer(text="Choose your rating from the dropdown below")
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="setup-reviews", description="Setup the review system in this channel (Admin only)")
async def setup_reviews_command(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Setup the review system in a channel"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    target_channel = channel or interaction.channel
    
    # Add channel to sticky channels and create initial sticky message
    embed = await create_sticky_review_embed()
    message = await target_channel.send(embed=embed)
    sticky_channels[target_channel.id] = message.id
    
    logger.info(f"Setup sticky review message in {target_channel.name}")
    
    # Confirm to admin
    await interaction.response.send_message(f"✅ Sticky review system setup successfully in {target_channel.mention}!\n💡 The review format will automatically stay at the bottom of the channel.", ephemeral=True)

@bot.tree.command(name="remove-sticky", description="Remove sticky review message from this channel (Admin only)")
async def remove_sticky_command(interaction: discord.Interaction, channel: discord.TextChannel = None):
    """Remove sticky review system from a channel"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    target_channel = channel or interaction.channel
    
    if target_channel.id in sticky_channels:
        # Delete the sticky message
        try:
            message = await target_channel.fetch_message(sticky_channels[target_channel.id])
            await message.delete()
        except:
            pass  # Message might already be deleted
        
        # Remove from sticky channels
        del sticky_channels[target_channel.id]
        
        logger.info(f"Removed sticky review message from {target_channel.name}")
        await interaction.response.send_message(f"✅ Sticky review system removed from {target_channel.mention}!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ No sticky review system found in {target_channel.mention}.", ephemeral=True)

@bot.tree.command(name="mute", description="Mute a user for a specified duration (Admin only)")
@discord.app_commands.describe(
    user="The user to mute",
    duration="Duration in seconds (e.g., 300 for 5 minutes)",
    reason="Reason for the mute (optional)"
)
async def mute_command(interaction: discord.Interaction, user: discord.Member, duration: int, reason: str = "No reason provided"):
    """Mute a user for a specified duration"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    try:
        # Check if duration is reasonable (max 24 hours)
        if duration > 86400:  # 24 hours in seconds
            await interaction.response.send_message("❌ Duration cannot exceed 24 hours (86400 seconds).", ephemeral=True)
            return
            
        if duration < 1:
            await interaction.response.send_message("❌ Duration must be at least 1 second.", ephemeral=True)
            return
        
        # Calculate timeout end time
        timeout_until = discord.utils.utcnow() + datetime.timedelta(seconds=duration)
        
        # Apply timeout
        await user.timeout(timeout_until, reason=f"Muted by {interaction.user.name}: {reason}")
        
        # Create success embed
        embed = discord.Embed(
            title="🔇 Utilisateur muté",
            description=f"{user.mention} a été muté avec succès.",
            color=0x5B2C6F
        )
        embed.add_field(name="👤 Utilisateur", value=f"{user.name} ({user.id})", inline=True)
        embed.add_field(name="⏰ Durée", value=f"{duration} secondes", inline=True)
        embed.add_field(name="📝 Raison", value=reason, inline=False)
        embed.add_field(name="👮 Modérateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="🕐 Fin du mute", value=f"<t:{int(timeout_until.timestamp())}:R>", inline=True)
        embed.set_footer(text="Modération Voralith")
        
        await interaction.response.send_message(embed=embed)
        
        # Log the action
        logger.info(f"User {user.name} muted by {interaction.user.name} for {duration}s. Reason: {reason}")
        
    except discord.Forbidden:
        await interaction.response.send_message("❌ Je n'ai pas les permissions pour muter cet utilisateur.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors du mute: {str(e)}", ephemeral=True)
        logger.error(f"Error muting user: {e}")

@bot.tree.command(name="unmute", description="Unmute a user immediately (Admin only)")
@discord.app_commands.describe(
    user="The user to unmute",
    reason="Reason for the unmute (optional)"
)
async def unmute_command(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    """Unmute a user immediately"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    try:
        # Check if user is actually muted
        if not user.is_timed_out():
            await interaction.response.send_message("❌ Cet utilisateur n'est pas muté.", ephemeral=True)
            return
        
        # Remove timeout
        await user.timeout(None, reason=f"Unmuted by {interaction.user.name}: {reason}")
        
        # Create success embed
        embed = discord.Embed(
            title="🔊 Utilisateur démuté",
            description=f"{user.mention} a été démuté avec succès.",
            color=0x5B2C6F
        )
        embed.add_field(name="👤 Utilisateur", value=f"{user.name} ({user.id})", inline=True)
        embed.add_field(name="📝 Raison", value=reason, inline=False)
        embed.add_field(name="👮 Modérateur", value=interaction.user.mention, inline=True)
        embed.set_footer(text="Modération Voralith")
        
        await interaction.response.send_message(embed=embed)
        
        # Log the action
        logger.info(f"User {user.name} unmuted by {interaction.user.name}. Reason: {reason}")
        
    except discord.Forbidden:
        await interaction.response.send_message("❌ Je n'ai pas les permissions pour démuter cet utilisateur.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur lors du démute: {str(e)}", ephemeral=True)
        logger.error(f"Error unmuting user: {e}")

@bot.tree.command(name="setup-rules", description="Setup server rules embed (Admin only)")
async def setup_rules_command(interaction: discord.Interaction):
    """Create a professional server rules embed"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ This command can only be used by admins in DM.", ephemeral=True)
            return
    else:  # Guild context
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command requires administrator permissions.", ephemeral=True)
            return
    
    # Create rules embed
    rules_embed = discord.Embed(
        title="📋 Server Rules",
        description="Please read and follow these rules to maintain a positive community environment.",
        color=0x5B2C6F  # Purple theme
    )
    
    # Add rules fields
    rules_embed.add_field(
        name="🤝 1. Be Respectful",
        value="Treat all members with respect. No harassment, bullying, or discrimination of any kind.",
        inline=False
    )
    
    rules_embed.add_field(
        name="🚫 2. No Spam or Self-Promotion",
        value="Avoid spamming messages, links, or self-promotion without permission from staff.",
        inline=False
    )
    
    rules_embed.add_field(
        name="💬 3. Use Appropriate Channels",
        value="Keep discussions in their designated channels. Read channel descriptions before posting.",
        inline=False
    )
    
    rules_embed.add_field(
        name="🔞 4. Keep Content Appropriate",
        value="No NSFW content, excessive profanity, or inappropriate material.",
        inline=False
    )
    
    rules_embed.add_field(
        name="🎯 5. No Drama or Arguments",
        value="Keep personal conflicts out of public channels. Use DMs or contact staff for help.",
        inline=False
    )
    
    rules_embed.add_field(
        name="🔒 6. Protect Privacy",
        value="Don't share personal information (yours or others') without consent.",
        inline=False
    )
    
    rules_embed.add_field(
        name="🎮 7. Follow Discord TOS",
        value="All Discord Terms of Service and Community Guidelines apply here.",
        inline=False
    )
    
    rules_embed.add_field(
        name="⚠️ 8. Staff Decisions are Final",
        value="Respect staff decisions. If you disagree, discuss privately with administrators.",
        inline=False
    )
    
    rules_embed.add_field(
        name="🎫 9. Use Support System",
        value="For help, questions, or reports, use the ticket system created by staff.",
        inline=False
    )
    
    rules_embed.add_field(
        name="⭐ 10. Have Fun!",
        value="Enjoy your time here and contribute positively to our community!",
        inline=False
    )
    
    # Add footer
    rules_embed.set_footer(
        text="Voralith • Rules last updated"
    )
    rules_embed.timestamp = datetime.datetime.now()
    
    # Add consequences section
    consequences_embed = discord.Embed(
        title="⚖️ Rule Violations & Consequences",
        description="Breaking these rules may result in the following actions:",
        color=0x5B2C6F
    )
    
    consequences_embed.add_field(
        name="🟡 Minor Violations",
        value="• Verbal warning\n• Message deletion\n• Temporary mute (5-30 minutes)",
        inline=True
    )
    
    consequences_embed.add_field(
        name="🟠 Moderate Violations",
        value="• Temporary mute (1-24 hours)\n• Temporary ban (1-7 days)\n• Role restrictions",
        inline=True
    )
    
    consequences_embed.add_field(
        name="🔴 Severe Violations",
        value="• Permanent ban\n• Report to Discord Trust & Safety\n• Immediate removal",
        inline=True
    )
    
    consequences_embed.add_field(
        name="📞 Appeals Process",
        value="If you believe a punishment was unfair, create a ticket to appeal. Be respectful and provide evidence.",
        inline=False
    )
    
    consequences_embed.set_footer(
        text="Voralith • Fair and consistent moderation",
        icon_url="https://cdn.discordapp.com/attachments/1234567890/voralith-logo.png"
    )
    
    # Send both embeds
    await interaction.response.send_message(embed=rules_embed)
    await interaction.followup.send(embed=consequences_embed)

class CustomOrderView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
    
    @discord.ui.button(label="📝 Create Custom Order Ticket", style=discord.ButtonStyle.primary, emoji="🎨", custom_id="custom_order_ticket_button")
    async def create_custom_order_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Create a custom order ticket"""
        try:
            guild = interaction.guild
            user = interaction.user
            
            # Find or create Support category
            support_category = None
            for category in guild.categories:
                if "support" in category.name.lower() or "ticket" in category.name.lower():
                    support_category = category
                    break
            
            if not support_category:
                # Create Support category if it doesn't exist
                support_category = await guild.create_category("Support")
            
            # Create ticket channel name
            channel_name = f"custom-order-{user.name.lower().replace(' ', '')}"
            
            # Set up permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    add_reactions=True,
                    use_external_emojis=True,
                    read_message_history=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    attach_files=True,
                    embed_links=True
                )
            }
            
            # Add permissions for admin and support roles
            for member in guild.members:
                if member.guild_permissions.administrator:
                    overwrites[member] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        manage_messages=True,
                        attach_files=True,
                        embed_links=True,
                        manage_channels=True  # Allow closing tickets
                    )
            
            # Add permissions for support role if it exists
            for role in guild.roles:
                if "support" in role.name.lower():
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        manage_messages=True,
                        attach_files=True,
                        embed_links=True,
                        manage_channels=True  # Allow closing tickets
                    )
            
            # Create the ticket channel
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=support_category,
                overwrites=overwrites
            )
            
            # Create custom order ticket embed
            embed = discord.Embed(
                title="🎨 Custom Order Ticket",
                description=f"Welcome {user.mention}! This ticket has been created for your custom order request.",
                color=0x5B2C6F
            )
            
            embed.add_field(
                name="📋 What to Include",
                value="Please provide the following information:",
                inline=False
            )
            
            embed.add_field(
                name="🎯 Order Details",
                value="• **What you want**: Detailed description of your custom order\n• **Purpose**: What will this be used for?\n• **Style preferences**: Colors, themes, design elements",
                inline=False
            )
            
            embed.add_field(
                name="📐 Specifications",
                value="• **Size/dimensions**: If applicable\n• **Format**: File type needed (PNG, JPG, MP4, etc.)\n• **Resolution**: Quality requirements",
                inline=False
            )
            
            embed.add_field(
                name="⏰ Timeline",
                value="• **Deadline**: When do you need this completed?\n• **Urgency level**: Rush order or standard timing?",
                inline=False
            )
            
            embed.add_field(
                name="💰 Budget",
                value="• **Budget range**: What's your expected price range?\n• **Payment method**: Preferred payment option",
                inline=False
            )
            
            embed.add_field(
                name="📎 References",
                value="• **Examples**: Share any reference images or links\n• **Inspiration**: Similar work you've seen and liked",
                inline=False
            )
            
            embed.set_footer(
                text="Voralith • Custom Orders • A staff member will assist you shortly"
            )
            embed.timestamp = datetime.datetime.now()
            
            # Create close button view
            close_view = TicketCloseView()
            
            # Send the embed with close button
            await ticket_channel.send(embed=embed, view=close_view)
            
            # Send confirmation to user
            success_embed = discord.Embed(
                title="✅ Custom Order Ticket Created",
                description=f"Your custom order ticket has been created: {ticket_channel.mention}",
                color=0x5B2C6F
            )
            success_embed.add_field(
                name="Next Steps",
                value="Please fill out the information requested in your ticket. A staff member will review your request and provide a quote.",
                inline=False
            )
            
            # Check if interaction is still valid
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=success_embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=success_embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error creating custom order ticket: {e}")
            # Check if interaction is still valid
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred while creating your custom order ticket. Please try again.", ephemeral=True)
            else:
                await interaction.followup.send("❌ An error occurred while creating your custom order ticket. Please try again.", ephemeral=True)

@bot.tree.command(name="setup-customorders", description="Setup custom orders system (Admin only)")
async def setup_customorders_command(interaction: discord.Interaction):
    """Setup the custom orders system with embed and button"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ This command can only be used by admins in DM.", ephemeral=True)
            return
    else:  # Guild context
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command requires administrator permissions.", ephemeral=True)
            return
    
    # Create custom orders embed
    embed = discord.Embed(
        title="🎨 Custom Orders",
        description="Need something unique? We create custom content tailored to your specific needs!",
        color=0x5B2C6F
    )
    
    embed.add_field(
        name="✨ What We Offer",
        value="• **Completely Custom**: Whatever you can imagine, we can create\n• **No Limitations**: Any type of project or service\n• **Your Vision**: We bring your ideas to life\n• **Unlimited Possibilities**: From simple to complex projects",
        inline=False
    )
    
    embed.add_field(
        name="🚀 Why Choose Custom?",
        value="• **Unique to You**: Completely original, made just for you\n• **Perfect Fit**: Tailored to your exact specifications\n• **Professional Quality**: High-end results that stand out\n• **Ongoing Support**: We're here even after delivery",
        inline=False
    )
    
    embed.add_field(
        name="💎 Premium Quality",
        value="• **Expert Team**: Skilled professionals in various fields\n• **Fast Turnaround**: Most orders completed within 1-7 days\n• **Unlimited Revisions**: We work until you're 100% satisfied\n• **Commercial Rights**: Full ownership of your custom content",
        inline=False
    )
    
    embed.add_field(
        name="💰 Pricing",
        value="• **Transparent**: No hidden fees or surprise costs\n• **Competitive**: Fair pricing for premium quality\n• **Flexible**: Payment plans available for larger projects\n• **Value**: Quality that exceeds the investment",
        inline=False
    )
    
    embed.add_field(
        name="📞 Ready to Start?",
        value="Click the button below to create a custom order ticket. Our team will review your request and provide a detailed quote within 24 hours.",
        inline=False
    )
    
    embed.set_footer(
        text="Voralith • Custom Orders • Making Your Vision Reality",
        icon_url="https://cdn.discordapp.com/attachments/1234567890/voralith-logo.png"
    )
    embed.timestamp = datetime.datetime.now()
    
    # Create the view with custom order button
    view = CustomOrderView()
    
    # Send the embed with button
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="end_giveaway", description="End an active giveaway manually (Admin only)")
async def end_giveaway_command(interaction: discord.Interaction):
    """Allow admins to manually end giveaways"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    # Get active giveaways for this server
    server_giveaways = [(gid, g) for gid, g in active_giveaways.items() if g['channel_id'] in [c.id for c in interaction.guild.channels]]
    
    if not server_giveaways:
        await interaction.response.send_message("❌ No active giveaways found in this server.", ephemeral=True)
        return
    
    # Create selection view
    view = EndGiveawayView(server_giveaways)
    
    embed = discord.Embed(
        title="🎲 End Giveaway",
        description=f"Select a giveaway to end manually:\n\n**Active Giveaways:** {len(server_giveaways)}",
        color=0x5B2C6F
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class EndGiveawayView(discord.ui.View):
    def __init__(self, giveaways):
        super().__init__(timeout=300)
        self.giveaways = giveaways
        
        # Create select options
        options = []
        for gid, giveaway in giveaways[:25]:  # Discord limit
            options.append(discord.SelectOption(
                label=f"#{gid}: {giveaway['prize'][:50]}",
                value=str(gid),
                description=f"Ends: {giveaway['end_time'].strftime('%Y-%m-%d %H:%M')} UTC"
            ))
        
        self.add_item(GiveawaySelectMenu(options))

class GiveawaySelectMenu(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Select a giveaway to end...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        giveaway_id = int(self.values[0])
        
        if giveaway_id not in active_giveaways:
            await interaction.response.send_message("❌ This giveaway no longer exists!", ephemeral=True)
            return
        
        giveaway = active_giveaways[giveaway_id]
        
        # Create confirmation view
        confirm_view = EndGiveawayConfirmView(giveaway_id, giveaway)
        
        embed = discord.Embed(
            title="⚠️ Confirm Giveaway End",
            description=f"Are you sure you want to end this giveaway?\n\n**Prize:** {giveaway['prize']}\n**Participants:** {len(giveaway['participants'])}\n**Scheduled End:** <t:{int(giveaway['end_time'].timestamp())}:R>",
            color=0x5B2C6F
        )
        
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)

class EndGiveawayConfirmView(discord.ui.View):
    def __init__(self, giveaway_id, giveaway_data):
        super().__init__(timeout=300)
        self.giveaway_id = giveaway_id
        self.giveaway_data = giveaway_data
    
    @discord.ui.button(label='✅ End Giveaway', style=discord.ButtonStyle.danger)
    async def confirm_end(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        # End the giveaway
        await end_giveaway(self.giveaway_id)
        
        await interaction.followup.send(f"✅ Giveaway **{self.giveaway_data['prize']}** has been ended manually!", ephemeral=True)
    
    @discord.ui.button(label='❌ Cancel', style=discord.ButtonStyle.secondary)
    async def cancel_end(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Giveaway termination cancelled.", ephemeral=True)

@bot.tree.command(name="clear", description="Clear messages from the channel (Admin only)")
async def clear_command(interaction: discord.Interaction, amount: int = None):
    """Clear messages from the channel with optional amount"""
    
    # Check DM permissions - STRICT
    if interaction.guild is None:  # DM context
        if interaction.user.id != ADMIN_USER_ID:
            await interaction.response.send_message("❌ Only administrators can use bot commands in DM.", ephemeral=True)
            return
    
    # Check if user has admin permissions in server
    if interaction.guild and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
        return
    
    # Check if command is used in a guild
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server!", ephemeral=True)
        return
    
    # Check bot permissions
    if not interaction.guild.me.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ I don't have permission to manage messages in this server!", ephemeral=True)
        return
    
    # If no amount specified, warn about clearing all messages
    if amount is None:
        embed = discord.Embed(
            title="⚠️ Clear All Messages",
            description="You haven't specified a number of messages to clear.\n\nThis will attempt to clear **ALL** messages in this channel.\n\n**Are you sure you want to continue?**",
            color=0xFF6B6B
        )
        embed.add_field(name="Tip", value="Use `/clear [number]` to clear a specific amount of messages.", inline=False)
        
        view = ClearConfirmView(amount=None)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        return
    
    # Validate amount
    if amount <= 0:
        await interaction.response.send_message("❌ Please specify a positive number of messages to clear!", ephemeral=True)
        return
    
    if amount > 100:
        embed = discord.Embed(
            title="⚠️ Large Clear Operation",
            description=f"You want to clear **{amount}** messages.\n\nThis is a large operation that may take some time.\n\n**Are you sure you want to continue?**",
            color=0xFF6B6B
        )
        
        view = ClearConfirmView(amount=amount)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        return
    
    # Clear messages directly for smaller amounts
    try:
        await interaction.response.defer(ephemeral=True)
        
        deleted = await interaction.channel.purge(limit=amount)
        
        embed = discord.Embed(
            title="✅ Messages Cleared",
            description=f"Successfully cleared **{len(deleted)}** messages from {interaction.channel.mention}.",
            color=0x5B2C6F
        )
        embed.set_footer(text=f"Cleared by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        logger.info(f"Admin {interaction.user.name} cleared {len(deleted)} messages in {interaction.channel.name}")
        
    except discord.Forbidden:
        await interaction.followup.send("❌ I don't have permission to delete messages in this channel!", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.followup.send(f"❌ Failed to clear messages: {str(e)}", ephemeral=True)
    except Exception as e:
        logger.error(f"Error clearing messages: {e}")
        await interaction.followup.send("❌ An error occurred while clearing messages!", ephemeral=True)

class ClearConfirmView(discord.ui.View):
    def __init__(self, amount):
        super().__init__(timeout=300)
        self.amount = amount
    
    @discord.ui.button(label='✅ Confirm Clear', style=discord.ButtonStyle.danger)
    async def confirm_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
            
            if self.amount is None:
                # Clear all messages (limit to 1000 for safety)
                deleted = await interaction.channel.purge(limit=1000)
            else:
                # Clear specific amount
                deleted = await interaction.channel.purge(limit=self.amount)
            
            embed = discord.Embed(
                title="✅ Messages Cleared",
                description=f"Successfully cleared **{len(deleted)}** messages from {interaction.channel.mention}.",
                color=0x5B2C6F
            )
            embed.set_footer(text=f"Cleared by {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            logger.info(f"Admin {interaction.user.name} cleared {len(deleted)} messages in {interaction.channel.name}")
            
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to delete messages in this channel!", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Failed to clear messages: {str(e)}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error clearing messages: {e}")
            await interaction.followup.send("❌ An error occurred while clearing messages!", ephemeral=True)
    
    @discord.ui.button(label='❌ Cancel', style=discord.ButtonStyle.secondary)
    async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Clear operation cancelled.", ephemeral=True)

# Event for when new members join
@bot.event
async def on_message(message):
    """Handle messages, anti-spam moderation, and update sticky if needed"""
    # Ignore bot messages to prevent infinite loops
    if message.author.bot:
        return
    
    # Check for spam and take action if needed
    is_spam = await check_spam(message)
    if is_spam:
        return  # Message was deleted for spam, stop processing
    
    # Check if this channel has a sticky review message
    if message.channel.id in sticky_channels:
        # Wait a moment to avoid spam
        await asyncio.sleep(0.5)
        # Update sticky message to keep it at bottom
        await update_sticky_message(message.channel)
    
    # Process commands normally
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    """Handle new member joining - Send them verification instructions"""
    
    # Send welcome DM with verification instructions
    try:
        embed = discord.Embed(
            title="🎉 Welcome to the Server!",
            description=f"Hello {member.mention}! Welcome to our community.",
            color=0x5B2C6F
        )
        
        embed.add_field(
            name="🔒 Get Verified",
            value="To access all server features, please verify your identity in the verification channel.",
            inline=False
        )
        
        embed.add_field(
            name="📝 How to Verify",
            value="1. Go to the verification channel\n2. Click the 'Verify Identity' button\n3. Complete the authorization process\n4. Receive your verified role automatically!",
            inline=False
        )
        
        embed.set_footer(text="Voralith Welcome System", icon_url="https://cdn.discordapp.com/attachments/1156246022104825920/1321844863446892574/voralith-logo.png")
        
        await member.send(embed=embed)
        logger.info(f"Sent welcome DM to {member.name}")
        
    except discord.Forbidden:
        logger.warning(f"Could not send welcome DM to {member.name} - DMs disabled")
    except Exception as e:
        logger.error(f"Error sending welcome DM to {member.name}: {e}")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    logger.error(f"Command error: {error}")

@bot.event
async def on_application_command_error(interaction, error):
    logger.error(f"Application command error: {error}")
    if not interaction.response.is_done():
        await interaction.response.send_message("❌ An error occurred while processing your command.", ephemeral=True)

# Start the bot
if __name__ == "__main__":
    # Start the Flask keep-alive server
    keep_alive()
    
    # Start internal monitoring system to keep bot connection active
    from keep_alive import internal_keep_alive
    internal_keep_alive()
    
    # Get bot token from environment
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN environment variable not set!")
        exit(1)
    
    logger.info("Starting Voralith bot...")
    bot.run(token)