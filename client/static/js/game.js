/**
 * Trump Card Game - Client Side JavaScript
 */

// ==================== Global State ====================
let socket = null;
let gameState = null;
let myPlayerId = null;
let roomCode = null;
let selectedTrump = null;
let partnerCards = [];
let validCards = [];
let viewingTimerId = null;
let gamePaused = false;
let disconnectedPlayers = [];
let trickDisplayPending = false;

// Suit symbols
const SUIT_SYMBOLS = {
    hearts: '\u2665',
    diamonds: '\u2666',
    clubs: '\u2663',
    spades: '\u2660'
};

const SUIT_COLORS = {
    hearts: 'red',
    diamonds: 'red',
    clubs: 'black',
    spades: 'black'
};

// ==================== Initialization ====================
document.addEventListener('DOMContentLoaded', () => {
    initializeSocket();
    setupEventListeners();
    fetchServerInfo();
});

function initializeSocket() {
    // Connect to server
    socket = io();

    socket.on('connect', () => {
        console.log('Connected to server');
    });

    socket.on('connected', (data) => {
        myPlayerId = data.sid;
        showScreen('home-screen');
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        showToast('Disconnected from server', 'error');
    });

    // Room events
    socket.on('room_created', handleRoomCreated);
    socket.on('room_joined', handleRoomJoined);
    socket.on('join_error', (data) => showToast(data.message, 'error'));
    socket.on('player_joined', handlePlayerJoined);
    socket.on('player_left', handlePlayerLeft);
    socket.on('player_disconnected', handlePlayerDisconnected);
    socket.on('player_reconnected', handlePlayerReconnected);
    socket.on('game_paused', handleGamePaused);
    socket.on('game_resumed', handleGameResumed);
    socket.on('player_kicked', handlePlayerKicked);
    socket.on('reconnected', handleReconnected);

    // Game events
    socket.on('game_started', handleGameStarted);
    socket.on('bidding_started', handleBiddingStarted);
    socket.on('bid_update', handleBidUpdate);
    socket.on('bid_error', (data) => showToast(data.message, 'error'));
    socket.on('bidding_complete', handleBiddingComplete);
    socket.on('selection_error', (data) => showToast(data.message, 'error'));
    socket.on('game_play_started', handleGamePlayStarted);
    socket.on('card_played', handleCardPlayed);
    socket.on('play_error', (data) => showToast(data.message, 'error'));
    socket.on('partner_revealed', handlePartnerRevealed);
    socket.on('trick_complete', handleTrickComplete);
    socket.on('state_update', handleStateUpdate);
    socket.on('game_over', handleGameOver);
    socket.on('error', (data) => showToast(data.message, 'error'));

    // Play again events
    socket.on('game_reset', handleGameReset);
    socket.on('play_again_requested', handlePlayAgainRequested);

    // Chat
    socket.on('chat_message', handleChatMessage);

    // Surrender (RageBait)
    socket.on('surrender_vote', handleSurrenderVote);
    socket.on('surrender_error', (data) => showToast(data.message, 'error'));
}

function setupEventListeners() {
    // Home screen
    document.getElementById('btn-create').addEventListener('click', () => {
        const name = document.getElementById('player-name').value.trim();
        if (!name) {
            showToast('Please enter your name', 'error');
            return;
        }
        showScreen('create-screen');
    });

    document.getElementById('btn-join').addEventListener('click', () => {
        const name = document.getElementById('player-name').value.trim();
        if (!name) {
            showToast('Please enter your name', 'error');
            return;
        }
        showScreen('join-screen');
    });

    // Create screen
    document.getElementById('num-players').addEventListener('input', (e) => {
        document.getElementById('num-players-value').textContent = e.target.value;
    });

    document.getElementById('num-decks').addEventListener('input', (e) => {
        document.getElementById('num-decks-value').textContent = e.target.value;
    });

    document.getElementById('num-partners').addEventListener('input', (e) => {
        const numPartners = parseInt(e.target.value);
        document.getElementById('num-partners-value').textContent = numPartners;
        // Update hint text
        const hint = document.getElementById('partners-hint');
        if (numPartners === 0) {
            hint.textContent = 'Solo mode: Bidder vs everyone else';
        } else if (numPartners === 1) {
            hint.textContent = 'Bidder + 1 partner vs others';
        } else {
            hint.textContent = 'Bidder + 2 partners vs others';
        }
    });

    document.getElementById('btn-create-room').addEventListener('click', createRoom);

    // Join screen
    document.getElementById('btn-join-room').addEventListener('click', joinRoom);
    document.getElementById('room-code').addEventListener('keyup', (e) => {
        if (e.key === 'Enter') joinRoom();
    });

    // Lobby
    document.getElementById('btn-start-game').addEventListener('click', startGame);

    // Bidding
    document.getElementById('btn-place-bid').addEventListener('click', placeBid);
    document.getElementById('btn-pass').addEventListener('click', passBid);

    // Partner selection
    document.querySelectorAll('.suit-btn').forEach(btn => {
        btn.addEventListener('click', () => selectTrump(btn.dataset.suit));
    });

    document.getElementById('btn-confirm-partners').addEventListener('click', confirmPartners);

    // Chat
    document.getElementById('btn-send-chat').addEventListener('click', sendChat);
    document.getElementById('chat-input').addEventListener('keyup', (e) => {
        if (e.key === 'Enter') sendChat();
    });
}

