#
# V8 Build Script for Windows, Linux, and FreeBSD
#
# This script automates the process of building a specific version of the V8 JavaScript engine.
# It can produce a monolithic static library or a component build (shared library),
# in either release or debug configurations.
#
# Prerequisites:
# 1.  General:
#     - Git
#     - Python 3
#
# 2.  Windows:
#     - Windows 10 or later (64-bit).
#     - Visual Studio 2022 (or 2019) with the "Desktop development with C++" workload installed.
#       Ensure the English language pack is installed.
#
# 3.  Linux (Debian/Ubuntu):
#     - sudo apt-get install build-essential clang git python3
#
# 4.  FreeBSD:
#     - pkg install devel/git python3 devel/clang
#
# How to run:
# 1.  Save this script as a Python file (e.g., `build_v8.py`).
# 2.  Open a terminal or command prompt and navigate to where you saved the file.
# 3.  For a static release library (default): `python3 build_v8.py`
# 4.  For a debug shared library build: `python3 build_v8.py --build-type dll --config debug`
# 5.  To specify a custom workspace: `python3 build_v8.py --workspace /path/to/my_v8_build`
# 6.  To provide custom GN arguments from a file: `python3 build_v8.py --gn-args-file my_args.txt`
#

import os
import subprocess
import sys
import argparse

# --- Configuration ---
# The specific version of V8 you want to build.
V8_VERSION = "12.1.3"

# The URL for the depot_tools repository.
DEPOT_TOOLS_URL = "https://chromium.googlesource.com/chromium/tools/depot_tools.git"

def run_command(command, working_dir=None, env=None):
    """
    Executes a shell command and prints its output in real-time.
    Exits the script if the command fails.
    """
    print(f"--- Running command: {' '.join(command)}")
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

