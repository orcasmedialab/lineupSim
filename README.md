
# Python Baseball Simulator

This project simulates baseball games for a single team based on detailed player statistics provided in a YAML configuration file. It allows for simulating individual seasons for specific lineups or running experiments across all possible lineup permutations.

## Features

*   Simulates games inning by inning for a 9-player lineup.
*   Calculates plate appearance outcome probabilities (1B, 2B, 3B, HR, BB, HBP, SO, Ground Out, Fly Out) based on input stats.
*   Distinguishes between Ground Outs (GO) and Fly Outs (FO) based on player GB/FB ratios.
*   Models complex baserunning scenarios:
    *   Forced advances.
    *   Double Plays (DP): Configurable attempt probability on GO, batter always out, weighted random choice for runner out.
    *   Fielder's Choice (FC): Weighted random choice for who is out (batter or runner) on single-out GOs with runners on.
    *   Sacrifice Flies: Runner on 3rd scores on FO if < 2 outs.
    *   Extra Base Advancement: Runners attempt extra bases on hits (Singles/Doubles), tagging up on Fly Outs, or advancing on Ground Outs based on their `extra_base_percentage` and base traffic.
    *   Base Traffic: Runners are held up if the base ahead is occupied.
    *   Third Out Rule: No runs score on plays where the third out is recorded.
*   Uses unique Player IDs for lineup management.
*   Simulates a configurable number of games per run (defined in `config.yaml`).
*   Flexible output options:
    *   **Verbose Mode:** Logs detailed play-by-play for each simulated game to a YAML file (`logs/simulation_results.yaml` by default).
    *   **CSV Mode:** Logs only the average score for the simulated games, appending a row to a specified CSV file. Ideal for large-scale experiments. Automatically disables verbose YAML logging.
*   Supports running simulations for:
    *   A specific lineup order provided via command-line arguments.
    *   The default lineup order defined in `config.yaml` if no specific order is provided.
*   Includes an orchestrator script (`orchestrator.py`) to automatically simulate all 9! (362,880) possible lineup permutations and aggregate results into a summary CSV file.

## Directory Structure


baseball_simulator/
├── data/ # Input configuration files
│ └── config.yaml
├── logs/ # Output log files (YAML format in verbose mode)
├── src/ # Source code
│ ├── init.py
│ ├── constants.py
│ ├── player.py
│ ├── game.py
│ ├── simulator.py
│ └── utils.py
├── main.py # Main execution script for single lineup simulations
├── orchestrator.py # Script to run simulations for all lineup permutations
├── requirements.txt # Python dependencies
├── all_lineup_results.csv # Example output file from orchestrator.py
└── README.md # This file

## Setup