async function fetchServerInfo() {
    try {
        const response = await fetch('/api/server-info');
        const data = await response.json();
        document.getElementById('server-url').textContent = `http://${data.ip}:${data.port}`;
    } catch (error) {
        console.error('Failed to fetch server info:', error);
    }
}

// ==================== Screen Management ====================
function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    document.getElementById(screenId).classList.add('active');
}

// ==================== Room Management ====================
function createRoom() {
    const playerName = document.getElementById('player-name').value.trim();
    const numPlayers = parseInt(document.getElementById('num-players').value);
    const numDecks = parseInt(document.getElementById('num-decks').value);
    const numPartners = parseInt(document.getElementById('num-partners').value);

    socket.emit('create_room', {
        player_name: playerName,
        max_players: numPlayers,
        num_decks: numDecks,
        num_partners: numPartners
    });
}

function joinRoom() {
    const playerName = document.getElementById('player-name').value.trim();
    const code = document.getElementById('room-code').value.trim().toUpperCase();

    if (!code || code.length !== 6) {
        showToast('Please enter a valid 6-character room code', 'error');
        return;
    }

    socket.emit('join_room', {
        room_code: code,
        player_name: playerName
    });
}

function handleRoomCreated(data) {
    roomCode = data.room_code;
    gameState = data.state;
    document.getElementById('display-room-code').textContent = roomCode;
    updateLobbyPlayers();
    document.getElementById('host-controls').classList.remove('hidden');
    document.getElementById('waiting-msg').classList.add('hidden');
    showScreen('lobby-screen');
    showToast('Room created!', 'success');
}

function handleRoomJoined(data) {
    roomCode = data.room_code;
    gameState = data.state;
    document.getElementById('display-room-code').textContent = roomCode;
    updateLobbyPlayers();

    if (gameState.host_id === myPlayerId) {
        document.getElementById('host-controls').classList.remove('hidden');
        document.getElementById('waiting-msg').classList.add('hidden');
    }

    showScreen('lobby-screen');
    showToast('Joined room!', 'success');
}

function handlePlayerJoined(data) {
    gameState = data.state;
    updateLobbyPlayers();
    showToast(`${data.player_name} joined`, 'info');
}

function handlePlayerLeft(data) {
    gameState = data.state;
    updateLobbyPlayers();
    showToast('A player left', 'info');
}

function handleReconnected(data) {
    roomCode = data.room_code;
    gameState = data.state;
    validCards = data.valid_cards || [];
    myPlayerId = data.state.players ? Object.keys(data.state.players).find(
        pid => data.state.players[pid].name === document.getElementById('player-name').value.trim()
    ) : null;

    showToast('Reconnected to game!', 'success');

    // Go to appropriate screen based on game phase
    const phase = gameState.phase;
    if (phase === 'waiting') {
        document.getElementById('display-room-code').textContent = roomCode;
        updateLobbyPlayers();
        showScreen('lobby-screen');
    } else if (phase === 'viewing_cards') {
        renderViewingScreen();
        showScreen('viewing-screen');
        // Join mid-viewing - start with remaining time (estimate 30 seconds for reconnect)
        startViewingTimer(30);
    } else if (phase === 'bidding') {
        renderBiddingScreen();
        showScreen('bidding-screen');
    } else if (phase === 'partner_selection') {
        if (gameState.highest_bidder_id === myPlayerId) {
            setupPartnerSelectionScreen();
            showScreen('partner-screen');
        } else {
            document.getElementById('bidder-won-name').textContent = gameState.highest_bidder;
            document.getElementById('won-bid-amount').textContent = gameState.bid_amount;
            showScreen('waiting-partner-screen');
        }
    } else if (phase === 'playing') {
        showScreen('game-screen');
        renderGameScreen();
    } else if (phase === 'game_over') {
        handleGameOver({ bidder_won: gameState.bidder_won, state: gameState });
    }
}

function updateLobbyPlayers() {
    const container = document.getElementById('lobby-players');
    container.innerHTML = '';

    for (const [playerId, player] of Object.entries(gameState.players)) {
        const isHost = playerId === gameState.host_id;
        const isYou = playerId === myPlayerId;

        const div = document.createElement('div');
        div.className = `player-item${isHost ? ' host' : ''}${isYou ? ' you' : ''}`;
        div.innerHTML = `
            <span class="player-name">${player.name}${isYou ? ' (You)' : ''}</span>
            <span class="player-status">${isHost ? 'Host' : 'Ready'}</span>
        `;
        container.appendChild(div);
    }

    // Update lobby settings display
    updateLobbySettings();
}

function updateLobbySettings() {
    const numDecks = gameState.num_decks || 1;
    const numPartners = gameState.num_partners !== undefined ? gameState.num_partners : 2;

    document.getElementById('lobby-num-decks').textContent = numDecks;
    document.getElementById('lobby-num-partners').textContent = numPartners;

    // Set game mode description
    let modeText;
    if (numPartners === 0) {
        modeText = 'Solo (1 vs All)';
    } else if (numPartners === 1) {
        modeText = 'Bidder + 1';
    } else {
        modeText = 'Bidder + 2';
    }
    document.getElementById('lobby-game-mode').textContent = modeText;
}

