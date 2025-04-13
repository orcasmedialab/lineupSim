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
            # --- Announce Batter ---
            batter = self.lineup[self.current_batter_index]
            outs_before_pa = self.outs
            bases_before_pa_announcement = list(self.bases) # State before steals/PA
            self.log_event(f"\nBatter: {batter.name} ({batter.id}), Outs: {outs_before_pa}, Bases: {self._get_base_runners_str(bases_before_pa_announcement)}", level=logging.INFO)

            # --- Check for Steals DURING Plate Appearance (after announcement) ---
            # Iterate through bases that could have steal attempts (1st, 2nd)
            # Process 2nd base first to avoid advancing a runner from 1st then checking them again at 2nd in same step
            for base_index in [SECOND_BASE, FIRST_BASE]:
                runner = self.bases[base_index]
                if runner and self.outs < 3: # Check if runner exists and inning isn't over
                    target_base = base_index + 1
                    # Check if target base is open (no stealing into an occupied base)
                    # Note: No stealing home (target_base == HOME_PLATE)
                    if target_base < HOME_PLATE and self.bases[target_base] is None:
                        # Check steal attempt probability
                        if random.random() < runner.prob_steal_attempt:
                            # Attempting steal
                            if random.random() < runner.prob_steal_success:
                                # Successful Steal (SB)
                                self.log_event(f"STEAL: {runner.name} steals {target_base + 1}B!", level=logging.INFO)
                                self.bases[target_base] = runner
                                self.bases[base_index] = None # Vacate original base
                            else:
                                # Caught Stealing (CS)
                                self.outs += 1
                                self.log_event(f"CAUGHT STEALING: {runner.name} caught stealing {target_base + 1}B. Outs: {self.outs}", level=logging.INFO)
                                self.bases[base_index] = None # Runner is out
                                # Check if this was the 3rd out
                                if self.outs >= 3:
                                    self.log_event(f"Inning ends on caught stealing.", level=logging.DEBUG)
                                    break # Exit steal check loop for this PA

            # If inning ended on CS, continue to end the inning processing below
            if self.outs >= 3:
                 self.log_event(f"--- End of Inning {self.inning} --- Outs: {self.outs}, Score: {self.score}", level=logging.INFO)
                 break # Break main while loop

            # --- Simulate PA Outcome ---
            # Use the base state *before* steals for process_outcome logic (DP/FC setup)
            outcome = self.simulate_plate_appearance(batter)
            self.log_event(f"PA Outcome: {outcome}", level=logging.INFO)

            # --- Process Outcome: Determine Outs and Immediate Placement ---
            # Modifies self.outs and potentially self.bases (if runner out on DP/FC)
            # Returns True if the batter reached safely on an FC where a runner was out.
            batter_safe_on_fc = self.process_outcome(batter, outcome, bases_before_pa_announcement)

            # --- Handle Baserunning ---
            # Uses the base state *after* steals and *after* process_outcome removed any outed runners.
            if self.outs < 3: # Only advance runners if inning is not over
                 self.handle_baserunning(batter, outcome, list(self.bases), outs_before_pa, batter_safe_on_fc)
            else:
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
        Returns True if the batter is safe due to a Fielder's Choice where a runner was out, False otherwise.
        Does NOT handle runner advancement for hits/walks or non-out runners.
        """
        batter_safe_on_fc = False # Initialize return value
        runners_on_before_pa = [i for i, player in enumerate(bases_before_pa) if player is not None]
        num_runners_on = len(runners_on_before_pa)

        if outcome == STRIKEOUT:
            self.outs += 1
            self.log_event(f"{batter.name} strikes out.", level=logging.INFO)
        elif outcome == WALK or outcome == HIT_BY_PITCH:
            # No outs on these unless weird scenario (not modeled)
            self.log_event(f"{batter.name} draws a {outcome}.", level=logging.INFO)
            pass
        elif outcome in [SINGLE, DOUBLE, TRIPLE, HOME_RUN]:
            # No outs on these unless baserunning mistake (not modeled)
            self.log_event(f"{batter.name} hits a {outcome}!", level=logging.INFO)
            pass
        elif outcome == FLY_OUT:
            self.outs += 1
            self.log_event(f"{batter.name} flies out.", level=logging.INFO)
        elif outcome == GROUND_OUT:
            # --- Ground Out Logic: Check for DP, FC, or standard GO ---
            is_dp = False
            is_fc = False

            # Determine if a force play exists at 2B, 3B based on runners_on_before_pa
            force_at_2b = (FIRST_BASE in runners_on_before_pa)
            force_at_3b = (FIRST_BASE in runners_on_before_pa and SECOND_BASE in runners_on_before_pa)
            is_force_possible = force_at_2b or force_at_3b # A force exists if 1B is occupied

            # Check for Double Play potential first (requires force and < 2 outs)
            if self.outs < 2 and is_force_possible:
                 dp_prob = self.sim_params.get('dp_attempt_probability_on_go', 0.0)
                 if random.random() < dp_prob:
                    is_dp = True
                    # Important: Only increment outs here, removal happens in handle_baserunning
                    # based on the final state after DP resolution.
                    # However, we need to decide *which* runner is out *now* to mark them.
                    self.outs += 2
                    self.log_event(f"{batter.name} grounds into a double play!", level=logging.INFO)
                    self.log_event(f" -> Batter {batter.name} is out.", level=logging.DEBUG) # Batter always out

                    # Choose which runner is out
                    possible_runners_out = []
                    if force_at_2b: possible_runners_out.append(FIRST_BASE)
                    if force_at_3b: possible_runners_out.append(SECOND_BASE)

                    if possible_runners_out:
                        weights_map = self.sim_params.get('double_play_runner_out_weights', {})
                        runner_weights = [weights_map.get(idx, 1) for idx in possible_runners_out]

                        if sum(runner_weights) > 0:
                             runner_out_idx = random.choices(possible_runners_out, weights=runner_weights, k=1)[0]
                             runner_out_player = bases_before_pa[runner_out_idx]
                             self.log_event(f" -> Runner {runner_out_player.name} ({runner_out_player.id}) is out attempting to advance.", level=logging.DEBUG)
                             self.bases[runner_out_idx] = None # Mark runner as out *now*
                        else:
                            logger.warning("DP occurred but runner weights summed to zero. Randomly choosing forced runner out.")
                            runner_out_idx = random.choice(possible_runners_out)
                            runner_out_player = bases_before_pa[runner_out_idx]
                            self.log_event(f" -> Runner {runner_out_player.name} ({runner_out_player.id}) (randomly chosen) is out attempting to advance.", level=logging.DEBUG)
                            self.bases[runner_out_idx] = None
                    else:
                         logger.error("DP logic error: Force possible but no runners identified.")
                         self.outs -=1 # Revert one out

            # Fielder's Choice (if not a DP and a force play was possible)
            elif self.outs < 3 and is_force_possible:
                 is_fc = True
                 self.outs += 1
                 self.log_event(f"{batter.name} grounds into a fielder's choice.", level=logging.INFO)

                 # Determine who is out (batter or one of the runners involved in the force)
                 fc_options = {BATTER_INDEX: batter}
                 if force_at_2b: fc_options[FIRST_BASE] = bases_before_pa[FIRST_BASE]
                 if force_at_3b: fc_options[SECOND_BASE] = bases_before_pa[SECOND_BASE]

                 option_indices = list(fc_options.keys())
                 weights_map = self.sim_params.get('fielders_choice_out_weights', {})
                 option_weights = [weights_map.get(idx, 1) for idx in option_indices]

                 out_player_idx = BATTER_INDEX
                 if sum(option_weights) > 0:
                      out_player_idx = random.choices(option_indices, weights=option_weights, k=1)[0]
                 else:
                      logger.warning("FC weights summed to zero or options invalid. Randomly choosing player out from options.")
                      if option_indices: out_player_idx = random.choice(option_indices)
                      else: logger.error("FC logic error: No options to choose from."); self.outs -= 1; is_fc = False

                 if is_fc:
                     out_player = fc_options[out_player_idx]
                     self.log_event(f" -> {out_player.name} ({out_player.id}) is out.", level=logging.DEBUG)
                     if out_player_idx != BATTER_INDEX:
                          self.bases[out_player_idx] = None # Mark runner as out *now*
                          batter_safe_on_fc = True # Batter is safe

            # Standard Ground Out (only if not DP and no force was possible)
            elif not is_dp and not is_force_possible:
                 self.outs += 1
                 self.log_event(f"{batter.name} grounds out.", level=logging.INFO)

        return batter_safe_on_fc


    def handle_baserunning(self, batter, outcome, current_bases_state, outs_before_pa, batter_safe_on_fc):
        """
        Handles advancement of runners AND the batter (if not out).
        Calculates runs scored, respecting the 3rd out rule.
        Uses the current base state (after steals, after outs from process_outcome) as the starting point.
        Updates self.bases and self.score.
        """
        current_outs = self.outs # Use current outs count
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
            # Batter is safe *only* if process_outcome determined it was an FC where a runner was out
            if batter_safe_on_fc:
                 batter_target_base = FIRST_BASE
                 batter_is_safe = True
            # Otherwise, batter is out (batter_is_safe remains False)

        # --- Create combined list/dict of runners to process (including batter if safe) ---
        # Use the current_bases_state passed into the function (reflects steals and outs from process_outcome)
        runners_to_process = {}
        for i, runner in enumerate(current_bases_state):
            if runner is not None: # Include all runners currently on base
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
            took_extra_base = False # Reset XBP flag for each runner

            # --- Determine Base Advancement ---
            if is_batter:
                advance_amount = batter_target_base - start_base_idx # e.g., 1B (0) - Batter (-1) = 1 base
            else: # Runner on base
                # Check for Force Plays
                batter_causes_force = batter_is_safe and (outcome in [WALK, HIT_BY_PITCH, SINGLE] or (outcome == GROUND_OUT and batter_safe_on_fc))
                if batter_causes_force:
                    # Determine if *this specific runner* is forced
                    is_forced = True # Assume forced
                    check_base = start_base_idx - 1
                    while check_base >= BATTER_INDEX:
                        # Check if the base is occupied *now* (in runners_to_process)
                        occupying_runner = runners_to_process.get(check_base, None)
                        if occupying_runner is None:
                            is_forced = False
                            break
                        check_base -= 1

                if is_forced:
                    advance_amount = 1 # Standard force advance is 1 base
                else:
                    # --- Non-Forced Advancement Rules ---
                    standard_advance = 0
                    if outcome == SINGLE: standard_advance = 1
                    elif outcome == DOUBLE: standard_advance = 2
                    elif outcome == TRIPLE: standard_advance = 3
                    elif outcome == HOME_RUN: standard_advance = 4 # Score
                    elif outcome == FLY_OUT:
                         # Tagging up (Sac Fly or standard tag)
                         if current_outs < 3: # Can only advance if not 3rd out
                             if start_base_idx == THIRD_BASE: # Sac Fly
                                 standard_advance = 1 # Scores
                             else: # Tagging from 1st or 2nd
                                 if random.random() < runner.extra_base_percentage:
                                      standard_advance = 1
                                      took_extra_base = True # Indicate tag up advance
                    elif outcome == GROUND_OUT: # Includes FC survivors, DP survivors
                         # Non-forced runners on ground outs generally hold unless XBP dictates otherwise
                         if current_outs < 3:
                             if random.random() < runner.extra_base_percentage:
                                  standard_advance = 1
                                  took_extra_base = True # Indicate advance on contact

                    advance_amount = standard_advance

                    # XBP Check for non-forced runners on Singles/Doubles
                    # Only apply if runner wouldn't score automatically with standard advance
                    potential_target_std = start_base_idx + standard_advance
                    if potential_target_std < HOME_PLATE:
                        # Apply XBP check only if not forced and outcome allows potential extra base
                        if not is_forced and outcome in [SINGLE, DOUBLE]:
                             if random.random() < runner.extra_base_percentage:
                                 advance_amount += 1
                                 took_extra_base = True
                        # Note: took_extra_base flag is already set for tag-up/contact advances above

            # --- Calculate Target Base and Handle Placement/Scoring ---
            target_base = start_base_idx + advance_amount
            runner_placed = False # Track if runner was successfully placed
            log_suffix = " (XB)" if took_extra_base else "" # Suffix for logging extra bases

            if target_base >= HOME_PLATE: # Score
                if current_outs < 3:
                    runs_scored_this_play += 1
                    # Log score, include Sac Fly note if applicable
                    sac_fly_note = " on Sac Fly" if outcome == FLY_OUT and start_base_idx == THIRD_BASE else ""
                    # Don't log batter scoring separately if HR
                    if not (is_batter and outcome == HOME_RUN):
                        self.log_event(f"RUN SCORES: {runner.name} scores{sac_fly_note}. Score: {self.score + runs_scored_this_play}", level=logging.INFO)
                    runner_placed = True # Considered 'placed' by scoring
                else:
                    # Don't log batter not scoring on HR after 3rd out
                    if not (is_batter and outcome == HOME_RUN):
                        self.log_event(f"Runner {runner.name} crosses plate, but after 3rd out. No run.", level=logging.DEBUG)
                    runner_placed = True # Still 'handled', just didn't score

            elif target_base >= FIRST_BASE: # Advance to 1B, 2B, or 3B
                 # Do not log batter advancement here, only runners
                 log_advancement = not is_batter

                 if new_bases[target_base] is None:
                     new_bases[target_base] = runner
                     # Only log advancement for non-batters
                     if log_advancement: self.log_event(f"Runner {runner.name} advances to {target_base + 1}B{log_suffix}.", level=logging.DEBUG)
                     runner_placed = True
                 else:
                     # Base occupied by lead runner, hold up at base behind it
                     fallback_base = target_base - 1
                     # Check fallback base
                     if fallback_base >= FIRST_BASE and new_bases[fallback_base] is None:
                         new_bases[fallback_base] = runner
                         if log_advancement: self.log_event(f"Runner {runner.name} held up by lead runner, stops at {fallback_base + 1}B.", level=logging.DEBUG)
                         runner_placed = True
                     else:
                         # Fallback also occupied or invalid? Blocked. Stay put if possible.
                         if start_base_idx >= FIRST_BASE and new_bases[start_base_idx] is None:
                             new_bases[start_base_idx] = runner
                             if log_advancement: self.log_event(f"Runner {runner.name} blocked ahead, retreats/holds at {start_base_idx + 1}B.", level=logging.DEBUG)
                             runner_placed = True
                         else: # Cannot stay at original base either
                             if log_advancement: logger.warning(f"Runner {runner.name} blocked at {target_base+1}B and fallback/original. Cannot place runner cleanly.")
                             runner_placed = True # Handled (by being removed implicitly)

            # If runner didn't advance (target_base == start_base_idx) and wasn't placed yet
            if not runner_placed and target_base == start_base_idx and start_base_idx >= FIRST_BASE:
                 # Ensure they stay on their original base if it's still available in new_bases
                 if new_bases[start_base_idx] is None:
                     new_bases[start_base_idx] = runner
                     # Only log hold if not the batter
                     if log_advancement: self.log_event(f"Runner {runner.name} holds at {start_base_idx + 1}B.", level=logging.DEBUG)
                     runner_placed = True
                 # else: Original base now occupied by trailing runner? Should be rare. Log if happens.
                 elif new_bases[start_base_idx] != runner and log_advancement:
                      logger.warning(f"Runner {runner.name} held position {start_base_idx+1}B, but it was taken by {new_bases[start_base_idx].id}. State issue?")
                      runner_placed = True # Implicitly removed

            # If runner was batter and wasn't placed (e.g., out or blocked)
            if not runner_placed and is_batter:
                 # Batter was out or couldn't be placed, already handled/logged.
                 pass

        # --- Update Game State ---
        self.bases = new_bases
        self.score += runs_scored_this_play


    def _get_base_runners_str(self, bases_to_use):
        """Helper to get a string representation of base runners from a given base list."""
        base_strs = []
        # Iterate in order 1B, 2B, 3B
        if bases_to_use[FIRST_BASE]:
            base_strs.append(f"1B: {bases_to_use[FIRST_BASE].id}")
        if bases_to_use[SECOND_BASE]:
            base_strs.append(f"2B: {bases_to_use[SECOND_BASE].id}")
        if bases_to_use[THIRD_BASE]:
            base_strs.append(f"3B: {bases_to_use[THIRD_BASE].id}")
        return ", ".join(base_strs) if base_strs else "Bases empty"
