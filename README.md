# Python Baseball Simulator

This project simulates baseball games for a single team based on detailed player statistics provided in YAML configuration files. It allows for simulating individual seasons for specific lineups or running experiments across all possible lineup permutations.

## Features

*   Simulates games inning by inning for a 9-player lineup.
*   Calculates Plate Appearance outcome probabilities (1B, 2B, 3B, HR, BB, HBP, SO, Ground Out, Fly Out) based on input stats.
*   Distinguishes between Ground Outs (GO) and Fly Outs (FO) based on player GB/FB ratios.
*   Models complex baserunning scenarios, including Forced Advances, Double Plays (DP), Fielder's Choice (FC), Sacrifice Flies, Extra Base Advancement, Base Traffic
*   Simulates a configurable number of games per run (defined in `data/config.yaml`, can be overridden via `--num-games` flag).
*   Flexible output options:
*   **Logging:**
    *   By default, only WARNING and ERROR messages are shown on the console (stderr).
    *   Use `--debug` to see all DEBUG level messages.
    *   Use `--show-game-logs` to see INFO level play-by-play details from the game simulation on stderr, even if the overall level is WARNING.
*   **Output Files (saved in `results/` directory):**
    *   **Direct `main.py` Runs:**
        *   YAML logs are saved as `results/simulation_results_YYYYMMDD_HHMMSS.yaml`.
        *   CSV files specified via `--csv FILENAME.csv` are saved/appended as `results/FILENAME.csv`.
    *   **`orchestrator.py` Runs:**
        *   All results for a run are saved within a timestamped subdirectory: `results/YYYYMMDD_HHMMSS/`.
        *   The main summary CSV is saved as `results/YYYYMMDD_HHMMSS/all_lineup_results.csv`.
        *   Individual YAML logs (if `--save-yaml` is used with `main.py`, though not default for orchestrator) would also go into this subdirectory.
    *   **Options:**
        *   `--save-yaml` flag in `main.py` forces YAML generation even when using `--csv`.
*   Supports executing simulations for:
    *   A specific lineup order provided via command-line arguments.
    *   The default lineup order defined in the player data file (`data/players.yaml` by default).
*   Includes an orchestrator script (`orchestrator.py`) to automatically simulate lineup permutations and aggregate results into a summary CSV file. Supports simulating slices of permutations (`--start`, `--stop`).

## Directory Structure

```bash
lineupSim/
├── data/ # Input configuration files
│   ├── config.yaml # Main simulation parameters
│   └── players.yaml # Player roster and stats
├── results/ # Output files (YAML and CSV formats)
│   └── YYYYMMDD_HHMMSS/ # Timestamped folder for each orchestrator run
│       ├── 162_game_results.csv # Example initial run CSV (162 games)
│       └── 1000_game_results.csv # Example rerun CSV (1000 games)
│   ├── simulation_results_YYYYMMDD_HHMMSS.yaml # Example direct run YAML output
│   └── my_sim_results.csv # Example direct run CSV output
├── src/ # Source code
│   ├── __init__.py
│   ├── constants.py
│   ├── player.py
│   ├── game.py
│   ├── simulator.py
│   └── utils.py
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
    (This will install `PyYAML` and `pandas`)

## Configuration

Configuration is split into two files within the `data/` directory:

### 1. `data/config.yaml`

*   Defines simulation parameters and points to the player data file.
    *   `simulation_params`:
        *   `num_games`: Default number of games to simulate *per lineup execution*. Can be overridden by `--num-games` flag in `main.py` or `orchestrator.py`.
        *   `innings_per_game`: Typically 9.
        *   `verbose`: Default logging mode (`True` for YAML, `False` otherwise). Overridden if `--csv` is used in `main.py`.
        *   `dp_attempt_probability_on_go`: Chance a GO with runner(s) on and < 2 outs becomes a DP attempt.
        *   `double_play_runner_out_weights`: Relative weights for which *runner* (on 1B, 2B, or 3B) is the second out in a DP. Keys are base indices (0, 1, 2).
        *   `fielders_choice_out_weights`: Relative weights for who is out (Batter = -1, Runner on 1B = 0, etc.) on an FC.
    *   `player_data_file`: **Required.** Path to the YAML file containing the player roster (e.g., `data/players.yaml`).
    *   `orchestrator_params`: Settings specific to `orchestrator.py`:
        *   `auto_rerun`: (Boolean, default `False`) Whether to automatically run a more detailed simulation for the top N lineups after the initial permutation run completes.
        *   `rerun_top_n`: (Integer, default `10`) How many of the top-scoring lineups from the initial run to include in the auto-rerun.
        *   `rerun_num_games`: (Integer, default `1000`) How many games to simulate for each lineup during the auto-rerun phase.

### 2. `data/players.yaml` (Example)

*   Contains the list of players available for simulation under the `players:` key.
    *   `players`: A list of 9 players (required for orchestrator), each with:
        *   `id`: Unique alphanumeric player identifier (e.g., "P001").
        *   `name`: Player's display name.
        *   `stats`: Dictionary including required metrics (`plate_appearances`, `at_bats`, `hits`, `doubles`, `triples`, `home_runs`, `walks`, `strikeouts`, `hit_by_pitch`, `extra_base_percentage`, `gb_fb_ratio`, etc.).
        *   The order in this list defines the *default* lineup if `main.py` is run without the `--lineup` argument.

```yaml
# Example data/players.yaml
players:
  - id: "P001"
    name: "Lead Hitter"
    stats: { ... } # Full stats dictionary
  - id: "P002"
    name: "Solid Contact"
    stats: { ... }
  # ... other players ...
  - id: "P009"
    name: "Pitcher Spot (Weak Hitter)"
    stats: { ... }