function copyRoomCode() {
    navigator.clipboard.writeText(roomCode).then(() => {
        showToast('Room code copied!', 'success');
    });
}

function startGame() {
    if (Object.keys(gameState.players).length < 2) {
        showToast('Need at least 2 players to start', 'error');
        return;
    }
    socket.emit('start_game', {});
}

// ==================== Viewing Phase ====================
function handleGameStarted(data) {
    gameState = data.state;
    const viewingTime = data.viewing_time || 20;

    // Show info about cards distribution
    const cardsPerPlayer = gameState.cards_per_player;
    const removedCards = gameState.removed_cards || [];

    if (removedCards.length > 0) {
        const removedList = removedCards.map(c => c.display).join(', ');
        showToast(`${cardsPerPlayer} cards each. Removed for equal distribution: ${removedList}`, 'info');
    } else {
        showToast(`${cardsPerPlayer} cards dealt to each player`, 'info');
    }

    // Render and show viewing screen with timer
    renderViewingScreen();
    showScreen('viewing-screen');
    startViewingTimer(viewingTime);
}

function renderViewingScreen() {
    const container = document.getElementById('viewing-cards');
    container.innerHTML = '';

    const myPlayer = gameState.players[myPlayerId];
    if (!myPlayer || !myPlayer.cards) return;

    // Sort cards by suit and rank for better viewing
    const sortedCards = [...myPlayer.cards].sort((a, b) => {
        const suitOrder = ['spades', 'hearts', 'diamonds', 'clubs'];
        const rankOrder = ['A', 'K', 'Q', 'J', '10', '9', '8', '7', '6', '5', '4', '3', '2'];
        const suitDiff = suitOrder.indexOf(a.suit) - suitOrder.indexOf(b.suit);
        if (suitDiff !== 0) return suitDiff;
        return rankOrder.indexOf(a.rank) - rankOrder.indexOf(b.rank);
    });

    sortedCards.forEach(card => {
        const div = document.createElement('div');
        div.className = `viewing-card ${SUIT_COLORS[card.suit]}`;
        div.innerHTML = `
            <span class="card-rank">${card.rank}</span>
            <span class="card-suit">${SUIT_SYMBOLS[card.suit]}</span>
        `;
        container.appendChild(div);
    });

    // Update stats
    document.getElementById('viewing-card-count').textContent = myPlayer.cards.length;

    // Count point cards (5s, 10s, Aces, Queen of Spades)
    const pointCards = myPlayer.cards.filter(c =>
        c.rank === '5' || c.rank === '10' || c.rank === 'A' ||
        (c.rank === 'Q' && c.suit === 'spades')
    ).length;
    document.getElementById('viewing-point-cards').textContent = pointCards;
}

function startViewingTimer(seconds) {
    // Clear any existing timer
    if (viewingTimerId) {
        clearInterval(viewingTimerId);
    }

    let timeLeft = seconds;
    const timerDisplay = document.getElementById('viewing-timer');

    function updateTimer() {
        const mins = Math.floor(timeLeft / 60);
        const secs = timeLeft % 60;
        timerDisplay.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;

        // Visual warning when time is low
        if (timeLeft <= 10) {
            timerDisplay.classList.add('warning');
        }

        if (timeLeft <= 0) {
            clearInterval(viewingTimerId);
            viewingTimerId = null;
            timerDisplay.classList.remove('warning');
            // Emit to server that viewing phase should end
            socket.emit('start_bidding_phase');
        }
        timeLeft--;
    }

    updateTimer(); // Show initial time
    viewingTimerId = setInterval(updateTimer, 1000);
}

function handleBiddingStarted(data) {
    // Clear viewing timer if still running
    if (viewingTimerId) {
        clearInterval(viewingTimerId);
        viewingTimerId = null;
    }

    gameState = data.state;
    renderBiddingScreen();
    showScreen('bidding-screen');
}

// ==================== Bidding ====================

function renderBiddingScreen() {
    document.getElementById('current-bid-amount').textContent = gameState.current_bid;
    document.getElementById('highest-bidder-name').textContent = gameState.highest_bidder || '-';

    // Show max bid info
    const maxBid = gameState.max_bid || 150;
    const maxBidDisplay = document.getElementById('max-bid-display');
    if (maxBidDisplay) {
        maxBidDisplay.textContent = maxBid;
    }

    const isMyTurn = gameState.current_bidder_id === myPlayerId;
    const myPlayer = gameState.players[myPlayerId];

    if (myPlayer.has_passed) {
        document.getElementById('bidding-turn-text').textContent = 'You have passed';
        document.getElementById('bid-controls').classList.add('hidden');
    } else if (isMyTurn) {
        document.getElementById('bidding-turn-text').textContent = 'Your turn to bid!';
        document.getElementById('bid-controls').classList.remove('hidden');
        const bidInput = document.getElementById('bid-amount');
        bidInput.value = Math.min(gameState.current_bid + 10, maxBid);
        bidInput.min = gameState.current_bid + 10;
        bidInput.max = maxBid;
    } else {
        document.getElementById('bidding-turn-text').textContent =
            `Waiting for ${gameState.current_bidder} to bid...`;
        document.getElementById('bid-controls').classList.add('hidden');
    }

    // Render cards preview
    renderCardsPreview();
}

