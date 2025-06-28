import os
import subprocess
import sys
import platform
import shutil
import argparse

# --- Configuration (Relative Names) ---
# These are now relative names; the full paths will be built inside the workspace.
DEPOT_TOOLS_SUBDIR = "depot_tools"
DEVTOOLS_PARENT_SUBDIR = "devtools"
DEVTOOLS_FRONTEND_REPO_SUBDIR = "devtools-frontend"

def run_command(command, working_dir):
    """
    Runs a command in a specified directory with detailed logging and error handling.
    Raises an exception on failure.
    """
    print(f"\n--- Running Command: {' '.join(command)}")
    print(f"--- In Directory: {os.path.abspath(working_dir)}")
    try:
        # Use shell=True on Windows because many depot_tools commands are batch files.
        use_shell = platform.system() == "Windows"
        process = subprocess.Popen(
            command,
            cwd=working_dir,
            shell=use_shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=os.environ # Explicitly pass the current environment
        )

        # Stream the output in real-time.
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
        
        process.stdout.close()
        return_code = process.wait()

        if return_code:
            # Raise an exception that the main function can catch to trigger cleanup.
            raise subprocess.CalledProcessError(return_code, command)
            
        print(f"--- Command finished successfully.")

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"\n[ERROR] Command failed: {' '.join(command)}", file=sys.stderr)
        print(f"[ERROR] In directory: {os.path.abspath(working_dir)}", file=sys.stderr)
        # Re-raise the exception to be handled by the main try...except block.
        raise e

def check_prerequisites(workspace_dir):
    """
    Checks if Git and npm are installed on the system.
    """
    print("--- Checking for prerequisites (Git, npm)...")
    try:
        run_command(["git", "--version"], workspace_dir)
        run_command(["npm", "--version"], workspace_dir)
    except Exception as e:
        print("[ERROR] Git and/or npm are not installed or not in your PATH.", file=sys.stderr)
        print("Please install them before running this script.", file=sys.stderr)
        raise e
    print("--- Prerequisites found.")

def check_environment(workspace_dir):
    """
    Verifies that the depot_tools environment is correctly set up.
    """
    print("\n--- Verifying depot_tools environment...")
    # Commands to check for. On Windows, they are .bat files.
    commands_to_check = ["gclient", "fetch", "npm", "gn", "autoninja"]
    if platform.system() == "Windows":
        # Adjust for windows command extensions
        win_cmds = []
        for cmd in commands_to_check:
            if cmd == 'npm':
                win_cmds.append('npm.cmd')
            else:
                win_cmds.append(f'{cmd}.bat')
        commands_to_check = win_cmds
    
    for cmd in commands_to_check:
        try:
            run_command(["where" if platform.system() == "Windows" else "which", cmd], workspace_dir)
        except Exception as e:
            print(f"[ERROR] Environment check failed. Could not find '{cmd}'.", file=sys.stderr)
            print("[ERROR] Ensure depot_tools was cloned correctly and the PATH is set.", file=sys.stderr)
            raise e
    print("--- Environment sanity check passed.")

def check_path_length(workspace_dir):
    """
    On Windows, warns the user if the workspace path is excessively long.
    """
    if platform.system() == "Windows":
        path = os.path.abspath(workspace_dir)
        # MAX_PATH is 260, but we'll warn sooner.
        if len(path) > 150:
            print("\n------------------------- WARNING -------------------------")
            print("Your workspace path is very long:")
            print(path)
            print("Windows and some build tools have issues with paths longer")
            print("than 260 characters. If the build fails, please try")
            print("a shorter workspace path (e.g., C:\\build).")
            print("---------------------------------------------------------")

def main():
    """
    Main function to orchestrate the entire checkout and build process.
    Includes cleanup logic to wipe the workspace on any failure.
    """
    parser = argparse.ArgumentParser(description="Builds Chrome DevTools Frontend in a dedicated workspace.")
    parser.add_argument(
        '--workspace', 
        default='devtools_workspace', 
        help='The directory to use as the workspace. All files will be created here. Defaults to "./devtools_workspace"'
    )
    args = parser.parse_args()

    workspace_dir = os.path.abspath(args.workspace)
    depot_tools_dir = os.path.join(workspace_dir, DEPOT_TOOLS_SUBDIR)
    devtools_parent_dir = os.path.join(workspace_dir, DEVTOOLS_PARENT_SUBDIR)
    print(f"--- Chrome Dev Tools Frontend Builder. Copyright Mikael K. Aboagye & WD Studios Corp. All Rights Reserved. ---")
    print(f"--- Starting Chrome DevTools Frontend Build in Workspace: {workspace_dir} ---")
    
    build_succeeded = False

    try:
        os.makedirs(workspace_dir, exist_ok=True)
        check_path_length(workspace_dir)
        check_prerequisites(workspace_dir)

        # Clone depot_tools if it doesn't exist. This step is a prerequisite.
        if not os.path.exists(depot_tools_dir):
            run_command(["git", "clone", "https://chromium.googlesource.com/chromium/tools/depot_tools.git", depot_tools_dir], workspace_dir)
        else:
            print(f"\n--- Skipping clone, '{depot_tools_dir}' already exists.")

        print("\n--- Setting up environment variables...")
        os.environ["PATH"] = depot_tools_dir + os.pathsep + os.environ["PATH"]
        if platform.system() == "Windows":
            os.environ["DEPOT_TOOLS_WIN_TOOLCHAIN"] = "0"
        
        check_environment(workspace_dir)

        # Step 1 from docs: `mkdir devtools`
        if not os.path.exists(devtools_parent_dir):
            os.makedirs(devtools_parent_dir)

        # Step 2 & 3 from docs: `cd devtools`, `fetch devtools-frontend`
        # The 'fetch' command handles the clone and the initial `gclient sync`.
        frontend_repo_path = os.path.join(devtools_parent_dir, DEVTOOLS_FRONTEND_REPO_SUBDIR)
        if not os.path.exists(frontend_repo_path):
            run_command(["fetch", "devtools-frontend"], devtools_parent_dir)
        else:
            print(f"\n--- Skipping fetch, '{frontend_repo_path}' already exists.")
            print("--- Assuming existing checkout is valid. If build fails, please use a clean workspace.")
        
        # The working directory for build commands is the repository itself.
        work_dir = frontend_repo_path
        
        # Run npm install as per best practices.
        run_command(["npm", "install"], work_dir)

        # **FIX:** Bypass the failing `npm run build` script and use the core build tools directly.
        # This is a more robust way to build and avoids issues with the npm wrapper.
        # 1. Explicitly generate the build files with `gn`.
        run_command(["gn", "gen", "out/Default"], work_dir)

        # 2. Compile the code using `autoninja`.
        run_command(["autoninja", "-C", "out/Default"], work_dir)

        build_succeeded = True
        build_artifacts_path = os.path.join(work_dir, "out", "Default", "gen", "front_end")
        print("\n-------------------------------------------")
        print("✅ Build process completed successfully!")
        print(f"Build artifacts are located in: {build_artifacts_path}")
        print("-------------------------------------------")

    except Exception:
        print("\n[FATAL] A step in the build process failed.", file=sys.stderr)
    
    finally:
        if not build_succeeded:
            print(f"\n--- Build failed. Cleaning up workspace: {workspace_dir}")
            shutil.rmtree(workspace_dir, ignore_errors=True)
            print("--- Cleanup complete. Exiting script.")
            sys.exit(1)

if __name__ == "__main__":
    main()
