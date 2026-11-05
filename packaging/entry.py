"""Point d'entrée de l'exécutable (PyInstaller)."""

import sys

from sbs.app import main

if __name__ == "__main__":
    sys.exit(main())