function renderCardsPreview() {
    const container = document.getElementById('bidding-cards-preview');
    container.innerHTML = '';

    const myPlayer = gameState.players[myPlayerId];
    if (!myPlayer || !myPlayer.cards) return;

    myPlayer.cards.forEach(card => {
        const div = document.createElement('div');
        div.className = `preview-card ${SUIT_COLORS[card.suit]}`;
        div.innerHTML = `
            <span>${card.rank}</span>
            <span>${SUIT_SYMBOLS[card.suit]}</span>
        `;
        container.appendChild(div);
    });
}

function adjustBid(amount) {
    const input = document.getElementById('bid-amount');
    const newValue = parseInt(input.value) + amount;
    const minBid = gameState.current_bid + 10;
    const maxBid = gameState.max_bid || 150;
    input.value = Math.max(minBid, Math.min(maxBid, newValue));
}

function placeBid() {
    const bidAmount = parseInt(document.getElementById('bid-amount').value);
    socket.emit('place_bid', { bid_amount: bidAmount });
}

function passBid() {
    socket.emit('place_bid', { bid_amount: 0 });
}

function handleBidUpdate(data) {
    gameState = data.state;
    renderBiddingScreen();
}

function handleBiddingComplete(data) {
    const bidderId = data.state.highest_bidder_id;
    gameState = data.state;

    if (bidderId === myPlayerId) {
        // I won the bid - show partner selection
        setupPartnerSelectionScreen();
        showScreen('partner-screen');
    } else {
        // Someone else won - show waiting screen
        document.getElementById('bidder-won-name').textContent = data.highest_bidder;
        document.getElementById('won-bid-amount').textContent = data.bid_amount;
        showScreen('waiting-partner-screen');
    }
}

function setupPartnerSelectionScreen() {
    const numPartners = gameState.num_partners !== undefined ? gameState.num_partners : 2;
    partnerCards = []; // Reset partner cards

    const container = document.getElementById('partner-selection-container');
    const label = document.getElementById('partner-selection-label');
    const hint = document.getElementById('partner-selection-hint');
    const slotsContainer = document.getElementById('partner-cards-selected');

    if (numPartners === 0) {
        // Solo mode - hide partner selection entirely
        container.style.display = 'none';
        label.textContent = '';
        hint.textContent = '';
    } else {
        container.style.display = 'block';
        if (numPartners === 1) {
            label.textContent = 'Choose 1 Partner Card';
            hint.textContent = 'The player holding this card is your secret partner';
            slotsContainer.innerHTML = `
                <div class="partner-card-slot" id="partner-slot-1">Select Card 1</div>
            `;
        } else {
            label.textContent = 'Choose 2 Partner Cards';
            hint.textContent = 'Players holding these cards are your secret partners';
            slotsContainer.innerHTML = `
                <div class="partner-card-slot" id="partner-slot-1">Select Card 1</div>
                <div class="partner-card-slot" id="partner-slot-2">Select Card 2</div>
            `;
        }
    }

    // Reset trump selection
    selectedTrump = null;
    document.querySelectorAll('.suit-btn').forEach(btn => btn.classList.remove('selected'));
    checkPartnerSelection();
}

// ==================== Partner Selection ====================
function selectTrump(suit) {
    selectedTrump = suit;
    document.querySelectorAll('.suit-btn').forEach(btn => {
        btn.classList.toggle('selected', btn.dataset.suit === suit);
    });
    checkPartnerSelection();
}

function addPartnerCard() {
    const numPartners = gameState.num_partners !== undefined ? gameState.num_partners : 2;

    if (partnerCards.length >= numPartners) {
        showToast(`Already selected ${numPartners} partner card(s)`, 'error');
        return;
    }

    const rank = document.getElementById('partner-rank').value;
    const suit = document.getElementById('partner-suit').value;

    // Check for duplicates
    const exists = partnerCards.find(c => c.rank === rank && c.suit === suit);
    if (exists) {
        showToast('Card already selected', 'error');
        return;
    }

    partnerCards.push({ rank, suit });
    updatePartnerSlots();
    checkPartnerSelection();
}

function updatePartnerSlots() {
    const numPartners = gameState.num_partners !== undefined ? gameState.num_partners : 2;

    for (let i = 0; i < numPartners; i++) {
        const slot = document.getElementById(`partner-slot-${i + 1}`);
        if (!slot) continue;

        if (partnerCards[i]) {
            const card = partnerCards[i];
            slot.innerHTML = `${card.rank}${SUIT_SYMBOLS[card.suit]}`;
            slot.className = 'partner-card-slot filled';
            slot.onclick = () => removePartnerCard(i);
        } else {
            slot.innerHTML = `Select Card ${i + 1}`;
            slot.className = 'partner-card-slot';
            slot.onclick = null;
        }
    }
}

