from flask import Flask, request, redirect, render_template_string
from threading import Thread
import logging
import requests
import os
import asyncio
import json
import discord
import time

# Configure logging for keep-alive
logging.getLogger('werkzeug').setLevel(logging.ERROR)

app = Flask('')

@app.route('/')
def home():
    return '''
    <html>
        <head>
            <title>Voralith Bot - Advanced Discord Management</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background: linear-gradient(135deg, #5B2C6F 0%, #2C1B47 50%, #1a0d2e 100%);
                    color: white;
                    text-align: center;
                    padding: 50px;
                    margin: 0;
                }
                .container {
                    max-width: 1000px;
                    margin: 0 auto;
                    background: rgba(255, 255, 255, 0.05);
                    padding: 40px;
                    border-radius: 20px;
                    backdrop-filter: blur(15px);
                    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }
                h1 {
                    font-size: 3.5em;
                    margin-bottom: 10px;
                    background: linear-gradient(45deg, #ffffff, #e0b3ff);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }
                .subtitle {
                    font-size: 1.2em;
                    color: #c9a9dd;
                    margin-bottom: 30px;
                }
                .status {
                    font-size: 1.6em;
                    color: #4ade80;
                    margin-bottom: 40px;
                    font-weight: bold;
                }
                .stats {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 20px;
                    margin: 30px 0;
                }
                .stat-box {
                    background: rgba(91, 44, 111, 0.3);
                    padding: 20px;
                    border-radius: 12px;
                    border: 1px solid rgba(224, 179, 255, 0.2);
                }
                .stat-number {
                    font-size: 2em;
                    font-weight: bold;
                    color: #e0b3ff;
                }
                .feature {
                    background: rgba(255, 255, 255, 0.08);
                    margin: 25px 0;
                    padding: 25px;
                    border-radius: 15px;
                    border-left: 4px solid #5B2C6F;
                    text-align: left;
                }
                .feature h3 {
                    color: #e0b3ff;
                    margin-top: 0;
                    font-size: 1.4em;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎉 VORALITH</h1>
                <div class="subtitle">Advanced Discord Management & Moderation Bot</div>
                <div class="status">✅ Bot is Online & Operational</div>
                
                <div class="stats">
                    <div class="stat-box">
                        <div class="stat-number">15</div>
                        <div>Total Commands</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">6</div>
                        <div>Feature Categories</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">24/7</div>
                        <div>Uptime</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">Active</div>
                        <div>PostgreSQL DB</div>
                    </div>
                </div>
                
                <div class="feature">
                    <h3>🎁 Giveaway Features</h3>
                    <ul style="text-align: left;">
                        <li>🎁 Create giveaways with /giveaway command</li>
                        <li>⏰ Flexible duration formats (1h, 30m, 2d, 1w)</li>
                        <li>🔘 Interactive button to join giveaways</li>
                        <li>🏆 Automatic winner selection</li>
                        <li>📊 View active giveaways with /giveaway_info</li>
                    </ul>
                </div>
                
                <div class="feature">
                    <h3>💼 Support Features</h3>
                    <ul style="text-align: left;">
                        <li>💳 Purchase information with /purchase_info</li>
                        <li>🎫 Support ticket system with /ticket</li>
                        <li>📢 Announcements with /announcement</li>
                        <li>🔄 Update logs with /update_log</li>
                        <li>🌐 24/7 uptime on Replit</li>
                    </ul>
                </div>
                
                <div class="feature">
                    <h3>🔐 Verification & Security</h3>
                    <ul style="text-align: left;">
                        <li>🛡️ Anti-bot verification system</li>
                        <li>👤 Human identity confirmation</li>
                        <li>🔗 Server reconnection protection</li>
                        <li>⚡ Automatic "| Voralith | Verified" role assignment</li>
                        <li>📩 Welcome DM to new members</li>
                        <li>🚫 Advanced anti-spam protection (5 msg/10s limit)</li>
                        <li>⚠️ Progressive warning system (3 warnings → timeout)</li>
                        <li>🔇 Automatic 5-minute timeouts for spammers</li>
                    </ul>
                </div>

                <div class="feature">
                    <h3>⭐ Review & Vouch System</h3>
                    <ul style="text-align: left;">
                        <li>⭐ Star rating system (1-5 stars)</li>
                        <li>📸 Image support for reviews</li>
                        <li>🔢 Dynamic numbering system with PostgreSQL</li>
                        <li>📌 Sticky review format guidance</li>
                        <li>🎨 Professional purple-themed embeds</li>
                        <li>🔒 Role-restricted (Customer role required)</li>
                    </ul>
                </div>

                <div class="feature">
                    <h3>🎫 Advanced Ticket System</h3>
                    <ul style="text-align: left;">
                        <li>📂 Auto-category detection and creation</li>
                        <li>🔒 Private channels with smart permissions</li>
                        <li>📁 Media upload support (images, files)</li>
                        <li>❌ Close button with confirmation system</li>
                        <li>📋 Professional HTML transcripts</li>
                        <li>💾 Automatic transcript saving to #transcript</li>
                    </ul>
                </div>

                <div class="feature">
                    <h3>🛡️ Moderation Tools</h3>
                    <ul style="text-align: left;">
                        <li>🔇 Manual mute command (1s - 24h duration)</li>
                        <li>🔊 Instant unmute with reason tracking</li>
                        <li>📝 Detailed moderation logs</li>
                        <li>⚖️ Reason tracking for all actions</li>
                        <li>🎯 Admin-only command restrictions</li>
                    </ul>
                </div>
                
                <div class="feature">
                    <h3>📋 Complete Command List (15 Total)</h3>
                    <p style="text-align: left; font-size: 14px;">
                    <strong>🎁 Giveaways:</strong><br>
                    • <strong>/giveaway</strong> - Create new giveaway (Admin)<br>
                    • <strong>/giveaway_info</strong> - View active giveaways (Admin)<br>
                    • <strong>/end_giveaway</strong> - Manually end giveaways (Admin)<br><br>
                    
                    <strong>🎫 Support:</strong><br>
                    • <strong>/ticket</strong> - Create support ticket system (Admin)<br>
                    • <strong>/purchase_info</strong> - Display payment options (Admin)<br><br>
                    
                    <strong>📢 Announcements:</strong><br>
                    • <strong>/announcement</strong> - Create professional announcements (Admin)<br>
                    • <strong>/update_log</strong> - Create update changelogs (Admin)<br><br>
                    
                    <strong>🔐 Verification:</strong><br>
                    • <strong>/setup_verification</strong> - Setup verification channel (Admin)<br>
                    • <strong>/verify_stats</strong> - View verification statistics (Admin)<br>
                    • <strong>/reconnect</strong> - Reconnect verified members (Admin)<br><br>
                    
                    <strong>⭐ Reviews:</strong><br>
                    • <strong>/vouch</strong> - Leave star-rated review (Customer role)<br>
                    • <strong>/setup-reviews</strong> - Setup review system (Admin)<br>
                    • <strong>/remove-sticky</strong> - Remove sticky review format (Admin)<br><br>
                    
                    <strong>🛡️ Moderation:</strong><br>
                    • <strong>/mute</strong> - Mute user with custom duration & reason (Admin)<br>
                    • <strong>/unmute</strong> - Instantly unmute user with reason (Admin)<br>
                    </p>
                </div>
                
                <div class="feature">
                    <h3>🎨 Theme & Branding</h3>
                    <ul style="text-align: left;">
                        <li>💜 Professional purple theme (#5B2C6F)</li>
                        <li>🏷️ Custom "Voralith" branding throughout</li>
                        <li>📱 Modern Discord UI components</li>
                        <li>🎯 Consistent embed styling</li>
                        <li>⚡ Responsive button interactions</li>
                    </ul>
                </div>

                <div class="feature">
                    <h3>💾 Technical Features</h3>
                    <ul style="text-align: left;">
                        <li>🗄️ PostgreSQL database integration</li>
                        <li>🔄 24/7 Replit hosting</li>
                        <li>📊 Real-time statistics tracking</li>
                        <li>🔧 Advanced error handling</li>
                        <li>📝 Comprehensive logging system</li>
                        <li>🌐 Flask web interface</li>
                    </ul>
                </div>
            </div>
        </body>
    </html>
    '''

