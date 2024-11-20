import random
import os
import pickle
import time
import argparse
import numpy as np
import matplotlib.pyplot as plt
from typing import List, Set, Tuple, Optional, Dict
from collections import defaultdict

from get_solutions import find_up_to_two_solutions


def visualize_queens(positions: List[Tuple[int, int]], n: int = 8):
    """Visualize queen positions on a chess board using matplotlib"""
    # Create figure and axis
    fig, ax = plt.subplots(figsize=(8, 8))
    
    # Create chess board pattern
    board = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if (i + j) % 2 == 0:
                board[i, j] = 0.8  # Light squares
            else:
                board[i, j] = 0.3  # Dark squares
    
    # Plot the board
    ax.imshow(board, cmap='gray')
    
    # Plot queens as red dots with white edge
    queen_rows, queen_cols = zip(*positions)
    ax.scatter(queen_cols, queen_rows, color='red', s=300, marker='o', 
              edgecolor='white', linewidth=2, zorder=2, label='Queens')
    
    # Customize the plot
    ax.grid(True, color='black', linewidth=0.5)
    ax.set_xticks(np.arange(-0.5, n, 1))
    ax.set_yticks(np.arange(-0.5, n, 1))
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    
    # Add board coordinates
    for i in range(n):
        ax.text(-0.7, i, str(i), ha='center', va='center')
        ax.text(i, -0.7, str(i), ha='center', va='center')
    
    plt.title(f"Queen Positions on {n}x{n} Board")
    plt.tight_layout()
    plt.show()


def visualize_regions_queens(board: np.ndarray, queens: List[Tuple[int, int]]):
    """Visualize the regions and queens"""
    n = board.shape[0]
    
    # Create color map with distinct colors
    num_colors = len(set(board.flatten()))
    colors = plt.get_cmap('tab20')(np.linspace(0, 1, num_colors))
    
    fig, ax = plt.subplots(figsize=(8, 8))
    
    # Plot regions
    im = ax.imshow(board, cmap=plt.get_cmap('tab20'))
    
    # Plot queens
    queen_rows, queen_cols = zip(*queens)
    ax.scatter(queen_cols, queen_rows, color='red', s=300, marker='o', 
              edgecolor='white', linewidth=2, zorder=2, label='Queens')
    
    # Customize the plot
    ax.grid(True, color='black', linewidth=0.5)
    ax.set_xticks(np.arange(-0.5, n, 1))
    ax.set_yticks(np.arange(-0.5, n, 1))
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    
    plt.title(f"Queen Positions and Regions on {n}x{n} Board")
    plt.tight_layout()
    plt.show()
    # plt.show(block=False)


def generate_random_queens(n: int = 8) -> List[Tuple[int, int]]:
    """Generate random valid queen positions on an nxn board using backtracking"""
    def is_valid_position(pos: Tuple[int, int], queens: List[Tuple[int, int]]) -> bool:
        row, col = pos
        
        # Check if position shares row or column with existing queens
        for q_row, q_col in queens:
            if row == q_row or col == q_col:
                return False
            
        # Check if position is adjacent to existing queens (including diagonally)
        for q_row, q_col in queens:
            if abs(row - q_row) <= 1 and abs(col - q_col) <= 1:
                return False
                
        return True

    def backtrack(queens: List[Tuple[int, int]], 
                 remaining_positions: List[Tuple[int, int]]) -> Optional[List[Tuple[int, int]]]:
        if len(queens) == n:
            return queens
            
        # Shuffle remaining positions for randomness
        positions = remaining_positions.copy()
        random.shuffle(positions)
        
        for pos in positions:
            if is_valid_position(pos, queens):
                queens.append(pos)
                new_remaining = [p for p in positions if p != pos]
                result = backtrack(queens, new_remaining)
                if result is not None:
                    return result
                queens.pop()
                
        return None

    # Initialize all possible positions
    all_positions = [(i, j) for i in range(n) for j in range(n)]
    
    # Keep trying until we find a valid solution
    while True:
        result = backtrack([], all_positions)
        if result is not None:
            return result


