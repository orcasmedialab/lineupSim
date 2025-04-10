
# Python Baseball Simulator

This project simulates baseball games for a single team based on detailed player statistics provided in a YAML configuration file. It allows for simulating individual seasons for specific lineups or running experiments across all possible lineup permutations.

## Features

*   Simulates games inning by inning for a 9-player lineup.
*   Calculates Plate Appearance outcome probabilities (1B, 2B, 3B, HR, BB, HBP, SO, Ground Out, Fly Out) based on input stats.
*   Distinguishes between Ground Outs (GO) and Fly Outs (FO) based on player GB/FB ratios.
*   Models complex baserunning scenarios, including Forced Advances, Double Plays (DP), Fielder's Choice (FC), Sacrifice Flies, Extra Base Advancement, Base Traffic
*   Simulates a configurable number of games per run (defined in `config.yaml`).
*   Flexible output options:
*   **Logging:**
    *   By default, only WARNING and ERROR messages are shown on the console (stderr).
    *   Use `--debug` to see all DEBUG level messages.
    *   Use `--show-game-logs` to see INFO level play-by-play details from the game simulation on stderr, even if the overall level is WARNING.
*   **Output Files:**
    *   **YAML Mode (Default):** Saves detailed simulation results, including play-by-play logs, to a YAML file in the `logs/` directory (default: `logs/simulation_results.yaml`). This is the default behavior if `--csv` is not used and `--verbose` is not set to `False`.
    *   **CSV Mode (`--csv`):** Appends the average score for the simulated games to a specified CSV file in the `logs/` directory. Disables YAML output by default.
    *   **Force YAML (`--save-yaml`):** Can be used alongside `--csv` to force the YAML log file to be saved even when primarily outputting to CSV.
*   Supports executing simulations for:
    *   A specific lineup order provided via command-line arguments.
    *   The default lineup order defined in `config.yaml` if no specific order is provided.
*   Includes an orchestrator script (`orchestrator.py`) to automatically simulate all 9! (362,880) possible lineup permutations and aggregate results into a summary CSV file.

## Directory Structure

```bash
lineupSim/
├── data/ # Input configuration files
│ └── config.yaml
├── logs/ # Output log files (YAML and CSV formats)
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
├── .gitignore # List of irrelevant and untracked elements
└── README.md # This file
```

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
        *   `stats`: Dictionary including required metrics (`plate_appearances`, `at_bats`, `hits`, `doubles`, `triples`, `home_runs`, `walks`, `strikeouts`, `hit_by_pitch`, `extra_base_percentage`, `gb_fb_ratio`, etc.). 
        *   The order in this list defines the *default* lineup if `main.py` is run without the `--lineup` argument.

## Usage

There are two primary ways to run simulations:

### 1. Running Single Simulations (`main.py`)

Use `main.py` to simulate games for one specific lineup order (either provided via arguments or default from config) and get detailed logs or a specific output value.

**Arguments:**

*   `--lineup ID1 ID2 ... ID9` (Optional): Specify the 9 player IDs in the desired batting order. If omitted, the order from `config.yaml` is used.
*   `--csv FILENAME.csv` (Optional): Output the average score for the run to the specified CSV file (e.g., `my_results.csv`) inside the `logs/` directory. Appends if the file exists. Disables default YAML logging.
*   `--verbose True|False` (Optional): Controls default YAML logging. `True` enables it, `False` disables it. Defaults to `True` if `--csv` is not used. Overridden by `--csv` unless `--save-yaml` is also used.
*   `--debug` (Optional Flag): Enable DEBUG level console logging (stderr) for all modules.
*   `--show-game-logs` (Optional Flag): Show INFO level play-by-play game logs on stderr, even if the root logging level is WARNING.
*   `--save-yaml` (Optional Flag): Force saving the detailed YAML log file (to `logs/`) even when `--csv` is used.

**Examples:**

*   **Simulate using default lineup order (from config) with verbose YAML output:**
    ```bash
    python main.py
    ```
    (Output will be in `logs/simulation_results.yaml`. Minimal console output.)

*   **Simulate a specific lineup with YAML output:**
    ```bash
    python main.py --lineup P003 P001 P004 P002 P006 P005 P007 P008 P009
    ```
    (Output will be in `logs/simulation_results.yaml`. Minimal console output.)

*   **Simulate the default lineup, append average score to CSV (minimal console output):**
    ```bash
    python main.py --csv my_sim_results.csv
    ```
    (A row with the default lineup IDs and average score will be appended to `logs/my_sim_results.csv`. No YAML log generated by default. Average score printed to *stdout* for capture, not visible on console unless redirected.)

