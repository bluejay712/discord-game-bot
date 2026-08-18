import os
import random
import asyncio
import discord
from discord.ext import commands
from discord.ui import Button, View

# Setup bot intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Active game state storage (channel_id -> game_data_dict)
active_games = {}

# Kid-friendly word pool for Hangman
HANGMAN_WORDS = [
    "minecraft", "roblox", "fortnite", "pokemon", "charizard", "creeper",
    "skateboard", "hoverboard", "basketball", "soccer", "touchdown", "trampoline",
    "astronaut", "galaxy", "spaceship", "dinosaur", "cheetah", "dolphin",
    "pizza", "milkshake", "chocolate", "spaghetti", "pineapple", "marshmallow",
    "backpack", "recess", "cafeteria", "homework", "principal", "whiteboard",
    "youtube", "streamer", "controller", "headset", "keyboard", "nintendo",
    "superhero", "avengers", "spiderman", "batman", "hogwarts", "wizard",
    "volcano", "tsunami", "lightning", "tornado", "avalanche", "earthquake"
]

# Generate standard 108-card Uno Deck
def create_uno_deck():
    deck = []
    colors = ["Red", "Yellow", "Green", "Blue"]
    for color in colors:
        deck.append({"color": color, "value": "0"})
        for num in range(1, 10):
            deck.append({"color": color, "value": str(num)})
            deck.append({"color": color, "value": str(num)})
        for action in ["Skip", "Reverse", "Draw 2"]:
            deck.append({"color": color, "value": action})
            deck.append({"color": color, "value": action})
    for _ in range(4):
        deck.append({"color": "Wild", "value": "Wild"})
        deck.append({"color": "Wild", "value": "Draw 4"})
    random.shuffle(deck)
    return deck

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

# --- CONNECT FOUR LOGIC ---
class C4Button(Button):
    def __init__(self, column, label):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, custom_id=f"c4_{column}")
        self.column = column

    async def callback(self, interaction: discord.Interaction):
        channel_id = interaction.channel_id
        if channel_id not in active_games or active_games[channel_id]["type"] != "c4":
            await interaction.response.send_message("No active Connect Four game here.", ephemeral=True)
            return
            
        game = active_games[channel_id]
        if game["state"] != "ACTIVE":
            await interaction.response.send_message("The game hasn't started yet!", ephemeral=True)
            return
            
        current_player = game["players"][game["turn"]]
        if interaction.user.id != current_player:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        # Gravity logic: drop token to bottom row available
        row_placed = -1
        for r in range(5, -1, -1):
            if game["board"][r][self.column] == "⚪":
                game["board"][r][self.column] = "🔴" if game["turn"] == 0 else "🔵"
                row_placed = r
                break
                
        if row_placed == -1:
            await interaction.response.send_message("Column full! Pick another.", ephemeral=True)
            return

        # Check win condition (Horizontal, Vertical, Diagonal)
        token = "🔴" if game["turn"] == 0 else "🔵"
        if check_c4_win(game["board"], token):
            await interaction.response.edit_message(content=f"🎉 <@{current_player}> wins!\n{render_c4(game['board'])}", view=None)
            del active_games[channel_id]
            return

        # Switch Turn
        game["turn"] = 1 - game["turn"]
        next_player = game["players"][game["turn"]]
        await interaction.response.edit_message(content=f"It is now <@{next_player}>'s turn!\n{render_c4(game['board'])}", view=self.view)

def render_c4(board):
    return "\n".join("".join(row) for row in board)

def check_c4_win(b, t):
    # Horizontal
    for r in range(6):
        for c in range(4):
            if b[r][c]==t and b[r][c+1]==t and b[r][c+2]==t and b[r][c+3]==t: return True
    # Vertical
    for r in range(3):
        for c in range(7):
            if b[r][c]==t and b[r+1][c]==t and b[r+2][c]==t and b[r+3][c]==t: return True
    # Diagonal down-right
    for r in range(3):
        for c in range(4):
            if b[r][c]==t and b[r+1][c+1]==t and b[r+2][c+2]==t and b[r+3][c+3]==t: return True
    # Diagonal up-right
    for r in range(3, 6):
        for c in range(4):
            if b[r][c]==t and b[r-1][c+1]==t and b[r-2][c+2]==t and b[r-3][c+3]==t: return True
    return False

