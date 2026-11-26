from agents.agent import Agent
from store import register_agent
from helpers import (get_valid_moves, execute_move, check_winner, copy_state,
                     top_view, LINES)
from constants import *
import time

THREAT_BONUS = 50
DOUBLE_THREAT_BONUS = 400
WINNING_THREAT = 5000 # I have a single gap in a line and it is my turn
TIME_LIMIT = 0.2 # TO SET BACK TO 1.5, this is to make testing faster
WIN_SCORE = 100000

#---------------------------------------------------------------------------
# HELPERS
#---------------------------------------------------------------------------

def after(board, reserves, player, move): # returns state after player makes a legal move
    next_board, next_reserves = copy_state(board, reserves)
    execute_move(next_board, next_reserves, player, move)
    return next_board, next_reserves


def opponent_has_immediate_win(board, reserves, opponent): # return if the opponent can win on their next move
    for move in get_valid_moves(board, reserves, opponent):
        next_board, _ = after(board, reserves, opponent, move)
        if check_winner(next_board, opponent) == opponent:
            return True
    return False


def largest_available_size(owners, sizes, reserves, who):
    for size in (LARGE, MEDIUM, SMALL):
        if reserves[who, size] > 0:
            return size # return largest size in the reserve
        if ALLOW_MOVES: # return largest size currently on the board that could be moved
            for r in range(BOARD_SIZE):
                for c in range(BOARD_SIZE):
                    if owners[r, c] == who and sizes[r, c] == size:
                        return size
    return -1

def can_be_covered(piece_size, opponent_max_size): # returns trye if the oponent can cover the piece
    return opponent_max_size > piece_size


def can_fill(owners, sizes, r, c, who, who_max): # can who place a piece on (r,c)
    if owners[r, c] == EMPTY:
        return who_max >= 0                      # any piece will do
    if owners[r, c] == 3 - who:                  # the other player's piece
        return who_max > sizes[r, c]             # need a strictly larger one
    return False                                 # own piece or obstacle


def threat_score(n):
        if n >= 2: # basically a win becayse opponent can mostly block one threat per move
            return DOUBLE_THREAT_BONUS
        if n == 1: # could be blocked next round
            return THREAT_BONUS
        return 0

# def get_stack(board, r,c): # returns the pieces on (r,c from bottom to top) as [(Player, size), (Player, size)....]
#     if board[r, c, SMALL] == OBSTACLE:
#         return []
#     for s in (SMALL, MEDIUM, LARGE):
#         if board[r, c, s] != EMPTY:
#             return [(int(board[r, c, s]), s)]

def piece_below_top(board, r, c, top_size): # what piece is revealed if the top piece at (r,c) moves
    for s in range(top_size - 1, -1, -1):      # next size down, then the one below
        if board[r, c, s] != EMPTY:
            return int(board[r, c, s])
    return EMPTY       

#---------------------------------------------------------------------------
# HEURISTIC
#---------------------------------------------------------------------------

def evaluate(board, reserves, player, opponent, turn = None):
    # Factors that count in the heuristic
    # 1. Score increases by the number of squares I own in lines where there are no obstacles and no pieces from the other player (at the top)
    # 2. Score decreases by the numner of squares the opponent owns in lines where I have no square and there are no obstacles
    # 3. Score fluctuations in 1 and 2 depend on whether or not the pieces can be covered by the other player (0,5 if yes, 1 if no)
    # 4. Score is increased if next turn player can fill the 4th square
    # 5. TO-DO Pin pieces in place that would allow the opponent to win if moved (a piece that hides an opponent piece that would form a line otherwise)

    owners, sizes = top_view(board)
    score = 0
    line_value = (0, 2, 12, 80, 0)

    opp_max = largest_available_size(owners, sizes, reserves, opponent)
    my_max  = largest_available_size(owners, sizes, reserves, player)

    # Squares missing to form a line:
    my_gaps = set()     
    their_gaps = set()

    # Pinned pieces not to move
    # pinned = set()

    for line in LINES[WIN_LENGTH]:
        # a player can never win with a line that has an obstacle
        if any(owners[r, c] == OBSTACLE for r, c in line):
            continue

        # Increment score by number of

        my_count = 0     # how many squares each side owns (integer)
        their_count = 0    
        my_sum = 0.0        # same, but coverable pieces count 0.5
        their_sum = 0.0
        my_squares = []

        for r, c in line:
            if owners[r, c] == player:
                my_count += 1
                my_squares.append((r, c))
                if can_be_covered(sizes[r, c], opp_max):
                    my_sum += 0.5
                else:
                    my_sum += 1.0
            elif owners[r, c] == opponent:
                their_count += 1
                if can_be_covered(sizes[r, c], my_max):
                    their_sum += 0.5
                else:
                    their_sum += 1.0

        if their_count == 0 and my_count > 0: # opponent has no piece in this line
            score += line_value[my_count] * (my_sum / my_count)
        elif my_count == 0 and their_count > 0:
            score -= line_value[their_count] * (their_sum / their_count)
        # elif their_count == 3 and my_count == 1:
        #     r, c = my_squares[1]
        #     if (piece_below_top(board, r, c, sizes[r,c]) != EMPTY):
        #         pinned.add(r,c)

        if my_count == WIN_LENGTH - 1:
            gap = next((r, c) for r, c in line if owners[r, c] != player)
            if can_fill(owners, sizes, gap[0], gap[1], player, my_max):
                my_gaps.add(gap)

        if their_count == WIN_LENGTH - 1:
            gap = next((r, c) for r, c in line if owners[r, c] != opponent)
            if can_fill(owners, sizes, gap[0], gap[1], opponent, opp_max):
                their_gaps.add(gap)

    # Update if the next move is a threat for the opponent

    if turn == player and my_gaps:
        score += WINNING_THREAT
    elif turn == opponent and their_gaps:
        score -= WINNING_THREAT
    else:
        score += threat_score(len(my_gaps))
        score -= threat_score(len(their_gaps))

    # Larger visible pieces can cover more opposing pieces.  Prefer keeping
    # large pieces in reserve slightly, so they remain available as replies.
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            owner = owners[r, c]
            if owner == player:
                score += int(sizes[r, c]) + 1
            elif owner == opponent:
                score -= int(sizes[r, c]) + 1
            # elif pinned.contains(board[r,c, sizes[r,c]]):
            #     score -= 1000 # decrease score by a lot for a move that reveals a piece in a winning line
    score += int(reserves[player, LARGE]) * 2
    score -= int(reserves[opponent, LARGE]) * 2
    return score