function removePartnerCard(index) {
    partnerCards.splice(index, 1);
    updatePartnerSlots();
    checkPartnerSelection();
}

function checkPartnerSelection() {
    const btn = document.getElementById('btn-confirm-partners');
    const numPartners = gameState.num_partners !== undefined ? gameState.num_partners : 2;

    // For 0 partners, just need trump selected
    if (numPartners === 0) {
        btn.disabled = !selectedTrump;
    } else {
        btn.disabled = !(selectedTrump && partnerCards.length === numPartners);
    }
}

function confirmPartners() {
    const numPartners = gameState.num_partners !== undefined ? gameState.num_partners : 2;

    if (!selectedTrump) {
        showToast('Please select trump suit', 'error');
        return;
    }

    if (partnerCards.length !== numPartners) {
        if (numPartners === 0) {
            // This shouldn't happen since we skip partner selection for 0
        } else if (numPartners === 1) {
            showToast('Please select 1 partner card', 'error');
        } else {
            showToast('Please select 2 partner cards', 'error');
        }
        return;
    }

    socket.emit('select_trump_partners', {
        trump_suit: selectedTrump,
        partner_cards: partnerCards
    });
}

// ==================== Game Play ====================
function handleGamePlayStarted(data) {
    gameState = data.state;
    validCards = data.valid_cards || [];
    showScreen('game-screen');
    renderGameScreen();

    // Build toast message based on number of partners
    let toastMsg = `Trump: ${SUIT_SYMBOLS[data.trump_suit]}`;
    if (data.partner_cards && data.partner_cards.length > 0) {
        toastMsg += ` | Looking for: ${data.partner_cards.map(c => c.rank + SUIT_SYMBOLS[c.suit]).join(', ')}`;
    } else {
        toastMsg += ` | Solo mode - Bidder vs Everyone!`;
    }
    showToast(toastMsg, 'info');
}

function handleStateUpdate(data) {
    // If we're displaying a completed trick, don't update yet
    if (trickDisplayPending) {
        // Only update valid cards for the next turn, but don't re-render
        validCards = data.valid_cards || [];
        return;
    }
    gameState = data.state;
    validCards = data.valid_cards || [];
    renderGameScreen();
}

function renderGameScreen() {
    if (!gameState) return;

    // Update scores
    document.getElementById('bidder-score').textContent = gameState.bidder_team_points || 0;
    document.getElementById('against-score').textContent = gameState.against_team_points || 0;
    document.getElementById('target-score').textContent = gameState.target_points || 100;

    if (gameState.highest_bidder) {
        document.getElementById('bidder-team-name').textContent = `${gameState.highest_bidder}'s Team`;
    }

    // Update game info
    if (gameState.trump_suit) {
        const trumpDisplay = document.getElementById('trump-suit-display');
        trumpDisplay.textContent = SUIT_SYMBOLS[gameState.trump_suit];
        trumpDisplay.className = `trump-suit ${SUIT_COLORS[gameState.trump_suit] === 'red' ? 'red' : ''}`;
    }

    // Update led suit display
    const ledSuitDisplay = document.getElementById('led-suit-display');
    if (gameState.led_suit) {
        ledSuitDisplay.textContent = SUIT_SYMBOLS[gameState.led_suit];
        ledSuitDisplay.className = `led-suit ${SUIT_COLORS[gameState.led_suit] === 'red' ? 'red' : ''}`;
    } else {
        ledSuitDisplay.textContent = '-';
        ledSuitDisplay.className = 'led-suit';
    }

    document.getElementById('trick-number').textContent = gameState.trick_number || 1;

    // Update partner cards display
    if (gameState.partner_cards) {
        document.getElementById('partner-cards-list').textContent =
            gameState.partner_cards.map(c => c.rank + SUIT_SYMBOLS[c.suit]).join(', ');
    }

    // Render other players
    renderOtherPlayers();

    // Render current trick
    renderCurrentTrick();

    // Render player's hand
    renderPlayerHand();

    // Update turn text
    updateTurnText();

    // Update RageBait button
    updateRageBaitButton(gameState.surrender_votes || 0, gameState.surrender_required || 2);
}

function renderOtherPlayers() {
    const container = document.getElementById('other-players');
    container.innerHTML = '';

    for (const [playerId, player] of Object.entries(gameState.players)) {
        if (playerId === myPlayerId) continue;

        const isCurrentTurn = gameState.current_player_id === playerId;
        const isBidder = playerId === gameState.highest_bidder_id;
        const isPartnerRevealed = player.partner_revealed;

        const div = document.createElement('div');
        div.className = `other-player${isCurrentTurn ? ' current-turn' : ''}${isPartnerRevealed ? ' partner-revealed' : ''}`;

        let badges = '';
        if (isBidder) badges += '<span class="badge bidder">Bidder</span>';
        if (isPartnerRevealed) badges += '<span class="badge partner">Partner</span>';

        div.innerHTML = `
            <span class="name">${player.name}</span>
            <span class="card-count">${player.card_count} cards</span>
            <div class="badges">${badges}</div>
        `;
        container.appendChild(div);
    }
}