def generate_regions_jagged(queens: List[Tuple[int, int]], n: int = 8) -> Optional[np.ndarray]:
    """
    Generate non-compact, jagged regions to increase likelihood of unique solutions.
    Returns an nxn numpy array where each cell contains a number 0 to n-1 representing its region.

    Maintains invariant that the coloring state has a unique solution. If there is no
    possible next color assignment then it will return None
    """
    def get_adjacent_cells(row: int, col: int) -> List[Tuple[int, int]]:
        """Get orthogonally adjacent cells"""
        adjacent = []
        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < n and 0 <= new_col < n:
                adjacent.append((new_row, new_col))
        return adjacent
    
    def get_adjacent_cells_diag(row: int, col: int) -> List[Tuple[int, int]]:
        """Get all adjacent cells including diagonals"""
        adjacent = []
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr != 0 or dc != 0:
                    new_row, new_col = row + dr, col + dc
                    if 0 <= new_row < n and 0 <= new_col < n:
                        adjacent.append((new_row, new_col))
        return adjacent
    
    def softmax(scores: List[float], temperature: float = 1.0) -> List[float]:
        """
        Convert scores to probabilities using softmax with temperature.
        Higher temperature = more random, Lower = more deterministic
        """
        # Shift scores to avoid overflow
        scores = np.array(scores)
        scores = scores - np.max(scores)
        exp_scores = np.exp(scores / temperature)
        return exp_scores / exp_scores.sum()

    
    def get_spindly_score(row: int, col: int, color: int, queens,
                          square_to_disallowed_color_mapping) -> float:
        """
        Calculate how 'spindly' placing color at this position would be.
        Higher score = more jagged/spindly (preferred)

        # Prefer positions that:
        # 1. Have few neighbors of same color (creates thin regions)
        # 2. Have many neighbors of different colors (creates jagged boundaries)
        # 3. Not marking next to a banned color
        """
        adjacent = get_adjacent_cells(row, col)
        
        # Count colored neighbors of same and different colors
        same_color = 0
        diff_color = 0
        for adj_row, adj_col in adjacent:
            if board[adj_row, adj_col] == color:
                same_color += 1
            elif board[adj_row, adj_col] != -1:
                diff_color += 1

        found_banned_square_adjacent = False
        neighbors_of_potential_spot = get_adjacent_cells(row, col)

        for n in neighbors_of_potential_spot:
            if color in square_to_disallowed_color_mapping[n]:
                found_banned_square_adjacent = True

        color_banned_penalty = 0
        if found_banned_square_adjacent:
            color_banned_penalty = -10
        
        return diff_color - (same_color * 1.5) + color_banned_penalty
    
    # Initialize board with -1 (uncolored)
    board = np.full((n, n), -1)
    
    # Assign random colors to queens
    colors = list(range(len(queens)))
    color_to_queen_loc = {}

    random.shuffle(colors)
    for (row, col), color in zip(queens, colors):
        board[row, col] = color
        color_to_queen_loc[color] = (row, col)

    # Keep track of uncolored cells
    uncolored_cells = set((i, j) for i in range(n) for j in range(n) 
                         if board[i, j] == -1)
    
    # Using symmetry test to mark disallowed colors
    square_to_disallowed_color_mapping = defaultdict(list)  # (row, col) -> list(int)

    while uncolored_cells:
        # Find all uncolored cells adjacent to colored regions
        candidates = []
        for row, col in uncolored_cells:
            adjacent = get_adjacent_cells(row, col)
            adj_colors = set(board[r, c] for r, c in adjacent if board[r, c] != -1)
            
            # For each adjacent color, calculate spindly score
            for color in adj_colors:
                score = get_spindly_score(row, col, color, queens, 
                                          square_to_disallowed_color_mapping)
                candidates.append((score, (row, col, color)))
        
        assert len(candidates) != 0

        # Loop until we find a valid color choice for a square that doesnt result in 
        # the board having multiple solutions
        next_color_found = False        
        while not next_color_found:
            # If run out of valid candidates, we reached a dead end so return None
            if not candidates:
                # visualize_regions_queens(board, queens)
                print("Reached a dead end of a genration, restarting!")
                return None
        
            # Probabilistically sample from candidates
            scores = [score for score, _ in candidates]
            positions = [(r, c, color) for _, (r, c, color) in candidates]
            probabilities = softmax([x+2 for x in scores], temperature=0.2)
            selected_idx = np.random.choice(len(positions), p=probabilities)
            row, col, color = positions[selected_idx]
            selected_score = scores[selected_idx]
            
            # If the color at that position is banned, reject it
            if color in square_to_disallowed_color_mapping[(row, col)]:
                candidates.remove((selected_score, (row, col, color)))
                continue

            # Test if the resulting board is single solution
            board[row, col] = color
            solutions = find_up_to_two_solutions(board)

            if len(solutions) == 1:
                # If so, mark next_color_found as True and visualize
                next_color_found = True
                uncolored_cells.remove((row, col))

                # visualize_regions_queens(board, queens)

                # Here we can do the symmetry check for when the color is on the
                #   same row or column as the original queen
                queen_loc_of_color = color_to_queen_loc[color]

                if queen_loc_of_color[0] == row:
                    # Use the column to find the queen of that column
                    conflicting_queen_loc = None

                    for queen_loc in queens:
                        if queen_loc[1] == col:
                            conflicting_queen_loc = queen_loc
                            break

                    assert conflicting_queen_loc is not None  # TODO: remove

                    new_potential_current_queen_loc = (row,
                                                        col)
                    # Conflicting potential is current queen col, same row
                    new_potential_conflicting_queen_loc = (conflicting_queen_loc[0],
                                                            queen_loc_of_color[1])
                    
                    # Only do this check if the conflicting potential square uncolored
                    if board[new_potential_conflicting_queen_loc] == -1:
                        # Check immediate neighbors of both. If there is no neighboring
                        #   queen in either new potential spot then we have to mark
                        #   a forbidden color. Ignore the queen of the same color when looking
                        new_potential_current_queen_surroundings = \
                            get_adjacent_cells_diag(new_potential_current_queen_loc[0],
                                                    new_potential_current_queen_loc[1])
                        if queen_loc_of_color in new_potential_current_queen_surroundings:
                            new_potential_current_queen_surroundings.remove(queen_loc_of_color)

                        new_potential_conflicting_queen_surroundings = \
                            get_adjacent_cells_diag(new_potential_conflicting_queen_loc[0],
                                                    new_potential_conflicting_queen_loc[1])
                        if conflicting_queen_loc in new_potential_conflicting_queen_surroundings:
                            new_potential_conflicting_queen_surroundings.remove(conflicting_queen_loc)
                        
                        found_neighbor_queen_in_new_potential_loc = False
                        for q in queens:
                            if q in new_potential_current_queen_surroundings:
                                # print("found neighbor queen for current potential", q)
                                found_neighbor_queen_in_new_potential_loc = True
                                break
                            if q in new_potential_conflicting_queen_surroundings:
                                # print("found neighbor queen for conflicting potential", q)
                                found_neighbor_queen_in_new_potential_loc = True
                                break
                        
                        if not found_neighbor_queen_in_new_potential_loc:
                            square_to_disallowed_color_mapping[new_potential_conflicting_queen_loc].append(
                                int(board[conflicting_queen_loc]))
                            # print(f"No neighbor conflicts found, need to mark illegal color of {board[conflicting_queen_loc]}")                        

                elif queen_loc_of_color[1] == col:
                    # Use the row to find the queen of that row
                    conflicting_queen_loc = None

                    for queen_loc in queens:
                        if queen_loc[0] == row:
                            conflicting_queen_loc = queen_loc
                            break

                    assert conflicting_queen_loc is not None  # TODO: remove
                    # Current potential is where we will place new color
                    new_potential_current_queen_loc = (row,
                                                        col)
                    # Conflicting potential is current queen row, same col
                    new_potential_conflicting_queen_loc = (queen_loc_of_color[0],
                                                            conflicting_queen_loc[1])
                    # Only do this check if the conflicting potential square uncolored
                    if board[new_potential_conflicting_queen_loc] == -1:
                        # Check immediate neighbors of both. If there is no neighboring
                        #   queen in either new potential spot then we have to mark
                        #   a forbidden color. Ignore the queen of the same color when looking
                        new_potential_current_queen_surroundings = \
                            get_adjacent_cells_diag(new_potential_current_queen_loc[0],
                                                    new_potential_current_queen_loc[1])
                        new_potential_conflicting_queen_surroundings = \
                            get_adjacent_cells_diag(new_potential_conflicting_queen_loc[0],
                                                    new_potential_conflicting_queen_loc[1])

                        found_neighbor_queen_in_new_potential_loc = False
                        # ignore the swapping queens
                        queens_to_check = [q for q in queens
                                        if q != queen_loc_of_color
                                        if q != conflicting_queen_loc]
                        assert len(queens_to_check) == (n - 2)
                        for q in queens_to_check:
                            if q in new_potential_current_queen_surroundings:
                                # print("found neighbor queen for current potential", q)
                                found_neighbor_queen_in_new_potential_loc = True
                                break
                            if q in new_potential_conflicting_queen_surroundings:
                                # print("found neighbor queen for conflicting potential", q)
                                found_neighbor_queen_in_new_potential_loc = True
                                break
                        
                        if not found_neighbor_queen_in_new_potential_loc:
                            square_to_disallowed_color_mapping[new_potential_conflicting_queen_loc].append(
                                int(board[conflicting_queen_loc]))
                            # print(f"No neighbor conflicts found, need to mark illegal color of {board[conflicting_queen_loc]}")

            else:
                # Found multiple solutions, undo color and remove from candidates
                board[row, col] = -1
                candidates.remove((selected_score, (row, col, color)))
    
    return board