#---------------------------------------------------------------------------
# ALPHA-BETA
#---------------------------------------------------------------------------

class TimeUp(Exception):
    pass

def max_value(board, reserves, player, opponent, alpha, beta, depth, deadline):
    if time.perf_counter() > deadline:
        raise TimeUp()

    winner = check_winner(board, opponent)
    if winner == opponent:
        return -WIN_SCORE
    if winner == player:
        return WIN_SCORE
    if depth == 0:
        return evaluate(board, reserves, player, opponent, turn = player)

    for move in get_valid_moves(board, reserves, player):
        next_board, next_reserves = after(board, reserves, player, move)
        alpha = max(alpha, min_value(next_board, next_reserves, player, opponent, alpha, beta, depth - 1, deadline))
        if alpha >= beta:
            return beta
    return alpha

def min_value(board, reserves, player, opponent, alpha, beta, depth, deadline):
    if time.perf_counter() > deadline:
            raise TimeUp()
    
    winner = check_winner(board, player)
    if winner == player:
        return WIN_SCORE
    if winner == opponent:
        return -WIN_SCORE
    if depth == 0:
        return evaluate(board, reserves, player, opponent, turn = opponent)

    for move in get_valid_moves(board, reserves, opponent):
        next_board, next_reserves = after(board, reserves, opponent, move)
        beta = min(beta, max_value(next_board, next_reserves, player, opponent, alpha, beta, depth - 1, deadline))
        if alpha >= beta:
            return alpha
    return beta

def alpha_beta_decision(board, reserves, player, opponent, depth, deadline, first_move):
    moves = get_valid_moves(board, reserves, player)

    if first_move is not None:
        moves.remove(first_move)
        moves.insert(0, first_move)

    best_move = moves[0]
    alpha = float("-inf")
    beta = float("inf")
    for move in moves:
        next_board, next_reserves = after(board, reserves, player, move)
        value = min_value(next_board, next_reserves, player, opponent,
                            alpha, beta, depth - 1, deadline)
        if value > alpha:
            alpha = value
            best_move = move
    return best_move, alpha

def iterative_deepening(board, reserves, player, opponent):
    deadline = time.perf_counter() + TIME_LIMIT
    best_move = None
    depth = 1
    try:
        while True:
            best_move, value = alpha_beta_decision(board, reserves, player, opponent, depth, deadline, best_move)
            if value >= WIN_SCORE or value <= -WIN_SCORE:
                break
            depth += 1
    except TimeUp:
        pass
    return best_move

#---------------------------------------------------------------------------
# AGENT INITIALIZATION
#---------------------------------------------------------------------------

@register_agent("student_agent")          # do not change this string
class StudentAgent(Agent):
    def __init__(self):
        """Set up your agent. This runs once per game, before the first move, and must finish
        within INIT_TIME_LIMIT seconds."""
        super().__init__()
        self.name = "StudentAgent"

    def step(self, board, reserves, player, opponent):
        """Return the Move you want to play.

        Takes: board, reserves - your own copies of the current position.
               player, opponent - your player number (1 or 2) and the other one.
        Agent.step in agents/agent.py explains each argument and the time limit.
        """
        search_move = iterative_deepening(board, reserves, player, opponent)
        if search_move is not None:
            return search_move
        
        moves = get_valid_moves(board, reserves, player)
        survivors = []
        safe = []

        for move in moves:
            next_board, next_reserves = after(board, reserves, player, move)
            winner = check_winner(next_board, player)

            if winner == player:
                return move
            if winner == opponent:
                # Moving a top piece can reveal the opponent's completed line.
                # That loss has priority over any line made by this move.
                continue

            candidate = (move, next_board, next_reserves)
            survivors.append(candidate)
            if not opponent_has_immediate_win(next_board, next_reserves, opponent):
                safe.append(candidate)

        # If every move permits an immediate opponent win, still prefer a move
        # that does not itself lose by the uncovering rule.  This fallback also
        # guarantees a legal move if no alternative exists.
        pool = safe or survivors
        if not pool:
            return moves[0]

        best_move = pool[0][0]
        best_score = evaluate(pool[0][1], pool[0][2], player, opponent)
        for move, next_board, next_reserves in pool[1:]:
            score = evaluate(next_board, next_reserves, player, opponent)
            if score > best_score:
                best_move, best_score = move, score

        return best_move