```

## Usage

There are two primary ways to run simulations:

### 1. Running Single Simulations (`main.py`)

Use `main.py` to simulate games for one specific lineup order (either provided via arguments or default from `players.yaml`) and get detailed logs or a specific output value. Output files are saved in the `results/` directory.

**Arguments:**

*   `--lineup ID1 ID2 ... ID9` (Optional): Specify the 9 player IDs in the desired batting order. If omitted, the order from `data/players.yaml` is used.
*   `--csv FILENAME.csv` (Optional): Output the average score for the run to the specified CSV file (e.g., `my_results.csv`) inside the `results/` directory. Appends if the file exists. Disables default YAML logging.
*   `--num-games N` (Optional): Override the number of games per simulation specified in `config.yaml`.
*   `--verbose True|False` (Optional): Controls default YAML logging. `True` enables it, `False` disables it. Defaults to `True` if `--csv` is not used. Overridden by `--csv` unless `--save-yaml` is also used.
*   `--debug` (Optional Flag): Enable DEBUG level console logging (stderr) for all modules.
*   `--show-game-logs` (Optional Flag): Show INFO level play-by-play game logs on stderr, even if the root logging level is WARNING.
*   `--save-yaml` (Optional Flag): Force saving the detailed YAML log file (to `results/`) even when `--csv` is used. YAML filename will include a timestamp.

**Examples:**

*   **Simulate default lineup for 10 games (overriding config) with YAML output:**
    ```bash
    python main.py --num-games 10
    ```
    (Output will be saved to `results/simulation_results_YYYYMMDD_HHMMSS.yaml`. Minimal console output.)

*   **Simulate a specific lineup, append to CSV, AND save the YAML log:**
    ```bash
    python main.py --lineup P001 P002 P003 P004 P005 P006 P007 P008 P009 --csv lineup_test.csv --save-yaml
    ```
    (Row appended to `results/lineup_test.csv`. Full results also saved to `results/simulation_results_YYYYMMDD_HHMMSS.yaml`. Minimal console output.)

### 2. Running All Permutations (`orchestrator.py`)

Use `orchestrator.py` to automatically run simulations for batting order permutations using the players defined in `data/players.yaml`. This is useful for finding the optimal lineup based on average runs scored over a season.

**Arguments:**

*   `--start N` (Optional): Starting index (0-based) of permutations to simulate. Defaults to 0.
*   `--stop N` (Optional): Stopping index (exclusive) of permutations to simulate. Defaults to simulating all permutations.
*   `--num-games N` (Optional): Override the number of games per lineup for the **initial** permutation run (defaults to value in `config.yaml`).
*   `--rerun TOP_N NUM_GAMES` (Optional): Manually trigger a rerun simulation for the `TOP_N` best-performing lineups found in the initial run, simulating `NUM_GAMES` for each. This overrides the `auto_rerun` settings in `config.yaml`. Example: `--rerun 20 5000` reruns the top 20 lineups for 5000 games each.
*   `--debug` (Optional Flag): Enable DEBUG level console logging (stderr) for the orchestrator script itself.

**How it works:**

*   Reads `data/config.yaml` to find the path to the player data file.
*   Reads player IDs from the specified player data file (e.g., `data/players.yaml`).
*   Creates a timestamped directory for the run (e.g., `results/YYYYMMDD_HHMMSS/`).
*   Generates the specified slice of permutations (using `--start` and `--stop`).
*   For each permutation in the slice:
    *   Calls `main.py` as a subprocess with the lineup, the initial `num_games`, and the output directory.
    *   Captures the average score printed to standard output by `main.py`.
    *   Writes the lineup permutation and its average score to `results/YYYYMMDD_HHMMSS/[initial_num_games]_game_results.csv`.
*   Logs progress to the console (stderr).
*   **Auto-Rerun (Optional):**
    *   If `auto_rerun` is `True` in `config.yaml` or `--rerun` is specified:
        *   Reads the initial results CSV file.
        *   Identifies the top `rerun_top_n` lineups based on `AverageScore`.
        *   For each of these top lineups:
            *   Calls `main.py` again as a subprocess with the lineup, the `rerun_num_games`, and the output directory.
            *   Captures the new average score.
            *   Writes the lineup and its new average score to `results/YYYYMMDD_HHMMSS/[rerun_num_games]_game_results.csv`.

**To Run:**

*   **Run all permutations using config `num_games`:**
    ```bash
    python orchestrator.py
    ```
*   **Run the first 100 permutations using config `num_games`:**
    ```bash
    python orchestrator.py --stop 100
    ```
*   **Run permutations 1000 to 1999 (1000 total) using config `num_games`:**
    ```bash
    python orchestrator.py --start 1000 --stop 2000
    ```
*   **Run all permutations, simulating 50 games per lineup initially:**
    ```bash
    python orchestrator.py --num-games 50
    ```
*   **Run all permutations (162 games default), then manually rerun the top 20 lineups for 1000 games each:**
    ```bash
    python orchestrator.py --rerun 20 1000
    ```

**Output:**

*   Initial results are saved in `results/YYYYMMDD_HHMMSS/[initial_num_games]_game_results.csv`.
*   If a rerun is performed, those results are saved in `results/YYYYMMDD_HHMMSS/[rerun_num_games]_game_results.csv`.
*   Console output (stderr) shows progress for each lineup simulation in both phases.

**WARNING**: Running the orchestrator script for all permutations will **take a very long** time as it simulates `num_permutations` * `num_games` (e.g., 362,880 * 162 = nearly 59 million games). Use `--start`/`--stop` and consider reducing `num_games` (either in config or via `--num-games`) for testing.

## Notes & Future Improvements

*   This simulation focuses solely on the batting team's performance. Opposing pitching and defense are not dynamically factored-in beyond the assumed league-average outcomes reflected in the input player stats.

*   Baserunning logic, while enhanced, still simplifies some situations (e.g., no explicit modeling of runner speed differences beyond XBP, basic DP trigger logic, no hit-and-run, no simulation of SB/CS attempts during play).

**General ToDo**
   *   Implement stealing
   *   Periodic progress updates during long orchestrator runs (e.g., time elapsed/remaining estimate).
   *   Create simple web interface for website use
   *   (Consider) Modify indices for weighted baserunner outs (index at 0 instead of -1)
   *   Probability parameter(s) for scoring on sac flies
   *   Upon completion, orchestrator should call a visual-generator script that will dump plots into the appropriate results folder. Argument flag to call plotter
   *   Create Roster in players.yaml. Roster is a subset of player IDs listed in Players (roster pool). The "roster" is the specific subset of players that will be permutated. Roster can contain more than 9 players, but fails if at least 9 unique IDs are not listed. Important to cross-check roster with player list before running program.

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
