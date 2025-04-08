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
            return

        # Calculate derived stats
        hits = self.raw_stats['hits']
        doubles = self.raw_stats['doubles']
        triples = self.raw_stats['triples']
        home_runs = self.raw_stats['home_runs']
        singles = hits - (doubles + triples + home_runs)
        if singles < 0:
            logger.warning(f"Player {self.name} has negative singles ({singles}). Clamping to 0.")
            singles = 0

        walks = self.raw_stats['walks']
        hbp = self.raw_stats['hit_by_pitch']
        so = self.raw_stats['strikeouts']

        # Calculate probabilities based on Plate Appearances (PA)
        self.probabilities[WALK] = walks / pa
        self.probabilities[HIT_BY_PITCH] = hbp / pa
        self.probabilities[STRIKEOUT] = so / pa
        self.probabilities[SINGLE] = singles / pa
        self.probabilities[DOUBLE] = doubles / pa
        self.probabilities[TRIPLE] = triples / pa
        self.probabilities[HOME_RUN] = home_runs / pa

        # Calculate probability of *any* out on a ball in play
        prob_reached_base_or_so = sum(self.probabilities.values())
        prob_out_in_play = max(0.0, 1.0 - prob_reached_base_or_so) # Ensure non-negative

        # Distribute prob_out_in_play between GO and FO based on GB/FB ratio
        # P(GO) = P(OutInPlay) * (GB / (GB + FB)) = P(OutInPlay) * (Ratio / (Ratio + 1))
        # P(FO) = P(OutInPlay) * (FB / (GB + FB)) = P(OutInPlay) * (1 / (Ratio + 1))
        gb_weight = self.gb_fb_ratio
        fb_weight = 1.0
        total_weight = gb_weight + fb_weight

        if total_weight > 0:
            self.probabilities[GROUND_OUT] = prob_out_in_play * (gb_weight / total_weight)
            self.probabilities[FLY_OUT] = prob_out_in_play * (fb_weight / total_weight)
        else: # Should not happen with gb_fb_ratio > 0 check, but safety first
             self.probabilities[GROUND_OUT] = 0.0
             self.probabilities[FLY_OUT] = 0.0


        # --- Final check and potential normalization ---
        # Ensure all defined outcomes have a probability
        for outcome in OUTCOMES:
             if outcome not in self.probabilities:
                 self.probabilities[outcome] = 0.0
             # Handle potential NaN from division by zero if pa was 0 but sliped through
             if math.isnan(self.probabilities[outcome]):
                 self.probabilities[outcome] = 0.0


        total_prob = sum(self.probabilities.values())
        if abs(total_prob - 1.0) > 0.01 and pa > 0: # Allow minor float inaccuracies if PA > 0
             logger.warning(f"Probabilities for {self.name} sum to {total_prob:.4f}, not 1.0. Normalizing.")
             # Normalize
             if total_prob > 0:
                 factor = 1.0 / total_prob
                 for outcome in self.probabilities:
                     self.probabilities[outcome] *= factor
             else: # If total_prob is 0 (e.g., PA=0), ensure all are 0
                 for outcome in self.probabilities:
                     self.probabilities[outcome] = 0.0
             # Ensure the largest probability takes any remaining difference due to float issues
             if pa > 0:
                 diff = 1.0 - sum(self.probabilities.values())
                 max_prob_outcome = max(self.probabilities, key=self.probabilities.get)
                 self.probabilities[max_prob_outcome] += diff


        # Prepare lists for random.choices
        self.outcome_list = list(self.probabilities.keys())
        self.probability_weights = list(self.probabilities.values())

    def get_probabilities(self):
        return self.probabilities

    def get_outcome_weights(self):
        """Returns outcomes and their corresponding weights for random.choices."""
        return self.outcome_list, self.probability_weights

    def __str__(self):
        return f"Player({self.id} - {self.name})"

    def __repr__(self):
        return f"Player({self.id})"