import os
import sys
from .config import DATA_DIR
from .nhl_scraper import get_and_save_data_for_tableau

def run_for_game(game_id):
    print(f"Processing game {game_id}...")
    get_and_save_data_for_tableau(game_id)
    print(f"Game {game_id} data saved!")

if __name__ == "__main__":
    game_id = int(input("Enter NHL game ID: ").strip())
    run_for_game(game_id)