def find_unique_solution_board(n: int, max_attempts: int = 1000000) -> Optional[np.ndarray]:
    """
    Optimized version of board finder.
    """
    start_time = time.time()

    for attempt_num in range(max_attempts):
        queens = generate_random_queens(n)
        board = generate_regions_jagged(queens, n)

        if (attempt_num+1) % 10 == 0:
            elapsed = time.time() - start_time
            boards_per_sec = attempt_num / elapsed if elapsed > 0 else 0
            print(f"Attempt {attempt_num}, {boards_per_sec:.1f} boards/sec")            

        if board is not None:
            print(f"Found unique solution board after {attempt_num} attempts")
            attempt_time = time.time() - start_time
            print(f"Took {attempt_time:.2f} seconds")
            print(board)
            print(queens)
            return board, queens

    return None

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Generate puzzle boards with unique queen solutions')
    
    # Add arguments
    parser.add_argument('--size', '-n', 
                       type=int, 
                       default=8,
                       help='Size of the board (default: 8)')
    parser.add_argument('--output_folder',
                        type=str,
                        default="output_folder",
                        help="The folder to save the generated boards to")
    parser.add_argument('--num_generations',
                        type=int,
                        default=1,
                        help="Number of boards to generate")
    parser.add_argument('--visualize_boards',
                        action="store_true",
                        help="Set flag to visualize finished board each iteration")
    args = parser.parse_args()

    n = args.size
    output_folder = args.output_folder
    num_generations = args.num_generations
    visualize_boards = args.visualize_boards

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for i in range(num_generations):
        print(f"Generation Number {i}")
        board, queens = find_unique_solution_board(n)

        game_data = {"board": board, "queens": queens}
        with open(os.path.join(output_folder, f'board_num_{i}.pkl'), 'wb') as f:
            pickle.dump(game_data, f)

        if visualize_boards:
            visualize_regions_queens(board, queens)
