# orchestrator.py

import itertools
import subprocess
import yaml
import os
import sys
import csv
import logging
import datetime # Added for timestamp
import argparse # Added for command-line arguments
from math import factorial
from src.utils import setup_logging

CONFIG_FILE = os.path.join("data", "config.yaml")
# Base directory for all results
RESULTS_BASE_DIR = "results"

def load_player_ids_from_config(config_path):
    """Loads player IDs from the player data file specified in the main config."""
    # Get logger instance within the function scope
    logger = logging.getLogger(__name__) # Or use "Orchestrator" if preferred for consistency
    logger.info(f"Loading main configuration from: {config_path}")
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        player_file_path = config_data.get('player_data_file')
        if not player_file_path:
            raise ValueError("Main config file must specify 'player_data_file'.")

        logger.info(f"Loading player IDs from player data file: {player_file_path}")
        with open(player_file_path, 'r') as f_players:
            player_config = yaml.safe_load(f_players)
        roster_data = player_config.get('players', [])
        if not roster_data:
            raise ValueError(f"Player data file {player_file_path} must contain a 'players' list.")

        player_ids = [player['id'] for player in roster_data]
        # Validation
        if len(player_ids) != 9:
            raise ValueError(f"Expected 9 players in player data file '{player_file_path}', found {len(player_ids)}")
        if len(player_ids) != len(set(player_ids)):
             raise ValueError(f"Duplicate player IDs found in player data file '{player_file_path}'.")
        logger.info(f"Successfully loaded {len(player_ids)} player IDs.")
        return player_ids
    except FileNotFoundError as e:
        # More specific error message depending on which file was not found
        if 'config_data' not in locals():
             logger.error(f"Main configuration file not found at {config_path}")
        else:
             logger.error(f"Player data file not found at {player_file_path}")
        raise
    except yaml.YAMLError as e:
         # More specific error message
         if 'player_config' not in locals():
              logger.error(f"Error parsing main config YAML {config_path}: {e}")
         else:
              logger.error(f"Error parsing player data YAML {player_file_path}: {e}")
         raise
    except KeyError as e:
        logger.error(f"Could not find expected key ('player_data_file' in config or 'id'/'players' in player file): {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading player IDs: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Run baseball simulations for all lineup permutations.")
    parser.add_argument('--start', type=int, default=0,
                        help='Starting index (0-based) of permutations to simulate.')
    parser.add_argument('--stop', type=int, default=None,
                        help='Stopping index (exclusive) of permutations to simulate. If None, simulates to the end.')
    parser.add_argument('--num-games', type=int, default=None,
                        help='Override the number of games to simulate per lineup (from config.yaml).')
    parser.add_argument('--debug', action='store_true', help='Enable DEBUG level logging.')

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(level=log_level)
    logger = logging.getLogger("Orchestrator")

    logger.info("Starting Lineup Permutation Simulation Orchestrator...")
    logger.debug(f"Orchestrator Args: {args}")

    try:
        player_ids = load_player_ids_from_config(CONFIG_FILE)
        logger.info(f"Loaded Player IDs: {player_ids}")
    except Exception:
        logger.error("Failed to load player IDs. Exiting.")
        sys.exit(1)

    # --- Create Timestamped Output Directory ---
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_output_dir = os.path.join(RESULTS_BASE_DIR, timestamp)
    try:
        os.makedirs(run_output_dir, exist_ok=True)
        logger.info(f"Created results directory: {run_output_dir}")
    except OSError as e:
        logger.error(f"Failed to create results directory {run_output_dir}: {e}")
        sys.exit(1)

    # Define CSV output path within the timestamped directory
    output_csv_path = os.path.join(run_output_dir, "all_lineup_results.csv")
    logger.info(f"Orchestrator results CSV will be saved to: {output_csv_path}")

    # Generate all permutations
    logger.info("Generating all lineup permutations...")
    all_permutations_generator = itertools.permutations(player_ids)
    total_possible_perms = factorial(len(player_ids))
    logger.info(f"Total possible permutations: {total_possible_perms}")

    # Apply slicing based on --start and --stop
    start_index = args.start
    stop_index = args.stop if args.stop is not None else total_possible_perms

    if start_index < 0 or start_index >= total_possible_perms:
        logger.error(f"Invalid start index {start_index}. Must be between 0 and {total_possible_perms - 1}.")
        sys.exit(1)
    if stop_index <= start_index or stop_index > total_possible_perms:
         logger.error(f"Invalid stop index {stop_index}. Must be greater than start index ({start_index}) and no more than {total_possible_perms}.")
         sys.exit(1)

    # Use islice to efficiently handle the range without generating all permutations in memory at once
    permutations_to_run = list(itertools.islice(all_permutations_generator, start_index, stop_index))
    num_permutations_in_slice = len(permutations_to_run)
    logger.info(f"Selected permutations from index {start_index} to {stop_index} (exclusive). Total to simulate: {num_permutations_in_slice}")

    try:
        # Open in append mode ('a') if starting mid-way to potentially continue a previous run?
        # For simplicity, let's stick with 'w' - each orchestrator run creates a new file in its timestamped dir.
        with open(output_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            # Write Header
            header = [f"P{i+1}_ID" for i in range(9)] + ["AverageScore"]
            writer.writerow(header)
            logger.info(f"Initialized CSV '{output_csv_path}' with header.")

            # Loop through the selected slice of permutations
            for i, lineup_perm in enumerate(permutations_to_run):
                # Calculate the absolute index for logging purposes
                absolute_index = start_index + i
                lineup_str = " ".join(lineup_perm)
                logger.info(f"\n--- Running Simulation {i+1}/{num_permutations_in_slice} (Absolute Index: {absolute_index}) ---")
                logger.info(f"Lineup: {lineup_str}")

                # Construct command for main.py subprocess
                command = [
                    sys.executable, 'main.py',
                    '--lineup'] + list(lineup_perm) + [
                    '--verbose', 'False', # Keep main.py non-verbose for stdout capture
                    '--output-dir', run_output_dir # Pass the specific dir for this run
                ]
                # Add --num-games override if provided to orchestrator
                if args.num_games is not None:
                    command.extend(['--num-games', str(args.num_games)])

                logger.debug(f"Executing command: {' '.join(command)}")

                try:
                    # Run main.py as a subprocess, capture stdout, check for errors
                    process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')

                    # Process completed successfully, read average score from stdout
                    avg_score_str = process.stdout.strip()
                    try:
                        avg_score = float(avg_score_str)
                        logger.info(f"Simulation successful. Average Score: {avg_score:.4f}")

                        # Write result row to CSV
                        row = list(lineup_perm) + [f"{avg_score:.4f}"]
                        writer.writerow(row)
                        f.flush() # Ensure data is written periodically

                        # Removed grand_total_runs update

                    except ValueError:
                        logger.error(f"Could not convert stdout ('{avg_score_str}') to float for lineup {lineup_perm}. Skipping row.")
                        logger.error(f"Subprocess stderr:\n{process.stderr}")


                except subprocess.CalledProcessError as e:
                    logger.error(f"!!! Error running main.py for lineup: {lineup_perm} !!!")
                    logger.error(f"Return Code: {e.returncode}")
                    logger.error(f"Stdout:\n{e.stdout}")
                    logger.error(f"Stderr:\n{e.stderr}")
                    # Decide whether to continue or stop
                    # continue # Skip this permutation
                    logger.error("Stopping orchestrator due to error in subprocess.")
                    sys.exit(1) # Stop execution

            # Removed writing the total runs row
            logger.info(f"\n--- All Simulations Complete ---")
            logger.info(f"Results summary saved to '{output_csv_path}'")


    except IOError as e:
        logger.error(f"Failed to write to CSV file {output_csv_path}: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"An unexpected error occurred during orchestration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