1.  **Create a virtual environment (optional but recommended):**
    ```bash
    python -m venv venv
    # On Windows PowerShell: .\venv\Scripts\Activate.ps1
    # On Windows Cmd.exe: venv\Scripts\activate.bat
    # On Linux/macOS: source venv/bin/activate
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration (`data/config.yaml`)

*   Edit `data/config.yaml` to define:
    *   `simulation_params`:
        *   `num_games`: Number of games to simulate *per lineup execution*.
        *   `innings_per_game`: Typically 9.
        *   `verbose`: Default logging mode (`True` for YAML, `False` otherwise). Overridden if `--csv` is used in `main.py`.
        *   `output_log_file`: Filename for YAML log in verbose mode.
        *   `dp_attempt_probability_on_go`: Chance a GO with runner(s) on and < 2 outs becomes a DP attempt.
        *   `double_play_runner_out_weights`: Relative weights for which *runner* (on 1B, 2B, or 3B) is the second out in a DP. Keys are base indices (0, 1, 2).
        *   `fielders_choice_out_weights`: Relative weights for who is out (Batter = -1, Runner on 1B = 0, etc.) on an FC.
    *   `lineup`: **Acts as a player pool.** A list of 9 players, each with:
        *   `id`: Unique alphanumeric player identifier (e.g., "P001").
        *   `name`: Player's display name.
        *   `stats`: Dictionary including required metrics (`plate_appearances`, `at_bats`, `hits`, `doubles`, `triples`, `home_runs`, `walks`, `strikeouts`, `hit_by_pitch`, `extra_base_percentage`, `gb_fb_ratio`, etc.). The order in this list defines the *default* lineup if `main.py` is run without the `--lineup` argument.

## Usage

There are two primary ways to run simulations:

### 1. Running Single Simulations (`main.py`)

Use `main.py` to simulate games for one specific lineup order (either provided via arguments or default from config) and get detailed logs or a specific output value.

**Arguments:**

*   `--lineup ID1 ID2 ... ID9` (Optional): Specify the 9 player IDs in the desired batting order. If omitted, the order from `config.yaml` is used.
*   `--csv FILEPATH.csv` (Optional): Output the average score for the run to the specified CSV file (appends if file exists). Disables verbose YAML logging. If omitted, defaults to verbose YAML logging unless `--verbose` is explicitly set to false (or similar).
*   `--verbose` (Optional Flag): Force detailed YAML logging. Ignored if `--csv` is used.
*   `--debug` (Optional Flag): Enable DEBUG level console logging for troubleshooting.

**Examples:**

*   **Simulate using default lineup order (from config) with verbose YAML output:**
    ```bash
    python main.py
    ```
    (Output will be in `logs/simulation_results.yaml`)

*   **Simulate a specific lineup with verbose YAML output:**
    ```bash
    python main.py --lineup P003 P001 P004 P002 P006 P005 P007 P008 P009
    ```
    (Output will be in `logs/simulation_results.yaml`)

*   **Simulate the default lineup and append average score to a CSV:**
    ```bash
    python main.py --csv my_sim_results.csv
    ```
    (A row with the default lineup IDs and average score will be appended to `my_sim_results.csv`. No YAML log generated. Average score also printed to console.)

*   **Simulate a specific lineup and append average score to a CSV:**
    ```bash
    python main.py --lineup P001 P002 P003 P004 P005 P006 P007 P008 P009 --csv lineup_test.csv
    ```
    (A row with this lineup's IDs and average score appended to `lineup_test.csv`. No YAML log generated. Average score also printed to console.)

### 2. Running All Permutations (`orchestrator.py`)

Use `orchestrator.py` to automatically run simulations for *all possible* 9! (362,880) batting order permutations using the players defined in `config.yaml`. This is useful for finding the optimal lineup based on average runs scored over a season.

**How it works:**

*   Reads player IDs from `config.yaml`.
*   Generates every permutation of those 9 IDs.
*   For each permutation:
    *   Calls `main.py --lineup ID1 ... ID9` as a subprocess. `main.py` runs in non-verbose mode.
    *   Captures the average score printed to standard output by `main.py`.
    *   Writes the lineup permutation and its average score to `all_lineup_results.csv`.
*   Logs progress to the console.
*   Writes a final row with the grand total runs scored across all simulations.

**To Run:**

```bash
python orchestrator.py
```


**Output:**

*   Results are saved in `all_lineup_results.csv` (or overwritten if it exists).

*   Console output shows progress for each lineup simulation.

**WARNING**: Running the orchestrator script will **take a very long** time as it simulates 362,880 * `num_games` (e.g., nearly 59 million games if `num_games` is 162). Ensure `num_games` in `config.yaml` is set appropriately for your testing needs. Consider reducing it significantly for initial tests.

## Notes & Future Improvements

*   This simulation focuses solely on the batting team's performance. Opposing pitching and defense are not dynamically factored in beyond the assumed league-average outcomes reflected in the input player stats.

*   Baserunning logic, while enhanced, still simplifies some situations (e.g., no explicit modeling of runner speed differences beyond XBP, basic DP trigger logic, no hit-and-run, no simulation of SB/CS attempts during play).

Does not model errors explicitly.

Could be extended to include pitching stats, fielding variations, more granular baserunning decisions, weather effects, park factors, etc.

Consider using `multiprocessing` within `orchestrator.py` to significantly speed up the permutation testing on multi-core machines.