function renderCurrentTrick() {
    const container = document.getElementById('trick-cards');
    container.innerHTML = '';

    // If waiting for next trick, show the last completed trick
    const trickToShow = (trickDisplayPending && gameState.last_trick && gameState.last_trick.length > 0)
        ? gameState.last_trick
        : gameState.current_trick;

    if (!trickToShow) return;

    trickToShow.forEach(play => {
        const div = document.createElement('div');
        div.className = 'trick-card';
        div.innerHTML = `
            <div class="card ${SUIT_COLORS[play.card.suit]}">
                <span class="rank">${play.card.rank}</span>
                <span class="suit-symbol">${play.card.symbol}</span>
            </div>
            <span class="player-label">${play.player}</span>
        `;
        container.appendChild(div);
    });
}

function renderPlayerHand() {
    const container = document.getElementById('player-hand');
    container.innerHTML = '';

    const myPlayer = gameState.players[myPlayerId];
    if (!myPlayer || !myPlayer.cards) return;

    const isMyTurn = gameState.current_player_id === myPlayerId;
    const validCardKeys = validCards.map(c => `${c.rank}-${c.suit}`);

    myPlayer.cards.forEach(card => {
        const cardKey = `${card.rank}-${card.suit}`;
        const isValid = validCardKeys.includes(cardKey);
        const canPlay = isMyTurn && isValid;

        const div = document.createElement('div');
        div.className = `card ${card.color}${!canPlay && isMyTurn ? ' disabled' : ''}${isValid && isMyTurn ? ' valid' : ''}`;
        div.innerHTML = `
            <span class="rank">${card.rank}</span>
            <span class="suit-symbol">${card.symbol}</span>
        `;

        if (canPlay) {
            div.onclick = () => playCard(card);
        }

        container.appendChild(div);
    });
}

function updateTurnText() {
    const text = document.getElementById('current-turn-text');
    if (gameState.current_player_id === myPlayerId) {
        text.textContent = 'Your turn!';
        text.style.color = '#4caf50';
    } else {
        text.textContent = `${gameState.current_player}'s turn`;
        text.style.color = '';
    }
}

function playCard(card) {
    socket.emit('play_card', {
        suit: card.suit,
        rank: card.rank
    });
}

function handleCardPlayed(data) {
    gameState = data.state;

    // Check if this card completed a trick (current_trick is empty but last_trick shows it)
    if (gameState.current_trick && gameState.current_trick.length === 0 &&
        gameState.last_trick && gameState.last_trick.length > 0) {
        // Pre-emptively set pending flag to show last_trick immediately
        // The actual trick_complete event will arrive shortly to set the timeout
        trickDisplayPending = true;
    }

    renderGameScreen();
}

function handlePartnerRevealed(data) {
    showToast(`${data.player_name} is a PARTNER!`, 'partner-reveal');
    gameState = data.state;
    renderGameScreen();
}

function handleTrickComplete(data) {
    // Set flag to prevent state updates from clearing the trick display
    trickDisplayPending = true;

    showToast(`${data.winner} won the trick! (+${data.points_won} points)`, 'success');

    // 5 second delay so players can see the complete trick
    setTimeout(() => {
        trickDisplayPending = false;
        socket.emit('get_state');
    }, 5000);
}

// ==================== Game Over ====================
function handleGameOver(data) {
    gameState = data.state;
    const bidderWon = data.bidder_won;
    const surrendered = data.surrendered || (gameState && gameState.surrendered);

    // Result animation
    const resultAnim = document.getElementById('result-animation');
    if (surrendered) {
        resultAnim.innerHTML = '\uD83C\uDFF3\uFE0F';  // White flag emoji
        resultAnim.className = 'result-animation lose';
    } else if (bidderWon) {
        resultAnim.innerHTML = '\uD83C\uDFC6';
        resultAnim.className = 'result-animation win';
    } else {
        resultAnim.innerHTML = '\uD83D\uDE22';
        resultAnim.className = 'result-animation lose';
    }

    // Result title
    if (surrendered) {
        document.getElementById('result-title').textContent = "Game Surrendered!";
        document.getElementById('result-subtitle').textContent = 'RageBait successful - everyone gave up!';
    } else {
        document.getElementById('result-title').textContent =
            bidderWon ? "Bidder's Team Wins!" : "Against Team Wins!";
        document.getElementById('result-subtitle').textContent =
            bidderWon ? 'Target reached!' : 'Failed to reach target!';
    }

    // Final scores
    document.getElementById('final-bidder-score').textContent = gameState.final_bidder_points;
    document.getElementById('final-target').textContent = gameState.target_points;
    document.getElementById('final-against-score').textContent = gameState.final_against_points;

    // Team reveals
    const bidderList = document.getElementById('bidder-team-list');
    bidderList.innerHTML = '';

    if (gameState.bidder) {
        const li = document.createElement('li');
        li.className = 'highlight';
        li.textContent = `${gameState.bidder.name} (Bidder)`;
        bidderList.appendChild(li);
    }

    if (gameState.all_partners) {
        gameState.all_partners.forEach(partner => {
            if (partner.id !== gameState.bidder?.id) {
                const li = document.createElement('li');
                li.textContent = `${partner.name} (Partner)`;
                bidderList.appendChild(li);
            }
        });
    }

    const againstList = document.getElementById('against-team-list');
    againstList.innerHTML = '';

    const bidderTeamIds = [gameState.bidder?.id, ...(gameState.all_partners?.map(p => p.id) || [])];

    for (const [playerId, player] of Object.entries(gameState.players)) {
        if (!bidderTeamIds.includes(playerId)) {
            const li = document.createElement('li');
            li.textContent = player.name;
            againstList.appendChild(li);
        }
    }

    // Display cheating report
    renderCheatingReport();

    // Update Play Again button based on host status
    updatePlayAgainButton();

    showScreen('gameover-screen');
}