@bot.command(name="c4")
async def start_c4(ctx):
    if ctx.channel.name != "connect-four":
        await ctx.send("❌ This command can ONLY be run in the `#connect-four` channel!")
        return
    if ctx.channel.id in active_games:
        await ctx.send("A game is already running in this channel.")
        return

    active_games[ctx.channel.id] = {
        "type": "c4",
        "state": "LOBBY",
        "players": [ctx.author.id],
        "board": [["⚪"] * 7 for _ in range(6)],
        "turn": 0
    }
    
    view = View()
    join_btn = Button(label="Join Match", style=discord.ButtonStyle.green)
    
    async def join_callback(interaction: discord.Interaction):
        game = active_games[ctx.channel.id]
        if interaction.user.id in game["players"]:
            await interaction.response.send_message("You already joined!", ephemeral=True)
            return
        game["players"].append(interaction.user.id)
        game["state"] = "ACTIVE"
        
        game_view = View()
        for i in range(7):
            game_view.add_item(C4Button(i, str(i+1)))
            
        await interaction.response.edit_message(content=f"Game Started! Matchup: <@{game['players'][0]}> vs <@{game['players'][1]}>\n{render_c4(game['board'])}", view=game_view)

    join_btn.callback = join_callback
    view.add_item(join_btn)
    await ctx.send(f"🎮 Connect Four initialized by {ctx.author.mention}! Waiting for Player 2 to join...", view=view)


# --- HANGMAN LOGIC ---
@bot.command(name="hangman")
async def start_hangman(ctx):
    if ctx.channel.name != "hangman":
        await ctx.send("❌ This command can ONLY be run in the `#hangman` channel!")
        return
    if ctx.channel.id in active_games:
        await ctx.send("A game is already running in this channel.")
        return

    active_games[ctx.channel.id] = {
        "type": "hangman",
        "state": "LOBBY",
        "players": [ctx.author.id],
        "word": random.choice(HANGMAN_WORDS).lower(),
        "guesses": set(),
        "wrong_count": 0
    }
    
    await ctx.send("🎯 Hangman Lobby Open! Type `!join` within 1 minute to join the cooperative guessing team.")
    await asyncio.sleep(60)
    
    game = active_games.get(ctx.channel.id)
    if game and game["state"] == "LOBBY":
        game["state"] = "ACTIVE"
        hidden = "".join([char if char in game["guesses"] else " \_ " for char in game["word"]])
        await ctx.send(f"⏱️ Time's up! Lobby locked. Word: {hidden}\nStart guessing single letters directly in chat!")


# --- GLOBAL CHAT ROUTER ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return
        
    channel_id = message.channel.id
    
    # Handle Global Join Command
    if message.content.strip().lower() == "!join" and channel_id in active_games:
        game = active_games[channel_id]
        if game["type"] == "hangman":
            if game["state"] == "LOBBY":
                if message.author.id not in game["players"]:
                    game["players"].append(message.author.id)
                    await message.channel.send(f"✅ {message.author.mention} joined the Hangman team!")
            else:
                await message.channel.send("❌ Match in progress! You must wait until this game ends.")
            return
            
        if game["type"] == "uno" and game["state"] == "LOBBY":
            if message.author.id not in game["players"]:
                game["players"].append(message.author.id)
                await message.channel.send(f"✅ {message.author.mention} joined the Uno lobby!")
            return

    # Handle Active Game Inputs
    if channel_id in active_games:
        game = active_games[channel_id]
        
        # Hangman Processing
        if game["type"] == "hangman" and game["state"] == "ACTIVE":
            if message.author.id not in game["players"]:
                return # Ignore spectators
                
            content = message.content.strip().lower()
            if len(content) == 1 and content.isalpha():
                if content in game["guesses"]:
                    await message.channel.send("That letter was already guessed!")
                    return
                    
                game["guesses"].add(content)
                if content not in game["word"]:
                    game["wrong_count"] += 1
                    limbs = ["Head", "Body", "Left Arm", "Right Arm", "Left Leg", "Right Leg"]
                    lost_limb = limbs[game["wrong_count"]-1]
                    await message.channel.send(f"❌ Wrong guess! Added: **{lost_limb}** ({game['wrong_count']}/6 lives used)")
                    
                    if game["wrong_count"] >= 6:
                        await message.channel.send(f"💥 Game Over! The team loses. The word was: **{game['word']}**")
                        del active_games[channel_id]
                        return
                else:
                    await message.channel.send("✅ Correct guess!")
                    
                hidden = "".join([char if char in game["guesses"] else " \_ " for char in game["word"]])
                if " \_ " not in hidden:
                    await message.channel.send(f"🎉 Victory! The team successfully uncovered the word: **{game['word']}**!")
                    del active_games[channel_id]
