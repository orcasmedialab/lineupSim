# src/player.py

import logging
import math # For checking isnan
from .constants import *

logger = logging.getLogger(__name__)

class Player:
    """Represents a player with their stats and calculated probabilities."""

    def __init__(self, player_id, name, stats):
        self.id = player_id
        self.name = name
        self.raw_stats = stats
        self.probabilities = {}
        self.extra_base_percentage = stats.get('extra_base_percentage', 0.0)
        self.gb_fb_ratio = stats.get('gb_fb_ratio', 1.0) # Default to 1 if missing
        self.prob_steal_attempt = 0.0 # Probability of attempting a steal per opportunity
        self.prob_steal_success = 0.0 # Probability of success given an attempt

        if self.gb_fb_ratio <= 0:
            logger.warning(f"Player {self.name} has non-positive GB/FB ratio ({self.gb_fb_ratio}). Setting to 1.0.")
            self.gb_fb_ratio = 1.0

        self._calculate_probabilities()

    def _calculate_probabilities(self):
        """Calculates the probability of each plate appearance outcome."""
        pa = self.raw_stats['plate_appearances']
        if pa <= 0:
            logger.warning(f"Player {self.name} has {pa} Plate Appearances. Setting all probabilities to 0.")
            for outcome in OUTCOMES:
                self.probabilities[outcome] = 0.0
            self.outcome_list = list(self.probabilities.keys())
            self.probability_weights = list(self.probabilities.values())
            # Also set steal probabilities to 0 if no PA
            self.prob_steal_attempt = 0.0
            self.prob_steal_success = 0.0
            return

        # --- Calculate PA Outcome Probabilities ---
        # Required stats for PA outcomes
        hits = self.raw_stats.get('hits', 0)
        doubles = self.raw_stats.get('doubles', 0)
        triples = self.raw_stats.get('triples', 0)
        home_runs = self.raw_stats.get('home_runs', 0)
        walks = self.raw_stats.get('walks', 0)
        hbp = self.raw_stats.get('hit_by_pitch', 0)
        so = self.raw_stats.get('strikeouts', 0)

        singles = hits - (doubles + triples + home_runs)
        if singles < 0:
            logger.warning(f"Player {self.name} has negative singles ({singles}). Clamping to 0.")
            singles = 0

        # Calculate probabilities based on Plate Appearances (PA)
        self.probabilities[WALK] = walks / pa
        self.probabilities[HIT_BY_PITCH] = hbp / pa
        # Check for missing keys needed for PA outcomes before division
        required_pa_keys = ['hits', 'doubles', 'triples', 'home_runs', 'walks', 'hit_by_pitch', 'strikeouts']
        missing_pa_keys = [k for k in required_pa_keys if k not in self.raw_stats]
        if missing_pa_keys:
            logger.warning(f"Player {self.name} missing required stats for PA calculation: {missing_pa_keys}. Some PA probabilities might be inaccurate.")
            # Ensure missing keys result in 0 counts for calculations below
            for k in missing_pa_keys:
                if k == 'hits': hits = 0
                if k == 'doubles': doubles = 0
                if k == 'triples': triples = 0
                if k == 'home_runs': home_runs = 0
                if k == 'walks': walks = 0
                if k == 'hit_by_pitch': hbp = 0
                if k == 'strikeouts': so = 0
            # Recalculate singles if hits was missing
            if 'hits' in missing_pa_keys:
                singles = 0 - (doubles + triples + home_runs)
                if singles < 0: singles = 0


        self.probabilities[STRIKEOUT] = so / pa
        self.probabilities[SINGLE] = singles / pa
        self.probabilities[DOUBLE] = doubles / pa
        self.probabilities[TRIPLE] = triples / pa
        self.probabilities[HOME_RUN] = home_runs / pa

        # Calculate probability of *any* out on a ball in play
        # Sum only the probabilities calculated so far
        current_probs = [self.probabilities.get(k, 0.0) for k in [WALK, HIT_BY_PITCH, STRIKEOUT, SINGLE, DOUBLE, TRIPLE, HOME_RUN]]
        prob_reached_base_or_so = sum(current_probs)
        prob_out_in_play = max(0.0, 1.0 - prob_reached_base_or_so) # Ensure non-negative

        # Distribute prob_out_in_play between GO and FO based on GB/FB ratio
        gb_weight = self.gb_fb_ratio
        fb_weight = 1.0
        total_bip_weight = gb_weight + fb_weight

        if total_bip_weight > 0:
            self.probabilities[GROUND_OUT] = prob_out_in_play * (gb_weight / total_bip_weight)
            self.probabilities[FLY_OUT] = prob_out_in_play * (fb_weight / total_bip_weight)
        else: # Should not happen with gb_fb_ratio > 0 check, but safety first
             self.probabilities[GROUND_OUT] = 0.0
             self.probabilities[FLY_OUT] = 0.0


        # --- Final check and potential normalization for PA outcomes ---
        # Ensure all defined PA outcomes have a probability
        for outcome in OUTCOMES:
             if outcome not in self.probabilities:
                 self.probabilities[outcome] = 0.0
             # Handle potential NaN from division by zero if pa was 0 but slipped through
             if math.isnan(self.probabilities[outcome]):
                 self.probabilities[outcome] = 0.0

        # Normalize PA outcome probabilities
        total_pa_prob = sum(self.probabilities.values())
        if abs(total_pa_prob - 1.0) > 0.01 and pa > 0: # Allow minor float inaccuracies if PA > 0
             logger.warning(f"PA outcome probabilities for {self.name} sum to {total_pa_prob:.4f}, not 1.0. Normalizing.")
             if total_pa_prob > 0:
                 factor = 1.0 / total_pa_prob
                 for outcome in self.probabilities:
                     self.probabilities[outcome] *= factor
             else: # If total_prob is 0 (e.g., PA=0), ensure all are 0
                 for outcome in self.probabilities:
                     self.probabilities[outcome] = 0.0
             # Ensure the largest probability takes any remaining difference due to float issues
             if pa > 0:
                 diff = 1.0 - sum(self.probabilities.values())
                 if abs(diff) > 1e-9: # Avoid adding tiny float differences if already normalized
                    max_prob_outcome = max(self.probabilities, key=self.probabilities.get)
                    self.probabilities[max_prob_outcome] += diff


        # Prepare lists for random.choices (PA outcomes)
        self.outcome_list = list(self.probabilities.keys())
        self.probability_weights = list(self.probabilities.values())

        # --- Calculate Stealing Probabilities ---
        sb = self.raw_stats.get('stolen_bases', 0)
        cs = self.raw_stats.get('caught_stealing', 0)

        # Check for missing keys needed for steal calculation
        required_steal_keys = ['hits', 'walks', 'hit_by_pitch', 'triples', 'home_runs', 'stolen_bases', 'caught_stealing']
        missing_steal_keys = [k for k in required_steal_keys if k not in self.raw_stats]
        if missing_steal_keys:
            logger.warning(f"Player {self.name} missing required stats for steal calculation: {missing_steal_keys}. Steal probabilities set to 0.")
            self.prob_steal_attempt = 0.0
            self.prob_steal_success = 0.0
        else:
            total_steal_attempts = sb + cs
            # Opportunities = Times reaching 1B/2B via Hit/BB/HBP
            # Hits = 1B + 2B + 3B + HR
            # Opportunities = (1B + 2B) + BB + HBP = (Hits - 3B - HR) + BB + HBP
            steal_opportunities = (hits - triples - home_runs) + walks + hbp

            if steal_opportunities > 0:
                self.prob_steal_attempt = total_steal_attempts / steal_opportunities
            else:
                self.prob_steal_attempt = 0.0 # Cannot attempt steal if never in position

            if total_steal_attempts > 0:
                self.prob_steal_success = sb / total_steal_attempts
            else:
                self.prob_steal_success = 0.0 # Cannot succeed if never attempted

            # Log calculated steal probabilities at debug level
            logger.debug(f"Player {self.name}: Steal Opps={steal_opportunities}, SB={sb}, CS={cs} -> P(Attempt)={self.prob_steal_attempt:.4f}, P(Success|Attempt)={self.prob_steal_success:.4f}")


    def get_probabilities(self):
        """Returns the dictionary of Plate Appearance outcome probabilities."""
        return self.probabilities

    def get_outcome_weights(self):
        """Returns outcomes and their corresponding weights for random.choices."""
        return self.outcome_list, self.probability_weights

    def __str__(self):
        return f"Player({self.id} - {self.name})"

    def __repr__(self):
        return f"Player({self.id})"
