# main.py

import logging
import argparse
import os
import sys
import csv
import datetime # Added for timestamp
from src.simulator import Simulator
from src.utils import setup_logging

CONFIG_FILE = os.path.join("data", "config.yaml")
RESULTS_BASE_DIR = "results" # Consistent base directory

def main():
    parser = argparse.ArgumentParser(description="Baseball Game Simulator")
    # Make --lineup optional, default to None
    parser.add_argument('--lineup', required=False, nargs='+', default=None,
                        help='List of 9 player IDs in batting order (e.g., P001 P002 ...). If omitted, uses order from config.yaml.')
    parser.add_argument('--csv', type=str, default=None,
                        help='Output CSV file path for average score. If provided, disables verbose YAML logging.')
    # Changed verbose argument: removed action='store_true', allows string/bool interpretation
    parser.add_argument('--verbose', default=None,
                        help='Enable detailed YAML logging (e.g., --verbose True or --verbose False). Overridden by --csv unless --save-yaml is also used.')
    parser.add_argument('--debug', action='store_true', help='Enable DEBUG level logging for all modules.')
    # New flags
    parser.add_argument('--show-game-logs', action='store_true',
                        help='Show detailed play-by-play logs from the game simulation on stderr.')
    parser.add_argument('--save-yaml', action='store_true',
                        help='Force saving the detailed YAML log file, even when using --csv.')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='Specify the output directory for results (used internally by orchestrator).')
    parser.add_argument('--num-games', type=int, default=None,
                        help='Override the number of games to simulate per lineup (from config.yaml).')

    args = parser.parse_args()

    # --- Determine Output Directory ---
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") # Timestamp for potential filenames
    if args.output_dir:
        # Use the directory provided by the orchestrator
        run_output_dir = args.output_dir
        # Ensure the orchestrator-provided directory exists (it should, but safety check)
        os.makedirs(run_output_dir, exist_ok=True)
    else:
        # Direct run: Use the base results directory
        run_output_dir = RESULTS_BASE_DIR
        os.makedirs(run_output_dir, exist_ok=True) # Ensure base results directory exists

    # Determine verbosity more robustly
    if args.csv:
        verbose_mode = False
        # Log warning only if user explicitly tried to enable verbose with csv
        if args.verbose is not None and str(args.verbose).lower() == 'true':
             logger.warning("Warning: --csv argument provided, overriding --verbose flag. YAML output disabled.")
    elif args.verbose is not None and str(args.verbose).lower() == 'false':
        # Handles --verbose False, --verbose false, etc. passed from orchestrator or user
        verbose_mode = False
    else:
        # Default to verbose if --csv is not present and --verbose wasn't explicitly 'false'
        # This covers cases where --verbose is None or --verbose is 'True'/'true'/etc.
         # Default to verbose if --csv is not present and --verbose wasn't explicitly 'false'
         # This covers cases where --verbose is None or --verbose is 'True'/'true'/etc.
         verbose_mode = True

    # Setup logging - Default level is WARNING (from utils)
    # Set root logger level based on --debug
    root_log_level = logging.DEBUG if args.debug else logging.WARNING
    setup_logging(level=root_log_level) # Setup root logger

    # Get the main logger for this script
    logger = logging.getLogger(__name__)

    # Log directory info now that logger is available
    logger.info(f"Using output directory: {run_output_dir}")

    # Specifically set game logger level if requested
    if args.show_game_logs:
        logging.getLogger('src.game').setLevel(logging.INFO)
        logger.info("Showing detailed game logs (INFO level for src.game).")
    elif not args.debug: # If not showing game logs and not debugging, ensure game logger is also WARNING
         logging.getLogger('src.game').setLevel(logging.WARNING)


    logger.info("Baseball Simulator Run Initializing...") # This will only show if root level is INFO/DEBUG
    logger.debug(f"Command line args: {args}")

    try:
        # Instantiate Simulator first, as we might need it for the default lineup
        simulator = Simulator(config_path=CONFIG_FILE)

        # Determine the lineup to use
        if args.lineup:
            lineup_to_use = args.lineup
            logger.info(f"Using lineup order from command line arguments: {' '.join(lineup_to_use)}")
        else:
            logger.info("No --lineup argument provided. Using default order from config.yaml.")
            try:
                lineup_to_use = simulator.get_default_lineup_ids()
                logger.info(f"Default lineup order: {' '.join(lineup_to_use)}")
            except Exception as e:
                 logger.error(f"Failed to get default lineup from config: {e}")
                 sys.exit(1) # Exit if default lineup cannot be determined


        logger.info(f"Verbose Logging: {verbose_mode}")
        if args.csv:
            logger.info(f"CSV Output Path: {args.csv}")

        # Run simulations for the determined lineup
        # The validate_lineup method inside run_simulations will check the final lineup_to_use
        # Pass the calculated verbose_mode and potential num_games override
        # Note: verbose_mode now primarily controls the *default* YAML saving behavior
        simulator.run_simulations(
            lineup_ids=lineup_to_use,
            verbose=verbose_mode,
            num_games_override=args.num_games # Pass the override value
        )

        # --- Handle Output ---
        avg_score = simulator.get_average_score()

        # Determine if YAML should be saved
        # Save YAML if explicitly requested OR if running verbosely by default (not csv, not --verbose False)
        save_yaml_output = args.save_yaml or verbose_mode
        # Determine if score should be printed to stdout (for orchestrator)
        # Print score ONLY if YAML is NOT being saved by default (i.e., csv mode or --verbose False)
        # AND YAML wasn't explicitly forced with --save-yaml
        print_score_to_stdout = not verbose_mode and not args.save_yaml

        # --- Save YAML ---
        if save_yaml_output:
            # Generate timestamped YAML filename
            yaml_filename = f"simulation_results_{timestamp}.yaml"
            yaml_path = os.path.join(run_output_dir, yaml_filename)
            logger.info(f"Saving results to YAML file: {yaml_path}") # Use INFO level
            # Pass directory and filename to simulator method (needs update)
            simulator.save_results_yaml(output_path=yaml_path) # Pass full path

        # --- Print Score to Stdout (for Orchestrator) ---
        if print_score_to_stdout:
            # Print average score to stdout for potential orchestrator capture
            print(f"{avg_score:.4f}", end='')
            # Log score printing only at DEBUG level to avoid noise when orchestrator runs
            logger.debug(f"Printed average score to stdout: {avg_score:.4f}")


        # --- Append Score to CSV ---
        if args.csv:
            # Use the determined run_output_dir (results/ for direct, results/timestamp/ for orchestrator)
            csv_filename = args.csv # Keep the user-provided filename part
            csv_path = os.path.join(run_output_dir, csv_filename)
            logger.info(f"Attempting to append score to CSV: {csv_path}") # This will only show if root level is INFO/DEBUG
            try:
                file_exists = os.path.isfile(csv_path)
                # Ensure directory exists (redundant if created above, but safe)
                os.makedirs(os.path.dirname(csv_path), exist_ok=True)
                with open(csv_path, 'a', newline='') as f:
                    writer = csv.writer(f)
                    # Add header if file is new and we are appending directly
                    # Note: If run via orchestrator, header should be handled there.
                    # This header logic is mainly for direct main.py runs with --csv.
                    # if not file_exists:
                    #     header = [f"P{i+1}_ID" for i in range(9)] + ["AverageScore"]
                    #     writer.writerow(header)

                    # Format: Player1, Player2, ..., Player9, AvgScore
                    row = list(lineup_to_use) + [f"{avg_score:.4f}"]
                    writer.writerow(row)
                    logger.info(f"Appended average score to {csv_path}") # This will only show if root level is INFO/DEBUG
            except IOError as e:
                logger.error(f"Failed to append score to CSV {csv_path}: {e}")


        logger.info("Baseball Simulator Run Finished.")

    except FileNotFoundError:
        logger.error(f"Fatal Error: Cannot find configuration file at {CONFIG_FILE}. Exiting.")
        sys.exit(1)
    except ValueError as e:
         # Catch errors from Simulator init, get_default_lineup_ids, or validate_lineup
         logger.error(f"Fatal Error: Configuration, Lineup, or Validation error - {e}. Exiting.")
         sys.exit(1)
    except Exception as e:
        logger.exception(f"An unexpected fatal error occurred during simulation run: {e}") # Log traceback
        sys.exit(1)

if __name__ == "__main__":
    main()