function updatePlayAgainButton() {
    const container = document.getElementById('play-again-container');
    if (!container) return;

    const isHost = gameState.host_id === myPlayerId;

    if (isHost) {
        container.innerHTML = `
            <button onclick="playAgain()" class="btn btn-primary btn-large">Play Again</button>
            <p class="play-again-hint">Start a new game with the same players</p>
        `;
    } else {
        container.innerHTML = `
            <button onclick="playAgain()" class="btn btn-secondary btn-large">Request Play Again</button>
            <p class="play-again-hint">Ask the host to start a new game</p>
        `;
    }
}

function renderCheatingReport() {
    const container = document.getElementById('cheating-report');
    if (!container) return;

    const cheatingLog = gameState.cheating_log || [];

    if (cheatingLog.length === 0) {
        container.innerHTML = `
            <div class="no-cheaters">
                <span class="checkmark">&#10004;</span>
                <p>No cheating detected in this game!</p>
            </div>
        `;
        container.className = 'cheating-report clean';
    } else {
        // Group violations by player
        const playerViolations = {};
        cheatingLog.forEach(violation => {
            const name = violation.player_name;
            if (!playerViolations[name]) {
                playerViolations[name] = [];
            }
            playerViolations[name].push(violation);
        });

        let html = `
            <div class="cheaters-found">
                <span class="warning-icon">&#9888;</span>
                <h3>Cheating Detected!</h3>
                <p>${cheatingLog.length} violation(s) found</p>
            </div>
            <div class="violations-list">
        `;

        for (const [playerName, violations] of Object.entries(playerViolations)) {
            html += `
                <div class="player-violations">
                    <div class="cheater-name">
                        <span class="skull">&#9760;</span>
                        ${playerName} - ${violations.length} violation(s)
                    </div>
                    <ul class="violation-details">
            `;

            violations.forEach(v => {
                html += `
                    <li>
                        <strong>Trick #${v.trick_number}:</strong>
                        Had ${v.led_suit_symbol} ${v.led_suit} but played
                        <span class="played-card ${v.played_card.color}">${v.played_card.rank}${v.played_card.symbol}</span>
                    </li>
                `;
            });

            html += `
                    </ul>
                </div>
            `;
        }

        html += '</div>';
        container.innerHTML = html;
        container.className = 'cheating-report violations';
    }
}

// ==================== Play Again Handling ====================
function handleGameReset(data) {
    roomCode = data.room_code;
    gameState = data.state;

    // Hide any pause overlay
    hidePauseOverlay();

    // Reset client state
    selectedTrump = null;
    partnerCards = [];
    validCards = [];

    // Update lobby display
    document.getElementById('display-room-code').textContent = roomCode;
    updateLobbyPlayers();

    // Show/hide host controls
    if (gameState.host_id === myPlayerId) {
        document.getElementById('host-controls').classList.remove('hidden');
        document.getElementById('waiting-msg').classList.add('hidden');
    } else {
        document.getElementById('host-controls').classList.add('hidden');
        document.getElementById('waiting-msg').classList.remove('hidden');
    }

    showScreen('lobby-screen');
    showToast('Returning to lobby for a new game!', 'success');
}

function handlePlayAgainRequested(data) {
    showToast(`${data.player_name} wants to play again!`, 'info');
}

function playAgain() {
    // Check if I'm the host
    if (gameState.host_id === myPlayerId) {
        // Host can directly start a new game
        socket.emit('play_again');
    } else {
        // Non-host requests to play again (notifies host)
        socket.emit('request_play_again');
        showToast('Waiting for host to start a new game...', 'info');
    }
}

// Make playAgain globally available
window.playAgain = playAgain;

// ==================== RageBait Surrender ====================
function voteSurrender() {
    if (gameState && gameState.has_voted_surrender) {
        showToast('You already voted to surrender', 'error');
        return;
    }
    socket.emit('vote_surrender');
}

function handleSurrenderVote(data) {
    showToast(`${data.player_name}: ${data.message}`, 'info');

    // Update button state
    updateRageBaitButton(data.votes, data.required);

    // If game ended due to surrender, the game_over event will handle it
}

function updateRageBaitButton(votes, required) {
    const btn = document.getElementById('btn-ragebait');
    const votesSpan = document.getElementById('ragebait-votes');

    if (btn && votesSpan) {
        if (votes > 0) {
            votesSpan.textContent = `(${votes}/${required})`;
        } else {
            votesSpan.textContent = '';
        }

        // Mark as voted if player has voted
        if (gameState && gameState.has_voted_surrender) {
            btn.classList.add('voted');
        } else {
            btn.classList.remove('voted');
        }
    }
}

