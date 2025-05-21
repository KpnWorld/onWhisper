# replit.nix controls the environment and dependencies manually.
{ pkgs }: 

pkgs.mkShell {
  buildInputs = [
    pkgs.python39
    pkgs.python39Packages.pip
    pkgs.python39Packages.aiohttp
    pkgs.python39Packages.python_dotenv
    # Add any other Python packages your bot needs here:
    # e.g. pkgs.python39Packages.sqlite  (if needed)
  ];

  shellHook = ''
    # Install your dependencies manually in the venv if not already installed
    if [ ! -d venv ]; then
      python3 -m venv venv
      source venv/bin/activate
      pip install -r requirements.txt
    fi
  '';
}
# This file is used to create a development environment for your Discord bot using Nix.
# It sets up a shell with Python 3.9 and installs the necessary packages.