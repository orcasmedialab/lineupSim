# src/game.py

import random
import logging
from .player import Player # Keep this if Player class is in the same directory structure
from .constants import *

logger = logging.getLogger(__name__)

class Game:
    """Simulates a single baseball game for one team."""

    def __init__(self, game_id, lineup_players, lineup_ids, innings_per_game, sim_params):
        self.game_id = game_id
        self.lineup = lineup_players # List of Player objects in order
        self.lineup_ids = lineup_ids # List of string IDs in order
        self.innings_per_game = innings_per_game
        self.sim_params = sim_params # Store config params here

        # Game State
        self.current_batter_index = 0
        self.score = 0
        self.inning = 1
        self.outs = 0
        self.bases = [None] * 3 # Index 0=1B, 1=2B, 2=3B; stores Player object
        self.game_log = [] # Stores play-by-play if verbose logging is enabled

    def log_event(self, message, level=logging.INFO):
        """Adds an event to the game log IF verbose logging is enabled."""
        # Use debug level for very frequent logs like base state
        if self.sim_params.get('verbose', True):
            self.game_log.append(message)
        # Always log INFO level or higher to console logger regardless of verbosity
        if level >= logger.getEffectiveLevel():
             logger.log(level, message)


    def run_game(self):
        """Simulates the entire game inning by inning."""
        self.log_event(f"--- Starting Game {self.game_id} --- Lineup: {', '.join(self.lineup_ids)}", level=logging.INFO)
        while self.inning <= self.innings_per_game:
            self.play_inning()
            # Check for walk-off win? Not applicable for single team sim.
            self.inning += 1
        self.log_event(f"--- Game {self.game_id} Over --- Final Score: {self.score}", level=logging.INFO)
        # Return score and log (log will be empty if not verbose)
        return {"game_id": self.game_id, "final_score": self.score, "log": self.game_log}

    def play_inning(self):
        """Simulates a single inning."""
        self.outs = 0
        self.bases = [None] * 3 # Clear bases
        self.log_event(f"\n--- Inning {self.inning} --- Score: {self.score}, Outs: {self.outs}", level=logging.INFO)

        while self.outs < 3:
            batter = self.lineup[self.current_batter_index]
            outs_before_pa = self.outs
            # Store base state BEFORE the play resolves for calculations
            bases_before_pa = list(self.bases) # Shallow copy is fine

            self.log_event(f"\nBatter: {batter.name} ({batter.id}), Outs: {outs_before_pa}, Bases: {self._get_base_runners_str(bases_before_pa)}", level=logging.DEBUG)

            outcome = self.simulate_plate_appearance(batter)
            self.log_event(f"Outcome: {outcome}", level=logging.DEBUG)

            # --- Process Outcome: Determine Outs and Immediate Placement ---
            # This section determines WHO is out and increments self.outs
            # It does NOT handle advancing runners yet.
            self.process_outcome(batter, outcome, bases_before_pa)

            # --- Handle Baserunning ---
            # This section advances runners based on the outcome and outs
            # Ensures no runs score on 3rd out of inning.
            if self.outs < 3: # Only advance runners if inning is not over
                 self.handle_baserunning(batter, outcome, bases_before_pa, outs_before_pa)
            else:
                 # If the play resulted in the 3rd out (or more), ensure no trailing runners score
                 self.log_event("Inning ends on the play.", level=logging.DEBUG)


            # Log state AFTER baserunning resolves
            self.log_event(f"End of PA: Outs: {self.outs}, Score: {self.score}, Bases: {self._get_base_runners_str(self.bases)}", level=logging.DEBUG)

            # Advance batter index
            self.current_batter_index = (self.current_batter_index + 1) % len(self.lineup)

            # Check for inning end (redundant with loop condition but safe)
            if self.outs >= 3:
                 self.log_event(f"--- End of Inning {self.inning} --- Outs: {self.outs}, Score: {self.score}", level=logging.INFO)
                 break

    def simulate_plate_appearance(self, batter):
        """Determines the outcome of a single plate appearance."""
        outcomes, weights = batter.get_outcome_weights()
        # Ensure weights sum is positive before choosing
        if sum(weights) <= 0:
             logger.warning(f"Player {batter.name} has zero total probability weight. Defaulting to SO.")
             # Find SO outcome or fallback
             default_outcome = STRIKEOUT if STRIKEOUT in outcomes else outcomes[0] if outcomes else None
             return default_outcome # Should ideally not happen if PA > 0

        chosen_outcome = random.choices(outcomes, weights=weights, k=1)[0]
        return chosen_outcome

    def process_outcome(self, batter, outcome, bases_before_pa):
        """
        Determines outs, updates self.outs, handles immediate batter/runner removal for outs.
        Does NOT handle runner advancement for hits/walks or non-out runners.
        """
        runners_on_before_pa = [i for i, player in enumerate(bases_before_pa) if player is not None]
        num_runners_on = len(runners_on_before_pa)

        if outcome == STRIKEOUT:
            self.outs += 1
            self.log_event(f"{batter.name} strikes out.", level=logging.INFO)
        elif outcome == WALK or outcome == HIT_BY_PITCH:
            # No outs on these unless weird scenario (not modeled)
            self.log_event(f"{batter.name} draws a {outcome}.", level=logging.INFO)
            # Batter placement and runner advancement handled in handle_baserunning
            pass
        elif outcome in [SINGLE, DOUBLE, TRIPLE, HOME_RUN]:
            # No outs on these unless baserunning mistake (not modeled)
            self.log_event(f"{batter.name} hits a {outcome}!", level=logging.INFO)
            # Batter placement and runner advancement handled in handle_baserunning
            pass
        elif outcome == FLY_OUT:
            self.outs += 1
            self.log_event(f"{batter.name} flies out.", level=logging.INFO)
            # Runner advancement (tagging) handled in handle_baserunning
        elif outcome == GROUND_OUT:
            # --- Ground Out Logic: Check for DP, FC, or standard GO ---
            is_dp = False
            is_fc = False

            # Check for Double Play potential
            if self.outs < 2 and num_runners_on > 0:
                 dp_prob = self.sim_params.get('dp_attempt_probability_on_go', 0.0)
                 if random.random() < dp_prob:
                    is_dp = True
                    self.outs += 2
                    self.log_event(f"{batter.name} grounds into a double play!", level=logging.INFO)
                    # Batter is always out in our DP model
                    self.log_event(f" -> Batter {batter.name} is out.", level=logging.DEBUG)

                    # Choose which runner is out
                    possible_runners_out = [idx for idx in runners_on_before_pa] # Base indices 0, 1, 2
                    if possible_runners_out:
                        weights_map = self.sim_params.get('double_play_runner_out_weights', {})
                        runner_weights = [weights_map.get(idx, 1) for idx in possible_runners_out] # Default weight 1 if base not in config

                        if sum(runner_weights) > 0:
                             runner_out_idx = random.choices(possible_runners_out, weights=runner_weights, k=1)[0]
                             runner_out_player = bases_before_pa[runner_out_idx]
                             self.log_event(f" -> Runner {runner_out_player.name} ({runner_out_player.id}) is out at base {runner_out_idx + 1}.", level=logging.DEBUG)
                             # Remove the runner from the current state immediately
                             self.bases[runner_out_idx] = None
                        else:
                            logger.warning("DP occurred but runner weights summed to zero. Randomly choosing runner out.")
                            runner_out_idx = random.choice(possible_runners_out)
                            runner_out_player = bases_before_pa[runner_out_idx]
                            self.log_event(f" -> Runner {runner_out_player.name} ({runner_out_player.id}) (randomly chosen) is out at base {runner_out_idx + 1}.", level=logging.DEBUG)
                            self.bases[runner_out_idx] = None
                    else:
                        # This case (DP with no runners) shouldn't happen based on check above, but safety
                        logger.warning("DP attempt logic triggered with no runners on base.")
                        self.outs -= 1 # Correct outs back to 1 if DP was wrongly assumed


            # Check for Fielder's Choice (if not a DP and runners were on)
            elif self.outs < 3 and num_runners_on > 0:
                 is_fc = True
                 self.outs += 1
                 self.log_event(f"{batter.name} grounds into a fielder's choice.", level=logging.INFO)

                 # Determine who is out (batter or one of the runners)
                 fc_options = {BATTER_INDEX: batter} # Batter is index -1
                 for idx in runners_on_before_pa:
                     fc_options[idx] = bases_before_pa[idx]

                 option_indices = list(fc_options.keys())
                 weights_map = self.sim_params.get('fielders_choice_out_weights', {})
                 option_weights = [weights_map.get(idx, 1) for idx in option_indices]

                 if sum(option_weights) > 0:
                      out_player_idx = random.choices(option_indices, weights=option_weights, k=1)[0]
                 else:
                      logger.warning("FC weights summed to zero. Randomly choosing player out.")
                      out_player_idx = random.choice(option_indices)

                 out_player = fc_options[out_player_idx]
                 self.log_event(f" -> {out_player.name} ({out_player.id}) is out.", level=logging.DEBUG)

                 if out_player_idx != BATTER_INDEX: # A runner was out
                      # Remove the runner immediately
                      self.bases[out_player_idx] = None
                      # Batter is safe on FC, placed later in handle_baserunning
                 # else: Batter was out, handled implicitly (no placement later)

            # Standard Ground Out (no runners, or after DP/FC resolved)
            if not is_dp and not is_fc:
                 self.outs += 1
                 self.log_event(f"{batter.name} grounds out.", level=logging.INFO)


    def handle_baserunning(self, batter, outcome, bases_before_pa, outs_before_pa):
        """
        Handles advancement of runners AND the batter (if not out).
        Calculates runs scored, respecting the 3rd out rule.
        Uses the state *before* the play (bases_before_pa) as starting point.
        Updates self.bases and self.score.
        """
        current_outs = self.outs # Outs *after* process_outcome finished
        runs_scored_this_play = 0
        new_bases = [None] * 3 # Represents the target state AFTER advancement

        # --- Determine Batter's target base (if not out) ---
        batter_target_base = -1 # Assume out initially
        batter_is_safe = False # Flag if batter reached base safely

        if outcome == WALK or outcome == HIT_BY_PITCH:
            batter_target_base = FIRST_BASE
            batter_is_safe = True
        elif outcome == SINGLE:
            batter_target_base = FIRST_BASE
            batter_is_safe = True
        elif outcome == DOUBLE:
            batter_target_base = SECOND_BASE
            batter_is_safe = True
        elif outcome == TRIPLE:
            batter_target_base = THIRD_BASE
            batter_is_safe = True
        elif outcome == HOME_RUN:
            batter_target_base = HOME_PLATE # Will score
            batter_is_safe = True # Scored
        elif outcome == GROUND_OUT:
            # Batter might be safe *only* on a Fielder's Choice where a runner was out
            # Need to reconstruct if FC occurred and batter wasn't chosen
            # Check if outs increased by only 1 and runners were on
            outs_this_play = current_outs - outs_before_pa
            if outs_this_play == 1 and any(p is not None for p in bases_before_pa):
                # Was the batter the one chosen in FC? We need to know that...
                # This is tricky. Let's modify process_outcome slightly?
                # Or assume if outs==1 and runners were on GO, it *was* FC and batter is safe *unless* process_outcome logged batter out.
                # Simplification: Let's assume the log tells the story. If FC logged and batter wasn't logged out, batter is safe.
                # This requires careful log reading or a better state passing mechanism.
                # SAFER: Re-evaluate the FC choice logic based on who is *missing* from self.bases now vs bases_before_pa.
                is_fc_where_runner_out = False
                if any(p is not None for p in bases_before_pa) and outs_this_play == 1:
                     # Check if a runner who was on bases_before_pa is now missing from self.bases
                     runner_out_on_fc = None
                     for idx, p_before in enumerate(bases_before_pa):
                         if p_before is not None and self.bases[idx] is None:
                             # Found a runner removed during process_outcome
                             runner_out_on_fc = p_before
                             break
                     if runner_out_on_fc:
                         is_fc_where_runner_out = True

                if is_fc_where_runner_out:
                    batter_target_base = FIRST_BASE
                    batter_is_safe = True


        # --- Create combined list/dict of runners to process (including batter if safe) ---
        # Use a dictionary: {start_base_index: player} -> {-1: batter, 0: runner_on_1st, ...}
        runners_to_process = {}
        for i, runner in enumerate(bases_before_pa):
            # Include only runners who were NOT outed by process_outcome
            if runner is not None and self.bases[i] is not None:
                 runners_to_process[i] = runner
        if batter_is_safe:
            runners_to_process[BATTER_INDEX] = batter # -1 is batter's "start base"

        # --- Process runners from lead base downwards ---
        sorted_start_bases = sorted(runners_to_process.keys(), reverse=True) # e.g., [2, 1, 0, -1]

        for start_base_idx in sorted_start_bases:
            runner = runners_to_process[start_base_idx]
            is_batter = (start_base_idx == BATTER_INDEX)
            advance_amount = 0
            is_forced = False

            # --- Determine Base Advancement ---
            if is_batter:
                advance_amount = batter_target_base - start_base_idx # e.g., 1B (0) - Batter (-1) = 1 base
            else: # Runner on base
                # Check for Force Plays
                # Forced if all bases between runner and batter (inclusive) were occupied *before* the play
                # AND the batter reached base safely (or walked/HBP).
                is_forced = False
                if batter_is_safe and (outcome == WALK or outcome == HIT_BY_PITCH or outcome == SINGLE): # Only these force runners typically
                    force_check_base = start_base_idx - 1
                    is_forced = True # Assume forced unless a gap is found
                    while force_check_base >= BATTER_INDEX:
                        if force_check_base not in runners_to_process:
                             # Check if the base was occupied *before* the PA, even if runner out on FC/DP
                             if bases_before_pa[force_check_base] is None:
                                is_forced = False
                                break
                        force_check_base -= 1


                if is_forced:
                    advance_amount = 1 # Standard force advance is 1 base
                    self.log_event(f"Runner {runner.name} is forced to advance.", level=logging.DEBUG)
                else:
                    # --- Non-Forced Advancement Rules ---
                    if outcome in [SINGLE, DOUBLE, TRIPLE, HOME_RUN]:
                         # Standard advance based on hit type for non-forced runners
                         if outcome == SINGLE: advance_amount = 1
                         elif outcome == DOUBLE: advance_amount = 2
                         elif outcome == TRIPLE: advance_amount = 3
                         elif outcome == HOME_RUN: advance_amount = 4 # Score

                         # XBP Check for Singles/Doubles (discretionary extra base)
                         if (outcome == SINGLE or outcome == DOUBLE):
                              if random.random() < runner.extra_base_percentage:
                                  self.log_event(f"Runner {runner.name} takes extra base on {outcome} (XBP).", level=logging.DEBUG)
                                  advance_amount += 1
                    elif outcome == FLY_OUT:
                         # Tagging up
                         if start_base_idx == THIRD_BASE and current_outs < 3: # Sac Fly condition
                             self.log_event(f"Runner {runner.name} tags up from 3rd on fly out (Sac Fly).", level=logging.INFO)
                             advance_amount = 1 # Scores
                         elif current_outs < 3: # Tagging from 1st or 2nd
                             if random.random() < runner.extra_base_percentage:
                                  self.log_event(f"Runner {runner.name} tags up and advances on fly out (XBP).", level=logging.DEBUG)
                                  advance_amount = 1
                             else:
                                  self.log_event(f"Runner {runner.name} holds on fly out.", level=logging.DEBUG)
                                  advance_amount = 0
                         else: # 3rd out made on the catch
                              advance_amount = 0
                    elif outcome == GROUND_OUT:
                         # Non-forced runners on ground outs (inc. DP survivors, FC survivors)
                         if current_outs < 3:
                             if random.random() < runner.extra_base_percentage:
                                  self.log_event(f"Runner {runner.name} advances on ground out (XBP).", level=logging.DEBUG)
                                  advance_amount = 1
                             else:
                                  self.log_event(f"Runner {runner.name} holds on ground out.", level=logging.DEBUG)
                                  advance_amount = 0
                         else: # 3rd out made on the play
                              advance_amount = 0
                    # Default: No advance on SO, Walk, HBP if not forced
                    else:
                         advance_amount = 0

            # --- Calculate Target Base and Handle Placement/Scoring ---
            target_base = start_base_idx + advance_amount

            if target_base >= HOME_PLATE: # Score
                # **** CRITICAL: Check if this run scores before the 3rd out ****
                if current_outs < 3:
                    runs_scored_this_play += 1
                    self.log_event(f"Run scores! {runner.name} crosses the plate. Score now {self.score + runs_scored_this_play}.", level=logging.INFO)
                    # Don't place runner on a base
                else:
                    self.log_event(f"Runner {runner.name} crosses plate, but after 3rd out. No run.", level=logging.DEBUG)
            elif target_base >= FIRST_BASE: # Place on 1B, 2B, or 3B
                 if new_bases[target_base] is None:
                     new_bases[target_base] = runner
                 else:
                     # Base occupied by lead runner, hold up at base behind
                     fallback_base = target_base - 1
                     if fallback_base >= FIRST_BASE:
                         if new_bases[fallback_base] is None:
                             new_bases[fallback_base] = runner
                             self.log_event(f"Runner {runner.name} held up, stops at {fallback_base + 1}B.", level=logging.DEBUG)
                         else:
                             # Fallback also occupied? Stay put? Log warning.
                             # If original base is available, stay there.
                             if start_base_idx >= FIRST_BASE and new_bases[start_base_idx] is None:
                                 new_bases[start_base_idx] = runner
                                 self.log_event(f"Runner {runner.name} blocked, retreats/holds at {start_base_idx + 1}B.", level=logging.DEBUG)
                             else:
                                 logger.warning(f"Runner {runner.name} blocked at {target_base+1}B and fallback {fallback_base+1}B. Cannot place runner cleanly.")
                                 # Runner effectively disappears in this simple model if truly blocked
                     elif start_base_idx >= FIRST_BASE and new_bases[start_base_idx] is None:
                         # Cannot advance (target was 1B, fallback is 0), stay at start if possible
                         new_bases[start_base_idx] = runner
                         self.log_event(f"Runner {runner.name} cannot advance from {start_base_idx+1}B, stays.", level=logging.DEBUG)
                     else:
                         logger.warning(f"Runner {runner.name} from {start_base_idx+1}B blocked at {target_base+1}B, cannot retreat/stay. Base state issue?")
            # else: target_base < 0, runner doesn't reach base (shouldn't happen for safe runners)

        # --- Update Game State ---
        self.bases = new_bases
        self.score += runs_scored_this_play


    def _get_base_runners_str(self, bases_to_use):
        """Helper to get a string representation of base runners from a given base list."""
        base_strs = []
        if bases_to_use[THIRD_BASE]:
            base_strs.append(f"3B: {bases_to_use[THIRD_BASE].id}")
        if bases_to_use[SECOND_BASE]:
            base_strs.append(f"2B: {bases_to_use[SECOND_BASE].id}")
        if bases_to_use[FIRST_BASE]:
            base_strs.append(f"1B: {bases_to_use[FIRST_BASE].id}")
        return ", ".join(base_strs) if base_strs else "Bases empty"