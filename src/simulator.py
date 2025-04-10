# src/simulator.py

import yaml
import os
import logging
import csv # For CSV writing
from .player import Player
from .game import Game

logger = logging.getLogger(__name__)

class Simulator:
    """Manages running multiple game simulations and saving results."""

    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.simulation_params = self.config['simulation_params']
        # Load players into a dictionary keyed by ID
        self.player_pool = self._load_players()
        self.results = [] # Stores game results (full log if verbose, just score otherwise)
        self.average_score = 0.0 # Store average score for non-verbose runs

    def _load_config(self, config_path):
        """Loads the YAML configuration file."""
        logger.info(f"Loading configuration from: {config_path}")
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            logger.info("Configuration loaded successfully.")
            return config_data
        except FileNotFoundError:
            logger.error(f"Error: Configuration file not found at {config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred loading config: {e}")
            raise

    def _load_players(self):
        """Creates Player objects from the config, stores in a dict by ID."""
        players = {}
        roster_data = self.config.get('lineup', []) # It's really a roster pool now
        if not roster_data:
             logger.error("No lineup/roster found in configuration file.")
             raise ValueError("Configuration must contain a 'lineup' section.")

        for player_data in roster_data:
            try:
                player_id = player_data['id']
                player = Player(player_id, player_data['name'], player_data['stats'])
                if player_id in players:
                    logger.warning(f"Duplicate player ID '{player_id}' found. Overwriting.")
                players[player_id] = player
                logger.debug(f"Loaded player: {player.id} - {player.name}")
            except KeyError as e:
                logger.error(f"Missing key {e} in player data: {player_data}")
                raise
        logger.info(f"Successfully loaded {len(players)} players into pool.")
        return players

    def validate_lineup(self, lineup_ids):
        """Checks if the provided lineup IDs are valid and form a 9-player lineup."""
        if len(lineup_ids) != 9:
            raise ValueError(f"Invalid lineup: Must contain exactly 9 player IDs, found {len(lineup_ids)}.")

        unknown_ids = [p_id for p_id in lineup_ids if p_id not in self.player_pool]
        if unknown_ids:
            raise ValueError(f"Invalid lineup: Unknown player IDs found: {', '.join(unknown_ids)}")

        # Check for duplicate IDs in the requested lineup
        if len(lineup_ids) != len(set(lineup_ids)):
             raise ValueError(f"Invalid lineup: Duplicate player IDs found in requested order: {lineup_ids}")

        logger.info("Provided lineup IDs validated successfully.")
        return True


    def run_simulations(self, lineup_ids, verbose):
        """
        Runs the configured number of game simulations for a specific lineup order.
        """
        self.simulation_params['verbose'] = verbose # Update internal verbose state

        # Validate and create the ordered list of Player objects
        self.validate_lineup(lineup_ids)
        ordered_lineup = [self.player_pool[p_id] for p_id in lineup_ids]

        num_games = self.simulation_params.get('num_games', 1) # Games per lineup run
        innings_per_game = self.simulation_params.get('innings_per_game', 9)
        logger.info(f"Starting simulation of {num_games} game(s) for lineup: {', '.join(lineup_ids)}...")

        total_score = 0
        self.results = [] # Clear results from previous runs

        for i in range(num_games):
            game_id = i + 1
            # Pass sim_params to Game for access to weights etc.
            game = Game(game_id=game_id,
                        lineup_players=ordered_lineup,
                        lineup_ids=lineup_ids,
                        innings_per_game=innings_per_game,
                        sim_params=self.simulation_params) # Pass params down

            game_result = game.run_game()
            self.results.append(game_result) # Store result (contains log only if verbose)
            total_score += game_result['final_score']
            # Reduce console noise when not verbose
            if verbose:
                logger.info(f"Game {game_id} finished. Score: {game_result['final_score']}")
            elif (i + 1) % (num_games // 10 if num_games >= 10 else 1) == 0: # Progress update for non-verbose
                 logger.info(f"Simulated game {i+1}/{num_games}...")


        self.average_score = total_score / num_games if num_games > 0 else 0.0
        logger.info(f"Simulation finished for lineup. Average Score: {self.average_score:.2f}")

    def save_results_yaml(self, output_path):
        """Saves the detailed simulation results to the specified YAML file path."""
        # output_dir = "logs" # No longer needed
        # output_filename = self.simulation_params.get('output_log_file', 'simulation_results.yaml') # Filename is now passed in path
        # output_path = os.path.join(output_dir, output_filename) # Path is now passed directly
        # os.makedirs(output_dir, exist_ok=True) # Directory creation handled in main.py

        # Ensure the directory for the output path exists (safety check)
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        except OSError as e:
             logger.error(f"Error ensuring directory exists for {output_path}: {e}")
             # Optionally, re-raise or return to indicate failure
             return # Exit the save function if directory cannot be confirmed

        logger.debug(f"Attempting to save detailed simulation results (YAML) to: {output_path}")
        output_data = {
            "simulation_summary": {
                "num_games_simulated": len(self.results),
                "innings_per_game": self.simulation_params.get('innings_per_game', 9),
                "average_score": self.average_score,
                "lineup_order": self.results[0]['log'][0].split("Lineup: ")[1] if self.results and self.results[0]['log'] else "N/A" # Extract from log
            },
            "game_details": self.results # List of individual game logs and scores
        }
        try:
            with open(output_path, 'w') as f:
                yaml.dump(output_data, f, default_flow_style=False, sort_keys=False, indent=2)
            logger.info("YAML Results saved successfully.")
        except IOError as e:
            logger.error(f"Error writing YAML results to file {output_path}: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred saving YAML results: {e}")

    def get_average_score(self):
        """Returns the calculated average score for the last simulation run."""
        return self.average_score
    
    def get_default_lineup_ids(self):
        """
        Retrieves the player IDs in the order they appear in the config file.
        """
        logger.debug("Fetching default lineup order from config file.")
        try:
            roster_data = self.config.get('lineup', [])
            if not roster_data:
                raise ValueError("Cannot determine default lineup: 'lineup' section is missing or empty in config.")

            default_ids = [player['id'] for player in roster_data]

            if len(default_ids) != 9:
                 logger.warning(f"Default lineup extracted from config has {len(default_ids)} players, expected 9.")
                 # Decide if this should be a hard error or just a warning
                 # Raising an error is safer if the rest of the logic expects 9 players
                 raise ValueError(f"Default lineup from config must have exactly 9 players, found {len(default_ids)}.")
            if len(default_ids) != len(set(default_ids)):
                raise ValueError("Duplicate player IDs found in the default lineup order in the config file.")

            logger.debug(f"Default lineup IDs: {default_ids}")
            return default_ids
        except KeyError as e:
            logger.error(f"Missing 'id' key for a player in config 'lineup' section while getting default order.")
            raise ValueError(f"Configuration error: Missing 'id' key in lineup data: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred getting default lineup order: {e}")
            raise # Re-raise other exceptions
