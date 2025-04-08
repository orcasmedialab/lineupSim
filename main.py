# main.py

import logging
import argparse
import os
import sys
import csv # Import csv here if using the secondary append logic
from src.simulator import Simulator
from src.utils import setup_logging

CONFIG_FILE = os.path.join("data", "config.yaml")

def main():
    parser = argparse.ArgumentParser(description="Baseball Game Simulator")
    # Make --lineup optional, default to None
    parser.add_argument('--lineup', required=False, nargs='+', default=None,
                        help='List of 9 player IDs in batting order (e.g., P001 P002 ...). If omitted, uses order from config.yaml.')
    parser.add_argument('--csv', type=str, default=None,
                        help='Output CSV file path for average score. If provided, disables verbose YAML logging.')
    parser.add_argument('--verbose', action='store_true', default=None,
                        help='Enable detailed YAML logging (overridden by --csv)')
    parser.add_argument('--debug', action='store_true', help='Enable DEBUG level logging.')

    args = parser.parse_args()

    # Determine verbosity (same logic as before)
    if args.csv:
        verbose_mode = False
        if args.verbose is True:
             print("Warning: --csv argument provided, overriding --verbose flag. YAML output disabled.", file=sys.stderr)
    elif args.verbose is False:
        verbose_mode = False
    else:
         # Default to verbose if --csv is not present and --verbose wasn't explicitly False
         verbose_mode = True # Explicitly setting default behavior

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(level=log_level)
    logger = logging.getLogger(__name__)

    logger.info("Baseball Simulator Run Initializing...")
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
        simulator.run_simulations(lineup_ids=lineup_to_use, verbose=verbose_mode)

        # Handle output (same logic as before)
        if verbose_mode:
            simulator.save_results_yaml()
        else:
            avg_score = simulator.get_average_score()
            # Print average score to stdout for potential orchestrator capture
            print(f"{avg_score:.4f}", end='')

            # Optional CSV append (primarily for direct runs, orchestrator might handle differently)
            if args.csv:
                try:
                    file_exists = os.path.isfile(args.csv)
                    with open(args.csv, 'a', newline='') as f:
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
                        logger.info(f"Appended average score to {args.csv}")
                except IOError as e:
                    logger.error(f"Failed to append score to CSV {args.csv}: {e}")


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

