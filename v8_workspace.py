# Copyright Mikael K. Aboagye & WD Studios Corp.
#
# Advanced V8 Build Script for Windows, Linux, and FreeBSD
#
# This script automates building V8, including support for custom forks and MSVC-specific flags.
#
# Prerequisites:
# 1.  General:
#     - Git
#     - Python 3
#
# 2.  Windows:
#     - Windows 10 or later (64-bit).
#     - Visual Studio 2022 with the "Desktop development with C++" workload installed.
#       Ensure the English language pack is installed.
#
# 3.  Linux (Debian/Ubuntu):
#     - sudo apt-get install build-essential clang git python3
#
# 4.  FreeBSD:
#     - pkg install devel/git python3 devel/clang
#
# How to run:
# 1.  Save this script as a Python file (e.g., `build_v8_advanced.py`).
# 2.  Open a terminal or command prompt. For Windows, this MUST be run with
#     **Administrator privileges**. A Developer Command Prompt is also recommended.
# 3.  Examples:
#     - Default build (official V8, static, release):
#       `python3 build_v8_advanced.py`
#
#     - Build without the Rust toolchain dependency:
#       `python3 build_v8_advanced.py --no-rust`
#

import os
import subprocess
import sys
import argparse
import ctypes

# --- Configuration ---
# The URL for the depot_tools repository.
DEPOT_TOOLS_URL = "https://chromium.googlesource.com/chromium/tools/depot_tools.git"

def run_command(command, working_dir=None, env=None):
    """
    Executes a shell command and prints its output in real-time.
    Exits the script if the command fails.
    """
    print(f"--- Running command: {' '.join(command)} in '{working_dir}'")
    try:
        command_str = ' '.join(command)
        process = subprocess.Popen(
            command_str,
            cwd=working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            shell=True,
            env=env
        )
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip(), flush=True)

        if process.returncode != 0:
            print(f"--- Command failed with exit code {process.returncode}")
            sys.exit(process.returncode)

    except FileNotFoundError:
        print(f"--- Error: Command not found - {command[0]}. Is it in your PATH?")
        sys.exit(1)
    except Exception as e:
        print(f"--- An unexpected error occurred: {e}")
        sys.exit(1)
    print(f"--- Command finished successfully.")

def check_admin_privileges():
    """Checks for administrator privileges on Windows and exits if not found."""
    if sys.platform != "win32":
        return # Not applicable for non-Windows platforms
    try:
        is_admin = (os.getuid() == 0)
    except AttributeError:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    
    if not is_admin:
        print("\n" + "="*80)
        print("--- ERROR: Administrator privileges are required.")
        print("Please re-run this script from a command prompt with Administrator rights.")
        print("Right-click your Command Prompt/Terminal icon and select 'Run as administrator'.")
        print("="*80)
        sys.exit(1)
    print("--- Administrator privileges confirmed.")