# OAuth2 callback route for Discord authorization
@app.route('/oauth/callback')
def oauth_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    if error:
        return render_template_string('''
        <html>
            <head><title>Authorization Failed</title></head>
            <body style="font-family: Arial; text-align: center; margin-top: 100px;">
                <h2 style="color: #ff5555;">❌ Authorization Failed</h2>
                <p>There was an error with the Discord authorization.</p>
                <p>Please return to Discord and try the verification process again.</p>
            </body>
        </html>
        ''')
    
    if not code or not state:
        return render_template_string('''
        <html>
            <head><title>Invalid Request</title></head>
            <body style="font-family: Arial; text-align: center; margin-top: 100px;">
                <h2 style="color: #ff5555;">❌ Invalid Request</h2>
                <p>Missing authorization code or state parameter.</p>
                <p>Please return to Discord and try the verification process again.</p>
            </body>
        </html>
        ''')
    
    # Process the authorization and assign role automatically
    try:
        print(f"Processing OAuth callback - Code: {code[:10]}..., State: {state}")
        
        # Parse user ID from state
        user_id = state.split('_')[0]
        guild_id = state.split('_')[1] if len(state.split('_')) > 1 else None
        
        print(f"Parsed user_id: {user_id}, guild_id: {guild_id}")
        
        # Exchange code for access token
        token_data = exchange_code_for_token(code)
        print(f"Token exchange result: {token_data is not None}")
        
        if token_data:
            # Assign role using the bot
            success = assign_verified_role(user_id, guild_id, token_data)
            print(f"Role assignment result: {success}")
            
            if success:
                return render_template_string('''
                <html>
                    <head>
                        <title>Verification Complete</title>
                        <style>
                            body { font-family: Arial, sans-serif; text-align: center; margin-top: 100px; background: #2f3136; color: white; }
                            .success { background: #57f287; color: #2f3136; padding: 20px; border-radius: 10px; max-width: 500px; margin: 0 auto; }
                            .icon { font-size: 48px; margin-bottom: 20px; }
                        </style>
                    </head>
                    <body>
                        <div class="success">
                            <div class="icon">✅</div>
                            <h2>Verification Complete!</h2>
                            <p><strong>Your verified role has been automatically assigned.</strong></p>
                            <p>You can now close this page and return to Discord.</p>
                            <p>Welcome to the verified community!</p>
                        </div>
                    </body>
                </html>
                ''')
    except Exception as e:
        print(f"Error in OAuth callback: {e}")
    
    # Fallback success message
    return render_template_string('''
    <html>
        <head>
            <title>Authorization Successful</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin-top: 100px; background: #2f3136; color: white; }
                .success { background: #5865f2; padding: 20px; border-radius: 10px; max-width: 500px; margin: 0 auto; }
                .icon { font-size: 48px; margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <div class="success">
                <div class="icon">✅</div>
                <h2>Authorization Successful!</h2>
                <p><strong>Voralith is now authorized</strong> to help you rejoin servers if needed.</p>
                <p>You can now return to Discord and click <strong>"Complete Verification"</strong> to finish the process.</p>
                <p style="margin-top: 30px; font-size: 14px; opacity: 0.8;">
                    You can revoke this authorization anytime in Discord Settings > Authorized Apps
                </p>
            </div>
        </body>
    </html>
    ''')