// Make voteSurrender globally available
window.voteSurrender = voteSurrender;

// ==================== Disconnect/Pause Handling ====================
function handlePlayerDisconnected(data) {
    showToast(`${data.player_name} disconnected`, 'error');
    gameState = data.state;
    disconnectedPlayers = data.disconnected_players || [data.player_name];

    // Show pause overlay if game is paused
    if (data.paused) {
        showPauseOverlay();
    }
}

function handlePlayerReconnected(data) {
    showToast(`${data.player_name} reconnected!`, 'success');
    gameState = data.state;
    disconnectedPlayers = data.disconnected_players || [];

    // Hide pause overlay if no more disconnected players
    if (disconnectedPlayers.length === 0) {
        hidePauseOverlay();
    } else {
        updatePauseOverlay();
    }

    // Re-render appropriate screen
    const phase = gameState.phase;
    if (phase === 'playing') {
        renderGameScreen();
    } else if (phase === 'bidding') {
        renderBiddingScreen();
    }
}

function handleGamePaused(data) {
    gamePaused = true;
    disconnectedPlayers = data.disconnected_players || [];
    gameState = data.state;
    showPauseOverlay();
}

function handleGameResumed(data) {
    gamePaused = false;
    disconnectedPlayers = [];
    gameState = data.state;
    hidePauseOverlay();

    // Re-render current screen
    const phase = gameState.phase;
    if (phase === 'playing') {
        renderGameScreen();
    } else if (phase === 'bidding') {
        renderBiddingScreen();
    } else if (phase === 'viewing_cards') {
        renderViewingScreen();
    }
}

function handlePlayerKicked(data) {
    gameState = data.state;
    disconnectedPlayers = data.disconnected_players || [];

    // Check if I was kicked
    if (data.kicked_player_id === myPlayerId) {
        hidePauseOverlay();
        showToast('You have been removed from the game', 'error');
        showScreen('home-screen');
        return;
    }

    showToast(`${data.kicked_player_name} was removed from the game`, 'info');

    // If no more disconnected players, resume game
    if (disconnectedPlayers.length === 0) {
        hidePauseOverlay();
    } else {
        updatePauseOverlay();
    }
}

function showPauseOverlay() {
    let overlay = document.getElementById('pause-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'pause-overlay';
        overlay.className = 'pause-overlay';
        document.getElementById('app').appendChild(overlay);
    }

    updatePauseOverlay();
    overlay.classList.add('active');
}

function hidePauseOverlay() {
    const overlay = document.getElementById('pause-overlay');
    if (overlay) {
        overlay.classList.remove('active');
    }
    gamePaused = false;
}

function updatePauseOverlay() {
    const overlay = document.getElementById('pause-overlay');
    if (!overlay) return;

    const isHost = gameState && gameState.host_id === myPlayerId;

    let html = `
        <div class="pause-content">
            <div class="pause-loader">
                <div class="pause-spinner"></div>
            </div>
            <h2>Game Paused</h2>
            <p>Waiting for players to reconnect...</p>
            <div class="disconnected-list">
                <h3>Disconnected Players:</h3>
                <ul>
    `;

    disconnectedPlayers.forEach(player => {
        const playerName = typeof player === 'string' ? player : player.name;
        const playerId = typeof player === 'string' ? null : player.id;
        html += `<li class="disconnected-player">
            <span class="player-name">${playerName}</span>
            ${isHost ? `<button class="btn btn-kick" onclick="kickPlayer('${playerId || playerName}', '${playerName}')">Kick</button>` : ''}
        </li>`;
    });

    html += `
                </ul>
            </div>
            ${isHost ? '<p class="kick-hint">As the host, you can kick disconnected players to resume the game.</p>' : '<p class="kick-hint">Only the host can remove disconnected players.</p>'}
        </div>
    `;

    overlay.innerHTML = html;
}

function kickPlayer(playerId, playerName) {
    socket.emit('kick_player', {
        player_id: playerId,
        player_name: playerName
    });
}

// Make kickPlayer globally available
window.kickPlayer = kickPlayer;

// ==================== Utilities ====================
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ==================== Chat ====================
function sendChat() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();

    if (!message) return;

    socket.emit('send_chat', { message });
    input.value = '';
}

function handleChatMessage(data) {
    const container = document.getElementById('chat-popup-container');

    const popup = document.createElement('div');
    popup.className = 'chat-popup';
    popup.innerHTML = `
        <div class="chat-sender">${data.player_name}</div>
        <div class="chat-text">${escapeHtml(data.message)}</div>
    `;

    container.appendChild(popup);

    // Remove after 5 seconds
    setTimeout(() => {
        popup.style.opacity = '0';
        popup.style.transform = 'translateX(50px)';
        popup.style.transition = 'all 0.3s ease';
        setTimeout(() => popup.remove(), 300);
    }, 5000);

    // Limit to 5 popups max
    while (container.children.length > 5) {
        container.firstChild.remove();
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Make showScreen globally available
window.showScreen = showScreen;
window.copyRoomCode = copyRoomCode;
window.adjustBid = adjustBid;
window.addPartnerCard = addPartnerCard;