def main():
    """Main function to orchestrate the build process."""
    check_admin_privileges()

    # --- Platform Detection ---
    is_windows = sys.platform == "win32"
    
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description="WD Studios's V8 Build Script that supports all platforms. (non-console-version)",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--workspace', type=str, default='v8_build', help='The directory where all work will be done.')
    parser.add_argument('--build-type', type=str, choices=['static', 'dll'], default='static', help='Build a static library (.lib/.a) or shared library (.dll/.so).')
    parser.add_argument('--config', type=str, choices=['release', 'debug'], default='release', help='Build configuration.')
    parser.add_argument('--gn-args-file', type=str, help='Path to a file with additional GN arguments.')
    parser.add_argument('--v8-fork-url', type=str, help='URL of a custom V8 git repository to build.')
    parser.add_argument('--v8-fork-branch', type=str, default='main', help='Branch, tag, or commit to check out from the custom fork.')
    parser.add_argument('--msvc', action='store_true', help='On Windows, add GN flags to explicitly use the MSVC toolchain instead of clang-cl.')
    parser.add_argument('--no-rust', action='store_true', help='Disable Rust toolchain download and dependency.')
    parser.add_argument('--no-custom-cxx', action='store_true', help='Disable custom C++ toolchain download and dependency. The custom C++ toolchain causes problems with Windows builds.')
    args = parser.parse_args()
    
    V8_BASE_DIR = os.path.abspath(args.workspace)
    
    print("--- V8 Build Configuration ---")
    for arg, value in vars(args).items():
        print(f"  {arg.replace('_', '-'):<15}: {value}")
    print("-" * 30)

    # 1. Create and set up workspace and depot_tools
    if not os.path.exists(V8_BASE_DIR):
        os.makedirs(V8_BASE_DIR)

    depot_tools_dir = os.path.join(V8_BASE_DIR, "depot_tools")
    if not os.path.exists(depot_tools_dir):
        print("--- Cloning depot_tools...")
        run_command(["git", "clone", DEPOT_TOOLS_URL, depot_tools_dir])
    else:
        print("--- depot_tools already exists.")

    os.environ["PATH"] = f"{depot_tools_dir}{os.pathsep}{os.environ['PATH']}"
    if is_windows:
        os.environ["DEPOT_TOOLS_WIN_TOOLCHAIN"] = "0"
    
    print("--- Bootstrapping depot_tools...")
    run_command(["gclient"], working_dir=V8_BASE_DIR)

    # 2. Fetch V8 source code
    v8_src_dir = os.path.join(V8_BASE_DIR, "v8")
    if not os.path.exists(v8_src_dir):
        print("--- Fetching official V8 source code (base)...")
        run_command(["fetch", "v8"], working_dir=V8_BASE_DIR)
    else:
        print("--- V8 source directory already exists.")

    # 3. Handle custom fork if specified
    if args.v8_fork_url:
        print(f"--- Integrating custom V8 fork from: {args.v8_fork_url}")
        # Check if remote already exists
        try:
            subprocess.check_output(["git", "remote", "get-url", "fork"], cwd=v8_src_dir, stderr=subprocess.STDOUT)
            print("--- 'fork' remote already exists. Setting new URL.")
            run_command(["git", "remote", "set-url", "fork", args.v8_fork_url], working_dir=v8_src_dir)
        except subprocess.CalledProcessError:
            print("--- Adding 'fork' remote.")
            run_command(["git", "remote", "add", "fork", args.v8_fork_url], working_dir=v8_src_dir)
        
        print("--- Fetching from custom fork...")
        run_command(["git", "fetch", "fork"], working_dir=v8_src_dir)
        print(f"--- Checking out branch/tag: {args.v8_fork_branch}")
        run_command(["git", "checkout", f"fork/{args.v8_fork_branch}"], working_dir=v8_src_dir)
    else:
        # Default to a recent known tag if no fork is specified.
        run_command(["git", "checkout", "12.1.285.27"], working_dir=v8_src_dir)

    print("--- Synchronizing dependencies with gclient sync...")
    run_command(["gclient", "sync"], working_dir=v8_src_dir)

    # 4. Generate build files with GN
    output_path = f"out.gn/x64.{args.config}"
    print(f"--- Generating build files in: {output_path}")
    
    gn_args = [
        f'is_debug={str(args.config == "debug").lower()}',
        'target_cpu=""x64""',
        'v8_use_external_startup_data=false',
        'treat_warnings_as_errors=false',
    ]
    
    if args.no_rust:
        print("--- Disabling Rust toolchain dependency.")
        gn_args.append('v8_enable_rust=false')

    if args.build_type == 'static':
        gn_args.extend(['is_component_build=false', 'v8_monolithic=true'])
        build_target = 'v8_monolithic'
    else:  # dll or .so
        gn_args.extend(['is_component_build=true', 'v8_monolithic=false'])
        build_target = 'v8'

    if is_windows and args.msvc:
        print("--- Applying MSVC-specific GN flags...")
        gn_args.extend(['is_clang=false', 'v8_win_clang=false'])
    elif not is_windows:
        gn_args.append('is_clang=true')

    if args.gn_args_file and os.path.exists(args.gn_args_file):
        print(f"--- Reading custom GN args from {args.gn_args_file}")
        with open(args.gn_args_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    gn_args.append(line)

    gn_command_str = f'gn gen {output_path} --args="{" ".join(gn_args)}"'
    print(f"--- Using GN command: {gn_command_str}")
    subprocess.run(gn_command_str, check=True, cwd=v8_src_dir, shell=True)

    # 5. Build V8 with Ninja
    print(f"--- Building V8 target '{build_target}' with Ninja...")
    run_command(["ninja", "-C", output_path, build_target], working_dir=v8_src_dir)

    # 6. Final output message
    print(f"\n--- V8 ({args.build_type} / {args.config} build) Process Completed Successfully! ---")
    final_output_dir = os.path.join(v8_src_dir, output_path)
    print(f"Build artifacts are located in: {final_output_dir}")
    print(f"Include headers are located at: {os.path.join(v8_src_dir, 'include')}")

if __name__ == "__main__":
    main()