# OAuth2 callback route for automatic role assignment
@app.route('/oauth2/authorized')
def oauth2_authorized():
    """Handle OAuth2 callback from Discord and automatically assign role"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    print(f"OAuth2 callback received - Code: {'Yes' if code else 'No'}, State: {state}, Error: {error}")
    
    if error:
        return render_template_string('''
        <html>
            <head>
                <title>Voralith - Authorization Failed</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #2c2f33; color: #ffffff; }
                    .container { max-width: 600px; margin: 0 auto; background-color: #36393f; padding: 40px; border-radius: 10px; }
                    .error { color: #ff4444; }
                    .logo { width: 64px; height: 64px; margin: 0 auto 20px; }
                    .logo img { width: 100%; height: 100%; border-radius: 50%; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="logo">
                        <img src="https://cdn.discordapp.com/attachments/1280536402064478291/1298638949463580724/voralith-logo.png" alt="Voralith">
                    </div>
                    <h1>Authorization Failed</h1>
                    <p class="error">Error: {error}</p>
                    <p>Please try the verification process again.</p>
                </div>
            </body>
        </html>
        '''.format(error=error))
    
    if not code or not state:
        return render_template_string('''
        <html>
            <head>
                <title>Voralith - Invalid Request</title>
                <style>
                    body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #2c2f33; color: #ffffff; }
                    .container { max-width: 600px; margin: 0 auto; background-color: #36393f; padding: 40px; border-radius: 10px; }
                    .error { color: #ff4444; }
                    .logo { width: 64px; height: 64px; margin: 0 auto 20px; }
                    .logo img { width: 100%; height: 100%; border-radius: 50%; }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="logo">
                        <img src="https://cdn.discordapp.com/attachments/1280536402064478291/1298638949463580724/voralith-logo.png" alt="Voralith">
                    </div>
                    <h1>Invalid Request</h1>
                    <p class="error">Missing authorization code or state parameter.</p>
                    <p>Please try the verification process again.</p>
                </div>
            </body>
        </html>
        ''')
    
    # Process the authorization and assign role automatically
    try:
        print(f"Processing OAuth callback - Code: {code[:10]}..., State: {state}")
        
        # Parse user ID from state
        user_id = state.split('_')[0]
        guild_id = state.split('_')[1] if len(state.split('_')) > 1 else None
        
        print(f"Parsed user_id: {user_id}, guild_id: {guild_id}")
        
        # Exchange code for access token
        token_data = exchange_code_for_token(code)
        print(f"Token exchange result: {token_data is not None}")
        
        if token_data:
            # Assign role using the bot
            success = assign_verified_role(user_id, guild_id, token_data)
            print(f"Role assignment result: {success}")
            
            if success:
                return render_template_string('''
                <html>
                    <head>
                        <title>Voralith - Verification Complete</title>
                        <style>
                            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #2c2f33; color: #ffffff; }
                            .container { max-width: 600px; margin: 0 auto; background-color: #36393f; padding: 40px; border-radius: 10px; }
                            .success { color: #57f287; }
                            .logo { width: 64px; height: 64px; margin: 0 auto 20px; }
                            .logo img { width: 100%; height: 100%; border-radius: 50%; }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="logo">
                                <img src="https://cdn.discordapp.com/attachments/1280536402064478291/1298638949463580724/voralith-logo.png" alt="Voralith">
                            </div>
                            <h1>✅ Verification Complete!</h1>
                            <p class="success">Your verified role has been automatically assigned.</p>
                            <p>You can now close this page and return to Discord.</p>
                            <p>Welcome to the verified community!</p>
                        </div>
                    </body>
                </html>
                ''')
    except Exception as e:
        print(f"Error in OAuth callback: {e}")
    
    # Fallback success message
    return render_template_string('''
    <html>
        <head>
            <title>Voralith - Authorization Successful</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #2c2f33; color: #ffffff; }
                .container { max-width: 600px; margin: 0 auto; background-color: #36393f; padding: 40px; border-radius: 10px; }
                .success { color: #44ff44; }
                .logo { width: 64px; height: 64px; margin: 0 auto 20px; }
                .logo img { width: 100%; height: 100%; border-radius: 50%; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="logo">
                    <img src="https://cdn.discordapp.com/attachments/1280536402064478291/1298638949463580724/voralith-logo.png" alt="Voralith">
                </div>
                <h1>Authorization Successful!</h1>
                <p class="success">Your Discord authorization has been received.</p>
                <p>Return to Discord to check your verified role.</p>
            </div>
        </body>
    </html>
    ''')

def exchange_code_for_token(code):
    """Exchange authorization code for access token"""
    try:
        client_id = os.environ.get('DISCORD_CLIENT_ID', '1388883435828940810')
        client_secret = os.environ.get('DISCORD_CLIENT_SECRET')
        
        if not client_secret:
            print("Discord client secret not found in environment variables")
            return None
        
        data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': 'https://advanced-discord-giveaway-bot.replit.app/oauth2/authorized'
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post('https://discord.com/api/oauth2/token', data=data, headers=headers)
        
        print(f"Token exchange response: {response.status_code}")
        if response.status_code == 200:
            token_data = response.json()
            print(f"Successfully obtained token for user")
            return token_data
        else:
            print(f"Failed to exchange code for token: {response.status_code}")
            print(f"Response text: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error exchanging code for token: {e}")
        return None

def assign_verified_role(user_id, guild_id, token_data):
    """Assign verified role to user using the bot"""
    try:
        # Import here to avoid circular imports
        from main import bot, logger
        
        # Check if bot is ready
        if not bot.is_ready():
            print("Bot is not ready yet")
            return False
            
        # Run the role assignment in the bot's event loop
        loop = bot.loop
        if loop and not loop.is_closed():
            # Schedule the coroutine to run in the bot's event loop
            asyncio.run_coroutine_threadsafe(
                _assign_role_async(user_id, guild_id, token_data),
                loop
            )
            return True
        else:
            print("Bot event loop is not available")
            return False
            
    except Exception as e:
        print(f"Error assigning verified role: {e}")
        return False

async def _assign_role_async(user_id, guild_id, token_data):
    """Async function to assign the verified role"""
    try:
        from main import bot, logger
        
        # Get the guild
        if guild_id and guild_id != 'dm':
            guild = bot.get_guild(int(guild_id))
        else:
            # Get the first guild the bot is in
            guild = bot.guilds[0] if bot.guilds else None
        
        if not guild:
            print("Guild not found")
            return False
        
        # Get the user
        user = guild.get_member(int(user_id))
        if not user:
            print(f"User {user_id} not found in guild {guild.name}")
            return False
        
        # Find the verified role
        verified_role = None
        for role in guild.roles:
            if role.name == "| Voralith | Verified":
                verified_role = role
                break
        
        if not verified_role:
            print("Verified role not found")
            return False
        
        # Assign the role
        await user.add_roles(verified_role, reason="Automatic verification via OAuth2")
        
        logger.info(f"Successfully assigned verified role to {user.name} ({user.id})")
        
        # Try to send a DM to the user
        try:
            import discord
            embed = discord.Embed(
                title="✅ Verification Complete!",
                description="Your identity has been verified and you've been assigned the verified role.",
                color=0x57f287
            )
            embed.add_field(
                name="What's Next?",
                value="You now have access to all verified member features.",
                inline=False
            )
            embed.set_footer(text="Voralith Verification System")
            
            await user.send(embed=embed)
        except:
            # If DM fails, it's not critical
            pass
            
        return True
        
    except Exception as e:
        print(f"Error in _assign_role_async: {e}")
        return False

def run():
    print("Starting Flask server on 0.0.0.0:5000...")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

def internal_keep_alive():
    """Internal monitoring to keep the bot connection active"""
    def monitor_loop():
        while True:
            try:
                # Import here to avoid circular imports
                from main import bot
                
                # Check if bot is connected
                if bot.is_ready():
                    # Log bot status for monitoring
                    print(f"[MONITOR] Bot status check: Connected to {len(bot.guilds)} guilds")
                    
                    # Ping one of the guilds to keep connection active
                    if bot.guilds:
                        guild = bot.guilds[0]
                        print(f"[MONITOR] Active in guild: {guild.name} ({guild.id})")
                else:
                    print("[MONITOR] WARNING: Bot is not ready - connection may be lost")
                    
            except Exception as e:
                print(f"[MONITOR] Error in internal monitoring: {e}")
                
            # Wait 30 seconds before next check (more frequent)
            time.sleep(30)
    
    # Create aggressive keep-alive system
    def aggressive_keep_alive():
        while True:
            try:
                # Make frequent requests to prevent sleep
                requests.get("http://localhost:5000", timeout=3)
                requests.get("https://httpbin.org/get", timeout=5)
                requests.get("https://api.github.com", timeout=5)
            except:
                pass
            time.sleep(10)  # Every 10 seconds
    
    monitor_thread = Thread(target=monitor_loop)
    aggressive_thread = Thread(target=aggressive_keep_alive)
    
    monitor_thread.daemon = True
    aggressive_thread.daemon = True
    
    monitor_thread.start()
    aggressive_thread.start()
    
    print("[MONITOR] Internal bot monitoring started")
    print("[MONITOR] Aggressive keep-alive system started")
