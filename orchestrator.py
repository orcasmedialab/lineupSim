# orchestrator.py

import itertools
import subprocess
import yaml
import os
import sys
import csv
import logging
import datetime
import argparse
from math import factorial
import pandas as pd # Added for reading/sorting CSV
from src.utils import setup_logging

CONFIG_FILE = os.path.join("data", "config.yaml")
RESULTS_BASE_DIR = "results"

def load_config_and_players(config_path):
    """Loads main config, orchestrator params, and player IDs."""
    logger = logging.getLogger("Orchestrator")
    logger.info(f"Loading main configuration from: {config_path}")
    try:
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        player_file_path = config_data.get('player_data_file')
        if not player_file_path:
            raise ValueError("Main config file must specify 'player_data_file'.")

        sim_params = config_data.get('simulation_params', {})
        orch_params = config_data.get('orchestrator_params', {}) # Load orchestrator params

        logger.info(f"Loading player IDs from player data file: {player_file_path}")
        with open(player_file_path, 'r') as f_players:
            player_config = yaml.safe_load(f_players)
        roster_data = player_config.get('players', [])
        if not roster_data:
            raise ValueError(f"Player data file {player_file_path} must contain a 'players' list.")

        player_ids = [player['id'] for player in roster_data]
        if len(player_ids) != 9:
            raise ValueError(f"Expected 9 players in player data file '{player_file_path}', found {len(player_ids)}")
        if len(player_ids) != len(set(player_ids)):
             raise ValueError(f"Duplicate player IDs found in player data file '{player_file_path}'.")

        logger.info(f"Successfully loaded {len(player_ids)} player IDs.")
        return sim_params, orch_params, player_ids

    except FileNotFoundError as e:
        if 'config_data' not in locals(): logger.error(f"Main configuration file not found at {config_path}")
        else: logger.error(f"Player data file not found at {player_file_path}")
        raise
    except yaml.YAMLError as e:
        if 'player_config' not in locals(): logger.error(f"Error parsing main config YAML {config_path}: {e}")
        else: logger.error(f"Error parsing player data YAML {player_file_path}: {e}")
        raise
    except KeyError as e:
        logger.error(f"Could not find expected key ('player_data_file', 'simulation_params', 'orchestrator_params' in config or 'id'/'players' in player file): {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading config/players: {e}")
        raise


def run_simulation_for_lineup(lineup_perm, num_games, run_output_dir):
    """Runs main.py for a single lineup and returns the average score."""
    logger = logging.getLogger("Orchestrator")
    lineup_str = " ".join(lineup_perm)
    command = [
        sys.executable, 'main.py',
        '--lineup'] + list(lineup_perm) + [
        '--verbose', 'False', # Keep main.py non-verbose for stdout capture
        '--output-dir', run_output_dir, # Pass the specific dir for this run
        '--num-games', str(num_games) # Use specified number of games
    ]
    logger.debug(f"Executing command: {' '.join(command)}")
    try:
        process = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        avg_score_str = process.stdout.strip()
        avg_score = float(avg_score_str)
        logger.debug(f"Lineup {lineup_str} -> Avg Score: {avg_score:.4f}")
        return avg_score
    except subprocess.CalledProcessError as e:
        logger.error(f"!!! Error running main.py for lineup: {lineup_perm} !!!")
        logger.error(f"Return Code: {e.returncode}")
        logger.error(f"Stdout:\n{e.stdout}")
        logger.error(f"Stderr:\n{e.stderr}")
        raise # Re-raise the exception to be handled by the caller
    except ValueError:
        logger.error(f"Could not convert stdout ('{avg_score_str}') to float for lineup {lineup_perm}.")
        logger.error(f"Subprocess stderr:\n{process.stderr}")
        raise # Re-raise the exception


