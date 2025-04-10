# orchestrator.py

import itertools
import subprocess
import yaml
import os
import sys
import csv
import logging
import datetime # Added for timestamp
from math import factorial
from src.utils import setup_logging

CONFIG_FILE = os.path.join("data", "config.yaml")
# Base directory for all results
RESULTS_BASE_DIR = "results"

def load_player_ids_from_config(config_path):
    """Loads only the list of player IDs from the config file."""
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        roster_data = config_data.get('lineup', [])
        player_ids = [player['id'] for player in roster_data]
        if len(player_ids) != 9:
            raise ValueError(f"Expected 9 players in config 'lineup', found {len(player_ids)}")
        if len(player_ids) != len(set(player_ids)):
             raise ValueError(f"Duplicate player IDs found in config file.")
        return player_ids
    except FileNotFoundError:
        logging.error(f"Configuration file not found at {config_path}")
        raise
    except KeyError:
        logging.error(f"Could not find 'id' key for a player in {config_path}")
        raise
    except Exception as e:
        logging.error(f"Error loading player IDs from config: {e}")
        raise

def main():
    setup_logging(level=logging.INFO)
    logger = logging.getLogger("Orchestrator")

    logger.info("Starting Lineup Permutation Simulation Orchestrator...")

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
    all_permutations = list(itertools.permutations(player_ids))
    #all_permutations = all_permutations[0:100]  # for testing
    num_permutations = len(all_permutations) # factorial(9) = 362,880
    logger.info(f"Generated {num_permutations} lineup permutations.")

    # Removed grand_total_runs calculation and num_games reading for it

    try:
        with open(output_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            # Write Header
            header = [f"P{i+1}_ID" for i in range(9)] + ["AverageScore"]
            writer.writerow(header)
            logger.info(f"Initialized CSV '{output_csv_path}' with header.")

            # Loop through permutations
            for i, lineup_perm in enumerate(all_permutations):
                lineup_str = " ".join(lineup_perm)
                logger.info(f"\n--- Running Simulation {i+1}/{num_permutations} ---")
                logger.info(f"Lineup: {lineup_str}")

                # Construct command
                # Ensure python executable is correctly found (sys.executable is robust)
                # Add '--verbose False' and pass the '--output-dir'
                command = [
                    sys.executable, 'main.py',
                    '--lineup'] + list(lineup_perm) + [
                    '--verbose', 'False',
                    '--output-dir', run_output_dir # Pass the specific dir for this run
                ]
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