def main():
    """Main function to orchestrate the build process."""

    # --- Platform Detection ---
    is_windows = sys.platform == "win32"
    is_linux = sys.platform.startswith("linux")
    is_freebsd = sys.platform.startswith("freebsd")
    
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description="Build V8 on Windows, Linux, and FreeBSD.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        '--workspace',
        type=str,
        default='v8_build',
        help='The directory where all work will be done. Defaults to "./v8_build"'
    )
    parser.add_argument(
        '--build-type',
        type=str,
        choices=['static', 'dll'],
        default='static',
        help='The type of build to produce:\n'
             '"static" (monolithic .lib/.a, default)\n'
             '"dll"    (component/shared .dll/.so)'
    )
    parser.add_argument(
        '--config',
        type=str,
        choices=['release', 'debug'],
        default='release',
        help='The build configuration:\n'
             '"release" (optimized, default)\n'
             '"debug"   (includes debug symbols)'
    )
    parser.add_argument(
        '--gn-args-file',
        type=str,
        help='Path to a file containing additional GN arguments, one per line.\n'
             'Example line: v8_enable_i18n_support=false'
    )
    args = parser.parse_args()
    
    V8_BASE_DIR = os.path.abspath(args.workspace)
    print(f"--- Chrome Dev Tools Frontend Builder. Copyright Mikael K. Aboagye & WD Studios Corp. All Rights Reserved. ---")
    print(f"--- Starting V8 Build Process ---")
    print(f"           OS: {sys.platform}")
    print(f"    Workspace: {V8_BASE_DIR}")
    print(f"   Build Type: {args.build_type}")
    print(f"Configuration: {args.config}")
    if args.gn_args_file:
        print(f" Custom Args.: {os.path.abspath(args.gn_args_file)}")


    # 1. Create the main directory for the build process
    if not os.path.exists(V8_BASE_DIR):
        print(f"--- Creating base directory: {V8_BASE_DIR}")
        os.makedirs(V8_BASE_DIR)

    # 2. Set up depot_tools
    depot_tools_dir = os.path.join(V8_BASE_DIR, "depot_tools")
    if not os.path.exists(depot_tools_dir):
        print("--- Cloning depot_tools...")
        run_command(["git", "clone", DEPOT_TOOLS_URL, depot_tools_dir])
    else:
        print("--- depot_tools already exists. Skipping clone.")

    # 3. Add depot_tools to the PATH for this script's execution
    original_path = os.environ["PATH"]
    os.environ["PATH"] = f"{depot_tools_dir}{os.pathsep}{original_path}"
    
    # Set Windows-specific environment variable
    if is_windows:
        os.environ["DEPOT_TOOLS_WIN_TOOLCHAIN"] = "0"
    
    print("--- Bootstrapping depot_tools...")
    run_command(["gclient"], working_dir=V8_BASE_DIR)

    # 4. Fetch the V8 source code
    v8_src_dir = os.path.join(V8_BASE_DIR, "v8")
    if not os.path.exists(v8_src_dir):
        print("--- Fetching V8 source code...")
        # On non-Windows, fetch might need python explicitly. The bootstrapped one should be in PATH.
        fetch_cmd = "fetch.py" if is_windows else "python3 `which fetch.py`"
        run_command([fetch_cmd, "v8"], working_dir=V8_BASE_DIR)

    else:
        print("--- V8 source directory already exists. Skipping fetch.")

    # 5. Checkout the specific version tag and sync
    print(f"--- Checking out V8 version: {V8_VERSION}")
    run_command(["git", "checkout", V8_VERSION], working_dir=v8_src_dir)

    print("--- Synchronizing dependencies with gclient sync...")
    run_command(["gclient", "sync"], working_dir=v8_src_dir)

    # 7. Generate build files with GN
    print(f"--- Generating build files for x64/{args.config} ({args.build_type} build)...")
    
    output_path = f"out.gn/x64.{args.config}"
    build_target = ""
    
    gn_args = [
        f'is_debug={str(args.config == "debug").lower()}',
        'target_cpu="x64"',
        'v8_use_external_startup_data=false',
        'treat_warnings_as_errors=false'
    ]
    
    if is_linux or is_freebsd:
        gn_args.append('is_clang=true')
    
    if is_freebsd:
        gn_args.append('target_os="freebsd"')

    if args.build_type == 'static':
        gn_args.extend(['is_component_build=false', 'v8_monolithic=true'])
        build_target = 'v8_monolithic'
    else:  # dll or .so
        gn_args.extend(['is_component_build=true', 'v8_monolithic=false'])
        build_target = 'v8'

    # Add custom arguments from file if provided
    if args.gn_args_file:
        gn_args_file_path = os.path.abspath(args.gn_args_file)
        if os.path.exists(gn_args_file_path):
            print(f"--- Reading custom GN args from {gn_args_file_path}")
            with open(gn_args_file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        gn_args.append(line)
        else:
            print(f"--- WARNING: GN args file not found at {gn_args_file_path}. Skipping.")

    gn_command_str = f'gn gen {output_path} --args="{" ".join(gn_args)}"'
    print(f"--- Using GN command: {gn_command_str}")
    subprocess.run(gn_command_str, check=True, cwd=v8_src_dir, shell=True)

    # 8. Build V8 with Ninja
    print(f"--- Building V8 target '{build_target}' with Ninja...")
    run_command(["ninja", "-C", output_path, build_target], working_dir=v8_src_dir)

    # 9. Final output message
    print(f"\n--- V8 ({args.build_type} / {args.config} build) Process Completed Successfully! ---")
    output_dir = os.path.join(v8_src_dir, output_path)
    
    if args.build_type == 'static':
        print(f"The built static library can be found at:")
        if is_windows:
            lib_path = os.path.join(output_dir, "obj", "v8_monolithic.lib")
        else: # Linux/FreeBSD
            lib_path = os.path.join(output_dir, "obj", "libv8_monolithic.a")
        print(lib_path)
    else:  # dll or .so
        print("The built shared library and related files can be found in:")
        print(output_dir)
        if is_windows:
            print(f"  - {os.path.join(output_dir, 'v8.dll')}")
            print(f"  - {os.path.join(output_dir, 'v8.dll.lib')}")
        else: # Linux/FreeBSD
            print(f"  - {os.path.join(output_dir, 'libv8.so')}")
        print("\nOther required files (like .dat snapshot files) are also in that directory.")

    print("\nInclude headers are located at:")
    print(os.path.join(v8_src_dir, "include"))

if __name__ == "__main__":
    main()