*   **Simulate a specific lineup, append to CSV, AND see play-by-play on console:**
    ```bash
    python main.py --lineup P001 P002 P003 P004 P005 P006 P007 P008 P009 --csv lineup_test.csv --show-game-logs
    ```
    (Row appended to `logs/lineup_test.csv`. Play-by-play shown on *stderr*. No YAML log generated.)

*   **Simulate a specific lineup, append to CSV, AND save the YAML log:**
    ```bash
    python main.py --lineup P001 P002 P003 P004 P005 P006 P007 P008 P009 --csv lineup_test.csv --save-yaml
    ```
    (Row appended to `logs/lineup_test.csv`. Full results also saved to `logs/simulation_results.yaml`. Minimal console output.)

*   **Simulate default lineup with full debug output:**
    ```bash
    python main.py --debug
    ```
    (Outputs YAML log. Shows all DEBUG messages from all modules on stderr.)

### 2. Running All Permutations (`orchestrator.py`)

Use `orchestrator.py` to automatically run simulations for *all possible* 9! (362,880) batting order permutations using the players defined in `config.yaml`. This is useful for finding the optimal lineup based on average runs scored over a season.

**How it works:**

*   Reads player IDs from `config.yaml`.
*   Generates every permutation of those 9 IDs.
*   For each permutation:
*   Calls `main.py --lineup ID1 ... ID9 --verbose False` as a subprocess.
*   Captures the average score printed to *standard output* by `main.py`.
*   Writes the lineup permutation and its average score to `logs/all_lineup_results.csv`.
*   Logs progress to the console (stderr).

**To Run:**

```bash
python orchestrator.py
```


**Output:**

*   Results are saved in `logs/all_lineup_results.csv` (overwritten if it exists).
*   Console output (stderr) shows progress for each lineup simulation.

**WARNING**: Running the orchestrator script will **take a very long** time as it simulates 362,880 * `num_games` (e.g., nearly 59 million games if `num_games` is 162). Ensure `num_games` in `config.yaml` is set appropriately for your testing needs. Consider reducing it significantly for initial tests.

## Notes & Future Improvements

*   This simulation focuses solely on the batting team's performance. Opposing pitching and defense are not dynamically factored-in beyond the assumed league-average outcomes reflected in the input player stats.

*   Baserunning logic, while enhanced, still simplifies some situations (e.g., no explicit modeling of runner speed differences beyond XBP, basic DP trigger logic, no hit-and-run, no simulation of SB/CS attempts during play).

**General ToDo**
   *   Add date and time to csv filenames
   *   Implement stealing
   *   Ability to auto-rerun N `num_games` (i.e. 100k) for top M batting orders (i.e. 1000)
   *   Periodic updates on time progressed
   *   Create simple web interface for website use
   *   Modify indicies for weighted baserunner outs
   *   Probability parameter(s) for scoring on sac flies
   *   Add arguments for number of games, number of permutations (cropped)
   *   Rename logs/ to results/ or similar. Each result set should have its own timestamped folder
   *   Upon completion, orchestrator should call a visual-generator script that will dump plots into the appropriate results folder. Argument flag to call plotter
   *   Consider separating stats from config file (i.e. player_profiles.yaml). Also consider renaming parent folder
   *   Change "lineup" in config to "roster", and replace elsewhere. Roster can contain more than 9 players, but fails if at least 9 are not listed. Come up with a way to detmine which players are selected for permutations by orchestrator.

Does not model errors explicitly.

Could be extended to include pitching stats, fielding variations, more granular baserunning decisions, weather effects, park factors, etc.

Consider using `multiprocessing` within `orchestrator.py` to significantly speed up the permutation testing on multi-core machines. Make `--cores` a command line arg.

Expanding on "granular baserunning decisions", consider implementing proper strategic baserunning that incorporates factors like runner speed, and placement of batted balls. (i.e. Mamiko Kato et al., 2025, https://journals.sagepub.com/doi/10.1177/22150218251313931). Furthermore, an accurate simulation would also incorporate tagouts on attempted "extra base" advancements.

Expanding on Website:
   *   User can upload stats, or use fake players for product preview
   *   Upon completion of simulation:
      *   Notification will be sent to user email
      *   Opportunity for user to obtain CSV results and plots
   *   Webapp will have interactable plots and visualizations
   *   WebApp will show progress of current simulation, perhaps viewable via a special userkey or login
   *   Upon initiation of simulation, params will be fetched by local server and computed on prem. Alternatively, multiple containiers can be launched on cloud provider to each process a predetermined portion of the permutation-set.

Explore means of visually representing results
