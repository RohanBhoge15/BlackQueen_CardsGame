# Trump Card Game

A multiplayer trick-taking card game with bidding and secret partners. Built for fun to play with friends over local WiFi!

Works as a **PWA (Progressive Web App)** - installable on mobile devices as an app!

> **Note:** This project is made just for fun and learning purposes.

---

## 🌐 Host Online (Play from Anywhere!)

Want to play with friends who aren't on the same WiFi? Use Cloudflare Tunnel to create a public URL:

**Prerequisites:**
- Download Cloudflare Tunnel: [cloudflared for Windows](https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe)
- Place the `.exe` file in your project folder

**Steps:**
1. Start your game server first (see "How to Run" section below)
2. Open a new terminal and run:
   ```bash
   .\cloudflared-windows-amd64.exe tunnel --url http://localhost:5000
   ```
3. Copy the generated `https://` URL (looks like `https://xxxx-xxx-xxx-xxx.trycloudflare.com`)
4. Share this URL with your friends - they can join from anywhere in the world!

**Note:** The tunnel URL changes each time. Make sure your server is running before starting the tunnel.

**For other OS:**
- [Mac/Linux Downloads](https://github.com/cloudflare/cloudflared/releases)

---

## Features

- **2-10 Players** - Play with any group size
- **1-3 Decks** - Configurable for longer games
- **0-2 Partners** - Solo mode, 1 partner, or 2 partners
- **20-Second Viewing Phase** - Study your cards before bidding
- **Secret Partners** - Hidden until partner cards are played
- **Real-time Multiplayer** - Instant updates via WebSocket
- **Reconnection Support** - Rejoin if you disconnect
- **Game Pause System** - Game pauses when someone disconnects
- **Kick Player** - Host can remove disconnected players
- **Cheat Detection** - Tracks players who don't follow suit
- **Play Again** - Start new rounds without recreating rooms
- **PWA Support** - Install as app on mobile devices
- **Responsive Design** - Works on phones, tablets, and desktops

---

## Game Rules

### Setup
- **Players:** 2-10 players
- **Decks:** 1-3 decks (configurable)
- **Partners:** 0, 1, or 2 (configurable)
- **Network:** Local WiFi/Hotspot only (same network)

### Game Modes

| Partners | Mode | Description |
|----------|------|-------------|
| 0 | Solo | Bidder alone vs everyone else |
| 1 | Bidder + 1 | Bidder + 1 secret partner vs others |
| 2 | Bidder + 2 | Bidder + 2 secret partners vs others |

### Game Flow

1. **Viewing Phase (20 seconds)**
   - See your cards before bidding starts
   - Cards are sorted by suit for easy viewing
   - Shows total cards and point cards count

2. **Bidding Phase**
   - Starts at 100 points, goes clockwise
   - Players can raise bid or pass
   - Max bid = 150 points per deck
   - Highest bidder wins

3. **Partner Selection** (by bid winner)
   - Choose **Trump Suit** (leader suit)
   - Choose **0, 1, or 2 partner cards** based on game mode
   - Partner identities stay hidden until their card is played

4. **Playing Phase**
   - Must follow the **led suit** if you have it
   - If you don't have led suit:
     - **Fuse:** Play any non-trump card (can't win)
     - **Cut:** Play trump suit (can beat led suit)
   - Highest trump wins, otherwise highest of led suit wins
   - Trick winner leads next

5. **Game Over**
   - Bidder's team must reach their bid amount to win
   - Teams are revealed
   - Cheating report shows any rule violations
   - Play again without leaving the room!

### Point System

| Card | Points |
|------|--------|
| 5s | 5 |
| 10s | 10 |
| Aces | 15 |
| Queen of Spades | 30 |

**Total per deck = 150 points**

---

## How to Run

### Prerequisites
- Python 3.8+
- pip

### Step 1: Install Dependencies

```bash
cd "Cards Game"
pip install -r requirements.txt
```

Or install manually:
```bash
pip install flask flask-socketio eventlet
```

### Step 2: Run the Server

```bash
cd server
python app.py
```

You'll see:
```
==================================================
  CARD GAME SERVER
==================================================
  Local:   http://localhost:5000
  Network: http://192.168.x.x:5000
==================================================
  Share the Network URL with players on same WiFi/Hotspot
==================================================
```

### Step 3: Play!

1. **Host:** Open the Network URL in browser
2. **Share:** Give the URL to friends on same WiFi
3. **Create Room:** Enter name, select settings, create room
4. **Join:** Others enter the 6-digit room code
5. **Start:** Host clicks "Start Game"

---

## Game Settings

When creating a room, the host can configure:

| Setting | Options | Description |
|---------|---------|-------------|
| Players | 2-10 | Maximum players in the room |
| Decks | 1-3 | More decks = more cards = longer game |
| Partners | 0-2 | Solo, duo, or trio mode |

---

## Special Features

### Reconnection
- If you disconnect during a game, rejoin with the **same name** and **room code**
- Your cards and game state are preserved

### Game Pause
- When a player disconnects, the game pauses for everyone
- Shows who disconnected with a waiting screen
- Game resumes automatically when they reconnect

### Kick Player (Host Only)
- Host can kick disconnected players from the pause screen
- Kicked players are removed from the game
- Game resumes after kick if no more disconnected players

### Cheat Detection
- The game tracks when players don't follow the led suit
- At game end, a report shows:
  - "No cheating detected" (green) - if everyone played fair
  - List of violations (red) - showing who cheated, when, and how

### Play Again
- After game ends, host can start a new round
- All players return to lobby together
- No need to recreate rooms or rejoin!

---

## Installing as Mobile App (PWA)

### Android
1. Open the game URL in Chrome
2. Tap the **3-dot menu** → "Add to Home Screen"
3. The app will be installed!

### iPhone/iPad
1. Open the game URL in Safari
2. Tap the **Share button** → "Add to Home Screen"
3. The app will be installed!

---

## Project Structure

```
Cards Game/
├── server/
│   ├── app.py              # Flask + Socket.IO server
│   └── game_logic.py       # Game rules & state management
├── client/
│   ├── templates/
│   │   └── index.html      # Main game page
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css   # Styles (responsive)
│   │   ├── js/
│   │   │   └── game.js     # Client-side game logic
│   │   └── icons/          # PWA icons
│   ├── manifest.json       # PWA manifest
│   └── sw.js               # Service worker
├── requirements.txt
├── create_icons.py
└── README.md
```

---

## Tech Stack

- **Backend:** Python Flask + Flask-SocketIO + Eventlet
- **Frontend:** Vanilla HTML/CSS/JavaScript
- **Real-time:** Socket.IO (WebSocket)
- **PWA:** Service Worker + Web App Manifest

---

## Troubleshooting

### "Connection failed"
- Make sure all players are on the **same WiFi/Hotspot**
- Check if firewall is blocking port 5000
- Try using the IP address instead of localhost

### "Room not found"
- Room codes are 6 characters (letters + numbers)
- Codes are case-insensitive
- Make sure the host's server is still running

### Player disconnected
- They can rejoin with the same name and room code
- Host can kick them to resume the game

### Cards not showing
- Refresh the page
- Check browser console for errors

---

## Running on Phone (Termux)

It's possible to run the server on Android using Termux:

```bash
pkg update && pkg upgrade
pkg install python
pip install flask flask-socketio eventlet
cd /path/to/Cards\ Game/server
python app.py
```

**Note:** Laptop/PC is recommended for hosting. Phone hosting is possible but less stable.

---

Made with fun by friends, for friends!