def main():
    parser = argparse.ArgumentParser(description="Run baseball simulations for lineup permutations and optionally rerun top performers.")
    parser.add_argument('--start', type=int, default=0, help='Starting index (0-based) of permutations to simulate.')
    parser.add_argument('--stop', type=int, default=None, help='Stopping index (exclusive) of permutations to simulate. If None, simulates to the end.')
    parser.add_argument('--num-games', type=int, default=None, help='Override the number of games per lineup for the INITIAL run (from config.yaml).')
    parser.add_argument('--debug', action='store_true', help='Enable DEBUG level logging.')
    # New --rerun argument: Takes 2 integer values
    parser.add_argument('--rerun', type=int, nargs=2, metavar=('TOP_N', 'NUM_GAMES'), default=None,
                        help='Manually trigger a rerun for the TOP_N lineups using NUM_GAMES simulations each. Overrides config auto_rerun settings.')

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(level=log_level)
    logger = logging.getLogger("Orchestrator")

    logger.info("Starting Lineup Permutation Simulation Orchestrator...")
    logger.debug(f"Orchestrator Args: {args}")

    try:
        sim_params, orch_params, player_ids = load_config_and_players(CONFIG_FILE)
        logger.info(f"Loaded Player IDs: {player_ids}")
    except Exception as e:
        logger.error(f"Failed to load configuration or player IDs: {e}. Exiting.")
        sys.exit(1)

    # --- Determine Number of Games for Initial Run ---
    initial_num_games = args.num_games if args.num_games is not None else sim_params.get('num_games', 162)
    logger.info(f"Initial simulation run will use {initial_num_games} games per lineup.")

    # --- Create Timestamped Output Directory ---
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_output_dir = os.path.join(RESULTS_BASE_DIR, timestamp)
    try:
        os.makedirs(run_output_dir, exist_ok=True)
        logger.info(f"Created results directory: {run_output_dir}")
    except OSError as e:
        logger.error(f"Failed to create results directory {run_output_dir}: {e}")
        sys.exit(1)

    # --- Initial Permutation Simulation ---
    initial_csv_filename = f"{initial_num_games}_game_results.csv"
    initial_csv_path = os.path.join(run_output_dir, initial_csv_filename)
    logger.info(f"Initial results CSV will be saved to: {initial_csv_path}")

    logger.info("Generating lineup permutations for initial run...")
    all_permutations_generator = itertools.permutations(player_ids)
    total_possible_perms = factorial(len(player_ids))
    logger.info(f"Total possible permutations: {total_possible_perms}")

    start_index = args.start
    stop_index = args.stop if args.stop is not None else total_possible_perms

    if not (0 <= start_index < total_possible_perms):
        logger.error(f"Invalid start index {start_index}. Must be between 0 and {total_possible_perms - 1}.")
        sys.exit(1)
    if not (start_index < stop_index <= total_possible_perms):
         logger.error(f"Invalid stop index {stop_index}. Must be > start ({start_index}) and <= {total_possible_perms}.")
         sys.exit(1)

    permutations_to_run = list(itertools.islice(all_permutations_generator, start_index, stop_index))
    num_permutations_in_slice = len(permutations_to_run)
    logger.info(f"Selected permutations from index {start_index} to {stop_index} (exclusive). Total to simulate: {num_permutations_in_slice}")

    initial_run_successful = False
    try:
        with open(initial_csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            header = [f"P{i+1}_ID" for i in range(9)] + ["AverageScore"]
            writer.writerow(header)
            logger.info(f"Initialized CSV '{initial_csv_path}' with header.")

            for i, lineup_perm in enumerate(permutations_to_run):
                absolute_index = start_index + i
                logger.info(f"\n--- Running Initial Sim {i+1}/{num_permutations_in_slice} (Abs Index: {absolute_index}, Games: {initial_num_games}) ---")
                logger.info(f"Lineup: {' '.join(lineup_perm)}")

                try:
                    avg_score = run_simulation_for_lineup(lineup_perm, initial_num_games, run_output_dir)
                    logger.info(f"Simulation successful. Average Score: {avg_score:.4f}")
                    row = list(lineup_perm) + [f"{avg_score:.4f}"]
                    writer.writerow(row)
                    f.flush()
                except (subprocess.CalledProcessError, ValueError):
                    logger.error(f"Failed simulation for lineup {lineup_perm}. Stopping orchestrator.")
                    sys.exit(1) # Stop if any simulation fails

            logger.info(f"\n--- Initial Simulation Run Complete ---")
            logger.info(f"Results summary saved to '{initial_csv_path}'")
            initial_run_successful = True

    except IOError as e:
        logger.error(f"Failed to write to initial CSV file {initial_csv_path}: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"An unexpected error occurred during initial simulation run: {e}")
        sys.exit(1)

    # --- Auto-Rerun Logic ---
    if not initial_run_successful:
        logger.warning("Initial simulation run did not complete successfully. Skipping rerun.")
        sys.exit(1)

    # Determine if rerun is needed and get parameters
    rerun_enabled = False
    rerun_top_n = 0
    rerun_num_games = 0

    if args.rerun:
        rerun_enabled = True
        rerun_top_n = args.rerun[0]
        rerun_num_games = args.rerun[1]
        logger.info(f"Manual rerun triggered via --rerun flag: Top {rerun_top_n} lineups, {rerun_num_games} games each.")
    elif orch_params.get('auto_rerun', False):
        rerun_enabled = True
        rerun_top_n = orch_params.get('rerun_top_n', 10) # Default from config if missing
        rerun_num_games = orch_params.get('rerun_num_games', 1000) # Default from config if missing
        logger.info(f"Automatic rerun enabled via config: Top {rerun_top_n} lineups, {rerun_num_games} games each.")
    else:
        logger.info("Rerun not enabled via config or command line flag.")

    if rerun_enabled:
        if rerun_top_n <= 0 or rerun_num_games <= 0:
            logger.error(f"Invalid rerun parameters: TOP_N ({rerun_top_n}) and NUM_GAMES ({rerun_num_games}) must be positive.")
            sys.exit(1)

        logger.info(f"\n--- Starting Rerun Phase ---")
        rerun_csv_filename = f"{rerun_num_games}_game_results.csv"
        rerun_csv_path = os.path.join(run_output_dir, rerun_csv_filename)
        logger.info(f"Rerun results will be saved to: {rerun_csv_path}")

        try:
            # Read the initial results CSV
            logger.info(f"Reading initial results from: {initial_csv_path}")
            df = pd.read_csv(initial_csv_path)

            # Sort by AverageScore (descending) and get top N lineups
            top_lineups_df = df.sort_values(by='AverageScore', ascending=False).head(rerun_top_n)
            logger.info(f"Identified Top {len(top_lineups_df)} lineups for rerun:")
            for idx, row in top_lineups_df.iterrows():
                 lineup_ids = tuple(row[f'P{i+1}_ID'] for i in range(9))
                 logger.debug(f"  Rank {idx+1}: {lineup_ids} (Score: {row['AverageScore']:.4f})")


            # Run simulations for the top lineups
            with open(rerun_csv_path, 'w', newline='') as f_rerun:
                writer_rerun = csv.writer(f_rerun)
                header = [f"P{i+1}_ID" for i in range(9)] + ["AverageScore"]
                writer_rerun.writerow(header)
                logger.info(f"Initialized Rerun CSV '{rerun_csv_path}' with header.")

                for i, (index, row) in enumerate(top_lineups_df.iterrows()):
                    lineup_perm = tuple(row[f'P{j+1}_ID'] for j in range(9)) # Extract lineup tuple
                    logger.info(f"\n--- Running Rerun Sim {i+1}/{len(top_lineups_df)} (Games: {rerun_num_games}) ---")
                    logger.info(f"Lineup: {' '.join(lineup_perm)}")

                    try:
                        avg_score = run_simulation_for_lineup(lineup_perm, rerun_num_games, run_output_dir)
                        logger.info(f"Rerun simulation successful. Average Score: {avg_score:.4f}")
                        result_row = list(lineup_perm) + [f"{avg_score:.4f}"]
                        writer_rerun.writerow(result_row)
                        f_rerun.flush()
                    except (subprocess.CalledProcessError, ValueError):
                        logger.error(f"Failed rerun simulation for lineup {lineup_perm}. Stopping orchestrator.")
                        # Optionally, decide if one failure should stop the whole rerun
                        sys.exit(1) # Stop if any rerun simulation fails

            logger.info(f"\n--- Rerun Phase Complete ---")
            logger.info(f"Rerun results saved to '{rerun_csv_path}'")

        except FileNotFoundError:
            logger.error(f"Initial results file not found at {initial_csv_path}. Cannot perform rerun.")
            sys.exit(1)
        except pd.errors.EmptyDataError:
             logger.error(f"Initial results file {initial_csv_path} is empty. Cannot perform rerun.")
             sys.exit(1)
        except KeyError as e:
             logger.error(f"Missing expected column in {initial_csv_path} (e.g., 'AverageScore' or 'P*_ID'): {e}. Cannot perform rerun.")
             sys.exit(1)
        except IOError as e:
            logger.error(f"Failed to write to rerun CSV file {rerun_csv_path}: {e}")
            sys.exit(1)
        except Exception as e:
            logger.exception(f"An unexpected error occurred during the rerun phase: {e}")
            sys.exit(1)

    logger.info("\nOrchestrator finished.")


if __name__ == "__main__":
    main()
