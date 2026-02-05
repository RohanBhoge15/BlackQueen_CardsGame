"""
Flask + Socket.IO Server for Card Game
Local Network Multiplayer Only
"""
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import socket

from game_logic import GameManager, GamePhase

app = Flask(__name__,
            static_folder='../client/static',
            template_folder='../client/templates')
app.config['SECRET_KEY'] = 'card-game-secret-key-2024'

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Game manager instance
game_manager = GameManager()

# Track player sessions: socket_id -> {room_code, player_id, player_name}
player_sessions = {}

# Track disconnected players for reconnection: (room_code, player_name) -> player_id
disconnected_players = {}


def get_local_ip():
    """Get the local IP address for network play"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ==================== HTTP Routes ====================

@app.route('/')
def index():
    """Serve the main game page"""
    return render_template('index.html')


@app.route('/manifest.json')
def manifest():
    """Serve PWA manifest"""
    return send_from_directory('../client', 'manifest.json')


@app.route('/sw.js')
def service_worker():
    """Serve service worker"""
    return send_from_directory('../client', 'sw.js')


@app.route('/api/server-info')
def server_info():
    """Get server info for connecting"""
    return jsonify({
        "ip": get_local_ip(),
        "port": 5000
    })


# ==================== Socket.IO Events ====================

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('connected', {'sid': request.sid})


@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

    # Clean up player session
    if request.sid in player_sessions:
        session = player_sessions[request.sid]
        room_code = session.get('room_code')
        player_id = session.get('player_id')
        player_name = session.get('player_name')

        if room_code:
            room = game_manager.get_room(room_code)
            if room:
                # If game is in progress, don't remove player - allow reconnection
                if room.phase != GamePhase.WAITING:
                    # Store for reconnection
                    disconnected_players[(room_code, player_name)] = player_id
                    print(f"Player {player_name} disconnected from room {room_code} - can reconnect")

                    # Get list of all disconnected players for this room
                    room_disconnected = get_room_disconnected_players(room_code, room)

                    # Notify others player disconnected and game is paused
                    emit('player_disconnected', {
                        'player_name': player_name,
                        'disconnected_players': room_disconnected,
                        'paused': True,
                        'state': room.get_state()
                    }, room=room_code)

                    # Also emit game_paused event
                    emit('game_paused', {
                        'disconnected_players': room_disconnected,
                        'state': room.get_state()
                    }, room=room_code)
                else:
                    # Game not started - remove player from room
                    room.remove_player(player_id)
                    leave_room(room_code)

                    # Notify others
                    emit('player_left', {
                        'player_id': player_id,
                        'state': room.get_state()
                    }, room=room_code)

                    # Delete room if empty
                    if len(room.players) == 0:
                        game_manager.delete_room(room_code)

        del player_sessions[request.sid]


def get_room_disconnected_players(room_code, room):
    """Get list of disconnected players for a room"""
    result = []
    for (rc, pname), pid in disconnected_players.items():
        if rc == room_code:
            result.append({'name': pname, 'id': pid})
    return result


def is_game_paused(room_code):
    """Check if game is paused due to disconnected players"""
    for (rc, _), _ in disconnected_players.items():
        if rc == room_code:
            return True
    return False


@socketio.on('create_room')
def handle_create_room(data):
    """Create a new game room"""
    player_name = data.get('player_name', 'Player')
    num_decks = data.get('num_decks', 1)
    max_players = data.get('max_players', 4)
    num_partners = data.get('num_partners', 2)
    player_id = request.sid

    room = game_manager.create_room(
        host_id=player_id,
        host_name=player_name,
        num_decks=num_decks,
        max_players=max_players,
        num_partners=num_partners
    )

    # Track session
    player_sessions[request.sid] = {
        'room_code': room.room_code,
        'player_id': player_id,
        'player_name': player_name
    }

    # Join socket room
    join_room(room.room_code)

    emit('room_created', {
        'room_code': room.room_code,
        'state': room.get_state(for_player_id=player_id)
    })

    print(f"Room created: {room.room_code} by {player_name}")


@socketio.on('join_room')
def handle_join_room(data):
    """Join an existing room or reconnect"""
    room_code = data.get('room_code', '').upper()
    player_name = data.get('player_name', 'Player')
    new_socket_id = request.sid

    # Check if this is a reconnection
    reconnect_key = (room_code, player_name)
    if reconnect_key in disconnected_players:
        old_player_id = disconnected_players[reconnect_key]
        room = game_manager.get_room(room_code)

        if room and old_player_id in room.players:
            # Reconnection successful - update player's socket ID
            player = room.players[old_player_id]

            # Update player_order with new socket ID
            idx = room.player_order.index(old_player_id)
            room.player_order[idx] = new_socket_id

            # Move player data to new ID
            room.players[new_socket_id] = player
            player.id = new_socket_id
            del room.players[old_player_id]

            # Update host_id if this was the host
            if room.host_id == old_player_id:
                room.host_id = new_socket_id

            # Update highest_bidder_id if this was the bidder
            if room.highest_bidder_id == old_player_id:
                room.highest_bidder_id = new_socket_id

            # Update partner_ids if this player was a partner
            if old_player_id in room.partner_ids:
                idx = room.partner_ids.index(old_player_id)
                room.partner_ids[idx] = new_socket_id

            # Remove from disconnected list
            del disconnected_players[reconnect_key]

            # Track new session
            player_sessions[new_socket_id] = {
                'room_code': room_code,
                'player_id': new_socket_id,
                'player_name': player_name
            }

            # Join socket room
            join_room(room_code)

            # Get remaining disconnected players
            room_disconnected = get_room_disconnected_players(room_code, room)

            # Send reconnection success with full state
            emit('reconnected', {
                'room_code': room_code,
                'state': room.get_state(for_player_id=new_socket_id),
                'valid_cards': room.get_valid_cards(new_socket_id)
            })

            # Notify others
            emit('player_reconnected', {
                'player_name': player_name,
                'disconnected_players': room_disconnected,
                'state': room.get_state()
            }, room=room_code, include_self=False)

            # If no more disconnected players, resume game
            if len(room_disconnected) == 0:
                emit('game_resumed', {
                    'state': room.get_state()
                }, room=room_code)

            print(f"Player {player_name} reconnected to room {room_code}")
            return

    # Normal join (not reconnection)
    success, message, room = game_manager.join_room(room_code, new_socket_id, player_name)

    if not success:
        emit('join_error', {'message': message})
        return

    # Track session
    player_sessions[new_socket_id] = {
        'room_code': room_code,
        'player_id': new_socket_id,
        'player_name': player_name
    }

    # Join socket room
    join_room(room_code)

    emit('room_joined', {
        'room_code': room_code,
        'state': room.get_state(for_player_id=new_socket_id)
    })

    # Notify all players in room
    emit('player_joined', {
        'player_name': player_name,
        'state': room.get_state()
    }, room=room_code, include_self=False)

    print(f"Player {player_name} joined room {room_code}")


@socketio.on('start_game')
def handle_start_game(data):
    """Start the game (host only)"""
    session = player_sessions.get(request.sid)
    if not session:
        emit('error', {'message': 'Not in a room'})
        return

    room_code = session['room_code']
    player_id = session['player_id']

    success, message = game_manager.start_game(room_code, player_id)

    if not success:
        emit('error', {'message': message})
        return

    room = game_manager.get_room(room_code)

    # Send state to each player with their own cards (viewing phase)
    for pid in room.players:
        emit('game_started', {
            'state': room.get_state(for_player_id=pid),
            'viewing_time': 20  # 20 seconds to view cards
        }, room=pid)

    print(f"Game started in room {room_code} - viewing phase")


@socketio.on('start_bidding_phase')
def handle_start_bidding_phase():
    """Transition from viewing phase to bidding phase"""
    session = player_sessions.get(request.sid)
    if not session:
        return

    room_code = session['room_code']
    room = game_manager.get_room(room_code)

    if not room:
        return

    # Only transition if we're in viewing phase
    if room.phase == GamePhase.VIEWING_CARDS:
        room.start_bidding()

        # Notify all players that bidding has started
        for pid in room.players:
            emit('bidding_started', {
                'state': room.get_state(for_player_id=pid)
            }, room=pid)

        print(f"Bidding started in room {room_code}")


@socketio.on('place_bid')
def handle_place_bid(data):
    """Place a bid or pass"""
    session = player_sessions.get(request.sid)
    if not session:
        emit('error', {'message': 'Not in a room'})
        return

    room_code = session['room_code']
    player_id = session['player_id']
    bid_amount = data.get('bid_amount', 0)  # 0 = pass

    # Check if game is paused
    if is_game_paused(room_code):
        emit('bid_error', {'message': 'Game is paused - waiting for disconnected players'})
        return

    room = game_manager.get_room(room_code)
    if not room:
        emit('error', {'message': 'Room not found'})
        return

    success, message = room.place_bid(player_id, bid_amount)

    if not success:
        emit('bid_error', {'message': message})
        return

    # Broadcast updated state to all players
    for pid in room.players:
        emit('bid_update', {
            'state': room.get_state(for_player_id=pid)
        }, room=pid)

    # If bidding ended, notify about partner selection phase
    if room.phase == GamePhase.PARTNER_SELECTION:
        emit('bidding_complete', {
            'highest_bidder': room.players[room.highest_bidder_id].name,
            'bid_amount': room.bid_amount,
            'state': room.get_state()
        }, room=room_code)


@socketio.on('select_trump_partners')
def handle_select_trump_partners(data):
    """Bidder selects trump suit and partner cards"""
    session = player_sessions.get(request.sid)
    if not session:
        emit('error', {'message': 'Not in a room'})
        return

    room_code = session['room_code']
    player_id = session['player_id']
    trump_suit = data.get('trump_suit')
    partner_cards = data.get('partner_cards', [])

    # Check if game is paused
    if is_game_paused(room_code):
        emit('selection_error', {'message': 'Game is paused - waiting for disconnected players'})
        return

    room = game_manager.get_room(room_code)
    if not room:
        emit('error', {'message': 'Room not found'})
        return

    success, message = room.select_trump_and_partners(player_id, trump_suit, partner_cards)

    if not success:
        emit('selection_error', {'message': message})
        return

    # Broadcast to all players with their valid cards
    for pid in room.players:
        emit('game_play_started', {
            'trump_suit': trump_suit,
            'partner_cards': partner_cards,
            'state': room.get_state(for_player_id=pid),
            'valid_cards': room.get_valid_cards(pid)
        }, room=pid)

    print(f"Trump: {trump_suit}, Partners: {partner_cards}")


@socketio.on('play_card')
def handle_play_card(data):
    """Play a card in the current trick"""
    session = player_sessions.get(request.sid)
    if not session:
        emit('error', {'message': 'Not in a room'})
        return

    room_code = session['room_code']
    player_id = session['player_id']
    card_suit = data.get('suit')
    card_rank = data.get('rank')

    # Check if game is paused
    if is_game_paused(room_code):
        emit('play_error', {'message': 'Game is paused - waiting for disconnected players'})
        return

    room = game_manager.get_room(room_code)
    if not room:
        emit('error', {'message': 'Room not found'})
        return

    success, message, result_data = room.play_card(player_id, card_suit, card_rank)

    if not success:
        emit('play_error', {'message': message})
        return

    # Broadcast card played
    emit('card_played', {
        'player_id': player_id,
        'player_name': room.players[player_id].name,
        'card': {'suit': card_suit, 'rank': card_rank},
        'state': room.get_state()
    }, room=room_code)

    # If partner revealed
    if result_data.get('partner_revealed'):
        emit('partner_revealed', {
            'player_name': result_data['revealed_player'],
            'state': room.get_state()
        }, room=room_code)

    # If trick complete
    if result_data.get('trick_complete'):
        emit('trick_complete', {
            'winner': result_data['trick_winner'],
            'winner_id': result_data['trick_winner_id'],
            'points_won': result_data['points_won'],
            'bidder_team_points': result_data['bidder_team_points'],
            'against_team_points': result_data['against_team_points']
        }, room=room_code)

        # If game over
        if result_data.get('game_over'):
            emit('game_over', {
                'bidder_won': result_data['bidder_won'],
                'state': room.get_state()
            }, room=room_code)

    # Send individual states with valid cards
    for pid in room.players:
        emit('state_update', {
            'state': room.get_state(for_player_id=pid),
            'valid_cards': room.get_valid_cards(pid) if room.phase == GamePhase.PLAYING else []
        }, room=pid)


@socketio.on('get_state')
def handle_get_state():
    """Get current game state"""
    session = player_sessions.get(request.sid)
    if not session:
        emit('error', {'message': 'Not in a room'})
        return

    room_code = session['room_code']
    player_id = session['player_id']

    room = game_manager.get_room(room_code)
    if not room:
        emit('error', {'message': 'Room not found'})
        return

    emit('state_update', {
        'state': room.get_state(for_player_id=player_id),
        'valid_cards': room.get_valid_cards(player_id) if room.phase == GamePhase.PLAYING else []
    })


@socketio.on('get_valid_cards')
def handle_get_valid_cards():
    """Get list of valid cards current player can play"""
    session = player_sessions.get(request.sid)
    if not session:
        emit('error', {'message': 'Not in a room'})
        return

    room_code = session['room_code']
    player_id = session['player_id']

    room = game_manager.get_room(room_code)
    if not room:
        emit('error', {'message': 'Room not found'})
        return

    valid_cards = room.get_valid_cards(player_id)
    emit('valid_cards', {'cards': valid_cards})


@socketio.on('send_chat')
def handle_send_chat(data):
    """Send a chat message to all players in the room"""
    session = player_sessions.get(request.sid)
    if not session:
        return

    room_code = session['room_code']
    player_name = session.get('player_name', 'Unknown')
    message = data.get('message', '').strip()[:100]  # Limit to 100 chars

    if not message:
        return

    # Broadcast to all players in room
    emit('chat_message', {
        'player_name': player_name,
        'message': message
    }, room=room_code)


@socketio.on('vote_surrender')
def handle_vote_surrender():
    """Vote to surrender (RageBait button)"""
    session = player_sessions.get(request.sid)
    if not session:
        emit('error', {'message': 'Not in a room'})
        return

    room_code = session['room_code']
    player_id = session['player_id']
    player_name = session.get('player_name', 'Unknown')

    room = game_manager.get_room(room_code)
    if not room:
        emit('error', {'message': 'Room not found'})
        return

    success, message, game_ended = room.vote_surrender(player_id)

    if not success:
        emit('surrender_error', {'message': message})
        return

    # Notify all players about the vote
    emit('surrender_vote', {
        'player_name': player_name,
        'message': message,
        'votes': len(room.surrender_votes),
        'required': room.get_required_surrender_votes(),
        'game_ended': game_ended
    }, room=room_code)

    # If game ended due to surrender
    if game_ended:
        emit('game_over', {
            'bidder_won': False,
            'surrendered': True,
            'state': room.get_state()
        }, room=room_code)


@socketio.on('kick_player')
def handle_kick_player(data):
    """Kick a disconnected player from the game (host only)"""
    session = player_sessions.get(request.sid)
    if not session:
        emit('error', {'message': 'Not in a room'})
        return

    room_code = session['room_code']
    requester_id = session['player_id']

    room = game_manager.get_room(room_code)
    if not room:
        emit('error', {'message': 'Room not found'})
        return

    # Only host can kick
    if room.host_id != requester_id:
        emit('error', {'message': 'Only the host can kick players'})
        return

    player_name_to_kick = data.get('player_name')
    player_id_to_kick = data.get('player_id')

    # Find and remove the disconnected player
    kick_key = None
    for (rc, pname), pid in disconnected_players.items():
        if rc == room_code and (pname == player_name_to_kick or pid == player_id_to_kick):
            kick_key = (rc, pname)
            player_id_to_kick = pid
            player_name_to_kick = pname
            break

    if not kick_key:
        emit('error', {'message': 'Player not found in disconnected list'})
        return

    # Remove from disconnected list
    del disconnected_players[kick_key]

    # Remove player from the game room
    if player_id_to_kick in room.players:
        room.remove_player(player_id_to_kick)

    # Get remaining disconnected players
    room_disconnected = get_room_disconnected_players(room_code, room)

    # Notify all players
    emit('player_kicked', {
        'kicked_player_id': player_id_to_kick,
        'kicked_player_name': player_name_to_kick,
        'disconnected_players': room_disconnected,
        'state': room.get_state()
    }, room=room_code)

    # If no more disconnected players, resume game
    if len(room_disconnected) == 0:
        emit('game_resumed', {
            'state': room.get_state()
        }, room=room_code)

    print(f"Player {player_name_to_kick} kicked from room {room_code}")


@socketio.on('play_again')
def handle_play_again():
    """Reset the game and return all players to lobby (host only)"""
    session = player_sessions.get(request.sid)
    if not session:
        emit('error', {'message': 'Not in a room'})
        return

    room_code = session['room_code']
    requester_id = session['player_id']

    room = game_manager.get_room(room_code)
    if not room:
        emit('error', {'message': 'Room not found'})
        return

    # Only host can trigger play again
    if room.host_id != requester_id:
        emit('error', {'message': 'Only the host can start a new game'})
        return

    # Only allow play again when game is over
    if room.phase != GamePhase.GAME_OVER:
        emit('error', {'message': 'Game is not over yet'})
        return

    # Clear any disconnected players for this room
    keys_to_remove = [key for key in disconnected_players.keys() if key[0] == room_code]
    for key in keys_to_remove:
        del disconnected_players[key]

    # Reset the game
    room.reset_game()

    # Notify all players to go back to lobby
    for pid in room.players:
        emit('game_reset', {
            'room_code': room_code,
            'state': room.get_state(for_player_id=pid)
        }, room=pid)

    print(f"Game reset in room {room_code} - returning to lobby")


@socketio.on('request_play_again')
def handle_request_play_again():
    """Non-host player requests to play again - notifies the host"""
    session = player_sessions.get(request.sid)
    if not session:
        return

    room_code = session['room_code']
    player_name = session.get('player_name', 'A player')

    room = game_manager.get_room(room_code)
    if not room:
        return

    # Notify the host that someone wants to play again
    emit('play_again_requested', {
        'player_name': player_name
    }, room=room.host_id)


if __name__ == '__main__':
    local_ip = get_local_ip()
    print(f"\n{'='*50}")
    print(f"  CARD GAME SERVER")
    print(f"{'='*50}")
    print(f"  Local:   http://localhost:5000")
    print(f"  Network: http://{local_ip}:5000")
    print(f"{'='*50}")
    print(f"  Share the Network URL with players on same WiFi/Hotspot")
    print(f"{'='*50}\n")

    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
